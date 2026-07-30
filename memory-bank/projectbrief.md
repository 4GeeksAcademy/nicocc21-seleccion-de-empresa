# Empresa: Brasaland

## Descripción general

Brasaland es una cadena de restaurantes con **14 sedes** distribuidas en Colombia y Estados Unidos.

| Sede | Ciudad |
|------|--------|
| L01 - L03 | Bogotá, Medellín, Cali |
| L04 - L06 | Barranquilla, Cartagena, Bucaramanga |
| L07 | Pereira |
| L08 - L10 | Miami, Orlando, Tampa |
| L11 - L14 | Bogotá, Medellín, Cali, Miami (segundas sedes) |

## Problema de negocio

Brasaland opera las 14 sedes **sin visibilidad centralizada**. La dirección ejecutiva toma decisiones reactivas sin datos exactos de cómo funciona cada local. En paralelo, operaciones no tiene control claro del stock ni de cuándo se necesitará reposición.

## Stakeholders clave

- **Mariana** — Dirección Ejecutiva (CEO). Necesita visibilidad de costos reales por local, identificar locales eficientes, y reportes semanales automáticos.
- **Jefe de Inventarios** — Operaciones de restaurante. Necesita saber qué hay en stock, anticipar demanda por temporada, y recibir alertas de faltantes/excesos.

## Frente 1: Dirección Ejecutiva

- Totales de costos por local (entradas, salidas, balance).
- Filtrado por rango de fechas (tiempo real, día, mes, rango libre).
- Gasto desglosado por departamento: cocina, barra, administración, marketing, mantenimiento.
- Informes semanales automáticos con puntos clave de mejora.
- Portal ejecutivo con totales claros por local.

## Frente 2: Operaciones de restaurante

- Stock general por categoría: comida, bebida, empaque.
- Anticipar demanda según temporada y fechas especiales (San Valentín, Navidad, Año Nuevo).
- Alertas anticipadas de faltantes o excesos para optimizar compras y reducir desperdicio.
- Agregar productos nuevos cuando cambie la carta.

## Regla de rotación de stock

| Tipo de insumo | Ciclo de rotación |
|----------------|-------------------|
| Perecederos refrigerados (carne, queso, pollo, verduras) | 7 días |
| Licores y bebidas | 15 días |

Criterio de exceso: si el stock actual no se consume dentro del ciclo definido.

## Relación entre frentes

Ambos módulos comparten entidades base (`Local`, fechas, movimientos). Esto permite que a futuro un agente de IA responda preguntas cruzadas entre finanzas y operaciones.

> Ejemplo: *"Medellín es el local que más gasta. ¿Ese gasto está justificado por su volumen de ventas o hay baja rotación de stock que indique desperdicio?"*

Esto no se construye en esta fase, pero el modelo de datos ya está orientado para habilitarlo.
