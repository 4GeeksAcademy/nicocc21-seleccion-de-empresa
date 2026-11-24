# Línea Base de Seguridad — Brasaland

> Documento de estado actual antes de la auditoría OWASP Top 10.
> Fecha: 2026-11-23
> Rama: `feature/owasp-top10-audit`

---

## 1. Acceso al Servidor (SSH)

| Aspecto | Estado actual |
|---------|---------------|
| Usuario de acceso | **No documentado** — sin archivo `ssh_config` en el repo |
| Login root directo | **No verificado** — no hay configuración SSH en el repositorio |
| Autenticación SSH | Depende del entorno de despliegue |
| Usuario no-root dedicado | **No existe configuración** en el repositorio |

> **Hallazgo:** No hay configuración SSH versionada. El servidor puede estar usando root por defecto. Sin acceso al servidor real no se puede verificar, pero la ausencia de configuración es un riesgo.

---

## 2. Puertos Expuestos (Docker Compose)

Basado en `docker-compose.yml` y `services/Dockerfile`:

| Servicio | Puerto(s) | Expuesto en host | Propósito |
|----------|-----------|------------------|-----------|
| PostgreSQL | 5432 | ✅ `5432:5432` | Base de datos inventario |
| Backend (WSGI) | 8000 | ✅ `8000:8000` | Incidencias analyze/export |
| Backend (FastAPI) | 8001 | ✅ `8001:8001` | Auth, suppliers, incidents CRUD, inventory |
| Frontend Web | 3000 | ✅ `3000:3000` | Web pública Next.js |
| Frontend Backoffice | 3001 | ✅ `3001:3001` | Panel admin interno |
| Qdrant (REST) | 6333 | ✅ `6333:6333` | API vectorial |
| Qdrant (Dashboard) | 6334 | ✅ `6334:6334` | UI administración Qdrant |
| MCP Server | 8081 | ❌ No en compose | Tools MCP (incidencias, inventario) |

> **Hallazgo:** PostgreSQL (5432), Qdrant (6333, 6334) están expuestos al host. Son servicios que no deberían ser accesibles desde internet. El MCP Server (8081) no está en el compose pero se levanta por separado con `MCP_AUTH_DISABLED=1`.

---

## 3. Firewall

| Aspecto | Estado actual |
|---------|---------------|
| Firewall activo | **No configurado** en el repositorio |
| Reglas de entrada | Sin definir |
| Reglas de salida | Sin definir |
| Puertos bloqueados | Ninguno documentado |

> **Hallazgo:** No existe configuración de firewall (iptables, ufw, nftables) en el repositorio. No hay restricción de puertos.

---

## 4. Autenticación y Autorización

### 4.1 API Backend (FastAPI)

| Aspecto | Estado |
|---------|--------|
| JWT Secret Key | ✅ Requerida en `.env` |
| CORS | ⚠️ `allow_origins=["*"]` — cualquier origen permitido |
| OAuth2 | ✅ Implementado con `OAuth2PasswordBearer` |
| Token expiry | 60 min (acceso), 15 min (reset) |
| Hash de contraseñas | ✅ bcrypt |

### 4.2 MCP Server

| Aspecto | Estado |
|---------|--------|
| Auth middleware | ✅ Implementado con validación de scopes |
| Modo desarrollo | ⚠️ `MCP_AUTH_DISABLED=1` en `env/mcp` — **sin autenticación** |
| Scopes definidos | `incidents:read`, `incidents:write`, `inventory:read` |
| Principio mínimo privilegio | ✅ Inventory tools son read-only con rechazo explícito de escritura |

> **Hallazgo crítico:** En desarrollo, el MCP Server se ejecuta con `MCP_AUTH_DISABLED=1`, lo que permite acceso sin token a todas las tools, incluyendo escritura de incidencias.

### 4.3 Agente de Soporte

| Aspecto | Estado |
|---------|--------|
| SecurityGuardrail | ✅ Detecta jailbreak/prompt injection (3 niveles: CRITICAL, HIGH, LOW) |
| DomainClassifier | ✅ Clasifica intención del usuario (JAILBREAK, SENSITIVE, PERSONAL, DOMAIN, etc.) |
| ContentGuardrail | ✅ Detecta fuga de datos en respuestas |
| System prompt fingerprint | ✅ SHA-256 hash y fingerprint marker |
| MCP Client | ✅ Usa `BrasalandMCPClient` con autenticación |

---

## 5. Almacenamiento de Secretos

| Secreto | ¿En repositorio? |
|---------|------------------|
| `JWT_SECRET_KEY` | ❌ Solo en `.env.example` (vacío) |
| `RESEND_API_KEY` | ❌ Solo en `.env.example` (vacío) |
| `DATABASE_URL` | ❌ Solo en `.env.example` (placeholder) |
| `GEMINI_API_KEY` | ❌ Solo en `.env.example` (vacío) |
| `OAUTH_CLIENT_SECRET` | ⚠️ `dev-secret-change-in-prod` en `env/mcp` |
| `MCP_CLIENT_SECRET` | ⚠️ `dev-secret-change-in-prod` en `env/mcp` |

> **Hallazgo:** Secretos de desarrollo hardcodeados en `env/mcp` (`dev-secret-change-in-prod`). Aunque no es un secreto real, indica que en desarrollo no hay validación fuerte.

---

## 6. Dependencias y Versiones

| Componente | Versión | Notas |
|------------|---------|-------|
| Python | 3.12-slim | Docker |
| Node.js | 22-alpine | Docker |
| PostgreSQL | 16-alpine | Docker |
| Qdrant | latest | Docker |
| FastAPI | v0.3.0 | Sin versión pin específica |
| JWT Algorithm | HS256 | Simétrico |

---

## 7. Inventario de Sistemas de IA

| Componente | Estado | Riesgo principal |
|------------|--------|------------------|
| Agente de soporte (LangGraph) | ✅ Implementado | Excessive agency si tiene acceso a escritura |
| Asistente RAG (entrenamiento) | ✅ Implementado | Prompt injection indirecta |
| MCP Server (incidentes/inventario) | ✅ Implementado | MCP_AUTH_DISABLED en dev |
| Dashboard SSE en tiempo real | ⚠️ Implementado en backoffice | Exposición de datos |
| Pipeline pedidos a proveedor | 📝 Sugerido por IA | Acción de alto impacto económico |

---

## 8. Cumplimiento Regulatorio

| Normativa | Aplica | Datos afectados |
|-----------|--------|-----------------|
| Ley 1581 de 2012 (Colombia) | ✅ Sí | Datos clientes Brasa Points, empleados, proveedores |
| FIPA (Florida, EE. UU.) | ✅ Sí | Datos clientes en locales L08-L10, L14 |

---

## Resumen de Hallazgos Críticos

| # | Hallazgo | Componente | Severidad |
|---|----------|-----------|-----------|
| H1 | `CORS: allow_origins=["*"]` | Backend FastAPI | 🔴 Alta |
| H2 | `MCP_AUTH_DISABLED=1` en desarrollo | MCP Server | 🔴 Alta |
| H3 | PostgreSQL expuesto en host (5432) | Docker Compose | 🔴 Alta |
| H4 | Qdrant expuesto en host (6333, 6334) | Docker Compose | 🔴 Alta |
| H5 | Sin configuración de firewall | Servidor | 🔴 Alta |
| H6 | Sin usuario no-root documentado | Servidor | 🟡 Media |
| H7 | Secretos hardcodeados en dev (`dev-secret-change-in-prod`) | MCP Config | 🟡 Media |
| H8 | JWT con algoritmo simétrico HS256 | Backend Auth | 🟡 Media |