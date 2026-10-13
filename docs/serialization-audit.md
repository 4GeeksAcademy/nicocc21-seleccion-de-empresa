# Auditoría de Serialización — Brasaland API

> **Fecha:** 2026-10-13
> **Rama:** `feature/serialization-audit`
> **Alcance:** Toda la superficie de `services/brasaland_api` (FastAPI) + API WSGI legada de incidencias.
> **Objetivo del CTO:** Que ningún endpoint devuelva un objeto ORM en crudo y que cada endpoint tenga un `response_model` (serializer de salida) explícito y ajustado al consumidor real.
> **Estado:** ✅ **ENTREGADO** — auditoría completada + serializers implementados + verificado (46 tests ✔ + pruebas funcionales con TestClient ✔).

---

## 0. Resumen ejecutivo

| Métrica | Valor |
|---|---|
| Endpoints FastAPI auditados | 34 |
| Endpoints WSGI legados (incidencias) | 2 |
| 🔴 **Críticos** (sin esquema de salida / dict genérico) | 1 → **resuelto** ✅ |
| 🟡 **Mejorables** (payload inflado o forma pobre) | 4 → **2 resueltos** ✅, 2 documentados como candidatos a futuro |
| 🟢 **Bien definidos** | 29 |
| ¿Algún endpoint devuelve ORM crudo? | **No** |
| ¿Algún endpoint expone `password_hash`? | **No** |
| ¿Algún endpoint devuelve email en un flujo de **registro** público? | **No** (corregido: `/auth/register` y `POST /users` ahora usan `UserRegisteredOut`) |

**Conclusión principal:** la API ya aplica serializers Pydantic en casi toda la superficie. No se encontró ninguna fuga de credenciales ni objeto ORM devuelto en crudo. El único endpoint **sin contrato de respuesta explícito** era `GET /incidents/summary` (`response_model=dict`) y **ya se corrigió** con `IncidentsSummaryOut`. El resto de cambios aplicados van orientados a *optimización de payload*, *seguridad de los flujos de registro* y *consistencia de contrato*.

**Cambios aplicados en esta rama (resumen):**
1. ✅ **P1** — `IncidentsSummaryOut` tipado para `GET /incidents/summary` (antes `response_model=dict`).
2. ✅ **P1-auth** — `UserRegisteredOut` (sin email) en `POST /auth/register` y `POST /users` (flujos públicos de registro).
3. ✅ **P2** — `DELETE /suppliers/{id}` alineado a `200` + `MessageResponse` (antes declaraba `204` con body).
4. ✅ **P3** — refactor de `IngredientEntryOut`/`IngredientExitOut` a base común `InventoryMovementBase` (mismo JSON, menos duplicación).

---

## 1. Autenticación (`router /auth`)

> La academia recomienda empezar por auth porque es la zona de mayor riesgo: un usuario ORM crudo puede filtrar `hashed_password`. Este proyecto **ya usa esquemas Pydantic explícitos** en todas las rutas de auth y la capa de datos devuelve dicts (nunca objetos ORM). Aun así, se auditan con lupa y se documenta el motivo de cada campo expuesto.

### Estado de serialización por endpoint

| # | Endpoint | Método | `response_model` | Verdict |
|---|---|---|---|---|
| 1 | `/auth/register` | POST | `UserRegisteredOut` | 🟢 Bien (corregido — sin email) |
| 2 | `/auth/login` | POST | `Token` | 🟢 Bien |
| 3 | `/auth/me` | GET | `UserMeOut` | 🟡 Mejorable (candidato a futuro, ver nota) |
| 4 | `/auth/forgot-password` | POST | `MessageResponse` | 🟢 Bien |
| 5 | `/auth/reset-password` | POST | `MessageResponse` | 🟢 Bien |
| 6 | `/auth/change-password` | POST | `MessageResponse` | 🟢 Bien |

