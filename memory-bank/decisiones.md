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
