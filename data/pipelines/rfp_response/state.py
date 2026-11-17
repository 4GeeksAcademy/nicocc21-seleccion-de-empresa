"""Estado compartido del pipeline rfp_response — Hito 9, Parte 2.

Dataclasses que definen el estado runtime del ciclo generador-evaluador.
No confundir con los modelos ORM de rfp_models.py.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class EvaluationResult:
    """Resultado de una evaluación sobre una sección generada.

    Cada evaluador (legibilidad, pertinencia, cumplimiento) produce
    uno de estos resultados.
    """
    evaluator_id: str  # "readability" | "relevance" | "compliance"
    passed: bool
    score: Optional[float] = None       # 0.0 – 1.0
    feedback: str = ""                   # Mensaje concreto para el generador
    details: Optional[dict] = None       # Métricas específicas del evaluador


@dataclass
class DepartmentIteration:
    """Una iteración del ciclo generador-evaluador para un departamento.

    Cada iteración contiene el draft generado + las evaluaciones de los
    3 evaluadores en paralelo.
    """
    iteration: int
    draft_content: str
    evaluations: list[EvaluationResult] = field(default_factory=list)
    all_passed: bool = False


@dataclass
class DepartmentResponse:
    """Estado completo del proceso generador-evaluador para un departamento.

    Flujo interno:
      pendiente → generando → evaluando → (aprobado | needs_human_review)
    """
    department_id: str

    # --- Entrada desde Parte 1 ---
    key_aspects: Optional[dict] = None
    metadata: Optional[dict] = None  # Metadatos relevantes para este depto

    # --- Ciclo generador-evaluador ---
    iterations: list[DepartmentIteration] = field(default_factory=list)
    max_iterations: int = 3
    current_iteration: int = 0
    needs_human_review: bool = False

    # --- Resultado final ---
    final_draft: Optional[str] = None
    final_evaluations: list[EvaluationResult] = field(default_factory=list)

    # --- Resumen consolidado (formato spec) ---
    evaluation_summary: Optional[dict] = None
    # {
    #   "section_id": str,
    #   "readability": {"pass": bool, "score": float, "details": dict},
    #   "relevance": {"pass": bool, "missing_aspects": list[str]},
    #   "compliance": {"pass": bool, "rule_ids": list[str], "violations": list[str]},
    #   "overall_pass": bool,
    #   "feedback_for_generator": str,
    # }

    # --- Estado interno ---
    status: str = "pendiente"
    # pendiente | generando | evaluando | aprobado | needs_human_review


@dataclass
class RFPResponseState:
    """Estado completo del pipeline de generación de respuesta a RFP.

    Entrada (handoff desde Parte 1):
      - ticket_id: int (obligatorio)
      - rfp_metadata: dict con metadatos completos
      - departments: list[DepartmentResponse] (uno por departamento activo)

    El pipeline itera el ciclo generador-evaluador hasta que todos los
    departamentos pasan o agotan su límite de iteraciones.
    """
    ticket_id: int

    # --- Handoff desde Parte 1 ---
    rfp_metadata: Optional[dict] = None

    # --- Departamentos activos ---
    departments: list[DepartmentResponse] = field(default_factory=list)

    # --- Estado global del ticket ---
    status: str = "generando_borrador"
    # generando_borrador | en_evaluacion | esperando_aprobacion | needs_human_review

    global_error: Optional[str] = None

    # --- Integración opcional con knowledge base ---
    knowledge_base_available: bool = False
    knowledge_context: Optional[str] = None