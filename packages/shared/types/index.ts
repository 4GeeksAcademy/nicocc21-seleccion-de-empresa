/**
 * Tipos compartidos del dominio de Incidencias Brasaland.
 * Usado por las apps (backoffice, website, etc.) y servicios.
 */

// ─── Enums como type unions ───────────────────────────────────────
export type IncidentOrigin = "cliente" | "interno";
export type IncidentCategory = "queja" | "solicitud" | "fallo_operativo";
export type IncidentState = "abierta" | "en_progreso" | "resuelta" | "descartada";
export type IncidentPriority = "baja" | "media" | "alta" | "critica";

// ─── Locales ──────────────────────────────────────────────────────
export const VALID_LOCAL_IDS = [
  "L01", "L02", "L03", "L04", "L05", "L06", "L07",
  "L08", "L09", "L10", "L11", "L12", "L13", "L14",
] as const;

export type LocalId = (typeof VALID_LOCAL_IDS)[number];

export const LOCAL_ID_LABELS: Record<string, string> = {
  L01: "Bogotá Sede 1",
  L02: "Medellín Sede 1",
  L03: "Cali Sede 1",
  L04: "Barranquilla Sede 1",
  L05: "Cartagena Sede 1",
  L06: "Bucaramanga Sede 1",
  L07: "Pereira Sede 1",
  L08: "Miami Sede 1",
  L09: "Orlando Sede 1",
  L10: "Tampa Sede 1",
  L11: "Bogotá Sede 2",
  L12: "Medellín Sede 2",
  L13: "Cali Sede 2",
  L14: "Miami Sede 2",
};

// ─── Labels ───────────────────────────────────────────────────────
export const PRIORITY_LABELS: Record<IncidentPriority, string> = {
  baja: "Baja",
  media: "Media",
  alta: "Alta",
  critica: "Crítica",
};

export const STATE_LABELS: Record<IncidentState, string> = {
  abierta: "Abierta",
  en_progreso: "En progreso",
  resuelta: "Resuelta",
  descartada: "Descartada",
};

export const CATEGORY_LABELS: Record<IncidentCategory, string> = {
  queja: "Queja",
  solicitud: "Solicitud",
  fallo_operativo: "Fallo operativo",
};

export const ORIGIN_LABELS: Record<IncidentOrigin, string> = {
  cliente: "Cliente",
  interno: "Interno",
};

// ─── Domain models ────────────────────────────────────────────────
export interface Incident {
  id: number;
  incident_id: string;
  title: string;
  description: string;
  fecha_reporte: string;
  local_id: string;
  origen: IncidentOrigin;
  categoria: IncidentCategory;
  estado: IncidentState;
  prioridad: IncidentPriority;
  cliente_id: string | null;
  cliente_email: string | null;
  cliente_telefono: string | null;
  satisfaccion: number | null;
  created_at: string;
  updated_at: string;
}

export interface IncidentCreatePayload {
  title: string;
  description: string;
  fecha_reporte: string;
  local_id: string;
  origen: IncidentOrigin;
  categoria: IncidentCategory;
  prioridad: IncidentPriority;
  cliente_id?: string | null;
  cliente_email?: string | null;
  cliente_telefono?: string | null;
}

export interface IncidentUpdatePayload {
  title?: string;
  description?: string;
  local_id?: string;
  categoria?: IncidentCategory;
  prioridad?: IncidentPriority;
  cliente_id?: string | null;
  cliente_email?: string | null;
  cliente_telefono?: string | null;
  satisfaccion?: number | null;
}

export interface IncidentStatusUpdatePayload {
  estado: IncidentState;
}

export interface IncidentsSummary {
  total: number;
  by_state: Record<string, number>;
  by_category: Record<string, number>;
  by_priority: Record<string, number>;
  by_origin: Record<string, number>;
}

// ─── Helper functions ─────────────────────────────────────────────
export function priorityColor(priority: IncidentPriority): string {
  switch (priority) {
    case "critica": return "text-rose-300 border-rose-700 bg-rose-950/40";
    case "alta": return "text-orange-300 border-orange-700 bg-orange-950/40";
    case "media": return "text-yellow-300 border-yellow-700 bg-yellow-950/40";
    case "baja": return "text-stone-300 border-stone-600 bg-stone-800/40";
  }
}

export function stateColor(state: IncidentState): string {
  switch (state) {
    case "abierta": return "text-sky-300 border-sky-700 bg-sky-950/40";
    case "en_progreso": return "text-amber-300 border-amber-700 bg-amber-950/40";
    case "resuelta": return "text-emerald-300 border-emerald-700 bg-emerald-950/40";
    case "descartada": return "text-stone-400 border-stone-700 bg-stone-800/40";
  }
}

// ─── Legacy CSV validation types (formato abierto/cerrado/descartado) ──
export type LegacyCsvState = "abierto" | "cerrado" | "descartado";

export interface CsvIncidentRow {
  incident_id: string;
  fecha_reporte: string;
  local_id: string;
  cliente_id: string;
  cliente_email: string;
  cliente_telefono: string;
  categoria: string;
  estado: LegacyCsvState;
  prioridad: string;
  descripcion: string;
  satisfaccion?: string;
}