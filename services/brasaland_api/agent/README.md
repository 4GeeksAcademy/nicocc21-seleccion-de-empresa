# Agente de soporte (LangGraph)

Migración del RAG de Brasaland (`data/pipelines/rag.py`) a un grafo explícito de
[LangGraph](https://langchain-ai.github.io/langgraph/). La lógica de `embed`,
`retrieve` y `generate_answer` **no se reescribe**: los nodos la llaman por
separado, y nunca se usa `query()` (que haría recuperación y generación a la vez).

## Flujo

```
START → receive_question ─┬─(pregunta vacía)→ END
                          └→ retrieve ─┬─(hay contexto ≥ umbral)→ generate   → END
                                       └─(sin contexto)────────→ no_context → END
```

| Pieza | Archivo | Responsabilidad |
|-------|---------|-----------------|
| Estado | `state.py` | `run_id`, `question`, `documents`, `answer`, `error`. Sin historial: cada corrida es una pregunta aislada |
| `receive_question` | `nodes.py` | Normaliza y valida la pregunta |
| `route_after_receive` | `nodes.py` | Pregunta vacía → `END`; si no, `retrieve` |
| `retrieve` | `nodes.py` | `rag.retrieve(question)` |
| `route_after_retrieve` | `nodes.py` | Con documentos → `generate`; sin documentos → `no_context` |
| `generate` | `nodes.py` | `rag.generate_answer(question, documents)` con el contexto ya recuperado |
| `no_context` | `nodes.py` | Respuesta honesta sin llamar al LLM |
| Grafo | `graph.py` | Se compila al importar el módulo; un error estructural lanza `AgentGraphBuildError` |
| Checkpoints | `graph.py` | `SqliteSaver` con `thread_id = run_id`: un checkpoint por transición |
| Trace | `tracing.py` | Nodos y aristas en orden, con entrada, salida, duración y error |

Para la Parte 2, una capacidad nueva se añade como nodo y arista condicional en
`graph.py`, sin tocar los nodos existentes.

## API

| Método | Ruta | Respuesta |
|--------|------|-----------|
| `POST` | `/agent/query` | `{"answer", "run_id"}` · 400 si la pregunta está vacía · 503 si falla un nodo (sin detalles internos) |
| `GET` | `/agent/traces/{run_id}` | Trace completo de la corrida |
| `GET` | `/agent/traces/{run_id}/checkpoints` | Transiciones guardadas por el checkpointer |

`POST /knowledge/query` (RAG original) sigue disponible y no se modificó.

## Persistencia

| Dato | Ruta por defecto (ignorada por git) | Variable de entorno |
|------|-------------------------------------|---------------------|
| Traces | `services/brasaland_api/agent/data/traces.json` | `AGENT_TRACES_DB` |
| Checkpoints | `services/brasaland_api/agent/data/checkpoints.sqlite` | `AGENT_CHECKPOINTS_DB` |

De los chunks solo se guardan en el trace sus metadatos (`source_document`,
`section`, `chunk_index`, `score`), no el texto completo.

## Evals

Los evals corren sobre traces grabados, no en vivo.

1. Grabar los traces reales (requiere `GEMINI_API_KEY` y Qdrant con la base indexada):

   ```bash
   uv run python -m services.brasaland_api.agent.record_traces
   ```

   Se escriben en `tests/pipelines/fixtures/agent_traces/<caso>.json`.

2. Ejecutar los evals:

   ```bash
   uv run pytest tests/pipelines/test_agent_evals.py -v
   ```

| Eval | Criterio |
|------|----------|
| Orden | `receive_question → retrieve → generate` |
| Anclaje: nivel Oro | La respuesta menciona 1.500 puntos y se recuperó `loyalty-program` |
| Anclaje: alérgenos | La respuesta del Ceviche Brasaland menciona Pescado y se recuperó la guía de alérgenos |
| Sin contexto | Ruta `no_context`; `generate` no se ejecuta |
| Pregunta vacía | Rechazada antes de `retrieve` |

Tests unitarios del grafo (con mocks): `uv run pytest tests/pipelines/test_agent_graph.py`.
