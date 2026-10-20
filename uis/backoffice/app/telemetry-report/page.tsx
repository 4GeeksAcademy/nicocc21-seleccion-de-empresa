"use client";

import { useEffect, useState } from "react";

// Página de reporte de telemetría — Fase 3
// Muestra 4 métricas: eventos/día, tasa de error, latencia, auth failures.

interface TelemetryReport {
  period: { from: string; to: string };
  metrics: {
    events_per_day: { date: string; event_type: string; count: number }[];
    error_rate_by_type: { event_type: string; total: number; errors: number; error_rate: number }[];
    api_latency_summary: {
      route_template: string;
      method: string;
      count: number;
      p50_ms: number;
      p90_ms: number;
      p99_ms: number;
      mean_ms: number;
    }[];
    auth_failure_rate: {
      date: string;
      attempts: number;
      failures: number;
      successes: number;
      failure_rate: number | null;
    }[];
  };
}

function isoNow(): string {
  const d = new Date();
  return d.toISOString().slice(0, 16);
}

function isoWeekAgo(): string {
  const d = new Date(Date.now() - 7 * 86_400_000);
  return d.toISOString().slice(0, 16);
}

function fmtPct(v: number | null): string {
  if (v === null) return "—";
  return `${(v * 100).toFixed(1)} %`;
}

function fmtDate(iso: string): string {
  const d = new Date(iso + "T00:00:00Z");
  return d.toLocaleDateString("es-ES", { day: "2-digit", month: "2-digit" });
}

async function fetchReport(
  startDate: string,
  endDate: string,
  signal?: AbortSignal,
): Promise<TelemetryReport> {
  const params = new URLSearchParams();
  if (startDate) params.set("start_date", startDate + ":00Z");
  if (endDate) params.set("end_date", endDate + ":00Z");

  const res = await fetch(`/api/telemetry/report?${params.toString()}`, {
    signal,
  });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`HTTP ${res.status}: ${body.slice(0, 200)}`);
  }
  return res.json() as Promise<TelemetryReport>;
}

// ─── Tabla genérica ─────────────────────────────────────

