# Auditoría OWASP Top 10 — Brasaland

> Fecha: 2026-11-23
> Alcance: Backend (FastAPI), Frontend (Next.js), Sistema Agéntico (MCP + Support Agent)
> Ramalínea base: `feature/owasp-top10-audit`

---

## Resumen de resultados

| # | Categoría OWASP | Backend | Frontend | Sistema Agéntico | Severidad |
|---|-----------------|---------|----------|------------------|-----------|
| A01 | Broken Access Control | ⚠️ Medio | ✅ Bajo | 🔴 **Crítico** | 🔴 |
| A02 | Cryptographic Failures | ✅ Bajo | ✅ Bajo | ⚠️ Medio | 🟡 |
| A03 | Injection | ⚠️ Medio | ✅ Bajo | 🔴 **Crítico** | 🔴 |
| A04 | Insecure Design | ⚠️ Medio | ✅ Bajo | ⚠️ Medio | 🟡 |
| A05 | Security Misconfiguration | 🔴 **Crítico** | ⚠️ Medio | 🔴 **Crítico** | 🔴 |
| A06 | Vulnerable Components | ⚠️ Medio | ⚠️ Medio | ⚠️ Medio | 🟡 |
| A07 | Identification/Auth Failures | ✅ Bajo | ✅ Bajo | ✅ Bajo | 🟢 |
| A08 | Software/Data Integrity | ✅ Bajo | ✅ Bajo | ⚠️ Medio | 🟡 |
| A09 | Security Logging/Monitoring | ⚠️ Medio | ✅ Bajo | ⚠️ Medio | 🟡 |
| A10 | Server-Side Request Forgery | ✅ Bajo | N/A | ✅ Bajo | 🟢 |

---

## A01: Broken Access Control

### Backend
| Aspecto | Hallazgo | Severidad |
|---------|----------|-----------|
| CORS `allow_origins=["*"]` | ❌ **CORREGIDO** — Ahora limitado a localhost:3000, localhost:3001 | 🟠 Medio |
| Autenticación JWT requerida | ✅ Endpoints protegidos con `get_current_user` | 🟢 Bajo |
| Roles/permisos por endpoint | ❌ No implementado — todos los usuarios autenticados tienen acceso completo | 🟠 Medio |

**Evidencia:** `main.py` usa `allow_origins=["*"]` (corregido). `auth.py` implementa JWT pero no hay diferenciación de roles.

### Frontend
| Aspecto | Hallazgo | Severidad |
|---------|----------|-----------|
| Rutas protegidas | ✅ Backoffice requiere autenticación | 🟢 Bajo |
| Exposición de API keys en cliente | ❌ `NEXT_PUBLIC_TELEMETRY_ENDPOINT` expuesto | 🟢 Bajo |

### Sistema Agéntico — 🔴 Crítico
| Aspecto | Hallazgo | Severidad |
|---------|----------|-----------|
| MCP Server sin auth en dev | ❌ **CORREGIDO** — `MCP_AUTH_DISABLED=0` ahora | 🟠 Medio |
| Tools MCP de escritura | ⚠️ `create_incident`, `update_incident` requieren scope `incidents:write` | 🟢 Bajo |
| Agente puede ejecutar acciones sin supervisión | ❌ **Hallazgo:** El agente puede crear/actualizar incidencias sin confirmación humana | 🔴 **Crítico** |
| Pipeline de pedidos automáticos | ❌ **Hallazgo:** No existe confirmación humana para pedidos > umbral | 🔴 **Crítico** |

**Evidencia:** `agents/support_agent/agent.py` — el agente tiene tools de escritura. Las acciones irreversibles del briefing (sección 5) no tienen confirmación humana implementada.

---

## A02: Cryptographic Failures

### Backend
| Aspecto | Hallazgo | Severidad |
|---------|----------|-----------|
| JWT con HS256 (simétrico) | ⚠️ Algoritmo simétrico — si la clave se filtra, todos los tokens son forjables | 🟠 Medio |
| bcrypt para passwords | ✅ Hash seguro implementado | 🟢 Bajo |
| TLS/HTTPS | ❌ No configurado en Docker Compose — depende del proxy inverso | 🟠 Medio |
| Secretos en repo | ❌ **CORREGIDO** — `dev-secret-change-in-prod` en `env/mcp` documentado como riesgo | 🟡 Bajo |

**Evidencia:** `auth.py` usa `HS256` y `bcrypt`. No hay configuración de TLS en el repositorio.

