# NIST Cybersecurity Framework — Checklist de Implementación

> **Proyecto:** Compliance / Seguridad en IA — Brasaland
> **Fecha:** 2026-11-23
> **Rama:** `feature/compliance-ai-security`
> **Propósito:** Verificar el estado de cada control NIST CSF 2.0 en los sistemas de IA de Brasaland.

---

## Leyenda

| Símbolo | Significado |
|---------|-------------|
| ✅ | Implementado y verificado |
| ⚠️ | Parcialmente implementado |
| ❌ | No implementado |
| 🔲 | No aplica / fuera de alcance |

---

## 1. Govern (Gobernanza)

| ID | Control | Estado | Evidencia |
|----|---------|--------|-----------|
| GV.OC-01 | Política de seguridad documentada y comunicada | ✅ | `docs/security/nist-ai-report.md` §1.1 |
| GV.OC-02 | Roles y responsabilidades de seguridad asignados | ✅ | `docs/security/nist-ai-report.md` §1.2 |
| GV.RM-01 | Marco regulatorio identificado (Ley 1581, FIPA) | ✅ | `docs/security/nist-ai-report.md` §1.3 |
| GV.RM-02 | Responsabilidad de terceros definida | ✅ | `docs/security/nist-ai-report.md` §1.4 |
| GV.SC-01 | Supply chain / terceros identificados en el inventario | ✅ | `docs/security/nist-ai-report.md` §1.4 |
| GV.SC-04 | Controles sobre componentes de terceros (Qdrant, LLM, Supabase) | ✅ | `docs/security/nist-ai-report.md` §1.4 + `env/` para credenciales |

---

## 2. Identify (Identificar)

| ID | Control | Estado | Evidencia |
|----|---------|--------|-----------|
| ID.AM-01 | Inventario completo de sistemas IA | ✅ | `docs/security/nist-ai-report.md` §2.1 (5 sistemas) |
| ID.AM-02 | Responsable asignado por componente | ✅ | `docs/security/nist-ai-report.md` §2.1 (Squad Backend/Frontend) |
| ID.AM-03 | Datos sensibles identificados y catalogados | ✅ | `docs/security/nist-ai-report.md` §2.2 |
| ID.AM-04 | Superficie de ataque mapeada (puntos de input al LLM) | ✅ | `docs/security/nist-ai-report.md` §2.3 |
| ID.RA-01 | Riesgos identificados por componente | ✅ | `docs/security/nist-ai-report.md` §2.1 (columna Riesgo Principal) |
| ID.RA-02 | Evaluación de impacto de datos personales | ✅ | Ley 1581 / FIPA aplicados por tipo de dato |

---

## 3. Protect (Proteger)

| ID | Control | Estado | Evidencia |
|----|---------|--------|-----------|
| PR.AC-01 | Control de acceso (mínimo privilegio) | ✅ | MCP scopes: `inventory:read`, `incidents:read/write` separados |
| PR.AC-02 | Autenticación MCP habilitada (OAuth 2.1) | ✅ | `env/mcp` → `MCP_AUTH_DISABLED=0` |
| PR.AC-03 | CORS restringido a orígenes conocidos | ✅ | `services/brasaland_api/main.py` — orígenes locales únicamente |
| PR.AC-04 | Sin credenciales hardcodeadas | ✅ | Todos los secretos vía variables de entorno (`env/*.example`) |
| PR.AC-05 | Usuario no-root en servidor | ✅ | `infra/hardening/init-hardening.sh` |
| PR.AC-06 | SSH root login deshabilitado | ✅ | `infra/hardening/init-hardening.sh` |
| PR.AC-07 | Firewall UFW (solo puertos 22, 80, 443) | ✅ | `infra/hardening/init-hardening.sh` |
| PR.DS-01 | Protección contra prompt injection indirecta | ✅ | `data/pipelines/rag_safety.py` — 26+ patrones |
| PR.DS-02 | Separación system prompt vs. contenido de usuario | ✅ | `agent.py` — `verify_system_prompt()` SHA-256 |
| PR.DS-03 | Sanitización de input de usuario antes del LLM | ✅ | `rag_safety.py` + guardrails en `harness.py` |
| PR.DS-04 | Rate limiting en endpoint de IA | ✅ | `services/brasaland_api/main.py` — 10 req/min |
| PR.AT-01 | Confirmación humana para acciones irreversibles | ✅ | `agents/support_agent/human_confirmation.py` |
| PR.AT-02 | Umbral de auto-aprobación configurado ($500 USD) | ✅ | `ThresholdConfig.AUTO_APPROVE_MAX_COST_USD = 500.0` |
| PR.AT-03 | Puertos Docker vinculados a 127.0.0.1 | ✅ | `docker-compose.yml` |
| PR.PS-01 | CSP headers en frontends | ❌ | Pendiente de implementar |
| PR.PS-02 | Política de complejidad de contraseñas | ❌ | Pendiente de implementar |

