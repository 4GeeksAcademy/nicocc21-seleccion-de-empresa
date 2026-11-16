"""Pipeline de recepción RFP — Hito 9, Parte 1.

Grafo LangGraph dedicado que orquesta:
  1. PDF → Markdown (MarkItDown)
  2. Métricas de legibilidad (py-readability-metrics)
  3. Clasificador (¿es RFP válida?)
  4. Orquestador (descomposición por departamento)
  5. Workers (análisis por departamento)
  6. Synthesizer (resumen consolidado)
  7. Persistencia en PostgreSQL

Uso:
    from data.pipelines.rfp_intake.graph import run_rfp_intake
    result = run_rfp_intake(ticket_id=1, pdf_path="data/raw/solicitud.pdf")
"""

from data.pipelines.rfp_intake.graph import run_rfp_intake

__all__ = ["run_rfp_intake"]