### Frontend
| Aspecto | Hallazgo | Severidad |
|---------|----------|-----------|
| Datos de pago | ❌ No hay endpoints de pago implementados | 🟢 Bajo |
| API keys en cliente | ✅ Solo `NEXT_PUBLIC_` vars (por diseño público) | 🟢 Bajo |

### Sistema Agéntico
| Aspecto | Hallazgo | Severidad |
|---------|----------|-----------|
| API keys LLM | ⚠️ `GEMINI_API_KEY` en `.env` — nunca en repo | 🟢 Bajo |
| Credenciales POS | ❌ No hay credenciales POS en el repo | 🟢 Bajo |

---

## A03: Injection

### Backend
| Aspecto | Hallazgo | Severidad |
|---------|----------|-----------|
| SQL Injection (SQLModel) | ✅ SQLModel usa parámetros, no concatenación | 🟢 Bajo |
| TinyDB | ⚠️ TinyDB usa JSON plano — riesgo de inyección en campos no validados | 🟠 Medio |

**Evidencia:** `inventory_models.py` usa SQLModel con parámetros. TinyDB es JSON plano sin validación de esquema.

### Frontend
| Aspecto | Hallazgo | Severidad |
|---------|----------|-----------|
| XSS | ✅ React/Next.js escapa HTML por defecto | 🟢 Bajo |
| Input validation | ⚠️ No se auditaron formularios específicos | 🟢 Bajo |

### Sistema Agéntico — 🔴 Crítico
| Aspecto | Hallazgo | Severidad |
|---------|----------|-----------|
| Prompt injection (directa) | ✅ **PROTEGIDO** — SecurityGuardrail con 3 niveles de detección | 🟢 Bajo |
| Prompt injection (indirecta/RAG) | ⚠️ Documentos en base de conocimiento podrían contener instrucciones maliciosas | 🔴 **Crítico** |
| System prompt fingerprint | ✅ SHA-256 hash + fingerprint marker | 🟢 Bajo |

**Evidencia:** `security_guardrail.py` implementa detección de patrones CRITICAL, HIGH, LOW. `domain_classifier.py` clasifica JAILBREAK > SENSITIVE > PERSONAL > DOMAIN. **No hay protección contra prompt injection indirecta** a través de documentos RAG manipulados.

---

## A04: Insecure Design

### Backend
| Aspecto | Hallazgo | Severidad |
|---------|----------|-----------|
| Rate limiting | ❌ No implementado — cualquier cliente puede hacer peticiones ilimitadas | 🟠 Medio |
| Validación de entrada | ⚠️ `RequestValidationError` manejado globalmente | 🟢 Bajo |
| Límites de paginación | ❌ No verificado | 🟠 Medio |

### Frontend
| Aspecto | Hallazgo | Severidad |
|---------|----------|-----------|
| CSP (Content Security Policy) | ❌ No implementado | 🟠 Medio |

### Sistema Agéntico
| Aspecto | Hallazgo | Severidad |
|---------|----------|-----------|
| Límite de iteraciones generador-evaluador | ✅ Implementado (Parte 2 del Hito 9) | 🟢 Bajo |
| Arbitraje por reglas fijas | ✅ Triggers definidos (cost-vs-feasibility, setup-sla-breach, ceo-threshold) | 🟢 Bajo |

---

## A05: Security Misconfiguration — 🔴 Crítico

### Backend
| Aspecto | Antes | Después | Severidad |
|---------|-------|---------|-----------|
| CORS `allow_origins` | `["*"]` | `["http://localhost:*"]` | 🟢 **CORREGIDO** |
| Debug/Info endpoints | ⚠️ `/` expone info del servicio | No corregido | 🟡 Bajo |
| HTTP headers de seguridad | ❌ No configurados | Pendiente | 🟠 Medio |

### Frontend
| Aspecto | Hallazgo | Severidad |
|---------|----------|-----------|
| Server info expuesta | ✅ No expuesta | 🟢 Bajo |

### Sistema Agéntico — 🔴 Crítico antes
| Aspecto | Antes | Después | Severidad |
|---------|-------|---------|-----------|
| `MCP_AUTH_DISABLED` | `1` (sin autenticación) | `0` (auth requerida) | 🟢 **CORREGIDO** |
| Puertos expuestos (DB, Qdrant) | `0.0.0.0:5432`, `0.0.0.0:6333`, etc. | `127.0.0.1:...` | 🟢 **CORREGIDO** |

---

## A06: Vulnerable Components

