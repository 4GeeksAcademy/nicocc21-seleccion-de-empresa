#!/usr/bin/env python3
"""
data/process/rag.py — Indexación de la base de conocimiento en Qdrant.

Responsabilidades (setup + embed):
  1. setup()       : Lee documentos desde docs/company-knowledge-base/,
                     los fragmenta en chunks semánticos (por encabezado),
                     los embebe con embed() y los indexa en Qdrant.
  2. embed(text)   : Genera el vector embedding de un texto usando un
                     modelo de embeddings dedicado (no el de generación).

Este módulo NO contiene lógica de recuperación ni generación de respuestas.
"""

from __future__ import annotations

import hashlib
import logging
import os
import re
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from google.genai import Client as GenaiClient
from google.genai.types import EmbedContentConfig
from qdrant_client import QdrantClient
from qdrant_client.http.models import (
    CollectionStatus,
    Distance,
    PointStruct,
    VectorParams,
)

_logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

CORPUS_DIR = Path(__file__).resolve().parents[2] / "docs" / "company-knowledge-base"
SOURCE_DOCUMENTS = {
    "loyalty-program": CORPUS_DIR / "brasaland-loyalty-program.es.md",
    "waste-protocol": CORPUS_DIR / "brasaland-waste-protocol.es.md",
    "menu-allergens": CORPUS_DIR / "brasaland-menu-allergens.es.md",
    "supplier-ordering": CORPUS_DIR / "brasaland-supplier-ordering.es.md",
}

# Mapa nombre-de-archivo → source_document payload
FILENAME_TO_SOURCE = {
    "brasaland-loyalty-program.es.md": "loyalty-program",
    "brasaland-waste-protocol.es.md": "waste-protocol",
    "brasaland-menu-allergens.es.md": "menu-allergens",
    "brasaland-supplier-ordering.es.md": "supplier-ordering",
}

# Vector dimensiones para text-embedding-004 (modelo de Google)
EMBEDDING_DIMENSION = 768

# Nombre de colección Qdrant (definido en BRIEFING)
QDRANT_COLLECTION = "brasaland_knowledge"


# ---------------------------------------------------------------------------
# Configuración de clientes (se inicializa bajo demanda)
# ---------------------------------------------------------------------------

def _load_env() -> None:
    """Carga .env desde services/brasaland_api/.env si existe."""
    env_path = Path(__file__).resolve().parents[2] / "services" / "brasaland_api" / ".env"
    if env_path.exists():
        load_dotenv(env_path)


def _get_qdrant_client() -> QdrantClient:
    """Devuelve un cliente Qdrant configurado desde variables de entorno."""
    _load_env()
    host = os.getenv("QDRANT_HOST", "localhost")
    port = int(os.getenv("QDRANT_PORT", "6333"))
    return QdrantClient(host=host, port=port)


def _get_genai_client() -> GenaiClient:
    """Devuelve un cliente GenAI configurado con la API key de 4Geeks."""
    _load_env()
    api_key = os.getenv("GEMINI_API_KEY", "")
    return GenaiClient(api_key=api_key)


# ---------------------------------------------------------------------------
# Chunking semántico
# ---------------------------------------------------------------------------

def _chunk_markdown(text: str, source_doc: str) -> list[dict[str, Any]]:
    """
    Fragmenta un documento Markdown en chunks semánticos basados en
    encabezados de nivel ## y ###.

    Cada chunk es una unidad autocontenida: no corta frases ni
    condiciones por la mitad. La estrategia es:
      1. Dividir el documento por líneas.
      2. Detectar secciones de nivel ## (título principal).
      3. Dentro de una sección ##, subdividir por ### si existen.
      4. Cada chunk incluye su encabezado para mantener contexto.
      5. Las cabeceras sin contenido sustancial (< 50 chars) se fusionan
         con el chunk siguiente para evitar fragmentos vacíos.

    Devuelve una lista de dicts con 'section', 'text'.
    """
    lines = text.splitlines()
    chunks: list[dict[str, Any]] = []

    # Variables de estado
    current_h2: str | None = None        # Último ## visto
    current_h3: str | None = None        # Último ### visto (si aplica)
    buffer: list[str] = []               # Líneas acumuladas del chunk actual
    current_section: str | None = None   # Título compuesto para el payload

    def _flush() -> None:
        """Vuelca el buffer actual como un chunk."""
        nonlocal buffer
        if not buffer:
            return
        body = "\n".join(buffer).strip()
        if body:
            chunks.append({
                "section": current_section or "sin-sección",
                "text": body,
            })
        buffer = []

    def _flush_if_substantial() -> None:
        """Vuelca el buffer solo si tiene contenido sustancial (>50 chars)."""
        nonlocal buffer
        if not buffer:
            return
        body = "\n".join(buffer).strip()
        if len(body) < 50:
            # Es solo un encabezado sin contenido → lo arrastramos al siguiente
            # Sección vacía pero mantenemos la referencia de section
            return
        chunks.append({
            "section": current_section or "sin-sección",
            "text": body,
        })
        buffer = []

    for line in lines:
        h2_match = re.match(r"^##\s+(.+)", line)
        h3_match = re.match(r"^###\s+(.+)", line)

        if h2_match:
            # Nueva sección de nivel 2 → cerrar chunk anterior si es sustancial
            _flush_if_substantial()
            current_h2 = h2_match.group(1).strip()
            current_h3 = None
            current_section = current_h2
            # Incluir el encabezado como parte del chunk
            buffer.append(line)
        elif h3_match:
            # Nueva subsección de nivel 3 → cerrar chunk anterior si es sustancial
            _flush_if_substantial()
            current_h3 = h3_match.group(1).strip()
            current_section = f"{current_h2} — {current_h3}" if current_h2 else current_h3
            buffer.append(line)
        else:
            buffer.append(line)

    # Último chunk
    body = "\n".join(buffer).strip() if buffer else ""
    if body:
        chunks.append({
            "section": current_section or "sin-sección",
            "text": body,
        })

    return chunks


