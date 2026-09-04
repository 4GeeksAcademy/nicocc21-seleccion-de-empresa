from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Cargar variables de entorno desde .env (antes de importar módulos que las usan)
_env_path = Path(__file__).resolve().parent / ".env"
if _env_path.exists():
    load_dotenv(_env_path)

from services.brasaland_api.incidents_seed import run_incidents_seed
from services.brasaland_api.routes.auth import router as auth_router
from services.brasaland_api.routes.incidents import router as incidents_router
from services.brasaland_api.routes.profiles import router as profiles_router
from services.brasaland_api.routes.suppliers import router as suppliers_router
from services.brasaland_api.routes.users import router as users_router
from services.brasaland_api.seed import run_seed

import logging

_logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    try:
        run_seed(verbose=False)
        run_incidents_seed(verbose=False)
    except Exception:
        _logger.exception("Error al ejecutar seed durante el inicio")
    yield


app = FastAPI(
    title="Brasaland API",
    description="Brasaland — API de proveedores e incidencias con FastAPI + TinyDB + Pydantic",
    version="0.2.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root() -> dict[str, str]:
    return {"service": "suppliers-api", "status": "ok"}


app.include_router(auth_router)
app.include_router(users_router)
app.include_router(profiles_router)
app.include_router(suppliers_router)
app.include_router(incidents_router)
