import { FechaEspecial, Insumo, Local, MovimientoFinanciero } from "./types";

const ciudades = [
  "Bogota",
  "Medellin",
  "Cali",
  "Barranquilla",
  "Cartagena",
  "Bucaramanga",
  "Pereira",
  "Miami",
  "Orlando",
  "Tampa",
  "Bogota",
  "Medellin",
  "Cali",
  "Miami",
];

export const locales: Local[] = Array.from({ length: 14 }, (_, i) => ({
  id: `L${String(i + 1).padStart(2, "0")}`,
  nombre: `Brasaland Sede ${i + 1}`,
  ciudad: ciudades[i],
}));

const departamentos = ["cocina", "barra", "administracion", "marketing", "mantenimiento"] as const;

export const movimientos: MovimientoFinanciero[] = locales.flatMap((local, localIndex) => {
  return Array.from({ length: 10 }, (_, i) => {
    const dia = (i % 28) + 1;
    const esEntrada = i % 2 === 0;
    const base = 1_000_000 + localIndex * 50_000 + i * 20_000;

    return {
      id: `M-${local.id}-${i + 1}`,
      localId: local.id,
      fecha: new Date(2026, 6, dia),
      tipo: esEntrada ? "entrada" : "salida",
      monto: esEntrada ? base * 1.8 : base,
      departamento: departamentos[i % departamentos.length],
      descripcion: esEntrada ? "Ventas del dia" : "Gasto operativo",
    };
  });
});

export const insumos: Insumo[] = [
  {
    id: "I-001",
    nombre: "Carne premium",
    categoria: "comida",
    stockActual: 120,
    stockMinimo: 150,
    perecedero: true,
    diasVidaUtil: 7,
    frecuenciaRotacionDias: 7,
  },
  {
    id: "I-002",
    nombre: "Queso mozzarella",
    categoria: "comida",
    stockActual: 180,
    stockMinimo: 120,
    perecedero: true,
    diasVidaUtil: 10,
    frecuenciaRotacionDias: 7,
  },
  {
    id: "I-003",
    nombre: "Cerveza artesanal",
    categoria: "bebida",
    stockActual: 420,
    stockMinimo: 180,
    perecedero: false,
    diasVidaUtil: 180,
    frecuenciaRotacionDias: 15,
  },
  {
    id: "I-004",
    nombre: "Vino tinto",
    categoria: "bebida",
    stockActual: 90,
    stockMinimo: 100,
    perecedero: false,
    diasVidaUtil: 365,
    frecuenciaRotacionDias: 15,
  },
  {
    id: "I-005",
    nombre: "Empaques takeout",
    categoria: "empaque",
    stockActual: 950,
    stockMinimo: 400,
    perecedero: false,
    diasVidaUtil: 365,
    frecuenciaRotacionDias: 15,
  },
];

export const fechasEspeciales: FechaEspecial[] = [
  {
    nombre: "San Valentin",
    fechaInicio: new Date(2026, 1, 10),
    fechaFin: new Date(2026, 1, 16),
    factorDemanda: 1.6,
  },
  {
    nombre: "Navidad",
    fechaInicio: new Date(2026, 11, 20),
    fechaFin: new Date(2026, 11, 31),
    factorDemanda: 2.0,
  },
  {
    nombre: "Ano Nuevo",
    fechaInicio: new Date(2026, 0, 1),
    fechaFin: new Date(2026, 0, 7),
    factorDemanda: 1.7,
  },
];

export const consumoPromedioPorDia: Record<string, number> = {
  "I-001": 55,
  "I-002": 18,
  "I-003": 22,
  "I-004": 20,
  "I-005": 40,
};
