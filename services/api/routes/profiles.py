from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from services.api.auth import get_current_user
from services.api.database import create_profile, get_profile_by_user_id, update_profile
from services.api.models import ProfileCreate, ProfileOut, ProfileUpdate

router = APIRouter(prefix="/profiles", tags=["profiles"])


@router.post("", response_model=ProfileOut, status_code=status.HTTP_201_CREATED)
def create_my_profile(
    payload: ProfileCreate,
    current_user: dict = Depends(get_current_user),
) -> ProfileOut:
    """Crear mi perfil (requiere token). Solo un perfil por usuario."""
    try:
        profile = create_profile(
            user_id=current_user["id"],
            data=payload.model_dump(mode="json"),
        )
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El usuario ya tiene un perfil",
        )
    return ProfileOut.model_validate(profile)


@router.get("/me", response_model=ProfileOut)
def get_my_profile(current_user: dict = Depends(get_current_user)) -> ProfileOut:
    """Ver mi perfil (requiere token)."""
    profile = get_profile_by_user_id(current_user["id"])
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Perfil no encontrado",
        )
    return ProfileOut.model_validate(profile)


@router.patch("/me", response_model=ProfileOut)
def update_my_profile(
    payload: ProfileUpdate,
    current_user: dict = Depends(get_current_user),
) -> ProfileOut:
    """Actualizar mi perfil (requiere token). Solo actualiza campos enviados."""
    updated = update_profile(
        user_id=current_user["id"],
        data=payload.model_dump(exclude_unset=True),
    )
    if updated is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Perfil no encontrado",
        )
    return ProfileOut.model_validate(updated)


@router.put("/me", response_model=ProfileOut)
def put_my_profile(
    payload: ProfileUpdate,
    current_user: dict = Depends(get_current_user),
) -> ProfileOut:
    """Actualizar mi perfil completo (requiere token).

    Reemplaza name, phone y address. Solo el dueño del perfil puede modificarlo.
    """
    # Verificar que el perfil exista
    existing = get_profile_by_user_id(current_user["id"])
    if existing is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Perfil no encontrado",
        )

    updated = update_profile(
        user_id=current_user["id"],
        data=payload.model_dump(exclude_unset=True),
    )
    if updated is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Perfil no encontrado",
        )
    return ProfileOut.model_validate(updated)
