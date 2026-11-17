"""Harness de protección para el Support Agent de Brasaland.

Proporciona guardrails multicapa para asegurar al agente:
1. SecurityGuardrail — detecta jailbreak / inyección de prompt
2. DomainClassifier  — clasifica la intención del usuario
3. ContentGuardrail  — detecta fuga de datos sensibles en respuestas
4. Harness           — orquestador que encadena los guardrails
"""

from .domain_classifier import DomainClassifier, DomainType, DomainResult
from .security_guardrail import SecurityGuardrail, SecurityResult, ThreatLevel
from .content_guardrail import ContentGuardrail, ContentResult
from .harness import Harness, HarnessResult, HarnessAction

__all__ = [
    "DomainClassifier",
    "DomainType",
    "DomainResult",
    "SecurityGuardrail",
    "SecurityResult",
    "ThreatLevel",
    "ContentGuardrail",
    "ContentResult",
    "Harness",
    "HarnessResult",
    "HarnessAction",
]