const MAX_EVENTS = 20;
const MAX_QUEUE = 200;
const MAX_BYTES = 64 * 1024;
const MAX_ATTEMPTS = 3;
const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

const SECTIONS = ["dashboard", "inventory_products", "inventory_orders", "suppliers", "incidents", "profile"] as const;
const WORKFLOWS = ["inventory_inbound", "inventory_outbound", "supplier_create", "supplier_rate_update", "supplier_status_update", "incident_create", "incident_status_update", "profile_update"] as const;
export type SectionCode = (typeof SECTIONS)[number];
export type WorkflowType = (typeof WORKFLOWS)[number];

interface FrontendProperties {
  section_viewed: { section_code: SectionCode };
  workflow_started: { workflow_id: string; workflow_type: WorkflowType };
  workflow_cancelled: { workflow_id: string; workflow_type: WorkflowType; step_code: "form" | "review" | "submit" };
  frontend_error_detected: { error_code: "UNHANDLED_ERROR" | "UNHANDLED_REJECTION" | "API_CONNECTION_FAILED"; section_code: SectionCode; release_version: string };
}

type FrontendEventType = keyof FrontendProperties;
const INVENTORY_KEYS = ["location_id", "country", "currency", "product_id", "product_category", "quantity", "unit"];
const BACKEND_KEYS = {
  inbound_order_created: [...INVENTORY_KEYS, "order_id", "supplier_id", "unit_price", "total_amount"],
  outbound_order_created: [...INVENTORY_KEYS, "order_id", "reason"],
  stock_waste_registered: [...INVENTORY_KEYS, "order_id", "reason"],
  stock_threshold_triggered: [...INVENTORY_KEYS, "order_id", "stock_before", "stock_after", "minimum_stock"],
  direct_stock_edit_rejected: [...INVENTORY_KEYS, "rejection_code", "operation", "attempted_fields"],
  ingredient_price_variance_detected: [...INVENTORY_KEYS, "order_id", "supplier_id", "unit_price", "reference_price", "variance_pct", "threshold_pct"],
  workflow_completed: ["workflow_id", "workflow_type", "entity_id"],
} as const;
type BackendEventType = keyof typeof BACKEND_KEYS;
type PropertyValue = string | number | null | string[];
export interface ConfirmedTelemetryEvent {
  eventId: string;
  timestamp: string;
  sessionId: string | null;
  userId: string | null;
  event_type: BackendEventType;
  schemaVersion: "1.0.0";
  requestId: string;
  properties: Record<string, unknown>;
}
interface CaptureContext {
  requestId?: string;
  userId?: string | null;
}
export type FrontendCapture = <EventType extends FrontendEventType>(
  eventType: EventType, properties: FrontendProperties[EventType], context?: CaptureContext,
) => boolean;
interface TelemetryEvent {
  eventId: string;
  timestamp: string;
  sessionId: string | null;
  userId: string | null;
  event_type: FrontendEventType | BackendEventType;
  schemaVersion: "1.0.0";
  requestId: string;
  properties: Record<string, PropertyValue>;
}
interface PendingBatch {
  events: TelemetryEvent[];
  attempts: number;
  retryAt: number;
}

function propertiesFor(eventType: FrontendEventType, input: object): Record<string, string> | null {
  const values = input as Record<string, unknown>;
  const section = values.section_code;
  const validSection = typeof section === "string" && SECTIONS.some((value) => value === section);
  if (eventType === "section_viewed" && validSection) {
    return { section_code: section as string };
  }
  if (eventType === "frontend_error_detected" && validSection) {
    const code = values.error_code;
    const version = values.release_version;
    if (typeof code === "string" && ["UNHANDLED_ERROR", "UNHANDLED_REJECTION", "API_CONNECTION_FAILED"].includes(code)
      && typeof version === "string" && /^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$/.test(version)) {
      return { error_code: code, section_code: section as string, release_version: version };
    }
  }
  if (eventType === "workflow_started" || eventType === "workflow_cancelled") {
    const workflowId = values.workflow_id;
    const workflowType = values.workflow_type;
    if (typeof workflowId !== "string" || !UUID_PATTERN.test(workflowId)
      || typeof workflowType !== "string" || !WORKFLOWS.some((value) => value === workflowType)) return null;
    const result = { workflow_id: workflowId, workflow_type: workflowType };
    if (eventType === "workflow_started") return result;
    const step = values.step_code;
    if (typeof step === "string" && ["form", "review", "submit"].includes(step)) {
      return { ...result, step_code: step };
    }
  }
  return null;
}

