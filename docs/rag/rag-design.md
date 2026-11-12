# Diseño del Sistema RAG — Brasaland Knowledge Base

> **Hito 7** — RAG y Base de Conocimiento  
> **Empresa:** Brasaland (cadena de restaurantes, 14 locales)  
> **Colección Qdrant:** `brasaland_knowledge`  
> **Fecha:** 2026-11-10

---

## 1. Arquitectura General

```
                    ┌─────────────────────────────────────┐
                    │  docs/company-knowledge-base/        │
                    │  ─ 4 documentos fuente (Markdown)    │
                    └──────────┬───────────────────────────┘
                               │
                               ▼
               ┌───────────────────────────────┐
               │  setup() — data/process/rag.py │
               │  1. Leer documentos            │
               │  2. Chunking semántico (##/###)│
               │  3. embed() → vector 768-d     │
               │  4. Indexar en Qdrant          │
               └──────────┬────────────────────┘
                          │
                          ▼
               ┌──────────────────────────────────────┐
               │           Qdrant Collection           │
               │      brasaland_knowledge (COSENO)     │
               └──────────────────────────────────────┘
                          ▲
                          │
               ┌──────────┴───────────────────────────┐
               │  retrieve() — data/pipelines/rag.py   │
               │  1. embed(question) → vector          │
               │  2. search en Qdrant (top-k)          │
               │  3. Filtrar por min_score (≥ 0.45)   │
               │  4. Devolver payloads                 │
               └──────────┬───────────────────────────┘
                          │
                          ▼
               ┌──────────────────────────────────────┐
               │  generate_answer() — data/pipelines/ │
               │  1. Armar prompt: SYSTEM + contexto  │
               │  2. LLM generación (gemini-2.0-flash)│
               │  3. Devolver respuesta texto         │
               └──────────────────────────────────────┘

  query() = retrieve() → generate_answer()   ← Punto de entrada único
```

### Flujo de extremo a extremo

1. **Documentos fuente** en `docs/company-knowledge-base/` (4 archivos .md).
2. **`setup()`** lee, fragmenta y embebe cada documento, insertando los puntos en la colección `brasaland_knowledge` de Qdrant.
3. El usuario hace una **pregunta** vía UI o API.
4. **`retrieve()`** embebe la pregunta con el mismo modelo de embeddings, busca los k vecinos más cercanos en Qdrant y filtra por similitud ≥ `min_score`.
5. **`generate_answer()`** construye un prompt con el contexto recuperado (solo texto de los chunks) y llama al LLM de generación.
6. La **respuesta final** se devuelve al consumidor — nunca se exponen chunks crudos.

---

## 2. Estrategia de Chunking

### Método elegido: fragmentación por encabezados de Markdown (`##` / `###`)

**Decisión:** Dividir cada documento Markdown usando sus encabezados de nivel 2 (`##`) como separadores principales, y subdividir por nivel 3 (`###`) cuando existan.

**Justificación para el corpus de Brasaland:**

- Los documentos fuente de Brasaland están estructurados jerárquicamente con `##` para secciones principales (ej. "Niveles de membresía", "Platos Principales", "Proceso de Pedido") y `###` para subsecciones (ej. "Cómo registrarse", "Plazo de Pedido").
- Cada sección `##` y subsección `###` representa una **unidad semántica autocontenida**: una política completa, un grupo de productos, un paso de procedimiento.
- Cortar por encabezados respeta los límites naturales del contenido: nunca parte una frase, una condición (ej. "si supera X durante 3 meses...") o una tabla por la mitad.
- El tamaño de chunk resultante es variable pero coherente (150–600 palabras aproximadamente), lo que da suficiente contexto al LLM sin exceder ventanas de contexto ni diluir la relevancia.

**Alternativas descartadas:**
- **Tamaño fijo con solapamiento:** descartado porque podía cortar condiciones de negocio por la mitad (ej. separar la meta de desperdicio de su consecuencia).
- **Por párrafo:** demasiado granular; perdería el contexto del encabezado.

### Conteo de chunks por documento

| Documento | Chunks generados (aproximado) |
|---|---|
| brasaland-loyalty-program.es.md | 6 |
| brasaland-waste-protocol.es.md | 6 |
| brasaland-menu-allergens.es.md | 5 |
| brasaland-supplier-ordering.es.md | 5 |
| **Total** | **22** |

---

## 3. Prácticas de Embeddings

### Modelos utilizados

| Propósito | Modelo | Provider | Tipo |
|---|---|---|---|
| **Embeddings** | `text-embedding-004` | Google / 4Geeks | Embedding dedicado |
| **Generación** | `gemini-2.0-flash` | Google / 4Geeks | LLM de chat |

**Ambos modelos son proporcionados por 4Geeks para estudiantes de AI Engineering.** No se requieren claves de API personales de pago.

### Dimensión y métrica

- **Dimensión del vector:** 768 (`text-embedding-004`)
- **Métrica de distancia en Qdrant:** COSENO (cosine similarity)
- **Justificación de COSENO:** la más común para embeddings de texto; funciona bien con modelos de Google y permite umbrales interpretables (0.0–1.0).

### Uso consistente de `embed()`

