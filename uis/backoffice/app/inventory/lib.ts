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
import type {
  Ingredient,
  IngredientEntryCreate,
  IngredientEntryOut,
  IngredientExitCreate,
  IngredientExitOut,
  InventoryOrder,
  ApiError,
} from "./types";

const API_BASE = "/api/inventory";

// ─── Helper ─────────────────────────────────────────────────────

function authHeaders(): Record<string, string> {
  const token = getToken();
  if (!token) throw new Error("No hay sesión activa");
  return { Authorization: `Bearer ${token}` };
}

async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    let message = `Error del servidor (${response.status})`;
    try {
      const body = (await response.json()) as ApiError;
      if (body.error) message = body.error;
      else if (body.detail) message = body.detail;
    } catch {
      // usa el mensaje por defecto
    }
    throw new Error(message);
  }
  return response.json() as Promise<T>;
}

// ─── Products ───────────────────────────────────────────────────

export async function fetchProducts(): Promise<Ingredient[]> {
  const res = await fetch(`${API_BASE}/products`, { cache: "no-store" });
  return handleResponse<Ingredient[]>(res);
}

export async function fetchProduct(id: number): Promise<Ingredient> {
  const res = await fetch(`${API_BASE}/products/${id}`, { cache: "no-store" });
  return handleResponse<Ingredient>(res);
}

// ─── Orders: Inbound ─────────────────────────────────────────────

export async function createInboundOrder(
  payload: IngredientEntryCreate,
): Promise<IngredientEntryOut> {
  const res = await fetch(`${API_BASE}/orders/inbound`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...authHeaders(),
    },
    body: JSON.stringify(payload),
  });
  return handleResponse<IngredientEntryOut>(res);
}

// ─── Orders: Outbound ────────────────────────────────────────────

export async function createOutboundOrder(
  payload: IngredientExitCreate,
): Promise<IngredientExitOut> {
  const res = await fetch(`${API_BASE}/orders/outbound`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...authHeaders(),
    },
    body: JSON.stringify(payload),
  });
  return handleResponse<IngredientExitOut>(res);
}

// ─── Orders: List (combined) ─────────────────────────────────────

export async function fetchOrders(): Promise<InventoryOrder[]> {
  const res = await fetch(`${API_BASE}/orders`, { cache: "no-store" });
  return handleResponse<InventoryOrder[]>(res);
}