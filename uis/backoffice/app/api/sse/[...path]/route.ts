// uis/backoffice/app/api/sse/[...path]/route.ts
// Proxy SSE: GET /api/sse/events → Backend GET /sse/events
// Usa streaming para mantener la conexión SSE abierta.

import { NextResponse } from "next/server";

const BACKEND_BASE =
  process.env.SSE_BACKEND_BASE_URL ?? "http://127.0.0.1:8001";

export async function GET(
  request: Request,
  context: { params: Promise<{ path: string[] }> },
) {
  try {
    const { path } = await context.params;
    const upstreamPath = `/sse/${path.join("/")}`;
    const upstreamUrl = new URL(upstreamPath, BACKEND_BASE);

    // Pasar query params al backend
    const { searchParams } = new URL(request.url);
    for (const [key, value] of searchParams) {
      upstreamUrl.searchParams.set(key, value);
    }

    // Pasar headers de autenticación y reconexión al backend
    const headers: Record<string, string> = {};
    const auth = request.headers.get("authorization");
    if (auth) {
      headers["authorization"] = auth;
    }
    const lastEventId = request.headers.get("last-event-id");
    if (lastEventId) {
      headers["last-event-id"] = lastEventId;
    }

    const response = await fetch(upstreamUrl.toString(), {
      method: "GET",
      headers,
      cache: "no-store",
    });

    // Verificar que el backend devuelva text/event-stream
    const contentType = response.headers.get("Content-Type") ?? "";

    // Reenviar el body como stream con los headers SSE adecuados
    return new NextResponse(response.body, {
      status: response.status,
      headers: {
        "Content-Type": contentType,
        "Cache-Control": "no-cache, no-store, must-revalidate",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
      },
    });
  } catch (error) {
    return NextResponse.json(
      {
        error: "No se pudo conectar con el servicio SSE.",
        detail: error instanceof Error ? error.message : "Desconocido",
      },
      { status: 502 },
    );
  }
}