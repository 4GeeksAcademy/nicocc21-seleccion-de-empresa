"""Caché simple en memoria para endpoints de la API Brasaland.

Uso:
    from services.brasaland_api.cache import cache, cached

    @router.get("/products")
    @cached(ttl_seconds=60)
    def list_products(categoria: str | None = None, pais: str | None = None):
        # ... lógica costosa ...
        return data

    # O directamente:
    data = cache.get("mi_clave")
    if data is not None:
        return data
    cache.set("mi_clave", data, ttl_seconds=60)

Sin dependencias externas. Para entornos multi-worker, migrar a Redis.
"""

from __future__ import annotations

import functools
import inspect
import logging
import time
from typing import Any, Callable

_logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# Decorador @cached
# ──────────────────────────────────────────────

def cached(
    ttl_seconds: int | float = 60,
    skip_args: set[str] | None = None,
    prefix: str | None = None,
):
    """Decorador para cachear resultados de endpoints FastAPI.

    Calcula la clave de caché a partir del nombre de la función y los
    argumentos realmente provistos (excluye defaults de FastAPI como
    Query(), Path(), Body(), etc.).

    Args:
        ttl_seconds: Tiempo de vida en segundos (por defecto 60).
        skip_args: Conjunto de nombres de argumentos a excluir de la clave
                   (ej. {"session", "current_user"}).
        prefix: Prefijo explícito para agrupar claves de un mismo dominio
                (ej. "inventory"). Facilita la invalidación: al escribir
                datos del dominio, llamar a cache.invalidate(prefix).
                Si es None, se usa func.__module__.

    Uso:
        @router.get("/products")
        @cached(ttl_seconds=60, skip_args={"session"}, prefix="inventory")
        def list_products(
            session: Session = Depends(get_db),
            categoria: str | None = None,
        ):
            ...
    """
    skip = skip_args or set()

    def _is_fastapi_default(val: Any) -> bool:
        """Detecta si un valor es un objeto de parametro de FastAPI (Query, Path, Body, etc.)."""
        # Estos objetos viven en fastapi.params.Param o starlette.params
        # Verificamos por nombre de clase para evitar import circular
        type_name = type(val).__name__
        return type_name in ("ParamFunc", "Param", "FieldInfo") or (
            hasattr(val, "default") and type_name in ("Query", "Path", "Body", "Header", "Cookie", "Form", "File", "Depends")
        )

    def decorator(func: Callable) -> Callable:
        sig = inspect.signature(func)
        param_names = list(sig.parameters.keys())

        def _build_cache_key(bound: inspect.BoundArguments) -> str:
            """Construye clave única ignorando defaults de FastAPI."""
            domain = prefix or func.__module__
            parts = [domain, func.__qualname__]
            for name in param_names:
                if name in skip:
                    continue
                if name in bound.arguments:
                    val = bound.arguments[name]
                    # Saltar objetos de parametro de FastAPI (Query, Path, etc.)
                    if _is_fastapi_default(val):
                        continue
                    parts.append(f"{name}={val!r}")
            return "|".join(parts)

        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            bound = sig.bind(*args, **kwargs)
            bound.apply_defaults()
            cache_key = _build_cache_key(bound)

            cached_value = cache._get(cache_key)
            if cached_value is not None:
                return cached_value

            result = await func(*args, **kwargs)
            cache._set(cache_key, result, ttl_seconds)
            return result

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            bound = sig.bind(*args, **kwargs)
            bound.apply_defaults()
            cache_key = _build_cache_key(bound)

            cached_value = cache._get(cache_key)
            if cached_value is not None:
                return cached_value

            result = func(*args, **kwargs)
            cache._set(cache_key, result, ttl_seconds)
            return result

        if inspect.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


class _InMemoryCache:
    """Caché con expiración por TTL, sin dependencias externas.

    Almacena valores en un dict con timestamp de expiración.
    No es seguro para hilos (thread-safe) — suficiente para un
    servidor single-process como el de desarrollo.
    """

    def __init__(self):
        self._store: dict[str, Any] = {}
        self._expires_at: dict[str, float] = {}

    def get(self, key: str) -> Any | None:
        """Retorna el valor cacheado o None si no existe o expiró.

        Método público con logging para diagnóstico.
        """
        value = self._get(key)
        if value is not None:
            _logger.debug("CACHE HIT  key=%s", key)
        else:
            _logger.debug("CACHE MISS key=%s", key)
        return value

    def _get(self, key: str) -> Any | None:
        """Retorna el valor cacheado sin logging (uso interno)."""
        if key not in self._store:
            return None
        if time.monotonic() > self._expires_at[key]:
            del self._store[key]
            del self._expires_at[key]
            return None
        return self._store[key]

    def set(self, key: str, value: Any, ttl_seconds: int | float) -> None:
        """Almacena un valor con tiempo de vida en segundos (con logging)."""
        self._set(key, value, ttl_seconds)
        _logger.debug("CACHE SET  key=%s  ttl=%ss", key, ttl_seconds)

    def _set(self, key: str, value: Any, ttl_seconds: int | float) -> None:
        """Almacena sin logging (uso interno del decorador)."""
        self._store[key] = value
        self._expires_at[key] = time.monotonic() + ttl_seconds

    def invalidate(self, key_prefix: str = "") -> None:
        """Invalida entradas que empiecen con key_prefix. Si está vacío, limpia todo."""
        if not key_prefix:
            self._store.clear()
            self._expires_at.clear()
            _logger.debug("CACHE invalidada completamente")
            return
        keys = [k for k in self._store if k.startswith(key_prefix)]
        for k in keys:
            del self._store[k]
            del self._expires_at[k]
        if keys:
            _logger.debug("CACHE invalidada prefix=%s (%d entradas)", key_prefix, len(keys))

    @property
    def size(self) -> int:
        """Número de entradas en caché (sin limpiar expiradas)."""
        return len(self._store)

    def clear_expired(self) -> int:
        """Limpia entradas expiradas manualmente. Retorna cuántas eliminó."""
        now = time.monotonic()
        expired = [k for k, t in self._expires_at.items() if now > t]
        for k in expired:
            del self._store[k]
            del self._expires_at[k]
        return len(expired)


# Singleton — instancia única compartida por toda la aplicación
cache = _InMemoryCache()