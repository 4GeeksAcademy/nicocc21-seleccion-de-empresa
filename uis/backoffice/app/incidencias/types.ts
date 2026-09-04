/**
 * Tipos de incidencias — re-export desde el paquete compartido.
 *
 * Mantenemos este archivo para compatibilidad con imports existentes.
 * Los tipos se definen en packages/shared/types/index.ts.
 */
export type {
  IncidentOrigin,
  IncidentCategory,
  IncidentState,
  IncidentPriority,
  Incident,
  IncidentCreatePayload,
  IncidentUpdatePayload,
  IncidentStatusUpdatePayload,
  IncidentsSummary,
  LocalId,
  LegacyCsvState,
  CsvIncidentRow,
} from "../../../../packages/shared/types";

export {
  VALID_LOCAL_IDS,
  LOCAL_ID_LABELS,
  PRIORITY_LABELS,
  STATE_LABELS,
  CATEGORY_LABELS,
  ORIGIN_LABELS,
  priorityColor,
  stateColor,
} from "../../../../packages/shared/types";