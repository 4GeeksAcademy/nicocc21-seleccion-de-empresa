from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm

from services.api.auth import (
    create_access_token,
    create_reset_token,
    decode_reset_token,
    get_current_user,
    get_reset_link,
    hash_password,
    verify_password,
)
from services.api.database import (
    create_profile,
    create_user,
    get_profile_by_user_id,
    get_user_by_email,
    get_user_by_id,
    hash_token,
    is_token_used_or_expired,
    mark_reset_token_used,
    store_reset_token,
    update_user_password,
    utc_now,
)
from services.api.email_service import send_reset_email
from services.api.models import (
    ChangePasswordRequest,
    ForgotPasswordRequest,
    MessageResponse,
    ResetPasswordRequest,
    Token,
    UserCreate,
    UserMeOut,
    UserMeProfile,
    UserOut,
)

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


# =============================================================================
# AUTH-03: Forgot / Reset / Change Password
# =============================================================================


@router.post(
    "/forgot-password",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
)
def forgot_password(payload: ForgotPasswordRequest) -> MessageResponse:
    """Solicitar restablecimiento de contraseña.

    Siempre devuelve 200 independientemente de si el email existe,
    para evitar enumeración de usuarios.
    Si el usuario existe, genera un token de restablecimiento,
    lo almacena hasheado y envía un email con el enlace.
    """
    user = get_user_by_email(payload.email)

    if user is not None:
        try:
            user_id = user["id"]
            # Generar token JWT de corta duración
            reset_token = create_reset_token(user_id)

            # Extraer el jti para almacenarlo (el token ya tiene exp)
            _, jti = decode_reset_token(reset_token)

            # Calcular expires_at (sumando los minutos de expiración)
            from datetime import datetime, timedelta, timezone
            from services.api.auth import RESET_TOKEN_EXPIRE_MINUTES
            expires_at = (
                datetime.now(timezone.utc) + timedelta(minutes=RESET_TOKEN_EXPIRE_MINUTES)
            ).isoformat()

            # Almacenar token hasheado
            store_reset_token(
                user_id=user_id,
                token_hash=hash_token(reset_token),
                expires_at=expires_at,
            )

            # Enviar email
            reset_link = get_reset_link(reset_token)
            send_reset_email(to_email=payload.email, reset_link=reset_link)

        except Exception:
            # Si falla el envío del email, no revelamos nada al usuario
            # pero registramos el error internamente
            import logging
            logger = logging.getLogger(__name__)
            logger.exception("Error al procesar forgot-password para %s", payload.email)

    # Siempre devolver el mismo mensaje
    return MessageResponse(
        message="Si esa dirección está registrada, recibirás un enlace para restablecer tu contraseña en breve."
    )


@router.post(
    "/reset-password",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
)
def reset_password(payload: ResetPasswordRequest) -> MessageResponse:
    """Restablecer contraseña con un token de restablecimiento.

    Valida el token (firma, expiración, que no se haya usado ya).
    Si es válido, hashea la nueva contraseña, actualiza el usuario
    e invalida el token.
    """
    # 1. Decodificar el token JWT (valida firma y expiración)
    try:
        user_id, _ = decode_reset_token(payload.token)
    except HTTPException:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El enlace de restablecimiento es inválido o ha expirado. Solicita uno nuevo.",
        )

    # 2. Verificar que el token no se haya usado ya
    token_hash = hash_token(payload.token)
    now_iso = utc_now().isoformat()

    if is_token_used_or_expired(token_hash, now_iso):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El enlace de restablecimiento ya fue utilizado o ha expirado. Solicita uno nuevo.",
        )

    # 3. Verificar que el usuario existe
    user = get_user_by_id(user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El enlace de restablecimiento es inválido o ha expirado. Solicita uno nuevo.",
        )

    # 4. Actualizar la contraseña
    new_hash = hash_password(payload.new_password)
    update_user_password(user_id, new_hash)

    # 5. Invalidar el token
    mark_reset_token_used(token_hash)

    return MessageResponse(
        message="Contraseña restablecida correctamente. Ya puedes iniciar sesión con tu nueva contraseña."
    )


@router.post(
    "/change-password",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
)
def change_password(
    payload: ChangePasswordRequest,
    current_user: dict = Depends(get_current_user),
) -> MessageResponse:
    """Cambiar contraseña estando autenticado.

    Verifica la contraseña actual antes de actualizarla.
    """
    # 1. Verificar contraseña actual
    if not verify_password(payload.current_password, current_user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La contraseña actual no es correcta.",
        )

    # 2. Actualizar a la nueva contraseña
    new_hash = hash_password(payload.new_password)
    update_user_password(current_user["id"], new_hash)

    return MessageResponse(
        message="Contraseña actualizada correctamente."
    )