function batchBody(events: TelemetryEvent[]): string {
  return JSON.stringify({ events });
}

export function isConfirmedEvent(value: unknown): value is ConfirmedTelemetryEvent {
  if (!value || typeof value !== "object") return false;
  const event = value as Record<string, unknown>;
  return typeof event.event_type === "string" && Object.prototype.hasOwnProperty.call(BACKEND_KEYS, event.event_type)
    && typeof event.eventId === "string" && UUID_PATTERN.test(event.eventId)
    && typeof event.requestId === "string" && UUID_PATTERN.test(event.requestId)
    && typeof event.timestamp === "string" && event.timestamp.endsWith("Z") && Number.isFinite(Date.parse(event.timestamp))
    && event.schemaVersion === "1.0.0"
    && (event.sessionId === null || (typeof event.sessionId === "string" && UUID_PATTERN.test(event.sessionId)))
    && (event.userId === null || (typeof event.userId === "string" && /^[A-Za-z0-9][A-Za-z0-9:_-]{0,127}$/.test(event.userId)))
    && event.properties !== null && typeof event.properties === "object" && !Array.isArray(event.properties);
}

function validBackendProperty(key: string, value: unknown): value is PropertyValue {
  if (value === null) return INVENTORY_KEYS.includes(key);
  if (typeof value === "number") {
    return Number.isFinite(value) && (key === "variance_pct" ||
      (["quantity", "threshold_pct"].includes(key) ? value > 0
        : ["stock_before", "stock_after", "minimum_stock"].includes(key) && value >= 0));
  }
  if (key === "attempted_fields") return Array.isArray(value) && value.length > 0 && value.length <= 3
    && value.every((item) => ["stock", "stockActual", "current_stock"].includes(item));
  if (typeof value !== "string") return false;
  if (["product_id", "order_id", "supplier_id"].includes(key)) return /^[1-9][0-9]{0,19}$/.test(value);
  if (["unit_price", "reference_price", "total_amount"].includes(key)) return /^(0|[1-9][0-9]*)\.[0-9]{2}$/.test(value) && value.length <= 24;
  if (key === "workflow_id") return UUID_PATTERN.test(value);
  if (key === "workflow_type") return WORKFLOWS.some((item) => item === value);
  if (key === "entity_id") return /^[A-Za-z0-9][A-Za-z0-9:_-]{0,127}$/.test(value);
  if (key === "location_id") return /^L(0[1-9]|1[0-4])$/.test(value);
  const enums: Record<string, readonly string[]> = {
    country: ["CO", "US"], currency: ["COP", "USD"], unit: ["kg", "unit", "liter"],
    product_category: ["meat", "produce", "sauce", "beverage", "packaging", "cleaning"],
    reason: ["consumption", "expired", "kitchen_error", "theft_suspected"],
    rejection_code: ["DIRECT_STOCK_EDIT_FORBIDDEN"], operation: ["direct_stock_edit"],
  };
  return enums[key]?.includes(value) ?? false;
}

function confirmedEvent(input: ConfirmedTelemetryEvent): TelemetryEvent | null {
  if (!isConfirmedEvent(input)) return null;
  const properties: Record<string, PropertyValue> = {};
  for (const key of BACKEND_KEYS[input.event_type]) {
    const value = input.properties[key];
    if (!validBackendProperty(key, value)) return null;
    properties[key] = Array.isArray(value) ? [...value] : value;
  }
  return {
    eventId: input.eventId, timestamp: input.timestamp, sessionId: input.sessionId,
    userId: input.userId, event_type: input.event_type, schemaVersion: input.schemaVersion,
    requestId: input.requestId, properties,
  };
}

