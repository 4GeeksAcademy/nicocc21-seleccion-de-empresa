import { AlertaInventario, FechaEspecial, Insumo, PrioridadAlerta } from "./types";

const PRIORIDAD_PESO: Record<PrioridadAlerta, number> = {
  critica: 4,
  alta: 3,
  media: 2,
  informativa: 1,
};

export const tieneStockBajo = (insumo: Insumo): boolean => {
  return insumo.stockActual <= insumo.stockMinimo;
};

export const calcularImpactoEnDemanda = (
  fechaActual: Date,
  fechasEspeciales: FechaEspecial[]
): number => {
  const vigente = fechasEspeciales.find(
    (f) => fechaActual >= f.fechaInicio && fechaActual <= f.fechaFin
  );
  return vigente?.factorDemanda ?? 1;
};

export const generarAlertasInventario = (
  insumos: Insumo[],
  fechaActual: Date,
  fechasEspeciales: FechaEspecial[],
  consumoPromedioPorDia: Record<string, number>
): AlertaInventario[] => {
  const factorDemanda = calcularImpactoEnDemanda(fechaActual, fechasEspeciales);

  const alertas: AlertaInventario[] = [];

  for (const insumo of insumos) {
    const consumoBase = consumoPromedioPorDia[insumo.id] ?? 0;
    const consumoAjustado = consumoBase * factorDemanda;

    if (consumoAjustado <= 0) continue;

    const diasCobertura = insumo.stockActual / consumoAjustado;

    if (tieneStockBajo(insumo) || diasCobertura < 3) {
      const prioridad: PrioridadAlerta = diasCobertura < 2 ? "critica" : "alta";
      alertas.push({
        insumoId: insumo.id,
        nombreInsumo: insumo.nombre,
        prioridad,
        tipo: "faltante",
        mensaje: `Cobertura aproximada ${diasCobertura.toFixed(1)} dias. Reponer urgente.`,
      });
      continue;
    }

    if (diasCobertura > insumo.frecuenciaRotacionDias * 1.2) {
      alertas.push({
        insumoId: insumo.id,
        nombreInsumo: insumo.nombre,
        prioridad: "media",
        tipo: "exceso",
        mensaje: `Cobertura aproximada ${diasCobertura.toFixed(1)} dias supera el ciclo de rotacion (${insumo.frecuenciaRotacionDias} dias).`,
      });
      continue;
    }

    if (diasCobertura > insumo.frecuenciaRotacionDias) {
      alertas.push({
        insumoId: insumo.id,
        nombreInsumo: insumo.nombre,
        prioridad: "informativa",
        tipo: "exceso",
        mensaje: `Cobertura en limite alto (${diasCobertura.toFixed(1)} dias). Revisar pedido siguiente.`,
      });
    }
  }

  return alertas.sort((a, b) => PRIORIDAD_PESO[b.prioridad] - PRIORIDAD_PESO[a.prioridad]);
};
