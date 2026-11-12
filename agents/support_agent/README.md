# Agente de soporte (LangGraph)

Migración del RAG de Brasaland (`data/pipelines/rag.py`) a un grafo explícito de
[LangGraph](https://langchain-ai.github.io/langgraph/). La lógica de `embed`,
`retrieve` y `generate_answer` **no se reescribe**: los nodos la reutilizan.

## Flujo

```
START → retrieve → route_after_retrieve ─┬→ generate   → END
                                         └→ no_context → END
```

| Pieza | Archivo | Responsabilidad |
|-------|---------|-----------------|
| Estado | `state.py` | `run_id`, `question`, `documents`, `answer` (sin historial de conversación) |
| `retrieve` | `nodes.py` | Llama a `rag.retrieve(question)` |
| `route_after_retrieve` | `nodes.py` | Arista condicional: `generate` si hay documentos, si no `no_context` |
| `generate` | `nodes.py` | Llama a `rag.generate_answer(question, documents)` |
| `no_context` | `nodes.py` | Respuesta honesta sin llamar al LLM |
| Grafo | `graph.py` | `build_graph()` y `support_agent_graph`, compilado al importar el módulo |
| Trace | `tracing.py` | Registro por paso (entrada, salida, duración, error) persistido por `run_id` |

Para la Parte 2, una capacidad nueva se añade como nodo y arista condicional en
`graph.py`, sin tocar los nodos existentes.

## Uso

```python
from agents.support_agent import run_agent

result = run_agent("¿Cuántos puntos necesito para el nivel Oro?")
result.answer, result.run_id
```

Vía API:

- `POST /knowledge/query` con `{"question": "..."}` → `{"answer": "...", "run_id": "..."}`
- `GET /agent/traces/{run_id}` → trace de la corrida (404 si no existe)

## Trace

Se guarda en TinyDB en `agents/support_agent/data/traces.json` (ignorado por git).
La ruta se puede cambiar con la variable de entorno `AGENT_TRACES_DB`. De los
chunks solo se guardan metadatos (`source_document`, `section`, `chunk_index`,
`score`), no el texto completo.

## Tests

```bash
uv run pytest tests/agents -q
```
