# Telemetría de tu compañía – Reporte técnico

Instrucciones del proyecto (4Geeks, módulo Application Telemetry) y checklist de verificación paso a paso.

## Fase 1 — Pipeline de análisis con Pandas

- [ ] Crear `services/telemetry/analysis.py` con al menos **3 funciones de métrica**, cada una sobre una dimensión operacional distinta, calculada desde el catálogo de eventos propio.
- [ ] Cada función es **independiente y sin efectos secundarios**: dos llamadas con los mismos parámetros devuelven el mismo resultado.
- [ ] **Sin loops** para calcular métricas: solo Pandas (`.groupby()`, `.agg()`, `.count()`, `.sum()`, `.mean()`).
- [ ] Las métricas son **técnicas/operacionales** (volumen, errores, latencia, disponibilidad), no de negocio (ventas, conversión, ingresos).

## Fase 2 — Endpoint de reporte

- [ ] `GET /telemetry/report` en FastAPI, en `services/`.
- [ ] Query params opcionales `start_date` y `end_date` (ISO 8601). Por defecto: `start_date = now - 7d`, `end_date = now` (UTC).
- [ ] Resolver el período **una sola vez** y pasar `start_date`/`end_date` a cada función; las funciones no aplican su propia ventana por defecto.
- [ ] Respuesta JSON:

```json
{
  "period": { "from": "...", "to": "..." },
  "metrics": {
    "events_per_day": [],
    "error_rate_by_type": []
  }
}
```

- [ ] Caché simple en memoria con **TTL de 60 s**: misma combinación `start_date`/`end_date` dentro del TTL devuelve el resultado cacheado sin recalcular.

## Actividad adicional — Métrica de autenticación

- [ ] Tercera función: **tasa diaria de fallos de login** = `user_login_failed / (user_login_failed + user_login_succeeded)` por día.
- [ ] Cargar ambos tipos con `event_type IN (...)` en SQL y calcular la razón en Pandas.
- [ ] Incluirla en el endpoint bajo la clave `auth_failure_rate`.

## Actividad adicional — Dashboard visual simple

- [ ] Página mínima en `uis/backoffice/` (p. ej. `/telemetry`) que consuma `GET /telemetry/report`.
- [ ] Gráfico de barras/líneas o tabla HTML por métrica (`events_per_day`, `error_rate_by_type`, ...).
- [ ] Mostrar el `period` (`from`/`to`) visualizado.
- [ ] Vista técnica para ingeniería, no de negocio. Sin pulido de diseño.

## Qué se evalúa

- [ ] `services/telemetry/analysis.py` existe con ≥ 3 funciones de métrica independientes.
- [ ] Cada función sigue: **cargar (SQL) → refinar (Pandas) → convertir tipos → agrupar → agregar**, en ese orden.
- [ ] Timestamps convertidos a `datetime` con `utc=True` antes de cualquier `groupby()` temporal.
- [ ] Sin loops para métricas.
- [ ] Cada función devuelve una lista de dicts serializable a JSON.
- [ ] El endpoint acepta `start_date` y `end_date` opcionales, con 7 días por defecto.
- [ ] El endpoint devuelve `{ "period": {...}, "metrics": {...} }`.
- [ ] Caché en memoria con TTL de 60 s.
- [ ] Cada métrica responde una pregunta técnica/operacional.
- [ ] Cada métrica tiene una dimensión de agrupamiento (no números globales sin contexto).

## Cómo entregar

1. `analysis.py` en `services/telemetry/` y el endpoint `GET /telemetry/report` en `services/`.
2. Pull Request contra la rama principal con el título: `feat: telemetry report endpoint`.
3. Descripción del PR:
   - Nombre de las métricas implementadas y qué pregunta operacional responde cada una.
   - Muestra del JSON devuelto por `GET /telemetry/report` con **datos reales**.
   - Mención de la métrica de autenticación y/o el dashboard, si se implementaron.

## Estado verificado del repositorio (2026-10-20)

| Punto | Estado | Detalle |
|-------|--------|---------|
| `services/telemetry/` | No existe | Hay que crear la carpeta (con `__init__.py`). |
| `pandas` | No está en `pyproject.toml` | Dependencia nueva a añadir. |
| `POST /telemetry/events` | Stub | Valida y registra en log; **no persiste** eventos. |
| `TelemetryEventRecord` | Existe, sin uso | `services/brasaland_api/telemetry_models.py`, tabla `telemetry_events`. |
| Eventos `user_login_*` | Por verificar | Confirmar en `docs/telemetry/event-schemas.json` y que el backend los emita. |
| Caché | Existe `@cached` | `services/brasaland_api/cache.py`; verificar si sirve para TTL por `start_date`/`end_date`. |
| Frontend | Existe instrumentación | `uis/backoffice/app/telemetry*.ts`. |

## Orden de trabajo propuesto

1. Persistir eventos en `telemetry_events` (sin datos reales no hay reporte).
2. Añadir `pandas` y crear `services/telemetry/analysis.py` (3 métricas).
3. Endpoint `GET /telemetry/report` con período único y caché TTL 60 s.
4. Métrica `auth_failure_rate`.
5. Dashboard en `uis/backoffice/`.
6. Tests, rama nueva desde `main` y PR `feat: telemetry report endpoint`.
