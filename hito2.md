# Hito 2 - Fundamentos de Programacion (Brasaland)

> Regla de implementacion: todo el desarrollo del Hito 2 se realiza en TypeScript.

## 1. Objetivo del hito

Construir la logica base de negocio para Brasaland en dos frentes:

- Direccion ejecutiva: control financiero por local con filtros de fecha.
- Operaciones: control de inventario con alertas de faltantes y excesos.

Este hito se enfoca en funciones, estructuras de datos y reglas de negocio implementadas en TypeScript (sin acoplarse aun a una UI final ni a integraciones reales con POS/facturacion).

## 2. Contexto funcional

Brasaland opera 14 locales y necesita tomar decisiones con datos confiables.

Problemas actuales:

- No existe visibilidad centralizada de costos por sede.
- Las decisiones se toman de forma reactiva.
- Operaciones no cuenta con alertas preventivas de inventario.
- No hay una lectura conjunta entre movimientos financieros y rotacion de stock.

## 3. Alcance de Hito 2

### Incluye

- Modelado de entidades de dominio en interfaces y tipos TypeScript.
- Funciones genericas de colecciones (filtrar, ordenar, agrupar, buscar) en TypeScript.
- Reportes financieros agregados por local en TypeScript.
- Validaciones de negocio por entidad en TypeScript.
- Logica de inventario para stock bajo y demanda por fecha especial en TypeScript.
- Simulacion de datos para 14 locales con tipado estricto.

### No incluye (se abordara en hitos siguientes)

- API productiva.
- Dashboard en produccion.
- Integracion real con sistemas externos.
- Automatizacion real de envio de reportes (correo, bots, etc.).

### Stack de implementacion del hito

- Lenguaje principal: TypeScript.
- Estilo recomendado: tipado estricto (`strict: true`) y sin `any` salvo justificacion puntual.

## 4. Entidades y reglas de negocio

### Entidades clave

- Local
- MovimientoFinanciero
- Insumo
- FechaEspecial

### Reglas clave

- `MovimientoFinanciero` debe permitir trazabilidad por `localId`, fecha y departamento.
- `Insumo` debe modelar categoria, stock, perecibilidad y vida util.
- Se incorpora `frecuenciaRotacionDias` para detectar exceso segun ciclo:
- `7` dias para perecederos refrigerados.
- `15` dias para bebidas y licores.

## 5. Funcionalidades implementadas (base actual)

En el paquete de utilidades de Brasaland:

- `types.ts`: modelo de datos del dominio.
- `collections.ts`: utilidades de colecciones (`filtrar`, `ordenar`, `buscar`, `agrupar`).
- `aggregations.ts`: reportes agregados (financiero por local e inventario por insumo).
- `validations.ts`: validaciones de negocio por entidad.

Funciones destacadas:

- `generarReporteFinancieroPorLocal()`
- `tieneStockBajo(insumo)`
- `calcularImpactoEnDemanda(fecha, fechaEspecial)`

## 6. Funcionalidad pendiente en este hito

Implementar la funcion de alertas priorizadas de inventario que combine:

- Stock bajo actual (`tieneStockBajo`).
- Impacto de demanda por temporada (`calcularImpactoEnDemanda`).
- Rotacion esperada (`frecuenciaRotacionDias`).

### Firma sugerida

`generarAlertasInventario(insumos, fechaActual, fechasEspeciales, consumoPromedioPorDia)`

Firma tipada sugerida en TypeScript:

`generarAlertasInventario(insumos: Insumo[], fechaActual: Date, fechasEspeciales: FechaEspecial[], consumoPromedioPorDia: Record<string, number>): AlertaInventario[]`

### Salida esperada

Lista de alertas ordenadas por prioridad:

- Critica: riesgo de quiebre inminente.
- Alta: riesgo alto en ventana corta.
- Media: ajustar pedido.
- Informativa: revisar sobrestock.

## 7. Datos de simulacion requeridos

Para representar el negocio real:

- 14 locales simulados.
- Movimientos financieros de varios departamentos por local.
- Fechas distribuidas por dia, semana y mes.
- Insumos mixtos (perecederos y no perecederos) con diferentes rotaciones.
- Casos de fecha especial (San Valentin, Navidad, Ano Nuevo).

## 8. Criterios de aceptacion del Hito 2

1. El reporte financiero por local devuelve entradas, salidas y balance por cada una de las 14 sedes.
2. El filtrado por rango de fechas modifica correctamente el reporte sin inconsistencias.
3. La logica de stock detecta faltantes y exceso segun categoria y rotacion.
4. La demanda se ajusta correctamente por fechas especiales.
5. La funcion de alertas entrega prioridades coherentes para toma de decision.
6. Todas las reglas se prueban con datos simulados no triviales.
7. El codigo del hito compila en TypeScript sin errores de tipos.

## 9. Entregables

- Documento de contexto validado: [CONTEXT.md](CONTEXT.md)
- Documento de hito tecnico: [hito2.md](hito2.md)
- Modulo de utilidades de dominio en TypeScript (`types.ts`, `collections.ts`, `aggregations.ts`, `validations.ts`).
- Dataset de simulacion para 14 locales.
- Evidencia de pruebas funcionales de la logica.

## 10. Proximo paso recomendado

Conectar esta base de logica con la nueva pagina de trabajo del proyecto:

- `hito-2-fundamentos-programacion` (pagina adicional)

Objetivo del siguiente paso:

- Presentar visualmente los resultados de la logica del hito (reportes y alertas) con datos simulados de Brasaland.
