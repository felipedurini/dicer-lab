"""Principal local de desarrollo y validación de access tokens Supabase."""

from __future__ import annotations

import asyncio
import ipaddress
import json
import logging
import time
from urllib.parse import urlsplit
from uuid import UUID

import httpx
from fastapi import HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials

from .settings import Settings

logger = logging.getLogger(__name__)
LOCAL_USER_ID = "00000000-0000-4000-8000-000000000001"
_JWKS_TTL_SECONDS = 300
_MAX_TOKEN_CHARS = 8192


def _loopback(value: str) -> bool:
    host = urlsplit(value).hostname or ""
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def _loopback_authority(value: str) -> bool:
    """Validate the raw Host authority before interpreting it as a URL."""
    if not value or any(char.isspace() or char in "/\\?#@" for char in value):
        return False
    try:
        parsed = urlsplit(f"http://{value}")
        _ = parsed.port  # Reject malformed or out-of-range ports.
        return _loopback(f"http://{value}")
    except ValueError:
        return False


async def _jwks(request: Request, settings: Settings) -> dict[str, object]:
    now = time.monotonic()
    cached = getattr(request.app.state, "jwks_cache", None)
    if cached and cached[0] > now:
        return cached[1]
    lock: asyncio.Lock = request.app.state.jwks_lock
    async with lock:
        now = time.monotonic()
        cached = getattr(request.app.state, "jwks_cache", None)
        if cached and cached[0] > now:
            return cached[1]
        client: httpx.AsyncClient = request.app.state.http_client
        url = f"{settings.supabase_url}/auth/v1/.well-known/jwks.json"
        try:
            response = await client.get(url, timeout=5.0)
            response.raise_for_status()
            data = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise HTTPException(
                status_code=503,
                detail={"code": "auth_provider_unavailable", "message": "No se pudo verificar la sesión"},
            ) from exc
        if not isinstance(data, dict) or not isinstance(data.get("keys"), list):
            raise HTTPException(
                status_code=503,
                detail={"code": "auth_keys_unavailable", "message": "No se pudo verificar la sesión"},
            )
        request.app.state.jwks_cache = (now + _JWKS_TTL_SECONDS, data)
        return data


async def require_principal(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None,
) -> str:
    """Autentica en cada endpoint privado; nunca lee un user ID del request."""
    settings: Settings = request.app.state.settings
    if settings.auth_mode == "local":
        client_host = request.client.host if request.client else ""
        try:
            peer_is_loopback = ipaddress.ip_address(client_host).is_loopback
        except ValueError:
            peer_is_loopback = client_host == "testclient"
        host_headers = request.headers.getlist("host")
        if (not peer_is_loopback or not _loopback(settings.app_origin)
                or len(host_headers) != 1 or not _loopback_authority(host_headers[0])):
            raise HTTPException(status_code=403, detail="El modo local solo acepta loopback")
        return LOCAL_USER_ID

    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="Sesión requerida", headers={"WWW-Authenticate": "Bearer"})
    token = credentials.credentials
    if not token or len(token) > _MAX_TOKEN_CHARS:
        raise HTTPException(status_code=401, detail="Token inválido", headers={"WWW-Authenticate": "Bearer"})

    try:
        import jwt

        header = jwt.get_unverified_header(token)
        if "jku" in header or "x5u" in header:
            raise ValueError("URLs de claves aportadas por el token no están permitidas")
        algorithm = header.get("alg")
        kid = header.get("kid")
        if algorithm not in settings.jwt_algorithms or not isinstance(kid, str):
            raise ValueError("cabecera JWT no admitida")
        jwks = await _jwks(request, settings)
        keys = jwks["keys"]
        matching = [
            item for item in keys
            if isinstance(item, dict)
            and item.get("kid") == kid
            and item.get("alg", algorithm) == algorithm
            and item.get("use", "sig") == "sig"
        ]
        if len(matching) != 1:
            request.app.state.jwks_cache = None
            jwks = await _jwks(request, settings)
            matching = [
                item for item in jwks["keys"]
                if isinstance(item, dict)
                and item.get("kid") == kid
                and item.get("alg", algorithm) == algorithm
                and item.get("use", "sig") == "sig"
            ]
        if len(matching) != 1:
            raise ValueError("no hay una clave de firma para este token")
        key = jwt.PyJWK.from_dict(matching[0], algorithm=algorithm).key
        claims = jwt.decode(
            token,
            key=key,
            algorithms=list(settings.jwt_algorithms),
            audience="authenticated",
            issuer=f"{settings.supabase_url}/auth/v1",
            options={"require": ["exp", "iat", "iss", "aud", "sub"]},
            leeway=30,
        )
        owner_id = str(UUID(claims["sub"]))
        if claims.get("role") != "authenticated" or owner_id not in settings.allowed_user_ids:
            raise ValueError("principal no autorizado")
        return owner_id
    except HTTPException:
        raise
    except Exception as exc:
        # No incluir token, header ni claims en el log/error.
        logger.info("Rejected access token (%s)", type(exc).__name__)
        raise HTTPException(
            status_code=401,
            detail={"code": "invalid_session", "message": "Sesión inválida o vencida"},
            headers={"WWW-Authenticate": "Bearer"},
        ) from None
