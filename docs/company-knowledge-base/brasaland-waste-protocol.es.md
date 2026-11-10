# Protocolo de Control de Desperdicio — Brasaland

## 1. Objetivo

Establecer un procedimiento estandarizado para minimizar el desperdicio de alimentos e insumos en todos los locales de Brasaland (14 sedes: 10 en Colombia y 4 en Florida), garantizando el cumplimiento de normas sanitarias y contribuyendo a la eficiencia operativa y la reducción de costos.

## 2. Clasificación de Desperdicios

### 2.1 Desperdicio Evitable

Corresponde a alimentos e insumos que podrían haberse aprovechado pero se descartan por:
- Sobreproducción en cocina.
- Errores en la preparación.
- Mal manejo en la rotación de inventarios (FIFO no respetado).
- Daños por almacenamiento inadecuado.

### 2.2 Desperdicio Inevitable

Corresponde a residuos que no pueden aprovecharse:
- Peladuras, huesos, espinas, cáscaras.
- Alimentos descompuestos o contaminados.
- Productos vencidos.

## 3. Procedimiento Diario de Control

### 3.1 Registro de Desperdicio

Cada local debe registrar diariamente en el sistema los siguientes datos:

| Campo | Descripción |
|---|---|
| `fecha` | Fecha del registro |
| `local_id` | Identificador del local (L01 a L14) |
| `categoria` | Cocina, Barra, Administración, Almacén |
| `tipo` | Evitable o Inevitable |
| `insumo_id` | Identificador del insumo desperdiciado |
| `cantidad_kg` | Peso en kilogramos (aproximación ±0,1 kg) |
| `causa` | Motivo del desperdicio |
| `costo_estimado` | Costo estimado del desperdicio en COP |

### 3.2 Frecuencia de Registro

- Cocina: después de cada servicio (almuerzo y cena).
- Barra: al cierre del local.
- Administración y Almacén: una vez al día.

### 3.3 Responsable

El registro debe realizarlo el encargado de turno. El gerente del local debe revisar y validar el reporte semanal de desperdicio antes del cierre del sábado.

## 4. Metas y Umbrales

| Tipo de local | Meta máxima de desperdicio evitable |
|---|---|
| Locales Colombia | 4,5 % del total de insumos utilizados en el mes |
| Locales Florida | 3,5 % del total de insumos utilizados en el mes |

### 4.1 Consecuencias por incumplimiento

- Si un local supera la meta durante 2 meses consecutivos, el gerente debe presentar un plan de mejora.
- Si la supera durante 3 meses consecutivos, se activa una auditoría operativa.

## 5. Protocolo para Alimentos Aprovechables

### 5.1 Donación

Los alimentos en buen estado que no puedan venderse (por proximidad a vencimiento o excedentes de producción) pueden donarse a bancos de alimentos locales autorizados. Cada donación debe registrarse en el sistema indicando:
- `local_id`
- `fecha`
- `insumo_id`
- `cantidad_kg`
- `entidad_receptora`

### 5.2 Compostaje

Los residuos orgánicos no aptos para consumo humano (cáscaras, restos vegetales) deben enviarse a compostaje en los locales que cuenten con el servicio. En locales sin compostaje, deben desecharse según la normativa municipal.

## 6. Reporte Semanal

El sistema genera automáticamente cada lunes el reporte de desperdicio de la semana anterior. El reporte incluye:
- Total de desperdicio evitable vs inevitable por local.
- Porcentaje de desperdicio sobre insumos totales.
- Comparación con la meta semanal.
- Ranking de locales con menor y mayor desperdicio.
- Causas más frecuentes de desperdicio evitable.

## 7. Sanciones por Incumplimiento del Protocolo

- No registrar el desperdicio diario: amonestación verbal la primera vez, amonestación escrita la segunda.
- Falsear datos de desperdicio: falta grave sujeta a medidas disciplinarias según el reglamento interno de Brasaland.

## 8. Contacto

Para dudas sobre el protocolo de desperdicio, contactar a operaciones@brasaland.com.