function DataTable({
  headers,
  rows,
}: {
  headers: string[];
  rows: (string | number | null)[][];
}) {
  return (
    <div className="overflow-x-auto">
      <table className="min-w-full text-left text-sm">
        <thead>
          <tr className="border-b border-stone-700">
            {headers.map((h) => (
              <th key={h} className="px-3 py-2 text-stone-300 text-left text-xs uppercase tracking-wide">
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, ri) => (
            <tr key={ri} className="border-b border-stone-800/80">
              {row.map((cell, ci) => (
                <td key={ci} className="px-3 py-2 text-stone-200 text-sm">
                  {cell ?? "—"}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function TelemetryReportPage() {
  const [report, setReport] = useState<TelemetryReport | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [startDate, setStartDate] = useState(isoWeekAgo);
  const [endDate, setEndDate] = useState(isoNow);

  async function load(signal?: AbortSignal) {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchReport(startDate, endDate, signal);
      setReport(data);
    } catch (e: unknown) {
      if (signal?.aborted) return;
      setError(e instanceof Error ? e.message : "Error desconocido");
    } finally {
      setLoading(false);
    }
  }

  // Carga inicial
  useEffect(() => {
    const controller = new AbortController();
    load(controller.signal);
    return () => controller.abort();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="min-h-screen bg-stone-950 text-stone-100">
      <main className="mx-auto max-w-6xl px-4 py-10 sm:px-6 lg:px-8">
        {/* Header */}
        <header className="rounded-3xl border border-fuchsia-300/30 bg-gradient-to-br from-stone-900 to-fuchsia-950 p-8 shadow-2xl shadow-black/40">
          <p className="text-xs font-bold uppercase tracking-[0.18em] text-fuchsia-300">
            Observabilidad Brasaland
          </p>
          <h1 className="mt-4 text-3xl font-black leading-tight sm:text-4xl">
            Reporte de telemetría
          </h1>
          <p className="mt-4 max-w-3xl text-sm text-stone-300 sm:text-base">
            Métricas técnicas/operacionales obtenidas del bus de telemetría.
            Las métricas se calculan sobre el período seleccionado y se cachean
            60 segundos en el backend.
          </p>
        </header>

        {/* Navegación */}
        <nav className="mt-6 flex flex-wrap gap-3 text-sm">
          <a
            href="/"
            className="rounded-full border border-stone-700 px-4 py-2 text-stone-200 transition hover:border-fuchsia-300 hover:text-fuchsia-200"
          >
            Volver al panel principal
          </a>
          <button
            onClick={() => load()}
            className="rounded-full border border-fuchsia-300/60 bg-fuchsia-300/10 px-4 py-2 font-bold text-fuchsia-200 transition hover:bg-fuchsia-300/20"
          >
            {loading ? "Cargando…" : "Refrescar"}
          </button>
        </nav>

        {/* Selector de fechas */}
        <section className="mt-6 rounded-2xl border border-stone-700 bg-stone-900 p-6">
          <div className="flex flex-wrap items-end gap-4">
            <label className="flex flex-col text-xs text-stone-400">
              Desde
              <input
                type="datetime-local"
                value={startDate}
                onChange={(e) => setStartDate(e.target.value)}
                className="mt-1 rounded-lg border border-stone-700 bg-stone-800 px-3 py-1.5 text-sm text-stone-200"
              />
            </label>
            <label className="flex flex-col text-xs text-stone-400">
              Hasta
              <input
                type="datetime-local"
                value={endDate}
                onChange={(e) => setEndDate(e.target.value)}
                className="mt-1 rounded-lg border border-stone-700 bg-stone-800 px-3 py-1.5 text-sm text-stone-200"
              />
            </label>
            <button
              onClick={() => load()}
              className="rounded-lg border border-fuchsia-300/60 bg-fuchsia-300/10 px-5 py-1.5 font-bold text-fuchsia-200 transition hover:bg-fuchsia-300/20"
            >
              Aplicar
            </button>
          </div>
        </section>

        {/* Estado de carga */}
        {loading && (
          <div className="mt-8 rounded-2xl border border-stone-700 bg-stone-900 p-6 text-center text-sm text-stone-400">
            Cargando reporte…
          </div>
        )}

        {/* Error */}
        {error && (
          <div className="mt-8 rounded-2xl border border-red-400/50 bg-red-950 p-6">
            <p className="text-sm font-bold text-red-200">Error al cargar el reporte</p>
            <pre className="mt-2 overflow-x-auto text-xs text-red-300">{error}</pre>
          </div>
        )}

        {/* Reporte */}
        {report && (
          <>
            {/* Período */}
            <p className="mt-4 text-xs uppercase tracking-wide text-stone-400">
              Período: {new Date(report.period.from).toLocaleString("es-ES")}
              &nbsp;→&nbsp;
              {new Date(report.period.to).toLocaleString("es-ES")}
            </p>

            {/* ── Métrica 1: Eventos por día ── */}
            <section className="mt-8 rounded-2xl border border-stone-700 bg-stone-900 p-6">
              <h2 className="text-xl font-extrabold text-fuchsia-200">Eventos por día</h2>
              <p className="mt-1 text-xs text-stone-400">
                Volumen diario de eventos agrupado por tipo.
              </p>
              {report.metrics.events_per_day.length === 0 ? (
                <p className="mt-4 text-sm text-stone-500">No hay eventos en el período seleccionado.</p>
              ) : (
                <DataTable
                  headers={["Fecha", "Tipo de evento", "Cantidad"]}
                  rows={report.metrics.events_per_day.map(
                    (e) => [fmtDate(e.date), e.event_type, e.count],
                  )}
                />
              )}
            </section>

            {/* ── Métrica 2: Tasa de error por tipo ── */}
            <section className="mt-8 rounded-2xl border border-stone-700 bg-stone-900 p-6">
              <h2 className="text-xl font-extrabold text-fuchsia-200">Tasa de error por tipo</h2>
              <p className="mt-1 text-xs text-stone-400">
                Proporción de eventos con error (status &ge;400 o validation_failed) sobre el total.
              </p>
              {report.metrics.error_rate_by_type.length === 0 ? (
                <p className="mt-4 text-sm text-stone-500">No hay eventos en el período.</p>
              ) : (
                <DataTable
                  headers={["Tipo", "Total", "Errores", "Tasa error"]}
                  rows={report.metrics.error_rate_by_type.map(
                    (e) => [e.event_type, e.total, e.errors, fmtPct(e.error_rate)],
                  )}
                />
              )}
            </section>

            {/* ── Métrica 3: Latencia API ── */}
            <section className="mt-8 rounded-2xl border border-stone-700 bg-stone-900 p-6">
              <h2 className="text-xl font-extrabold text-fuchsia-200">Latencia de API</h2>
              <p className="mt-1 text-xs text-stone-400">
                Percentiles de latencia (ms) de api_request_completed por ruta y método.
              </p>
              {report.metrics.api_latency_summary.length === 0 ? (
                <p className="mt-4 text-sm text-stone-500">
                  No hay eventos api_request_completed con duration_ms en el período.
                </p>
              ) : (
                <DataTable
                  headers={["Ruta", "Método", "Req", "P50", "P90", "P99", "Media"]}
                  rows={report.metrics.api_latency_summary.map(
                    (e) => [
                      e.route_template,
                      e.method,
                      e.count,
                      `${e.p50_ms.toFixed(1)} ms`,
                      `${e.p90_ms.toFixed(1)} ms`,
                      `${e.p99_ms.toFixed(1)} ms`,
                      `${e.mean_ms.toFixed(1)} ms`,
                    ],
                  )}
                />
              )}
            </section>

            {/* ── Métrica 4: Auth failure rate ── */}
            <section className="mt-8 rounded-2xl border border-stone-700 bg-stone-900 p-6">
              <h2 className="text-xl font-extrabold text-fuchsia-200">Tasa de fallo de autenticación</h2>
              <p className="mt-1 text-xs text-stone-400">
                Proporción diaria de intentos fallidos de login sobre el total de intentos.
              </p>
              {report.metrics.auth_failure_rate.length === 0 ? (
                <p className="mt-4 text-sm text-stone-500">
                  No hay eventos de login en el período seleccionado.
                </p>
              ) : (
                <DataTable
                  headers={["Fecha", "Intentos", "Fallos", "Exitosos", "Tasa fallo"]}
                  rows={report.metrics.auth_failure_rate.map(
                    (e) => [fmtDate(e.date), e.attempts, e.failures, e.successes, fmtPct(e.failure_rate)],
                  )}
                />
              )}
            </section>
          </>
        )}
      </main>
    </div>
  );
}
              <h2 className="text-xl font-extrabold text-fuchsia-200">
                Tasa de error por tipo
              </h2>
              <p className="mt-1 text-xs text-stone-400">
                Proporción de eventos con error (status &ge;400 o validation_failed) sobre el total.
              </p>
              {report.metrics.error_rate_by_type.length === 0 ? (
                <p className="mt-4 text-sm text-stone-500">No hay eventos en el período.</p>
              ) : (
                <div className="mt-4 overflow-x-auto">
                  {(() => {
                    const h = ["Tipo", "Total", "Errores", "Tasa error"];
                    const r = report.metrics.error_rate_by_type.map(
                      (e) => [e.event_type, e.total, e.errors, fmtPct(e.error_rate)],
                    );
                    return dangerouslyParseHtml(renderTable(h, r));
                  })()}
                </div>
              )}
            </section>

            {/* ── Métrica 3: Latencia API ── */}
            <section className="mt-8 rounded-2xl border border-stone-700 bg-stone-900 p-6">
              <h2 className="text-xl font-extrabold text-fuchsia-200">
                Latencia de API
              </h2>
              <p className="mt-1 text-xs text-stone-400">
                Percentiles de latencia (ms) de api_request_completed por ruta y método.
              </p>
              {report.metrics.api_latency_summary.length === 0 ? (
                <p className="mt-4 text-sm text-stone-500">
                  No hay eventos api_request_completed con duration_ms en el período.
                </p>
              ) : (
                <div className="mt-4 overflow-x-auto">
                  {(() => {
                    const h = ["Ruta", "Método", "Req", "P50", "P90", "P99", "Media"];
                    const r = report.metrics.api_latency_summary.map(
                      (e) => [e.route_template, e.method, e.count, fmtMs(e.p50_ms), fmtMs(e.p90_ms), fmtMs(e.p99_ms), fmtMs(e.mean_ms)],
                    );
                    return dangerouslyParseHtml(renderTable(h, r));
                  })()}
                </div>
              )}
            </section>

            {/* ── Métrica 4: Auth failure rate ── */}
            <section className="mt-8 rounded-2xl border border-stone-700 bg-stone-900 p-6">
              <h2 className="text-xl font-extrabold text-fuchsia-200">
                Tasa de fallo de autenticación
              </h2>
              <p className="mt-1 text-xs text-stone-400">
                Proporción diaria de intentos fallidos de login sobre el total de intentos.
              </p>
              {report.metrics.auth_failure_rate.length === 0 ? (
                <p className="mt-4 text-sm text-stone-500">
                  No hay eventos de login en el período seleccionado.
                </p>
              ) : (
                <div className="mt-4 overflow-x-auto">
                  {(() => {
                    const h = ["Fecha", "Intentos", "Fallos", "Exitosos", "Tasa fallo"];
                    const r = report.metrics.auth_failure_rate.map(
                      (e) => [fmtDate(e.date), e.attempts, e.failures, e.successes, fmtPct(e.failure_rate)],
                    );
                    return dangerouslyParseHtml(renderTable(h, r));
                  })()}
                </div>
              )}
            </section>
          </>
        )}
      </main>
    </div>
  );
}