export class TelemetryService {
  private queue: TelemetryEvent[] = [];
  private batch: PendingBatch | null = null;
  private sessionId: string | null = null;
  private interval: ReturnType<typeof setInterval> | null = null;
  private retryTimer: ReturnType<typeof setTimeout> | null = null;
  private controller: AbortController | null = null;
  private running = false;
  private sending = false;
  private scheduled = false;
  private discarded = 0;
  private readonly seenIds = new Set<string>();

  constructor(private readonly endpoint: string) {}

  private captureSessionId(): string {
    if (this.sessionId) return this.sessionId;
    const generated = crypto.randomUUID();
    this.sessionId = generated;
    if (typeof window === "undefined") return generated;
    try {
      const saved = window.sessionStorage.getItem("brasaland_telemetry_session");
      if (saved && UUID_PATTERN.test(saved)) this.sessionId = saved;
      else window.sessionStorage.setItem("brasaland_telemetry_session", generated);
    } catch {
      return generated;
    }
    return this.sessionId;
  }

  getSessionHeaders(): Record<string, string> {
    if (!this.endpoint) return {};
    try {
      return { "X-Telemetry-Session-ID": this.captureSessionId() };
    } catch {
      return {};
    }
  }

  start(): void {
    if (this.running || !this.endpoint) return;
    this.running = true;
    this.interval = setInterval(() => { void this.flush(); }, 10000);
    if (this.batch || this.queue.length >= MAX_EVENTS) this.scheduleFlush();
  }

  stop(): void {
    this.running = false;
    if (this.interval !== null) clearInterval(this.interval);
    if (this.retryTimer !== null) clearTimeout(this.retryTimer);
    this.interval = null;
    this.retryTimer = null;
    this.controller?.abort();
  }

  track(event: ConfirmedTelemetryEvent): boolean;
  track<EventType extends FrontendEventType>(
    eventType: EventType,
    properties: FrontendProperties[EventType],
    context?: CaptureContext,
  ): boolean;
  track(
    eventType: FrontendEventType | ConfirmedTelemetryEvent,
    properties?: FrontendProperties[FrontendEventType],
    context: CaptureContext = {},
  ): boolean {
    if (!this.endpoint) return false;
    try {
      if (typeof eventType === "object") {
        const event = confirmedEvent(eventType);
        return event ? this.enqueue(event) : false;
      }
      if (!properties) return false;
      const safeProperties = propertiesFor(eventType, properties);
      if (!safeProperties) return false;
      if (context.requestId !== undefined && !UUID_PATTERN.test(context.requestId)) return false;
      if (context.userId != null && !/^[A-Za-z0-9][A-Za-z0-9:_-]{0,127}$/.test(context.userId)) return false;
      const sessionId = this.captureSessionId();
      const event: TelemetryEvent = {
        eventId: crypto.randomUUID(), timestamp: new Date().toISOString(),
        sessionId, userId: context.userId ?? null,
        event_type: eventType, schemaVersion: "1.0.0",
        requestId: context.requestId ?? crypto.randomUUID(), properties: safeProperties,
      };
      return this.enqueue(event);
    } catch {
      return false;
    }
  }

  private enqueue(event: TelemetryEvent): boolean {
    if (this.seenIds.has(event.eventId)) return false;
    if (new TextEncoder().encode(batchBody([event])).byteLength > MAX_BYTES) {
      this.discarded += 1;
      return false;
    }
    if (this.queue.length + (this.batch?.events.length ?? 0) >= MAX_QUEUE) {
      const visitIndex = this.queue.findIndex((item) => item.event_type === "section_viewed");
      this.discarded += 1;
      if (visitIndex === -1) return false;
      this.queue.splice(visitIndex, 1);
    }
    this.seenIds.add(event.eventId);
    if (this.seenIds.size > MAX_QUEUE * 2) this.seenIds.delete(this.seenIds.values().next().value!);
    this.queue.push(event);
    if (this.queue.length >= MAX_EVENTS) this.scheduleFlush();
    return true;
  }

  getDiagnostics(): { queued: number; discarded: number } {
    return { queued: this.queue.length + (this.batch?.events.length ?? 0), discarded: this.discarded };
  }

  private scheduleFlush(): void {
    if (this.scheduled || !this.running) return;
    this.scheduled = true;
    queueMicrotask(() => {
      this.scheduled = false;
      void this.flush();
    });
  }

