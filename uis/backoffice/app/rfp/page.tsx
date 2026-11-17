"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { getToken } from "../../../../src/auth/auth-client";

/*
 * Página de recepción de RFPs (Hito 9).
 *
 * Features:
 * - Subida de PDF (drag & drop o file input)
 * - Polling del estado del ticket en background
 * - Visualización del resultado cuando el análisis se completa
 * - Notificaciones SSE en tiempo real (Hito 10)
 */

type TicketStatus = "analizando" | "descartado" | "analisis_completo";

interface TicketInfo {
  ticket_id: number;
  status: TicketStatus;
  rfp_external_id: string | null;
  created_at: string;
  updated_at: string;
  error_message: string | null;
}

interface DepartmentSection {
  department_id: string;
  key_aspects: Record<string, unknown> | null;
  approval_status: string;
}

interface RFPResult {
  ticket_id: number;
  status: string;
  metadata: Record<string, unknown> | null;
  departments: DepartmentSection[];
  readability: Record<string, unknown> | null;
  summary: string | null;
  error_message: string | null;
}

interface SSETicketEvent {
  ticket_id: string;
  rfp_id: string;
  client_name?: string;
  location?: string;
  service_type?: string;
  status: string;
  created_at: string;
}

interface SSENotification {
  id: string;
  ticket_id: string;
  client_name: string;
  location: string;
  service_type: string;
  timestamp: string;
}

