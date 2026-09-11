# PLAN — Hito 5: Gestión de Inventario Backend (Brasaland)

## 1. Resumen Ejecutivo

**Objetivo:** Construir la capa centralizada de gestión de inventario de la plataforma Brasaland Digital. Por primera vez, la cadena tendrá una única fuente de verdad sobre el stock de ingredientes en sus 14 locales.

**Stack técnico:** FastAPI + SQLModel (Supabase PostgreSQL) + TinyDB + Pydantic + psycopg2

**Arquitectura de doble base de datos:**
- **TinyDB** (existente) → Usuarios, autenticación, proveedores, incidencias
- **Supabase (PostgreSQL)** (nuevo) → Inventario: Ingredient, IngredientEntry, IngredientExit

**Ubicación:** Todo el código nuevo se integra dentro de `services/brasaland_api/`, siguiendo la estructura existente del proyecto.

---

## ✅ ESTADO ACTUAL (Refinado a nivel academia)

Todo implementado, probado end-to-end y refinado:

| Componente | Estado |
|-----------|--------|
| Conexión Supabase (PostgreSQL 17.6) | ✅ |
| Modelos ORM (`inventory_models.py`) | ✅ con campos de negocio |
| Engine SQLModel + `get_db` | ✅ doble conexión (TinyDB + Supabase) |
| `SQLModel.metadata.create_all` al inicio | ✅ vía `create_db_and_tables()` en `lifespan` |
| Schemas Pydantic separados | ✅ `schemas.py` |
| Router `/inventory` (6 endpoints) | ✅ con auth JWT real |
| **Auth JWT** en POST (products, inbound, outbound) | ✅ `user_uuid` del token, no del body |
| **Dominio alineado CONTEXT.md** | ✅ categorías `comida/bebida/empaque`, razones `consumo/merma` |
| **Campos de negocio** `stock_minimo`, `perecedero`, `dias_vida_util`, `frecuencia_rotacion_dias` | ✅ |
| **Filtros** por `categoria` y `pais` | ✅ |
| **Documentación OpenAPI** descriptiva con `summary`, `description`, `responses` | ✅ |
| Seed idempotente | ✅ |
| `.env.example` actualizado | ✅ |

## 2. Estructura de Archivos (Nuevos y Modificados)

### 2.1 Archivos a crear

| # | Archivo | Propósito |
|---|---------|-----------|
| 1 | `services/brasaland_api/routes/inventory.py` | Router con todos los endpoints `/inventory/*` |
| 2 | `services/brasaland_api/schemas.py` | Schemas Pydantic de request/response para inventario |

### 2.2 Archivos a modificar

| # | Archivo | Cambio |
|---|---------|--------|
| 1 | `services/brasaland_api/database.py` | Añadir motor SQLModel (SQLite) + sesión + dependencia `get_db` |
| 2 | `services/brasaland_api/models.py` | Añadir modelos SQLModel: `Ingredient`, `IngredientEntry`, `IngredientExit` |
| 3 | `services/brasaland_api/seed.py` | Añadir seed de datos de inventario (ingredients, entries, exits) |
| 4 | `services/brasaland_api/main.py` | Importar y registrar `inventory_router` |
| 5 | `pyproject.toml` | Añadir `sqlmodel` a dependencias |

---

## 3. Diseño de Base de Datos (SQLModel + Supabase PostgreSQL)

### 3.1 Modelo `Ingredient`

| Campo | Tipo | Notas |
|-------|------|-------|
| `id` | `int` (PK) | Autoincremental |
| `name` | `str` | Ej.: "Falda de ternera" |
| `sku` | `str` | Único, ej.: "BRS-BEEF-001" |
| `unit` | `str` | "kg", "litro", "unidad" |
| `category` | `str` | Alineado CONTEXT: "comida", "bebida", "empaque" |
| `country` | `str` | "CO" o "US" |
| `stock_minimo` | `float` | Stock mínimo antes de generar alerta |
| `perecedero` | `bool` | ¿Es perecedero? |
| `dias_vida_util` | `int` | Días de vida útil desde recepción |
| `frecuencia_rotacion_dias` | `int` | Ciclo de rotación (7=perecedero, 15=bebidas) |

**`current_stock`** → Campo calculado, NO almacenado. Se calcula como:
```sql
SUM(IngredientEntry.quantity) - SUM(IngredientExit.quantity)
```

### 3.2 Modelo `IngredientEntry`

