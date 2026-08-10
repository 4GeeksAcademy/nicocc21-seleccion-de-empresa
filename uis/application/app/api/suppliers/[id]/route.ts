import { NextResponse } from "next/server";

const BACKEND_BASE =
  process.env.SUPPLIERS_BACKEND_BASE_URL ?? "http://127.0.0.1:8001";

type Context = {
  params: Promise<{ id: string }>;
};

export async function GET(_: Request, context: Context) {
  const { id } = await context.params;

  try {
    const response = await fetch(`${BACKEND_BASE}/suppliers/${id}`, {
      method: "GET",
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

export async function DELETE(_: Request, context: Context) {
  const { id } = await context.params;

  try {
    const response = await fetch(`${BACKEND_BASE}/suppliers/${id}`, {
      method: "DELETE",
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