export default function RFPPage() {
  const [uploading, setUploading] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const [activeTicketId, setActiveTicketId] = useState<number | null>(null);
  const [ticket, setTicket] = useState<TicketInfo | null>(null);
  const [result, setResult] = useState<RFPResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [sseConnected, setSseConnected] = useState(false);
  const [reconnecting, setReconnecting] = useState(false);
  const [notifications, setNotifications] = useState<SSENotification[]>([]);
  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const sseRef = useRef<AbortController | null>(null);
  const lastEventIdRef = useRef<number | null>(null);
  const receivedTicketIds = useRef<Set<string>>(new Set());

  // ── SSE: conectar al canal de eventos RFP ────────────────────────
  // Usamos fetch + ReadableStream en vez de EventSource porque
  // necesitamos enviar Authorization header (JWT) y controlar
  // la reconexión con backoff progresivo.
  const connectSSE = useCallback(() => {
    // Cancelar conexión previa si existe
    if (sseRef.current) {
      sseRef.current.abort();
      sseRef.current = null;
    }

    const abortController = new AbortController();
    sseRef.current = abortController;

    const connect = async (retryCount = 0) => {
      try {
        const token = getToken();
        if (!token) {
          console.error("SSE: No hay sesión activa — el usuario debe iniciar sesión");
          setSseConnected(false);
          return;
        }

        const headers: Record<string, string> = {
          Authorization: `Bearer ${token}`,
        };
        if (lastEventIdRef.current !== null) {
          headers["last-event-id"] = String(lastEventIdRef.current);
        }

        const response = await fetch("/api/sse/rfp/events", {
          method: "GET",
          headers,
          signal: abortController.signal,
          cache: "no-store",
        });

        if (!response.ok) {
          if (response.status === 401 || response.status === 403) {
            console.error("SSE: Autenticación fallida — token inválido o expirado");
            setSseConnected(false);
            setReconnecting(false);
            return;
          }
          throw new Error(`HTTP ${response.status}`);
        }

        setSseConnected(true);
        setReconnecting(false);
        retryCount = 0; // Resetear backoff al conectar

        const reader = response.body!.getReader();
        const decoder = new TextDecoder();
        let buffer = "";

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });

          // Parsear SSE framing: eventos separados por \n\n
          const parts = buffer.split("\n\n");
          buffer = parts.pop() || ""; // Última parte puede estar incompleta

          for (const block of parts) {
            if (!block.trim()) continue;

            let eventName = "";
            let eventData = "";
            let eventId: string | null = null;

            for (const line of block.split("\n")) {
              if (line.startsWith("id: ")) {
                eventId = line.substring(4);
              } else if (line.startsWith("event: ")) {
                eventName = line.substring(7);
              } else if (line.startsWith("data: ")) {
                eventData += line.substring(6);
              }
              // Heartbeats son comentarios ": heartbeat" — los ignoramos
            }

            // Actualizar Last-Event-ID para reconexión
            if (eventId) {
              const parsedId = parseInt(eventId, 10);
              if (!isNaN(parsedId)) {
                lastEventIdRef.current = parsedId;
              }
            }

            // Procesar solo eventos que nos interesan
            if (eventName === "rfp_ticket_created" && eventData) {
              try {
                const data: SSETicketEvent = JSON.parse(eventData);

                // Deduplicación: si ya recibimos este ticket_id, ignorar
                if (receivedTicketIds.current.has(data.ticket_id)) {
                  console.log("SSE: ticket duplicado ignorado", data.ticket_id);
                  continue;
                }
                receivedTicketIds.current.add(data.ticket_id);

                console.log("SSE evento recibido: rfp_ticket_created", data);

                // Añadir a notificaciones toast
                const notification: SSENotification = {
                  id: data.ticket_id,
                  ticket_id: data.ticket_id,
                  client_name: data.client_name || "Cliente pendiente",
                  location: data.location || "Ubicación pendiente",
                  service_type: data.service_type || "",
                  timestamp: new Date().toLocaleTimeString("es-CO", { hour: "2-digit", minute: "2-digit" }),
                };
                setNotifications((prev) => {
                  const updated = [notification, ...prev];
                  return updated.slice(0, 20); // Máximo 20 notificaciones en memoria
                });

                // Si no hay un ticket activo, mostrar éste automáticamente
                if (!pollingRef.current) {
                  const ticketInfo: TicketInfo = {
                    ticket_id: parseInt(data.ticket_id.replace("tkt_", "")),
                    status: "analizando",
                    rfp_external_id: null,
                    created_at: data.created_at,
                    updated_at: data.created_at,
                    error_message: null,
                  };
                  setTicket(ticketInfo);
                  setActiveTicketId(ticketInfo.ticket_id);
                  startPolling(ticketInfo.ticket_id);
                }
              } catch (err) {
                console.error("Error al procesar evento SSE:", err);
              }
            }
          }
        }

        // Stream cerró limpiamente → reconectar
        setSseConnected(false);
        throw new Error("Stream finalizado");

      } catch (err) {
        if (abortController.signal.aborted) return; // Desmontaje intencional

        setSseConnected(false);
        setReconnecting(true);

        // Backoff progresivo: 1s, 2s, 4s, 8s, ... máx 30s + jitter
        const delay = Math.min(1000 * Math.pow(2, retryCount), 30000);
        const jitter = Math.random() * 1000;
        console.log(
          `SSE: Reintentando conexión en ${((delay + jitter) / 1000).toFixed(1)}s ` +
          `(intento ${retryCount + 1})`
        );

        setTimeout(() => connect(retryCount + 1), delay + jitter);
      }
    };

    connect(0);
  }, [startPolling]);

  // ── Limpiar polling y SSE al desmontar ────────────────────────────
  useEffect(() => {
    connectSSE();
    return () => {
      if (pollingRef.current) clearInterval(pollingRef.current);
      if (sseRef.current) sseRef.current.abort();
    };
  }, [connectSSE]);

  // ── Polling del estado ────────────────────────────────────────────
  const startPolling = useCallback((ticketId: number) => {
    if (pollingRef.current) clearInterval(pollingRef.current);

    pollingRef.current = setInterval(async () => {
      try {
        const res = await fetch(`/api/rfp/${ticketId}`);
        if (!res.ok) {
          setError(`Error al consultar ticket: ${res.statusText}`);
          if (pollingRef.current) clearInterval(pollingRef.current);
          return;
        }
        const data: TicketInfo = await res.json();
        setTicket(data);

        // Si terminó, dejar de poll y cargar resultado
        if (data.status === "analisis_completo" || data.status === "descartado") {
          if (pollingRef.current) clearInterval(pollingRef.current);
          loadResult(ticketId);
        }
      } catch (err) {
        console.error("Polling error:", err);
      }
    }, 2000); // cada 2 segundos
  }, []);

  // ── Cargar resultado completo ─────────────────────────────────────
  const loadResult = async (ticketId: number) => {
    try {
      const res = await fetch(`/api/rfp/${ticketId}/result`);
      if (res.ok) {
        const data: RFPResult = await res.json();
        setResult(data);
      }
    } catch (err) {
      console.error("Error loading result:", err);
    }
  };

  // ── Subir archivo ─────────────────────────────────────────────────
  const handleUpload = async (file: File) => {
    if (!file.name.toLowerCase().endsWith(".pdf")) {
      setError("Solo se aceptan archivos PDF");
      return;
    }

    setUploading(true);
    setError(null);
    setResult(null);
    setTicket(null);

    try {
      const formData = new FormData();
      formData.append("file", file);

      const res = await fetch("/api/rfp/upload", {
        method: "POST",
        body: formData,
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => null);
        setError(errData?.detail || `Error al subir: ${res.statusText}`);
        setUploading(false);
        return;
      }

      const data = await res.json();
      setActiveTicketId(data.ticket_id);
      setTicket({ ticket_id: data.ticket_id, status: "analizando", rfp_external_id: null, created_at: "", updated_at: "", error_message: null });
      startPolling(data.ticket_id);
    } catch (err) {
      setError(`Error de conexión: ${err instanceof Error ? err.message : "Desconocido"}`);
    } finally {
      setUploading(false);
    }
  };

  // ── Handlers de drag & drop ──────────────────────────────────────
  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const files = e.dataTransfer.files;
    if (files.length > 0) handleUpload(files[0]);
  }, []);

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(true);
  };

  const handleDragLeave = () => setDragOver(false);

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (files && files.length > 0) handleUpload(files[0]);
  };

  // ── Estado del ticket con color ───────────────────────────────────
  const statusBadge = (status: string) => {
    const colors: Record<string, string> = {
      analizando: "bg-amber-500/20 text-amber-400 border-amber-500/30",
      descartado: "bg-red-500/20 text-red-400 border-red-500/30",
      analisis_completo: "bg-emerald-500/20 text-emerald-400 border-emerald-500/30",
    };
    return (
      <span className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-medium ${colors[status] || "bg-stone-700 text-stone-300"}`}>
        <span className={`h-1.5 w-1.5 rounded-full ${status === "analizando" ? "bg-amber-400 animate-pulse" : status === "analisis_completo" ? "bg-emerald-400" : "bg-red-400"}`} />
        {status === "analizando" ? "Analizando…" : status === "analisis_completo" ? "Análisis completo" : "Descartado"}
      </span>
    );
  };

  // ── Render ────────────────────────────────────────────────────────
  return (
    <div className="mx-auto max-w-4xl space-y-8 p-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Recepción de RFPs</h1>
          <p className="mt-1 text-sm text-stone-400">
            Sube una solicitud de propuesta (RFP) en PDF para que el sistema la analice
            y la distribuya a los departamentos correspondientes.
          </p>
        </div>
        {/* Indicador de conexión SSE */}
        <div className="flex items-center gap-2 text-xs">
          <span className={`h-2.5 w-2.5 rounded-full ${sseConnected ? "bg-emerald-400" : reconnecting ? "bg-amber-400 animate-pulse" : "bg-red-400"}`} />
          <span className={sseConnected ? "text-emerald-400" : reconnecting ? "text-amber-400" : "text-red-400"}>
            {sseConnected ? "Tiempo real conectado" : reconnecting ? "Reconectando…" : "Desconectado"}
          </span>
        </div>
      </div>

      {/* Notificaciones toast SSE */}
      {notifications.length > 0 && (
        <div className="fixed top-4 right-4 z-50 w-80 max-h-96 space-y-2 overflow-y-auto">
          {notifications.slice(0, 5).map((n) => (
            <div key={`${n.id}-${n.timestamp}`} className="animate-slide-in rounded-lg border border-sky-500/30 bg-stone-800/90 p-3 shadow-2xl backdrop-blur-sm">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-sky-300">Nueva RFP</span>
                <span className="text-xs text-stone-500">{n.timestamp}</span>
              </div>
              <p className="mt-1 text-sm font-medium text-white">{n.ticket_id}</p>
              <p className="text-xs text-stone-400">
                {n.client_name}{n.location ? ` · ${n.location}` : ""}
              </p>
            </div>
          ))}
        </div>
      )}

      {/* Drop zone */}
      <div
        onDrop={handleDrop}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onClick={() => fileInputRef.current?.click()}
        className={`flex cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed p-12 transition-colors ${
          dragOver
            ? "border-sky-500 bg-sky-500/10"
            : "border-stone-600 bg-stone-900/50 hover:border-stone-500"
        }`}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept=".pdf"
          className="hidden"
          onChange={handleFileSelect}
        />
        {uploading ? (
          <div className="flex flex-col items-center gap-3">
            <div className="h-8 w-8 animate-spin rounded-full border-2 border-sky-400 border-t-transparent" />
            <p className="text-sm text-stone-400">Subiendo y analizando…</p>
          </div>
        ) : (
          <>
            <svg className="mb-3 h-10 w-10 text-stone-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
            </svg>
            <p className="text-sm text-stone-400">
              Arrastra un PDF aquí o haz clic para seleccionar
            </p>
            <p className="mt-1 text-xs text-stone-500">Solo archivos PDF</p>
          </>
        )}
      </div>

      {/* Error */}
      {error && (
        <div className="rounded-lg border border-red-500/30 bg-red-500/10 p-4 text-sm text-red-400">
          {error}
        </div>
      )}

      {/* Ticket activo */}
      {ticket && (
        <div className="rounded-xl border border-stone-700 bg-stone-900 p-6">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold text-white">
              Ticket #{ticket.ticket_id}
            </h2>
            {statusBadge(ticket.status)}
          </div>

          {ticket.error_message && (
            <p className="mt-3 text-sm text-red-400">{ticket.error_message}</p>
          )}
        </div>
      )}

      {/* Resultado */}
      {result && result.status === "analisis_completo" && (
        <div className="space-y-6">
          {/* Metadatos */}
          {result.metadata && (
            <div className="rounded-xl border border-stone-700 bg-stone-900 p-6">
              <h3 className="mb-4 text-lg font-semibold text-white">Metadatos de la RFP</h3>
              <dl className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                {Object.entries(result.metadata).map(([key, value]) => (
                  <div key={key}>
                    <dt className="text-xs font-medium uppercase tracking-wider text-stone-500">
                      {key.replace(/_/g, " ")}
                    </dt>
                    <dd className="mt-1 text-sm text-stone-300">
                      {value === null || value === "" ? (
                        <span className="text-stone-600">—</span>
                      ) : Array.isArray(value) ? (
                        value.join(", ")
                      ) : (
                        String(value)
                      )}
                    </dd>
                  </div>
                ))}
              </dl>
            </div>
          )}

          {/* Legibilidad */}
          {result.readability && (
            <div className="rounded-xl border border-stone-700 bg-stone-900 p-6">
              <h3 className="mb-4 text-lg font-semibold text-white">Métricas de Legibilidad</h3>
              <dl className="grid grid-cols-2 gap-4 sm:grid-cols-4">
                {Object.entries(result.readability).map(([key, value]) => (
                  <div key={key}>
                    <dt className="text-xs font-medium uppercase tracking-wider text-stone-500">
                      {key.replace(/_/g, " ")}
                    </dt>
                    <dd className="mt-1 text-sm text-stone-300">
                      {value !== null && value !== undefined ? String(value) : <span className="text-stone-600">—</span>}
                    </dd>
                  </div>
                ))}
              </dl>
            </div>
          )}

          {/* Departamentos */}
          {result.departments.length > 0 && (
            <div className="rounded-xl border border-stone-700 bg-stone-900 p-6">
              <h3 className="mb-4 text-lg font-semibold text-white">
                Departamentos Involucrados ({result.departments.length})
              </h3>
              <div className="space-y-4">
                {result.departments.map((dept) => (
                  <div key={dept.department_id} className="rounded-lg border border-stone-700/50 bg-stone-800/50 p-4">
                    <div className="flex items-center justify-between">
                      <h4 className="font-medium text-white">{dept.department_id}</h4>
                      <span className={`rounded px-2 py-0.5 text-xs ${
                        dept.approval_status === "pendiente" ? "bg-amber-500/10 text-amber-400" : "bg-emerald-500/10 text-emerald-400"
                      }`}>
                        {dept.approval_status}
                      </span>
                    </div>
                    {dept.key_aspects && (
                      <pre className="mt-2 max-h-48 overflow-auto rounded bg-stone-950 p-3 text-xs text-stone-400">
                        {JSON.stringify(dept.key_aspects, null, 2)}
                      </pre>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Summary */}
          {result.summary && (
            <div className="rounded-xl border border-stone-700 bg-stone-900 p-6">
              <h3 className="mb-4 text-lg font-semibold text-white">Resumen</h3>
              <pre className="whitespace-pre-wrap text-sm text-stone-300">{result.summary}</pre>
            </div>
          )}
        </div>
      )}

      {/* Descartado */}
      {result && result.status === "descartado" && (
        <div className="rounded-xl border border-red-500/30 bg-red-500/10 p-6">
          <h3 className="text-lg font-semibold text-red-400">Documento Descartado</h3>
          <p className="mt-2 text-sm text-red-300">
            El documento no fue reconocido como una RFP válida.
          </p>
          {result.error_message && (
            <p className="mt-1 text-sm text-red-400">{result.error_message}</p>
          )}
        </div>
      )}

      {/* Botón de nuevo análisis */}
      {result && (
        <button
          onClick={() => {
            setActiveTicketId(null);
            setTicket(null);
            setResult(null);
            setError(null);
          }}
          className="rounded-lg bg-sky-600 px-4 py-2 text-sm font-medium text-white hover:bg-sky-500 transition-colors"
        >
          Nueva RFP
        </button>
      )}
    </div>
  );
}