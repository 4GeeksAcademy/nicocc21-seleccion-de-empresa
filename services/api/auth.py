"""Centraliza hash de contraseñas, JWT y la dependencia get_current_user."""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt

from services.api.database import get_user_by_id

# --- Configuración ---

SECRET_KEY = os.getenv("JWT_SECRET_KEY", "brasaland-dev-secret-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "60"))
RESET_TOKEN_EXPIRE_MINUTES = int(os.getenv("RESET_TOKEN_EXPIRE_MINUTES", "15"))

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


# --- Hash ---

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


# --- JWT ---

def create_access_token(user_id: int) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {"sub": str(user_id), "exp": expire}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> int:
    """Decodifica el JWT y retorna el user_id. Lanza HTTPException si falla."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id_str = payload.get("sub")
        if user_id_str is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token inválido",
            )
        return int(user_id_str)
    except (JWTError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido o expirado",
        )


# --- Dependencia reutilizable ---

def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
    """Dependencia FastAPI: decodifica el token y retorna el usuario completo."""
    user_id = decode_token(token)
    user = get_user_by_id(user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario no encontrado",
        )
    return user


# --- AUTH-03: Reset Token ---

import uuid


def create_reset_token(user_id: int) -> str:
    """Crea un JWT de restablecimiento de contraseña de corta duración.

    Incluye un jti (ID único) para poder invalidar el token tras su uso.
    """
    expire = datetime.now(timezone.utc) + timedelta(minutes=RESET_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": str(user_id),
        "exp": expire,
        "jti": str(uuid.uuid4()),
        "type": "password_reset",
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_reset_token(token: str) -> tuple[int, str]:
    """Decodifica un token de restablecimiento y retorna (user_id, jti).

    Lanza HTTPException si el token es inválido, expiró o no es de tipo reset.
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("type") != "password_reset":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Token inválido",
            )
        user_id_str = payload.get("sub")
        jti = payload.get("jti")
        if user_id_str is None or jti is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Token inválido",
            )
        return int(user_id_str), str(jti)
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token inválido o expirado",
        )


def get_reset_link(token: str, base_url: str | None = None) -> str:
    """Construye la URL completa de restablecimiento.

    Args:
        token: JWT de restablecimiento.
        base_url: URL base de la app (ej: http://localhost:3000).
                  Si es None, se lee de la variable de entorno FRONTEND_URL.

    Returns:
        URL completa con el token como query param.
    """
    if base_url is None:
        base_url = os.getenv("FRONTEND_URL", "http://localhost:3000")
    return f"{base_url.rstrip('/')}/reset-password?token={token}"
