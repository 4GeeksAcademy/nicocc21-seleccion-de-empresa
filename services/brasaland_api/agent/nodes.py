"""
services/brasaland_api/agent/nodes.py — Nodos y condiciones de salida del grafo.

Cada nodo tiene una sola responsabilidad. La lógica RAG no se reescribe: los
nodos llaman por separado a `retrieve` y `generate_answer` de
data/pipelines/rag.py. Nunca se usa `query()`, que haría ambas cosas a la vez.
"""

from __future__ import annotations

import logging
from typing import Any, Literal

from data.pipelines import rag

from services.brasaland_api.agent.state import SupportAgentState
from services.brasaland_api.agent.tools import (
    InventoryToolInput,
    IncidentToolInput,
    run_incident_tool,
    run_inventory_tool,
)

_logger = logging.getLogger(__name__)

EMPTY_QUESTION_ERROR = "La pregunta no puede estar vacía."
NO_CONTEXT_ANSWER = (
    "No tengo información suficiente en la base de conocimiento "
    "para responder esa pregunta."
)

# =========================================================================
# Nodos base (sin cambios)
# =========================================================================


def receive_question_node(state: SupportAgentState) -> dict[str, Any]:
    """Normaliza la pregunta y la valida antes de recuperar contexto."""
    question = state["question"].strip()
    if not question:
        return {"question": question, "error": EMPTY_QUESTION_ERROR}
    return {"question": question}


def retrieve_node(state: SupportAgentState) -> dict[str, Any]:
    """Recupera los chunks que superan el umbral de similitud."""
    return {"documents": rag.retrieve(state["question"])}


def generate_node(state: SupportAgentState) -> dict[str, Any]:
    """Genera la respuesta usando solo el contexto que ya recuperó `retrieve`."""
    return {"answer": rag.generate_answer(state["question"], state.get("documents", []))}


def no_context_node(state: SupportAgentState) -> dict[str, Any]:
    """Responde con honestidad cuando no hay contexto, sin llamar al LLM."""
    return {"answer": NO_CONTEXT_ANSWER}


# =========================================================================
# Router con LLM — decide qué fuente(s) usar según la pregunta
# =========================================================================

ROUTER_SYSTEM_PROMPT = """Eres un router de un agente de soporte de Brasaland, una cadena de restaurantes.
Tu tarea es clasificar la pregunta del usuario en UNA de las siguientes categorías.
Responde SOLO con el nombre de la categoría, nada más.

Categorías:
  - rag: La pregunta es sobre políticas, menú, información general de restaurantes, alérgenos, horarios, sucursales, etc. Usa la base de conocimiento.
  - incident_tool: La pregunta es sobre un ticket/incidente concreto (ej. "INC-0001"), quejas de clientes, estado de reportes, o filtros de incidentes.
  - inventory_tool: La pregunta es sobre insumos, stock, inventario, productos, ingredientes, cantidades disponibles.
  - rag_and_incident_tool: La pregunta NECESITA tanto información de políticas como datos de incidentes.
  - rag_and_inventory_tool: La pregunta NECESITA tanto información de políticas como datos de inventario.

Ejemplos:
  - "¿Cuánto cuesta el menú infantil?" → rag
  - "¿Qué pasó con el ticket INC-0001?" → incident_tool
  - "¿Cuánto pollo tenemos en inventario?" → inventory_tool
  - "Muestra los incidentes abiertos en el local 3" → incident_tool
  - "¿Hay suficiente carne para el menú del fin de semana?" → rag_and_inventory_tool
  - "¿Los clientes han reportado alergias al maní y tenemos suficiente inventario?" → rag_and_inventory_tool"""


def _call_llm_router(question: str) -> str:
    """Clasifica la pregunta usando Gemini (el mismo modelo del RAG)."""
    try:
        import google.genai as genai
        from google.genai import types as genai_types

        from services.brasaland_api.agent.graph import _load_env

        _load_env()
        import os

        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            _logger.warning("No GEMINI_API_KEY, usando fallback keyword router")
            return _keyword_router(question)

        client = genai.Client(api_key=api_key)
        model = os.environ.get("GENAI_MODEL", "gemini-2.0-flash-lite")

        response = client.models.generate_content(
            model=model,
            contents=question,
            config=genai_types.GenerateContentConfig(
                system_instruction=ROUTER_SYSTEM_PROMPT,
                temperature=0.0,
                max_output_tokens=20,
            ),
        )
        label = (response.text or "").strip().lower()
        valid = {"rag", "incident_tool", "inventory_tool", "rag_and_incident_tool", "rag_and_inventory_tool"}
        if label in valid:
            return label
        _logger.warning("Router devolvió label inválida '%s', usando fallback keyword", label)
        return _keyword_router(question)
    except Exception as exc:
        _logger.warning("Router LLM falló: %s, usando fallback keyword", exc)
        return _keyword_router(question)


