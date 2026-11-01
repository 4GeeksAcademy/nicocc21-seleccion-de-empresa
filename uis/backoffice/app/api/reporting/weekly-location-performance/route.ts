import { NextResponse } from "next/server";

const BACKEND_BASE =
  process.env.INVENTORY_BACKEND_BASE_URL ?? "http://127.0.0.1:8001";

export async function GET(request: Request) {
  try {
    const { searchParams } = new URL(request.url);
    const upstreamUrl = new URL(
      `${BACKEND_BASE}/reporting/weekly-location-performance`
    );
    const weekStart = searchParams.get("week_start");

    if (weekStart) upstreamUrl.searchParams.set("week_start", weekStart);

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
      { error: "No se pudo conectar con el reporte semanal." },
      { status: 502 }
    );
  }
}