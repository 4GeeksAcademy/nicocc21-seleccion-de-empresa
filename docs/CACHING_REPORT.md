# CACHING_REPORT.md — Optimización de caché en Brasaland

> Proyecto: Optimización de rendimiento del monorepo Brasaland (backoffice + API)
> Rama: `feature/caching-optimisation`
> Fecha: 2026-10-14
> Alcance: Backend FastAPI (`services/brasaland_api`) + Frontend Next.js (`uis/backoffice`)

---

## Resumen ejecutivo

Se identificaron tres problemas de rendimiento en el stack:

1. **Endpoint `GET /inventory/products`** ejecutaba 2 agregados SQL (SUM entradas + SUM salidas) en cada llamada a pesar de que el panel de inventario lo consulta continuamente y los datos cambian con poca frecuencia.
2. **Endpoint `GET /inventory/orders`** era el más caro del stack (~70ms): dos `JOIN` + ordenamiento cronológico de 1000+ movimientos, llamado cada vez que se abre el historial.
3. **Frontend**: la página de incidencias importaba estáticamente el formulario y el analizador CSV aunque el usuario no siempre los usa, y la clasificación de stock se recalculaba en cada `render` de la tabla.

Todas las optimizaciones se implementaron con una **caché en memoria con TTL** en backend y **Lazy Loading + `useMemo`** en frontend, priorizando decisiones justificadas antes que cantidad de cambios.

---

## 1. Decisiones en el frontend

### 1.1 Lazy Loading (2 componentes)

#### Componente 1: `IncidentsAnalyzer` — página `/incidencias`
- **Qué se hizo:** se reemplazó el import estático por `dynamic(() => import("./IncidentsAnalyzer"), { ssr: false, loading: skeleton })`.
- **Justificación:**
  - Es una herramienta **secundaria** de análisis CSV ubicada al final de la página: el usuario primero ve el formulario y el listado.
  - Su bundle no aporta nada al *first paint* ni a la interactividad inicial: el usuario solo lo necesita si decide subir un CSV.
  - Queda fuera del primer *paint* y no bloquea la carga del listado de incidencias (que es el contenido principal y hace 2 `fetch` al backend).
- **Beneficio estimado:** el JS del analizador se descarga bajo demanda; reduce el tamaño del bundle inicial de la página (no se re-hidrata un componente que el usuario puede nunca abrir).

#### Componente 2: `IncidentForm` — página `/incidencias`
- **Qué se hizo:** `dynamic(() => import("./IncidentForm"), { ssr: false, loading: skeleton })`.
- **Justificación:**
  - El formulario arranca **cerrado** (estado interno `open = false` en `IncidentForm.tsx`): todo su estado y lógica de validación no se necesita hasta que el usuario pulsa "Registrar incidencia".
  - Diferir su carga evita descargar/evaluar handlers y estado de un formulario que es un camino de uso minoritario frente al listado.
- **Beneficio estimado:** el JavaScript del formulario (validación + envío + estado) solo se pide al servidor cuando el usuario lo va a usar; reduce la hidratación inicial de la página.

> **Nota:** `IncidentList` (el componente principal) **no** se difirió: es el contenido visible primero y hace 2 llamadas de datos. Diferirlo empeoraría la experiencia sin ganancia real.

### 1.2 `useMemo` — página de productos `/inventory/products`

- **Valor memoizado:** `productStatus` — mapa `id → { indicatorClass, label }` obtenido clasificando **todos** los productos con 4 umbrales de stock (`stock_minimo * 0.5`, `stock_minimo`, `> stock_minimo`, `<= 0`).
- **Por qué es no trivial:** en producción real hay **120+ productos**; por cada uno se evalúan 4 condiciones con aritmética de umbral. En el render de la tabla esto se hacía 2 veces por producto (clase + etiqueta) en cada re-render.
- **Array de dependencias:** `[products]` — el cálculo solo depende de la lista de productos obtenida del backend. Correcto: cuando la lista cambia (nuevo fetch) se recalcula; cuando solo cambia el estado local de UI (loading/error) se reutiliza.
- **Beneficio estimado:** evita O(n × umbrales) de trabajo por cada render de la tabla; el re-render por cambios de `loading`/`error` ya no re-clasifica los 120 productos.

