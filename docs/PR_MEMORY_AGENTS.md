# PR: Hito 8 — Memory & Self-Improvement for Support Agent (Part 1)

**Branch:** `feature/agent-memory`
**Ticket:** #MEM-092

---

## Resumen

Implementación del subsistema de memoria para el **Support Agent** de Brasaland. El agente ahora puede recordar información recurrente sobre locales, horarios, proveedores, incidencias y preferencias, siguiendo un flujo **proposal-before-write**: primero pregunta al usuario, y solo si este confirma explícitamente, guarda la información.

### Flujo completo

```
Interacción del usuario
    │
    ▼
Evaluator (regex) → ¿es memorable? → No → fin
    │ Sí
    ▼
Proposer → crea propuesta + pide confirmación
    │
    ▼
Usuario responde: Sí / No / Edita / (ambiguo)
    │
    ▼
Proposer clasifica → registra decisión (siempre)
    │
    ├─ Aceptado/Editado → MemoryEntry + Consolidación
    └─ Rechazado/Ambiguo  → solo registro (no se guarda)
```

---

## Checklist de requerimientos (Hito 8)

| # | Requisito | Estado |
|---|-----------|--------|
| 1 | `agents/support_agent/memory/` con `__init__.py`, `schemas.py` | ✅ |
| 2 | `MemoryEvaluator` — detección basada en regex (umbral configurable) | ✅ |
| 3 | `MemoryProposer` — genera propuestas y clasifica respuestas del usuario | ✅ |
| 4 | `MemoryStore` — persistencia JSON atómica con ThreadSafety | ✅ |
| 5 | `MemoryConsolidator` — agrupa por (location_id, category) | ✅ |
| 6 | `MemoryManager` — orquestador (evalúa → propone → decide → guarda → contexto) | ✅ |
| 7 | Integración en `SupportAgent` (CLI + MCP) | ✅ |
| 8 | Tests unitarios (178 tests, todos pasan) | ✅ |
| 9 | Documentación: `ARCHITECTURE.md` + `DESIGN_DECISIONS.md` | ✅ |
| 10 | Evidencia de 4 ciclos completos (✅❌🤷✏️) | ✅ |

## Decisiones de diseño

Las 5 preguntas clave del checklist están documentadas en detalle en:
- [`agents/support_agent/memory/ARCHITECTURE.md`](agents/support_agent/memory/ARCHITECTURE.md) — justificación técnica, alternativas consideradas, estructura de datos, garantías
- [`agents/support_agent/memory/DESIGN_DECISIONS.md`](agents/support_agent/memory/DESIGN_DECISIONS.md) — las 5 decisiones con razonamiento y cuándo revisitar

Resumen:

1. **¿Regex o LLM?** → Regex puro. Determinista, sin latencia, sin coste de API, suficiente para patrones estructurados de horarios/proveedores/preferencias.
2. **¿JSON KV o Redis/VectorDB?** → JSON con Lock. Brasaland tiene 6 locales, pocas entradas. Redis/VectorDB sería sobredimensionado.
3. **¿Misma conversación o agente separado?** → Misma conversación (evaluate_and_propose → process_decision). Sin estado compartido entre agentes.
4. **¿Consolidación por qué clave?** → (location_id, category). Agrupa entradas relacionadas y permite inyección contextual por local.
5. **¿Chain-of-thought?** → No. Las decisiones se registran con clasificación directa (aceptado/rechazado/editado/ambiguo), sin reasoning oculto.

## Arquitectura

```
memory/
├── __init__.py           # Public API exports
├── schemas.py            # Pydantic models (MemoryEntry, MemoryProposal, MemoryDecision, ConsolidatedMemory, etc.)
├── memory_evaluator.py   # Regex-based evaluation (SensitivityPatterns, PositivePatterns)
├── memory_proposer.py    # Proposal creation, confirmation prompts, response classification, decision recording
├── memory_store.py       # Thread-safe JSON persistence (atomic writes, CRUD, search, auto-expiration)
├── memory_consolidator.py # Grouping engine: (location_id, category) → summary
├── memory_manager.py     # Orchestrator (evaluate_and_propose → process_decision → get_context)
├── ARCHITECTURE.md       # Architecture justification and alternative analysis
└── DESIGN_DECISIONS.md   # 5 design decisions with reasoning
```

## Tests

```bash
$ pytest agents/support_agent/tests/test_memory*.py -v
# 178 passed in 0.48s
```

## Evidencia de funcionamiento

Se ejecutaron 4 ciclos completos demostrando todos los caminos posibles:

| Ciclo | Interacción | Respuesta | Decisión | Entry | Resultado |
|-------|------------|-----------|----------|-------|-----------|
| 1 | "L03 cierra a las 10pm los viernes" | "Sí" | **accepted** | Creado | ✅ Guardado en store |
| 2 | "proveedor de carne pasa los lunes" | "No" | **rejected** | No creado | ❌ Rechazado, decisión registrada |
| 3 | "reporte semanal en PDF" | "quizás" | **rejected** (ambiguous→rejected) | No creado | 🤷→❌ Ambiguo = rechazado |
| 4 | "local abre a las 8am" | "edita, es a las 9am" | **edited** | Creado (corregido) | ✏️ Editado y guardado |

La consolidación agrupó correctamente 2 entries de `L03`/`horarios` en un único resumen.

## Notas

- Los datos de memoria se almacenan en `data/memory/` (configurable via `MEMORY_STORE_DIR`)
- El store es JSON con escritura atómica (`.tmp` + `replace`) — seguro ante cortes
- Las propuestas expiran automáticamente (configurable via `PROPOSAL_EXPIRATION_HOURS`)
- Las decisiones son inmutables — toda decisión queda registrada para auditoría
- El borrado es soft-delete (is_active=False) por defecto
- Soporte bilingüe: español e inglés para prompts y clasificación de respuestas

---

*PR description preparada. Pendiente de autorización para push y creación del PR.*