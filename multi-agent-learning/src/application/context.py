from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

from config import ModelProviderConfig, resolve_provider_config
from security.secret_cipher import SecretCipher
from storage.db.session import create_session_factory


@dataclass(frozen=True)
class ServiceContext:
    provider_config: ModelProviderConfig
    thinking_mode: str
    database_url: str
    session_factory: object


@dataclass(frozen=True)
class AppContext:
    database_url: str
    session_factory: object
    secret_cipher: SecretCipher


@dataclass(frozen=True)
class ResolvedModelProfile:
    profile_id: str
    name: str
    provider: str
    model_name: str
    api_key: str
    base_url: str | None
    thinking_mode: str


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _load_runtime_config(config_path: str | None) -> dict:
    cleaned = (config_path or "").strip()
    if not cleaned:
        return {}

    raw_path = Path(cleaned)
    if raw_path.is_absolute():
        resolved_path = raw_path
    else:
        cwd_candidate = Path.cwd() / raw_path
        if cwd_candidate.exists():
            resolved_path = cwd_candidate
        else:
            resolved_path = _project_root() / raw_path
    if not resolved_path.exists():
        return {}

    content = resolved_path.read_text(encoding="utf-8").strip()
    if not content:
        return {}

    data = json.loads(content)
    if not isinstance(data, dict):
        raise ValueError("runtime config must be a JSON object.")
    return data


def _resolve_database_url(database_url: str | None, runtime_config: str | None) -> str:
    cleaned_database_url = (database_url or "").strip()
    if cleaned_database_url:
        return cleaned_database_url

    env_database_url = os.getenv("DATABASE_URL", "").strip()
    if env_database_url:
        return env_database_url

    config = _load_runtime_config(runtime_config)
    raw_config_database_url = config.get("database_url") or config.get("DATABASE_URL")
    if isinstance(raw_config_database_url, str) and raw_config_database_url.strip():
        return raw_config_database_url.strip()

    return ""


def _resolve_app_secret_key(app_secret_key: str | None) -> str:
    cleaned = (app_secret_key or "").strip()
    if cleaned:
        return cleaned

    env_value = os.getenv("APP_SECRET_KEY", "").strip()
    if env_value:
        return env_value

    raise ValueError("APP_SECRET_KEY is required for the operations console.")


def build_app_context(
    *,
    database_url: str | None,
    runtime_config: str | None,
    app_secret_key: str | None,
) -> AppContext:
    resolved_database_url = _resolve_database_url(database_url, runtime_config)
    session_factory = create_session_factory(resolved_database_url)
    return AppContext(
        database_url=resolved_database_url,
        session_factory=session_factory,
        secret_cipher=SecretCipher(_resolve_app_secret_key(app_secret_key)),
    )


def build_service_context(
    *,
    provider: str,
    model: str | None,
    base_url: str | None,
    thinking: str,
    database_url: str | None,
    runtime_config: str | None,
) -> ServiceContext:
    provider_config = resolve_provider_config(
        provider=provider,
        model_name=model,
        base_url=base_url,
    )
    resolved_database_url = _resolve_database_url(database_url, runtime_config)
    session_factory = create_session_factory(resolved_database_url)
    return ServiceContext(
        provider_config=provider_config,
        thinking_mode=thinking,
        database_url=resolved_database_url,
        session_factory=session_factory,
    )
