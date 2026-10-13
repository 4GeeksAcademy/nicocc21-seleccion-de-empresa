# Plan de Dockerización — Brasaland Monorepo

> **Propósito**: Definir el entorno de desarrollo en código para que se ejecute de forma idéntica en cualquier máquina del equipo, sin configuración manual.
>
> ⚠️ **Estado**: BORRADOR — Pendiente de aprobación paso a paso.

---

## Índice

1. [Resumen de la arquitectura actual](#1-resumen-de-la-arquitectura-actual)
2. [Estrategia de contenedorización](#2-estrategia-de-contenedorización)
3. [Archivos a crear](#3-archivos-a-crear)
4. [Archivos a modificar](#4-archivos-a-modificar)
5. [Variables de entorno](#5-variables-de-entorno)
6. [Plan de ejecución paso a paso](#6-plan-de-ejecución-paso-a-paso)
7. [Verificación](#7-verificación)
8. [Preguntas abiertas y decisiones pendientes](#8-preguntas-abiertas-y-decisiones-pendientes)

---

## 1. Resumen de la arquitectura actual

```
brasaland/
├── services/brasaland_api/     ← Backend Python (FastAPI + WSGI legacy)
│   ├── main.py                 ← FastAPI app (uvicorn) → puerto 8001
│   ├── app.py                  ← WSGI app (incidencias) → puerto 8000
│   ├── routes/                 ← auth, suppliers, incidents, inventory, profiles, users
│   ├── database.py             ← TinyDB (auth/suppliers/incidents) + SQLModel/PostgreSQL (inventory)
│   ├── data/                   ← Archivos TinyDB (suppliers.json, incidents.json)
│   └── requirements.txt
│
├── uis/website/                ← Frontend público (Next.js 16.2) → puerto 3000
│   └── (estático, sin llamadas API)
│
├── uis/backoffice/             ← Panel admin (Next.js 16.2) → puerto 3001
│   ├── app/api/*/route.ts      ← API Routes proxy al backend (usan 127.0.0.1:8000/8001)
│   └── next.config.ts          ← Rewrite para /api/auth/* → 127.0.0.1:8001
│
└── .gitignore                  ← Ya protege .env, node_modules, __pycache__, .next/
```

### Puntos críticos identificados

| # | Asunto | Detalle |
|---|--------|---------|
| 1 | **Dos servidores en backend** | `app.py` (WSGI, puerto 8000) y `main.py` (uvicorn FastAPI, puerto 8001) — ambos necesarios |
| 2 | **Env var compartida** | `INCIDENTS_BACKEND_BASE_URL` se usa con dos valores distintos (8000 y 8001) según el route. En Docker necesitamos separarlas |
| 3 | **Rewrite sin env** | `next.config.ts` tiene `127.0.0.1:8001` hardcodeado — necesita un env var |
| 4 | **Sin Dockerfile ni compose** | No existe ningún archivo Docker en el repositorio |
| 5 | **PostgreSQL opcional** | `DATABASE_URL` apunta a Supabase externo. Para dev offline conviene un contenedor Postgres local |

---

## 2. Estrategia de contenedorización

### 2.1 Topología

```
┌──────────────────────────────────────────────────────────────────┐
│                        docker-compose.yml                        │
│                                                                  │
│  ┌──────────────┐     ┌──────────────────┐     ┌─────────────┐  │
│  │   website     │     │   backoffice     │     │   backend   │  │
│  │  (Next.js)   │     │  (Next.js)       │     │ (FastAPI +  │  │
│  │  :3000       │     │  :3001           │     │  WSGI)      │  │
│  │              │     │                  │     │  :8000      │  │
│  │              │     │  ─────────────────┼──▶  │  :8001      │  │
│  │              │     │  INCIDENTS_BASE  │     │             │  │
│  │              │     │  SUPPLIERS_BASE  │     │             │  │
│  └──────────────┘     └──────────────────┘     └──────┬──────┘  │
│                                                        │        │
│                                              ┌─────────▼──────┐ │
│                                              │   postgres      │ │
│                                              │   (opcional)   │ │
│                                              │   :5432        │ │
│                                              └────────────────┘ │
└──────────────────────────────────────────────────────────────────┘
```

### 2.2 Servicios

| Servicio | Imagen base | Puerto(s) | Comando |
|----------|------------|-----------|---------|
| **backend** | `python:3.12-slim` | 8000 (WSGI), 8001 (FastAPI) | Script `start.sh` que lanza ambos servidores |
| **website** | `node:22-alpine` | 3000 | `next dev -p 3000` |
| **backoffice** | `node:22-alpine` | 3001 | `next dev -p 3001` |
| **postgres** (opcional) | `postgres:16-alpine` | 5432 | Imagen oficial |

### 2.3 Red

- Red virtual `brasaland-net` (creada por defecto por docker-compose)
- Los servicios se comunican por nombre de servicio (`backend`, `backoffice`, `postgres`)
- `website` NO necesita comunicación con backend (es estático)

### 2.4 Volúmenes (hot-reload)

| Servicio | Montaje bind | Propósito |
|----------|-------------|-----------|
| backend | `./services/brasaland_api/:/app/services/brasaland_api/` | Recarga con `--reload` de uvicorn |
| website | `./uis/website/:/app/` | Next.js dev server hot-reload |
| backoffice | `./uis/backoffice/:/app/` | Next.js dev server hot-reload |
| postgres | `pgdata:/var/lib/postgresql/data` | Persistencia de BD |

---

## 3. Archivos a crear

### 3.1 `.env` — Variables de entorno (raíz del repo)

Archivo ignorado por git (`.env` ya está en `.gitignore`). Contiene todos los secretos y configuración.

```env
# ─── Backend ──────────────────────────────────────────────
JWT_SECRET_KEY=desarrollo-cambiar-en-produccion-123456
JWT_EXPIRE_MINUTES=60
RESET_TOKEN_EXPIRE_MINUTES=15

SEED_ADMIN_EMAIL=admin@brasaland.com
SEED_ADMIN_PASSWORD=Admin1234

FRONTEND_URL=http://localhost:3000

# Resend (email) — opcional en desarrollo
RESEND_API_KEY=

# ─── PostgreSQL (Inventario Hito 5) ──────────────────────
# Por defecto apunta al contenedor postgres local
DATABASE_URL=postgresql://brasaland:brasaland_dev@postgres:5432/brasaland

# ─── Backoffice (URLs internas Docker) ────────────────────
INCIDENTS_ANALYZE_BACKEND_URL=http://backend:8000
INCIDENTS_BACKEND_BASE_URL=http://backend:8001
SUPPLIERS_BACKEND_BASE_URL=http://backend:8001

# ─── PostgreSQL credentials (para el servicio postgres) ───
POSTGRES_DB=brasaland
POSTGRES_USER=brasaland
POSTGRES_PASSWORD=brasaland_dev
```

### 3.2 `services/Dockerfile` — Imagen del backend

```dockerfile
# services/Dockerfile
FROM python:3.12-slim

# Evitar .pyc y buffers
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Dependencias del sistema (psycopg2 necesita gcc/libpq)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copiar e instalar dependencias Python
COPY services/brasaland_api/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el código de la API
COPY services/brasaland_api/ ./services/brasaland_api/
COPY services/__init__.py ./services/__init__.py
COPY packages/ ./packages/

# Script de arranque
COPY services/start.sh /start.sh
RUN chmod +x /start.sh

EXPOSE 8000 8001

CMD ["/start.sh"]
```

### 3.3 `services/start.sh` — Script de arranque del backend

```bash
#!/bin/sh
# start.sh — Lanza el servidor WSGI (incidencias) y el FastAPI (uvicorn)
# en segundo plano. Atrapa SIGTERM para apagado graceful.

set -e

echo "=== Iniciando servidor WSGI (incidencias) en puerto 8000 ==="
python3 /app/services/brasaland_api/app.py &
PID_WSGI=$!

echo "=== Iniciando FastAPI (uvicorn) en puerto 8001 ==="
cd /app
python3 -m uvicorn services.brasaland_api.main:app \
    --host 0.0.0.0 \
    --port 8001 \
    --reload &
PID_UVICORN=$!

# Trap SIGTERM: apagar ambos procesos
trap 'echo "Apagando..."; kill $PID_WSGI $PID_UVICORN 2>/dev/null; exit 0' INT TERM

# Esperar a que cualquier proceso hijo termine
wait
```

### 3.4 `services/.dockerignore`

```
__pycache__/
*.pyc
*.pyo
.env
.git
```

### 3.5 `uis/Dockerfile` — Imagen compartida para UIs Next.js

```dockerfile
# uis/Dockerfile
FROM node:22-alpine

WORKDIR /app

# Exponer puertos de desarrollo
EXPOSE 3000 3001
```

Nota: El comando de arranque se define en `docker-compose.yml` para cada servicio (website y backoffice).

### 3.6 `uis/.dockerignore`

```
node_modules/
.next/
.env
.git
```

### 3.7 `docker-compose.yml` — Orquestación principal

```yaml
# docker-compose.yml
services:

  # ─── Backend Python (FastAPI + WSGI) ───────────────────
  backend:
    build:
      context: .
      dockerfile: services/Dockerfile
    container_name: brasaland-backend
    ports:
      - "8000:8000"   # WSGI (incidencias analyze/export)
      - "8001:8001"   # FastAPI (auth, suppliers, incidents CRUD, inventory)
    env_file: .env
    volumes:
      - ./services/brasaland_api/:/app/services/brasaland_api/
      - ./packages/:/app/packages/
    depends_on:
      postgres:
        condition: service_healthy
    networks:
      - brasaland-net

  # ─── PostgreSQL (Inventario Hito 5) ────────────────────
  postgres:
    image: postgres:16-alpine
    container_name: brasaland-postgres
    environment:
      POSTGRES_DB: ${POSTGRES_DB:-brasaland}
      POSTGRES_USER: ${POSTGRES_USER:-brasaland}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-brasaland_dev}
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER:-brasaland} -d ${POSTGRES_DB:-brasaland}"]
      interval: 5s
      timeout: 5s
      retries: 10
    networks:
      - brasaland-net

  # ─── Frontend: Web pública ─────────────────────────────
  website:
    build:
      context: ./uis
      dockerfile: Dockerfile
    container_name: brasaland-website
    command: sh -c "npm install && npm run dev -- -p 3000"
    ports:
      - "3000:3000"
    volumes:
      - ./uis/website/:/app/
      - /app/node_modules/
    networks:
      - brasaland-net

  # ─── Frontend: Backoffice (panel admin) ────────────────
  backoffice:
    build:
      context: ./uis
      dockerfile: Dockerfile
    container_name: brasaland-backoffice
    command: sh -c "npm install && npm run dev -- -p 3001"
    ports:
      - "3001:3001"
    volumes:
      - ./uis/backoffice/:/app/
      - /app/node_modules/
    env_file: .env
    depends_on:
      - backend
    networks:
      - brasaland-net

volumes:
  pgdata:

networks:
  brasaland-net:
    driver: bridge
```

---

## 4. Archivos a modificar

### 4.1 `uis/backoffice/next.config.ts` — Rewrite de autenticación

**Problema**: Tiene `127.0.0.1:8001` hardcodeado.

**Solución**: Usar variable de entorno con fallback.

```typescript
// Antes:
destination: "http://127.0.0.1:8001/auth/:path*",

// Después:
destination: `${process.env.AUTH_BACKEND_BASE_URL ?? "http://127.0.0.1:8001"}/auth/:path*`,
```

Y añadir al `.env`:
```env
AUTH_BACKEND_BASE_URL=http://backend:8001
```

### 4.2 `uis/backoffice/app/api/incidents/analyze/route.ts` — Puerto 8000

**Problema**: Usa `INCIDENTS_BACKEND_BASE_URL` con fallback a `127.0.0.1:8000`, pero el mismo env var se usa para puerto 8001 en otros routes.

**Solución**: Cambiar a `INCIDENTS_ANALYZE_BACKEND_URL` (nuevo env var específico).

```typescript
const BACKEND_BASE =
  process.env.INCIDENTS_ANALYZE_BACKEND_URL ?? "http://127.0.0.1:8000";
```

### 4.3 `uis/backoffice/app/api/incidents/results/export/route.ts` — Puerto 8000

Mismo cambio que 4.2:

```typescript
const BACKEND_BASE =
  process.env.INCIDENTS_ANALYZE_BACKEND_URL ?? "http://127.0.0.1:8000";
```

### 4.4 `uis/backoffice/app/api/incidents/route.ts` — Puerto 8001

**No requiere cambio de código**: Usa `INCIDENTS_BACKEND_BASE_URL` con fallback a `127.0.0.1:8001`. En Docker se inyecta `INCIDENTS_BACKEND_BASE_URL=http://backend:8001` via `.env`.

### 4.5–4.9 Routes restantes

| Archivo | Env var | Fallback actual | Docker value |
|---------|---------|-----------------|--------------|
| `incidents/[id]/route.ts` | `INCIDENTS_BACKEND_BASE_URL` | `127.0.0.1:8001` | `http://backend:8001` ✅ |
| `incidents/[id]/status/route.ts` | `INCIDENTS_BACKEND_BASE_URL` | `127.0.0.1:8001` | `http://backend:8001` ✅ |
| `suppliers/route.ts` | `SUPPLIERS_BACKEND_BASE_URL` | `127.0.0.1:8001` | `http://backend:8001` ✅ |
| `suppliers/[id]/route.ts` | `SUPPLIERS_BACKEND_BASE_URL` | `127.0.0.1:8001` | `http://backend:8001` ✅ |
| `suppliers/[id]/rate/route.ts` | `SUPPLIERS_BACKEND_BASE_URL` | `127.0.0.1:8001` | `http://backend:8001` ✅ |
| `suppliers/[id]/status/route.ts` | `SUPPLIERS_BACKEND_BASE_URL` | `127.0.0.1:8001` | `http://backend:8001` ✅ |

Todos ellos ya usan env vars con fallback razonable. **Solo necesitan que el `.env` esté bien configurado**. No requieren cambios de código.

### Resumen de archivos a modificar

| Archivo | Tipo de cambio |
|---------|---------------|
| `uis/backoffice/next.config.ts` | Usar env var para `AUTH_BACKEND_BASE_URL` |
| `uis/backoffice/app/api/incidents/analyze/route.ts` | Cambiar a `INCIDENTS_ANALYZE_BACKEND_URL` |
| `uis/backoffice/app/api/incidents/results/export/route.ts` | Cambiar a `INCIDENTS_ANALYZE_BACKEND_URL` |

---

## 5. Variables de entorno

### 5.1 Inventario completo de env vars

| Variable | ¿Requerida? | Default | Servicio | Propósito |
|----------|:-----------:|---------|----------|-----------|
| `JWT_SECRET_KEY` | ✅ Sí | *(ninguno)* | backend | Firma de tokens JWT |
| `JWT_EXPIRE_MINUTES` | ❌ No | `60` | backend | Duración del access token |
| `RESET_TOKEN_EXPIRE_MINUTES` | ❌ No | `15` | backend | Duración del reset token |
| `SEED_ADMIN_EMAIL` | ❌ No | `admin@brasaland.com` | backend | Email del admin inicial |
| `SEED_ADMIN_PASSWORD` | ❌ No | `Admin1234` | backend | Password del admin inicial |
| `FRONTEND_URL` | ❌ No | `http://localhost:3000` | backend | CORS / enlaces de email |
| `RESEND_API_KEY` | ❌ No | *(vacío)* | backend | API key para emails |
| `DATABASE_URL` | ⚠️ Según uso | *(ninguno)* | backend | Conexión PostgreSQL (inventario) |
| `INCIDENTS_ANALYZE_BACKEND_URL` | ❌ No *(nueva)* | `http://127.0.0.1:8000` | backoffice | URL del WSGI de incidencias |
| `INCIDENTS_BACKEND_BASE_URL` | ❌ No | `http://127.0.0.1:8001` | backoffice | URL del FastAPI (incidencias CRUD) |
| `SUPPLIERS_BACKEND_BASE_URL` | ❌ No | `http://127.0.0.1:8001` | backoffice | URL del FastAPI (proveedores) |
| `AUTH_BACKEND_BASE_URL` | ❌ No *(nueva)* | `http://127.0.0.1:8001` | backoffice | URL del FastAPI (auth) |

### 5.2 Flujo de resolución de URLs en Docker

```
Backoffice (Next.js :3001)
│
├── next.config.ts rewrite
│   /api/auth/* ─────────────────────────▶ http://backend:8001/auth/*
│
├── API Routes (server-side fetch)
│   /api/incidents/analyze  ─────────────▶ http://backend:8000/api/incidents/analyze
│   /api/incidents/results/export ──────▶ http://backend:8000/api/incidents/results/export
│   /api/incidents           ────────────▶ http://backend:8001/incidents
│   /api/incidents/:id       ────────────▶ http://backend:8001/incidents/:id
│   /api/incidents/:id/status ──────────▶ http://backend:8001/incidents/:id/status
│   /api/suppliers           ────────────▶ http://backend:8001/suppliers
│   /api/suppliers/:id       ────────────▶ http://backend:8001/suppliers/:id
│   /api/suppliers/:id/rate  ────────────▶ http://backend:8001/suppliers/:id/rate
│   /api/suppliers/:id/status ──────────▶ http://backend:8001/suppliers/:id/status
```

---

## 6. Plan de ejecución paso a paso

Este plan se ejecutará secuencialmente, **solo tras tu aprobación en cada paso**.

### Fase 0 — Preparación (1 paso)

- [ ] **Paso 0.1**: Crear rama `feat/docker-containerization` desde `main`

### Fase 1 — Archivos nuevos (6 pasos)

- [ ] **Paso 1.1**: Crear `.env` con valores por defecto para desarrollo
- [ ] **Paso 1.2**: Crear `services/Dockerfile` (imagen Python 3.12-slim)
- [ ] **Paso 1.3**: Crear `services/start.sh` (script que lanza WSGI + uvicorn)
- [ ] **Paso 1.4**: Crear `services/.dockerignore`
- [ ] **Paso 1.5**: Crear `uis/Dockerfile` (imagen Node 22-alpine)
- [ ] **Paso 1.6**: Crear `uis/.dockerignore`

### Fase 2 — Modificaciones de código (3 pasos)

- [ ] **Paso 2.1**: Modificar `uis/backoffice/next.config.ts` — usar env var en rewrite
- [ ] **Paso 2.2**: Modificar `uis/backoffice/app/api/incidents/analyze/route.ts` — usar `INCIDENTS_ANALYZE_BACKEND_URL`
- [ ] **Paso 2.3**: Modificar `uis/backoffice/app/api/incidents/results/export/route.ts` — usar `INCIDENTS_ANALYZE_BACKEND_URL`

### Fase 3 — Orquestación (1 paso)

- [ ] **Paso 3.1**: Crear `docker-compose.yml` con todos los servicios

### Fase 4 — Verificación (3 pasos)

- [ ] **Paso 4.1**: Build de imágenes y arranque con `docker compose up --build`
- [ ] **Paso 4.2**: Verificar conectividad entre servicios
- [ ] **Paso 4.3**: Commit y push, crear PR

---

## 7. Verificación

### 7.1 Pruebas de humo post-Docker

```bash
# 1. Build y arranque
docker compose up --build -d

# 2. Logs de cada servicio
docker compose logs -f backend
docker compose logs -f backoffice
docker compose logs -f website

# 3. Health checks
curl http://localhost:3000                    # Website público
curl http://localhost:3001                    # Backoffice (debe redirigir o dar 200)
curl http://localhost:8001/                   # FastAPI → {"service":"brasaland-api","status":"ok"}
curl http://localhost:8000/                   # WSGI → {"service":"incidents-api","status":"ok"}
curl http://localhost:5432                    # PostgreSQL (debe responder)

# 4. Probar login (full-stack)
curl -X POST http://localhost:3001/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin@brasaland.com","password":"Admin1234"}'

# 5. Probar proveedores (proxy backoffice → backend)
curl http://localhost:3001/api/suppliers

# 6. Probar incidencias
curl http://localhost:3001/api/incidents
```

### 7.2 Hot-reload

```bash
# Tras modificar un archivo Python, debe recargar automáticamente:
docker compose restart backend
# o esperar a que uvicorn --reload detecte el cambio

# Tras modificar un archivo React/Next.js, debe recargar automáticamente:
# (Next.js dev server detecta cambios vía bind mount)
```

---

## 8. Preguntas abiertas y decisiones pendientes

| # | Pregunta | Alternativas |
|---|----------|-------------|
| 1 | **¿PostgreSQL en contenedor o usar Supabase externo?** | Opción A: Contenedor `postgres:16-alpine` con `DATABASE_URL` local. Opción B: Usar Supabase externo y no incluir Postgres en compose. |
| 2 | **¿Dos contenedores para backend o uno con ambos servidores?** | Opción A (actual en el plan): `start.sh` lanza ambos en un contenedor. Opción B: Contenedores separados `backend-wsgi` y `backend-fastapi`. |
| 3 | **¿Incluir Redis/celery para async?** | No hay evidencia de necesidad actual. Se omite. |
| 4 | **¿Exponer Postgres al host?** | Recomiendo sí (puerto 5432) para herramientas como DBeaver, pgAdmin. Ya incluido en el plan. |
| 5 | **Volumen anónimo vs nombrado para node_modules?** | En el plan uso `/app/node_modules/` (anónimo) para evitar sobrescribir con el bind mount. Es la práctica recomendada. |

---

> **Siguiente paso**: Revisa este plan y dime por qué paso empezamos. Aprobaremos cada fase secuencialmente.