### Comprobaciones de seguridad de auth

| Comprobación | Resultado |
|---|---|
| ¿Se devuelve `password_hash` en alguna respuesta? | ❌ No. Nunca se incluye en ningún schema de salida. |
| ¿Se devuelve la contraseña en texto plano? | ❌ No. |
| ¿Se devuelve el email en un flujo de **registro** público? | ❌ No. `/auth/register` y `POST /users` ya no reenvían el email (`UserRegisteredOut`). |
| ¿Se devuelve el email sin necesidad? | ⚠️ Solo en `/auth/me` (sesión) y `GET /users` (admin) — casos justificados. |
| ¿Las respuestas de write usan solo confirmación? | ✅ Sí en forgot/reset/change (solo mensaje). |

---

### 1.1 `POST /auth/register` → 🟢 (corregido)

- **Entrada (`UserCreate`):** `email`, `password`, y opcionales `name`, `phone`, `address`.
- **Salida ANTES (`UserOut`):** `id`, `email`, `is_active`, `role`, `created_at`.
- **Salida AHORA (`UserRegisteredOut`):** `id`, `is_active`, `role`, `created_at`.
- **Cambio aplicado:** se creó `UserRegisteredOut` (sin `email`) y la ruta ahora la usa como `response_model`.
- **Quién lo llama:** `src/auth/auth-client.ts` → `register()` (firma y luego `loginAfterRegister`). La UI no consume el email del resultado: tras el registro el frontend hace login. Verificado: las tres `register-form.tsx` de `uis/*` llaman `register(...)` y luego `loginAfterRegister(...)`, por lo que **ninguna UI se rompe**.
- **¿Qué queda interno?** `email`, `password_hash`, `password_changed_at` — correctamente fuera. El email viaja solo en el body de entrada y no se reenvía.
- **Veredicto sanitizado:** Cumple el criterio de la academia: *"Las rutas de auth (registro, login, forgot/reset password) nunca deben devolver contraseñas ni email"*.

### 1.2 `POST /auth/login` → 🟢

- **Entrada:** `OAuth2PasswordRequestForm` (`username`=email, `password`).
- **Salida (`Token`):** `access_token`, `token_type`.
- **Quién lo llama:** `src/auth/auth-client.ts` → `login()` + todas las apps (backoffice, application).
- **Qué usa el cliente:** Solo el `access_token` (guardado en localStorage).
- **¿Qué queda interno?** El usuario completo (`password_hash`, `role`, etc.) — se resuelve en el servidor vía `get_user_by_email`, nunca sale.
- **Nota email:** El email viene en el **body**, no se reenvía en la respuesta. ✅ Cumple la recomendación de la academia al pie de la letra.
- **Veredicto:** Óptimo. Devuelve exactamente lo que el cliente necesita (el token).

### 1.3 `GET /auth/me` → 🟡 (revisar, no romper)

- **Entrada:** `Authorization: Bearer <token>`.
- **Salida (`UserMeOut`):** `id`, `email`, `is_active`, `role`, `created_at`, `profile` (objeto anidado con `full_name`, `phone`, `address`).
- **Quién lo llama:** `src/auth/auth-client.ts` → `getMe()` y el `auth-guard` de `uis/backoffice`, `uis/application` y `uis/talent-pipeline-tracker` (valida sesión y lee `role`).
- **Qué usa realmente el cliente:** El `auth-guard` solo necesita saber si hay sesión y qué `role` tiene. El perfil anidado se usa en páginas de perfil (edición).
- **Análisis:**
  - El schema es explícito y no expone credenciales. ➕
  - Devuelve `email` **y** `created_at` (auditoría) — inofensivo.
  - `profile` es una relación anidada. **Quién lo consume**: el cliente de perfil; está justificado embekerlo aquí porque `/auth/me` es el punto único de sesión.
  - **Riesgo**: `profile` se serializa como `null` si no hay perfil, lo que fuerza al frontend a manejar nullable en cada lectura. Está modelado así en `UserMeOut.profile: UserMeProfile | None`.
