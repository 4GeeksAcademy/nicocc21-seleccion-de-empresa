# Propuesta de Arquitectura de Backend — Brasaland

**Autor:** Nicolás CC21  
**Fecha:** 31 de julio de 2026  
**Estado:** Borrador para revisión del equipo de ingeniería

---

## 1. Contexto del negocio

Brasaland es una cadena de restaurantes de comida a la brasa con **14 sedes** distribuidas entre Colombia y Florida. Actualmente opera sin visibilidad centralizada: la dirección ejecutiva toma decisiones reactivas sin datos consolidados, y el equipo de operaciones no tiene control confiable del inventario ni de las alertas de stock.

El backend que vamos a construir debe servir a **dos frentes de negocio claros**:

- **Dirección Ejecutiva:** reportes financieros por local, filtros temporales, informes semanales automáticos.
- **Operaciones de restaurante:** gestión de inventario, alertas de faltantes y excesos, control de rotación por tipo de insumo.

Ambos frentes comparten las mismas entidades base (`Local`, `MovimientoFinanciero`, `Insumo`, `FechaEspecial`) y en el futuro un agente de IA (Yayo) consultará datos cruzados entre ambos módulos. El backend debe estar preparado para ese cruce sin requerir una reestructuración completa.

---

## 2. Patrón arquitectónico propuesto: Arquitectura en Capas (Layered Architecture)

### 2.1 ¿Qué es?

La arquitectura en capas organiza el código en niveles horizontales donde cada capa tiene una responsabilidad definida y solo puede depender de la capa inmediatamente inferior:

```
┌─────────────────────────────┐
│       Capa de Rutas         │  ← Define endpoints HTTP, valida entrada
├─────────────────────────────┤
│     Capa de Servicios       │  ← Contiene la lógica de negocio
├─────────────────────────────┤
│   Capa de Repositorios      │  ← Acceso a datos (BD, archivos, APIs externas)
├─────────────────────────────┤
│    Capa de Modelos          │  ← Definición de entidades y esquemas
└─────────────────────────────┘
```

### 2.2 ¿Por qué encaja con Brasaland?

| Característica del negocio | Por qué la arquitectura en capas encaja |
|---|---|
| Dos frentes independientes pero con datos compartidos | Las capas de servicios y repositorios se reutilizan entre ambos módulos sin duplicar lógica |
| Lógica de negocio definida (ya tenemos `types.ts`, `aggregations.ts`, `inventory-alerts.ts`) | La capa de servicios traduce esa lógica existente a endpoints, manteniendo separación clara |
| Futuro agente IA que consulta datos cruzados | La capa de repositorios abstractiona el acceso a datos, permitiendo que múltiples consumidores (API, agente, jobs) accedan a la misma información |
| Equipo que necesita claridad y rapidez de implementación | Es un patrón simple, ampliamente documentado en la comunidad de FastAPI y fácil de seguir por desarrolladores con diferentes niveles de experiencia |
| Datos simulados que eventualmente se conectarán a un POS real | La capa de repositorios permite cambiar la fuente de datos sin tocar la lógica de negocio |

### 2.3 ¿Por qué no otros patrones?

- **MVC (Model-View-Controller):** Diseñado para aplicaciones donde la vista se renderiza en el servidor. Nuestro frontend es un sistema separado (Next.js) que consume la API por HTTP. No necesitamos una capa de "vista" en el backend.
- **Serverless (Lambda/Functions):** Aunque factible para eventos puntuales, Brasaland necesita consultas cruzadas y lógica de negocio acumulativa (reportes semanales, alertas que dependen de múltiples entidades). La gestión de estado y la coherencia entre funciones dispersas aumentaría la complejidad innecesariamente en esta fase.
- **Arquitectura Hexagonal (Ports & Adapters):** Podría funcionar, pero introduce una abstracción (puertos/adaptadores) que, para el volumen actual de 14 sedes y dos módulos, añade una capa de complejidad que el equipo no necesita todavía. Si el sistema crece significativamente, esta migración es viable desde una arquitectura en capas bien estructurada.

---

## 3. Estructura de carpetas y módulos propuesta

La estructura sigue la convención estándar de proyectos FastAPI organizados por dominios. Investigando las prácticas habituales de la comunidad FastAPI, los patrones más comunes son:

