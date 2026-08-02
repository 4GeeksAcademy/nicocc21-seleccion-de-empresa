"use client";

import { useEffect, useMemo, useState } from "react";

type Summary = {
  total_processed: number;
  total_valid: number;
  total_invalid: number;
  invalid_reasons: Record<string, number>;
  by_category: Record<string, number>;
  by_state: Record<string, number>;
  closed_with_score: number;
  avg_satisfaction_closed_with_score: number;
};

function resolveApiBase(): string {
  const configured = process.env.NEXT_PUBLIC_INCIDENTS_API_BASE;
  if (configured && configured.trim().length > 0) {
    return configured;
  }

  if (typeof window !== "undefined") {
    const origin = window.location.origin;
    if (origin.includes("-3000.")) {
      return origin.replace("-3000.", "-8000.");
    }
  }

  return "http://localhost:8000";
}

function formatMetricLabel(key: string): string {
  return key.replaceAll("_", " ");
}

export default function IncidentsAnalyzer() {
  const [apiBase, setApiBase] = useState("mismo origen (/api)");
  const [file, setFile] = useState<File | null>(null);
  const [summary, setSummary] = useState<Summary | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    setApiBase("mismo origen (/api)");
  }, []);

  const invalidTotal = useMemo(() => {
    if (!summary) return 0;
    return Object.values(summary.invalid_reasons).reduce((acc, value) => acc + value, 0);
  }, [summary]);

  const onSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError(null);

    if (!file) {
      setError("Selecciona un archivo CSV antes de analizar.");
      return;
    }

    const formData = new FormData();
    formData.append("file", file);

    setLoading(true);
    try {
      const response = await fetch(`/api/incidents/analyze`, {
        method: "POST",
        body: formData,
      });

      const payload = (await response.json()) as Summary | { error: string };
      if (!response.ok) {
        setSummary(null);
        setError((payload as { error?: string }).error ?? "No se pudo procesar el archivo.");
        return;
      }

      setSummary(payload as Summary);
    } catch {
      setSummary(null);
      setError(
        "No se pudo conectar con la API de incidencias. Verifica que el backend este en ejecucion."
      );
    } finally {
      setLoading(false);
    }
  };

  const onDownload = async () => {
    setError(null);
    try {
      const response = await fetch(`/api/incidents/results/export`);
      if (!response.ok) {
        const payload = (await response.json()) as { error?: string };
        setError(payload.error ?? "No hay resultados para exportar.");
        return;
      }

      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = "incidents-results.csv";
      anchor.click();
      window.URL.revokeObjectURL(url);
    } catch {
      setError("No se pudo descargar el CSV de resultados.");
    }
  };

  return (
    <div>
      <h2 className="text-xl font-extrabold text-cyan-200">Cargar y analizar CSV</h2>
      <p className="mt-2 text-sm text-stone-300">
        Endpoint activo esperado: <span className="font-semibold text-cyan-300">{apiBase}</span>
      </p>

      <form onSubmit={onSubmit} className="mt-5 flex flex-col gap-4 rounded-xl border border-stone-700 p-4">
        <input
          type="file"
          accept=".csv,text/csv"
          onChange={(event) => {
            const selected = event.target.files?.[0] ?? null;
            setFile(selected);
          }}
          className="block w-full rounded-lg border border-stone-600 bg-stone-950 px-3 py-2 text-sm text-stone-100 file:mr-4 file:rounded-md file:border-0 file:bg-cyan-700 file:px-3 file:py-2 file:text-sm file:font-semibold file:text-white"
        />

        <div className="flex flex-wrap gap-3">
          <button
            type="submit"
            disabled={loading}
            className="rounded-full bg-cyan-600 px-5 py-2 text-sm font-bold text-white transition hover:bg-cyan-500 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {loading ? "Analizando..." : "Analizar archivo"}
          </button>
          <button
            type="button"
            onClick={onDownload}
            className="rounded-full border border-cyan-400 px-5 py-2 text-sm font-bold text-cyan-200 transition hover:bg-cyan-900/40"
          >
            Descargar resultados CSV
          </button>
        </div>
      </form>

      {error ? (
        <div className="mt-4 rounded-lg border border-red-500/60 bg-red-950/50 px-4 py-3 text-sm text-red-200">
          {error}
        </div>
      ) : null}

      {summary ? (
        <div className="mt-6 space-y-6">
          <section className="rounded-xl border border-stone-700 bg-stone-950/60 p-4">
            <h3 className="text-lg font-bold text-cyan-200">Métricas generales</h3>
            <div className="mt-3 grid gap-3 sm:grid-cols-3">
              <div className="rounded-lg border border-stone-700 p-3">
                <p className="text-xs uppercase tracking-wide text-stone-400">Procesados</p>
                <p className="mt-1 text-2xl font-black">{summary.total_processed}</p>
              </div>
              <div className="rounded-lg border border-stone-700 p-3">
                <p className="text-xs uppercase tracking-wide text-stone-400">Válidos</p>
                <p className="mt-1 text-2xl font-black text-emerald-300">{summary.total_valid}</p>
              </div>
              <div className="rounded-lg border border-stone-700 p-3">
                <p className="text-xs uppercase tracking-wide text-stone-400">Inválidos</p>
                <p className="mt-1 text-2xl font-black text-rose-300">{summary.total_invalid}</p>
              </div>
            </div>
          </section>

          <section className="rounded-xl border border-stone-700 bg-stone-950/60 p-4">
            <h3 className="text-lg font-bold text-cyan-200">Inválidos por tipo</h3>
            {invalidTotal === 0 ? (
              <p className="mt-2 text-sm text-emerald-300">No se encontraron registros inválidos.</p>
            ) : (
              <ul className="mt-3 space-y-2">
                {Object.entries(summary.invalid_reasons).map(([reason, count]) => (
                  <li key={reason} className="flex items-center justify-between rounded-lg border border-stone-700 px-3 py-2 text-sm">
                    <span className="text-stone-200">{formatMetricLabel(reason)}</span>
                    <span className="font-bold text-rose-300">{count}</span>
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section className="grid gap-6 lg:grid-cols-2">
            <div className="rounded-xl border border-stone-700 bg-stone-950/60 p-4">
              <h3 className="text-lg font-bold text-cyan-200">Desglose por categoría</h3>
              <ul className="mt-3 space-y-2">
                {Object.entries(summary.by_category).map(([category, count]) => (
                  <li key={category} className="flex items-center justify-between rounded-lg border border-stone-700 px-3 py-2 text-sm">
                    <span className="text-stone-200">{formatMetricLabel(category)}</span>
                    <span className="font-bold text-cyan-200">{count}</span>
                  </li>
                ))}
              </ul>
            </div>

            <div className="rounded-xl border border-stone-700 bg-stone-950/60 p-4">
              <h3 className="text-lg font-bold text-cyan-200">Desglose por estado</h3>
              <ul className="mt-3 space-y-2">
                {Object.entries(summary.by_state).map(([state, count]) => (
                  <li key={state} className="flex items-center justify-between rounded-lg border border-stone-700 px-3 py-2 text-sm">
                    <span className="text-stone-200">{formatMetricLabel(state)}</span>
                    <span className="font-bold text-cyan-200">{count}</span>
                  </li>
                ))}
              </ul>
            </div>
          </section>

          <section className="rounded-xl border border-stone-700 bg-stone-950/60 p-4">
            <h3 className="text-lg font-bold text-cyan-200">Índice de satisfacción</h3>
            <p className="mt-2 text-sm text-stone-300">
              Cerrados con puntuación: <span className="font-bold text-cyan-200">{summary.closed_with_score}</span>
            </p>
            <p className="mt-1 text-sm text-stone-300">
              Satisfacción media: <span className="font-bold text-cyan-200">{summary.avg_satisfaction_closed_with_score}</span>
            </p>
          </section>
        </div>
      ) : null}
    </div>
  );
}
