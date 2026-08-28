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

from services.api.routes.auth import router as auth_router
from services.api.routes.users import router as users_router
from services.api.routes.profiles import router as profiles_router
from services.api.routes.suppliers import router as suppliers_router
from services.api.seed import run_seed


@asynccontextmanager
async def lifespan(_: FastAPI):
    run_seed(verbose=False)
    yield


app = FastAPI(
    title="Brasaland Suppliers API",
    description="Directorio de proveedores con FastAPI + TinyDB + Pydantic",
    version="0.1.0",
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
