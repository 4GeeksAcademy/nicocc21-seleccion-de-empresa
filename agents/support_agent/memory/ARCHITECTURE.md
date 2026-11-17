# Arquitectura del Subsistema de Memoria — Support Agent Brasaland

> **Propósito:** Documentar por qué se eligió un backend JSON clave-valor como store
> de memoria episódica para el Support Agent de Brasaland, y por qué no se usaron
> Redis, VectorDB, RAG collections u otras alternativas.

---

## 1. Contexto: ¿Qué necesita recordar el Support Agent?

El Support Agent de Brasaland gestiona incidencias de clientes (quejas, solicitudes,
fallos operativos). Durante las conversaciones con el equipo de soporte, surgen
hechos episódicos que conviene recordar en interacciones futuras:

- **Correcciones operativas:** "El local L03 cierra a las 10pm los viernes"
- **Datos de proveedores:** "El proveedor de carne pasa los lunes"
- **Incidentes conocidos:** "El POS de L07 tiene un error conocido al procesar tarjetas"
- **Preferencias de comunicación:** "Mándame el reporte semanal en PDF"
- **Información sensible:** Nóminas, datos personales de clientes → **NUNCA recordar**

Son hechos concretos, de volumen bajo-medio (~decenas por local, cientos total),
con una estructura simple: `{location, categoría, contenido, idioma}`.

## 2. Backend elegido: JSON Key-Value Store local

### ¿Qué es?

Un archivo JSON (`data/memory/memory_store.json`) con estructura indexada por ID,
gestionado mediante `MemoryStore` con acceso thread-safe vía `Lock` y escritura
atómica mediante `write-to-tmp + replace`.

```json
{
  "entries": { "mem_abc123": { "location_id": "L03", "category": "horarios", ... } },
  "proposals": { "prop_def456": { ... } },
  "decisions": { "dec_ghi789": { ... } },
  "consolidations": { "con_jkl012": { ... } },
  "last_consolidated": "2026-11-15T..."
}
```

### ¿Por qué encaja con Brasaland?

| Característica de Brasaland | Por qué JSON KV es la opción correcta |
|---|---|
| **14 locales activos** | El volumen es bajo: ~10-30 hechos memorables por local. Un archivo JSON de 1-2 MB basta. No necesita cluster Redis ni escalado horizontal. |
| **Agente conversacional (no web)** | El agente se ejecuta en CLI o como biblioteca Python. No hay múltiples réplicas compitiendo por la misma memoria — un Lock thread-safe basta. |
| **Episódico, no semántico** | La memoria es factual ("el proveedor X pasa los lunes"), no semántica ("¿qué es un proveedor?"). No necesita embeddings ni búsqueda vectorial. |
| **Sin shared-nothing** | El agente opera en un solo proceso. No hay microservicios que deban compartir memoria. La persistencia es local. |
| **Audit trail obligatorio** | JSON permite una estructura de datos no normalizada: podemos almacenar proposals, decisions y entries en el mismo archivo, con referencias cruzadas para trazabilidad. |
| **Simplicidad operativa** | El equipo de Brasaland no necesita operar un Redis ni una VectorDB. Un archivo JSON + backup periódico es trivial. |

## 3. ¿Por qué NO otras alternativas?

### ❌ Redis

**Razón:** Redis es excelente para caching y datos efímeros de alta velocidad,
pero Brasaland necesita **memoria persistente con audit trail** que sobreviva
reinicios. Redis sin AOF/RDB no persiste; con persistencia habilitada, añade
complejidad operativa (configuración, backup, monitoreo) para un volumen de
datos que cabe en 500 KB.

Además, Redis no tiene un modelo de datos nativo para el triplete
`proposal → decision → entry` con referencias cruzadas. Habría que
implementar esa relación en la capa de aplicación, duplicando lógica que
JSON resuelve de forma natural con un dict anidado.

### ❌ VectorDB (Qdrant, Chroma, Pinecone)

**Razón:** Las VectorDB están diseñadas para **búsqueda semántica** sobre texto
no estructurado. La memoria episódica del Support Agent es **texto estructurado**
con categorías conocidas (`horarios`, `proveedores`, `preferencias`, etc.).
No necesitamos "encontrar el concepto más similar", necesitamos:
- Recuperar todo lo que sabemos sobre el local L03 en categoría `horarios`
- Saber si ya hay una entrada sobre "proveedor de carne"