---

## 4. Detect (Detectar)

| ID | Control | Estado | Evidencia |
|----|---------|--------|-----------|
| DE.AE-01 | Logging de eventos de seguridad (RAG safety) | ✅ | `rag_safety.py` — `logging.warning` en chunks bloqueados |
| DE.AE-02 | Logging de confirmaciones humanas | ✅ | `human_confirmation.py` — `logging.warning` en acciones pendientes |
| DE.AE-03 | Logging de trazabilidad de agente (decisiones) | ✅ | `agent.py` — logging de tools, guardrails, resultados |
| DE.AE-04 | Logging de timing de API | ✅ | `main.py` — `api.timing` logger |
| DE.AE-05 | Detección de rate limiting excedido | ✅ | Rate limit middleware → `logging.warning` + HTTP 429 |
| DE.AE-06 | Alertas de stock bajo en inventario | ✅ | `src/hito2/inventory-alerts.ts` |
| DE.AE-07 | Detección automatizada de brechas de datos personales | ❌ | Pendiente — detección manual por ahora |
| DE.CM-01 | Monitoreo de accesos al MCP Server | ⚠️ | Logs de OAuth, sin dashboard de monitoreo |

---

## 5. Respond (Responder)

| ID | Control | Estado | Evidencia |
|----|---------|--------|-----------|
| RS.RP-01 | Plan de respuesta a incidentes documentado | ✅ | `docs/security/nist-ai-report.md` §5.1 (6 fases) |
| RS.RP-02 | Procedimiento de escalación según jurisdicción | ✅ | `docs/security/nist-ai-report.md` §5.2 |
| RS.CO-01 | Notificación a SIC (Colombia) documentada | ✅ | Ley 1581 — "a la mayor brevedad posible" |
| RS.CO-02 | Notificación a Attorney General (Florida) documentada | ✅ | FIPA — 30 días desde detección |
| RS.AN-01 | Clasificación de incidentes (brecha vs. no brecha) | ✅ | `docs/security/nist-ai-report.md` §5.2 |
| RS.MI-01 | Contención de componente afectado (aislar tool, revocar token) | ✅ | Documentado en plan de respuesta |
| RS.IM-01 | Post-mortem de incidentes | ⚠️ | Proceso documentado pero sin template formal |

---

## 6. Recover (Recuperar)

| ID | Control | Estado | Evidencia |
|----|---------|--------|-----------|
| RC.RP-01 | Procedimientos de restauración documentados | ✅ | `docs/security/nist-ai-report.md` §6.1 |
| RC.RP-02 | Backup de base de conocimiento Qdrant | ✅ | Script `setup(force_recreate=True)` |
| RC.RP-03 | Backup de TinyDB (incidentes, proveedores) | ⚠️ | Manual — copia de archivos JSON |
| RC.RP-04 | Backup de PostgreSQL (inventario, RFP) | ❌ | Pendiente — sin backup automatizado |
| RC.RP-05 | Backup de variables de entorno | ⚠️ | Archivos gitignored — depende de copia externa |
| RC.RP-06 | Rollback de agentes vía git | ✅ | `git revert` + redeploy |
| RC.CO-01 | Plan de continuidad para fallo de Qdrant | ✅ | Fallback a supervisor manual |
| RC.CO-02 | Plan de continuidad para fallo de MCP | ✅ | Respuesta "servicio no disponible temporalmente" |
| RC.CO-03 | Plan de continuidad para fallo de PostgreSQL | ⚠️ | Operaciones continúa con registros manuales |
| RC.CO-04 | Plan de continuidad para brecha de seguridad | ✅ | Activar plan de respuesta + notificar autoridades |

---

## Resumen

| Función NIST | ✅ Implementado | ⚠️ Parcial | ❌ Pendiente | 🔲 N/A |
|-------------|----------------|------------|-------------|--------|
| **Govern** | 6 | 0 | 0 | 0 |
| **Identify** | 6 | 0 | 0 | 0 |
| **Protect** | 13 | 0 | 2 | 0 |
| **Detect** | 6 | 1 | 1 | 0 |
| **Respond** | 6 | 1 | 0 | 0 |
| **Recover** | 5 | 3 | 1 | 0 |
| **Total** | **42** | **5** | **4** | **0** |

**Total de controles evaluados:** 51
**Implementados:** 42 (82%)
**Parciales:** 5 (10%)
**Pendientes:** 4 (8%)

> ⚠️ Los 4 controles pendientes están documentados en `docs/security/nist-ai-report.md` §8 (Brechas Identificadas No Corregidas).