- Agrupar los módulos de la aplicación bajo un directorio `app/`
- Separar routers (endpoints), esquemas (Pydantic models), modelos (BD), y servicios (lógica de negocio)
- Mantener un archivo `main.py` que orquesta la creación de la aplicación y el montaje de routers
- Usar un directorio `core/` o `config/` para configuración global, dependencias y settings

Siguiendo estas convenciones, la estructura propuesta para Brasaland sería:

```
backend/
├── main.py                          # Punto de entrada: crea la app FastAPI, monta routers
├── requirements.txt                 # Dependencias: fastapi, uvicorn, pydantic, etc.
├── .env                             # Variables de entorno (no se sube a repositorio)
│
├── core/                            # Configuración y dependencias compartidas
│   ├── __init__.py
│   ├── config.py                    # Settings de la aplicación (puerto, entorno, CORS origins)
│   └── dependencies.py              # Inyección de dependencias comunes
│
├── models/                          # Modelos de base de datos (SQLAlchemy o equivalentes)
│   ├── __init__.py
│   ├── local.py                     # Modelo Local
│   ├── movimiento_financiero.py     # Modelo MovimientoFinanciero
│   ├── insumo.py                    # Modelo Insumo
│   └── fecha_especial.py            # Modelo FechaEspecial
│
├── schemas/                         # Esquemas Pydantic para request/response
│   ├── __init__.py
│   ├── local.py                     # schemas de entrada/salida para Local
│   ├── movimiento.py                # schemas de entrada/salida para movimientos
│   ├── insumo.py                    # schemas de entrada/salida para insumos
│   ├── reporte.py                   # schemas para ReporteFinancieroLocal
│   └── alerta.py                    # schemas para AlertaInventario
│
├── services/                        # Lógica de negocio pura (sin dependencia de HTTP)
│   ├── __init__.py
│   ├── financiero.py                # generarReporteFinancieroPorLocal, filtrado por fechas
│   ├── inventario.py                # tieneStockBajo, calcularImpactoEnDemanda, alertas
│   └── reportes.py                  # Generación de informes semanales automáticos
│
├── repositories/                    # Acceso a datos (abstracción sobre fuente de datos)
│   ├── __init__.py
│   ├── local_repository.py          # CRUD de locales
│   ├── movimiento_repository.py     # Consultas de movimientos financieros
│   ├── insumo_repository.py         # Consultas de inventario
│   └── fecha_especial_repository.py # Consultas de fechas especiales
│
├── routers/                         # Endpoints agrupados por dominio
│   ├── __init__.py
│   ├── locales.py                   # Rutas de /api/locales
│   ├── movimientos.py               # Rutas de /api/movimientos
│   ├── inventario.py                # Rutas de /api/inventario
│   ├── reportes.py                  # Rutas de /api/reportes
│   └── alertas.py                   # Rutas de /api/alertas
│
└── jobs/                            # Tareas programadas
    ├── __init__.py
    └── reporte_semanal.py           # Job que genera el reporte semanal automático
```

### 3.1 Criterio de separación

La separación se basa en **responsabilidad** (cada capa hace una cosa) y **dominio** (cada módulo agrupa lo relacionado con una entidad de negocio):

- **`core/`**: No pertenece a ningún dominio. Es infraestructura compartida (configuración, dependencias globales).
- **`models/`**: Un archivo por entidad de negocio. Define la estructura de los datos en la capa de persistencia.
- **`schemas/`**: Un archivo por entidad o grupo de entidades relacionadas. Define cómo se reciben y devuelven los datos por HTTP.
- **`services/`**: Un archivo por dominio de negocio (`financiero`, `inventario`). Contiene la lógica pura, sin saber nada de HTTP ni de la base de datos. Aquí viven las funciones que ya construimos en `src/hito2/` (adaptadas a Python).
- **`repositories/`**: Un archivo por entidad. Abstrae el acceso a la fuente de datos. Si mañana cambiamos de SQLite a PostgreSQL, solo tocamos esta capa.
- **`routers/`**: Un archivo por dominio de endpoints. FastAPI usa `APIRouter` para agrupar rutas, lo cual mantiene el archivo `main.py` limpio y los endpoints organizados.
- **`jobs/`**: Tareas que se ejecutan periódicamente, separadas del ciclo de vida de las peticiones HTTP.

---

