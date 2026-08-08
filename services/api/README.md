# APIs de Brasaland en `services/api`

La carpeta contiene dos servicios backend:

1. API de incidencias (WSGI legado).
2. API de proveedores (FastAPI + TinyDB + Pydantic).

## 1) API de incidencias

Servicio backend para análisis interno de incidencias CSV.

### Ejecutar local

Desde la raíz del monorepo:

```bash
python3 services/api/app.py
```

La API quedará disponible en `http://localhost:8000`.

### Endpoints

#### POST /api/incidents/analyze

- Content-Type: `multipart/form-data`
- Campo esperado del archivo: `file` (acepta también `csv` o `incidents`)
- Respuesta: JSON con métricas de análisis

Ejemplo:

```bash
curl -X POST \
  -F "file=@scripts/incidents-BRASALAND.csv" \
  http://localhost:8000/api/incidents/analyze
```

#### GET /api/incidents/results/export

Descarga el CSV del último análisis ejecutado.

```bash
curl -OJ http://localhost:8000/api/incidents/results/export
```

## 2) API de proveedores

Directorio de proveedores para compras con validaciones de negocio y persistencia en TinyDB.

### Instalar dependencias

Desde la raíz del monorepo:

```bash
python3 -m pip install -r services/api/requirements.txt
```

### Ejecutar seeder

```bash
python3 services/api/seed.py
```

El seeder es idempotente: no duplica proveedores ya existentes.

### Ejecutar API FastAPI

```bash
python3 -m uvicorn services.api.main:app --host 0.0.0.0 --port 8001 --reload
```

Base URL: `http://localhost:8001`

### Endpoints de proveedores

- `POST /suppliers`
- `GET /suppliers`
- `GET /suppliers?country=Colombia|USA`
- `GET /suppliers?category=<categoria_valida>`
- `GET /suppliers/{id}`
- `PATCH /suppliers/{id}/rate`
- `PATCH /suppliers/{id}/status`
- `DELETE /suppliers/{id}`

Notas:

- `updated_at` lo genera el sistema.
- `status` solo acepta `active` o `suspended`.
- `rate_per_unit` debe ser mayor que 0.