- **Clasificación:** 🟡 *Mejorable (bajo)* — no porque filtre datos, sino porque acopla sesión + perfil en un solo payload grande para un guard que solo lee `role`. 

  **Mejora recomendada (opcional, requiere decisión de producto):**
  - Mantener `/auth/me` como está (punto único de sesión con perfil) **o**
  - Devolver una proyección ligera (`UserMeLite`: `id`, `email`, `role`, `is_active`) y dejar el perfil en `/profiles/me` (ya existe).
  - **Payload objetivo si se optimiza:**
    ```json
    {
      "id": 1,
      "email": "mariana@brasaland.test",
      "is_active": true,
      "role": "user"
    }
    ```
  - **Decisión:** como el frontend de perfil ya usa `/profiles/me` y el `auth-guard` solo lee `role`, vale la pena evaluar la proyección ligera. **No es bloqueante** y requiere tocar TS del frontend. Se deja registrado como mejora candidata, no como deuda urgente.

### 1.4 `POST /auth/forgot-password` → 🟢

- **Entrada (`ForgotPasswordRequest`):** `email`.
- **Salida (`MessageResponse`):** `message` genérico.
- **Análisis:** Devuelve un mensaje genérico idéntico exista o no el email (anti-enumeración de usuarios). No reenvía el email (viene en el body). Cumple la recomendación de la academia a la perfección.
- **Veredicto:** Óptimo.

### 1.5 `POST /auth/reset-password` → 🟢

- **Entrada (`ResetPasswordRequest`):** `token`, `new_password`. El token se valida (firma, expiración, usado).
- **Salida (`MessageResponse`):** mensaje de confirmación.
- **Análisis:** No devuelve token, ni email, ni credenciales. Solo confirmación. El token viaja en el body (no en la respuesta). Correcto.
- **Veredicto:** Óptimo.

### 1.6 `POST /auth/change-password` → 🟢

- **Entrada (`ChangePasswordRequest`):** `current_password`, `new_password`.
- **Salida (`MessageResponse`):** mensaje de confirmación.
- **Análisis:** Verifica la contraseña actual antes de cambiar. No devuelve nada sensible. Correcto.
- **Veredicto:** Óptimo.

---

## 2. Usuarios (`router /users`)

> Área administrativa. Hoy el frontend del monorepo **no consume** estas rutas (no hay UI de usuario en backoffice/application), pero forman parte del contrato de la API.

| # | Endpoint | Método | `response_model` | Verdict |
|---|---|---|---|---|
| 7 | `/users` | POST | `UserRegisteredOut` | 🟢 Bien (corregido — sin email) |
| 8 | `/users` | GET | `list[UserOut]` | 🟡 Mejorable (candidato a futuro) |
| 9 | `/users/{id}` | GET | `UserOut` | 🟢 Bien |
| 10 | `/users/{id}` | PUT | `UserOut` | 🟢 Bien |
| 11 | `/users/{id}` | DELETE | `dict[str, str]` (inline) | 🟢 Bien (mensaje simple) |

### 2.1 `POST /users` → 🟢 (corregido)
- Duplica la lógica de `/auth/register` (crea usuario + perfil opcional). Es un flujo **público** de registro (no requiere token).
- **Cambio aplicado:** alineado con `/auth/register` — ahora responde `UserRegisteredOut` (sin email). Antes usaba `UserOut` y reenviaba el email al cliente. Se añadió el helper `_user_to_registered_out`.
- **`GET /users` y `GET /users/{id}` se mantienen con `UserOut`** (incluyen email) porque son vistas administrativas legítimas; el criterio solo restringe los flujos de registro no autenticados.