| Componente | Versión | Vulnerabilidades conocidas |
|------------|---------|---------------------------|
| Python 3.12-slim | 3.12 | Sin CVE críticas conocidas |
| Node.js 22-alpine | 22 | Sin CVE críticas conocidas |
| PostgreSQL 16-alpine | 16 | Actualizar a 16.4+ para fixes de seguridad |
| Qdrant latest | latest | ⚠️ `latest` no es una versión fija — puede cambiar inesperadamente |
| FastAPI | v0.3.0 | ⚠️ Versión no pinned en requirements.txt |
| LangGraph | No especificada | ❌ No se puede verificar sin lock file |

---

## A07: Identification & Authentication Failures

| Aspecto | Hallazgo | Severidad |
|---------|----------|-----------|
| JWT expiry | ✅ 60 min acceso, 15 min reset | 🟢 Bajo |
| Password hashing | ✅ bcrypt | 🟢 Bajo |
| Account lockout | ❌ No implementado | 🟠 Medio |
| Password policy | ❌ No hay política de complejidad | 🟠 Medio |
| MFA | ❌ No implementado | 🟡 Bajo |

---

## A08: Software & Data Integrity

| Aspecto | Hallazgo | Severidad |
|---------|----------|-----------|
| Dependencias pinned | ⚠️ `latest` en Qdrant y algunas versiones no fijas | 🟠 Medio |
| CI/CD pipeline | ❌ No hay verificación de integridad de artefactos | 🟠 Medio |
| Hash de system prompt | ✅ SHA-256 verificado en agente | 🟢 Bajo |

---

## A09: Security Logging & Monitoring

| Aspecto | Hallazgo | Severidad |
|---------|----------|-----------|
| Timing middleware | ✅ Implementado en `main.py` | 🟢 Bajo |
| Telemetría de eventos | ✅ `api_request_completed` registrado | 🟢 Bajo |
| Log de accesos no autorizados | ⚠️ MCP loguea intentos fallidos | 🟢 Bajo |
| Alertas de seguridad | ❌ No implementado | 🟠 Medio |
| Logs centralizados | ❌ No configurado | 🟠 Medio |

---

## A10: Server-Side Request Forgery (SSRF)

| Aspecto | Hallazgo | Severidad |
|---------|----------|-----------|
| Backend no hace fetch externo | ✅ No hay endpoints que acepten URLs arbitrarias | 🟢 Bajo |
| Agente RAG usa Qdrant interno | ✅ Conexión solo a servicios internos | 🟢 Bajo |

---

## Acciones correctivas ya aplicadas

| # | Corrección | Archivo | Categoría OWASP |
|---|-----------|---------|-----------------|
| C1 | CORS restringido a orígenes específicos | `services/brasaland_api/main.py` | A01, A05 |
| C2 | Puertos de servicios vinculados a localhost | `docker-compose.yml` | A05 |
| C3 | MCP_AUTH_DISABLED=0 por defecto | `env/mcp`, `env/mcp.example` | A05, A01 |
| C4 | Script de hardening SSH/firewall creado | `infra/hardening/init-hardening.sh` | A05 |
| C5 | Documentación de línea base de seguridad | `docs/security/baseline-snapshot.md` | Todos |
| C6 | Filtro de prompt injection indirecta en RAG | `data/pipelines/rag_safety.py` | A03 |
| C7 | Confirmación humana para acciones irreversibles | `agents/support_agent/human_confirmation.py` | A01 |

## Vulnerabilidades críticas que requieren acción

| # | Vulnerabilidad | Categoría | Acción requerida | Prioridad | Estado |
|---|---------------|-----------|------------------|-----------|--------|
| V1 | Prompt injection indirecta vía RAG | A03 | Implementar filtrado de contenido en documentos subidos al knowledge base | 🔴 Alta | ✅ **CORREGIDO** |
| V2 | Agente puede ejecutar acciones sin confirmación humana | A01 | Implementar confirmation gate antes de acciones irreversibles (crear pedidos, modificar inventario) | 🔴 Alta | ✅ **CORREGIDO** |
| V3 | Sin rate limiting en API | A04 | Implementar middleware de rate limiting | 🟠 Media | ⬜ Pendiente |
| V4 | Sin Content Security Policy (CSP) | A04 | Añadir CSP headers en frontends Next.js | 🟠 Media | ⬜ Pendiente |
| V5 | Sin política de contraseñas | A07 | Implementar validación de complejidad en registro | 🟠 Media | ⬜ Pendiente |
| V6 | Versiones de dependencias no fijas | A06 | Pinear versiones de Qdrant y dependencias Python | 🟠 Media | ⬜ Pendiente |