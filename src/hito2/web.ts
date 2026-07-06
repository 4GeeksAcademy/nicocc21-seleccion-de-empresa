import { generarReporteFinancieroPorLocal } from "./aggregations";
import { generarAlertasInventario } from "./inventory-alerts";
import {
  consumoPromedioPorDia,
  fechasEspeciales,
  insumos,
  locales,
  movimientos,
} from "./sample-data";

const moneda = new Intl.NumberFormat("es-CO", {
  style: "currency",
  currency: "COP",
  maximumFractionDigits: 0,
});

const formatearFecha = (fecha: Date): string => {
  return fecha.toLocaleDateString("es-CO", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  });
};

const clasePrioridad = (prioridad: string): string => {
  if (prioridad === "critica") return "border-red-500/40 bg-red-900/30";
  if (prioridad === "alta") return "border-orange-500/40 bg-orange-900/20";
  if (prioridad === "media") return "border-amber-500/40 bg-amber-900/20";
  return "border-stone-600 bg-stone-800/40";
};

const toInputDate = (fecha: Date): string => {
  const year = fecha.getFullYear();
  const month = String(fecha.getMonth() + 1).padStart(2, "0");
  const day = String(fecha.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
};

const parseInputDate = (raw: string): Date | null => {
  const [year, month, day] = raw.split("-").map(Number);
  if (!year || !month || !day) return null;
  return new Date(year, month - 1, day);
};

const render = (desde: Date, hasta: Date, fechaAnalisis: Date): void => {
  const tablaReportesBody = document.getElementById("tablaReportesBody");
  const listaAlertas = document.getElementById("listaAlertas");
  const rangoReporte = document.getElementById("rangoReporte");
  const contextoAlertas = document.getElementById("contextoAlertas");

  if (!tablaReportesBody || !listaAlertas || !rangoReporte || !contextoAlertas) return;

  const reportes = generarReporteFinancieroPorLocal(movimientos, locales, { desde, hasta }).sort(
    (a, b) => b.balance - a.balance
  );

  tablaReportesBody.innerHTML = reportes
    .map(
      (reporte) => `
      <tr class="border-b border-stone-800/80">
        <td class="px-3 py-2 font-semibold">${reporte.nombreLocal}</td>
        <td class="px-3 py-2 text-emerald-300">${moneda.format(reporte.entradas)}</td>
        <td class="px-3 py-2 text-rose-300">${moneda.format(reporte.salidas)}</td>
        <td class="px-3 py-2 font-bold ${reporte.balance >= 0 ? "text-amber-200" : "text-red-300"}">${moneda.format(reporte.balance)}</td>
      </tr>
    `
    )
    .join("");

  rangoReporte.textContent = `Rango: ${formatearFecha(desde)} - ${formatearFecha(hasta)}`;

  const alertas = generarAlertasInventario(insumos, fechaAnalisis, fechasEspeciales, consumoPromedioPorDia);

  contextoAlertas.textContent = `Fecha de analisis: ${formatearFecha(fechaAnalisis)} (con fechas especiales activas)`;

  listaAlertas.innerHTML = alertas
    .map(
      (alerta) => `
      <li class="rounded-xl border px-4 py-3 ${clasePrioridad(alerta.prioridad)}">
        <p class="text-xs font-bold uppercase tracking-wide text-stone-300">${alerta.prioridad}</p>
        <p class="mt-1 text-sm font-semibold text-stone-100">${alerta.nombreInsumo}</p>
        <p class="mt-1 text-sm text-stone-300">${alerta.mensaje}</p>
      </li>
    `
    )
    .join("");
};

const iniciarFiltros = (): void => {
  const inputDesde = document.getElementById("filtroDesde") as HTMLInputElement | null;
  const inputHasta = document.getElementById("filtroHasta") as HTMLInputElement | null;
  const inputAnalisis = document.getElementById("filtroAnalisis") as HTMLInputElement | null;
  const resetFiltros = document.getElementById("resetFiltros") as HTMLButtonElement | null;
  const filtrosError = document.getElementById("filtrosError");

  if (!inputDesde || !inputHasta || !inputAnalisis || !resetFiltros || !filtrosError) return;

  const defaults = {
    desde: new Date(2026, 6, 1),
    hasta: new Date(2026, 6, 31),
    analisis: new Date(2026, 1, 14),
  };

  const aplicarDefaults = (): void => {
    inputDesde.value = toInputDate(defaults.desde);
    inputHasta.value = toInputDate(defaults.hasta);
    inputAnalisis.value = toInputDate(defaults.analisis);
  };

  const recalcular = (): void => {
    const desde = parseInputDate(inputDesde.value);
    const hasta = parseInputDate(inputHasta.value);
    const analisis = parseInputDate(inputAnalisis.value);

    if (!desde || !hasta || !analisis) {
      filtrosError.textContent = "Completa todas las fechas para recalcular.";
      return;
    }

    if (desde > hasta) {
      filtrosError.textContent = "El rango es invalido: 'desde' no puede ser mayor que 'hasta'.";
      return;
    }

    filtrosError.textContent = "";
    render(desde, hasta, analisis);
  };

  aplicarDefaults();
  recalcular();

  inputDesde.addEventListener("input", recalcular);
  inputHasta.addEventListener("input", recalcular);
  inputAnalisis.addEventListener("input", recalcular);
  resetFiltros.addEventListener("click", () => {
    aplicarDefaults();
    recalcular();
  });
};

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", iniciarFiltros);
} else {
  iniciarFiltros();
}
