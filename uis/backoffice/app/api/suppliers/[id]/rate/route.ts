import { NextResponse } from "next/server";

const BACKEND_BASE =
  process.env.SUPPLIERS_BACKEND_BASE_URL ?? "http://127.0.0.1:8001";

function forwardHeaders(request: Request): Record<string, string> {
  const headers: Record<string, string> = {};
  const auth = request.headers.get("Authorization");
  if (auth) headers["Authorization"] = auth;
  return headers;
}

type Context = {
  params: Promise<{ id: string }>;
};

export async function PATCH(request: Request, context: Context) {
  const { id } = await context.params;

  let payload: unknown;
  try {
    payload = await request.json();
  } catch {
    return NextResponse.json(
      { error: "El cuerpo de la solicitud no tiene un formato JSON valido." },
      { status: 400 }
    );
  }

  try {
    const response = await fetch(`${BACKEND_BASE}/suppliers/${id}/rate`, {
      method: "PATCH",
      headers: {
        "Content-Type": "application/json",
        ...forwardHeaders(request),
      },
      body: JSON.stringify(payload),
      cache: "no-store",
    });

    const body = await response.text();
    return new NextResponse(body, {
      status: response.status,
      headers: {
        "Content-Type": response.headers.get("Content-Type") ?? "application/json; charset=utf-8",
      },
    });
  } catch {
    return NextResponse.json(
      { error: "No se pudo conectar con la API de proveedores." },
      { status: 502 }
    );
  }
}