---

## 2. Decisiones en el backend

### 2.1 Inventario de endpoints y evaluación

| Endpoint | Coste | Frecuencia estimada | Cambios de datos | Cacheable |
|---|---|---|---|---|
| `GET /inventory/products` | ~16ms (2 agregados SQL) | Alta (panel lo consulta siempre) | Baja (insumos + movimientos) | ✅ **Sí** |
| `GET /inventory/orders` | ~70ms (2 JOIN + sort) | Media (historial) | Baja (solo al crear movimientos) | ✅ **Sí** |
| `GET /inventory/products/{id}` | ~9ms (agregado por ítem) | Baja (ficha individual) | Baja | ✅ Sí (TTL corto) |
| `GET /incidents/summary` | ~7ms (4 agregaciones) | Alta (se llama con el listado) | Media (altas/estados) | ✅ **Sí** |
| `GET /incidents` | ~8ms (filtros + listado) | Media-Alta | Media | ✅ Sí (TTL corto) |
| `GET /incidents/{id}` | ~3ms (TinyDB lookup) | Baja | Media | ⛔ No (muy barato) |
| `GET /suppliers` | ~4ms (TinyDB) | Media | Media | ⛔ No (auth + barato) |
| `GET /profiles/me` | ~4ms | Alta por sesión | Alta por usuario | ⛔ **No** (dato personal) |

Los dos endpoints que cumplen **coste + frecuencia + estabilidad** de forma clara son `GET /inventory/products` y `GET /inventory/orders`; `GET /incidents/summary` es el tercero sólido porque combina alta frecuencia y 4 agregaciones.

### 2.2 Endpoints cacheados y TTL

| Endpoint | Coste real | TTL | Estrategia de invalidación |
|---|---|---|---|
| `GET /inventory/products` | ~58ms (frío) → **~2ms** (caché) | 60s | `cache.invalidate("inventory")` en POST product / orders |
| `GET /inventory/orders` | ~104ms (frío) → **~8ms** (caché) | 60s | `cache.invalidate("inventory")` en POST product / orders |
| `GET /inventory/products/{id}` | ~12ms (frío) → **~2ms** (caché) | 60s | Ídem (mismo namespace `inventory`) |
| `GET /incidents/summary` | ~6ms (frío) → **~2ms** (caché) | 30s | `cache.invalidate("incidents")` en POST/PATCH |
| `GET /incidents` | ~12ms (frío) → **~4ms** (caché) | 15s | Ídem (mismo namespace `incidents`) |

**Mecanismo:** módulo `services/brasaland_api/cache.py` — diccionario en memoria con expiración por TTL (`time.monotonic()`), expuesto como decorador `@cached(ttl_seconds, skip_args, prefix)` y como instancia única `cache`. Sin dependencias externas (no Redis), lo que respeta el stack "academia" single-process.

### 2.3 Invalidación de caché implementada (escrituras limpian)

- **Inventario (`namespace "inventory"`):**
  - `POST /inventory/products` → invalida tras crear insumo (afecta listado y stock).
  - `POST /inventory/orders/inbound` → invalida (cambia stock derivado + historial).
  - `POST /inventory/orders/outbound` → invalida (idem).
- **Incidencias (`namespace "incidents"`):**
  - `POST /incidents` → invalida (cambia listados + summary).
  - `PATCH /incidents/{id}` → invalida (cambia filtros + summary).
  - `PATCH /incidents/{id}/status` → invalida (cambia summary por estado).