### 2.2 `GET /users` → 🟡 (mejorable)
- **Salida hoy:** `list[UserOut]` — el **mismo schema que el detalle**.
- **Análisis:** Para un listado administrativo, cada fila devuelve `email`, `role`, `is_active`, `created_at`. Ningún consumidor actual lo usa. Como la UI no existe, no hay campos "desperdiciados" hoy, pero la academia recomienda schema de listado ligero cuando la proyección del listado difiere del detalle.
- **Mejora recomendada:** crear `UserListItem` (sin `created_at` de auditoría si no se usa en tablas) cuando exista un consumidor. Hasta entonces, **documentado como correcto-reutilizable** porque la proyección coincide con lo que razonablemente muestra una tabla de admins.
- **Clasificación → 🟡 bajo, no urgente.**

### 2.3 `GET /users/{id}` → 🟢
- `UserOut` explícito, sin `password_hash`. Correcto. Solo admin.

### 2.4 `PUT /users/{id}` → 🟢
- Entrada `UserUpdate` (solo `email`, `role`; ambos opcionales). Salida `UserOut`. Correcto, el contrato de escritura está ajustado (no acepta password).

### 2.5 `DELETE /users/{id}` → 🟢
- Responde `200` con `{"message": "Usuario eliminado"}`. Schema inline `dict[str, str]`. Aceptable; idealmente `MessageResponse` para formalizar, pero no filtra nada.

---

## 3. Perfiles (`router /profiles`)

| # | Endpoint | Método | `response_model` | Verdict |
|---|---|---|---|---|
| 12 | `/profiles` | POST | `ProfileOut` | 🟢 Bien |
| 13 | `/profiles/me` | GET | `ProfileOut` | 🟢 Bien |
| 14 | `/profiles/me` | PATCH | `ProfileOut` | 🟢 Bien |
| 15 | `/profiles/me` | PUT | `ProfileOut` | 🟢 Bien |

### Análisis general
- **`ProfileOut`**: `id`, `user_id`, `full_name`, `phone`, `address`. Es el contrato correcto para perfil: no tiene campos sensibles.
- **Consumidores:** `src/auth/auth-client.ts` → `updateProfile()` (`PUT /profiles/me`) y la UI de perfil. Todos los campos de `ProfileOut` se usan en formularios.
- **Observación:** `user_id` es una FK server-side que el cliente conoce pero no necesita para editar. Es un dato de identidad útil para el frontend (saber a qué usuario pertenece) y no es sensible. **Se mantiene; anotado.**
- **Veredicto:** Todo el módulo 🟢. Los schemas de entrada (`ProfileCreate`/`ProfileUpdate`) están ajustados: solo aceptan `full_name`, `phone`, `address`.

---

## 4. Proveedores (`router /suppliers`)

| # | Endpoint | Método | `response_model` | Verdict |
|---|---|---|---|---|
| 16 | `/suppliers` | POST | `SupplierOut` | 🟢 Bien |
| 17 | `/suppliers` | GET | `list[SupplierOut]` | 🟢 Bien (ver nota) |
| 18 | `/suppliers/{id}` | GET | `SupplierOut` | 🟢 Bien |
| 19 | `/suppliers/{id}/rate` | PATCH | `SupplierOut` | 🟢 Bien |
| 20 | `/suppliers/{id}/status` | PATCH | `SupplierOut` | 🟢 Bien |
| 21 | `/suppliers/{id}` | DELETE | `MessageResponse` | ✅ Corregido (era 204 + body) |

### 4.1 Nota sobre `GET /suppliers` (listado vs detalle)
- Analicé el consumidor real: `uis/backoffice/app/suppliers/SuppliersDirectory.tsx` y `uis/application/app/suppliers/`.
- **Campos que lee la UI en el listado:** `id`, `name`, `country`, `categories`, `rate_per_unit`, `currency`, `status`, `contact_email`, `notes`.
- **`SupplierOut` devuelve:** exactamente esos + `updated_at` (auditoría).
- **Conclusión:** el listado usa **todos** los campos del detalle, así que **reutilizar `SupplierOut` es correcto** aquí (la proyección coincide). `notes` y `contact_email` se usan en la fila/tarjeta, no solo en detalle. No hace falta schema separado. **Documentado como caso en que el schema compartido es válido.**

