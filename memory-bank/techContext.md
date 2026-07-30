# Arquitectura Técnica

## Stack

- **Lenguaje principal:** TypeScript (ES2020, módulos NodeNext, estricto).
- **Framework frontend:** Next.js (App Router) para apps en `uis/`.
- **Lógica de negocio:** TypeScript puro en `src/hito2/`.
- **Bundle web estático:** esbuild (para `web/`).
- **Runtime de desarrollo:** tsx.

## Convenciones de código

- `tsconfig.json` raíz: `strict: true`, `noEmit: true`, `rootDir: src`.
- Nomenclatura: `camelCase` para variables/funciones, `PascalCase` para tipos/interfaces.
- Los tipos viven en `src/hito2/types.ts`.
- Las funciones genéricas de colección viven en `src/hito2/collections.ts`.
- Las agregaciones de negocio viven en `src/hito2/aggregations.ts`.
- Las alertas de inventario viven en `src/hito2/inventory-alerts.ts`.
- Los datos de ejemplo viven en `src/hito2/sample-data.ts`.

## Estructura del monorepo

```
/
├── src/                    # Lógica de negocio TypeScript
│   └── hito2/              # Módulo de programación fundamental
├── web/                    # Web pública estática (HTML + JS bundle)
├── uis/                    # Aplicaciones de interfaz de usuario
│   ├── website/            # (próximo) Next.js público
│   └── backoffice/         # (próximo) Panel interno
├── services/               # (próximo) APIs y workers
├── data/                   # Datos raw, procesados, pipelines
├── template/               # Plantillas y READMEs de guía
├── memory-bank/            # Contexto persistente del proyecto
├── .agents/                # Configuración de agentes de código
│   ├── rules/              # Reglas de desarrollo
│   └── skills/             # Skills reutilizables
├── AGENTS.md               # Protocolo del agente (raíz)
└── CONTEXT.md              # Contexto de la empresa asignada
```

## Distinción crítica: `.agents/` vs `/agents/`

| Directorio | Propósito |
|------------|-----------|
| `.agents/` | Configuración del agente de código (Cursor, Copilot, Claude Code). Define CÓMO trabaja la herramienta. |
| `/agents/` | Agentes de producto que construimos para Brasaland. Define QUÉ construimos. |

## Reglas de datos

### Entidades principales

| Entidad | Archivo | Descripción |
|---------|---------|-------------|
| `Local` | types.ts | Sede de Brasaland (id, nombre, ciudad) |
| `MovimientoFinanciero` | types.ts | Entrada/salida financiera con departamento |
| `Insumo` | types.ts | Producto en stock con categoría y rotación |
| `FechaEspecial` | types.ts | Fecha con factor de demanda |
| `AlertaInventario` | types.ts | Alerta priorizada de faltante/exceso |
| `ReporteFinancieroLocal` | types.ts | Reporte agregado por local |

### Departamentos válidos

`cocina`, `barra`, `administracion`, `marketing`, `mantenimiento`

### Categorías de insumo

`comida`, `bebida`, `empaque`

### Prioridades de alerta

`critica` (peso 4) > `alta` (peso 3) > `media` (peso 2) > `informativa` (peso 1)

## Scripts disponibles

| Comando | Descripción |
|---------|-------------|
| `npm run typecheck` | Valida tipos de TypeScript |
| `npm run demo` | Ejecuta demo en consola |
| `npm run build:web` | Compila `web.ts` → `web/dist/hito2-web.js` |

## Criterios de calidad

- Todo código nuevo debe pasar `npm run typecheck` sin errores.
- No se introducen dependencias externas sin justificación documentada.
- Las funciones de negocio son puras (sin side effects, sin I/O directo).
- Los datos simulados deben ser representativos de los 14 locales.
