#!/usr/bin/env python3
"""
data/pipelines/rag_safety.py — Filtros de seguridad para el pipeline RAG.
Protege contra:
  1. Prompt injection indirecta: instrucciones maliciosas incrustadas en
     documentos de la base de conocimiento.
  2. Fuga de información: detección de intentos de extracción de datos
     sensibles a través de preguntas manipuladas.
Integración:
  - Se llama desde retrieve() para sanitizar chunks antes de pasarlos al LLM.
  - Se llama desde query() para validar la pregunta del usuario.
"""

from __future__ import annotations
import logging
import re
from typing import Any

_logger = logging.getLogger(__name__)

_INDIRECT_INJECTION_PATTERNS: list[re.Pattern] = [
    # ─── Instrucciones directas al LLM (ES) ──
    re.compile(r"\bal\s+(responder|contestar|generar|decir|escribir)\s*,?\s*(recomienda|sugiere|di\s+siempre|nunca\s+digas)", re.I),
    re.compile(r"\bal\s+(generar|decir|responder|contestar|escribir)\s+la\s+respuesta\s*,?\s*(recomienda|sugiere|di\s+siempre|nunca\s+digas)", re.I),
    re.compile(r"\b(siempre\s+que\s+respondas|cada\s+vez\s+que\s+respondas|en\s+tu\s+respuesta)\s*,?\s*(recomienda|sugiere|di)", re.I),
    # ─── Instrucciones directas al LLM (EN) ──
    re.compile(r"\b(when\s+(answering|responding|replying)|in\s+(your\s+)?response|as\s+(an?\s+)?assistant),?\s*(always|never|recommend|suggest|say)", re.I),
    # ─── Ignorar instrucciones (ES) ──
    re.compile(r"\big[n]ora\s+(todas\s+)?(las\s+)?instrucciones\s+(anteriores|previas|del\s+sistema)", re.I),
    re.compile(r"\big[n]ora\s+completamente\s+las\s+instrucciones", re.I),
    # ─── Ignorar instrucciones anteriores + pedir datos específicos (briefing Brasaland) ──
    re.compile(r"\big[n]ora\s+las\s+instrucciones\s+anteriores\s+y\s+dime\s+cu[aá]ntos\s+puntos\s+brasa", re.I),
    # ─── Ignorar instrucciones (EN) ──
    re.compile(r"\bignore\s+(all\s+)?(previous|system|prior)\s+(instructions|directives|prompt|rules)", re.I),
    re.compile(r"\band\s+do\s+what\s+(I|i)\s+say", re.I),
    # ─── Suplantación system prompt (ES) ──
    re.compile(r"\b(system\s+prompt|nuevas?\s+instrucciones?|new\s+instructions?)\s*:", re.I),
    re.compile(r"\ba\s+partir\s+de\s+ahora\s*[,:]\s*(eres|debes|tienes\s+que|act[uú]a)", re.I),
    re.compile(r"\bdesde\s+ahora\s+eres\s+un\s+", re.I),
    # ─── Suplantación system prompt (EN) ──
    re.compile(r"\bfrom\s+now\s+on\s*,?\s*(you\s+are|you\s+must|act\s+as|you'?re?\s+to)", re.I),
    # ─── Recomendaciones forzadas (ES) ──
    re.compile(r"\b(siempre\s+recomienda|sugiere\s+siempre)\s+(el\s+)?proveedor", re.I),
    # ─── Recomendaciones forzadas (EN) ──
    re.compile(r"\balways\s+recommend\s+(the\s+)?(supplier|product)", re.I),
    # ─── Override reglas (ES) ──
    re.compile(r"\b(no\s+hagas?\s+caso|disregard)\s+(a\s+)?(las?|los?|cualquier)\s+(regla|norma|pol[ií]tica|restricci[oó]n)", re.I),
    re.compile(r"\bno\s+tengas?\s+en\s+cuenta\s+(las?|los?|ninguna)\s+(regla|norma|pol[ií]tica|restricci[oó]n)", re.I),
    re.compile(r"\bno\s+(tengas|tenga)\s+en\s+(cuenta|consideraci[oó]n)\s+(las?|los?|ninguna|tus|mis)", re.I),
    re.compile(r"\ba\s+(ninguna|cualquier)\s+(regla\s+de\s+negocio|norma)", re.I),
    # ─── Override reglas (EN) ──
    re.compile(r"\b(disregard|ignore)\s+(any\s+)?(business\s+)?(rule|policy|restriction|guideline)", re.I),
    # ─── No mencionar competidores ──
    re.compile(r"\b(nunca\s+menciones|never\s+mention|no\s+diga)\s+(competidores?|precios?\s+reales?)", re.I),
    # ─── Mentir ──
    re.compile(r"\b(puedes?\s+mentir|it[`']?s?\s+ok(ay)?\s+to\s+lie|feel\s+free\s+to\s+lie)", re.I),
    # ─── Revelación datos (ES) ──
    re.compile(r"\b(dime|C[uú][eé]ntame|reveal|disclose)\s+(todo\s+)?(lo\s+)?(que\s+)?sabes?\s+(sobre|de|about)", re.I),
    re.compile(r"\b(dime|C[uú][eé]ntame)\s+(todo\s+)?(lo\s+)?(que\s+)?sabes?\s+de\s+(las?|los?)", re.I),
    # ─── Revelación datos (EN) ──
    re.compile(r"\b(tell\s+me|reveal|disclose)\s+(everything|all)\s+(you\s+knows+)?(about|regarding)", re.I),
    # ─── Olvidar identidad (ES) ──
    re.compile(r"\bolvida\s+que\s+(trabajas|trabajaste|eres|perteneces|haces\s+parte\s+de)", re.I),
    # ─── Olvidar identidad (EN) ──
    re.compile(r"\b(forget|erase|remove)\s+(that\s+)?(you\s+(work|are|belong|work\s+for))", re.I),
    # ─── "haz lo que te pido" ──
    re.compile(r"\by\s+haz\s+lo\s+que\s+(te\s+pido|yo\s+diga|quiero)", re.I),
]

