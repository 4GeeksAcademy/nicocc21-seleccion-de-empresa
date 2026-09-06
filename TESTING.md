# Pruebas de AUTH-088

Esta batería valida la lógica de autenticación existente de Brasaland. No depende de servicios externos, no envía correos reales y no usa la base TinyDB persistente.

## Alcance

- **Backend FastAPI** (25 tests, pytest): hashing, JWT, registro, login, sesión, recuperación, reset y cambio de contraseña. Cobertura ≥ 95 % en `auth.py`.
- **Cliente TypeScript** (31 tests, Jest): gestión de token (`getToken`, `setToken`, `removeToken`, `isAuthenticated`), login, registro, `loginAfterRegister`, `getMe`, `changePassword`, `forgotPassword`, `resetPassword`, `updateProfile`, `authFetch`, `logout`.
- Se prueban las decisiones de negocio y los errores. La serialización interna de FastAPI no es el objetivo de la cobertura.

## Evidencia del flujo asistido por IA

Durante la revisión asistida por IA se detectó que los primeros tests de autenticación dependían de `TestClient`, `status_code` y `response.json()`. Se refactorizaron para llamar directamente a las funciones de negocio y afirmar modelos, mensajes, tokens consumidos y contraseñas actualizadas. La batería ayudó a descubrir esta desviación del criterio de evaluación antes de la entrega.

## Preparación

Instala las dependencias del proyecto:

```bash
uv sync
npm install
```

Configura una clave exclusiva para pruebas:

```bash
export JWT_SECRET_KEY="clave-local-de-pruebas"
```

## Ejecución

Backend (desde la raíz del proyecto):

```bash
uv run pytest
JWT_SECRET_KEY="clave-local-de-pruebas" uv run pytest --cov=services.brasaland_api.auth --cov-report=term-missing
```

TypeScript:

```bash
npm test
npm run test:coverage
```

## API-042 — Endpoints del backoffice

Se añadieron 11 pruebas unitarias para dos grupos distintos de endpoints no relacionados con autenticación:

- **Perfiles** (`tests/test_profiles.py`): creación, consulta, actualización y decisiones de perfil duplicado o inexistente. Cobertura: **82%**.
- **Proveedores** (`tests/test_suppliers.py`): creación, listado filtrado, actualización de tarifa/estado, consulta inexistente y fallo de almacenamiento. Cobertura: **67%**.

La cobertura combinada de los dos routers es **72%**, por encima del objetivo mínimo del 60%. Las pruebas llaman directamente a las funciones de los routers y verifican resultados de negocio o errores traducidos; no prueban serialización HTTP, rutas, headers, cuerpos ni internals de FastAPI.

```bash
JWT_SECRET_KEY="clave-local-de-pruebas" uv run pytest \
	tests/test_profiles.py tests/test_suppliers.py \
	--cov=services.brasaland_api.routes.profiles \
	--cov=services.brasaland_api.routes.suppliers \
	--cov-report=term-missing
```

## FE-019 — Utilidades del frontend

La app `uis/talent-pipeline-tracker/` incluye una suite Jest independiente en [`__tests__/api.test.ts`](uis/talent-pipeline-tracker/__tests__/api.test.ts). Cubre cuatro helpers del cliente de talento, cada uno con camino feliz y modo de fallo:

- `getCandidates`: devuelve resultados paginados y traduce errores de consulta.
- `getCandidateById`: devuelve un candidato y convierte fallos de conexión en errores útiles.
- `createCandidate`: devuelve el candidato creado y rechaza respuestas con formato inválido.
- `updateCandidate`: devuelve el candidato actualizado y extrae mensajes de validación.

Resultado actual: **8 tests pasan**. La cobertura se mide sobre `src/lib/api.ts`.

Ejecutar solo la suite del frontend:

```bash
cd uis/talent-pipeline-tracker
npm test
npm run test:coverage
```

## Casos cubiertos — Cliente TypeScript (Jest)

Cada función del cliente tiene camino feliz y modo de fallo, además de casos adicionales para ramas de error:

