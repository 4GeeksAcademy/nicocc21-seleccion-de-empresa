# Estado Actual del Proyecto

> Última actualización: 30 de julio de 2026

## Hito 1 — Web pública

| Archivo | Estado | Descripción |
|---------|--------|-------------|
| `web/index.html` | ✅ Creado | Página principal pública |
| `web/hito-2-fundamentos-programacion.html` | ✅ Creado | Panel interno (HTML estático) |
| `web/styles.css` | ✅ Creado | Estilos de la web |
| `web/validation.js` | ✅ Creado | Validaciones de formularios |
| `web/aplication.html` | ✅ Creado | Página de aplicación |

## Hito 2 — Lógica de negocio en TypeScript

| Archivo | Estado | Descripción |
|---------|--------|-------------|
| `src/hito2/types.ts` | ✅ Creado | Modelo de datos completo |
| `src/hito2/collections.ts` | ✅ Creado | filtrar, ordenar, buscar, agruparPor |
| `src/hito2/aggregations.ts` | ✅ Creado | generarReporteFinancieroPorLocal |
| `src/hito2/inventory-alerts.ts` | ✅ Creado | generarAlertasInventario + tieneStockBajo + calcularImpactoEnDemanda |
| `src/hito2/sample-data.ts` | ✅ Creado | 14 locales, 5 insumos, 3 fechas especiales, consumo promedio |
| `src/demo.ts` | ✅ Creado | Script de consola |

## Hito 3 — Monorepo AI Setup ✅

| Componente | Estado | Descripción |
|------------|--------|-------------|
| `memory-bank/projectbrief.md` | ✅ Creado | Contexto de negocio de Brasaland |
| `memory-bank/techContext.md` | ✅ Creado | Stack, arquitectura, convenciones |
| `memory-bank/progress.md` | ✅ Creado | Estado actual (este archivo) |
| `memory-bank/decisiones.md` | ✅ Creado | Decisiones de diseño documentadas |
| `AGENTS.md` | ✅ Creado | Protocolo del agente de código (5 pasos obligatorios) |
| `.agents/rules/conveniones.md` | ✅ Creado | Reglas de desarrollo con alcance explícito |
| `.agents/skills/scaffold-next-app/` | ✅ Creado | Skill con objetivo, inputs y criterios verificables |
| `uis/website/` | ✅ Creado | Next.js público con contenido Brasaland |
| `uis/backoffice/` | ✅ Creado | Panel interno con lógica Hito 2 integrada |

## Dependencias instaladas

```json
{
  "esbuild": "^0.25.9",
  "tsx": "^4.19.0",
  "typescript": "^5.6.3"
}
```

## Notas importantes

- La web en `web/` es HTML estático con JS bundle (esbuild). No es una app Next.js.
- `uis/website/` y `uis/backoffice/` son apps Next.js independientes con su propio `package.json`.
- El backoffice importa la lógica de negocio desde `src/hito2/` — no duplica código.
- Los datos en `sample-data.ts` son simulados pero representativos de las 14 sedes.