Las VectorDB añaden coste de embedding (latencia, tokens, modelo) y complejidad
operativa para un beneficio nulo en este caso de uso.

### ❌ RAG collections (knowledge base)

**Razón (obligatorio por especificación):** Mezclar hechos episódicos/aprobados
con documentos curados (como `company-knowledge-base/`) rompe los evals de
retrieval y los controles de poison. El RAG sigue siendo herramienta de solo
lectura para documentación corporativa.

Nuestra memoria usa **`data/memory/`**, que es un store completamente aparte.

### ❌ SQLite / Base de datos relacional

**Razón:** SQLite sería viable, pero añade una dependencia binaria y un esquema
que hay que migrar. El volumen de datos no lo justifica: menos de 1000 entradas,
sin joins complejos, sin consultas ad-hoc. Un JSON indexado en memoria con
escritura atómica es más simple y cumple el mismo propósito.

### ❌ Multi-agente / agente separado para memoria

**Razón:** El checklist del Hito 8 es explícito: "No se necesita una segunda
llamada al modelo, ni un agente separado, ni una arquitectura multi-agente."
La evaluación de memoria se hace con reglas deterministas (regex), no con LLM.

## 4. Estructura de datos

```
data/memory/
└── memory_store.json          # Archivo único: entradas + proposals + decisions + consolidations
```

### Modelo de datos (Pydantic)

```
MemoryStoreData
├── entries: dict[str, MemoryEntry]        # Hechos aprobados
├── proposals: dict[str, MemoryProposal]   # Propuestas pendientes de decisión
├── decisions: dict[str, MemoryDecision]   # Audit trail inmutable
├── consolidations: dict[str, ConsolidatedMemory]  # Resúmenes agrupados
└── last_consolidated: datetime | None
```

### Flujo de datos

```
Usuario: "El L03 cierra a las 10pm"
    │
    ▼
MemoryEvaluator.evaluate()
    │ Regex match: SCHEDULE_CORRECTION
    │ confidence: 0.85 → debería proponer
    ▼
MemoryProposer.create_proposal()
    │ ProposalStatus.PENDING
    │ expires_at: +30 minutos
    ▼
MemoryStore.save_proposal()
    │ Persiste proposal en memory_store.json
    ▼
MemoryProposer.format_confirmation_prompt()
    │ "¿Quieres que recuerde esto?"
    ▼
Usuario: "Sí"
    │
    ▼
MemoryProposer.classify_response()
    │ DecisionValue.ACCEPTED
    │ confidence: 0.82
    ▼
MemoryProposer.record_decision()
    │ MemoryDecision almacenado SIEMPRE
    ▼
MemoryStore.save_entry()
    │ MemoryEntry persistido
    ▼
MemoryConsolidator.consolidate_location("L03")
    │ Agrupa por (L03, horarios) → resumen
    ▼
Próxima iteración:
    MemoryManager.get_context("L03")
    │ → "[horarios] El local L03 cierra a las 10pm los viernes"
```

## 5. Garantías

| Propiedad | Cómo se cumple |
|---|---|
| **Persistencia** | Escritura atómica: `json.dump(tmp) → tmp.replace(real)` |
| **Thread-safety** | `threading.Lock` en todas las operaciones de escritura |
| **Audit trail** | `MemoryDecision` se almacena **siempre**, incluso si el usuario rechaza |
| **No pérdida de datos** | Las propuestas pendientes se guardan en disco inmediatamente |
| **Expiración** | Las propuestas tienen TTL configurable (default 30 min) |
| **Soft-delete** | Las entradas usan `is_active=False` en lugar de borrado físico |
| **Atomicidad** | O todo se guarda o nada: si `_save()` falla, el estado en memoria se conserva |

## 6. Limitaciones y cuándo migrar

Esta arquitectura es adecuada para el **MVP y producción temprana** (cientos de
entradas, un solo agente). Las señales para migrar serían:

1. **Volumen > 10K entradas** → La carga/descarga del JSON completo empieza a ser lenta
2. **Múltiples agentes concurrentes** → Se necesita un backend compartido (Redis, PostgreSQL)
3. **Búsqueda por texto completo** → Añadir FTS5 (SQLite) o Elasticsearch
4. **Embeddings para matching semántico** → Migrar a VectorDB solo cuando el volumen
   de hechos no estructurados lo justifique

En cada caso, la capa de abstracción (`MemoryStore`) permite cambiar el backend
sin modificar el resto del sistema.