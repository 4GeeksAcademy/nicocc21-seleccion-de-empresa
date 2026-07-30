# Regla: Convenciones del Monorepo Brasaland

**Alcance:** Siempre activa. Aplica a TODO código escrito en este repositorio.

---

## Objetivo

Asegurar que cualquier cambio respete la estructura, los tipos y las convenciones ya establecidas en el monorepo, evitando romper funcionalidad existente.

---

## Reglas

### 1. Tipos
- Todo tipo nuevo se agrega en `src/hito2/types.ts` (o en el archivo de tipos de la app correspondiente).
- No duplicar definiciones de tipos entre carpetas.
- Usar `interface` para objetos con propiedades, `type` para uniones y alias.
- No usar `any` bajo ninguna circunstancia.

### 2. Funciones de negocio
- Las funciones en `src/hito2/` deben ser **puras** (sin side effects, sin I/O directo).
- No importar módulos de filesystem, red o bases de datos en la capa de lógica de negocio.
- Cada función debe tener un nombre descriptivo en español que indique qué calcula.

### 3. Estructura de carpetas
- No crear archivos sueltos en la raíz del proyecto.
- Cada app en `uis/` tiene su propio `package.json` y configuración.
- Los servicios van en `services/<nombre-del-servicio>/`.
- Los datos van en `data/` o en `src/hito2/sample-data.ts`.

### 4. Imports
- Usar imports relativos dentro de la misma app (`./types`, `../collections`).
- Para importar lógica de negocio desde otra app, usar la ruta absoluta del monorepo:
  ```typescript
  import { generarReporteFinancieroPorLocal } from "../../../../src/hito2/aggregations";
  ```
- No copiar código de un archivo a otro; siempre importar desde la fuente original.

### 5. Nomenclatura
- Variables y funciones: `camelCase`.
- Tipos e interfaces: `PascalCase`.
- Constantes globales: `UPPER_SNAKE_CASE`.
- Archivos: `kebab-case.ts` o `camelCase.ts` según la convención de la carpeta.

### 6. Commits
- Formato: `tipo(alcance): descripción corta`.
- Tipos válidos: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`.
- Ejemplo: `feat(uis): crear app backoffice con panel de inventario`.
- Los mensajes deben estar en español.

### 7. Dependencias
- No instalar dependencias nuevas sin justificación.
- Antes de instalar, verificar que no exista una alternativa ya disponible en el proyecto.
- Documentar en `memory-bank/progress.md` cada nueva dependencia agregada.

---

## Verificación

Antes de cada commit, ejecutar:
```bash
npm run typecheck
```

Si hay errores de tipos, **no hacer commit** hasta resolverlos.
