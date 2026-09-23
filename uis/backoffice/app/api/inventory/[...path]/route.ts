import { NextResponse } from "next/server";

const BACKEND_BASE =
  process.env.INVENTORY_BACKEND_BASE_URL ?? "http://127.0.0.1:8001";

function forwardHeaders(request: Request): Record<string, string> {
  const headers: Record<string, string> = {};
  const auth = request.headers.get("Authorization");
  if (auth) headers["Authorization"] = auth;
  return headers;
}

export async function GET(
  request: Request,
  context: { params: Promise<{ path: string[] }> }
) {
  const { path } = await context.params;
  const upstreamPath = `/inventory/${path.join("/")}`;
  return proxyFetch(request, upstreamPath, "GET");
}

export async function POST(
  request: Request,
  context: { params: Promise<{ path: string[] }> }
) {
  const { path } = await context.params;
  const upstreamPath = `/inventory/${path.join("/")}`;

  let payload: unknown;
  try {
    payload = await request.json();
  } catch {
    return NextResponse.json(
      { error: "El cuerpo de la solicitud no tiene un formato JSON válido." },
      { status: 400 }
    );
  }

  return proxyFetch(request, upstreamPath, "POST", payload);
}

async function proxyFetch(
  request: Request,
  upstreamPath: string,
  method: string,
  body?: unknown
): Promise<NextResponse> {
  try {
    const upstreamUrl = new URL(upstreamPath, BACKEND_BASE);
    const options: RequestInit = {
      method,
      headers: {
        ...(body ? { "Content-Type": "application/json" } : {}),
        ...forwardHeaders(request),
      },
      cache: "no-store" as RequestCache,
    };

    if (body !== undefined) {
      options.body = JSON.stringify(body);
    }

    const response = await fetch(upstreamUrl.toString(), options);
    const text = await response.text();

    let json: unknown;
    try {
      json = JSON.parse(text);
    } catch {
      return new NextResponse(text, {
        status: response.status,
        headers: {
          "Content-Type":
            response.headers.get("Content-Type") ?? "application/json; charset=utf-8",
        },
      });
    }

    return NextResponse.json(json, { status: response.status });
  } catch {
    return NextResponse.json(
      { error: "No se pudo conectar con la API de inventario." },
      { status: 502 }
    );
  }
}