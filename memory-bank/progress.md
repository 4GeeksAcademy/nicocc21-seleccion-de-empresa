# Estado Actual del Proyecto

> Última revisión documental: 14 de octubre de 2026. Las tablas históricas se conservan; esta revisión verifica código, no el funcionamiento del despliegue.

## Estado verificado para la fase de telemetría

- `services/brasaland_api/main.py` configura FastAPI y registra rutas de autenticación, usuarios, perfiles, proveedores, incidencias e inventario.
- La API declara TinyDB para autenticación, proveedores e incidencias, y SQLModel/Supabase PostgreSQL para inventario.
- `inventory_models.py` define ingredientes, entradas y salidas; los movimientos incluyen cantidad, local y usuario. El stock se deriva de los movimientos y no se almacena como columna.
- `src/hito2/inventory-alerts.ts` ya implementa `generarAlertasInventario`, `tieneStockBajo` y `calcularImpactoEnDemanda`.
- Los entregables de diseño existen en `docs/telemetry/telemetry-plan.md` y `docs/telemetry/event-schemas.json`: 22 eventos, seis obligatorios y 16 oportunidades identificadas. No se ha instrumentado la aplicación.
- La revisión del contrato Draft 2020-12 aceptó 31 casos válidos y rechazó 499 inválidos con fixtures sintéticas en memoria; no verifica el pipeline ni los datos reales. La publicación del PR sigue pendiente de aprobación.
- Quedan por definir las correspondencias entre entidades, categorías e identificadores existentes y los exigidos por el contexto de telemetría.

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

## Dependencias declaradas en la raíz

```json
{
  "@types/jest": "^30.0.0",
  "esbuild": "^0.25.9",
  "jest": "^30.5.1",
  "ts-jest": "^29.4.12",
  "tsx": "^4.19.0",
  "typescript": "^5.6.3"
}
```

El backend declara sus dependencias Python en `pyproject.toml`; cada app en `uis/` mantiene su propio `package.json`. Esta lista no certifica qué paquetes están instalados en el entorno.

## Notas importantes

- La web en `web/` es HTML estático con JS bundle (esbuild). No es una app Next.js.
- `uis/website/` y `uis/backoffice/` son apps Next.js independientes con su propio `package.json`.
- El backoffice importa la lógica de negocio desde `src/hito2/` — no duplica código.
- Los datos en `sample-data.ts` son simulados pero representativos de las 14 sedes.
