from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm

from services.api.auth import (
    create_access_token,
    get_current_user,
    hash_password,
    verify_password,
)
from services.api.database import (
    create_profile,
    create_user,
    get_profile_by_user_id,
    get_user_by_email,
)
from services.api.models import Token, UserCreate, UserMeOut, UserMeProfile, UserOut

router = APIRouter(prefix="/auth", tags=["auth"])


def _user_to_out(user: dict) -> UserOut:
    """Convierte un dict de usuario a UserOut."""
    return UserOut(
        id=user["id"],
        email=user["email"],
        is_active=user.get("is_active", True),
        role=user.get("role", "user"),
        created_at=user.get("created_at", ""),
    )


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(payload: UserCreate) -> UserOut:
    """Registrar un nuevo usuario con email y contraseña.

    Acepta campos opcionales de perfil inicial (name, phone, address)
    y crea el Profile vinculado en la misma operación.
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
            # Si falla la creación del perfil, no es crítico — el usuario ya se creó
            pass

    return _user_to_out(user)


@router.post("/login", response_model=Token)
def login(form: OAuth2PasswordRequestForm = Depends()) -> Token:
    """Validar credenciales y devolver JWT.

    Envia en el body:  username={email}  password={contraseña}
    (OAuth2PasswordRequestForm usa 'username' como campo, aquí lo tratamos como email)
    """
    user = get_user_by_email(form.username)
    if user is None or not verify_password(form.password, user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email o contraseña incorrectos",
        )
    token = create_access_token(user["id"])
    return Token(access_token=token)


@router.get("/me", response_model=UserMeOut)
def get_me(current_user: dict = Depends(get_current_user)) -> UserMeOut:
    """Devuelve el email, role y perfil del usuario autenticado (protegida)."""
    profile_data = get_profile_by_user_id(current_user["id"])
    profile = None
    if profile_data:
        profile = UserMeProfile(
            full_name=profile_data.get("full_name", ""),
            phone=profile_data.get("phone"),
            address=profile_data.get("address"),
        )

    return UserMeOut(
        id=current_user["id"],
        email=current_user["email"],
        is_active=current_user.get("is_active", True),
        role=current_user.get("role", "user"),
        created_at=current_user.get("created_at", ""),
        profile=profile,
    )
