/**
 * Cliente API de inventario — capa única de integración con el backend.
 *
 * Todos los componentes de la sección de inventario deben usar estas
 * funciones en lugar de llamar a fetch directamente.
 *
 * Los errores HTTP 4xx/5xx se convierten en excepciones con el mensaje
 * del backend para que la UI los capture y muestre al usuario.
 */

import { getToken } from "../../../../src/auth/auth-client";
import { navigationTelemetry } from "../telemetry-instrumentation";
import { telemetryService } from "../telemetry";
import type {
  Ingredient,
  IngredientEntryCreate,
  IngredientEntryOut,
  IngredientExitCreate,
  IngredientExitOut,
  InventoryOrder,
  ApiError,
  InventoryLocation,
  InventorySupplier,
} from "./types";

const API_BASE = "/api/inventory";

function reportConnectionFailure(): void {
  if (typeof window !== "undefined") {
    navigationTelemetry.error("API_CONNECTION_FAILED", window.location.pathname);
  }
}

async function inventoryFetch(url: string, options?: RequestInit): Promise<Response> {
  try {
    return await fetch(url, options);
  } catch (error) {
    reportConnectionFailure();
    throw error;
  }
}

// ─── Helper ─────────────────────────────────────────────────────

function authHeaders(): Record<string, string> {
  const token = getToken();
  if (!token) throw new Error("No hay sesión activa");
  return { Authorization: `Bearer ${token}` };
}

async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    if (response.status === 502) reportConnectionFailure();
    let message = `Error del servidor (${response.status})`;
    try {
      const body = (await response.json()) as ApiError;
      if (body.error) message = body.error;
      else if (typeof body.detail === "string") message = body.detail;
      else if (body.detail?.code) message = body.detail.code;
    } catch {
      // usa el mensaje por defecto
    }
    throw new Error(message);
  }
  return response.json() as Promise<T>;
}

// ─── Products ───────────────────────────────────────────────────

export async function fetchProducts(): Promise<Ingredient[]> {
  const res = await inventoryFetch(`${API_BASE}/products`, { cache: "no-store" });
  return handleResponse<Ingredient[]>(res);
}

export async function fetchProduct(id: number, locationId?: number): Promise<Ingredient> {
  const parameters = new URLSearchParams();
  if (locationId !== undefined) parameters.set("location_id", String(locationId));
  const query = parameters.size ? `?${parameters.toString()}` : "";
  const res = await inventoryFetch(`${API_BASE}/products/${id}${query}`, { cache: "no-store" });
  return handleResponse<Ingredient>(res);
}

export async function fetchInventoryLocations(): Promise<InventoryLocation[]> {
  return handleResponse<InventoryLocation[]>(await inventoryFetch(`${API_BASE}/locations`, { cache: "no-store" }));
}

export async function fetchInventorySuppliers(): Promise<InventorySupplier[]> {
  return handleResponse<InventorySupplier[]>(await inventoryFetch("/api/suppliers", {
    cache: "no-store", headers: authHeaders(),
  }));
}

// ─── Orders: Inbound ─────────────────────────────────────────────

export async function createInboundOrder(
  payload: IngredientEntryCreate,
  correlation: Record<string, string> = {},
): Promise<IngredientEntryOut> {
  const res = await inventoryFetch(`${API_BASE}/orders/inbound`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...authHeaders(),
      ...telemetryService.getSessionHeaders(),
      ...correlation,
    },
    body: JSON.stringify(payload),
  });
  return handleResponse<IngredientEntryOut>(res);
}

// ─── Orders: Outbound ────────────────────────────────────────────

export async function createOutboundOrder(
  payload: IngredientExitCreate,
  correlation: Record<string, string> = {},
): Promise<IngredientExitOut> {
  const res = await inventoryFetch(`${API_BASE}/orders/outbound`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...authHeaders(),
      ...telemetryService.getSessionHeaders(),
      ...correlation,
    },
    body: JSON.stringify(payload),
  });
  return handleResponse<IngredientExitOut>(res);
}

// ─── Orders: List (combined) ─────────────────────────────────────

export async function fetchOrders(): Promise<InventoryOrder[]> {
  const res = await inventoryFetch(`${API_BASE}/orders`, { cache: "no-store" });
  return handleResponse<InventoryOrder[]>(res);
}