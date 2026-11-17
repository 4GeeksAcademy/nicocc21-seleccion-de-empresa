"""Pipeline de generación de respuesta a RFP — Hito 9, Parte 2.

Grafo dedicado que orquesta:
  1. Lectura del handoff de la Parte 1 (ticket + metadatos + key_aspects)
  2. Ciclo generador-evaluador por departamento (máx. 3 iteraciones)
  3. Evaluación triple: legibilidad, pertinencia, cumplimiento
  4. Persistencia de resultados + handoff a Parte 3

Uso:
    from data.pipelines.rfp_response.graph import run_rfp_response_pipeline
    result = run_rfp_response_pipeline(ticket_id=42)
"""

from data.pipelines.rfp_response.graph import run_rfp_response_pipeline

__all__ = ["run_rfp_response_pipeline"]