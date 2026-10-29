// uis/backoffice/app/api/telemetry/report/route.ts
// Proxy: GET /api/telemetry/report → Backend GET /telemetry/report

import { NextResponse } from "next/server";

const BACKEND_BASE =
  process.env.INVENTORY_BACKEND_BASE_URL ?? "http://127.0.0.1:8001";

export async function GET(request: Request) {
  try {
    const { searchParams } = new URL(request.url);
    const upstreamUrl = new URL(`${BACKEND_BASE}/telemetry/report`);

    const start_date = searchParams.get("start_date");
    const end_date = searchParams.get("end_date");

    if (start_date) upstreamUrl.searchParams.set("start_date", start_date);
    if (end_date) upstreamUrl.searchParams.set("end_date", end_date);

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
      { error: "No se pudo conectar con la API de telemetría." },
      { status: 502 },
    );
  }
}