| Función | Tests | Camino feliz | Modo fallo |
|---|---|---|---|
| `getToken` / `setToken` / `removeToken` / `isAuthenticated` | 1 | Guarda, recupera y elimina el token | — |
| `login` | 3 | Credenciales válidas → `access_token` | 401 → lanza `detail`; JSON inválido → "Error de conexión" |
| `register` | 2 | Registro JSON → `UserOut` | 409 → lanza `detail`; JSON inválido → "Error de conexión" |
| `loginAfterRegister` | 1 | Llama a `login` con email como username | — |
| `getMe` | 4 | Token válido → `UserMeOut` | Sin sesión → "No hay sesión activa"; 401 → elimina token; 500 → "Error al obtener perfil" |
| `changePassword` | 5 | Sesión activa → `MessageResponse` | Sin sesión → "No hay sesión activa"; 401 → elimina token; 400 → lanza `detail`; JSON inválido → "Error de conexión" |
| `forgotPassword` | 3 | Email existente → 200 OK | 404 → "Usuario no encontrado"; JSON inválido → "Error de conexión" |
| `resetPassword` | 3 | Token válido → 200 OK | 400 → "Token inválido"; JSON inválido → "Error de conexión" |
| `authFetch` | 4 | Sin token → 200; con token → incluye Bearer | 401 con token → redirige; 401 sin token → no redirige |
| `updateProfile` | 4 | Sesión activa + PUT → `ProfileOut` | Sin sesión → "No hay sesión activa"; 401 → elimina token; 500 → "Error al actualizar perfil" |
| `logout` | 1 | Elimina token y redirige a /login | — |

## Casos cubiertos — Backend (pytest)

Cada endpoint contempla camino feliz, límite y fallo:

| Endpoint | Casos principales | Por qué se incluyen |
|---|---|---|
| `POST /auth/register` | Camino feliz: alta. Límite: contraseña vacía/corta. Fallo: email duplicado. | Comprueba el alta normal, la validación de credenciales mínimas y la protección contra cuentas duplicadas. |
| `POST /auth/login` | Camino feliz: credenciales válidas. Límite: contraseña vacía. Fallo: usuario o contraseña incorrectos. | Verifica el acceso normal, la validación de entrada y el rechazo de autenticaciones no autorizadas. |
| `GET /auth/me` | Camino feliz: token válido. Límite: perfil opcional. Fallo: token expirado o ausente. | Confirma que la sesión válida devuelve el usuario, que el perfil puede faltar y que los tokens inválidos no conceden acceso. |
| `POST /auth/forgot-password` | Camino feliz: usuario existente. Límite: email vacío o desconocido. Fallo controlado: error del servicio de email. | Comprueba la recuperación normal, evita la enumeración de usuarios y confirma que un fallo externo no expone un error interno. |
| `POST /auth/reset-password` | Camino feliz: reset válido. Límite: contraseña igual a la actual. Fallo: token reutilizado o inválido. | Verifica el cambio seguro, evita reutilizar credenciales y garantiza que los enlaces inválidos o usados no funcionen. |
| `POST /auth/change-password` | Camino feliz: cambio válido. Límite: reutilización de contraseña. Fallo: contraseña actual incorrecta o sesión ausente. | Confirma que solo un usuario autenticado puede cambiar su clave y que no se aceptan credenciales incorrectas o repetidas. |

Las pruebas Python usan `tmp_path` para TinyDB, fixtures independientes y mocks de `send_reset_email`. Las pruebas Jest sustituyen `fetch`, `localStorage` y `window.location` con `MemoryStorage` y `createFetchMock`.

## Cobertura

La cobertura relevante para este ticket se mide sobre `services/brasaland_api/auth.py` y `src/auth/auth-client.ts` y debe superar el 70 %:

```bash
JWT_SECRET_KEY="clave-local-de-pruebas" uv run pytest --cov=services.brasaland_api.auth --cov-report=term-missing
npm run test:coverage
```