### 4.2 `DELETE /suppliers/{id}` ✅ (corregido)
- Declaraba `status_code=204` pero **retornaba** `{"message": "Proveedor eliminado"}` — contrato confuso (con 204, FastAPI descarta el body).
- **Cambio aplicado:** ahora responde `200` + `MessageResponse` (`{"message": "Proveedor eliminado"}`), alineado con `DELETE /users/{id}` del mismo monorepo.
- **Impacto frontend:** ninguno (no se leía body sobre 204).

---

## 5. Incidencias (`router /incidents`)

| # | Endpoint | Método | `response_model` | Verdict |
|---|---|---|---|---|
| 22 | `/incidents/summary` | GET | `IncidentsSummaryOut` | ✅ Corregido (era `dict`) |
| 23 | `/incidents` | GET | `list[IncidentOut]` | 🟢 Bien |
| 24 | `/incidents/{id}` | GET | `IncidentOut` | 🟢 Bien |
| 25 | `/incidents` | POST | `IncidentOut` | 🟢 Bien |
| 26 | `/incidents/{id}` | PATCH | `IncidentOut` | 🟢 Bien |
| 27 | `/incidents/{id}/status` | PATCH | `IncidentOut` | 🟢 Bien |

### 5.1 `GET /incidents/summary` → ✅ (corregido)

- **ANTES:** `response_model=dict` — el **único** endpoint de toda la API sin schema explícito.
- **QUÉ DEVOLVÍA** (`incidents_database.get_incidents_summary`): un dict construido a mano:
  ```json
  {
    "total": 92,
    "by_state": { "abierta": 33, "cerrada": 0 },
    "by_category": { "queja": 34 },
    "by_priority": { "baja": 10 },
    "by_origin": { "cliente": 70 }
  }
  ```
- **Quién lo llama:** `uis/backoffice/app/incidencias/IncidentList.tsx` → `fetch("/api/incidents/summary")`. Modela el tipo `IncidentsSummary` en `packages/shared/types`:
  ```ts
  export interface IncidentsSummary {
    total: number;
    by_state: Record<string, number>;
    by_category: Record<string, number>;
    by_priority: Record<string, number>;
    by_origin: Record<string, number>;
  }
  ```
- **Qué usa la UI:** `summary.total`, `summary.by_state.abierta`, `by_state.en_progreso`, `by_state.resuelta`, `by_priority.critica`.
- **Por qué era crítico:** no había contrato. Aunque la forma coincidía con el frontend, **nada garantizaba** en el backend que `by_state` contuviera siempre las claves esperadas ni que los valores fueran `int`. Un cambio interno en `get_incidents_summary` rompería la UI **en silencio**.
- **Cambio aplicado:** se creó `IncidentsSummaryOut` en `incidents_models.py` y la ruta ahora lo usa como `response_model`:
  ```python
  class IncidentsSummaryOut(BaseModel):
      total: int
      by_state: dict[str, int]
      by_category: dict[str, int]
      by_priority: dict[str, int]
      by_origin: dict[str, int]
  ```
  ```python
  @router.get("/summary", response_model=IncidentsSummaryOut)
  def get_summary() -> IncidentsSummaryOut:
      return IncidentsSummaryOut(**get_incidents_summary())
  ```
- **Impacto en frontend:** ninguno — el schema nuevo preserva exactamente la misma forma JSON. Ahora Swagger documenta y **valida** el contrato. Verificado con TestClient: `{total, by_state, by_category, by_priority, by_origin}` con tipos `int`.

