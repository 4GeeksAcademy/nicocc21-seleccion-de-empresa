# Brasaland API

La carpeta contiene los módulos backend de Brasaland:

1. API de incidencias (WSGI legado).
2. API de proveedores (FastAPI + TinyDB + Pydantic).
3. API de inventario (FastAPI + SQLModel + Supabase PostgreSQL).

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
python3 -m uvicorn services.brasaland_api.main:app --host 0.0.0.0 --port 8001 --reload
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

## 3) API de inventario

El inventario usa una segunda base de datos PostgreSQL independiente de TinyDB.
Antes de iniciar la API, configura `DATABASE_URL` con la conexión de Supabase y
`JWT_SECRET_KEY` para autenticación.

### Endpoints

- `GET /inventory/products`
- `GET /inventory/products/{id}`
- `POST /inventory/products` (requiere JWT)
- `GET /inventory/orders`
- `POST /inventory/orders/inbound` (requiere JWT)
- `POST /inventory/orders/outbound` (requiere JWT)

El stock se calcula siempre como la suma de entradas menos la suma de salidas; no
se almacena como una columna editable. La documentación interactiva está
disponible en `http://localhost:8001/docs`.