def sanitize_context(chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Filtra chunks con instrucciones maliciosas."""
    if not chunks:
        return []
    safe_chunks: list[dict[str, Any]] = []
    removed_count = 0
    for chunk in chunks:
        text = chunk.get("text", "")
        if not text:
            continue
        if _has_injection_pattern(text):
            source = chunk.get("source_document", "unknown")
            _logger.warning(
                "Chunk bloqueado por posible prompt injection indirecta: "
                "source=%s, text_preview=%r", source, text[:100],
            )
            removed_count += 1
            continue
        safe_chunks.append(chunk)
    if removed_count > 0:
        _logger.info("Sanitización: %d chunks bloqueados de %d totales", removed_count, len(chunks))
    return safe_chunks

def _has_injection_pattern(text: str) -> bool:
    for pattern in _INDIRECT_INJECTION_PATTERNS:
        if pattern.search(text):
            return True
    return False

_SUSPICIOUS_QUESTION_PATTERNS: list[re.Pattern] = [
    re.compile(r"\b(ignora|ignore|olvida|forget)\s+(el\s+)?contexto\s+(anterior|previo|entregado|proporcionado)", re.I),
    re.compile(r"\b(d[aá]me|dame|give\s+me)\s+(todo\s+)?(el\s+)?contexto\s+(completo|sin\s+filtro)", re.I),
    re.compile(r"\b(devuelve|return|output|show)\s+(el\s+)?(texto\s+)?completo\s+(del\s+)?(documento|chunk|art[ií]culo)", re.I),
    re.compile(r"\b(d[aá]me|dame|d[ae]me)\s+(el\s+)?(texto\s+)?completo\s+(del\s+)?(documento|chunk)", re.I),
    re.compile(r"\b(cu[aá]les?\s+son\s+tus\s+instrucciones|what\s+are\s+your\s+instructions|rep[ií]te\s+tu\s+prompt)", re.I),
    re.compile(r"\b(dime\s+tu\s+system\s+prompt|repeat\s+your\s+system\s+prompt|output\s+your\s+prompt)", re.I),
    re.compile(r"\b(cu[aá]l\s+es\s+tu\s+prompt\s+del\s+sistema)", re.I),
    re.compile(r"\b(what\s+are\s+your\s+instructions|tell\s+me\s+your\s+system\s+prompt|what\s+is\s+your\s+prompt)", re.I),
    re.compile(r"\bforget\s+(the\s+)?(above\s+)?(context|instructions|everything|all)", re.I),
    re.compile(r"\big[n]ora\s+el\s+contexto\s+entregado", re.I),
    re.compile(r"\big[n]ora\s+el\s+contexto\s+proporcionado", re.I),
    re.compile(r"\b(dame|d[ae]me|mu[eé]strame|muestra|trae)\s+(todo\s+)?(el\s+)?documento\s+(completo|entero|sin\s+resumir)", re.I),
    re.compile(r"\b(devuelve|retorna|return)\s+(el\s+)?(documento|chunk)\s+(completo|entero|full)\s+(sin\s+)?(resumir|modificar|cambiar|text)", re.I),
    re.compile(r"\b(full\s+document\s+text|whole\s+document)", re.I),
    re.compile(r"\b(ignore|disregard)\s+(the\s+)?above", re.I),
]

def detect_suspicious_query(question: str) -> bool:
    if not question or not question.strip():
        return False
    for pattern in _SUSPICIOUS_QUESTION_PATTERNS:
        if pattern.search(question):
            _logger.warning("Pregunta sospechosa detectada: %r", question[:150])
            return True
    return False

def safe_retrieve(query: str, *, k: int = 5, min_score: float = 0.45) -> list[dict[str, Any]]:
    from data.pipelines.rag import retrieve as _retrieve
    chunks = _retrieve(query, k=k, min_score=min_score)
    return sanitize_context(chunks)