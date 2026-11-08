# AI Engineering Company Project — Student Template

[![4Geeks Academy](https://img.shields.io/badge/4Geeks-Academy-blue)](https://4geeksacademy.com)
[![AI Engineering](https://img.shields.io/badge/track-AI%20Engineering-green)](https://4geeksacademy.com/es/programas-de-carrera/ingenieria-ia)

_Base template for transversal projects in the AI Engineering Career Program — 4Geeks Academy._

> _Instrucciones disponibles en español en [README.es.md](./README.es.md)._

---

## Purpose

This repository is the **starter template** for transversal projects. You will work on real company scenarios (Brasaland, TrackFlow, Nexova), building deliverables that map to course milestones (Web, Programming, Backend, Telemetry, RAG, Agents, Workflows, Real-time).

- Create a template from this repository.
- Replace the placeholder `CONTEXT.md` with your assigned company context.
- Use `skills/` and the directory-level `README.md` files as working guidance.

### Active structure in this repository

To keep the explorer clean and easier to read:

- Hito UI pages and web assets now live in `web/`.
- TypeScript Hito business logic remains in `src/`.
- General documentation stays at root (`README`, `CONTEXT`) and `docs/`.
- Base template folders were grouped under `template/`.

---

## Current status of the template

The repository currently provides a **base folder structure and documentation skeleton**. It does not include runnable apps or global scripts yet.

- `CONTEXT.md` is a placeholder and must be replaced with your assigned company context.
- There is no root `AGENTS.md` yet.
- Shared package metadata exists in `packages/shared/package.json` (`@repo/shared-types`), but no workspace runner is configured at root.

---

## Repository structure

```text
ai-engineering-company-project-monorepo/
├── README.md
├── README.es.md
├── CONTEXT.md                # Placeholder to be replaced with assigned context
├── agents/                   # Agent patterns/templates and tools docs
├── data/                     # raw, process, pipelines, eval
├── docs/                     # Project and architecture documentation
├── infra/                    # Docker, Terraform, deployment configs
├── internal/                 # CLIs, packaged migration scripts, internal utilities
├── mcps/                     # Model Context Protocol (MCP) Servers
├── packages/
│   └── shared/               # Shared package (@repo/shared-types)
├── scripts/                  # Script conventions/documentation
├── services/                 # APIs and background workers
├── shared/                   # Shared assets/conventions at repo level
├── skills/                   # Reusable agent skills
├── uis/                      # User interfaces (React, Next.js, Streamlit, HTML)
└── workflows/                # Automation/orchestration documentation
```

---

## How to start

1. **Use this repository as a template** and create your own project repo.
2. **Clone** your repository (or open it in Codespaces).
3. **Replace** `CONTEXT.md` with the full context for your assigned company.
4. **Review** each top-level folder `README.md` to understand intended responsibilities (`uis/`, `services/`, `data/`, `skills/`, etc.).
5. **Start implementing** milestone deliverables in `uis/` and `services/`, reusing `packages/shared/` and `data/` as needed.

---

## Async tasks (DEV-55 — Redis + Celery)

El proyecto usa **Celery** con **Redis** como broker y backend de resultados para desacoplar operaciones pesadas de la API.

### Dependencias

- `celery`, `redis`, `flower` — instalados en `pyproject.toml` / `requirements.txt`.

### Infraestructura (Docker)

| Servicio | Puerto | Descripción |
|----------|--------|-------------|
| `redis`  | `6379` | Broker y result backend. Política `noeviction`. |
| `worker` | —      | Proceso independiente que consume la cola. |
| `flower` | `5555` | Monitor web de la cola (solo desarrollo). |

### Cómo levantar

```bash
# Todo junto (Redis + API + worker + Flower)
docker compose up --build

# O solo Redis si ejecutas el worker fuera de Docker:
docker compose up -d redis

# Worker local (requiere Redis corriendo y REDIS_URL configurada)
celery -A services.celery_app worker --loglevel=INFO

# Flower local
celery -A services.celery_app flower --port=5555
```

### Cómo detener

```bash
docker compose down
# Si el worker corre local: Ctrl+C
```

### Endpoints

- **`POST /reporting/pipeline-runs`** — encola un run del pipeline semanal y devuelve `202 Accepted` con `task_id`.
- **`GET /tasks/{task_id}`** — devuelve el estado (`pending`, `started`, `success`, `failure`) y el resultado si está disponible.

### Reintentos y Dead Letter Queue

- La tarea `run_weekly_pipeline` reintenta hasta 3 veces con backoff exponencial (`retry_backoff=2`).
- Tras 3 fallos consecutivos, se registra en la tabla `reporting.dead_letter_entries` de PostgreSQL con: `task_id`, `task_name`, `attempt`, `error`, `failed_at`.

### Observabilidad

- Señales de Celery (`task_prerun`, `task_postrun`, `task_failure`) registran cada tarea con `task_id`, nombre, estado y duración.
- Flower muestra tareas encoladas, en proceso y completadas.

---

## Milestones (reference)

| Milestone | Focus        | Typical deliverables                        |
| --------- | ------------ | ------------------------------------------- |
| 0         | Prework      | Environment setup, first prompts            |
| 1         | Web          | Corporate website, forms, SEO               |
| 2         | Programming  | Business logic, scoring, calculations       |
| 3         | AI-driven UI | AI-generated interfaces                     |
| 4         | Next.js      | Portals, loyalty app, operations UI         |
| 5         | Backend      | Central API (locations, menus, sales, etc.) |
| 6         | Telemetry    | Data pipeline, dashboards                   |
| 7         | RAG & Memory | Semantic knowledge base, search             |
| 8         | Agents       | Support, onboarding, training agents        |
| 9         | Workflows    | n8n automations                             |
| 10        | Real-time    | Live dashboards, alerts, streaming          |

---

## Links

- [4Geeks Academy — AI Engineering](https://4geeksacademy.com/es/programas-de-carrera/ingenieria-ia)
- [How to start a coding project](https://4geeks.com/lesson/how-to-start-a-project)

---

## Contributors

This template was built as part of the 4Geeks Academy AI Engineering Career Program by [@marcogonzalo](https://www.linkedin.com/in/marcogonzalo) and [@alezanchezr](https://x.com/alesanchezr) and many other contributors. Find out more about our [AI Engineering Course](https://4geeksacademy.com/en/career-programs/ai-engineering), and [other courses](https://4geeksacademy.com/en/program-comparison).

You can find other templates and resources like this at the [4Geeks Academy GitHub page](https://github.com/4geeksacademy).

_This template is maintained by 4Geeks Academy for the AI Engineering track. For exclusive use in the programme._