## 4. Organización de endpoints y routers

### 4.1 Criterio de agrupación

Cada router agrupa las rutas relacionadas con un dominio de negocio. Se usa el prefijo `/api` para namespace claro y se aplica un tag para documentación automática en Swagger (`/docs`).

### 4.2 Rutas propuestas

#### Locales — `routers/locales.py`

| Método | Ruta | Descripción |
|---|---|---|
| `GET` | `/api/locales` | Listar todas las sedes (14 locales) |
| `GET` | `/api/locales/{local_id}` | Obtener información de una sede específica |

**Justificación:** Los locales son la entidad base compartida por ambos frentes. Todos los reportes y consultas se filtran o agrupan por `localId`.

#### Movimientos Financieros — `routers/movimientos.py`

| Método | Ruta | Descripción |
|---|---|---|
| `GET` | `/api/movimientos` | Listar movimientos con filtros opcionales (`local_id`, `tipo`, `departamento`, `desde`, `hasta`) |
| `POST` | `/api/movimientos` | Registrar un nuevo movimiento financiero |

**Justificación:** El filtro temporal flexible (por día, mes, rango libre) es un requisito clave de Dirección Ejecutiva. Los query params permiten filtrado sin crear múltiples rutas.

#### Inventario — `routers/inventario.py`

| Método | Ruta | Descripción |
|---|---|---|
| `GET` | `/api/inventario` | Listar todos los insumos con su estado de stock |
| `GET` | `/api/inventario/{insumo_id}` | Detalle de un insumo específico |
| `POST` | `/api/inventario` | Agregar un nuevo insumo a la carta |
| `PUT` | `/api/inventario/{insumo_id}` | Actualizar stock o datos de un insumo |

**Justificación:** Operaciones necesita CRUD completo sobre insumos. La ruta se agrupa bajo `/inventario` porque es el lenguaje que usa el negocio (no "insumos" técnicos).

#### Reportes — `routers/reportes.py`

| Método | Ruta | Descripción |
|---|---|---|
| `GET` | `/api/reportes/financiero` | Reporte financiero por local con filtro de rango de fechas |
| `GET` | `/api/reportes/financiero/{local_id}` | Reporte financiero de una sede específica |
| `GET` | `/api/reportes/semanal` | Último reporte semanal generado |

**Justificación:** Los reportes son consultas pesadas que cruzan datos de múltiples entidades. Separarlos del router de movimientos evita confusión entre "datos crudos" y "datos agregados".

#### Alertas — `routers/alertas.py`

| Método | Ruta | Descripción |
|---|---|---|
| `GET` | `/api/alertas` | Obtener alertas activas de inventario (faltantes y excesos) |
| `GET` | `/api/alertas?prioridad=critica` | Filtrar alertas por nivel de prioridad |

**Justificación:** Las alertas son el producto más crítico para Operaciones. Merecen su propio router porque consumen datos de inventario + fechas especiales + consumo promedio, y su lógica es independiente del CRUD de insumos.

#### Fechas Especiales — (incluido en `routers/inventario.py` o router dedicado si crece)

| Método | Ruta | Descripción |
|---|---|---|
| `GET` | `/api/fechas-especiales` | Listar fechas especiales vigentes y próximas |
| `POST` | `/api/fechas-especiales` | Registrar una nueva fecha especial |

**Justificación:** Inicialmente se pueden incluir en el router de inventario ya que las fechas especiales afectan directamente la demanda de insumos. Si el dominio crece, se extrae a su propio router.

---

## 5. Comunicación Frontend ↔ Backend

### 5.1 Dos sistemas separados

El proyecto tiene una separación clara:

- **Frontend:** Next.js (React 19) en `uis/backoffice/` — desplegado de forma independiente
- **Backend:** FastAPI en `backend/` — desplegado como servicio independiente

No comparten runtime, no compilen juntos y pueden desplegarse, escalarse y actualizarse de forma independiente. Se comunican exclusivamente por HTTP mediante la API REST.

### 5.2 Convención de comunicación

```
Frontend (Next.js)  ──HTTP/JSON──▶  Backend (FastAPI)
     Puerto 3000                         Puerto 8000
```

- **Frontend** hace peticiones `fetch()` o usa un cliente HTTP (como `axios`) hacia las rutas `/api/*` del backend.
- **Backend** devuelve respuestas en formato JSON con códigos de estado HTTP estándar (200, 201, 400, 404, 500).