def _parse_corpus() -> list[dict[str, Any]]:
    """
    Lee todos los documentos fuente y los divide en chunks semánticos.

    Devuelve una lista de dicts con:
      - source_document
      - section
      - text
      - chunk_index
    """
    all_chunks: list[dict[str, Any]] = []

    for source_key, filepath in SOURCE_DOCUMENTS.items():
        if not filepath.exists():
            _logger.warning("Archivo no encontrado: %s", filepath)
            continue

        text = filepath.read_text(encoding="utf-8")
        raw_chunks = _chunk_markdown(text, source_key)

        for idx, chunk in enumerate(raw_chunks):
            all_chunks.append({
                "source_document": source_key,
                "section": chunk["section"],
                "text": chunk["text"],
                "chunk_index": idx,
            })

    return all_chunks


# ---------------------------------------------------------------------------
# Embeddings
# ---------------------------------------------------------------------------

def embed(text: str) -> list[float]:
    """
    Genera el vector embedding para un texto usando el modelo de embeddings
    dedicado (text-embedding-004).

    Esta función se usa tanto para indexar chunks como para embeber
    la consulta del usuario durante retrieve().
    """
    client = _get_genai_client()
    model = os.getenv("EMBEDDING_MODEL_ID", "text-embedding-004")
    config = EmbedContentConfig(model=model)
    result = client.models.embed_content(
        model=model,
        contents=text,
        config=config,
    )
    return result.embeddings[0].values


# ---------------------------------------------------------------------------
# Setup (idempotente)
# ---------------------------------------------------------------------------

def _chunk_id(source_document: str, chunk_index: int) -> str:
    """
    Genera un UUID determinista basado en el documento fuente y el índice
    del chunk. Esto permite que setup() sea idempotente: volver a ejecutarlo
    con los mismos documentos produce los mismos IDs.
    """
    raw = f"{source_document}:{chunk_index}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


def setup(*, force_recreate: bool = False) -> int:
    """
    Fase 1 — Indexación completa del corpus en Qdrant.

    1. Lee y fragmenta los documentos fuente.
    2. Crea la colección Qdrant si no existe (o la recrea si force_recreate).
    3. Embebe cada chunk y lo inserta como point.

    Es idempotente: si los chunks ya existen (mismo ID), Qdrant los
    sobrescribe silenciosamente gracias a los IDs deterministas.

    Args:
        force_recreate: si True, elimina y recrea la colección antes
                        de indexar.

    Returns:
        Número de chunks indexados.
    """
    # 1. Parsear corpus
    chunks = _parse_corpus()
    if not chunks:
        _logger.warning("No se encontraron chunks para indexar.")
        return 0

    _logger.info("Se procesaron %d chunks del corpus.", len(chunks))

    # 2. Conectar a Qdrant
    qdrant = _get_qdrant_client()

    # 3. Gestionar colección
    collection = os.getenv("QDRANT_COLLECTION", QDRANT_COLLECTION)
    existing = qdrant.get_collections()

    if force_recreate and collection in [c.name for c in existing.collections]:
        _logger.info("Eliminando colección existente '%s' (force_recreate=True).", collection)
        qdrant.delete_collection(collection)
        existing = qdrant.get_collections()

    if collection not in [c.name for c in existing.collections]:
        _logger.info("Creando colección '%s' con distancia COSENO.", collection)
        qdrant.create_collection(
            collection_name=collection,
            vectors_config=VectorParams(
                size=EMBEDDING_DIMENSION,
                distance=Distance.COSINE,
            ),
        )

    # 4. Embeder e indexar
    points: list[PointStruct] = []
    for chunk in chunks:
        chunk_text = chunk["text"]
        vector = embed(chunk_text)
        point_id = _chunk_id(chunk["source_document"], chunk["chunk_index"])

        points.append(PointStruct(
            id=point_id,
            vector=vector,
            payload={
                "company": "brasaland",
                "source_document": chunk["source_document"],
                "section": chunk["section"],
                "language": "es",
                "chunk_index": chunk["chunk_index"],
                "text": chunk_text,
            },
        ))

    # Insertar en lotes de 10 para evitar payloads demasiado grandes
    batch_size = 10
    for i in range(0, len(points), batch_size):
        batch = points[i : i + batch_size]
        qdrant.upsert(collection_name=collection, points=batch)
        _logger.info("Indexados %d / %d chunks...", min(i + batch_size, len(points)), len(points))

    _logger.info(
        "Indexación completada: %d chunks en colección '%s'.",
        len(points),
        collection,
    )
    return len(points)


# ---------------------------------------------------------------------------
# CLI directo
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
    force = "--force" in sys.argv
    count = setup(force_recreate=force)
    print(f"✅ Indexados {count} chunks en Qdrant.")