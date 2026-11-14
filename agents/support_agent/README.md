# Support Agent — Brasaland

Agente de IA para el departamento de atención postventa de Brasaland.
Gestiona incidencias de clientes (quejas, solicitudes y fallos operativos)
consumiendo el **Brasaland MCP Server** como backend, en lugar de llamar
directamente a la API o base de datos.

## Objetivo

Proporcionar un asistente conversacional que permita al equipo de soporte:

- Consultar incidencias con filtros (estado, local, categoría, prioridad, fechas).
- Obtener detalles de una incidencia específica.
- Ver resúmenes estadísticos de incidencias.
- Crear nuevas incidencias.
- Actualizar incidencias existentes.
- Cambiar el estado de una incidencia siguiendo la máquina de estados.

Todo ello a través del MCP Server, que aplica OAuth 2.1 con scopes
(`incidents:read`, `incidents:write`).

## Herramientas disponibles (vía MCP)

| Tool MCP | Descripción | Scope |
|----------|-------------|-------|
| `list_incidents_tool` | Lista incidencias con filtros | incidents:read |
| `get_incident_tool` | Obtiene incidencia por ID | incidents:read |
| `get_incidents_summary_tool` | Resumen estadístico | incidents:read |
| `create_incident_tool` | Crea nueva incidencia | incidents:write |
| `update_incident_tool` | Actualiza campos editables | incidents:write |
| `update_incident_status_tool` | Cambia estado (máquina de estados) | incidents:write |

> **Nota:** Inventario es solo lectura vía MCP. Cualquier intento de
> escribir en inventario es rechazado explícitamente por el servidor.

## Arquitectura

```
Usuario
  │
  ▼
┌──────────────────────────────┐
│    Support Agent (agente)     │
│  agents/support_agent/        │
│                              │
│  usa BrasalandMCPClient       │
│  (mcps/brasaland_mcp/client/) │
└──────────┬───────────────────┘
           │ MCP Protocol (Streamable HTTP + JWT)
           ▼
┌──────────────────────────────┐
│  Brasaland MCP Server        │
│  mcps/brasaland_mcp/         │
│  + OAuth 2.1 (mcpauth)       │
└──────────┬───────────────────┘
           │ Llamadas internas
           ▼
┌──────────────────────────────┐
│  incidents_database.py       │
│  (TinyDB CRUD)               │
└──────────────────────────────┘
```

## Configuración

Variables de entorno (ver `env/mcp.example`):

| Variable | Descripción |
|----------|-------------|
| `MCP_SERVER_URL` | URL del MCP Server (ej. `http://localhost:8081/mcp`) |
| `MCP_CLIENT_ID` | Client ID para OAuth |
| `MCP_CLIENT_SECRET` | Client secret para OAuth |
| `OAUTH_ISSUER` | Issuer del Authorization Server |
| `MCP_LOG_LEVEL` | Nivel de logging (`INFO`, `DEBUG`, etc.) |

## Uso rápido

```python
import asyncio
from agents.support_agent import SupportAgent

async def demo():
    async with SupportAgent() as agent:
        # Listar herramientas disponibles
        print("Tools:", agent.get_tool_names())

        # Listar incidencias abiertas
        result = await agent.list_incidents(estado="abierta")
        print(result)

        # Crear una incidencia
        result = await agent.create_incident(
            title="Cliente insatisfecho",
            description="El cliente reportó...",
            fecha_reporte="2026-11-14",
            local_id="L03",
            origen="cliente",
            categoria="queja",
            prioridad="alta",
        )
        print(result)

        # Consultar inventario
        result = await agent.query_inventory(category="meat")
        print(result)

asyncio.run(demo())
```

También puedes usar `BrasalandMCPClient` directamente (más bajo nivel):

```python
from mcps.brasaland_mcp.client import BrasalandMCPClient

async with BrasalandMCPClient(token="<jwt>") as session:
    result = await session.call_tool("list_incidents_tool", {"estado": "abierta"})
```

## CLI interactiva

```bash
uv run python -m agents.support_agent.agent
```

Comandos disponibles:
- `list estado=abierta` — Lista incidencias
- `get 42` — Obtiene incidencia por ID
- `summary` — Resumen estadístico
- `create` — Crea incidencia (asistido)
- `update 1 titulo=Nuevo` — Actualiza campos
- `status 1 en_progreso` — Cambia estado
- `inventory` — Consulta inventario
- `help` / `exit` — Ayuda / salir

## Tests

```bash
uv run pytest agents/support_agent/tests/test_agent.py -v
```

Los tests validan:

1. Conexión y listado de herramientas.
2. Llamada a herramientas de solo lectura (`list_incidents`, `get_incident`, `get_summary`).
3. Llamada a herramientas de escritura (`create_incident`, `update_incident`, `update_status`).
4. Consulta de inventario (`query_inventory`).
5. Error si se llama sin conectar.
6. Propagación de errores del servidor.

> Los tests usan un mock de `BrasalandMCPClient` y no requieren servidor MCP corriendo.