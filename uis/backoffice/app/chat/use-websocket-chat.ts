/**
 * useWebSocketChat — Hook personalizado para chat en tiempo real vía WebSocket.
 *
 * Gestiona:
 * - Conexión WebSocket con JWT desde localStorage
 * - Streaming de tokens en vivo
 * - Interrupción de generación
 * - Reconexión con backoff progresivo
 * - Rehidratación de sesión (session_snapshot)
 */

"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { getToken } from "@brasaland/auth-client";

// ─── Tipos ────────────────────────────────────────────────────────────

export interface ChatMessage {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  status: "streaming" | "completed" | "interrupted";
  timestamp: string;
}

interface WebSocketEvent {
  event: string;
  data: Record<string, unknown>;
}

export interface UseWebSocketChatOptions {
  apiBaseUrl?: string;
  onError?: (error: string) => void;
}

export interface UseWebSocketChatReturn {
  /** Lista de mensajes del chat */
  messages: ChatMessage[];
  /** Si el WebSocket está conectado */
  isConnected: boolean;
  /** Si el agente está generando una respuesta */
  isGenerating: boolean;
  /** ID de la sesión activa */
  sessionId: string | null;
  /** Enviar un mensaje de usuario */
  sendMessage: (text: string) => void;
  /** Interrumpir la generación en curso */
  interruptGeneration: (newInput?: string) => void;
  /** Conectar manualmente (se auto-conecta al montar) */
  connect: () => void;
  /** Desconectar */
  disconnect: () => void;
}

// ─── Constantes ────────────────────────────────────────────────────────
const WS_RECONNECT_BASE_MS = 1000;
const WS_RECONNECT_MAX_MS = 8000;
const WS_RECONNECT_JITTER_MS = 300;

// ─── Helper: generar IDs únicos para mensajes ─────────────────────────
let _msgCounter = 0;
function nextMessageId(): string {
  _msgCounter += 1;
  return `msg_${Date.now()}_${_msgCounter}`;
}

function getWsBaseUrl(apiBaseUrl: string): string {
  // Convertir http:// → ws://, https:// → wss://
  const url = apiBaseUrl.replace(/^http/, "ws");
  return url.replace(/\/+$/, ""); // quitar trailing slash
}

// ─── Hook ──────────────────────────────────────────────────────────────