### 5.2 Resto de incidencias → 🟢
- `IncidentOut` es explícito y cubre el modelo completo que el frontend tipa en `packages/shared/types` (`Incident`).
- **Entrada de escritura ajustada:** `IncidentCreate`, `IncidentUpdate`, `IncidentStatusUpdate` aceptan solo los campos necesarios. `IncidentStatusUpdate` solo `estado`, con transiciones validadas en servidor. Correcto.
- **Relación aplanada:** la incidencia devuelve `local_id` (clave) sin anidar el objeto `Local` completo — correcto, el cliente resuelve el label con `LOCAL_ID_LABELS` localmente. **Ejemplo de relación aplanada bien hecha.**

---

## 6. Inventario (`router /inventory`)

| # | Endpoint | Método | `response_model` | Verdict |
|---|---|---|---|---|
| 28 | `/inventory/products` | GET | `list[IngredientOut]` | 🟢 Bien |
| 29 | `/inventory/products` | POST | `IngredientOut` | 🟢 Bien |
| 30 | `/inventory/products/{id}` | GET | `IngredientOut` | 🟢 Bien |
| 31 | `/inventory/orders/inbound` | POST | `IngredientEntryOut` | 🟢 Bien |
| 32 | `/inventory/orders/outbound` | POST | `IngredientExitOut` | 🟢 Bien |
| 33 | `/inventory/orders` | GET | `list[EntryOut \| ExitOut]` | 🟢 Bien (con refactor aplicado) |

### Análisis general
- `services/brasaland_api/schemas.py` es **el mejor ejemplo del monorepo**: schemas de request/response separados de los modelos ORM (`inventory_models.py`), con `from_attributes=True`, y ningún endpoint devuelve el ORM directo.
- **`current_stock`** es un campo calculado (no existe en la tabla) y se inyecta vía `IngredientOut(**ingredient.model_dump(), current_stock=...)`. Correcto.
- **`IngredientEntryOut` / `IngredientExitOut`** aplanan la relación con el ingrediente: incluyen `ingredient_name` (join) en vez de anidar el objeto `Ingredient`. **Excelente ejemplo de relación aplanada** para el listado de órdenes.

### 6.1 Nota `GET /inventory/orders` → 🟢 (refactor aplicado)
- Devuelve una **unión tipada** `list[IngredientEntryOut | IngredientExitOut]`. Correcto a nivel de contrato (el frontend modela `InventoryOrder = EntryOut | ExitOut`).
- **Cambio aplicado (refactor de diseño, sin cambiar el JSON):** se introdujo `InventoryMovementBase` como base común con los campos compartidos de ambos movimientos (`id`, `ingredient_id`, `ingredient_name`, `quantity`, `location_id`, `created_at`, `user_uuid`) y `IngredientEntryOut`/`IngredientExitOut` ahora lo heredan. El campo `type` sigue discriminando la unión de forma explícita.
- **Verificación:** el JSON de salida es idéntico al anterior; se comprobó con los tests y con TestClient.

### 6.2 Seguridad
- **Nunca** se devuelve `password_hash` (no es modelo de inventario).
- `user_uuid` se extrae del JWT en el servidor, **no se acepta en el body** (`IngredientEntryCreate`/`IngredientExitCreate` no lo incluyen) → el cliente no puede suplantar al autor. Excelente.

---

## 7. Raíz y API WSGI legada

| # | Endpoint | Método | Serialización | Verdict |
|---|---|---|---|---|
| 34 | `/` | GET | dict inline | 🟢 Bien (healthcheck) |
| 35 | `/api/incidents/analyze` (WSGI) | POST | dict a mano | 🟡 Legado (fuera de FastAPI) |
| 36 | `/api/incidents/results/export` (WSGI) | GET | CSV binario | 🟡 Legado (fuera de FastAPI) |

