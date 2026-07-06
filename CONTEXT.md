# Contexto del Proyecto - Brasaland

- Empresa: Brasaland (cadena de restaurantes, 14 locales)
- Reto: Seleccion de empresa mediante agente de IA
- Autor de la propuesta: Nicolas (enfoque desde experiencia previa en restaurantes)

## 1. Problema de fondo

Brasaland opera 14 locales sin visibilidad centralizada. Mariana (Direccion ejecutiva) toma decisiones reactivas, "apagando incendios", sin datos exactos de como funciona cada local.

En paralelo, Operaciones no tiene un control claro del stock ni de cuando se necesitara reposicion, lo que impacta directamente la atencion al cliente.

La propuesta ataca estos retos en dos frentes independientes pero conectados por los mismos datos base (locales, movimientos y fechas).

## 2. Frente 1 - Direccion ejecutiva

### Que necesita el negocio

- Visibilidad de costos reales por local (no estimaciones).
- Identificar rapido que locales y decisiones son mas eficientes para la cadena.
- Un portal ejecutivo con totales claros por local.
- Filtrado temporal flexible: tiempo real, por dia, por mes o por rango libre.
- Trazabilidad de entradas, salidas y departamento que genero cada gasto.
- Informes semanales automaticos con puntos clave de mejora por local y a nivel de cadena.

### Que vamos a construir

| Necesidad de negocio | Pieza tecnica |
| --- | --- |
| Totales por local | `generarReporteFinancieroPorLocal()` (ya implementado): agrupa `MovimientoFinanciero` por `localId` y calcula entradas, salidas y balance. |
| Filtrado por rango de fechas | Filtro sobre movimientos usando `filtrar()` + comparacion de fechas antes de generar el reporte. |
| Gasto por departamento | El campo `departamento` en `MovimientoFinanciero` permite agrupar/filtrar por cocina, barra, administracion, marketing y mantenimiento. |
| Informe semanal automatico | Job programado (cron o similar) que ejecuta `generarReporteFinancieroPorLocal()` para la semana y lo almacena en el portal. |
| Portal ejecutivo | Dashboard frontend (Next.js) que consume una API con estos reportes. |

### Decision de alcance: simulacion con 14 locales

Mientras no haya integracion con POS/facturacion real, se simulara todo el flujo de datos, manteniendo el contexto real de 14 sedes.

- Generar datos simulados para las 14 sedes (no solo 2 o 3 de ejemplo).
- Incluir movimientos financieros de varios departamentos y rangos de fechas por sede.
- Simular el informe semanal automatico sobre las 14 sedes en conjunto.
- Entregar el informe semanal dentro del portal ejecutivo.

## 3. Frente 2 - Operaciones de restaurante

### Que necesita el negocio

- Saber que hay en stock general: comida, bebida e insumos de empaque.
- Anticipar demanda segun temporada y fechas especiales (San Valentin, Navidad, Ano Nuevo, etc.).
- Alertas anticipadas de faltantes o excesos para optimizar compras y reducir desperdicio.
- Poder agregar productos nuevos cuando cambie la carta.

### Que vamos a construir

| Necesidad de negocio | Pieza tecnica |
| --- | --- |
| Stock general por categoria | `Insumo` ya incluye `categoria`; `contarPorCategoria()` y `agruparPor()` permiten ver stock agrupado. |
| Control de faltantes | `tieneStockBajo(insumo)` (ya implementado): compara `stockActual` vs `stockMinimo`. |
| Anticipar demanda por temporada | `FechaEspecial` + `calcularImpactoEnDemanda()` (ya implementado): devuelve factor vigente (ej. San Valentin x1.6, Navidad x2.0). |
| Alertas de faltantes/excesos | Pendiente: funcion que cruce `tieneStockBajo()` + `calcularImpactoEnDemanda()` para generar alertas priorizadas. |
| Perecederos vs no perecederos | `Insumo.perecedero` + `diasVidaUtil` ya modelado para logica de vencimiento cercano. |
| Agregar productos nuevos | Crear nuevo objeto `Insumo`; el modelo lo soporta sin cambios de esquema. |

### Regla de rotacion de stock por tipo de insumo

- Perecederos refrigerados (carne, queso, pollo, verduras): rotacion semanal (7 dias).
- Licores y bebidas: rotacion quincenal (15 dias).
- Criterio de exceso: si el stock actual no se consume dentro del ciclo definido.

Implicacion tecnica:

- `Insumo` debe incluir `frecuenciaRotacionDias` (por ejemplo `7 | 15`) para evaluar exceso contra consumo esperado por ciclo, no con un umbral unico para todos los insumos.

## 4. Relacion entre ambos frentes

Ambos modulos comparten entidades base (`Local`, fechas y movimientos), permitiendo que a futuro el agente de IA (Yayo, construido con OpenClaw) responda preguntas cruzadas entre finanzas y operaciones.

Ejemplo de consulta futura:

> "Medellin es el local que mas gasta porque es el mas grande. Ese gasto esta justificado por su volumen de ventas o hay baja rotacion de stock que indique desperdicio?"

Esto no se construye en esta fase, pero el modelo de datos ya esta orientado para habilitarlo sin rehacer la base.

## 5. Estado actual vs proximos pasos

### Ya construido (`brasaland-utils/`)

- Modelo de datos completo para ambos frentes (`types.ts`).
- Funciones de colecciones: filtrar, ordenar, buscar, agrupar (`collections.ts`).
- Reportes agregados: financiero por local e inventario por insumo (`aggregations.ts`).
- Validaciones de negocio por entidad (`validations.ts`).

### Falta construir

- Funcion de alertas de stock (cruce de `tieneStockBajo` + `calcularImpactoEnDemanda`).
- API (Flask o Next.js API routes) para exponer funciones como endpoints.
- Portal ejecutivo (frontend) con totales por local y filtro de fechas.
- Vista de Operaciones (frontend) con estado de stock y alertas.
- Job de informe semanal automatico.
- Mecanismo de entrega de alertas e informes (en esta fase, dentro del portal).
