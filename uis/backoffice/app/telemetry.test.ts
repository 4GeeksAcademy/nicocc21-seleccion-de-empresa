import { afterEach, beforeEach, describe, expect, it, jest } from "@jest/globals";
import { TelemetryService, track, type ConfirmedTelemetryEvent } from "./telemetry";
import { NavigationTelemetry, navigationTelemetry, observeInventoryTelemetry, sectionForPath, WorkflowTelemetry } from "./telemetry-instrumentation";
import { createInboundOrder, fetchProducts } from "./inventory/lib";
import * as authClient from "../../../src/auth/auth-client";

const originalWindow = Object.getOwnPropertyDescriptor(globalThis, "window");

let service: TelemetryService;
let fetchMock: jest.MockedFunction<typeof fetch>;
let beaconMock: jest.MockedFunction<Navigator["sendBeacon"]>;

function visit(): void {
  service.track("section_viewed", { section_code: "inventory_products" });
}

function sentEvents(call = 0): Record<string, unknown>[] {
  return JSON.parse(fetchMock.mock.calls[call][1]?.body as string).events;
}

beforeEach(() => {
  jest.useFakeTimers({ doNotFake: ["queueMicrotask"] });
  jest.setSystemTime(new Date("2026-10-15T12:00:00Z"));
  fetchMock = jest.fn<typeof fetch>().mockResolvedValue(new Response(null, { status: 200 }));
  globalThis.fetch = fetchMock;
  beaconMock = jest.fn<Navigator["sendBeacon"]>().mockReturnValue(true);
  Object.defineProperty(globalThis, "navigator", { configurable: true, value: { sendBeacon: beaconMock } });
  service = new TelemetryService("http://localhost:8000/telemetry/events");
  service.start();
});

afterEach(() => {
  service.stop();
  jest.restoreAllMocks();
  jest.useRealTimers();
  if (originalWindow) Object.defineProperty(globalThis, "window", originalWindow);
  else Reflect.deleteProperty(globalThis, "window");
});