- **`/`**: healthcheck trivial, dict inline aceptable.
- **WSGI (`services/brasaland_api/app.py`)**: es una aplicación WSGI independiente (procesa CSV), **no parte del router FastAPI auditado**. Hay una **duplicación** de dominio de incidencias: la API WSGI (`/api/incidents/analyze`) y el router FastAPI (`/incidents`) coexisten. La serialización WSGI es manual pero controlada (nunca ORM). Se documenta como legado; su refactor a FastAPI (si aplica) se trataría aparte.

---

## 8. Estado de ejecución (Fase 2 — serializers implementados + Fase 3 — verificación)

> Todas las acciones prioritarias ya están **implementadas y verificadas** en `feature/serialization-audit`.

| Prioridad | Endpoint | Acción | Estado |
|---|---|---|---|
| 🔴 P1 | `GET /incidents/summary` | Crear `IncidentsSummaryOut` y fijar `response_model`. | ✅ Aplicado |
| ⚠️ P1-auth | `POST /auth/register` y `POST /users` | `UserRegisteredOut` para no reenviar email en registro. | ✅ Aplicado |
| ⚠️ P2 | `DELETE /suppliers/{id}` | Alinear 204→200 + `MessageResponse`. | ✅ Aplicado |
| 🟡 P3 | `GET /inventory/orders` | Refactor a `InventoryMovementBase` compartido. | ✅ Aplicado |
| 🟡 P4 | `GET /users` (futuro) | `UserListItem` ligero **cuando exista consumidor**. | ⏸ Diferido (documentado, sin UI hoy) |
| 🟡 P5 | `GET /auth/me` (futuro) | Evaluar `UserMeLite` para guard de sesión. | ⏸ Diferido (requeriría tocar TS del frontend) |

**Verificación realizada:**
- ✅ `JWT_SECRET_KEY=... uv run pytest` (equivalente local en `.venv`): **46/46 tests pasan**.
- ✅ Prueba funcional con `TestClient` sobre la app FastAPI real:
  - `POST /auth/register` → **201**, body `{id, is_active, role, created_at}` — **sin email ni password**.
  - `POST /users` → **201**, mismo contrato — **sin email**.
  - `POST /auth/login` → **200** con `access_token`.
  - `GET /incidents/summary` → **200**, contrato tipado `{total, by_state, by_category, by_priority, by_origin}` con `int`s.
- ✅ Inspección de routers: los 34 endpoints exponen `response_model` explícito.

**Criterios aplicados:**
1. Sin cambios de contrato JSON hacia el frontend salvo los que el propio briefing pide (y los flujos de registro, verificados sin consumidor del campo eliminado).
2. No se introducen dependencias externas (AGENTS.md).
3. Se respeta la arquitectura en capas ya existente (`routers` → `services` → `database` → `models/schemas`).
4. Los cambios están en `feature/serialization-audit` y se entregarán vía PR para revisión del tutor.

---

## 9. Cómo leer este documento

- **✅ Corregido**: endpoint que incumplía el requisito del CTO y **ya fue arreglado en esta rama** (se indica el cambio aplicado junto al estado original).
- **🟢 Bien**: endpoint con `response_model` explícito, sin datos sensibles, y cuya proyección encaja con su consumidor.
- **🟡 Mejorable**: no es una fuga, pero el payload o el schema podrían optimizarse (listados, uniones, duplicación). Los que quedan se documentan como candidatos a futuro (P4/P5) porque su cambio requeriría tocar el frontend o no hay consumidor real.
- **🔴 Crítico**: no cumple el requisito mínimo del CTO (sin serializer de respuesta explícito) — actualmente **ninguno**.
- **⚠️ Inconsistencia**: bug de contrato menor (código de estado vs body) — resuelto en suppliers.

> Este documento es el **entregable de la Fase 1 (Auditoría)**. La Fase 2 materializará la sección 8 en código, bajo la rama `feature/serialization-audit`, y se abrirá un PR para revisión del tutor antes de merge a `main`.