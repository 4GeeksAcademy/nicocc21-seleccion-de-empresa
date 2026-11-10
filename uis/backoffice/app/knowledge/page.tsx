"use client";

import { useState, FormEvent } from "react";

type QueryResponse = {
  answer: string;
};

type ApiError = {
  detail?: string | { code?: string; telemetry_events?: unknown[] };
};

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8001";

export default function KnowledgeQueryPage() {
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    const trimmed = question.trim();
    if (!trimmed) return;

    setLoading(true);
    setAnswer("");
    setError(null);

    try {
      const res = await fetch(`${API_BASE}/knowledge/query`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: trimmed }),
      });

      if (!res.ok) {
        let errMsg = `Error del servidor (${res.status})`;
        try {
          const errBody: ApiError = await res.json();
          if (typeof errBody.detail === "string") {
            errMsg = errBody.detail;
          } else if (errBody.detail && typeof errBody.detail.code === "string") {
            errMsg = errBody.detail.code;
          }
        } catch {
          // fallback al mensaje de error por defecto
        }
        throw new Error(errMsg);
      }

      const data: QueryResponse = await res.json();
      setAnswer(data.answer);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Error inesperado";
      setError(message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-stone-950 text-stone-100">
      <main className="mx-auto max-w-4xl px-4 py-10 sm:px-6 lg:px-8">
        {/* Header */}
        <header className="mb-10">
          <p className="text-xs font-bold uppercase tracking-[0.18em] text-amber-300">
            Brasaland OPS Console
          </p>
          <h1 className="mt-4 text-3xl font-black leading-tight sm:text-4xl">
            Asistente de Conocimiento Brasaland
          </h1>
          <p className="mt-4 max-w-3xl text-sm text-stone-300 sm:text-base">
            Consulta en lenguaje natural sobre políticas, alérgenos, programa de lealtad,
            protocolo de desperdicio y pedidos a proveedores. Las respuestas son generadas
            por IA basándose exclusivamente en la documentación oficial de Brasaland.
          </p>
        </header>

        {/* Formulario */}
        <form onSubmit={handleSubmit} className="mb-8">
          <div className="flex gap-3">
            <input
              type="text"
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              placeholder="Ej: ¿Cuántos puntos necesito para el nivel Oro?"
              className="flex-1 rounded-2xl border border-stone-600 bg-stone-800 px-4 py-3 text-stone-200 placeholder-stone-500 transition focus:border-amber-400 focus:ring-2 focus:ring-amber-400/30"
              disabled={loading}
            />
            <button
              type="submit"
              disabled={loading || !question.trim()}
              className="rounded-2xl bg-amber-600 px-6 py-3 font-bold text-stone-950 transition hover:bg-amber-500 disabled:opacity-40 disabled:cursor-not-allowed"
            >
              {loading ? "Consultando…" : "Preguntar"}
            </button>
          </div>
        </form>

        {/* Loading */}
        {loading && (
          <div className="rounded-2xl border border-stone-600 bg-stone-800 p-6">
            <p className="text-stone-300 text-sm">
              <span className="inline-block animate-pulse">●</span> Buscando en la base de conocimiento…
            </p>
          </div>
        )}

        {/* Error */}
        {error && (
          <div className="rounded-2xl border border-red-500 bg-red-950 p-6" role="alert">
            <h2 className="text-lg font-bold text-red-300">Error</h2>
            <p className="mt-2 text-red-200">{error}</p>
            <p className="mt-4 text-sm text-stone-400">
              Intenta de nuevo. Si el problema persiste, verifica que el servidor
              backend esté funcionando y que la base de conocimiento esté indexada.
            </p>
          </div>
        )}

        {/* Respuesta */}
        {answer && !loading && (
          <div className="rounded-2xl border border-emerald-300/40 bg-stone-800 p-6">
            <h2 className="text-lg font-bold text-emerald-300">Respuesta</h2>
            <div className="mt-2 whitespace-pre-wrap text-stone-200 leading-relaxed">
              {answer}
            </div>
          </div>
        )}

        {/* Sugerencias de preguntas */}
        <section className="mt-12">
          <h2 className="text-lg font-bold text-stone-200 mb-4">
            Preguntas de ejemplo
          </h2>
          <div className="flex flex-wrap gap-2">
            {[
              "¿Cuántos puntos necesito para el nivel Oro?",
              "¿La Costilla BBQ tiene alérgenos?",
              "¿Cuál es el plazo de entrega para pedidos regulares de alimentos?",
              "¿Cuál es la meta máxima de desperdicio evitable para locales en Colombia?",
              "¿Cómo canjeo mis puntos Brasa Points?",
            ].map((q) => (
              <button
                key={q}
                type="button"
                onClick={() => {
                  setQuestion(q);
                  setAnswer("");
                  setError(null);
                }}
                className="rounded-full border border-stone-600 bg-stone-800 px-3 py-1.5 text-xs text-stone-300 transition hover:border-amber-400 hover:text-amber-300"
              >
                {q}
              </button>
            ))}
          </div>
        </section>
      </main>
    </div>
  );
}