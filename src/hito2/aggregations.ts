import { agruparPor, filtrar } from "./collections";
import { Local, MovimientoFinanciero, ReporteFinancieroLocal } from "./types";

interface RangoFechas {
  desde?: Date;
  hasta?: Date;
}

const estaEnRango = (fecha: Date, rango: RangoFechas): boolean => {
  if (rango.desde && fecha < rango.desde) return false;
  if (rango.hasta && fecha > rango.hasta) return false;
  return true;
};

export const generarReporteFinancieroPorLocal = (
  movimientos: MovimientoFinanciero[],
  locales: Local[],
  rango: RangoFechas = {}
): ReporteFinancieroLocal[] => {
  const movimientosFiltrados = filtrar(movimientos, (m) => estaEnRango(m.fecha, rango));
  const movimientosPorLocal = agruparPor(movimientosFiltrados, (m) => m.localId);

  return locales.map((local) => {
    const items = movimientosPorLocal[local.id] ?? [];
    const entradas = items
      .filter((m) => m.tipo === "entrada")
      .reduce((acc, m) => acc + m.monto, 0);
    const salidas = items
      .filter((m) => m.tipo === "salida")
      .reduce((acc, m) => acc + m.monto, 0);

    return {
      localId: local.id,
      nombreLocal: local.nombre,
      entradas,
      salidas,
      balance: entradas - salidas,
    };
  });
};
