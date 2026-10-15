# Contexto del Proyecto - Brasaland

- Empresa: Brasaland (cadena de restaurantes, 14 locales)
- Reto: Seleccion de empresa mediante agente de IA
- Autor de la propuesta: Nicolas (enfoque desde experiencia previa en restaurantes)

> Revisión documental: 14 de octubre de 2026. Se conserva el briefing original y se corrigen referencias a componentes que ya existen. Esta revisión no certifica un despliegue en producción ni autoriza instrumentación.

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
| Alertas de faltantes/excesos | Implementadas en `src/hito2/inventory-alerts.ts` mediante `generarAlertasInventario()`, que cruza stock, demanda y consumo para generar alertas priorizadas. |
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

### Ya construido (lógica TypeScript en `src/hito2/`)

- Modelo de datos completo para ambos frentes (`types.ts`).
- Funciones de colecciones: filtrar, ordenar, buscar, agrupar (`collections.ts`).
- Reportes agregados: financiero por local e inventario por insumo (`aggregations.ts`).
- Validaciones de negocio por entidad (`validations.ts`).
- Alertas de inventario en `inventory-alerts.ts`.
- API FastAPI en `services/brasaland_api/`, con rutas de autenticación, usuarios, perfiles, proveedores, incidencias e inventario. El inventario usa modelos SQLModel para Supabase/PostgreSQL; otros módulos usan TinyDB.
- Apps Next.js pública e interna en `uis/website/` y `uis/backoffice/`. Su existencia no implica que todos los requisitos del portal ejecutivo estén completos.

### Alcance original pendiente de verificar o completar

- Portal ejecutivo (frontend) con totales por local y filtro de fechas.
- Vista de Operaciones (frontend) con estado de stock y alertas.
- Job de informe semanal automatico.
- Mecanismo de entrega de alertas e informes (en esta fase, dentro del portal).

Estos requisitos históricos no se implementan como parte de la corrección documental ni se dan por ausentes sin revisar sus flujos.

## 6. Modulo de incidencias postventa (simulacion interna)

El departamento de atencion postventa de Brasaland gestiona incidencias de clientes (quejas, solicitudes y fallos operativos). Para validar el proceso de analisis sin exponer datos sensibles, se definio un dataset simulado interno de 100 registros en CSV.

El objetivo es validar la logica ahora con datos ficticios y, en una fase posterior, sustituir el origen por datos reales sin cambiar la arquitectura.

### Archivo de prueba

- Ruta del archivo: scripts/incidents-BRASALAND.csv
- Total de filas de datos: 100 (mas cabecera)
- Registros validos esperados: 92
- Registros invalidos esperados: 8

### Esquema CSV (nombres exactos de columnas)

1. incident_id
2. fecha_reporte
3. local_id
4. cliente_id
5. cliente_email
6. cliente_telefono
7. categoria
8. estado
9. prioridad
10. satisfaccion
11. descripcion

### Campos obligatorios

Los siguientes campos se consideran obligatorios para que una fila sea valida:

- incident_id
- fecha_reporte
- local_id
- cliente_id
- cliente_email
- cliente_telefono
- categoria
- estado
- prioridad
- descripcion

Nota: satisfaccion es opcional salvo cuando aplique logica de validacion de rango si viene informada.

### Valores validos

- local_id: L01 a L14
- categoria: queja, solicitud, fallo_operativo
- estado: abierto, cerrado, descartado
- prioridad: baja, media, alta, critica
- satisfaccion: entero entre 1 y 5 cuando exista valor

### Reglas de invalidez

Una fila es invalida si cumple al menos una de estas condiciones:

1. Le falta un campo obligatorio.
2. categoria fuera de rango.
3. estado fuera de rango.
4. local_id fuera de rango.
5. prioridad fuera de rango.
6. satisfaccion fuera de rango (menor a 1 o mayor a 5) o no numerica.

### Resultados esperados para el dataset simulado (base de verificacion)

1. Totales generales
- procesados: 100
- validos: 92
- invalidos: 8

2. Invalidos por tipo
- campo_faltante: 2
- categoria_fuera_de_rango: 2
- estado_fuera_de_rango: 2
- satisfaccion_fuera_de_rango: 1
- local_id_fuera_de_rango: 1

3. Totalizacion por categoria (solo validos)
- queja: 34
- solicitud: 30
- fallo_operativo: 28

4. Totalizacion por estado (solo validos)
- abierto: 33
- cerrado: 45
- descartado: 14

5. Satisfaccion media (solo cerrados con puntuacion)
- casos cerrados con satisfaccion: 40
- satisfaccion_media: 4.1

### Observacion de privacidad

El CSV simulado contiene identificadores, correos y telefonos ficticios de prueba (dominio brasaland.test), por lo que no hay datos personales reales expuestos.

## 7. Contexto adicional de telemetría

El contexto de telemetría compartido para esta fase complementa el briefing original. Los entregables previstos son un plan Markdown y esquemas JSON en `docs/telemetry/`, sujetos a aprobación paso a paso; aún no se autoriza instrumentación.

Eventos obligatorios: `inbound_order_created`, `outbound_order_created`, `stock_waste_registered`, `stock_threshold_triggered`, `direct_stock_edit_rejected` e `ingredient_price_variance_detected`.

Restricciones: conservar `COP`/`USD` según el país del local, separar país e idioma de UI, mantener movimientos de stock trazables mediante órdenes y excluir nombres de empleados y datos de clientes de `properties`.

Las entidades del contexto (`Product`, `InboundOrder`, `OutboundOrder`) deben relacionarse explícitamente con los modelos actuales (`Ingredient`, `IngredientEntry`, `IngredientExit`). El mapeo de categorías y de `location_id` entero a los códigos `L01`–`L14` está pendiente; no se cambia el esquema existente en esta fase.
