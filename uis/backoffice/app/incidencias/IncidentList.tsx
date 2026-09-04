"use client";

import { useEffect, useState } from "react";
import {
  type Incident,
  type IncidentState,
  type IncidentCategory,
  type IncidentOrigin,
  type IncidentPriority,
  type IncidentsSummary,
  VALID_LOCAL_IDS,
  LOCAL_ID_LABELS,
  PRIORITY_LABELS,
  STATE_LABELS,
  CATEGORY_LABELS,
  ORIGIN_LABELS,
  priorityColor,
  stateColor,
} from "./types";

export default function IncidentList() {
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [summary, setSummary] = useState<IncidentsSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Filtros
  const [filterEstado, setFilterEstado] = useState<string>("");
  const [filterLocal, setFilterLocal] = useState<string>("");
  const [filterCategoria, setFilterCategoria] = useState<string>("");
  const [filterOrigen, setFilterOrigen] = useState<string>("");
  const [filterPrioridad, setFilterPrioridad] = useState<string>("");
  const [refreshKey, setRefreshKey] = useState(0);

  useEffect(() => {
    let cancelled = false;
    const params = new URLSearchParams();
    if (filterEstado) params.set("estado", filterEstado);
    if (filterLocal) params.set("local_id", filterLocal);
    if (filterCategoria) params.set("categoria", filterCategoria);
    if (filterOrigen) params.set("origen", filterOrigen);
    if (filterPrioridad) params.set("prioridad", filterPrioridad);

    const qs = params.toString();
    Promise.all([
      fetch(`/api/incidents${qs ? `?${qs}` : ""}`, { cache: "no-store" }),
      fetch("/api/incidents/summary", { cache: "no-store" }),
    ])
      .then(async ([incRes, sumRes]) => {
        if (cancelled) return;
        if (!incRes.ok) throw new Error("Error al cargar incidencias");
        const data = (await incRes.json()) as Incident[];
        setIncidents(data);
        if (sumRes.ok) {
          const sumData = (await sumRes.json()) as IncidentsSummary;
          setSummary(sumData);
        }
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : "Error de conexión");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => { cancelled = true; };
  }, [filterEstado, filterLocal, filterCategoria, filterOrigen, filterPrioridad, refreshKey]);

  const handleStatusChange = async (id: number, newStatus: IncidentState) => {
    try {
      const res = await fetch(`/api/incidents/${id}/status`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ estado: newStatus }),
      });
      if (!res.ok) throw new Error("Error al actualizar estado");
      setRefreshKey((k) => k + 1);
    } catch {
      setError("No se pudo actualizar el estado");
    }
  };

  return (
    <div className="space-y-6">
      {/* Summary cards */}
      {summary && (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
          <div className="rounded-lg border border-stone-700 bg-stone-950/60 p-3">
            <p className="text-xs uppercase text-stone-400">Total</p>
            <p className="text-2xl font-black text-white">{summary.total}</p>
          </div>
          <div className="rounded-lg border border-sky-700 bg-sky-950/20 p-3">
            <p className="text-xs uppercase text-sky-300">Abiertas</p>
            <p className="text-2xl font-black text-sky-200">{summary.by_state.abierta ?? 0}</p>
          </div>
          <div className="rounded-lg border border-amber-700 bg-amber-950/20 p-3">
            <p className="text-xs uppercase text-amber-300">En progreso</p>
            <p className="text-2xl font-black text-amber-200">{summary.by_state.en_progreso ?? 0}</p>
          </div>
          <div className="rounded-lg border border-emerald-700 bg-emerald-950/20 p-3">
            <p className="text-xs uppercase text-emerald-300">Resueltas</p>
            <p className="text-2xl font-black text-emerald-200">{summary.by_state.resuelta ?? 0}</p>
          </div>
          <div className="rounded-lg border border-rose-700 bg-rose-950/20 p-3">
            <p className="text-xs uppercase text-rose-300">Críticas</p>
            <p className="text-2xl font-black text-rose-200">{summary.by_priority.critica ?? 0}</p>
          </div>
        </div>
      )}

      {/* Filtros */}
      <div className="flex flex-wrap gap-3 rounded-xl border border-stone-700 bg-stone-900/60 p-4">
        <h4 className="w-full text-xs font-bold uppercase tracking-wide text-stone-400">Filtros</h4>
        <select
          value={filterEstado}
          onChange={(e) => setFilterEstado(e.target.value)}
          className="rounded-lg border border-stone-600 bg-stone-950 px-3 py-2 text-sm text-stone-100"
        >
          <option value="">Todos los estados</option>
          {(["abierta", "en_progreso", "resuelta", "descartada"] as IncidentState[]).map((s) => (
            <option key={s} value={s}>{STATE_LABELS[s]}</option>
          ))}
        </select>
        <select
          value={filterLocal}
          onChange={(e) => setFilterLocal(e.target.value)}
          className="rounded-lg border border-stone-600 bg-stone-950 px-3 py-2 text-sm text-stone-100"
        >
          <option value="">Todos los locales</option>
          {VALID_LOCAL_IDS.map((id) => (
            <option key={id} value={id}>{id} — {LOCAL_ID_LABELS[id]}</option>
          ))}
        </select>
        <select
          value={filterCategoria}
          onChange={(e) => setFilterCategoria(e.target.value)}
          className="rounded-lg border border-stone-600 bg-stone-950 px-3 py-2 text-sm text-stone-100"
        >
          <option value="">Todas las categorías</option>
          {(["queja", "solicitud", "fallo_operativo"] as IncidentCategory[]).map((c) => (
            <option key={c} value={c}>{CATEGORY_LABELS[c]}</option>
          ))}
        </select>
        <select
          value={filterOrigen}
          onChange={(e) => setFilterOrigen(e.target.value)}
          className="rounded-lg border border-stone-600 bg-stone-950 px-3 py-2 text-sm text-stone-100"
        >
          <option value="">Todos los orígenes</option>
          {(["cliente", "interno"] as IncidentOrigin[]).map((o) => (
            <option key={o} value={o}>{ORIGIN_LABELS[o]}</option>
          ))}
        </select>
        <select
          value={filterPrioridad}
          onChange={(e) => setFilterPrioridad(e.target.value)}
          className="rounded-lg border border-stone-600 bg-stone-950 px-3 py-2 text-sm text-stone-100"
        >
          <option value="">Todas las prioridades</option>
          {(["baja", "media", "alta", "critica"] as IncidentPriority[]).map((p) => (
            <option key={p} value={p}>{PRIORITY_LABELS[p]}</option>
          ))}
        </select>
      </div>

      {error && (
        <div className="rounded-lg border border-red-500/60 bg-red-950/50 px-4 py-3 text-sm text-red-200">
          {error}
        </div>
      )}

      {loading ? (
        <div className="py-8 text-center text-sm text-stone-400">Cargando incidencias...</div>
      ) : incidents.length === 0 ? (
        <div className="py-8 text-center text-sm text-stone-400">
          No se encontraron incidencias con los filtros seleccionados.
        </div>
      ) : (
        <div className="space-y-3">
          {incidents.map((inc) => (
            <div
              key={inc.id}
              className="rounded-xl border border-stone-700 bg-stone-900/80 p-4 transition hover:border-stone-600"
            >
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div className="flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-xs font-mono text-stone-500">{inc.incident_id}</span>
                    <span className={`rounded-full border px-2.5 py-0.5 text-xs font-bold ${stateColor(inc.estado)}`}>
                      {STATE_LABELS[inc.estado]}
                    </span>
                    <span className={`rounded-full border px-2.5 py-0.5 text-xs font-bold ${priorityColor(inc.prioridad)}`}>
                      {PRIORITY_LABELS[inc.prioridad]}
                    </span>
                    <span className="rounded-full border border-stone-700 bg-stone-800/40 px-2.5 py-0.5 text-xs text-stone-300">
                      {LOCAL_ID_LABELS[inc.local_id] ?? inc.local_id}
                    </span>
                    <span className="rounded-full border border-stone-700 bg-stone-800/40 px-2.5 py-0.5 text-xs text-stone-300">
                      {CATEGORY_LABELS[inc.categoria]}
                    </span>
                  </div>
                  <h4 className="mt-2 text-sm font-bold text-stone-100">{inc.title}</h4>
                  <p className="mt-1 text-xs text-stone-400 line-clamp-2">{inc.description}</p>
                  <div className="mt-2 flex flex-wrap items-center gap-3 text-xs text-stone-500">
                    <span>{inc.fecha_reporte}</span>
                    <span>{ORIGIN_LABELS[inc.origen]}</span>
                    {inc.cliente_id && <span>Cliente: {inc.cliente_id}</span>}
                    {inc.satisfaccion != null && <span>Satisfacción: {inc.satisfaccion}/5</span>}
                  </div>
                </div>

                {/* Acción: cambiar estado */}
                <div className="flex-shrink-0">
                  <select
                    value={inc.estado}
                    onChange={(e) => handleStatusChange(inc.id, e.target.value as IncidentState)}
                    className="rounded-lg border border-stone-600 bg-stone-950 px-2 py-1.5 text-xs text-stone-100"
                  >
                    {(["abierta", "en_progreso", "resuelta", "descartada"] as IncidentState[]).map((s) => (
                      <option key={s} value={s}>{STATE_LABELS[s]}</option>
                    ))}
                  </select>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}