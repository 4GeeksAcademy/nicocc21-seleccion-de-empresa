# Export nocturno de telemetría

El script se ejecuta como proceso independiente; no se inicia desde FastAPI.
La configuración de referencia usa `cron` del sistema en UTC, todos los días a
las 02:00 (`0 2 * * *`). Ajusta `BRASALAND_HOME` y `BRASALAND_PYTHON` en
`services/telemetry/nightly_export.crontab` al directorio de despliegue y su
entorno virtual, y luego instala la tabla con:

```sh
crontab services/telemetry/nightly_export.crontab
```

El proceso carga `TARGET_DATE` si está definida; de lo contrario, procesa el
día anterior en UTC. El CSV es un snapshot de auditoría y no se utiliza como
entrada del pipeline, que consulta `telemetry_events` directamente.

La migración `services/telemetry/migrations/001_nightly_telemetry.sql` crea
`job_runs`, sus índices de idempotencia/lock y `daily_kpi`. Puede aplicarse con:

```sh
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 \
  -f services/telemetry/migrations/001_nightly_telemetry.sql
```

Ejemplos de logs estructurados:

```text
2026-11-02T02:00:00+0000 INFO job_name=nightly_export status=processing Lock adquirido para 2026-11-01
2026-11-02T02:00:03+0000 INFO job_name=nightly_export status=completed Ejecución completada para 2026-11-01
2026-11-02T02:00:00+0000 INFO job_name=nightly_export status=blocked Omitido: ya existe una ejecución processing
```