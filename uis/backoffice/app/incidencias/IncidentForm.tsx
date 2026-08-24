"use client";

import { useState } from "react";
import {
  type IncidentCategory,
  type IncidentOrigin,
  type IncidentPriority,
  type IncidentCreatePayload,
  VALID_LOCAL_IDS,
  LOCAL_ID_LABELS,
  PRIORITY_LABELS,
  CATEGORY_LABELS,
  ORIGIN_LABELS,
} from "./types";

interface Props {
  onCreated: () => void;
}

export default function IncidentForm({ onCreated }: Props) {
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [fecha_reporte, setFechaReporte] = useState(new Date().toISOString().slice(0, 10));
  const [local_id, setLocalId] = useState<string>(VALID_LOCAL_IDS[0]);
  const [origen, setOrigen] = useState<IncidentOrigin>("cliente");
  const [categoria, setCategoria] = useState<IncidentCategory>("queja");
  const [prioridad, setPrioridad] = useState<IncidentPriority>("media");
  const [cliente_id, setClienteId] = useState("");
  const [cliente_email, setClienteEmail] = useState("");
  const [cliente_telefono, setClienteTelefono] = useState("");

  const reset = () => {
    setTitle("");
    setDescription("");
    setFechaReporte(new Date().toISOString().slice(0, 10));
    setLocalId(VALID_LOCAL_IDS[0]);
    setOrigen("cliente");
    setCategoria("queja");
    setPrioridad("media");
    setClienteId("");
    setClienteEmail("");
    setClienteTelefono("");
    setError(null);
    setSuccess(false);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSuccess(false);

    if (!title.trim() || !description.trim()) {
      setError("El título y la descripción son obligatorios.");
      return;
    }

    const payload: IncidentCreatePayload = {
      title: title.trim(),
      description: description.trim(),
      fecha_reporte,
      local_id,
      origen,
      categoria,
      prioridad,
    };

    if (origen === "cliente") {
      if (cliente_id.trim()) payload.cliente_id = cliente_id.trim();
      if (cliente_email.trim()) payload.cliente_email = cliente_email.trim();
      if (cliente_telefono.trim()) payload.cliente_telefono = cliente_telefono.trim();
    }

    setLoading(true);
    try {
      const res = await fetch("/api/incidents", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail ?? "Error al crear la incidencia");
      }

      setSuccess(true);
      reset();
      onCreated();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error de conexión");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <button
        onClick={() => setOpen(!open)}
        className="rounded-full bg-cyan-600 px-5 py-2 text-sm font-bold text-white transition hover:bg-cyan-500"
      >
        {open ? "Cerrar formulario" : "+ Nueva incidencia"}
      </button>

      {open && (
        <form onSubmit={handleSubmit} className="mt-4 space-y-4 rounded-xl border border-stone-700 bg-stone-900/80 p-5">
          <h3 className="text-lg font-bold text-cyan-200">Registrar nueva incidencia</h3>

          {error && (
            <div className="rounded-lg border border-red-500/60 bg-red-950/50 px-4 py-3 text-sm text-red-200">
              {error}
            </div>
          )}

          {success && (
            <div className="rounded-lg border border-emerald-500/60 bg-emerald-950/50 px-4 py-3 text-sm text-emerald-200">
              Incidencia creada correctamente.
            </div>
          )}

          <div className="grid gap-4 sm:grid-cols-2">
            {/* Título */}
            <div className="sm:col-span-2">
              <label className="block text-xs font-bold uppercase tracking-wide text-stone-400">
                Título *
              </label>
              <input
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                required
                className="mt-1 w-full rounded-lg border border-stone-600 bg-stone-950 px-3 py-2 text-sm text-stone-100"
              />
            </div>

            {/* Descripción */}
            <div className="sm:col-span-2">
              <label className="block text-xs font-bold uppercase tracking-wide text-stone-400">
                Descripción *
              </label>
              <textarea
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                required
                rows={3}
                className="mt-1 w-full rounded-lg border border-stone-600 bg-stone-950 px-3 py-2 text-sm text-stone-100"
              />
            </div>

            {/* Fecha */}
            <div>
              <label className="block text-xs font-bold uppercase tracking-wide text-stone-400">
                Fecha del reporte
              </label>
              <input
                type="date"
                value={fecha_reporte}
                onChange={(e) => setFechaReporte(e.target.value)}
                className="mt-1 w-full rounded-lg border border-stone-600 bg-stone-950 px-3 py-2 text-sm text-stone-100"
              />
            </div>

            {/* Local */}
            <div>
              <label className="block text-xs font-bold uppercase tracking-wide text-stone-400">
                Local
              </label>
              <select
                value={local_id}
                onChange={(e) => setLocalId(e.target.value)}
                className="mt-1 w-full rounded-lg border border-stone-600 bg-stone-950 px-3 py-2 text-sm text-stone-100"
              >
                {VALID_LOCAL_IDS.map((id) => (
                  <option key={id} value={id}>
                    {id} — {LOCAL_ID_LABELS[id]}
                  </option>
                ))}
              </select>
            </div>

            {/* Origen */}
            <div>
              <label className="block text-xs font-bold uppercase tracking-wide text-stone-400">
                Origen
              </label>
              <select
                value={origen}
                onChange={(e) => setOrigen(e.target.value as IncidentOrigin)}
                className="mt-1 w-full rounded-lg border border-stone-600 bg-stone-950 px-3 py-2 text-sm text-stone-100"
              >
                {(["cliente", "interno"] as IncidentOrigin[]).map((o) => (
                  <option key={o} value={o}>{ORIGIN_LABELS[o]}</option>
                ))}
              </select>
            </div>

            {/* Categoría */}
            <div>
              <label className="block text-xs font-bold uppercase tracking-wide text-stone-400">
                Categoría
              </label>
              <select
                value={categoria}
                onChange={(e) => setCategoria(e.target.value as IncidentCategory)}
                className="mt-1 w-full rounded-lg border border-stone-600 bg-stone-950 px-3 py-2 text-sm text-stone-100"
              >
                {(["queja", "solicitud", "fallo_operativo"] as IncidentCategory[]).map((c) => (
                  <option key={c} value={c}>{CATEGORY_LABELS[c]}</option>
                ))}
              </select>
            </div>

            {/* Prioridad */}
            <div>
              <label className="block text-xs font-bold uppercase tracking-wide text-stone-400">
                Prioridad
              </label>
              <select
                value={prioridad}
                onChange={(e) => setPrioridad(e.target.value as IncidentPriority)}
                className="mt-1 w-full rounded-lg border border-stone-600 bg-stone-950 px-3 py-2 text-sm text-stone-100"
              >
                {(["baja", "media", "alta", "critica"] as IncidentPriority[]).map((p) => (
                  <option key={p} value={p}>{PRIORITY_LABELS[p]}</option>
                ))}
              </select>
            </div>

            {/* Campos de cliente (solo si origen === cliente) */}
            {origen === "cliente" && (
              <>
                <div>
                  <label className="block text-xs font-bold uppercase tracking-wide text-stone-400">
                    ID del cliente
                  </label>
                  <input
                    value={cliente_id}
                    onChange={(e) => setClienteId(e.target.value)}
                    placeholder="Ej: C-2001"
                    className="mt-1 w-full rounded-lg border border-stone-600 bg-stone-950 px-3 py-2 text-sm text-stone-100"
                  />
                </div>
                <div>
                  <label className="block text-xs font-bold uppercase tracking-wide text-stone-400">
                    Email del cliente
                  </label>
                  <input
                    type="email"
                    value={cliente_email}
                    onChange={(e) => setClienteEmail(e.target.value)}
                    placeholder="cliente@email.com"
                    className="mt-1 w-full rounded-lg border border-stone-600 bg-stone-950 px-3 py-2 text-sm text-stone-100"
                  />
                </div>
                <div>
                  <label className="block text-xs font-bold uppercase tracking-wide text-stone-400">
                    Teléfono del cliente
                  </label>
                  <input
                    value={cliente_telefono}
                    onChange={(e) => setClienteTelefono(e.target.value)}
                    placeholder="Ej: 3001234567"
                    className="mt-1 w-full rounded-lg border border-stone-600 bg-stone-950 px-3 py-2 text-sm text-stone-100"
                  />
                </div>
              </>
            )}
          </div>

          <div className="flex gap-3 pt-2">
            <button
              type="submit"
              disabled={loading}
              className="rounded-full bg-cyan-600 px-5 py-2 text-sm font-bold text-white transition hover:bg-cyan-500 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {loading ? "Creando..." : "Crear incidencia"}
            </button>
            <button
              type="button"
              onClick={() => setOpen(false)}
              className="rounded-full border border-stone-600 px-5 py-2 text-sm text-stone-300 transition hover:border-stone-400"
            >
              Cancelar
            </button>
          </div>
        </form>
      )}
    </div>
  );
}