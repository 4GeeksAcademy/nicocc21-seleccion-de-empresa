# Decisiones de Diseño — Subsistema de Memoria (Hito 8)

> **Propósito:** Responder las 5 preguntas de diseño del checklist del Hito 8,
> justificando cada decisión con el contexto de Brasaland.

---

## Pregunta 1: ¿Por qué el agente usa evaluación determinista (regex) en lugar de un LLM para decidir si algo es memorable?

**Decisión:** El `MemoryEvaluator` usa reglas basadas en expresiones regulares
con sensibilidad a patrones positivos (memorables) y de rechazo (nunca memorizar).

**Por qué:**
1. **Determinismo:** La misma interacción produce siempre la misma evaluación.
   Con un LLM, el mismo texto podría ser memorable en una llamada y no en otra,
   lo que rompe la previsibilidad del sistema.
2. **Latencia cero:** No hay llamada a un modelo externo. La evaluación ocurre
   en microsegundos, no en segundos.
3. **Coste:** Cero tokens por evaluación. Con 14 locales y cientos de interacciones
   diarias, el coste de usar un LLM para cada evaluación sería significativo.
4. **Control explícito:** Las reglas están escritas, visibles y auditables en
   `memory_evaluator.py`. Cualquier stakeholder puede ver exactamente qué
   patrones son memorables y cuáles están prohibidos.

**Trade-off:** Las regex son menos flexibles que un LLM para detectar matices
semánticos. Sin embargo, los hechos que Brasaland necesita recordar son
**estructurados y predecibles** (horarios, proveedores, preferencias), no
conceptos abstractos. Para este dominio, las reglas son suficientes y superiores
en fiabilidad.

---

## Pregunta 2: ¿Por qué se usa un JSON KV store local en lugar de Redis, VectorDB o una base de datos?

**Decisión:** `MemoryStore` con persistencia en archivo JSON bajo `data/memory/`.

**Por qué:** Ver `ARCHITECTURE.md` sección 3 para el análisis completo de
alternativas. En resumen:
- **Volumen bajo-medio:** Cientos de entradas, no millones
- **Sin concurrencia real:** Un solo agente en un solo proceso
- **Audit trail simple:** Un archivo JSON con referencias cruzadas
- **Cero dependencias externas:** No necesita Redis, Qdrant ni PostgreSQL

---

## Pregunta 3: ¿Por qué el agente propone memoria en la misma conversación en lugar de usar un agente separado?

**Decisión:** `evaluate_and_propose()` es una llamada síncrona en el mismo flujo
de la conversación. No hay un segundo agente, ni una segunda llamada al modelo.

**Por qué:** El checklist del Hito 8 es explícito en este punto:
> "No se necesita una segunda llamada al modelo, ni un agente separado, ni una
> arquitectura multi-agente: es el mismo agente con un campo adicional en su salida."

Además, proponer en la misma conversación permite:
1. **Inmediatez:** El usuario responde sobre el contexto caliente
2. **Traza completa:** La propuesta y la decisión están vinculadas a la interacción
   que las originó
3. **Simplicidad:** No hay estado compartido entre agentes, ni colas de mensajes,
   ni orquestación

**Implementación:**
```python
# Flujo: una sola llamada
proposal, prompt = manager.evaluate_and_propose(
    interaction_text=text,
    location_id=location_id,
)
if prompt:
    # Enviar prompt al usuario en el mismo turno de conversación
    await send_to_user(prompt)
```

---

## Pregunta 4: ¿Por qué la consolidación agrupa por (location_id + category) y no por otros criterios?

**Decisión:** `MemoryConsolidator` agrupa entradas activas por el par
`(location_id, category)` y genera un resumen por grupo.

**Por qué:**
1. **Location es el eje primario:** Brasaland tiene 14 locales independientes.
   El horario de L03 (Medellín) no es relevante para L08 (Miami). Separar por
   location evita contaminación contextual.
2. **Category es el eje secundario:** "Proveedores" y "Horarios" son dominios
   distintos incluso dentro del mismo local. Mezclarlos en un solo resumen
   haría la memoria menos útil.
3. **Alternative 1 — Global summary:** Un solo resumen para todos los locales
   perdería la especificidad que el agente necesita ("¿qué sabemos de L03?").
4. **Alternative 2 — Per-entry storage:** Almacenar cada corrección como entrada
   suelta sin agrupar funciona, pero el contexto crece linealmente. Con 14 locales
   y ~20 hechos cada uno, el prompt tendría 280 líneas sueltas. Consolidar reduce
   a ~14 resúmenes por categoría.

**Trade-off:** Dos entradas contradictorias sobre el mismo (location, category)
se pierden en el resumen (se sobrescribe). Esto es aceptable porque la
consolidación refleja el *último estado conocido*. Si se necesita historial,
las entradas individuales permanecen en `entries`.

---

## Pregunta 5: ¿Por qué no hay un paso de "razonamiento" explícito (chain-of-thought) antes de proponer memoria?

**Decisión:** El evaluador usa reglas deterministas, no razonamiento del modelo.

**Por qué:** El razonamiento (CoT, reflexión) tiene sentido cuando la decisión
requiere análisis semántico complejo. En nuestro caso, la pregunta es binaria:
"¿Esto coincide con algún patrón de hechos memorables?".

Un paso de razonamiento añadiría:
1. **Latencia:** Segundos adicionales por llamada al LLM
2. **Token cost:** Cientos de tokens innecesarios
3. **Inconsistencia:** El modelo podría "convencerse a sí mismo" de que algo
   es memorable cuando no debería serlo

Las reglas deterministas son más fiables, predecibles y baratas para este
caso de uso.

**Cuándo añadir razonamiento:** Si en el futuro el agente necesita detectar
hechos memorables implícitos (inferencias no literales), se podría añadir un
paso opcional de LLM como respaldo cuando las reglas no alcanzan el umbral de
confianza. Pero para el MVP, las reglas son suficientes.

---

## Resumen de decisiones

| # | Decisión | Alternativa descartada | Justificación principal |
|---|---|---|---|
| 1 | Evaluación determinista (regex) | LLM para evaluar memoria | Determinismo, latencia cero, coste cero, control explícito |
| 2 | JSON KV store local | Redis / VectorDB / SQLite | Volumen bajo-medio, sin concurrencia real, cero dependencias |
| 3 | Propuesta en misma conversación | Agente separado para memoria | Especificación explícita del Hito 8, inmediatez, simplicidad |
| 4 | Consolidación por (location, category) | Global / per-entry | 14 locales independientes, dominios separados por categoría |
| 5 | Sin chain-of-thought | Razonamiento del modelo | Decisión binaria, coste innecesario, inconsistencia potencial |