describe("cola y lotes", () => {
  it("encola sin enviar inmediatamente y usa el timestamp de captura", async () => {
    visit();
    expect(fetchMock).not.toHaveBeenCalled();
    await jest.advanceTimersByTimeAsync(5000);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(sentEvents()[0].timestamp).toBe("2026-10-15T12:00:00.000Z");
    expect(service.getDiagnostics().queued).toBe(0);
  });

  it("envia un solo lote al llegar a veinte eventos", async () => {
    for (let index = 0; index < 20; index += 1) visit();
    expect(fetchMock).not.toHaveBeenCalled();
    await jest.advanceTimersByTimeAsync(0);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(sentEvents()).toHaveLength(20);
    const body = fetchMock.mock.calls[0][1]?.body as string;
    expect(new TextEncoder().encode(body).byteLength).toBeLessThanOrEqual(64 * 1024);
  });

  it("no envia dos peticiones normales simultaneas ni pierde eventos nuevos", async () => {
    let resolveRequest!: (response: Response) => void;
    fetchMock.mockImplementationOnce(() => new Promise((resolve) => { resolveRequest = resolve; }));
    visit();
    const pending = service.flush();
    visit();
    await service.flush();
    expect(fetchMock).toHaveBeenCalledTimes(1);
    resolveRequest(new Response(null, { status: 200 }));
    await pending;
    expect(service.getDiagnostics().queued).toBe(1);
    await jest.advanceTimersByTimeAsync(5000);
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("mantiene la cola acotada incluso mientras hay un lote en vuelo", async () => {
    fetchMock.mockImplementation(() => new Promise(() => {}));
    visit();
    void service.flush();
    for (let index = 0; index < 250; index += 1) visit();
    expect(service.getDiagnostics()).toEqual({ queued: 200, discarded: 51 });
    await jest.advanceTimersByTimeAsync(0);
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("descarta propiedades ajenas a la allowlist antes de encolar", async () => {
    const input = { section_code: "inventory_products" as const, email: "private@example.com" };
    service.track("section_viewed", input);
    input.email = "changed@example.com";
    await service.flush();
    expect(sentEvents()[0].properties).toEqual({ section_code: "inventory_products" });
    expect(fetchMock.mock.calls[0][1]?.body).not.toContain("example.com");
  });

  it("rechaza valores no controlados e identidades con email", () => {
    expect(service.track("section_viewed", { section_code: "inventory_products" }, { userId: "private@example.com" })).toBe(false);
    expect(service.track("workflow_started", { workflow_id: "invalid", workflow_type: "inventory_inbound" })).toBe(false);
    expect(service.getDiagnostics().queued).toBe(0);
  });

  it("construye los cuatro eventos frontend con correlacion y sesion comun", async () => {
    const requestId = crypto.randomUUID();
    const workflowId = crypto.randomUUID();
    visit();
    service.track("workflow_started", { workflow_id: workflowId, workflow_type: "inventory_inbound" }, { requestId });
    service.track("workflow_cancelled", { workflow_id: workflowId, workflow_type: "inventory_inbound", step_code: "form" }, { requestId });
    service.track("frontend_error_detected", { error_code: "UNHANDLED_ERROR", section_code: "inventory_orders", release_version: "1.0.0" });
    await service.flush();
    const events = sentEvents();
    expect(events).toHaveLength(4);
    expect(new Set(events.map((event) => event.eventId)).size).toBe(4);
    expect(new Set(events.map((event) => event.sessionId)).size).toBe(1);
    expect(events[1].requestId).toBe(requestId);
    expect(events[2].requestId).toBe(requestId);
    expect(events[1].properties).toEqual({ workflow_id: workflowId, workflow_type: "inventory_inbound" });
    expect(events[2].properties).toEqual({ workflow_id: workflowId, workflow_type: "inventory_inbound", step_code: "form" });
    expect(events.every((event) => event.userId === null)).toBe(true);
  });

  it("no captura ni programa envios sin endpoint", () => {
    service.stop();
    service = new TelemetryService("");
    service.start();
    expect(service.track("section_viewed", { section_code: "dashboard" })).toBe(false);
    expect(jest.getTimerCount()).toBe(0);
  });
});

describe("reintentos", () => {
  it.each([500, 503])("reintenta respuestas HTTP %i", async (status) => {
    fetchMock.mockResolvedValueOnce(new Response(null, { status }));
    visit();
    await service.flush();
    await jest.advanceTimersByTimeAsync(1000);
    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(service.getDiagnostics().queued).toBe(0);
  });

  it("conserva IDs, timestamp y contenido despues de un fallo de red", async () => {
    fetchMock.mockRejectedValueOnce(new TypeError("offline"));
    visit();
    await service.flush();
    const original = fetchMock.mock.calls[0][1]?.body;
    visit();
    await jest.advanceTimersByTimeAsync(1000);
    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(fetchMock.mock.calls[1][1]?.body).toBe(original);
    expect(service.getDiagnostics().queued).toBe(1);
  });

  it("descarta el lote tras cinco intentos sin bloquear el siguiente", async () => {
    fetchMock.mockRejectedValue(new TypeError("offline"));
    visit();
    await service.flush();
    await jest.advanceTimersByTimeAsync(16000);
    expect(fetchMock).toHaveBeenCalledTimes(5);
    expect(service.getDiagnostics()).toEqual({ queued: 0, discarded: 1 });
    fetchMock.mockResolvedValue(new Response(null, { status: 200 }));
    visit();
    await service.flush();
    expect(service.getDiagnostics().queued).toBe(0);
  });

  it("respeta Retry-After de un 429 incluso al vencer el intervalo", async () => {
    fetchMock.mockResolvedValueOnce(new Response(null, { status: 429, headers: { "Retry-After": "12" } }));
    visit();
    await service.flush();
    await jest.advanceTimersByTimeAsync(11999);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    service.flushOnExit();
    expect(beaconMock).not.toHaveBeenCalled();
    await jest.advanceTimersByTimeAsync(1);
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("respeta Retry-After expresado como fecha HTTP", async () => {
    const retryAt = new Date(Date.now() + 12000).toUTCString();
    fetchMock.mockResolvedValueOnce(new Response(null, { status: 429, headers: { "Retry-After": retryAt } }));
    visit();
    await service.flush();
    await jest.advanceTimersByTimeAsync(11999);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    await jest.advanceTimersByTimeAsync(1);
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it.each([400, 401, 403, 413, 422])("no reintenta un error HTTP %i", async (status) => {
    fetchMock.mockResolvedValue(new Response(null, { status }));
    visit();
    await service.flush();
    await jest.advanceTimersByTimeAsync(20000);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(service.getDiagnostics()).toEqual({ queued: 0, discarded: 1 });
  });

  it("aborta peticiones bloqueadas y permite el reintento", async () => {
    fetchMock.mockImplementationOnce((_url, options) => new Promise((_resolve, reject) => {
      options?.signal?.addEventListener("abort", () => reject(new DOMException("timeout", "AbortError")));
    }));
    visit();
    const pending = service.flush();
    await jest.advanceTimersByTimeAsync(10000);
    await pending;
    await jest.advanceTimersByTimeAsync(1000);
    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(service.getDiagnostics().queued).toBe(0);
  });
});

describe("salida y ciclo de vida", () => {
  it("usa beacon y retira solo eventos aceptados por el navegador", () => {
    visit();
    beaconMock.mockReturnValueOnce(false);
    service.flushOnExit();
    expect(service.getDiagnostics().queued).toBe(1);
    service.flushOnExit();
    expect(service.getDiagnostics().queued).toBe(0);
    expect(beaconMock.mock.calls[1][1]).toBeInstanceOf(Blob);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("retiene la cola si beacon lanza una excepcion", () => {
    visit();
    beaconMock.mockImplementation(() => { throw new Error("unavailable"); });
    expect(() => service.flushOnExit()).not.toThrow();
    expect(service.getDiagnostics().queued).toBe(1);
  });

  it("no duplica por beacon un lote que sigue en vuelo", async () => {
    fetchMock.mockImplementationOnce(() => new Promise(() => {}));
    visit();
    void service.flush();
    service.flushOnExit();
    expect(beaconMock).not.toHaveBeenCalled();
    await jest.advanceTimersByTimeAsync(0);
  });

  it("envia por beacon la cola nueva aunque otro lote siga en vuelo", async () => {
    fetchMock.mockImplementationOnce(() => new Promise(() => {}));
    visit();
    void service.flush();
    visit();
    service.flushOnExit();
    expect(beaconMock).toHaveBeenCalledTimes(1);
    expect(service.getDiagnostics().queued).toBe(1);
    expect(fetchMock.mock.calls[0][1]?.keepalive).toBe(true);
    await jest.advanceTimersByTimeAsync(0);
  });

  it("no duplica temporizadores al iniciar dos veces y conserva la cola al reiniciar", async () => {
    service.start();
    expect(jest.getTimerCount()).toBe(1);
    visit();
    service.stop();
    expect(jest.getTimerCount()).toBe(0);
    service.start();
    await jest.advanceTimersByTimeAsync(5000);
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
});

describe("instrumentacion frontend", () => {
  it("observa rechazos sin consumir el body funcional ni capturar ingesta", async () => {
    Object.defineProperty(globalThis, "window", {
      configurable: true, value: { location: { origin: "http://localhost:3001" } },
    });
    const event: ConfirmedTelemetryEvent = {
      eventId: crypto.randomUUID(), requestId: crypto.randomUUID(), timestamp: "2026-10-15T12:00:00Z",
      sessionId: null, userId: "42", event_type: "direct_stock_edit_rejected", schemaVersion: "1.0.0",
      properties: { location_id: null, country: null, currency: null, product_id: null,
        product_category: null, quantity: null, unit: null, operation: "direct_stock_edit",
        rejection_code: "DIRECT_STOCK_EDIT_FORBIDDEN", attempted_fields: ["current_stock"] },
    };
    const responseBody = { detail: { code: "DIRECT_STOCK_EDIT_FORBIDDEN", telemetry_events: [event] } };
    fetchMock.mockImplementation(async () => new Response(JSON.stringify(responseBody), { status: 403 }));
    const capture = jest.fn<(event: ConfirmedTelemetryEvent) => boolean>().mockReturnValue(true);
    const stop = observeInventoryTelemetry(capture);
    try {
      const response = await fetch("/api/inventory/products/1", { method: "PATCH" });
      expect(await response.json()).toEqual(responseBody);
      await jest.advanceTimersByTimeAsync(0);
      expect(capture).toHaveBeenCalledWith(event);
      await fetch("/telemetry/events", { method: "POST" });
      await jest.advanceTimersByTimeAsync(0);
      expect(capture).toHaveBeenCalledTimes(1);
    } finally {
      stop();
    }
    expect(globalThis.fetch).toBe(fetchMock);
  });

  it("encola hechos backend conservando envelope, sin duplicados ni propiedades libres", async () => {
    const event: ConfirmedTelemetryEvent = {
      eventId: crypto.randomUUID(), requestId: crypto.randomUUID(), timestamp: "2026-10-15T11:59:00Z",
      sessionId: null, userId: "42", event_type: "outbound_order_created", schemaVersion: "1.0.0",
      properties: { location_id: "L01", country: "CO", currency: "COP", product_id: "1",
        product_category: "meat", quantity: 2, unit: "kg", order_id: "3", reason: "consumption", email: "private@example.com" },
    };
    expect(service.track(event)).toBe(true);
    expect(service.track(event)).toBe(false);
    await service.flush();
    expect(sentEvents()).toHaveLength(1);
    expect(sentEvents()[0].eventId).toBe(event.eventId);
    expect(sentEvents()[0].timestamp).toBe(event.timestamp);
    expect(JSON.stringify(sentEvents())).not.toContain("example.com");
    expect(service.track(event)).toBe(false);
  });

  it("conserva solo el UUID de sesion entre navegaciones completas", async () => {
    const values = new Map<string, string>();
    Object.defineProperty(globalThis, "window", {
      configurable: true,
      value: { sessionStorage: {
        getItem: (key: string) => values.get(key) ?? null,
        setItem: (key: string, value: string) => { values.set(key, value); },
      } },
    });
    visit();
    await service.flush();
    const sessionId = sentEvents()[0].sessionId;
    service.stop();
    service = new TelemetryService("http://localhost:8000/telemetry/events");
    service.start();
    visit();
    await service.flush();
    expect(sentEvents(1)[0].sessionId).toBe(sessionId);
    expect([...values.keys()]).toEqual(["brasaland_telemetry_session"]);
    expect([...values.values()]).toEqual([sessionId]);
  });

  it("no bloquea la captura cuando sessionStorage esta restringido", async () => {
    Object.defineProperty(globalThis, "window", {
      configurable: true,
      value: { sessionStorage: { getItem: () => { throw new Error("blocked"); } } },
    });
    visit();
    await service.flush();
    expect(sentEvents()).toHaveLength(1);
  });

  it("traduce rutas conocidas a secciones sin capturar IDs ni rutas desconocidas", () => {
    expect(sectionForPath("/inventory/products/123")).toBe("inventory_products");
    expect(sectionForPath("/inventory/orders/inbound")).toBe("inventory_orders");
    expect(sectionForPath("/suppliers-private")).toBeNull();
    expect(sectionForPath("/login")).toBeNull();
    expect(sectionForPath("/account/profile")).toBe("profile");
  });

  it("captura transiciones reales, no rerenders, y conserva salir y volver", () => {
    const capture = jest.fn<typeof track>().mockReturnValue(true);
    const navigation = new NavigationTelemetry(capture);
    navigation.visit("/inventory/products");
    navigation.visit("/inventory/products");
    navigation.visit("/inventory/products/123");
    navigation.visit("/suppliers");
    navigation.visit("/inventory/products");
    expect(capture.mock.calls.map((call) => call[1])).toEqual([
      { section_code: "inventory_products" }, { section_code: "suppliers" },
      { section_code: "inventory_products" },
    ]);
  });

  it("limita errores por firma durante sesenta segundos sin ocultar otra categoria", () => {
    const capture = jest.fn<typeof track>().mockReturnValue(true);
    const navigation = new NavigationTelemetry(capture, "test-build");
    navigation.error("UNHANDLED_ERROR", "/inventory/products");
    navigation.error("UNHANDLED_ERROR", "/inventory/products");
    navigation.error("UNHANDLED_REJECTION", "/inventory/products");
    expect(capture).toHaveBeenCalledTimes(2);
    jest.advanceTimersByTime(60000);
    navigation.error("UNHANDLED_ERROR", "/inventory/products");
    navigation.error("UNHANDLED_ERROR", "/login");
    expect(capture).toHaveBeenCalledTimes(3);
    expect(capture.mock.calls[0][1]).toEqual({
      error_code: "UNHANDLED_ERROR", section_code: "inventory_products", release_version: "test-build",
    });
  });

  it("inicia una sola vez por primer cambio y cancela solo un flujo iniciado", () => {
    const capture = jest.fn<typeof track>().mockReturnValue(true);
    const workflow = new WorkflowTelemetry("inventory_inbound", capture);
    workflow.cancel();
    expect(capture).not.toHaveBeenCalled();
    workflow.changed();
    const headers = workflow.headers();
    workflow.changed();
    expect(capture).toHaveBeenCalledTimes(1);
    workflow.cancel();
    workflow.cancel();
    expect(capture).toHaveBeenCalledTimes(2);
    expect(capture.mock.calls[1]).toEqual([
      "workflow_cancelled",
      { workflow_id: headers["X-Workflow-ID"], workflow_type: "inventory_inbound", step_code: "form" },
      { requestId: headers["X-Request-ID"] },
    ]);
    expect(workflow.headers()).toEqual({});
  });

  it("cierra el flujo tras exito sin emitir una finalizacion de negocio en frontend", () => {
    const capture = jest.fn<typeof track>().mockReturnValue(true);
    const workflow = new WorkflowTelemetry("inventory_outbound", capture);
    workflow.changed();
    const previousId = workflow.headers()["X-Workflow-ID"];
    workflow.finish();
    expect(capture).toHaveBeenCalledTimes(1);
    workflow.changed();
    expect(capture).toHaveBeenCalledTimes(2);
    expect(workflow.headers()["X-Workflow-ID"]).not.toBe(previousId);
  });

  it("propaga correlacion en la peticion de inventario sin cambiar su payload", async () => {
    jest.spyOn(authClient, "getToken").mockReturnValue("test-token");
    fetchMock.mockResolvedValue(new Response(JSON.stringify({ id: 123 }), { status: 201 }));
    const capture = jest.fn<typeof track>().mockReturnValue(true);
    const workflow = new WorkflowTelemetry("inventory_inbound", capture);
    workflow.changed();
    const payload = { ingredient_id: 1, quantity: 2, supplier_name: "Proveedor", location_id: 1 };
    await createInboundOrder(payload, workflow.headers());
    expect(fetchMock.mock.calls[0][1]?.headers).toEqual({
      "Content-Type": "application/json", Authorization: "Bearer test-token", ...workflow.headers(),
    });
    expect(JSON.parse(fetchMock.mock.calls[0][1]?.body as string)).toEqual(payload);
    expect(JSON.stringify(capture.mock.calls)).not.toContain("test-token");
    expect(JSON.stringify(capture.mock.calls)).not.toContain("Proveedor");
  });

  it("registra fallo de conexion sin enviar el mensaje libre y conserva el error original", async () => {
    Object.defineProperty(globalThis, "window", {
      configurable: true, value: { location: { pathname: "/inventory/products" } },
    });
    const recordError = jest.spyOn(navigationTelemetry, "error").mockImplementation(() => {});
    const failure = new TypeError("private@example.com");
    fetchMock.mockRejectedValue(failure);
    await expect(fetchProducts()).rejects.toBe(failure);
    expect(recordError).toHaveBeenCalledWith("API_CONNECTION_FAILED", "/inventory/products");
    expect(JSON.stringify(recordError.mock.calls)).not.toContain("example.com");
  });
});