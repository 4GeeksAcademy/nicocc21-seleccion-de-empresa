import { generarReporteFinancieroPorLocal } from "./hito2/aggregations";
import { generarAlertasInventario } from "./hito2/inventory-alerts";
import {
  consumoPromedioPorDia,
  fechasEspeciales,
  insumos,
  locales,
  movimientos,
} from "./hito2/sample-data";

const inicioMes = new Date(2026, 6, 1);
const finMes = new Date(2026, 6, 31);

const reportes = generarReporteFinancieroPorLocal(movimientos, locales, {
  desde: inicioMes,
  hasta: finMes,
});

const fechaAnalisis = new Date(2026, 1, 14);
const alertas = generarAlertasInventario(
  insumos,
  fechaAnalisis,
  fechasEspeciales,
  consumoPromedioPorDia
);

console.log("==== REPORTE FINANCIERO POR LOCAL (TOP 5 BALANCE) ====");
for (const item of [...reportes].sort((a, b) => b.balance - a.balance).slice(0, 5)) {
  console.log(
    `${item.nombreLocal} | Entradas: ${item.entradas.toLocaleString("es-CO")} | Salidas: ${item.salidas.toLocaleString("es-CO")} | Balance: ${item.balance.toLocaleString("es-CO")}`
  );
}

console.log("\n==== ALERTAS DE INVENTARIO ====");
for (const alerta of alertas) {
  console.log(`[${alerta.prioridad.toUpperCase()}] ${alerta.nombreInsumo}: ${alerta.mensaje}`);
}

console.log("\nComando recomendado para validar tipos: npm run typecheck");
