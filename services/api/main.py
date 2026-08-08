from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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


app.include_router(suppliers_router)
