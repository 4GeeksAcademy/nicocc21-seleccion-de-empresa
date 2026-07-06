export type Department =
  | "cocina"
  | "barra"
  | "administracion"
  | "marketing"
  | "mantenimiento";

export interface Local {
  id: string;
  nombre: string;
  ciudad: string;
}

export interface MovimientoFinanciero {
  id: string;
  localId: string;
  fecha: Date;
  tipo: "entrada" | "salida";
  monto: number;
  departamento: Department;
  descripcion: string;
}

export type CategoriaInsumo = "comida" | "bebida" | "empaque";

export interface Insumo {
  id: string;
  nombre: string;
  categoria: CategoriaInsumo;
  stockActual: number;
  stockMinimo: number;
  perecedero: boolean;
  diasVidaUtil: number;
  frecuenciaRotacionDias: 7 | 15;
}

export interface FechaEspecial {
  nombre: string;
  fechaInicio: Date;
  fechaFin: Date;
  factorDemanda: number;
}

export interface ReporteFinancieroLocal {
  localId: string;
  nombreLocal: string;
  entradas: number;
  salidas: number;
  balance: number;
}

export type PrioridadAlerta = "critica" | "alta" | "media" | "informativa";

export interface AlertaInventario {
  insumoId: string;
  nombreInsumo: string;
  prioridad: PrioridadAlerta;
  tipo: "faltante" | "exceso";
  mensaje: string;
}
