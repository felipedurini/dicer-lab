"""Configuración explícita del proceso HTTP del simulador web."""

from __future__ import annotations

from dataclasses import dataclass
import ipaddress
import os
from pathlib import Path
from typing import Mapping
from urllib.parse import urlsplit
from uuid import UUID


class SettingsError(ValueError):
    """Configuración de servicio incompleta o insegura."""


def _url(value: str, name: str, *, https: bool, origin: bool = False) -> str:
    try:
        parsed = urlsplit(value)
        hostname = parsed.hostname
        _ = parsed.port
    except ValueError as exc:
        raise SettingsError(f"{name} debe ser una URL absoluta válida") from exc
    schemes = {"https"} if https else {"http", "https"}
    if (
        parsed.scheme not in schemes
        or not hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or parsed.path not in ("", "/")
    ):
        requirement = "HTTPS" if https else "un esquema HTTP(S)"
        raise SettingsError(f"{name} requiere {requirement}, host y sin ruta/credenciales")
    if origin and (parsed.path not in ("", "/") or parsed.query or parsed.fragment):
        raise SettingsError(f"{name} debe ser solo un origen, sin ruta ni query")
    return value.rstrip("/")


def _is_loopback_url(value: str) -> bool:
    host = urlsplit(value).hostname
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host or "").is_loopback
    except ValueError:
        return False


def _user_ids(value: str | None) -> tuple[str, ...]:
    if not value:
        return ()
    result: list[str] = []
    for raw in value.split(","):
        try:
            parsed = UUID(raw.strip())
        except (ValueError, AttributeError) as exc:
            raise SettingsError("ALLOWED_USER_IDS debe contener UUIDs válidos") from exc
        normalized = str(parsed)
        if normalized in result:
            raise SettingsError("ALLOWED_USER_IDS contiene UUIDs duplicados")
        result.append(normalized)
    return tuple(result)


@dataclass(frozen=True)
class Settings:
    app_env: str
    auth_mode: str
    app_origin: str
    simulator_api_url: str
    data_dir: Path
    port: int
    api_host: str
    web_release: str
    log_level: str
    supabase_url: str | None
    allowed_user_ids: tuple[str, ...]
    jwt_algorithms: tuple[str, ...]

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> Settings:
        """Parsea entorno sin leer principal de petición ni cargar dotenv."""
        env = os.environ if environ is None else environ
        app_env = env.get("APP_ENV", "development")
        auth_mode = env.get("AUTH_MODE", "local")
        if app_env not in {"development", "test", "production"}:
            raise SettingsError("APP_ENV debe ser development, test o production")
        if auth_mode not in {"local", "supabase"}:
            raise SettingsError("AUTH_MODE debe ser local o supabase")
        if app_env == "production" and auth_mode != "supabase":
            raise SettingsError("producción requiere AUTH_MODE=supabase")

        hosted = "VERCEL" in env or "RENDER" in env
        if auth_mode == "local" and (app_env == "production" or hosted):
            raise SettingsError("AUTH_MODE=local solo se permite en desarrollo loopback")

        https = auth_mode == "supabase"
        app_origin = _url(
            env.get("APP_ORIGIN", "http://127.0.0.1:3000"),
            "APP_ORIGIN",
            https=https,
            origin=True,
        )
        api_url = _url(
            env.get("SIMULATOR_API_URL", "http://127.0.0.1:8000"),
            "SIMULATOR_API_URL",
            https=https,
        )
        data_value = env.get("DATA_DIR")
        if data_value is None and app_env in {"development", "test"}:
            data_dir = Path(__file__).resolve().parents[2] / ".local" / "dicer-web"
        else:
            data_dir = Path(data_value or "")
        if not data_value and not (
            data_value is None and app_env in {"development", "test"}
        ):
            raise SettingsError("DATA_DIR debe ser una ruta absoluta no vacía")
        if not data_dir.is_absolute():
            raise SettingsError("DATA_DIR debe ser una ruta absoluta no vacía")
        if data_dir == Path(data_dir.anchor):
            raise SettingsError("DATA_DIR no puede ser la raíz del sistema")

        try:
            port = int(env.get("PORT", "8000"))
        except ValueError as exc:
            raise SettingsError("PORT debe ser un entero entre 1 y 65535") from exc
        if not 1 <= port <= 65535:
            raise SettingsError("PORT debe ser un entero entre 1 y 65535")

        api_host = env.get("API_HOST", "127.0.0.1")
        if auth_mode == "local":
            try:
                loopback_bind = ipaddress.ip_address(api_host).is_loopback
            except ValueError:
                loopback_bind = api_host == "localhost"
            if not loopback_bind or not _is_loopback_url(app_origin) or not _is_loopback_url(api_url):
                raise SettingsError("modo local requiere bind y URLs loopback")
        elif api_host != "0.0.0.0":
            raise SettingsError("API_HOST debe ser 0.0.0.0 en el servicio Render")

        users = _user_ids(env.get("ALLOWED_USER_IDS"))
        supabase_url = env.get("SUPABASE_URL") or None
        algorithms_raw = env.get("SUPABASE_JWT_ALGORITHMS", "")
        algorithms = tuple(item.strip() for item in algorithms_raw.split(",") if item.strip())
        if auth_mode == "supabase":
            if not supabase_url or not users:
                raise SettingsError("Supabase requiere SUPABASE_URL y ALLOWED_USER_IDS")
            supabase_url = _url(supabase_url, "SUPABASE_URL", https=True)
            if not algorithms or any(item not in {"ES256", "RS256"} for item in algorithms):
                raise SettingsError("SUPABASE_JWT_ALGORITHMS solo admite ES256 y/o RS256")
            if len(set(algorithms)) != len(algorithms):
                raise SettingsError("SUPABASE_JWT_ALGORITHMS contiene duplicados")
            if app_env == "production" and (
                _is_loopback_url(app_origin) or _is_loopback_url(api_url)
            ):
                raise SettingsError("producción no puede usar URLs loopback")

        return cls(
            app_env=app_env,
            auth_mode=auth_mode,
            app_origin=app_origin,
            simulator_api_url=api_url,
            data_dir=data_dir,
            port=port,
            api_host=api_host,
            web_release=env.get("WEB_RELEASE", "local"),
            log_level=env.get("LOG_LEVEL", "INFO"),
            supabase_url=supabase_url,
            allowed_user_ids=users,
            jwt_algorithms=algorithms,
        )


def validate_data_dir(settings: Settings) -> None:
    """Crea DATA_DIR y prueba escritura local antes de arrancar servicio."""
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    probe = settings.data_dir / ".write-check"
    try:
        probe.write_bytes(b"ok")
        probe.unlink()
    except OSError as exc:
        raise SettingsError("DATA_DIR no permite escritura del proceso") from exc
