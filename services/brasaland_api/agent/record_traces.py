"""
services/brasaland_api/agent/record_traces.py — Graba traces reales para los evals.

Ejecuta cada pregunta de evaluación contra el grafo real (Gemini + Qdrant) y
exporta el trace de la corrida a tests/pipelines/fixtures/agent_traces/<id>.json.
Los evals de tests/pipelines/test_agent_evals.py leen esos archivos y nunca
llaman al modelo en vivo.

Uso (requiere GEMINI_API_KEY y Qdrant con la base de conocimiento indexada):
    uv run python -m services.brasaland_api.agent.record_traces            # todos los casos
    uv run python -m services.brasaland_api.agent.record_traces out_of_scope  # solo algunos
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[3]
FIXTURES_DIR = REPO_ROOT / "tests" / "pipelines" / "fixtures" / "agent_traces"

EVAL_QUESTIONS: dict[str, str] = {
    "loyalty_gold_tier": "¿Cuántos puntos necesito para alcanzar el nivel Oro de Brasa Points?",
    "ceviche_allergens": "¿Qué alérgenos tiene el Ceviche Brasaland?",
    "out_of_scope": "¿Quién ganó el Mundial de fútbol de 1986?",
    "empty_question": "   ",
}


def main(case_ids: list[str]) -> int:
    unknown = sorted(set(case_ids) - EVAL_QUESTIONS.keys())
    if unknown:
        print(f"Casos desconocidos: {', '.join(unknown)}. Disponibles: {', '.join(EVAL_QUESTIONS)}", file=sys.stderr)
        return 2

    load_dotenv(REPO_ROOT / ".env")
    load_dotenv(REPO_ROOT / "services" / "brasaland_api" / ".env")

    from services.brasaland_api.agent import AgentRunError, run_agent
    from services.brasaland_api.agent import tracing

    FIXTURES_DIR.mkdir(parents=True, exist_ok=True)
    failures = 0
    for case_id in case_ids or list(EVAL_QUESTIONS):
        question = EVAL_QUESTIONS[case_id]
        try:
            run_id = run_agent(question).run_id
        except AgentRunError as exc:
            run_id = exc.run_id
            failures += 1
        trace = tracing.get_trace(run_id)
        output_file = FIXTURES_DIR / f"{case_id}.json"
        output_file.write_text(json.dumps(trace, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        status = trace["status"] if trace else "sin trace"
        print(f"[{status}] {case_id} → {output_file.relative_to(REPO_ROOT)}")

    if failures:
        print(f"{failures} corrida(s) fallaron; revisa el campo 'error' de cada trace.", file=sys.stderr)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
