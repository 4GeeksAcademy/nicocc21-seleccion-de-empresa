"""Tests para el Support Agent.

Requiere el servidor MCP corriendo para tests de integración.
Los tests unitarios usan un mock de MCPSession.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agents.support_agent.agent import SupportAgent


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def mock_session():
    """Crea un MCPSession simulado."""
    session = MagicMock()
    session.tools = [
        {"name": "list_incidents_tool", "description": "Lista incidencias", "input_schema": {}},
        {"name": "get_incident_tool", "description": "Obtiene incidencia", "input_schema": {}},
        {"name": "create_incident_tool", "description": "Crea incidencia", "input_schema": {}},
    ]
    session.get_tool_names.return_value = ["list_incidents_tool", "get_incident_tool", "create_incident_tool"]
    session.call_tool = AsyncMock()
    return session


@pytest.fixture
def mock_client(mock_session):
    """Parchea BrasalandMCPClient en el módulo del agente para evitar conexión real."""
    @asynccontextmanager
    async def _fake_client(*args, **kwargs):
        yield mock_session

    with patch("agents.support_agent.agent.BrasalandMCPClient", _fake_client):
        yield


# ---------------------------------------------------------------------------
# Unit tests
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_connect_and_list_tools(mock_session, mock_client):
    """Verifica que al conectar se obtienen las tools."""
    async with SupportAgent() as agent:
        tools = agent.tools
        assert len(tools) == 3
        assert tools[0]["name"] == "list_incidents_tool"
        assert agent.get_tool_names() == ["list_incidents_tool", "get_incident_tool", "create_incident_tool"]


@pytest.mark.asyncio
async def test_list_incidents(mock_session, mock_client):
    """Verifica que list_incidents llama a la tool correcta."""
    mock_session.call_tool.return_value = "[OK] 3 incidencias encontradas"

    async with SupportAgent() as agent:
        result = await agent.list_incidents(estado="abierta")

    mock_session.call_tool.assert_awaited_once_with("list_incidents_tool", {"estado": "abierta"})
    assert result == "[OK] 3 incidencias encontradas"


@pytest.mark.asyncio
async def test_get_incident(mock_session, mock_client):
    """Verifica que get_incident pasa el ID correcto."""
    mock_session.call_tool.return_value = "[OK] Incidencia #42"

    async with SupportAgent() as agent:
        result = await agent.get_incident(42)

    mock_session.call_tool.assert_awaited_once_with("get_incident_tool", {"incident_id": 42})
    assert result == "[OK] Incidencia #42"


@pytest.mark.asyncio
async def test_create_incident(mock_session, mock_client):
    """Verifica que create_incident pasa todos los campos."""
    mock_session.call_tool.return_value = "[OK] Incidencia #100 creada"

    async with SupportAgent() as agent:
        result = await agent.create_incident(
            title="Test",
            description="Descripción test",
            fecha_reporte="2026-11-14",
            local_id="L03",
            origen="cliente",
            categoria="queja",
            prioridad="alta",
        )

    mock_session.call_tool.assert_awaited_once_with(
        "create_incident_tool",
        {
            "title": "Test",
            "description": "Descripción test",
            "fecha_reporte": "2026-11-14",
            "local_id": "L03",
            "origen": "cliente",
            "categoria": "queja",
            "prioridad": "alta",
        },
    )
    assert result == "[OK] Incidencia #100 creada"


@pytest.mark.asyncio
async def test_update_incident(mock_session, mock_client):
    """Verifica que update_incident pasa ID + campos."""
    mock_session.call_tool.return_value = "[OK] Incidencia #1 actualizada"

    async with SupportAgent() as agent:
        result = await agent.update_incident(1, titulo="Nuevo título", prioridad="critica")

    mock_session.call_tool.assert_awaited_once_with(
        "update_incident_tool",
        {"incident_id": 1, "titulo": "Nuevo título", "prioridad": "critica"},
    )
    assert result == "[OK] Incidencia #1 actualizada"


@pytest.mark.asyncio
async def test_update_status(mock_session, mock_client):
    """Verifica que update_status pasa ID + nuevo estado."""
    mock_session.call_tool.return_value = "[OK] Estado cambiado a en_progreso"

    async with SupportAgent() as agent:
        result = await agent.update_status(1, "en_progreso")

    mock_session.call_tool.assert_awaited_once_with(
        "update_incident_status_tool",
        {"incident_id": 1, "nuevo_estado": "en_progreso"},
    )
    assert result == "[OK] Estado cambiado a en_progreso"


@pytest.mark.asyncio
async def test_get_summary(mock_session, mock_client):
    """Verifica que get_summary llama a la tool correcta."""
    mock_session.call_tool.return_value = "[OK] Resumen: 100 incidencias"

    async with SupportAgent() as agent:
        result = await agent.get_summary()

    mock_session.call_tool.assert_awaited_once_with("get_incidents_summary_tool", {})
    assert result == "[OK] Resumen: 100 incidencias"


@pytest.mark.asyncio
async def test_query_inventory(mock_session, mock_client):
    """Verifica que query_inventory pasa filtros correctamente."""
    mock_session.call_tool.return_value = "[OK] 5 ingredientes"

    async with SupportAgent() as agent:
        result = await agent.query_inventory(categoria="comida", low_stock=True)

    mock_session.call_tool.assert_awaited_once_with(
        "query_inventory",
        {"categoria": "comida", "low_stock": True},
    )
    assert result == "[OK] 5 ingredientes"


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_error_not_connected():
    """Verifica que llamar sin conectar lanza RuntimeError."""
    agent = SupportAgent()
    with pytest.raises(RuntimeError, match="not connected"):
        _ = agent.tools


@pytest.mark.asyncio
async def test_error_on_call_failure(mock_session, mock_client):
    """Verifica que errores en call_tool se propagan."""
    mock_session.call_tool.side_effect = ConnectionError("Server unreachable")

    async with SupportAgent() as agent:
        with pytest.raises(ConnectionError, match="Server unreachable"):
            await agent.list_incidents()