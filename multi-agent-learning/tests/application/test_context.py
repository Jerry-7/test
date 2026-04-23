from __future__ import annotations

import shutil
from types import SimpleNamespace
from pathlib import Path
from uuid import uuid4

from application.context import _resolve_database_url, build_app_context, build_service_context


def test_build_service_context_uses_resolved_database_url(monkeypatch):
    monkeypatch.setattr(
        "application.context._resolve_database_url",
        lambda database_url, runtime_config: "postgresql://json.example/app",
    )
    monkeypatch.setattr(
        "application.context.resolve_provider_config",
        lambda **_: SimpleNamespace(provider="openai", model_name="gpt-5-mini"),
    )
    monkeypatch.setattr(
        "application.context.create_session_factory",
        lambda database_url: f"session:{database_url}",
    )

    ctx = build_service_context(
        provider="openai",
        model=None,
        base_url=None,
        thinking="default",
        database_url=None,
        runtime_config="config/runtime.json",
    )

    assert ctx.database_url == "postgresql://json.example/app"
    assert ctx.session_factory == "session:postgresql://json.example/app"
    assert ctx.provider_config.provider == "openai"


def test_build_app_context_reads_database_and_secret(monkeypatch):
    monkeypatch.setattr(
        "application.context._resolve_database_url",
        lambda database_url, runtime_config: "postgresql://runtime.example/app",
    )
    monkeypatch.setattr(
        "application.context._resolve_app_secret_key",
        lambda app_secret_key: "console-master-key",
    )
    monkeypatch.setattr(
        "application.context.create_session_factory",
        lambda database_url: f"session:{database_url}",
    )

    ctx = build_app_context(
        database_url=None,
        runtime_config="config/runtime.json",
        app_secret_key=None,
    )

    assert ctx.database_url == "postgresql://runtime.example/app"
    assert ctx.session_factory == "session:postgresql://runtime.example/app"
    assert ctx.secret_cipher.decrypt(ctx.secret_cipher.encrypt("abc")) == "abc"


def test_resolve_database_url_uses_environment_when_arg_missing(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("DATABASE_URL", "postgresql://env.example/app")
    monkeypatch.setattr("application.context._load_runtime_config", lambda _: {})

    assert _resolve_database_url(None, "config/runtime.json") == "postgresql://env.example/app"


def test_resolve_database_url_reads_runtime_config_from_project_root(monkeypatch):
    sandbox_root = Path.cwd() / ".tmp-test-context" / uuid4().hex
    project_root = sandbox_root / "repo"
    other_dir = sandbox_root / "elsewhere"
    config_dir = project_root / "config"
    config_dir.mkdir(parents=True)
    other_dir.mkdir(parents=True)
    (config_dir / "runtime.json").write_text(
        '{"database_url": "postgresql://json.example/app"}',
        encoding="utf-8",
    )

    try:
        monkeypatch.chdir(other_dir)
        monkeypatch.delenv("DATABASE_URL", raising=False)
        monkeypatch.setattr("application.context._project_root", lambda: project_root)

        assert _resolve_database_url(None, "config/runtime.json") == "postgresql://json.example/app"
    finally:
        shutil.rmtree(sandbox_root, ignore_errors=True)
