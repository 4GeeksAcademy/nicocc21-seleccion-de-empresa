# AGENTS.md — Protocolo del Agente de Código

> Este archivo define cómo opera cualquier agente de programación en este repositorio.
> Es obligatorio leerlo antes de empezar a trabajar.

---

## 1. Antes de empezar (lectura obligatoria)

Antes de escribir cualquier línea de código, el agente DEBE leer:

1. `memory-bank/projectbrief.md` — Contexto de negocio de Brasaland.
2. `memory-bank/techContext.md` — Decisiones técnicas y convenciones.
3. `memory-bank/progress.md` — Qué ya existe y qué está pendiente.
4. `memory-bank/decisiones.md` — Por qué se tomaron ciertas decisiones.
5. `CONTEXT.md` — Briefing original del proyecto.

Si alguno de estos archivos no existe o está desactualizado, **detenerse y reportarlo** antes de continuar.

---

## 2. Flujo de trabajo obligatorio

Para CADA tarea, el agente debe seguir este orden:

### Paso 1: Entender
- Leer la tarea completa.
- Identificar qué archivos se van a crear o modificar.
- Verificar que la tarea no rompa funcionalidad existente.

### Paso 2: Planificar
- Listar los archivos a tocar (crear, modificar, eliminar).
- Identificar dependencias entre cambios.
- Si hay riesgo de romper algo, **preguntar antes de actuar**.

### Paso 3: Ejecutar
- Implementar los cambios.
- Seguir las convenciones del repositorio (ver abajo).
- No introducir dependencias externas sin justificación.

### Paso 4: Verificar
- Ejecutar `npm run typecheck` y asegurar que pase sin errores.
- Verificar que no se rompió ninguna funcionalidad existente.
- Revisar que los archivos creados sigan la estructura del monorepo.

### Paso 5: Entregar
- Hacer commits con mensajes descriptivos en español.
- Formato: `tipo(alcance): descripción corta`.
  - Tipos: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`.
  - Ejemplo: `feat(uis): crear app backoffice con panel de inventario`.
- Si el cambio es grande, hacer un PR en vez de commit directo.

---

## 3. Convenciones del repositorio

### Código
- **TypeScript estricto** — `strict: true` en tsconfig. No usar `any`.
- **Nomenclatura:** `camelCase` para variables/funciones, `PascalCase` para tipos/interfaces.
- **Funciones puras** — La lógica de negocio no tiene side effects ni I/O directo.
- **Tipos centralizados** — Los tipos viven en `src/hito2/types.ts`. No duplicar definiciones.

### Estructura
- **No crear archivos sueltos en la raíz** — Todo va en su carpeta correspondiente.
- **No modificar `template/`** — Esas son plantillas de referencia, no código activo.
- **No tocar `node_modules/`** — Las dependencias se gestionan con `npm install`.
- **Cada app en `uis/` tiene su propio `package.json`** — No comparten dependencias directamente.

### Datos
- **No hardcodear datos de ejemplo** — Usar los archivos de `src/hito2/sample-data.ts` o crear nuevos en `data/`.
- **Los IDs de locales siguen el formato `L01`-`L14`** — No cambiar el esquema existente.

---

## 4. Cuándo detenerse y preguntar

El agente DEBE detenerse y pedir confirmación cuando:

- La tarea implica modificar archivos en `src/hito2/` que ya tienen funcionalidad probada.
- Hay que instalar una dependencia nueva que no está en `package.json`.
- La estructura de carpetas propuesta no existe en el monorepo.
- No está seguro de si un cambio afecta la funcionalidad existente.
- La tarea no está clara o tiene ambigüedades.

**Nunca asumir. Preguntar siempre cuando haya duda.**

---

## 5. Reglas de seguridad

- No exponer datos sensibles (credenciales, tokens, API keys) en código o commits.
- No ejecutar comandos que modifiquen el sistema fuera del proyecto.
- No eliminar archivos sin confirmación explícita del usuario.
- No modificar `.git/` ni configuración de git.

---

## 6. Archivos protegidos

Los siguientes archivos NO deben ser modificados sin autorización explícita:

- `CONTEXT.md` — Solo se actualiza cuando cambia el contexto de la empresa.
- `memory-bank/` — Se actualiza cuando hay decisiones nuevas, no en cada commit.
- `template/` — Plantillas de referencia, no código activo.
- `package.json` raíz — Solo se modifica para agregar scripts o dependencias globales.
- `tsconfig.json` raíz — Configuración compartida del proyecto.

---

## 7. Nota sobre carpetas

| Carpeta | Propósito | ¿El agente la modifica? |
|---------|-----------|--------------------------|
| `.agents/` | Configuración del agente de código | Sí, cuando se actualizan reglas/skills |
| `memory-bank/` | Contexto persistente del proyecto | Sí, cuando hay decisiones nuevas |
| `src/` | Lógica de negocio | Sí, con precaución |
| `uis/` | Apps de interfaz | Sí, creando/modificando apps |
| `services/` | APIs y workers | Sí, creando servicios |
| `template/` | Plantillas de referencia | **No** |
| `data/` | Datos raw y pipelines | Sí, para datos nuevos |
| `web/` | Web pública estática | Solo si se mejora el HTML existente |
