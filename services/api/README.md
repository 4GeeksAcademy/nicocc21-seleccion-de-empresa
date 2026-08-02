# API de Incidencias (Brasaland)

Servicio backend para análisis interno de incidencias CSV.

## Ejecutar local

Desde la raíz del monorepo:

```bash
python3 services/api/app.py
```

La API quedará disponible en `http://localhost:8000`.

## Endpoints

### POST /api/incidents/analyze

- Content-Type: `multipart/form-data`
- Campo esperado del archivo: `file` (acepta también `csv` o `incidents`)
- Respuesta: JSON con métricas de análisis

Ejemplo con curl:

```bash
curl -X POST \
  -F "file=@scripts/incidents-BRASALAND.csv" \
  http://localhost:8000/api/incidents/analyze
```

### GET /api/incidents/results/export

Descarga el CSV del último análisis ejecutado.

```bash
curl -OJ http://localhost:8000/api/incidents/results/export
```
