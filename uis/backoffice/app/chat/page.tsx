"use client";

import { useEffect, useRef, useState } from "react";
import { useWebSocketChat } from "./use-websocket-chat";

export default function ChatPage() {
  const {
    messages,
    isConnected,
    isGenerating,
    sessionId,
    sendMessage,
    interruptGeneration,
    connect,
  } = useWebSocketChat();

  const [inputValue, setInputValue] = useState("");
  const [newSessionId, setNewSessionId] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Scroll automático al último mensaje
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // Detectar nueva sesión
  useEffect(() => {
    if (sessionId && sessionId !== newSessionId) {
      setNewSessionId(sessionId);
    }
  }, [sessionId, newSessionId]);

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const trimmed = inputValue.trim();
    if (!trimmed || isGenerating) return;
    sendMessage(trimmed);
    setInputValue("");
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  }

  function handleNewSession() {
    sessionStorage.removeItem("chat_session_id");
    setNewSessionId(null);
    connect();
  }

  // ── Render ─────────────────────────────────────────────────

  return (
    <div className="min-h-screen bg-stone-950 text-stone-100">
      <main className="mx-auto max-w-4xl px-4 py-10 sm:px-6 lg:px-8">
        {/* Header */}
        <header className="mb-10">
          <p className="text-xs font-bold uppercase tracking-[0.18em] text-amber-300">
            Brasaland OPS Console
          </p>
          <h1 className="mt-4 text-3xl font-black leading-tight sm:text-4xl">
            Manager Support Agent
          </h1>
          <p className="mt-4 max-w-3xl text-sm text-stone-300 sm:text-base">
            Asistente de IA para gestores de locales Brasaland. Haz preguntas sobre
            incidencias, inventario, personal o recomendaciones operativas. Las respuestas
            se generan en tiempo real.
          </p>

          {/* Status bar */}
          <div className="mt-4 flex flex-wrap items-center gap-4">
            {/* Connection status */}
            <span
              className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium ${
                isConnected
                  ? "bg-emerald-900/50 text-emerald-300"
                  : "bg-red-900/50 text-red-300"
              }`}
            >
              <span
                className={`inline-block h-1.5 w-1.5 rounded-full ${
                  isConnected ? "bg-emerald-400" : "bg-red-400"
                }`}
              />
              {isConnected ? "Conectado" : "Desconectado"}
            </span>

            {/* Session ID */}
            {newSessionId && (
              <span className="text-xs text-stone-500">
                Sesión:{" "}
                <code className="text-stone-400">{newSessionId.slice(0, 8)}…</code>
              </span>
            )}

            {/* New session button */}
            <button
              type="button"
              onClick={handleNewSession}
              className="rounded-full border border-stone-600 bg-stone-800 px-3 py-0.5 text-xs text-stone-400 transition hover:border-amber-400 hover:text-amber-300"
            >
              + Nueva sesión
            </button>
          </div>
        </header>

        {/* Messages area */}
        <div className="mb-6 max-h-[60vh] min-h-[300px] overflow-y-auto rounded-2xl border border-stone-700 bg-stone-900 p-4 sm:p-6">
          {messages.length === 0 ? (
            <p className="text-center text-sm text-stone-500">
              {isConnected
                ? "Escribe un mensaje para comenzar la conversación."
                : "Conectando al asistente…"}
            </p>
          ) : (
            <div className="flex flex-col gap-4">
              {messages.map((msg) => (
                <div
                  key={msg.id}
                  className={`flex ${
                    msg.role === "user" ? "justify-end" : "justify-start"
                  }`}
                >
                  <div
                    className={`max-w-[85%] rounded-2xl px-4 py-3 text-sm leading-relaxed ${
                      msg.role === "user"
                        ? "bg-amber-600 text-stone-950"
                        : msg.status === "interrupted"
                          ? "border border-stone-600 bg-stone-800 text-stone-200"
                          : "border border-stone-600 bg-stone-800 text-stone-200"
                    }`}
                  >
                    {/* Role label */}
                    {msg.role !== "user" && (
                      <p className="mb-1 text-[10px] font-bold uppercase tracking-widest text-amber-400/70">
                        Asistente
                      </p>
                    )}

                    {/* Content */}
                    <div className="whitespace-pre-wrap break-words">
                      {msg.content}
                      {msg.role !== "user" &&
                        msg.status === "streaming" && (
                          <span className="ml-0.5 inline-block animate-pulse text-amber-400">
                            ▊
                          </span>
                        )}
                    </div>

                    {/* Status badges */}
                    {msg.status === "interrupted" && (
                      <div className="mt-1 flex items-center gap-1 text-[11px] text-yellow-400/80">
                        <span>⚠️</span>
                        <span>Interrumpido</span>
                      </div>
                    )}
                  </div>
                </div>
              ))}
              <div ref={messagesEndRef} />
            </div>
          )}
        </div>

        {/* Input bar */}
        <form onSubmit={handleSubmit} className="mb-4">
          <div className="flex gap-3">
            <input
              type="text"
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={
                isGenerating
                  ? "Espera a que termine la respuesta…"
                  : isConnected
                    ? "Escribe tu mensaje…"
                    : "Conectando…"
              }
              className="flex-1 rounded-2xl border border-stone-600 bg-stone-800 px-4 py-3 text-stone-200 placeholder-stone-500 transition focus:border-amber-400 focus:ring-2 focus:ring-amber-400/30"
              disabled={!isConnected}
            />

            {/* Send button */}
            <button
              type="submit"
              disabled={!inputValue.trim() || !isConnected || isGenerating}
              className="rounded-2xl bg-amber-600 px-6 py-3 font-bold text-stone-950 transition hover:bg-amber-500 disabled:opacity-40 disabled:cursor-not-allowed"
            >
              {isGenerating ? "…" : "Enviar"}
            </button>
          </div>
        </form>

        {/* Interrupt button — visible solo durante generación */}
        {isGenerating && (
          <div className="mb-4 text-center">
            <button
              type="button"
              onClick={() => interruptGeneration()}
              className="rounded-full border border-red-500/50 bg-red-950/50 px-4 py-1.5 text-xs font-medium text-red-300 transition hover:bg-red-900/50 hover:text-red-200"
            >
              ⏹ Interrumpir generación
            </button>
          </div>
        )}

        {/* Sugerencias de preguntas — solo si no hay mensajes */}
        {messages.length === 0 && isConnected && (
          <section className="mt-4">
            <h2 className="mb-3 text-sm font-bold text-stone-400">
              Preguntas de ejemplo
            </h2>
            <div className="flex flex-wrap gap-2">
              {[
                "¿Cuántas incidencias hay hoy?",
                "Recomiéndame acciones para mejorar rendimiento",
                "¿Qué productos están por agotarse?",
              ].map((q) => (
                <button
                  key={q}
                  type="button"
                  onClick={() => {
                    setInputValue(q);
                  }}
                  className="rounded-full border border-stone-600 bg-stone-800 px-3 py-1.5 text-xs text-stone-300 transition hover:border-amber-400 hover:text-amber-300"
                >
                  {q}
                </button>
              ))}
            </div>
          </section>
        )}

        {/* Footer note */}
        {messages.length > 0 && (
          <p className="mt-8 text-center text-[10px] text-stone-600">
            Las respuestas son generadas por IA. Verifica la información crítica con
            tu supervisor.
          </p>
        )}
      </main>
    </div>
  );
}