  private takeBatch(): PendingBatch | null {
    const events: TelemetryEvent[] = [];
    while (this.queue.length && events.length < MAX_EVENTS) {
      const next = this.queue[0];
      if (new TextEncoder().encode(batchBody([...events, next])).byteLength > MAX_BYTES) break;
      events.push(this.queue.shift()!);
    }
    return events.length ? { events, attempts: 0, retryAt: 0 } : null;
  }

  async flush(): Promise<void> {
    if (!this.running || this.sending) return;
    this.batch ??= this.takeBatch();
    const batch = this.batch;
    if (!batch || Date.now() < batch.retryAt) return;
    this.sending = true;
    batch.attempts += 1;
    const controller = new AbortController();
    this.controller = controller;
    const timeout = setTimeout(() => controller.abort(), 10000);
    try {
      const response = await fetch(this.endpoint, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: batchBody(batch.events), signal: controller.signal,
        credentials: "omit", referrerPolicy: "no-referrer", keepalive: true,
      });
      if (response.ok) {
        this.batch = null;
      } else if (response.status === 429 || response.status >= 500) {
        this.retry(batch, response.headers.get("Retry-After"));
      } else {
        this.discarded += batch.events.length;
        this.batch = null;
      }
    } catch {
      this.retry(batch, null);
    } finally {
      clearTimeout(timeout);
      this.controller = null;
      this.sending = false;
      if (this.running && !this.batch && this.queue.length >= MAX_EVENTS) this.scheduleFlush();
    }
  }

  private retry(batch: PendingBatch, retryAfter: string | null): void {
    if (batch.attempts >= MAX_ATTEMPTS) {
      this.discarded += batch.events.length;
      this.batch = null;
      return;
    }
    const backoff = Math.min(1000 * 2 ** (batch.attempts - 1), 60000) * (0.5 + Math.random() * 0.5);
    const seconds = retryAfter === null ? NaN : Number(retryAfter);
    const serverDelay = retryAfter === null ? 0
      : Number.isFinite(seconds) ? seconds * 1000 : Date.parse(retryAfter) - Date.now();
    const delay = Math.ceil(Math.min(Math.max(backoff, serverDelay || 0), 2147483647));
    batch.retryAt = Date.now() + delay;
    if (this.retryTimer !== null) clearTimeout(this.retryTimer);
    if (this.running) this.retryTimer = setTimeout(() => { void this.flush(); }, delay);
  }

  flushOnExit(): void {
    if (!this.endpoint || typeof navigator === "undefined" || typeof navigator.sendBeacon !== "function") return;
    try {
      if (this.batch && !this.sending) {
        if (Date.now() < this.batch.retryAt) return;
        const accepted = navigator.sendBeacon(this.endpoint, new Blob([batchBody(this.batch.events)], { type: "application/json" }));
        if (!accepted) return;
        this.batch = null;
        if (this.retryTimer !== null) clearTimeout(this.retryTimer);
        this.retryTimer = null;
      }
      while (this.queue.length) {
        const batch = this.takeBatch();
        if (!batch) return;
        let accepted = false;
        try {
          accepted = navigator.sendBeacon(this.endpoint, new Blob([batchBody(batch.events)], { type: "application/json" }));
        } finally {
          if (!accepted) this.queue.unshift(...batch.events);
        }
        if (!accepted) return;
      }
    } catch {
      return;
    }
  }
}

export const telemetryService = new TelemetryService(process.env.NEXT_PUBLIC_TELEMETRY_ENDPOINT?.trim() ?? "");

export function track(event: ConfirmedTelemetryEvent): boolean;
export function track<EventType extends FrontendEventType>(
  eventType: EventType,
  properties: FrontendProperties[EventType],
  context?: CaptureContext,
): boolean;
export function track(
  eventType: FrontendEventType | ConfirmedTelemetryEvent,
  properties?: FrontendProperties[FrontendEventType],
  context?: CaptureContext,
): boolean {
  if (typeof window === "undefined") return false;
  if (typeof eventType === "object") return telemetryService.track(eventType);
  return properties ? telemetryService.track(eventType, properties, context) : false;
}