### 5.3 Variables de entorno

Cada sistema gestiona sus propias variables de entorno de forma independiente:

**Backend (`.env`):**
```
DATABASE_URL=sqlite:///./brasaland.db
CORS_ORIGINS=http://localhost:3000
ENVIRONMENT=development
PORT=8000
```

**Frontend (`.env.local` en Next.js):**
```
NEXT_PUBLIC_API_URL=http://localhost:8000/api
```

La variable `NEXT_PUBLIC_API_URL` permite que el frontend apunte al backend sin hardcodear la URL. En producción, ambas variables apuntarán a los servicios desplegados.

### 5.4 CORS (Cross-Origin Resource Sharing)

Como frontend y backend corren en puertos diferentes durante desarrollo (3000 vs 8000), el navegador bloqueará las peticiones cross-origin a menos que el backend configure CORS explícitamente.

En FastAPI, esto se configura con el middleware `CORSMiddleware`:

- **Desarrollo:** Permitir orígenes de `localhost:3000` (el frontend Next.js en desarrollo).
- **Producción:** Restringir los orígenes al dominio real del frontend desplegado.
- **Regla práctica:** Nunca usar `allow_origins=["*"]` en producción — expone la API a cualquier sitio.

Esta configuración vive en `core/config.py` y se aplica en `main.py` al crear la aplicación.

### 5.5 Contrato de datos entre sistemas

El frontend y el backend comparten un **contrato de datos implícito** a través de los esquemas Pydantic. Los esquemas definen exactamente qué campos espera recibir y devolver cada endpoint.

Si el backend cambia la estructura de un JSON de respuesta sin avisar, el frontend se romperá. Por eso los `schemas/` en el backend actúan como la fuente de verdad del contrato. Si en el futuro se necesita formalizar esto, se puede generar un schema OpenAPI automático (FastAPI lo hace por defecto en `/docs`) y consumirlo desde el frontend para generar tipos TypeScript.

---

## 6. Decisiones técnicas iniciales

### 6.1 Framework: FastAPI

**Por qué FastAPI:**
- Documentación automática interactiva (`/docs` con Swagger) — invaluable para que el equipo valide endpoints sin escribir tests manuales al inicio.
- Validación automática de request/response mediante Pydantic — reduce bugs de datos desde el primer día.
- Rendimiento comparable a Node.js para I/O, pero con la simplicidad de Python que el equipo ya maneja.
- Soporte nativo para async/await, útil cuando en el futuro se conecte a APIs externas o bases de datos remotas.

### 6.2 Base de datos: SQLite para desarrollo, migración a PostgreSQL en producción

**Por qué SQLite inicialmente:**
- Sin configuración de servidor — el archivo de base de datos se crea automáticamente.
- Ideal para la fase de simulación con datos generados programáticamente.
- SQLAlchemy (el ORM propuesto) soporta SQLite y PostgreSQL con los mismos modelos, por lo que la migración requiere cambiar solo la variable `DATABASE_URL`.

**Cuándo migrar:**
- Cuando Brasaland necesite múltiples usuarios accediendo simultáneamente a la API.
- Cuando se integre con datos reales del POS.
- PostgreSQL es el estándar en producción para FastAPI y tiene soporte robusto de SQLAlchemy.

### 6.3 ORM: SQLAlchemy

**Por qué SQLAlchemy:**
- Es el ORM estándar y más maduro para Python.
- Se integra directamente con FastAPI mediante `SQLAlchemy` + `Pydantic`.
- Permite definir modelos de Python que se mapean a tablas de la base de datos.
- Soporta relaciones entre tablas (un Local tiene muchos MovimientosFinancieros, un Insumo pertenece a una categoría).

### 6.4 Validación de datos: Pydantic v2

**Por qué Pydantic:**
- FastAPI lo usa nativamente — cada esquema de request/response se valida automáticamente.
- Si el frontend envía un campo faltante o con tipo incorrecto, el backend responde con un error 422 claro y descriptivo.
- Los esquemas Pydantic pueden heredar de los modelos SQLAlchemy, evitando duplicación de definiciones.

### 6.5 Servidor de desarrollo: Uvicorn

