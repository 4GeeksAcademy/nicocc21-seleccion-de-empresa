import { NextResponse } from "next/server";

const BACKEND_BASE =
  process.env.INCIDENTS_BACKEND_BASE_URL ?? "http://127.0.0.1:8000";

function forwardHeaders(request: Request): Record<string, string> {
  const headers: Record<string, string> = {};
  const auth = request.headers.get("Authorization");
  if (auth) headers["Authorization"] = auth;
  return headers;
}

export async function POST(request: Request) {
  let incomingFormData: FormData;
  try {
    incomingFormData = await request.formData();
  } catch {
    return NextResponse.json(
      { error: "El cuerpo de la solicitud no es valido." },
      { status: 400 }
    );
  }

  const file = incomingFormData.get("file");

  if (!file || !(file instanceof File)) {
    return NextResponse.json(
      { error: "No se encontro archivo CSV en el formulario. Usa el campo 'file'." },
      { status: 400 }
    );
  }

  const forwardData = new FormData();
  forwardData.append("file", file);

  try {
    const response = await fetch(`${BACKEND_BASE}/api/incidents/analyze`, {
      method: "POST",
      headers: { ...forwardHeaders(request) },
      body: forwardData,
      cache: "no-store",
    });

    const payloadText = await response.text();
    return new NextResponse(payloadText, {
      status: response.status,
      headers: {
        "Content-Type": response.headers.get("Content-Type") ?? "application/json; charset=utf-8",
      },
    });
  } catch {
    return NextResponse.json(
      { error: "No se pudo conectar con la API de incidencias." },
      { status: 502 }
    );
  }
}