| Campo | Tipo | Notas |
|-------|------|-------|
| `id` | `int` (PK) | Autoincremental |
| `ingredient_id` | `int` (FK → Ingredient) | |
| `quantity` | `float` | Cantidad recibida |
| `supplier_name` | `str` | Nombre del proveedor |
| `location_id` | `int` | 1–14 (no FK) |
| `created_at` | `datetime` | Auto |
| `user_uuid` | `str` | UUID de TinyDB |

### 3.3 Modelo `IngredientExit`

| Campo | Tipo | Notas |
|-------|------|-------|
| `id` | `int` (PK) | Autoincremental |
| `ingredient_id` | `int` (FK → Ingredient) | |
| `quantity` | `float` | Cantidad consumida/mermada |
| `reason` | `str` | "consumption" o "waste" |
| `location_id` | `int` | 1–14 (no FK) |
| `created_at` | `datetime` | Auto |
| `user_uuid` | `str` | UUID de TinyDB |

---

## 4. Endpoints de la API

### 4.1 Registro del Router

Todos los endpoints bajo prefijo `/inventory`. Router ubicado en:
`services/brasaland_api/routes/inventory.py`

### 4.2 Tabla de Endpoints

| Método | Ruta | Función | Descripción |
|--------|------|---------|-------------|
| `GET` | `/inventory/products` | `list_products` | Lista ingredientes con `current_stock` |
| `POST` | `/inventory/products` | `create_product` | Crea nuevo ingrediente |
| `GET` | `/inventory/products/{id}` | `get_product` | Obtiene ingrediente con stock actual |
| `POST` | `/inventory/orders/inbound` | `create_inbound` | Registra entrega (IngredientEntry) |
| `POST` | `/inventory/orders/outbound` | `create_outbound` | Registra consumo/merma (IngredientExit) |
| `GET` | `/inventory/orders` | `list_orders` | Lista entradas y salidas con datos del ingrediente |

### 4.3 Schemas Pydantic

Archivo: `services/brasaland_api/schemas.py`

**Request schemas:**
- `IngredientCreate` — name, sku, unit, category, country
- `IngredientEntryCreate` — ingredient_id, quantity, supplier_name, location_id, user_uuid
- `IngredientExitCreate` — ingredient_id, quantity, reason ("consumption"|"waste"), location_id, user_uuid

**Response schemas:**
- `IngredientOut` — id, name, sku, unit, category, country, current_stock (float)
- `IngredientEntryOut` — id, ingredient_id, quantity, supplier_name, location_id, created_at, user_uuid, ingredient_name
- `IngredientExitOut` — id, ingredient_id, quantity, reason, location_id, created_at, user_uuid, ingredient_name
- `IngredientOrderOut` — Union[IngredientEntryOut, IngredientExitOut] con un campo `type` para distinguir

---

## 5. Reglas de Negocio (Implementación Crítica)

### Regla 1: `current_stock` calculado
```python
# En el endpoint GET /inventory/products/{id}
current_stock = sum(entries) - sum(exits)
# Se añade al schema de respuesta, NO se guarda en DB
```

### Regla 2: Validación de stock negativo en outbound
```python
# Antes de crear un IngredientExit:
stock_actual = calcular_stock(ingredient_id)
if stock_actual - quantity < 0:
    raise HTTPException(
        status_code=400,
        detail=f"Insufficient stock for ingredient '{name}'. Available: {available}, requested: {requested}."
    )
```

### Regla 3: País en modelo y respuesta
- Campo `country` presente en Ingredient (modelo) y en IngredientOut (schema)

### Regla 4: `reason` validado
- Solo acepta "consumption" o "waste" — validación Pydantic con `Literal` o `Field`

### Regla 5: Sin tabla User
- `user_uuid` es solo un string, referencia a TinyDB. No crear modelo User en SQLModel.

### Regla 6: Location IDs 1-14
- Solo enteros, sin FK, sin tabla de locales.

---

## 6. Datos Semilla

### 6.1 Ingredients (6)

| name | sku | unit | category | country |
|------|-----|------|----------|---------|
| Falda de ternera | BRS-BEEF-001 | kg | meat | CO |
| Costilla de cerdo | BRS-PORK-001 | kg | meat | US |
| Chimichurri | BRS-SAUCE-001 | litro | sauce | CO |
| Salsa BBQ de la casa | BRS-SAUCE-002 | litro | sauce | US |
| Yuca | BRS-PROD-001 | kg | produce | CO |
| Caja para llevar (M) | BRS-PKG-001 | unidad | packaging | CO |

### 6.2 IngredientEntries (4+)