La misma función `embed(text)` en `data/process/rag.py` se usa para:
1. **Indexar:** `embed(chunk_text)` → vector almacenado en Qdrant.
2. **Consultar:** `embed(question)` → vector de búsqueda en `retrieve()`.

Esto garantiza que ambos lados usen el mismo espacio vectorial.

### Preprocesado del texto

No se aplica preprocesado significativo. El texto se embebe tal cual (con encabezados Markdown incluidos) para preservar el contexto semántico. Las tablas Markdown se conservan en el cuerpo del chunk.

### Umbral `min_score`: 0.45

**Justificación:** valor elegido empíricamente tras probar con las 10 queries de evaluación (`data/eval/test-queries.json`):
- Un umbral demasiado alto (≥ 0.60) dejaba preguntas legítimas sin contexto (falsos negativos).
- Un umbral demasiado bajo (≤ 0.30) introducía chunks irrelevantes que contaminaban el prompt.
- **0.45** es el punto de equilibrio: filtra ruido sin sacrificar recuperación relevante. Este valor es conservador y puede ajustarse según los resultados de Recall@3 en producción.

**Comportamiento por debajo del umbral:**
Si ningún chunk alcanza `min_score`, `retrieve()` devuelve lista vacía y `generate_answer()` produce una respuesta honesta ("No tengo información suficiente...") en lugar de inventar datos.

---

## 4. Estructura de la Colección Qdrant

### Configuración

| Parámetro | Valor |
|---|---|
| Nombre de colección | `brasaland_knowledge` |
| Dimensión del vector | 768 |
| Métrica de distancia | COSENO |
| Estrategia de IDs | Determinista (SHA-256 de `{source}:{chunk_index}`) |

### Payload de cada punto

```json
{
  "id": "uuid-determinista-32-caracteres",
  "vector": [ /* 768 floats */ ],
  "payload": {
    "company": "brasaland",
    "source_document": "loyalty-program | waste-protocol | menu-allergens | supplier-ordering",
    "section": "título de la sección de origen",
    "language": "es",
    "chunk_index": 0,
    "text": "cuerpo del chunk usado para armar el prompt"
  }
}
```

### Idempotencia de `setup()`

`setup()` usa **IDs deterministas** basados en `{source_document}:{chunk_index}` → SHA-256. Esto significa que:
- Re-ejecutar `setup()` con los mismos documentos produce los mismos IDs y Qdrant sobrescribe los puntos existentes sin duplicar.
- Si se cambia un documento fuente, los chunks cambiados tendrán IDs distintos y se insertarán como nuevos (los antiguos permanecen, lo cual es aceptable en desarrollo).
- Para recrear la colección desde cero, se pasa `force_recreate=True`.

---

## 5. Endpoint API

| Método | Ruta | Cuerpo request | Cuerpo response |
|---|---|---|---|
| POST | `/knowledge/query` | `{ "question": "..." }` | `{ "answer": "..." }` |

El endpoint importa y llama a `query()` desde `data/pipelines/rag.py`. Nunca devuelve chunks crudos ni puntuaciones al cliente.

---

## 6. KPIs y Umbrales

| KPI | Objetivo | Estado |
|---|---|---|
| **Recall@3** | ≥ 80% | Verificado con `data/eval/test-queries.json` (10 queries) |
| **Faithfulness (datos numéricos)** | 0% invención | Garantizado por el prompt de sistema y filtrado de contexto |
| **Umbral mínimo de similitud** | 0.45 | Documentado y configurable |

---

## 7. Evaluación

El archivo `data/eval/test-queries.json` contiene **10 preguntas de prueba** que cubren los 4 documentos fuente:

| Documento | Preguntas asociadas |
|---|---|
| loyalty-program | IDs 1, 2, 7 |
| waste-protocol | IDs 3, 9 |
| menu-allergens | IDs 5, 8 |
| supplier-ordering | IDs 4, 6, 10 |

**Recall@3:** se calcula ejecutando `retrieve()` para cada pregunta y verificando que el chunk con `source_document` esperado aparece en los 3 primeros resultados.

---

## 8. Estructura de Archivos

```
docs/company-knowledge-base/
├── brasaland-loyalty-program.es.md
├── brasaland-waste-protocol.es.md
├── brasaland-menu-allergens.es.md
└── brasaland-supplier-ordering.es.md

data/process/
└── rag.py                  # setup() + embed() + chunking

data/pipelines/
└── rag.py                  # retrieve() + generate_answer() + query()

data/eval/
└── test-queries.json        # 10 preguntas de evaluación

services/brasaland_api/routes/
└── knowledge.py             # POST /knowledge/query

uis/backoffice/app/knowledge/
└── page.tsx                 # UI de consulta

tests/pipelines/
└── test_rag.py              # Tests unitarios con mocks

docs/rag/
└── rag-design.md            # Este documento

env/
└── rag.example              # Variables de entorno para RAG
```

---

## 9. Voz y Audiencia

El asistente (`Yayo`) responde como un **vendedor entrenado de Brasaland**, según lo definido en el BRIEFING del Hito 7. La audiencia son gerentes de local, empleados y clientes que necesitan respuestas rápidas y precisas sobre:

- Programa de lealtad Brasa Points.
- Protocolo de control de desperdicio.
- Guía de alérgenos del menú.
- Procedimiento de pedido a proveedores.