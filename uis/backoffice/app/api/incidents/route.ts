import { NextResponse } from "next/server";

const BACKEND_BASE =
  process.env.INCIDENTS_BACKEND_BASE_URL ?? "http://127.0.0.1:8001";

export async function GET(request: Request) {
  try {
    const { searchParams } = new URL(request.url);
    const upstreamUrl = new URL(`${BACKEND_BASE}/incidents`);

    const estado = searchParams.get("estado");
    const local_id = searchParams.get("local_id");
    const categoria = searchParams.get("categoria");
    const origen = searchParams.get("origen");
    const prioridad = searchParams.get("prioridad");
    const desde = searchParams.get("desde");
    const hasta = searchParams.get("hasta");

    if (estado) upstreamUrl.searchParams.set("estado", estado);
    if (local_id) upstreamUrl.searchParams.set("local_id", local_id);
    if (categoria) upstreamUrl.searchParams.set("categoria", categoria);
    if (origen) upstreamUrl.searchParams.set("origen", origen);
    if (prioridad) upstreamUrl.searchParams.set("prioridad", prioridad);
    if (desde) upstreamUrl.searchParams.set("desde", desde);
    if (hasta) upstreamUrl.searchParams.set("hasta", hasta);

    const response = await fetch(upstreamUrl.toString(), {
      method: "GET",
      cache: "no-store",
    });

    const body = await response.text();
    return new NextResponse(body, {
      status: response.status,
      headers: {
        "Content-Type":
          response.headers.get("Content-Type") ?? "application/json; charset=utf-8",
      },
    });
  } catch {
    return NextResponse.json(
      { error: "No se pudo conectar con la API de incidencias." },
      { status: 502 }
    );
  }
}

export async function POST(request: Request) {
  try {
    const payload = await request.json();

    const response = await fetch(`${BACKEND_BASE}/incidents`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
      cache: "no-store",
    });

    const body = await response.text();
    return new NextResponse(body, {
      status: response.status,
      headers: {
        "Content-Type":
          response.headers.get("Content-Type") ?? "application/json; charset=utf-8",
      },
    });
  } catch {
    return NextResponse.json(
      { error: "No se pudo conectar con la API de incidencias." },
      { status: 502 }
    );
  }
}