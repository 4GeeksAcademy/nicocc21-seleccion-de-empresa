# Decisiones de Diseño

## 1. TypeScript estricto, sin frameworks innecesarios

**Decisión:** La lógica de negocio vive en TypeScript puro, sin dependencias de frameworks.

**Por qué:** Permite reutilizar la misma lógica en cualquier contexto (consola, web, API, agente). Las funciones son puras y testables.

**Impacto:** `src/hito2/` no depende de Express, Next.js ni ningún runtime. Solo de tipos y funciones nativas.

## 2. Datos simulados pero representativos

**Decisión:** Mientras no haya integración con POS/facturación real, se simula todo el flujo de datos manteniendo el contexto real de 14 sedes.

**Por qué:** Permite desarrollar y demostrar funcionalidad completa sin dependencias externas. Los datos son lo suficientemente ricos para probar filtros, alertas y reportes.

**Impacto:** `sample-data.ts` genera 140 movimientos financieros (10 por local) y 5 insumos representativos.

## 3. Dos UIs separadas, una lógica compartida

**Decisión:** `uis/website/` (público) y `uis/backoffice/` (interno) son apps independientes que comparten la misma lógica de negocio.

**Por qué:** Audiencias diferentes, permisos diferentes, niveles de detalle diferentes. Pero los cálculos subyacentes son los mismos.

**Impacto:** La lógica de `src/hito2/` se importa en ambas apps. No se duplica.

## 4. API dentro de `/services/`, no en la raíz

**Decisión:** Cada servicio backend vive en su propia subcarpeta dentro de `services/`.

**Por qué:** El monorepo puede alojar múltiples servicios (admin-api, data-processor, etc.). Cada uno documentado y aislado.

**Impacto:** Cuando creemos la API, será `services/brasaland-api/` (o similar), no un archivo suelto.

## 5. `.agents/` para configuración, `/agents/` para producto

**Decisión:** El directorio `.agents/` (oculto) configura cómo trabaja el agente de código. `/agents/` (visible) contiene agentes de producto que construimos.

**Por qué:** Confusión frecuente en monorepos. Separar claramente evita que el agente de código modifique agentes de producto o viceversa.

**Impacto:** Las reglas de `.agents/rules/` se leen automáticamente. Los agentes en `/agents/` son código de aplicación.

## 6. Memory bank en español

**Decisión:** Todo el contexto en `memory-bank/` está escrito en español.

**Por qué:** El contexto de negocio de Brasaland está en español. Los stakeholders hablan español. Las instrucciones técnicas pueden mezclar términos en inglés (convención de código) pero la documentación es en español.

**Impacto:** Fácil de mantener por el equipo. Los agentes de código modernos manejan español sin problema.

## 7. Skill `scaffold-next-app` como primera skill

**Decisión:** La skill reutilizable del Hito 3 es `scaffold-next-app`.

**Por qué:** Crear apps Next.js dentro del monorepo es una tarea recurrente (website, backoffice, portales futuros). Estandarizar cómo se hace evita inconsistencias.

**Impacto:** Cada nueva app Next.js se crea siguiendo el mismo proceso verificable.

## 8. Stock de inventario: agregación SQL indexada, no columna cacheada

**Decisión:** El stock (`current_stock`) nunca se guarda como columna; se calcula con `SUM(entries) - SUM(exits)` vía agregación SQL, con índice (`index=True`) en `ingredient_id` de `IngredientEntry` e `IngredientExit`.

**Por qué:** Feedback del tutor en el hito de inventario: recorrer todo el historial de movimientos en Python no escala. La alternativa (columna de stock cacheada) rompe la garantía de "fuente de verdad única" y agrega riesgo de desincronización.

**Impacto:** `_stock_map_for_all` resuelve el stock de todos los insumos en 2 queries agregadas (sin N+1), apoyadas en el índice de `ingredient_id`. Si el volumen de movimientos crece mucho más, la siguiente escala sería una vista materializada o snapshot periódico — no una columna editable.

## 9. `node_modules` fuera del control de versiones

**Decisión:** Se destrackearon 208 archivos de `node_modules` que habían quedado en el índice de git desde antes de que existiera la regla en `.gitignore` raíz.

**Por qué:** Feedback del tutor: un PR incluía `node_modules/.package-lock.json`. Agregar la regla al `.gitignore` no basta si el archivo ya estaba trackeado.

**Impacto:** `git rm -r --cached node_modules` limpia el índice sin borrar los paquetes en disco. Los `.gitignore` de cada app en `uis/*` y el raíz ya cubren `node_modules`, así que no debería volver a colarse.
