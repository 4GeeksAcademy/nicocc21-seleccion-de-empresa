# Brasaland MCP Server

Servidor MCP (Model Context Protocol) que expone herramientas de gestión de
incidencias y consulta de inventario de Brasaland como **tools protegidas por
OAuth 2.1**.

## Arquitectura

```
┌──────────────┐     OAuth 2.1 (client_credentials)
│  MCP Client  │ ──► Bearer JWT ──► ┌────────────────────┐
│  (agente)    │                     │  Brasaland MCP     │
└──────────────┘                     │  Server             │
                                     │  (Streamable HTTP)  │
                                     ├────────────────────┤
                                     │  FastMCP + mcpauth  │
                                     │  OAuth middleware   │
                                     ├────────────────────┤
                                     │  Incidents Tools    │ ──► TinyDB
                                     │  Inventory Tools    │ ──► PostgreSQL
                                     └────────────────────┘
```

## Transporte

**Streamable HTTP** sobre uvicorn (no stdio). Elegido por:
- Compatibilidad con MCP Playground y clientes HTTP externos
- Soporte nativo para OAuth Bearer tokens en headers HTTP
- Capacidad de servir múltiples clientes concurrentes
- Despliegue sin fricción en infraestructura web existente

## Autenticación

MCP Auth (**mcpauth**) como resource server OAuth 2.1:

- **Sin token**: Error `-32001` (Unauthorized)
- **Token sin scope suficiente**: Error `-32002` (Forbidden)
- **Token válido**: Se valida el scope contra la tool invocada

### Scopes

| Scope | Tools que protege |
|-------|-------------------|
| `incidents:read` | `list_incidents_tool`, `get_incident_tool`, `get_incidents_summary_tool` |
| `incidents:write` | `create_incident_tool`, `update_incident_tool`, `update_incident_status_tool` |
| `inventory:read` | `query_inventory`, `reject_inventory_write` |

## Tools disponibles

### Incidencias — Lectura

| Tool | Descripción | Scopes |
|------|-------------|--------|
| `list_incidents_tool` | Lista incidencias con filtros (estado, local, categoría, origen, prioridad, fechas) | `incidents:read` |
| `get_incident_tool` | Obtiene una incidencia por ID numérico | `incidents:read` |
| `get_incidents_summary_tool` | Resumen estadístico (total, por estado/categoría/prioridad/origen) | `incidents:read` |

### Incidencias — Escritura

| Tool | Descripción | Scopes |
|------|-------------|--------|
| `create_incident_tool` | Crea una nueva incidencia (título, descripción, fecha, local, origen, categoría, prioridad) | `incidents:write` |
| `update_incident_tool` | Actualiza campos editables de una incidencia existente | `incidents:write` |
| `update_incident_status_tool` | Cambia el estado siguiendo la máquina de estados (`abierta → en_progreso → resuelta`) | `incidents:write` |

### Inventario — Solo lectura

| Tool | Descripción | Scopes |
|------|-------------|--------|
| `query_inventory` | Consulta ingredientes con filtros (categoría, país, perecedero, low_stock, ubicación) | `inventory:read` |
| `reject_inventory_write` | **Rechaza explícitamente** cualquier intento de escritura sobre el inventario | `inventory:read` |

### Transiciones de estado (Incidencias)

```
abierta ──────► en_progreso ──────► resuelta
    │                                  │
    └──────► descartada    (terminal)  │
                                      (terminal)
```

## Códigos de error

| Código MCP | Significado | Ejemplo |
|------------|-------------|---------|
| `-32001` | **Unauthorized** — No se proporcionó token o el token es inválido | `"Se requiere autenticación OAuth 2.1"` |
| `-32002` | **Forbidden** — Token válido pero sin scope suficiente | `"Token no tiene los scopes requeridos"` |
| `-32602` | **Invalid params** — Parámetros inválidos (transición de estado, ID negativo, etc.) | `"No se puede cambiar estado de 'resuelta' a 'abierta'"` |
| `-32603` | **Internal error** — Error interno del servidor o BD no disponible | `"Inventario no disponible: DATABASE_URL no configurada"` |

## Logging

Cada invocación de tool registra en `brasaland-mcp.*`:

```
[INFO] Tool 'list_incidents_tool' autorizada para subject=client-app con scopes=['incidents:read']
[INFO] Tool 'list_incidents_tool' ejecutada exitosamente para subject=client-app
[INFO] list_incidents_tool -> 3 resultados (filtros: estado=abierta)
```

## Configuración

| Variable | Descripción | Default |
|----------|-------------|---------|
| `MCP_HOST` | Host del servidor | `0.0.0.0` |
| `MCP_PORT` | Puerto del servidor | `8081` |
| `OAUTH_ISSUER` | URL del issuer OAuth | `http://localhost:8080` |
| `OAUTH_JWKS_URL` | URL del JWKS endpoint | `{OAUTH_ISSUER}/.well-known/jwks.json` |
| `OAUTH_CLIENT_SECRET` | Secret compartido (fallback HMAC) | `dev-secret-change-in-prod` |
| `DATABASE_URL` | URL de PostgreSQL para inventario | *(vacío)* |
| `MCP_LOG_LEVEL` | Nivel de logging | `INFO` |

## Uso

```bash
# Iniciar servidor
uv run python -m mcps.brasaland_mcp.server

# El servidor escucha en http://0.0.0.0:8081/mcp
```

### Cliente mínimo

```python
from mcps.brasaland_mcp.client import BrasalandMCPClient

async with BrasalandMCPClient(
    server_url="http://localhost:8081/mcp",
    token="<jwt>",
) as session:
    tools = session.tools
    print(f"Tools: {session.get_tool_names()}")
    result = await session.call_tool("list_incidents_tool", {"estado": "abierta"})
    print(result)
```

## Tests

```bash
uv run pytest agents/support_agent/tests/test_agent.py -v
```