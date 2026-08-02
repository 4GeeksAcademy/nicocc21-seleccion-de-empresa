#!/usr/bin/env python3
from __future__ import annotations

import cgi
import json
import sys
from pathlib import Path
from typing import Any, Iterable

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from services.api.incidents_core import (
    IncidentsValidationError,
    analyze_rows,
    load_rows_from_text,
    summary_to_csv_text,
)

LAST_SUMMARY: dict[str, Any] | None = None
LAST_SUMMARY_CSV: str | None = None


def _with_cors(headers: list[tuple[str, str]]) -> list[tuple[str, str]]:
    return headers + [
        ("Access-Control-Allow-Origin", "*"),
        ("Access-Control-Allow-Methods", "GET, POST, OPTIONS"),
        ("Access-Control-Allow-Headers", "Content-Type"),
    ]


def _json_response(status: str, payload: dict[str, Any]) -> tuple[str, list[tuple[str, str]], bytes]:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = [
        ("Content-Type", "application/json; charset=utf-8"),
        ("Content-Length", str(len(body))),
    ]
    return status, _with_cors(headers), body


def _extract_uploaded_csv(environ: dict[str, Any]) -> str:
    content_type = environ.get("CONTENT_TYPE", "")
    if "multipart/form-data" not in content_type:
        raise IncidentsValidationError(
            "Formato de contenido no soportado. Usa multipart/form-data."
        )

    form = cgi.FieldStorage(fp=environ["wsgi.input"], environ=environ, keep_blank_values=True)

    candidate_names = ["file", "csv", "incidents"]
    file_item = None

    for name in candidate_names:
        if name in form:
            file_item = form[name]
            break

    if file_item is None:
        for key in form.keys():
            item = form[key]
            if getattr(item, "file", None) is not None:
                file_item = item
                break

    if file_item is None or getattr(file_item, "file", None) is None:
        raise IncidentsValidationError(
            "No se encontro archivo CSV en el formulario. Usa el campo 'file'."
        )

    raw = file_item.file.read()
    if not raw:
        raise IncidentsValidationError("El archivo CSV esta vacio")

    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError as error:
        raise IncidentsValidationError(
            "El archivo no esta codificado en UTF-8"
        ) from error


def application(
    environ: dict[str, Any], start_response: Any
) -> Iterable[bytes]:
    global LAST_SUMMARY
    global LAST_SUMMARY_CSV

    method = environ.get("REQUEST_METHOD", "GET").upper()
    path = environ.get("PATH_INFO", "")

    if method == "OPTIONS":
        headers = _with_cors([
            ("Content-Type", "text/plain; charset=utf-8"),
            ("Content-Length", "0"),
        ])
        start_response("204 No Content", headers)
        return [b""]

    if path == "/" and method == "GET":
        status, headers, body = _json_response(
            "200 OK",
            {
                "service": "incidents-api",
                "status": "ok",
                "endpoints": {
                    "analyze": {
                        "method": "POST",
                        "path": "/api/incidents/analyze",
                        "content_type": "multipart/form-data",
                        "file_field": "file",
                    },
                    "export": {
                        "method": "GET",
                        "path": "/api/incidents/results/export",
                    },
                },
            },
        )
        start_response(status, headers)
        return [body]

    if path == "/api/incidents/analyze":
        if method != "POST":
            status, headers, body = _json_response(
                "405 Method Not Allowed", {"error": "Metodo no permitido"}
            )
            start_response(status, headers)
            return [body]

        try:
            csv_text = _extract_uploaded_csv(environ)
            rows = load_rows_from_text(csv_text)
            summary = analyze_rows(rows)
        except IncidentsValidationError as error:
            status, headers, body = _json_response("400 Bad Request", {"error": str(error)})
            start_response(status, headers)
            return [body]
        except Exception:
            status, headers, body = _json_response(
                "500 Internal Server Error", {"error": "Error interno procesando el archivo"}
            )
            start_response(status, headers)
            return [body]

        LAST_SUMMARY = summary
        LAST_SUMMARY_CSV = summary_to_csv_text(summary)

        status, headers, body = _json_response("200 OK", summary)
        start_response(status, headers)
        return [body]

    if path == "/api/incidents/results/export":
        if method != "GET":
            status, headers, body = _json_response(
                "405 Method Not Allowed", {"error": "Metodo no permitido"}
            )
            start_response(status, headers)
            return [body]

        if LAST_SUMMARY_CSV is None:
            status, headers, body = _json_response(
                "404 Not Found",
                {"error": "No hay resultados para exportar. Ejecuta primero el analisis."},
            )
            start_response(status, headers)
            return [body]

        body = LAST_SUMMARY_CSV.encode("utf-8")
        headers = [
            ("Content-Type", "text/csv; charset=utf-8"),
            ("Content-Disposition", "attachment; filename=incidents-results.csv"),
            ("Content-Length", str(len(body))),
        ]
        start_response("200 OK", _with_cors(headers))
        return [body]

    status, headers, body = _json_response("404 Not Found", {"error": "Ruta no encontrada"})
    start_response(status, headers)
    return [body]


if __name__ == "__main__":
    from wsgiref.simple_server import make_server

    host = "0.0.0.0"
    port = 8000
    print(f"API de incidencias disponible en http://{host}:{port}")
    with make_server(host, port, application) as httpd:
        httpd.serve_forever()
