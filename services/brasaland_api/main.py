from __future__ import annotations

import re
import time
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import uuid4

from dotenv import load_dotenv
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# Cargar variables de entorno desde .env (antes de importar módulos que las usan)
_env_path = Path(__file__).resolve().parent / ".env"
if _env_path.exists():
    load_dotenv(_env_path)

from services.brasaland_api.incidents_seed import run_incidents_seed
from services.brasaland_api.inventory_seed import run_inventory_seed
from services.brasaland_api.inventory_telemetry import event_context, make_event, route_template
from services.brasaland_api.routes.auth import router as auth_router
from services.brasaland_api.routes.incidents import router as incidents_router
from services.brasaland_api.routes.inventory import router as inventory_router
from services.brasaland_api.routes.profiles import router as profiles_router
from services.brasaland_api.routes.suppliers import router as suppliers_router
from services.brasaland_api.routes.telemetry import router as telemetry_router
from services.brasaland_api.routes.users import router as users_router
from services.brasaland_api.seed import run_seed

import logging

_logger = logging.getLogger(__name__)
_timing_logger = logging.getLogger("api.timing")


@asynccontextmanager
async def lifespan(_: FastAPI):
    try:
        run_seed(verbose=False)
        run_incidents_seed(verbose=False)
        run_inventory_seed(verbose=False)
    except Exception:
        _logger.exception("Error al ejecutar seed durante el inicio")
    yield


app = FastAPI(
    title="Brasaland API",
    description=(
        "API de autenticación, proveedores e incidencias con TinyDB, "
        "e inventario con SQLModel y Supabase PostgreSQL"
    ),
    version="0.3.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Middleware de timing y telemetría ─────────────────────────────────
@app.middleware("http")
async def telemetry_middleware(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    duration = (time.perf_counter() - start) * 1000  # ms

    _timing_logger.info(
        "%s %s → %s | %.1fms",
        request.method,
        request.url.path,
        response.status_code,
        duration,
    )

    # api_request_completed — excluir propio endpoint de telemetría
    if not request.url.path.startswith("/telemetry/"):
        ctx = event_context(request, None)
        event = make_event("api_request_completed", {
            "route_template": route_template(str(request.url.path)),
            "method": request.method, "status_code": response.status_code,
            "duration_ms": duration, "source": "backend",
        }, ctx)
        # Adjuntar el evento como encabezado de depuración (el frontend
        # puede recogerlo desde responses 2xx/4xx si el cliente lo soporta)
        if hasattr(response, "headers"):
            response.headers["X-Telemetry-Event"] = event["eventId"]
    return response


# ─── Exception handlers de telemetría ─────────────────────────────────

@app.exception_handler(RequestValidationError)
async def validation_failed_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    ctx = event_context(request, None)
    errors = exc.errors() if hasattr(exc, "errors") else []
    # El esquema exige slugs en minúscula para campos y códigos en MAYÚSCULA.
    field_names = sorted({
        name for name in (re.sub(r"[^a-z0-9_]", "_", str(error.get("loc", ("body",))[-1]).lower()) for error in errors)
        if re.fullmatch(r"[a-z][a-z0-9_]{0,63}", name)
    })
    validation_codes = sorted({
        code for code in (re.sub(r"[^A-Z0-9_]", "_", str(error.get("type", "INVALID_VALUE")).upper()) for error in errors)
        if re.fullmatch(r"[A-Z][A-Z0-9_]{0,63}", code)
    })
    event = make_event("validation_failed", {
        "route_template": route_template(str(request.url.path)),
        "field_names": field_names or ["body"],
        "validation_codes": validation_codes or ["INVALID_VALUE"],
    }, ctx)
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content={"detail": {"code": "VALIDATION_ERROR", "telemetry_events": [event]}},
    )


@app.get("/")
def root() -> dict[str, str]:
    return {"service": "brasaland-api", "status": "ok"}


app.include_router(auth_router)
app.include_router(users_router)
app.include_router(profiles_router)
app.include_router(suppliers_router)
app.include_router(incidents_router)
app.include_router(inventory_router)
app.include_router(telemetry_router)
