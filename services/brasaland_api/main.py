from __future__ import annotations

import collections
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
from services.brasaland_api.routes.knowledge import router as knowledge_router
from services.brasaland_api.routes.rfp import router as rfp_router
from services.brasaland_api.routes.rfp_response import router as rfp_response_router
from services.brasaland_api.routes.chat_ws import router as chat_ws_router
from services.brasaland_api.routes.agent import router as agent_router
from services.reporting.routes import router as reporting_router
from data.pipelines.storage import ensure_reporting_tables
from services.brasaland_api.seed import run_seed
from services.brasaland_api.notifications import init_notification_manager

import logging

_logger = logging.getLogger(__name__)
_timing_logger = logging.getLogger("api.timing")


@asynccontextmanager
async def lifespan(_: FastAPI):
    try:
        run_seed(verbose=False)
        run_incidents_seed(verbose=False)
        run_inventory_seed(verbose=False)
        ensure_reporting_tables()
        # Inicializar gestor de notificaciones SSE
        init_notification_manager()
        # Asegurar tablas de RFP en PostgreSQL
        from services.brasaland_api.rfp_models import ensure_rfp_tables
        ensure_rfp_tables()
        # Asegurar tablas de chat en PostgreSQL
        from services.brasaland_api.chat_models import ensure_chat_tables
        ensure_chat_tables()
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
    # CORS restringido a orígenes locales conocidos.
    # En producción, reemplazar con las URLs reales de los frontends.
    allow_origins=[
        "http://localhost:3000",   # Website (desarrollo)
        "http://localhost:3001",   # Backoffice (desarrollo)
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3001",
    ],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Rate Limiting (protección contra loops de costo en endpoints IA) ──
_RATE_LIMIT_STORE: dict[str, list[float]] = {}
_RATE_LIMIT_MAX_REQUESTS = 10
_RATE_LIMIT_WINDOW_SECONDS = 60

@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    # Solo aplicar rate limiting al endpoint de conocimiento (IA)
    if request.url.path == "/knowledge/query" and request.method == "POST":
        client_ip = request.client.host if request.client else "unknown"
        now = time.time()
        window_start = now - _RATE_LIMIT_WINDOW_SECONDS

        # Limpiar entradas antiguas
        if client_ip in _RATE_LIMIT_STORE:
            _RATE_LIMIT_STORE[client_ip] = [
                ts for ts in _RATE_LIMIT_STORE[client_ip]
                if ts > window_start
            ]
        else:
            _RATE_LIMIT_STORE[client_ip] = []

        # Verificar límite
        if len(_RATE_LIMIT_STORE[client_ip]) >= _RATE_LIMIT_MAX_REQUESTS:
            _logger.warning(
                "Rate limit excedido para %s en %s (%d requests en %ds)",
                client_ip, request.url.path,
                _RATE_LIMIT_MAX_REQUESTS, _RATE_LIMIT_WINDOW_SECONDS,
            )
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "detail": {
                        "code": "RATE_LIMIT_EXCEEDED",
                        "message": (
                            f"Máximo {_RATE_LIMIT_MAX_REQUESTS} requests por "
                            f"{_RATE_LIMIT_WINDOW_SECONDS} segundos. "
                            "Intenta de nuevo más tarde."
                        ),
                    }
                },
            )

        _RATE_LIMIT_STORE[client_ip].append(now)

    response = await call_next(request)
    return response


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
app.include_router(reporting_router)
app.include_router(knowledge_router)
app.include_router(rfp_router)
app.include_router(rfp_response_router)
app.include_router(chat_ws_router)
app.include_router(agent_router)
