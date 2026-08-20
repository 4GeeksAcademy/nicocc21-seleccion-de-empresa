from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from services.api.auth import get_current_user, hash_password
from services.api.database import (
    create_profile,
    create_user,
    delete_user,
    get_user_by_id,
    list_users,
    update_user,
)
from services.api.models import UserCreate, UserOut, UserUpdate

router = APIRouter(prefix="/users", tags=["users"])


def _require_admin(current_user: dict) -> None:
    """Lanza 403 si el usuario no es admin."""
    if current_user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Se requiere rol de administrador",
        )


def _user_to_out(user: dict) -> UserOut:
    """Convierte un dict de usuario a UserOut."""
    return UserOut(
        id=user["id"],
        email=user["email"],
        is_active=user.get("is_active", True),
        role=user.get("role", "user"),
        created_at=user.get("created_at", ""),
    )


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user_endpoint(payload: UserCreate) -> UserOut:
    """Registrar un nuevo usuario (público — no requiere token).

    Crea el usuario con credenciales hasheadas y, opcionalmente,
    un Profile vinculado si se proporciona name.
    """
    try:
        user = create_user(
            email=payload.email,
            password_hash=hash_password(payload.password),
        )
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya existe un usuario con ese email",
        )

    # Crear perfil inicial si se proporcionó el nombre
    if payload.name:
        try:
            create_profile(
                user_id=user["id"],
                data={
                    "full_name": payload.name,
                    "phone": payload.phone,
                    "address": payload.address,
                },
            )
        except ValueError:
            pass

    return _user_to_out(user)


@router.get("", response_model=list[UserOut])
def get_users(current_user: dict = Depends(get_current_user)) -> list[UserOut]:
    """Listar todos los usuarios (protegida)."""
    _require_admin(current_user)
    users = list_users()
    return [_user_to_out(u) for u in users]


@router.get("/{user_id}", response_model=UserOut)
def get_user(
    user_id: int,
    current_user: dict = Depends(get_current_user),
) -> UserOut:
    """Obtener un usuario por ID (protegida)."""
    _require_admin(current_user)
    user = get_user_by_id(user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado",
        )
    return _user_to_out(user)


@router.put("/{user_id}", response_model=UserOut)
def put_user(
    user_id: int,
    payload: UserUpdate,
    current_user: dict = Depends(get_current_user),
) -> UserOut:
    """Actualizar email o role de un usuario (protegida).

    Solo el propio usuario o un admin pueden actualizar.
    Solo admin puede cambiar el campo role.
    """
    # Verificar que el usuario exista
    target = get_user_by_id(user_id)
    if target is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado",
        )

    is_admin = current_user.get("role") == "admin"
    is_self = current_user["id"] == user_id

    if not is_admin and not is_self:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo puedes editar tu propio usuario",
        )

    # Solo admin puede cambiar el role
    update_data = payload.model_dump(exclude_unset=True)
    if "role" in update_data and not is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo un administrador puede cambiar el role",
        )

    try:
        updated = update_user(user_id, update_data)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        )

    if updated is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado",
        )
    return _user_to_out(updated)


@router.delete("/{user_id}", status_code=status.HTTP_200_OK)
def delete_user_endpoint(
    user_id: int,
    current_user: dict = Depends(get_current_user),
) -> dict[str, str]:
    """Eliminar un usuario y su perfil vinculado (protegida).

    Solo el propio usuario o un admin pueden eliminar.
    """
    is_admin = current_user.get("role") == "admin"
    is_self = current_user["id"] == user_id

    if not is_admin and not is_self:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo puedes eliminar tu propio usuario",
        )

    deleted = delete_user(user_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado",
        )
    return {"message": "Usuario eliminado"}