| ingredient (sku) | quantity | supplier_name | location_id |
|-----------------|----------|---------------|-------------|
| BRS-BEEF-001 | 50 | Carnes del Valle S.A. | 1 |
| BRS-BEEF-001 | 30 | Carnes del Valle S.A. | 1 |
| BRS-PORK-001 | 40 | MiamiMeat Co. | 8 |
| BRS-SAUCE-001 | 100 | Salsas Artesanales Ltda. | 3 |

### 6.3 IngredientExits (3+)

| ingredient (sku) | quantity | reason | location_id |
|-----------------|----------|--------|-------------|
| BRS-BEEF-001 | 20 | consumption | 1 |
| BRS-BEEF-001 | 5 | waste | 1 |
| BRS-PORK-001 | 15 | consumption | 8 |

**Stock resultante tras seed:**
- Falda de ternera: 50 + 30 - 20 - 5 = **55 kg**
- Costilla de cerdo: 40 - 15 = **25 kg**
- Chimichurri: 100 - 0 = **100 litros**
- Otros: 0 (sin movimientos)

---

## 7. Plan de Implementación (Orden de Ejecución)

### Paso 1: Dependencias
- Ejecutar `uv add sqlmodel psycopg2-binary` (dentro del entorno)
- Añadir también a `pyproject.toml` y `requirements.txt` si no usa uv

### Paso 2: Configurar `.env` con DATABASE_URL
- Obtener cadena de conexión Supabase (Transaction pooler → URI)
- Añadir `DATABASE_URL=postgresql://...` al `.env`
- Mantener intacta `JWT_SECRET_KEY` y config de TinyDB

### Paso 3: Modelos SQLModel (`models.py`)
- Definir `Ingredient`, `IngredientEntry`, `IngredientExit` como tablas SQLModel
- Usar `table=True` y Field(foreign_key=...)
- No crear modelo User en SQLModel

### Paso 4: Conexión Supabase (`database.py`)
- Añadir `create_engine()` con `DATABASE_URL` de Supabase
- Crear dependencia `get_db()` que provea Session
- Mantener intactas TODAS las funciones TinyDB existentes

### Paso 5: Schemas Pydantic (`schemas.py`)
- Schemas de request (create) y response (out) para cada operación
- Separados de los modelos ORM — nunca devolver ORM directo

### Paso 6: Router de inventario (`routes/inventory.py`)
- Implementar los 6 endpoints
- Aplicar reglas de negocio (stock calculado, validación outbound, etc.)
- Prevenir problema N+1 en GET /inventory/orders (joins)

### Paso 7: Seed de datos contra Supabase (`seed.py`)
- Añadir `seed_inventory()` que cree tablas y registros en Supabase
- Ejecutar en el lifespan de la app

### Paso 8: Registrar router en `main.py`
- Importar `inventory_router` y añadirlo con `app.include_router()`

---

## 8. Criterios de Evaluación / Aceptación

- [ ] `GET /inventory/products` devuelve lista con `current_stock` correcto
- [ ] `POST /inventory/orders/outbound` con cantidad > stock disponible → HTTP 400
- [ ] Mensaje de error exacto: `"Insufficient stock for ingredient '{name}'. Available: {available}, requested: {requested}."`
- [ ] `reason` solo acepta "consumption" o "waste"
- [ ] `country` aparece en modelo y schema de respuesta
- [ ] Seed data presente al iniciar la app (6 ingredients, 4+ entries, 3+ exits)
- [ ] SQLModel + TinyDB coexisten en `database.py`
- [ ] Router bajo prefijo `/inventory`

---

## 9. Riesgos y Mitigaciones

| Riesgo | Mitigación |
|--------|------------|
| SQLModel no compatible con FastAPI lifespan | Usar `on_event("startup")` o manejar engine global |
| Conflictos entre TinyDB y SQLModel en `database.py` | Separar claramente: TinyDB functions → sección TinyDB, SQLModel → sección SQLModel |
| Seed duplicado en cada reinicio | Usar `if table.count() > 0: return` en seed |
| Dependencia circular en imports | Mantener imports locales dentro de funciones cuando sea necesario |

---

## 10. Notas Técnicas

- **SQLite path:** `services/brasaland_api/data/inventory.db`
- **Engine:** `sqlmodel.create_engine("sqlite:///...")`
- **get_db:** Dependencia FastAPI que provee sesión SQLModel
- **current_stock:** Se calcula con dos queries SUM agrupadas por ingredient_id
- **user_uuid:** Es solo un string campo, sin validación contra TinyDB en este hito