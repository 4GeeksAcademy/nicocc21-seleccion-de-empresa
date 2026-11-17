"""
Pydantic models for the agent harness subsystem.

Defines shared types used across all guardrails:
- DomainType: classification of user intent
- DomainResult: output of DomainClassifier
- ThreatLevel: severity from SecurityGuardrail
- SecurityResult: output of SecurityGuardrail
- ContentResult: output of ContentGuardrail
- HarnessAction: what the harness decides to do
- HarnessResult: final decision from the orchestrator
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# ──────────────────────────────────────────────
# Enums
# ──────────────────────────────────────────────


class DomainType(str, Enum):
    """Classification of user intent per the company briefing and ticket SEC-114."""

    DOMAIN = "domain"
    """Pregunta sobre incidencias, inventario, procedimientos, calidad/operaciones."""

    SMALL_TALK = "small_talk"
    """Saludo breve, cortesía, conversación casual sin contenido operativo."""

    TRIVIA = "trivia"
    """Pregunta general de hostelería/operaciones que no revela secretos internos."""

    PERSONAL_TASK = "personal_task"
    """Tarea personal ajena al negocio: ensayos, deberes, código de otro proyecto,
    consejo personal no laboral, terapia."""

    SENSITIVE_QUERY = "sensitive_query"
    """Pregunta que busca datos sensibles: recetas madre con cantidades, precios de
    proveedores, contratos, nóminas, PII de clientes."""

    JAILBREAK = "jailbreak"
    """Intento de modificar instrucciones del sistema, inyección de prompt,
    "ignora tus instrucciones", "actúa como si no tuvieras reglas"."""


class ThreatLevel(str, Enum):
    """Severity level from the SecurityGuardrail."""

    NONE = "none"
    """No se detecta amenaza."""
    LOW = "low"
    """Patrón sospechoso pero no concluyente."""
    HIGH = "high"
    """Posible intento de jailbreak o inyección."""
    CRITICAL = "critical"
    """Intento directo y explícito de modificar instrucciones del sistema."""


class HarnessAction(str, Enum):
    """Action that the harness decides to take."""

    PASS = "pass"
    """Permitir que el agente procese la petición normalmente."""
    BLOCK = "block"
    """Rechazar la petición sin procesar."""
    REDIRECT = "redirect"
    """Responder brevemente y redirigir al contexto de la empresa."""
    SANITIZE = "sanitize"
    """Permitir pero filtrar contenido sensible de la respuesta."""


# ──────────────────────────────────────────────
# Results
# ──────────────────────────────────────────────


class DomainResult(BaseModel):
    """Result of domain classification."""

    domain: DomainType = Field(description="Clasificación del dominio.")
    confidence: float = Field(
        ge=0.0, le=1.0,
        description="Confianza en la clasificación (0-1).",
    )
    explanation: str = Field(
        default="",
        description="Razón de la clasificación (para logging/auditoría).",
    )
    matched_patterns: list[str] = Field(
        default_factory=list,
        description="Patrones que activaron la clasificación.",
    )


class SecurityResult(BaseModel):
    """Result of security guardrail check."""

    threat: ThreatLevel = Field(description="Nivel de amenaza detectado.")
    confidence: float = Field(
        ge=0.0, le=1.0,
        description="Confianza en la detección (0-1).",
    )
    explanation: str = Field(
        default="",
        description="Razón de la detección (para logging/auditoría).",
    )
    matched_patterns: list[str] = Field(
        default_factory=list,
        description="Patrones de ataque detectados.",
    )


class ContentResult(BaseModel):
    """Result of content guardrail scan (post-output)."""

    is_clean: bool = Field(description="True si la respuesta no contiene datos sensibles.")
    confidence: float = Field(
        ge=0.0, le=1.0,
        description="Confianza en la detección (0-1).",
    )
    explanation: str = Field(
        default="",
        description="Razón si se marcó como sensible.",
    )
    matched_patterns: list[str] = Field(
        default_factory=list,
        description="Patrones de datos sensibles detectados.",
    )
    sanitized_response: Optional[str] = Field(
        default=None,
        description="Respuesta con datos sensibles omitidos (si se aplicó sanitización).",
    )


class HarnessResult(BaseModel):
    """Final decision from the harness orchestrator."""

    action: HarnessAction = Field(description="Acción a tomar.")
    safe_input: str | None = Field(
        default=None,
        description="Texto seguro para pasar al agente (mensaje de redirección/bloqueo si aplica).",
    )
    safe_response: str | None = Field(
        default=None,
        description="Respuesta saneada lista para el usuario (post-content-scan).",
    )
    confidence: float = Field(
        default=0.0,
        ge=0.0, le=1.0,
        description="Confianza acumulada en la decisión.",
    )
    security_result: SecurityResult | None = Field(
        default=None,
        description="Resultado del guardrail de seguridad.",
    )
    domain_result: DomainResult | None = Field(
        default=None,
        description="Resultado del clasificador de dominio.",
    )
    content_result: ContentResult | None = Field(
        default=None,
        description="Resultado del guardrail de contenido (post-output).",
    )
    guardrail_results: dict[str, object] = Field(
        default_factory=dict,
        description="Resultados detallados de cada guardrail (clave: nombre del guardrail).",
    )
    processing_time_ms: float = Field(
        default=0.0,
        ge=0.0,
        description="Tiempo de procesamiento del pipeline en milisegundos.",
    )