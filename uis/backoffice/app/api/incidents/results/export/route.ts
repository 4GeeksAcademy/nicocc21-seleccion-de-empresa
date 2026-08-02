import { NextResponse } from "next/server";

const BACKEND_BASE =
  process.env.INCIDENTS_BACKEND_BASE_URL ?? "http://127.0.0.1:8000";

export async function GET() {
  try {
    const response = await fetch(`${BACKEND_BASE}/api/incidents/results/export`, {
      method: "GET",
      cache: "no-store",
    });

    const body = await response.arrayBuffer();
    return new NextResponse(body, {
      status: response.status,
      headers: {
        "Content-Type": response.headers.get("Content-Type") ?? "text/csv; charset=utf-8",
        "Content-Disposition":
          response.headers.get("Content-Disposition") ??
          "attachment; filename=incidents-results.csv",
      },
    });
  } catch {
    return NextResponse.json(
      { error: "No se pudo conectar con la API de incidencias." },
      { status: 502 }
    );
  }
}
