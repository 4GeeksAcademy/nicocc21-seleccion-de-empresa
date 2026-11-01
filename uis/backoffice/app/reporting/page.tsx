"use client";

import { useEffect, useState, type FormEvent } from "react";
import Link from "next/link";

interface LocationPerformance {
  location_id: string;
  country: string;
  total_purchase_cost: number;
  total_waste_cost: number;
  waste_ratio: number;
  stockout_events_count: number;
  price_alert_events_count: number;
  currency: string;
}

interface WeeklyPerformanceReport {
  week_start: string;
  locations: LocationPerformance[];
}

async function fetchWeeklyReport(
  weekStart: string,
  signal?: AbortSignal
): Promise<WeeklyPerformanceReport | null> {
  const params = new URLSearchParams();
  if (weekStart) params.set("week_start", weekStart);

  const query = params.toString();
  const response = await fetch(
    `/api/reporting/weekly-location-performance${query ? `?${query}` : ""}`,
    { cache: "no-store", signal }
  );

  if (response.status === 404) return null;
  if (!response.ok) {
    throw new Error(`No se pudo cargar el reporte (HTTP ${response.status}).`);
  }

  return response.json() as Promise<WeeklyPerformanceReport>;
}

function formatCurrency(value: number, currency: string): string {
  return new Intl.NumberFormat("es-CO", {
    style: "currency",
    currency,
    maximumFractionDigits: currency === "COP" ? 0 : 2,
  }).format(value);
}

function formatWeekStart(weekStart: string): string {
  return new Intl.DateTimeFormat("es-CO", {
    dateStyle: "long",
    timeZone: "UTC",
  }).format(new Date(`${weekStart}T00:00:00Z`));
}

export default function WeeklyPerformancePage() {
  const [weekStart, setWeekStart] = useState("");
  const [report, setReport] = useState<WeeklyPerformanceReport | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const controller = new AbortController();

    fetchWeeklyReport("", controller.signal)
      .then(setReport)
      .catch((cause: unknown) => {
        if (!controller.signal.aborted) {
          setError(cause instanceof Error ? cause.message : "Error inesperado.");
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) setIsLoading(false);
      });

    return () => controller.abort();
  }, []);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (
      weekStart &&
      new Date(`${weekStart}T00:00:00Z`).getUTCDay() !== 1
    ) {
      setError("Selecciona el lunes de la semana que quieres consultar.");
      return;
    }

    setIsLoading(true);
    setError(null);
    try {
      setReport(await fetchWeeklyReport(weekStart));
    } catch (cause: unknown) {
      setError(cause instanceof Error ? cause.message : "Error inesperado.");
      setReport(null);
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-stone-950 text-stone-100">
      <main className="mx-auto max-w-7xl px-4 py-10 sm:px-6 lg:px-8">
        <header className="border-b border-stone-800 pb-6">
          <p className="text-xs font-bold uppercase tracking-[0.18em] text-amber-300">
            Brasaland · Reporte de negocio
          </p>
          <h1 className="mt-3 text-3xl font-black leading-tight sm:text-4xl">
            Reporte Semanal de Costo y Merma por Local
          </h1>
          <p className="mt-3 max-w-3xl text-sm text-stone-300 sm:text-base">
            Indicadores de compra, merma y disponibilidad para los 14 locales.
          </p>
        </header>

        <nav className="mt-5 flex flex-wrap gap-4 text-sm">
          <Link className="text-amber-200 underline-offset-4 hover:underline" href="/">
            Volver al panel principal
          </Link>
          <a
            className="text-stone-300 underline-offset-4 hover:underline"
            href="/telemetry-report"
          >
            Reporte de telemetría
          </a>
        </nav>

        <section className="mt-6 border-y border-stone-800 py-5">
          <form className="flex flex-wrap items-end gap-4" onSubmit={handleSubmit}>
            <label className="flex flex-col gap-1 text-sm text-stone-300">
              Semana a consultar
              <input
                className="rounded-md border border-stone-700 bg-stone-900 px-3 py-2 text-stone-100"
                type="date"
                value={weekStart}
                onChange={(event) => setWeekStart(event.target.value)}
              />
            </label>
            <button
              className="rounded-md bg-amber-300 px-4 py-2 font-bold text-stone-950 transition hover:bg-amber-200 disabled:cursor-wait disabled:opacity-60"
              disabled={isLoading}
              type="submit"
            >
              {isLoading ? "Cargando…" : "Consultar semana"}
            </button>
            <p className="text-xs text-stone-400">
              Sin fecha seleccionada se muestra la semana más reciente.
            </p>
          </form>
        </section>

        {report && (
          <p className="mt-5 text-sm text-stone-300">
            Semana iniciada el <strong>{formatWeekStart(report.week_start)}</strong>
          </p>
        )}

        {isLoading && (
          <p className="mt-8 text-sm text-stone-400" role="status">
            Cargando indicadores…
          </p>
        )}

        {error && (
          <p className="mt-8 border-l-2 border-red-400 pl-4 text-sm text-red-200" role="alert">
            {error}
          </p>
        )}

        {!isLoading && !error && !report && (
          <p className="mt-8 text-sm text-stone-300">
            No hay un reporte disponible para esa semana.
          </p>
        )}

        {!isLoading && !error && report && report.locations.length === 0 && (
          <p className="mt-8 text-sm text-stone-300">
            El reporte de esa semana todavía no contiene locales.
          </p>
        )}

        {!isLoading && !error && report && report.locations.length > 0 && (
          <div className="mt-5 overflow-x-auto border-y border-stone-800">
            <table className="min-w-full text-left text-sm">
              <thead>
                <tr className="border-b border-stone-700 text-xs text-stone-300">
                  <th className="px-3 py-3">Local</th>
                  <th className="px-3 py-3">País</th>
                  <th className="px-3 py-3 text-right">Costo de compra por local</th>
                  <th className="px-3 py-3 text-right">Costo de merma por local</th>
                  <th className="px-3 py-3 text-right">Ratio de merma</th>
                  <th className="px-3 py-3 text-right">Frecuencia de quiebre de stock</th>
                  <th className="px-3 py-3 text-right">Frecuencia de alertas de precio</th>
                </tr>
              </thead>
              <tbody>
                {report.locations.map((location) => (
                  <tr
                    className="border-b border-stone-800/80 last:border-0"
                    key={location.location_id}
                  >
                    <th className="whitespace-nowrap px-3 py-3 font-semibold">
                      {location.location_id}
                    </th>
                    <td className="px-3 py-3 text-stone-400">{location.country}</td>
                    <td className="whitespace-nowrap px-3 py-3 text-right">
                      {formatCurrency(location.total_purchase_cost, location.currency)}
                    </td>
                    <td className="whitespace-nowrap px-3 py-3 text-right">
                      {formatCurrency(location.total_waste_cost, location.currency)}
                    </td>
                    <td className="px-3 py-3 text-right">
                      {new Intl.NumberFormat("es-CO", {
                        style: "percent",
                        maximumFractionDigits: 1,
                      }).format(location.waste_ratio)}
                    </td>
                    <td className="px-3 py-3 text-right">
                      {location.stockout_events_count}
                    </td>
                    <td className="px-3 py-3 text-right">
                      {location.price_alert_events_count}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </main>
    </div>
  );
}