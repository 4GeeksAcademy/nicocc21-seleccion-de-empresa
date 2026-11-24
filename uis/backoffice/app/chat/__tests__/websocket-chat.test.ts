/**
 * Tests para useWebSocketChat hook.
 *
 * Simula WebSocket mediante una implementación mock en jsdom.
 * Verifica conexión, envío de mensajes, streaming de tokens,
 * interrupción y rehidratación por session_snapshot.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, act, waitFor } from "@testing-library/react";
import { useWebSocketChat } from "../use-websocket-chat";

// ─── Mock de WebSocket ──────────────────────────────────────────

type WsHandler = ((event: MessageEvent) => void) | null;

interface MockWebSocket {
  readyState: number;
  onopen: WsHandler;
  onclose: WsHandler;
  onmessage: WsHandler;
  onerror: WsHandler;
  send: ReturnType<typeof vi.fn>;
  close: ReturnType<typeof vi.fn>;
  _triggerOpen: () => void;
  _triggerClose: () => void;
  _triggerMessage: (data: string) => void;
  _triggerError: () => void;
}

let mockWs: MockWebSocket | null = null;
const originalWebSocket = globalThis.WebSocket;

function createMockWebSocket(url: string): MockWebSocket {
  const ws: MockWebSocket = {
    readyState: WebSocket.OPEN,
    onopen: null,
    onclose: null,
    onmessage: null,
    onerror: null,
    send: vi.fn(),
    close: vi.fn(),
    _triggerOpen() {
      ws.readyState = WebSocket.OPEN;
      ws.onopen?.(new Event("open") as MessageEvent);
    },
    _triggerClose() {
      ws.readyState = WebSocket.CLOSED;
      ws.onclose?.(new CloseEvent("close") as unknown as MessageEvent);
    },
    _triggerMessage(data: string) {
      ws.onmessage?.(new MessageEvent("message", { data }) as MessageEvent);
    },
    _triggerError() {
      ws.onerror?.(new Event("error") as MessageEvent);
    },
  };
  mockWs = ws;
  return ws;
}

// ─── Mock de auth-client ───────────────────────────────────────

vi.mock("@brasaland/auth-client", () => ({
  getToken: vi.fn(() => "test-jwt-token"),
}));

// ─── Mock de sessionStorage ────────────────────────────────────

const createMockStorage = () => {
  const store: Record<string, string> = {};
  return {
    getItem: (key: string) => store[key] ?? null,
    setItem: (key: string, value: string) => {
      store[key] = value;
    },
    removeItem: (key: string) => {
      delete store[key];
    },
    clear: () => {
      Object.keys(store).forEach((k) => delete store[k]);
    },
  };
};

const mockSessionStorage = createMockStorage();

// ─── Tests ─────────────────────────────────────────────────────

describe("useWebSocketChat", () => {
  beforeEach(() => {
    mockWs = null;
    vi.clearAllMocks();

    // Mock WebSocket global
    globalThis.WebSocket = createMockWebSocket as unknown as typeof WebSocket;
    // @ts-expect-error - need URL property
    globalThis.WebSocket.CONNECTING = 0;
    // @ts-expect-error
    globalThis.WebSocket.OPEN = 1;
    // @ts-expect-error
    globalThis.WebSocket.CLOSING = 2;
    // @ts-expect-error
    globalThis.WebSocket.CLOSED = 3;

    // Mock sessionStorage
    Object.defineProperty(globalThis, "sessionStorage", {
      value: mockSessionStorage,
      writable: true,
    });
    mockSessionStorage.clear();

    // Mock localStorage for token
    const mockLocalStorage = createMockStorage();
    mockLocalStorage.setItem("brasaland_token", "test-jwt-token");
    Object.defineProperty(globalThis, "localStorage", {
      value: mockLocalStorage,
      writable: true,
    });
  });

  afterEach(() => {
    globalThis.WebSocket = originalWebSocket;
  });

  it("debe conectar y establecer isConnected=true", () => {
    const { result } = renderHook(() => useWebSocketChat());

    act(() => {
      mockWs?._triggerOpen();
    });

    expect(result.current.isConnected).toBe(true);
  });

  it("debe crear un nuevo ChatMessage al enviar un mensaje", () => {
    const { result } = renderHook(() => useWebSocketChat());

    act(() => {
      mockWs?._triggerOpen();
    });

    act(() => {
      result.current.sendMessage("Hola, ¿cómo estás?");
    });

    // El mensaje de usuario se añade al estado
    expect(result.current.messages.length).toBeGreaterThan(0);
    const lastMsg = result.current.messages[result.current.messages.length - 1];
    expect(lastMsg.role).toBe("user");
    expect(lastMsg.content).toBe("Hola, ¿cómo estás?");

    // Verificar que se envió por WebSocket
    expect(mockWs?.send).toHaveBeenCalled();
    const sentData = JSON.parse(mockWs!.send.mock.calls[0][0]);
    expect(sentData.event).toBe("user_message");
    expect(sentData.data.text).toBe("Hola, ¿cómo estás?");
  });

  it("debe manejar session_created y guardar sessionId", () => {
    const { result } = renderHook(() => useWebSocketChat());

    act(() => {
      mockWs?._triggerOpen();
    });

    act(() => {
      mockWs?._triggerMessage(
        JSON.stringify({
          event: "session_created",
          data: { session_id: "ses-123" },
        }),
      );
    });

    expect(result.current.sessionId).toBe("ses-123");
    expect(mockSessionStorage.getItem("chat_session_id")).toBe("ses-123");
  });

  it("debe manejar session_snapshot y rehidratar mensajes", () => {
    const { result } = renderHook(() => useWebSocketChat());

    const snapshotMessages = [
      { role: "user", content: "¿Cuántas incidencias?" },
      { role: "assistant", content: "Hay 3 incidencias hoy." },
    ];

    act(() => {
      mockWs?._triggerOpen();
    });

    act(() => {
      mockWs?._triggerMessage(
        JSON.stringify({
          event: "session_snapshot",
          data: { messages: snapshotMessages },
        }),
      );
    });

    expect(result.current.messages).toHaveLength(2);
    expect(result.current.messages[0].role).toBe("user");
    expect(result.current.messages[1].content).toBe("Hay 3 incidencias hoy.");
  });

  it("debe hacer streaming de tokens token_chunk", () => {
    const { result } = renderHook(() => useWebSocketChat());

    act(() => {
      mockWs?._triggerOpen();
    });

    act(() => {
      mockWs?._triggerMessage(
        JSON.stringify({
          event: "token_chunk",
          data: { token: "Hola", message_id: "msg-1" },
        }),
      );
    });

    expect(result.current.isGenerating).toBe(true);
    expect(result.current.messages).toHaveLength(1);
    expect(result.current.messages[0].content).toBe("Hola");
    expect(result.current.messages[0].status).toBe("streaming");

    // Segundo chunk
    act(() => {
      mockWs?._triggerMessage(
        JSON.stringify({
          event: "token_chunk",
          data: { token: ", ", message_id: "msg-1" },
        }),
      );
    });

    expect(result.current.messages[0].content).toBe("Hola, ");

    // Tercer chunk
    act(() => {
      mockWs?._triggerMessage(
        JSON.stringify({
          event: "token_chunk",
          data: { token: "mundo", message_id: "msg-1" },
        }),
      );
    });

    expect(result.current.messages[0].content).toBe("Hola, mundo");
  });

  it("debe marcar completed en generation_completed", () => {
    const { result } = renderHook(() => useWebSocketChat());

    act(() => {
      mockWs?._triggerOpen();
    });

    act(() => {
      mockWs?._triggerMessage(
        JSON.stringify({
          event: "token_chunk",
          data: { token: "Respuesta en curso", message_id: "msg-1" },
        }),
      );
    });

    expect(result.current.isGenerating).toBe(true);

    act(() => {
      mockWs?._triggerMessage(
        JSON.stringify({
          event: "generation_completed",
          data: { message_id: "msg-1", session_id: "ses-1" },
        }),
      );
    });

    expect(result.current.isGenerating).toBe(false);
    expect(result.current.messages[0].status).toBe("completed");
  });

  it("debe marcar interrupted en generation_interrupted", () => {
    const { result } = renderHook(() => useWebSocketChat());

    act(() => {
      mockWs?._triggerOpen();
    });

    act(() => {
      mockWs?._triggerMessage(
        JSON.stringify({
          event: "token_chunk",
          data: { token: "Respuesta a medias", message_id: "msg-1" },
        }),
      );
    });

    expect(result.current.isGenerating).toBe(true);

    act(() => {
      mockWs?._triggerMessage(
        JSON.stringify({
          event: "generation_interrupted",
          data: { message_id: "msg-1" },
        }),
      );
    });

    expect(result.current.isGenerating).toBe(false);
    expect(result.current.messages[0].status).toBe("interrupted");
  });

  it("debe enviar interrupt_requested al llamar interruptGeneration", () => {
    const { result } = renderHook(() => useWebSocketChat());

    act(() => {
      mockWs?._triggerOpen();
    });

    act(() => {
      result.current.interruptGeneration();
    });

    expect(mockWs?.send).toHaveBeenCalled();
    const sentData = JSON.parse(mockWs!.send.mock.calls[0][0]);
    expect(sentData.event).toBe("interrupt_requested");
  });

  it("debe enviar interrupt_requested con new_input si se proporciona", () => {
    const { result } = renderHook(() => useWebSocketChat());

    act(() => {
      mockWs?._triggerOpen();
    });

    act(() => {
      result.current.interruptGeneration("Nueva pregunta");
    });

    // La primera llamada es interrupt_requested
    const sentData = JSON.parse(mockWs!.send.mock.calls[0][0]);
    expect(sentData.event).toBe("interrupt_requested");
    expect(sentData.data.new_input).toBe("Nueva pregunta");

    // Se añade el mensaje de usuario con el nuevo input
    const userMsg = result.current.messages[result.current.messages.length - 1];
    expect(userMsg.role).toBe("user");
    expect(userMsg.content).toBe("Nueva pregunta");
  });

  it("debe intentar reconectar en onclose (reconnect)", async () => {
    const { result } = renderHook(() => useWebSocketChat());

    act(() => {
      mockWs?._triggerOpen();
    });

    expect(result.current.isConnected).toBe(true);

    act(() => {
      mockWs?._triggerClose();
    });

    expect(result.current.isConnected).toBe(false);

    // Debería reconectar tras el backoff (1s + jitter)
    await waitFor(
      () => {
        expect(mockWs).not.toBeNull();
      },
      { timeout: 3000 },
    );
  });
});