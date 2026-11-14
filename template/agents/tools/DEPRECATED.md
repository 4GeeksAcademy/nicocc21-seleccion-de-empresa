# ⚠️ Deprecado — Migración a MCP Server

Este directorio contenía herramientas directas para conectar agentes a las APIs de
Brasaland (Incidents Manager, Inventory, etc.).

**A partir de ahora, todos los agentes deben consumir estas funcionalidades
exclusivamente a través del MCP Server**, no invocando las APIs internas
directamente.

## ¿Qué cambió?

| Antes | Ahora |
|-------|-------|
| Cada agente llamaba `services.brasaland_api.*` directamente | El agente usa `BrasalandMCPClient` para llamar tools MCP |
| Las tools tenían que implementar auth y logging cada una | El MCP Server centraliza OAuth + logging |
| No había control de acceso centralizado | MCP Auth valida scopes OAuth 2.1 en cada llamada |

## ¿Qué pasa si un agente sigue usando el path antiguo?

Nada, los módulos de `services.brasaland_api.*` siguen funcionando para el servidor
FastAPI de Brasaland. Pero los agentes **no deben importarlos** — el MCP Server
es la única entrada para agentes externos.

## Migración

Reemplaza:

```python
# ❌ ANTIGUO
from services.brasaland_api.incidents_database import list_incidents
incidencias = list_incidents(estado="abierta")
```

por:

```python
# ✅ NUEVO
from mcps.brasaland_mcp.client import BrasalandMCPClient

async with BrasalandMCPClient() as session:
    result = await session.call_tool("list_incidents_tool", {"estado": "abierta"})
```

O mejor aún, usa el `SupportAgent` de `agents.support_agent` que ya encapsula
toda la lógica:

```python
from agents.support_agent import SupportAgent

async with SupportAgent() as agent:
    result = await agent.list_incidents(estado="abierta")
```

## Tools disponibles vía MCP

Ver `mcps/brasaland_mcp/tools/` para la lista completa de tools expuestas,
o llama al discovery del servidor MCP desde el cliente.