export function useWebSocketChat(
  options: UseWebSocketChatOptions = {},
): UseWebSocketChatReturn {
  const { apiBaseUrl: rawApiBaseUrl, onError } = options;
  const apiBaseUrl =
    rawApiBaseUrl ??
    (typeof window !== "undefined"
      ? process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8001"
      : "http://localhost:8001");

  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isConnected, setIsConnected] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(() => {
    // Intentar recuperar session_id de sessionStorage
    if (typeof window === "undefined") return null;
    return sessionStorage.getItem("chat_session_id");
  });

  // Refs para acceso en callbacks sin re-renders
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectAttemptRef = useRef(0);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const currentMessageIdRef = useRef<string | null>(null);
  const isGeneratingRef = useRef(false);
  const shouldReconnectRef = useRef(true);

  // ── Limpiar recursos ────────────────────────────────────────
  const cleanup = useCallback(() => {
    if (reconnectTimerRef.current) {
      clearTimeout(reconnectTimerRef.current);
      reconnectTimerRef.current = null;
    }
    if (wsRef.current) {
      wsRef.current.onopen = null;
      wsRef.current.onclose = null;
      wsRef.current.onmessage = null;
      wsRef.current.onerror = null;
      if (
        wsRef.current.readyState === WebSocket.OPEN ||
        wsRef.current.readyState === WebSocket.CONNECTING
      ) {
        wsRef.current.close();
      }
      wsRef.current = null;
    }
    setIsConnected(false);
  }, []);

  // ── Conectar WebSocket ───────────────────────────────────────
  const connect = useCallback(() => {
    cleanup();

    const token = getToken();
    if (!token) {
      onError?.("No hay sesión iniciada. Inicia sesión para usar el chat.");
      return;
    }

    shouldReconnectRef.current = true;
    const storedSessionId = sessionStorage.getItem("chat_session_id");
    const wsSessionId = storedSessionId || "new";
    const wsBaseUrl = getWsBaseUrl(apiBaseUrl);
    const wsUrl = `${wsBaseUrl}/ws/chat/${wsSessionId}?token=${encodeURIComponent(token)}`;

    let ws: WebSocket;
    try {
      ws = new WebSocket(wsUrl);
    } catch (err) {
      onError?.(`Error al crear WebSocket: ${err}`);
      return;
    }
    wsRef.current = ws;

    ws.onopen = () => {
      setIsConnected(true);
      reconnectAttemptRef.current = 0;
    };

    ws.onmessage = (event: MessageEvent) => {
      try {
        const parsed: WebSocketEvent = JSON.parse(event.data);
        handleWsEvent(parsed);
      } catch {
        // ignorar mensajes no JSON
      }
    };

    ws.onclose = () => {
      setIsConnected(false);
      wsRef.current = null;

      // Reconexión con backoff progresivo
      if (shouldReconnectRef.current) {
        const attempt = reconnectAttemptRef.current;
        const delay = Math.min(
          WS_RECONNECT_BASE_MS * Math.pow(2, attempt),
          WS_RECONNECT_MAX_MS,
        ) + Math.random() * WS_RECONNECT_JITTER_MS;
        reconnectAttemptRef.current = attempt + 1;
        reconnectTimerRef.current = setTimeout(() => {
          connect();
        }, delay);
      }
    };

    ws.onerror = () => {
      // onclose se dispara después de onerror
    };
  }, [apiBaseUrl, cleanup, onError]);

  // ── Manejar eventos del WebSocket ────────────────────────────
  function handleWsEvent(parsed: WebSocketEvent) {
    const { event, data } = parsed;
    const sessionIdFromEvent = data?.session_id as string | undefined;

    switch (event) {
      case "session_created": {
        const newSessionId = data.session_id as string;
        setSessionId(newSessionId);
        sessionStorage.setItem("chat_session_id", newSessionId);
        break;
      }

      case "session_snapshot": {
        const snapshotMessages = (data.messages as Array<{
          role: string;
          content: string;
        }>) ?? [];
        if (snapshotMessages.length > 0) {
          setMessages(
            snapshotMessages.map((msg) => ({
              id: nextMessageId(),
              role: msg.role as ChatMessage["role"],
              content: msg.content,
              status: "completed" as const,
              timestamp: new Date().toISOString(),
            })),
          );
        }
        break;
      }

      case "token_chunk": {
        setIsGenerating(true);
        isGeneratingRef.current = true;
        const token = (data.token as string) ?? "";
        const messageId = (data.message_id as string) ?? currentMessageIdRef.current;

        if (messageId && messageId !== currentMessageIdRef.current) {
          currentMessageIdRef.current = messageId;
        }

        setMessages((prev) => {
          const last = prev[prev.length - 1];
          // Si el último mensaje es un assistant en streaming, acumular
          if (
            last &&
            last.role === "assistant" &&
            last.status === "streaming" &&
            (messageId ? last.id === messageId : true)
          ) {
            const updated = [...prev];
            updated[updated.length - 1] = {
              ...last,
              content: last.content + token,
            };
            return updated;
          }

          // Si no, crear nuevo mensaje assistant
          const mid = messageId ?? nextMessageId();
          currentMessageIdRef.current = mid;
          return [
            ...prev,
            {
              id: mid,
              role: "assistant",
              content: token,
              status: "streaming",
              timestamp: new Date().toISOString(),
            },
          ];
        });
        break;
      }

      case "generation_completed": {
        setIsGenerating(false);
        isGeneratingRef.current = false;
        const messageId = (data.message_id as string) ?? currentMessageIdRef.current;
        if (sessionIdFromEvent) {
          setSessionId(sessionIdFromEvent);
        }
        // Marcar mensaje como completado
        setMessages((prev) => {
          if (messageId) {
            return prev.map((msg) =>
              msg.id === messageId && msg.status === "streaming"
                ? { ...msg, status: "completed" as const }
                : msg,
            );
          }
          // Si no hay messageId, marcar el último assistant streaming
          const last = prev[prev.length - 1];
          if (last && last.role === "assistant" && last.status === "streaming") {
            const updated = [...prev];
            updated[updated.length - 1] = { ...last, status: "completed" as const };
            return updated;
          }
          return prev;
        });
        break;
      }

      case "generation_interrupted": {
        setIsGenerating(false);
        isGeneratingRef.current = false;
        const interruptedMessageId = (data.message_id as string) ?? currentMessageIdRef.current;

        // Marcar mensaje como interrumpido
        setMessages((prev) => {
          if (interruptedMessageId) {
            return prev.map((msg) =>
              msg.id === interruptedMessageId && msg.status === "streaming"
                ? { ...msg, status: "interrupted" as const }
                : msg,
            );
          }
          // Fallback: marcar el último assistant streaming
          const last = prev[prev.length - 1];
          if (last && last.role === "assistant" && last.status === "streaming") {
            const updated = [...prev];
            updated[updated.length - 1] = { ...last, status: "interrupted" as const };
            return updated;
          }
          return prev;
        });

        // Si hay new_input en la interrupción, se maneja desde interruptGeneration
        break;
      }

      default:
        break;
    }
  }

  // ── Enviar mensaje ───────────────────────────────────────────
  const sendMessage = useCallback(
    (text: string) => {
      const trimmed = text.trim();
      if (!trimmed || !wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
        return;
      }

      // Si está generando, primero interrumpir
      if (isGeneratingRef.current) {
        interruptGeneration(trimmed);
        return;
      }

      // Añadir mensaje del usuario al estado
      const userMsgId = nextMessageId();
      const userMessage: ChatMessage = {
        id: userMsgId,
        role: "user",
        content: trimmed,
        status: "completed",
        timestamp: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, userMessage]);

      // Enviar por WebSocket
      const sid = sessionStorage.getItem("chat_session_id") || "";
      wsRef.current.send(
        JSON.stringify({
          event: "user_message",
          data: { session_id: sid, text: trimmed },
        }),
      );
    },
    [], // eslint-disable-line react-hooks/exhaustive-deps
  );

  // ── Interrumpir generación ───────────────────────────────────
  const interruptGeneration = useCallback(
    (newInput?: string) => {
      if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return;

      const sid = sessionStorage.getItem("chat_session_id") || "";
      wsRef.current.send(
        JSON.stringify({
          event: "interrupt_requested",
          data: {
            session_id: sid,
            new_input: newInput ?? "",
          },
        }),
      );

      // Si hay nuevo input, enviarlo como mensaje de usuario
      if (newInput?.trim()) {
        const userMsgId = nextMessageId();
        const userMessage: ChatMessage = {
          id: userMsgId,
          role: "user",
          content: newInput.trim(),
          status: "completed",
          timestamp: new Date().toISOString(),
        };
        setMessages((prev) => [...prev, userMessage]);

        // Enviar el nuevo mensaje tras la interrupción
        setTimeout(() => {
          if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
            wsRef.current.send(
              JSON.stringify({
                event: "user_message",
                data: { session_id: sid, text: newInput.trim() },
              }),
            );
          }
        }, 100);
      }
    },
    [],
  );

  // ── Desconectar ──────────────────────────────────────────────
  const disconnect = useCallback(() => {
    shouldReconnectRef.current = false;
    cleanup();
  }, [cleanup]);

  // ── Conectar al montar, desconectar al desmontar ─────────────
  useEffect(() => {
    connect();
    return () => {
      shouldReconnectRef.current = false;
      cleanup();
    };
  }, [connect, cleanup]);

  return {
    messages,
    isConnected,
    isGenerating,
    sessionId,
    sendMessage,
    interruptGeneration,
    connect,
    disconnect,
  };
}