def _keyword_router(question: str) -> str:
    """Router de respaldo basado en palabras clave.

    El orden es importante:
    1. Primero detecta combinaciones (RAG + tool)
    2. Luego tool individual
    3. Al final RAG por defecto
    """
    q = question.lower()

    # Palabras clave de incidentes
    incident_keywords = [
        "incidente", "inc-", "ticket", "queja", "reporte de incidente",
        "incidencia", "problema con pedido", "fallo operativo",
        "inc-000",
    ]
    has_incident = any(kw in q for kw in incident_keywords)

    # Palabras clave de inventario
    inventory_keywords = [
        "inventario", "stock", "insumo", "ingrediente",
        "cantidad disponible", "existencia",
        "inventario de", "bodega", "insumos",
    ]
    # "cuánto tenemos" solo es inventario si hay palabra de insumo cerca
    has_inventory = any(kw in q for kw in inventory_keywords)
    if not has_inventory:
        # Detectar preguntas de cantidad + producto alimenticio
        if ("cuánto" in q or "cuanta" in q or "cuantos" in q) and any(
            w in q for w in ["pollo", "carne", "pescado", "leche", "huevo", "verdura", "tomate", "cebolla"]
        ):
            has_inventory = True

    # Palabras clave RAG
    rag_keywords = [
        "menú", "menú infantil", "política", "horario", "alérgeno",
        "precio", "sucursal", "local", "info", "costo",
        "pollera brasaland", "brasapechito", "brasaland",
    ]
    has_rag = any(kw in q for kw in rag_keywords)

    # 1. Combinaciones primero
    if has_incident and has_rag:
        return "rag_and_incident_tool"
    if has_inventory and has_rag:
        return "rag_and_inventory_tool"

    # 2. Tool individual
    if has_incident:
        return "incident_tool"
    if has_inventory:
        return "inventory_tool"

    # 3. RAG por defecto
    return "rag"


def router_node(state: SupportAgentState) -> dict[str, Any]:
    """Clasifica la pregunta para decidir qué fuente(s) usar."""
    intent = _call_llm_router(state["question"])
    _logger.info("Router clasificó '%s' → %s", state["question"], intent)

    # Inicializar usage_summary
    usage = []
    if "rag" in intent:
        usage.append("rag")
    if "incident_tool" in intent:
        usage.append("incident_tool")
    if "inventory_tool" in intent:
        usage.append("inventory_tool")

    return {
        "intent": intent,
        "usage_summary": usage,
        "documents": [],                    # reset por si reconsumo
        "tool_input": {},
        "tool_result": {},
    }


# =========================================================================
# Nodos de tools externas
# =========================================================================


def incident_tool_node(state: SupportAgentState) -> dict[str, Any]:
    """Ejecuta la tool de incidentes contra el gestor real."""
    import time

    start = time.perf_counter()

    # Extraer ticket_id de la pregunta
    import re

    ticket_match = re.search(r"(INC-\d+)", state["question"])
    ticket_id = ticket_match.group(1) if ticket_match else None

    # Detectar filtros comunes
    input_ = IncidentToolInput(
        ticket_id=ticket_id,
    )

    result = run_incident_tool(input_)

    elapsed = round((time.perf_counter() - start) * 1000, 2)
    usage_summary = list(dict.fromkeys(state.get("usage_summary", []) + ["incident_tool"]))

    output: dict[str, Any] = {
        "tool_result": {
            "tool": "incident_tool",
            "success": result.success,
            "data": result.data,
            "error": result.error,
            "elapsed_ms": elapsed,
        },
        "usage_summary": usage_summary,
    }

    # Si la tool falló, registrar el error
    if not result.success:
        output["error"] = result.error

    return output


def inventory_tool_node(state: SupportAgentState) -> dict[str, Any]:
    """Ejecuta la tool de inventario contra el gestor real."""
    import time

    start = time.perf_counter()

    input_ = InventoryToolInput()

    result = run_inventory_tool(input_)

    elapsed = round((time.perf_counter() - start) * 1000, 2)
    usage_summary = list(dict.fromkeys(state.get("usage_summary", []) + ["inventory_tool"]))

    output: dict[str, Any] = {
        "tool_result": {
            "tool": "inventory_tool",
            "success": result.success,
            "data": result.data,
            "error": result.error,
            "elapsed_ms": elapsed,
        },
        "usage_summary": usage_summary,
    }

    if not result.success:
        output["error"] = result.error

    return output


