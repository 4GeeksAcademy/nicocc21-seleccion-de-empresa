from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status

from services.brasaland_api.incidents_database import (
    create_incident,
    get_incident,
    get_incidents_summary,
    list_incidents,
    update_incident,
    update_incident_status,
)
from services.brasaland_api.incidents_models import (
    IncidentCreate,
    IncidentOut,
    IncidentStatusUpdate,
    IncidentUpdate,
)

router = APIRouter(prefix="/incidents", tags=["incidents"])


@router.get("/summary", response_model=dict)
def get_summary():
    return get_incidents_summary()


@router.get("", response_model=list[IncidentOut])
def list_incidents_endpoint(
    estado: str | None = Query(default=None),
    local_id: str | None = Query(default=None),
    categoria: str | None = Query(default=None),
    origen: str | None = Query(default=None),
    prioridad: str | None = Query(default=None),
    desde: str | None = Query(default=None),
    hasta: str | None = Query(default=None),
):
    rows = list_incidents(
        estado=estado,
        local_id=local_id,
        categoria=categoria,
        origen=origen,
        prioridad=prioridad,
        desde=desde,
        hasta=hasta,
    )
    return [IncidentOut.model_validate(row) for row in rows]


@router.get("/{incident_id}", response_model=IncidentOut)
def get_incident_endpoint(incident_id: int):
    incident = get_incident(incident_id)
    if incident is None:
        raise HTTPException(status_code=404, detail="Incidencia no encontrada")
    return IncidentOut.model_validate(incident)


@router.post("", response_model=IncidentOut, status_code=status.HTTP_201_CREATED)
def create_incident_endpoint(payload: IncidentCreate):
    created = create_incident(payload.model_dump(mode="json"))
    return IncidentOut.model_validate(created)


@router.patch("/{incident_id}", response_model=IncidentOut)
def update_incident_endpoint(incident_id: int, payload: IncidentUpdate):
    updates = payload.model_dump(mode="json", exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No hay campos para actualizar")

    updated = update_incident(incident_id, updates)
    if updated is None:
        raise HTTPException(status_code=404, detail="Incidencia no encontrada")
    return IncidentOut.model_validate(updated)


@router.patch("/{incident_id}/status", response_model=IncidentOut)
def update_incident_status_endpoint(incident_id: int, payload: IncidentStatusUpdate):
    try:
        updated = update_incident_status(incident_id, payload.estado.value)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if updated is None:
        raise HTTPException(status_code=404, detail="Incidencia no encontrada")
    return IncidentOut.model_validate(updated)