- Servidor ASGI de alto rendimiento para FastAPI.
- Soporte de hot-reload durante desarrollo (`uvicorn main:app --reload`).
- En producción se ejecuta detrás de un reverse proxy (Nginx) o en un servicio como Gunicorn con workers Uvicorn.

### 6.6 Estructura de configuración: Variables de entorno

- Todas las configuraciones sensibles (URLs de base de datos, orígenes CORS, puertos) se manejan por variables de entorno.
- El archivo `.env` (no subido a repositorio) contiene los valores locales.
- El módulo `core/config.py` lee estas variables usando Pydantic `BaseSettings`.
- Esto permite desplegar en diferentes entornos (desarrollo, staging, producción) sin cambiar código.

---

## 7. Riesgos y puntos de atención

### Riesgo 1: Lógica de negocio duplicada entre TypeScript y Python

**El problema:** Ya tenemos funciones implementadas en TypeScript (`src/hito2/aggregations.ts`, `src/hito2/inventory-alerts.ts`). Si reescribimos esas funciones en Python para el backend sin un proceso disciplinado, podemos terminar con dos versiones de la misma lógica que se desincronizan.

**Mitigación:**
- Migrar las funciones de `src/hito2/` a Python como parte del proceso de implementación del backend, documentando cada cambio.
- Mantener los tests de TypeScript como referencia de comportamiento esperado.
- Definir qué funciones se mantienen en TypeScript (solo para el frontend vanilla) y cuáles viven exclusivamente en Python (backend).
- A futuro, el backend Python será la fuente de verdad de la lógica de negocio, y el frontend Next.js solo consumirá la API.

### Riesgo 2: Acoplamiento excesivo entre frontend y backend

**El problema:** Si el frontend hardcodea URLs, estructuras de respuesta o lógica de filtrado, cualquier cambio del backend romperá el frontend silenciosamente.

**Mitigación:**
- Usar siempre la variable de entorno `NEXT_PUBLIC_API_URL` para las peticiones al backend.
- Definir los esquemas Pydantic como contrato de datos y respetarlos en ambos lados.
- Consumir el schema OpenAPI de FastAPI (`/openapi.json`) para generar tipos TypeScript en el frontend, eliminando la definición manual de interfaces.
- Implementar un manejo centralizado de errores HTTP en el frontend (interceptor de fetch que maneja 400, 404, 500 de forma unificada).

### Riesgo 3: Datos simulados que se convierten en datos reales sin migración

**El problema:** Actualmente los datos vienen de `sample-data.ts` generados programáticamente. Si el backend carga estos datos directamente en la base de datos sin un proceso de migración, cuando lleguen datos reales del POS habrá conflictos de formato, IDs duplicados o estructura incompatible.

**Mitigación:**
- Diseñar los modelos SQLAlchemy desde el inicio pensando en el esquema real de datos del POS (no solo en los tipos de TypeScript actuales).
- Implementar un sistema de migraciones de base de datos desde el primer día (usando Alembic, la herramienta estándar de SQLAlchemy).
- Separar claramente los "datos de semilla" (seed data) de los datos de producción — nunca mezclarlos en la misma tabla sin un proceso controlado.

---

## 8. Conclusiones

La arquitectura en capas propuesta para Brasaland es una decisión técnica fundamentada en la naturaleza del negocio:

- **Simplicidad con estructura:** El patrón es lo suficientemente simple para que el equipo lo implemente rápido, pero lo suficientemente organizado para que no se convierta en un desorden a medida que crezca.
- **Reutilización natural:** Los servicios y repositorios se comparten entre ambos frentes de negocio (Dirección Ejecutiva y Operaciones) sin duplicar código.
- **Preparación para el futuro:** La capa de repositorios permite cambiar la fuente de datos, y la separación de routers permite agregar nuevos dominios (como el agente Yayo) sin reestructurar todo.
- **Alineación con FastAPI:** La estructura propuesta sigue las convenciones estándar de la comunidad FastAPI, lo que facilita la incorporación de nuevos desarrolladores.

Este documento es un borrador vivo. Se espera que el equipo lo revise, cuestione y ajuste antes de comenzar la implementación. Las mejores arquitecturas no son las que un solo persona diseña, sino las que el equipo adopta y mejora colectivamente.

---

*Documento preparado para revisión del equipo de ingeniería — Brasaland Backend Architecture Proposal*
