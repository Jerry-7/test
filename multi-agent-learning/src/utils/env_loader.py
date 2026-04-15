from __future__ import annotations

import os
from pathlib import Path


def load_project_env(
    env_path: str | Path | None = None,
    *,
    override: bool = False,
) -> Path | None:
    """加载项目根目录 `.env` 到当前进程环境变量。"""
    resolved_path = Path(env_path) if env_path is not None else _default_env_path()
    if not resolved_path.exists():
        return None

    for raw_line in resolved_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        if line.startswith("export "):
            line = line[7:].strip()

        if "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip().lstrip("\ufeff")
        value = _normalize_env_value(value.strip())

        if not key:
            continue

        current_value = os.environ.get(key)
        if override or current_value in (None, ""):
            os.environ[key] = value

    return resolved_path


def _default_env_path() -> Path:
    return Path(__file__).resolve().parents[2] / ".env"


def _normalize_env_value(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value
