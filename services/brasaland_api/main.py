from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from services.brasaland_api.incidents_seed import run_incidents_seed
from services.brasaland_api.routes.incidents import router as incidents_router
from services.brasaland_api.routes.suppliers import router as suppliers_router
from services.brasaland_api.seed import run_seed


@asynccontextmanager
async def lifespan(_: FastAPI):
    run_seed(verbose=False)
    run_incidents_seed(verbose=False)
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


app.include_router(suppliers_router)
app.include_router(incidents_router)
