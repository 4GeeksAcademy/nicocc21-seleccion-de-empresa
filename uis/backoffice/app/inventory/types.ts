/** Tipo de categoría de ingrediente, alineado con el contexto de Hito 5. */
export type CategoriaInsumo =
  | "meat"
  | "produce"
  | "sauce"
  | "beverage"
  | "packaging"
  | "cleaning";

/** Razón de salida de stock. */
export type RazonSalida = "consumption" | "waste";

/** País de origen del ingrediente. */
export type Pais = "CO" | "US";

/** Tipo de movimiento en la lista combinada de órdenes. */
export type TipoOrden = "inbound" | "outbound";

// ─── Ingredient ─────────────────────────────────────────────────

export interface Ingredient {
  id: number;
  name: string;
  sku: string;
  unit: string;
  category: string;
  country: string;
  stock_minimo: number;
  perecedero: boolean;
  dias_vida_util: number;
  frecuencia_rotacion_dias: number;
  current_stock: number; // calculado dinámicamente (no almacenado)
}

export interface IngredientCreate {
  name: string;
  sku: string;
  unit: string;
  category: CategoriaInsumo;
  country: Pais;
  stock_minimo?: number;
  perecedero?: boolean;
  dias_vida_util?: number;
  frecuencia_rotacion_dias?: number;
}

// ─── IngredientEntry (inbound) ──────────────────────────────────

export interface IngredientEntryCreate {
  ingredient_id: number;
  quantity: number;
  supplier_name: string;
  location_id: number;
}

export interface IngredientEntryOut {
  id: number;
  ingredient_id: number;
  ingredient_name: string;
  quantity: number;
  supplier_name: string;
  location_id: number;
  created_at: string;
  user_uuid: string;
  type: "inbound";
}

// ─── IngredientExit (outbound) ──────────────────────────────────

export interface IngredientExitCreate {
  ingredient_id: number;
  quantity: number;
  reason: RazonSalida;
  location_id: number;
}

export interface IngredientExitOut {
  id: number;
  ingredient_id: number;
  ingredient_name: string;
  quantity: number;
  reason: string;
  location_id: number;
  created_at: string;
  user_uuid: string;
  type: "outbound";
}

// ─── Orden combinada ────────────────────────────────────────────

export type InventoryOrder = IngredientEntryOut | IngredientExitOut;

// ─── Error de API ────────────────────────────────────────────────

export interface ApiError {
  error?: string;
  detail?: string;
}