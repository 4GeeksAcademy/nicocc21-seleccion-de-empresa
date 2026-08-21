import { generarReporteFinancieroPorLocal } from "@brasaland/aggregations";
import { generarAlertasInventario } from "@brasaland/inventory-alerts";
import {
  consumoPromedioPorDia,
  fechasEspeciales,
  insumos,
  locales,
  movimientos,
} from "@brasaland/sample-data";

const moneda = new Intl.NumberFormat("es-CO", {
  style: "currency",
  currency: "COP",
  maximumFractionDigits: 0,
});

const clasePrioridad = (prioridad: string): string => {
  if (prioridad === "critica") return "border-red-500 bg-red-950";
  if (prioridad === "alta") return "border-orange-500 bg-orange-950";
  if (prioridad === "media") return "border-amber-500 bg-amber-950";
  return "border-stone-600 bg-stone-900";
};

export default function BackofficePage() {
  const inicioMes = new Date(2026, 6, 1);
  const finMes = new Date(2026, 6, 31);

  const reportes = generarReporteFinancieroPorLocal(movimientos, locales, {
    desde: inicioMes,
    hasta: finMes,
  }).sort((a, b) => b.balance - a.balance);

  const fechaAnalisis = new Date(2026, 1, 14);
  const alertas = generarAlertasInventario(
    insumos,
    fechaAnalisis,
    fechasEspeciales,
    consumoPromedioPorDia
  );

  return (
    <div className="min-h-screen bg-stone-950 text-stone-100">
      <main className="mx-auto max-w-6xl px-4 py-10 sm:px-6 lg:px-8">
        {/* Header */}
        <header className="rounded-3xl border border-amber-300/30 bg-gradient-to-br from-stone-900 to-red-950 p-8 shadow-2xl shadow-black/40">
          <div className="flex items-start justify-between">
            <div>
              <p className="text-xs font-bold uppercase tracking-[0.18em] text-amber-300">
                Brasaland OPS Console
              </p>
              <h1 className="mt-4 text-3xl font-black leading-tight sm:text-4xl">
                Panel interno de control financiero e inventarios
              </h1>
              <p className="mt-4 max-w-3xl text-sm text-stone-300 sm:text-base">
                Plataforma interna para Dirección Ejecutiva y Jefatura de
                Inventarios. Datos generados desde la lógica de negocio del Hito 2.
              </p>
            </div>
            <div className="flex gap-2 text-sm">
              <a
                href="/account/profile"
                className="rounded-full border border-stone-500 bg-stone-800 px-3 py-1.5 text-stone-200 transition hover:bg-stone-700"
              >
                Mi perfil
              </a>
              <a
                href="/logout"
                className="rounded-full border border-red-400/50 bg-red-950 px-3 py-1.5 text-red-200 transition hover:bg-red-900"
              >
                Cerrar sesión
              </a>
            </div>
          </div>
          <nav className="mt-6 flex flex-wrap gap-3 text-sm">
            <a
              href="/suppliers"
              className="rounded-full border border-emerald-300/60 bg-emerald-300/10 px-4 py-2 font-bold text-emerald-200 transition hover:bg-emerald-300/20"
            >
              Ir al directorio de proveedores
            </a>
            <a
              href="/incidencias"
              className="rounded-full border border-amber-300/60 bg-amber-300/10 px-4 py-2 font-bold text-amber-200 transition hover:bg-amber-300/20"
            >
              Ir al analizador de incidencias
            </a>
          </nav>
        </header>

        {/* Reporte financiero */}
        <section className="mt-8 rounded-2xl border border-stone-700 bg-stone-900 p-6">
          <h2 className="text-xl font-extrabold text-amber-200">
            Reporte financiero por local
          </h2>
          <p className="mt-2 text-xs uppercase tracking-wide text-stone-400">
            Rango: 01/07/2026 — 31/07/2026
          </p>
          <div className="mt-4 overflow-x-auto">
            <table className="min-w-full text-left text-sm">
              <thead>
                <tr className="border-b border-stone-700 text-stone-300">
                  <th className="px-3 py-2">Local</th>
                  <th className="px-3 py-2">Ciudad</th>
                  <th className="px-3 py-2 text-right">Entradas</th>
                  <th className="px-3 py-2 text-right">Salidas</th>
                  <th className="px-3 py-2 text-right">Balance</th>
                </tr>
              </thead>
              <tbody>
                {reportes.map((r) => {
                  const local = locales.find((l) => l.id === r.localId);
                  return (
                    <tr
                      key={r.localId}
                      className="border-b border-stone-800/80"
                    >
                      <td className="px-3 py-2 font-semibold">
                        {r.nombreLocal}
                      </td>
                      <td className="px-3 py-2 text-stone-400">
                        {local?.ciudad}
                      </td>
                      <td className="px-3 py-2 text-right text-emerald-300">
                        {moneda.format(r.entradas)}
                      </td>
                      <td className="px-3 py-2 text-right text-rose-300">
                        {moneda.format(r.salidas)}
                      </td>
                      <td
                        className={`px-3 py-2 text-right font-bold ${
                          r.balance >= 0 ? "text-amber-200" : "text-red-300"
                        }`}
                      >
                        {moneda.format(r.balance)}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </section>

        {/* Alertas de inventario */}
        <section className="mt-8 rounded-2xl border border-stone-700 bg-stone-900 p-6">
          <h2 className="text-xl font-extrabold text-amber-200">
            Alertas de inventario
          </h2>
          <p className="mt-2 text-xs uppercase tracking-wide text-stone-400">
            Fecha de análisis: 14/02/2026 (San Valentín activo — factor x1.6)
          </p>
          <ul className="mt-4 space-y-3">
            {alertas.map((alerta) => (
              <li
                key={alerta.insumoId}
                className={`rounded-xl border px-4 py-3 ${clasePrioridad(
                  alerta.prioridad
                )}`}
              >
                <p className="text-xs font-bold uppercase tracking-wide text-stone-300">
                  {alerta.prioridad}
                </p>
                <p className="mt-1 text-sm font-semibold text-stone-100">
                  {alerta.nombreInsumo}
                </p>
                <p className="mt-1 text-sm text-stone-300">
                  {alerta.mensaje}
                </p>
              </li>
            ))}
          </ul>
        </section>

        {/* Footer */}
        <footer className="mt-8 text-center text-xs text-stone-600">
          <p>
            Fuente: <code>src/hito2/</code> — Importado desde la ubicación
            original del monorepo. Sin código duplicado.
          </p>
        </footer>
      </main>
    </div>
  );
}
