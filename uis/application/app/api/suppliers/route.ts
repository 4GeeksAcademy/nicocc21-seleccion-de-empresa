import { NextResponse } from "next/server";

const BACKEND_BASE =
  process.env.SUPPLIERS_BACKEND_BASE_URL ?? "http://127.0.0.1:8001";

export async function GET(request: Request) {
  try {
    const { searchParams } = new URL(request.url);
    const upstreamUrl = new URL(`${BACKEND_BASE}/suppliers`);

    const country = searchParams.get("country");
    const category = searchParams.get("category");

    if (country) upstreamUrl.searchParams.set("country", country);
    if (category) upstreamUrl.searchParams.set("category", category);

    const response = await fetch(upstreamUrl.toString(), {
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

export async function POST(request: Request) {
  try {
    const payload = await request.json();

    const response = await fetch(`${BACKEND_BASE}/suppliers`, {
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