Cada escritura llama `cache.invalidate(namespace)` tras el commit, garantizando que la siguiente lectura **recalcule**. Verificado de punta a punta: tras un `POST /inventory/orders/inbound`, el siguiente `GET /inventory/products` volvió de ~3ms a ~13ms (miss = recálculo), y tras `POST /incidents` el siguiente `GET /incidents/summary` volvió de ~2ms a ~6ms.

---

## 3. Intercambios reconocidos (frescura vs. rendimiento)

### Caso 1: `GET /incidents/summary` → TTL 30s

El resumen (totales por estado/prioridad) es lo primero que ve el usuario al entrar a `/incidencias`. Un TTL **de 30s** significa que si un compañero cambia el estado de una incidencia, el contador puede tardar hasta 30 segundos en reflejarlo.

**Por qué es aceptable:** el summary no es un dato transaccional crítico — es un KPI de monitoreo. Una desactualización de ≤30s en un contador agregado no produce decisiones incorrectas; en cambio, permitir la caché evita repetir 4 agregaciones sobre ~500 documentos en cada visita. El TTL corto (vs. 60s de inventario) refleja que aquí hay más movimiento.

### Caso 2: `GET /inventory/products` → TTL 60s + invalidación manual

El stock derivado debería reflejar movimientos casi en tiempo real para decisiones de compra. Para no sacrificar frescura, **no** se confió solo en el TTL: cada escritura (entrada/salida/crear) invalida el namespace al instante, de modo que la próxima lectura tras un movimiento es siempre fresca. El TTL de 60s actúa como **red de seguridad** para el caso en que un movimiento se realice por fuera de la API (inserción directa en BD, seed) y no dispare invalidación. Así se obtiene frescura *en el flujo normal* y estándar de frescura *en los flujos excepcionales*.

---

## 4. Qué no se cacheó y por qué

### 4.1 `GET /profiles/me` — NO cacheado (dato personal)

Es el ejemplo de la advertencia del enunciado: devuelve datos **personalizados por sesión**. Cualquier clave de caché compartida entre usuarios filtraría el perfil de un usuario a otro — una fuga de datos, no una mejora. Se descartó deliberadamente.

### 4.2 `GET /suppliers` — NO cacheado

Requiere autenticación JWT y tiene coste de ~4ms (lectura TinyDB, sin agregaciones). El coste no justifica el riesgo de complejizar la clave por usuario (habría que acotar `current_user.id` en la clave, y las cabeceras/CSRF cambian por sesión). **Coste bajo + complejidad de clave por usuario** = no vale la pena.

### 4.3 `GET /incidents/{id}` — NO cacheado

Lookup directo por ID en TinyDB de ~3ms. La ganancia de cachear un acceso por clave primaria sería despreciable y añadiría complejidad de invalidación por ítem. Los endpoints cacheados son los que tienen **trabajo de agregación o join**, donde la ganancia es real.

### 4.4 Frontend — `IncidentList` NO diferido

Aunque es candidato técnico de lazy load, es el **contenido principal** de la página y dispara las 2 llamadas de datos. Diferirlo solo retrasaría lo que el usuario espera ver primero; el coste de su bundle ya lo justifica cargar de forma eager. Esta decisión contrasta con `IncidentForm`/`IncidentsAnalyzer`, que sí se difirieron por ser flujos secundarios.

---

## 5. Limitaciones y trabajo futuro

- **Caché en memoria es single-process:** con múltiples workers de uvicorn o réplicas, cada worker tendría su copia y la invalidación no se propagaría. Para producción multi-worker, migrar a **Redis** manteniendo el mismo contrato del decorador (`@cached(...)`) y la misma lógica de invalidación por namespace.
- **El cache no es thread-safe por diseño:** suficiente para el servidor single-thread de desarrollo/academia. Un servidor de producción debería usar un lock o Redis.
- **Lazy loading con `ssr: false`:** los detalles de contenido diferido no se sirven en el HTML inicial, lo que es correcto para componentes 100% clientes como estos, pero debe tenerse en cuenta para SEO en la web pública (no aplica al backoffice interno).