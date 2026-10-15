from __future__ import annotations

from pathlib import Path

import pytest

from services.brasaland_api import incidents_database
from services.brasaland_api.incidents_models import IncidentsSummaryOut, IncidentOut
from services.brasaland_api.routes import incidents


@pytest.fixture
def incidents_db(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Apunta la BD de incidencias a un archivo temporal y lo siembra."""
    db_file = tmp_path / "incidents-tests.json"
    monkeypatch.setattr(incidents_database, "DB_FILE", db_file)

    incidents_database.create_incident(
        {
            "title": "Fuga de agua",
            "description": "Se reporta fuga en cocina",
            "fecha_reporte": "2026-10-01",
            "local_id": "L01",
            "origen": "cliente",
            "categoria": "fallo_operativo",
            "prioridad": "alta",
        }
    )
    incidents_database.create_incident(
        {
            "title": "Queja servicio",
            "description": "Demora en atencion",
            "fecha_reporte": "2026-10-02",
            "local_id": "L02",
            "origen": "interno",
            "categoria": "queja",
            "prioridad": "media",
        }
    )
    return db_file


def test_summary_endpoint_returns_typed_summary_contract(incidents_db: Path) -> None:
    """GET /incidents/summary ahora tiene un serializer explícito tipado."""
    result = incidents.get_summary()

    assert isinstance(result, IncidentsSummaryOut)
    assert result.total == 2
    assert result.by_state["abierta"] == 2
    assert result.by_priority["alta"] == 1
    assert result.by_priority["media"] == 1
    assert result.by_origin["cliente"] == 1
    assert result.by_origin["interno"] == 1


def test_list_incidents_endpoint_returns_incident_out(incidents_db: Path) -> None:
    # Al llamar al endpoint directamente hay que pasar None explícitamente:
    # los defaults `Query(default=None)` solo se resuelven vía FastAPI.
    result = incidents.list_incidents_endpoint(
        estado=None,
        local_id=None,
        categoria=None,
        origen=None,
        prioridad=None,
        desde=None,
        hasta=None,
    )

    assert len(result) == 2
    assert all(isinstance(item, IncidentOut) for item in result)


def test_get_incident_endpoint_returns_not_found_for_unknown(incidents_db: Path) -> None:
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as error:
        incidents.get_incident_endpoint(999)

    assert error.value.detail == "Incidencia no encontrada"