def synthesizer_node(state: SupportAgentState) -> dict[str, Any]:
    """Combina contexto RAG y/o resultados de tools en una respuesta final.

    Este nodo se ejecuta después de que retrieve/incident_tool/inventory_tool
    hayan producido sus resultados. Decide qué fuentes usar y construye la
    respuesta usando el LLM si hay contenido.
    """
    question = state["question"]
    intent = state.get("intent", "rag")
    usage = state.get("usage_summary", [])
    documents = state.get("documents", [])
    tool_result = state.get("tool_result", {})
    existing_answer = state.get("answer")

    # Sin contexto ni tool data → respuesta honesta
    if not documents and not tool_result:
        return {"answer": NO_CONTEXT_ANSWER}

    # Si solo hay RAG (sin tools) y ya se generó una respuesta, reusarla
    if documents and not tool_result and existing_answer:
        return {"answer": existing_answer}

    # Si solo hay tool data (sin RAG), sintetizar respuesta desde los datos
    if not documents and tool_result:
        data = tool_result.get("data", [])
        if not data:
            return {"answer": NO_CONTEXT_ANSWER}
        if tool_result.get("tool") == "incident_tool":
            lines = "\n".join(
                f"- {d.get('incident_id', '?')}: {d.get('title', '?')} "
                f"({d.get('estado', '?')})"
                for d in data[:10]
            )
            return {"answer": f"Resultados de incidentes:\n{lines}"}
        elif tool_result.get("tool") == "inventory_tool":
            lines = "\n".join(
                f"- {d.get('name', '?')}: {d.get('current_stock', 0)} {d.get('unit', 'unidades')}"
                for d in data[:15]
            )
            return {"answer": f"Productos en inventario:\n{lines}"}
        return {"answer": f"Datos consultados: {data[:5]}"}

    # Si solo hay RAG (sin tools), delegar a generate_answer
    if documents and not tool_result:
        return {"answer": rag.generate_answer(question, documents)}

    # Si hay RAG + tools: construir contexto combinado y generar respuesta
    context_parts = []

    if documents:
        context_str = "\n\n".join(
            d.get("text", str(d)) for d in documents[:5]
        )
        context_parts.append(f"Contexto de la base de conocimiento:\n{context_str}")

    if tool_result and tool_result.get("success") and tool_result.get("data"):
        import json
        context_parts.append(
            f"Datos de la herramienta ({tool_result.get('tool', 'unknown')}):\n"
            f"{json.dumps(tool_result['data'][:10], ensure_ascii=False, default=str)}"
        )

    combined_context = "\n\n---\n\n".join(context_parts)

    if combined_context:
        return {"answer": rag.generate_answer(question, [{"text": combined_context}])}

    return {"answer": NO_CONTEXT_ANSWER}


# =========================================================================
# Rutas (sin cambios en las originales, se añaden nuevas)
# =========================================================================


def route_after_receive(state: SupportAgentState) -> Literal["reject", "router"]:
    """Si la pregunta está vacía, la rechaza; si no, pasa al router."""
    if state.get("error"):
        return "reject"
    return "router"


def route_after_retrieve(state: SupportAgentState) -> Literal["generate", "no_context"]:
    """Si hay contexto relevante, pasa al generador; si no, a la respuesta honesta."""
    return "generate" if state.get("documents") else "no_context"


# --- Nuevas rutas ---


def route_after_router(state: SupportAgentState) -> Literal[
    "rag_only",
    "incident_tool_only",
    "inventory_tool_only",
    "rag_and_incident",
    "rag_and_inventory",
]:
    """Enruta según el intent clasificado por el router."""
    intent = state.get("intent", "rag")
    if intent == "incident_tool":
        return "incident_tool_only"
    elif intent == "inventory_tool":
        return "inventory_tool_only"
    elif intent == "rag_and_incident_tool":
        return "rag_and_incident"
    elif intent == "rag_and_inventory_tool":
        return "rag_and_inventory"
    else:
        return "rag_only"


def route_tool_fallback(state: SupportAgentState) -> Literal["synthesizer"]:
    """Después de una tool (con o sin error), va al sintetizador."""
    return "synthesizer"
