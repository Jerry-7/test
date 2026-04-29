# Runtime Model Profile Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the operations console boot with only `DATABASE_URL` and `APP_SECRET_KEY`, manage encrypted runtime model profiles in PostgreSQL, and require profile selection for plan creation and run launch.

**Architecture:** Keep the CLI's existing env-based provider flow intact, but refactor the web console to boot with an `AppContext` and resolve a `ResolvedModelProfile` per request. Add a dedicated `model_profiles` table, a `SecretCipher` boundary for reversible encryption, profile-aware application services, new FastAPI CRUD routes, and React UI flows for managing profiles and selecting them during plan/run actions.

**Tech Stack:** Python 3.13, FastAPI, SQLAlchemy 2.x, PostgreSQL, React 18, TypeScript, Vitest, pytest, cryptography

---

## File Structure Map

- Create: `src/security/__init__.py`
- Create: `src/security/secret_cipher.py`
- Create: `src/storage/repositories/model_profile_repository.py`
- Create: `src/console_api/routers/model_profiles.py`
- Create: `tests/security/test_secret_cipher.py`
- Create: `tests/storage/test_model_profile_repository.py`
- Create: `tests/application/test_model_profile_service.py`
- Create: `tests/api/test_model_profiles_api.py`
- Create: `console/src/components/ModelProfileForm.tsx`
- Create: `console/src/routes/ModelProfilesPage.tsx`
- Create: `console/src/test/ModelProfilesPage.test.tsx`
- Create: `console/src/test/PlansPage.test.tsx`
- Modify: `requirements.txt`
- Modify: `.env.example`
- Modify: `README.md`
- Modify: `src/application/context.py`
- Modify: `src/application/services/__init__.py`
- Modify: `src/application/services/plan_service.py`
- Modify: `src/application/services/run_service.py`
- Modify: `src/agents/planner_agent.py`
- Modify: `src/config/model_provider.py`
- Modify: `src/console_api/app.py`
- Modify: `src/console_api/schemas.py`
- Modify: `src/console_api/routers/__init__.py`
- Modify: `src/console_api/routers/plans.py`
- Modify: `src/console_api/routers/runs.py`
- Modify: `src/main.py`
- Modify: `src/storage/db/models.py`
- Modify: `src/storage/repositories/__init__.py`
- Modify: `src/storage/repositories/plan_repository.py`
- Modify: `src/storage/repositories/plan_run_repository.py`
- Modify: `tests/application/test_context.py`
- Modify: `tests/application/test_plan_service.py`
- Modify: `tests/application/test_run_service.py`
- Modify: `tests/api/test_plans_api.py`
- Modify: `tests/api/test_runs_api.py`
- Modify: `tests/integration/test_console_api_flow.py`
- Modify: `tests/storage/test_db_models.py`
- Modify: `tests/storage/test_plan_repository.py`
- Modify: `tests/storage/test_plan_run_repository.py`
- Modify: `console/src/App.tsx`
- Modify: `console/src/api/client.ts`
- Modify: `console/src/components/AppShell.tsx`
- Modify: `console/src/routes/DashboardPage.tsx`
- Modify: `console/src/routes/PlanDetailPage.tsx`
- Modify: `console/src/routes/PlansPage.tsx`
- Modify: `console/src/routes/RunDetailPage.tsx`
- Modify: `console/src/routes/RunsPage.tsx`
- Modify: `console/src/test/App.test.tsx`
- Modify: `console/src/test/RunDetailPage.test.tsx`

---

### Task 1: Add Boot-Time AppContext and Reversible Secret Cipher

**Files:**
- Create: `src/security/__init__.py`
- Create: `src/security/secret_cipher.py`
- Modify: `src/application/context.py`
- Modify: `tests/application/test_context.py`
- Create: `tests/security/test_secret_cipher.py`
- Modify: `requirements.txt`

- [ ] **Step 1: Write the failing tests**

```python
# tests/security/test_secret_cipher.py
from security.secret_cipher import SecretCipher


def test_secret_cipher_round_trips_plaintext():
    cipher = SecretCipher("local-dev-master-key")

    encrypted = cipher.encrypt("sk-test-123456")

    assert encrypted != "sk-test-123456"
    assert cipher.decrypt(encrypted) == "sk-test-123456"
```

```python
# tests/application/test_context.py
from application.context import build_app_context


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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `py -3 -m pytest tests/security/test_secret_cipher.py tests/application/test_context.py -v`
Expected: `FAIL` with `ModuleNotFoundError` for `security.secret_cipher` and `ImportError` for `build_app_context`

- [ ] **Step 3: Write the minimal implementation**

```python
# src/security/secret_cipher.py
from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken


class SecretCipher:
    def __init__(self, master_key: str):
        cleaned = master_key.strip()
        if not cleaned:
            raise ValueError("APP_SECRET_KEY cannot be empty.")
        digest = hashlib.sha256(cleaned.encode("utf-8")).digest()
        self._fernet = Fernet(base64.urlsafe_b64encode(digest))

    def encrypt(self, plaintext: str) -> str:
        cleaned = plaintext.strip()
        if not cleaned:
            raise ValueError("api_key cannot be empty.")
        return self._fernet.encrypt(cleaned.encode("utf-8")).decode("utf-8")

    def decrypt(self, ciphertext: str) -> str:
        cleaned = ciphertext.strip()
        if not cleaned:
            raise ValueError("ciphertext cannot be empty.")
        try:
            return self._fernet.decrypt(cleaned.encode("utf-8")).decode("utf-8")
        except InvalidToken as exc:
            raise ValueError("Unable to decrypt stored API key with APP_SECRET_KEY.") from exc
```

```python
# src/security/__init__.py
from .secret_cipher import SecretCipher
```

```python
# src/application/context.py
from dataclasses import dataclass
import os

from security.secret_cipher import SecretCipher


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
```

```text
# requirements.txt
langchain==1.2.15
langchain-openai==1.1.12
sqlalchemy==2.0.41
psycopg[binary]==3.2.9
pytest==8.3.5
fastapi==0.116.1
uvicorn==0.35.0
httpx==0.28.1
cryptography==45.0.6
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `py -3 -m pytest tests/security/test_secret_cipher.py tests/application/test_context.py -v`
Expected: both tests `PASS`

- [ ] **Step 5: Commit**

```bash
git add requirements.txt src/security/__init__.py src/security/secret_cipher.py src/application/context.py tests/application/test_context.py tests/security/test_secret_cipher.py
git commit -m "feat: add app context and secret cipher for console boot"
```

### Task 2: Extend Database Schema for Model Profiles and Profile References

**Files:**
- Modify: `src/storage/db/models.py`
- Modify: `tests/storage/test_db_models.py`
- Modify: `tests/storage/test_plan_repository.py`
- Modify: `tests/storage/test_plan_run_repository.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/storage/test_db_models.py
from storage.db.models import Base, ModelProfileRow, PlanRow, PlanRunRow


def test_schema_contains_model_profile_table_and_relationship_columns():
    table_names = set(Base.metadata.tables.keys())

    assert "model_profiles" in table_names
    assert "model_profile_id" in ModelProfileRow.__table__.primary_key.columns.keys()
    assert "model_profile_id" in PlanRow.__table__.columns.keys()
    assert "model_profile_id" in PlanRunRow.__table__.columns.keys()
```

```python
# tests/storage/test_plan_repository.py
from models.plan_task import PlanTask
from storage.db.models import ModelProfileRow
from storage.repositories.plan_repository import PlanRepository


def test_save_plan_persists_model_profile_id(db_session):
    profile = ModelProfileRow(
        name="Primary",
        provider="openai",
        model_name="gpt-5-mini",
        base_url=None,
        thinking_mode="default",
        api_key_encrypted="cipher",
        api_key_hint="****3456",
    )
    db_session.add(profile)
    db_session.commit()
    repo = PlanRepository(session_factory=lambda: db_session)

    plan_id = repo.save_plan(
        goal="profile-aware plan",
        model_profile_id=str(profile.model_profile_id),
        provider="openai",
        model_name="gpt-5-mini",
        thinking_mode="default",
        tasks=[PlanTask(id="task-1", title="Analyze", type="analysis", depends_on=[], status="pending", priority=1)],
    )

    summary = repo.get_plan_summary(plan_id)
    assert summary["model_profile_id"] == str(profile.model_profile_id)
```

```python
# tests/storage/test_plan_run_repository.py
from storage.db.models import ModelProfileRow, PlanRow
from storage.repositories.plan_run_repository import PlanRunRepository


def test_create_run_persists_model_profile_id(db_session):
    profile = ModelProfileRow(
        name="Primary",
        provider="openai",
        model_name="gpt-5-mini",
        base_url=None,
        thinking_mode="default",
        api_key_encrypted="cipher",
        api_key_hint="****3456",
    )
    db_session.add(profile)
    db_session.flush()
    plan = PlanRow(
        model_profile_id=profile.model_profile_id,
        source_goal="goal",
        provider="openai",
        model_name="gpt-5-mini",
        thinking_mode="default",
    )
    db_session.add(plan)
    db_session.commit()

    repo = PlanRunRepository(session_factory=lambda: db_session)

    run_id = repo.create_run(
        plan_id=str(plan.plan_id),
        model_profile_id=str(profile.model_profile_id),
        max_workers=1,
        started_at="2026-04-23T00:00:00+00:00",
    )

    summary = repo.get_run_summary(run_id)
    assert summary["model_profile_id"] == str(profile.model_profile_id)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `py -3 -m pytest tests/storage/test_db_models.py tests/storage/test_plan_repository.py tests/storage/test_plan_run_repository.py -v`
Expected: `FAIL` because `ModelProfileRow` and `model_profile_id` fields do not exist

- [ ] **Step 3: Write the minimal implementation**

```python
# src/storage/db/models.py
class ModelProfileRow(Base):
    __tablename__ = "model_profiles"

    model_profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    model_name: Mapped[str] = mapped_column(String(128), nullable=False)
    base_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    thinking_mode: Mapped[str] = mapped_column(String(32), nullable=False)
    api_key_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    api_key_hint: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class PlanRow(Base):
    __tablename__ = "plans"

    plan_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    model_profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("model_profiles.model_profile_id", ondelete="RESTRICT"),
        nullable=False,
    )
    source_goal: Mapped[str] = mapped_column(Text, nullable=False)
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    model_name: Mapped[str] = mapped_column(String(128), nullable=False)
    thinking_mode: Mapped[str] = mapped_column(String(32), nullable=False)
```

```python
# src/storage/db/models.py
class PlanRunRow(Base):
    __tablename__ = "plan_runs"

    run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    plan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("plans.plan_id", ondelete="CASCADE"),
        nullable=False,
    )
    model_profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("model_profiles.model_profile_id", ondelete="RESTRICT"),
        nullable=False,
    )
    max_workers: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `py -3 -m pytest tests/storage/test_db_models.py tests/storage/test_plan_repository.py tests/storage/test_plan_run_repository.py -v`
Expected: all targeted tests `PASS`

- [ ] **Step 5: Commit**

```bash
git add src/storage/db/models.py tests/storage/test_db_models.py tests/storage/test_plan_repository.py tests/storage/test_plan_run_repository.py
git commit -m "feat: add model profile schema and profile references"
```

### Task 3: Implement ModelProfile Repository and Service

**Files:**
- Create: `src/storage/repositories/model_profile_repository.py`
- Modify: `src/storage/repositories/__init__.py`
- Create: `tests/storage/test_model_profile_repository.py`
- Create: `tests/application/test_model_profile_service.py`
- Modify: `src/application/services/__init__.py`
- Create: `src/application/services/model_profile_service.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/storage/test_model_profile_repository.py
from storage.repositories.model_profile_repository import ModelProfileRepository


def test_create_and_get_model_profile_roundtrip(db_session):
    repo = ModelProfileRepository(session_factory=lambda: db_session)

    profile_id = repo.create_profile(
        name="OpenAI Main",
        provider="openai",
        model_name="gpt-5-mini",
        base_url=None,
        thinking_mode="default",
        api_key_encrypted="cipher-text",
        api_key_hint="****3456",
    )

    profile = repo.get_profile(profile_id)

    assert profile["name"] == "OpenAI Main"
    assert profile["api_key_encrypted"] == "cipher-text"
```

```python
# tests/application/test_model_profile_service.py
from application.services.model_profile_service import ModelProfileService
from security.secret_cipher import SecretCipher


def test_service_returns_plaintext_for_detail_but_not_list():
    service = ModelProfileService(
        repository=type(
            "Repo",
            (),
            {
                "create_profile": lambda self, **kwargs: "profile-1",
                "list_profiles": lambda self: [
                    {
                        "model_profile_id": "profile-1",
                        "name": "OpenAI Main",
                        "provider": "openai",
                        "model_name": "gpt-5-mini",
                        "base_url": None,
                        "thinking_mode": "default",
                        "api_key_hint": "****3456",
                        "updated_at": "2026-04-23T00:00:00+00:00",
                    }
                ],
                "get_profile": lambda self, profile_id: {
                    "model_profile_id": profile_id,
                    "name": "OpenAI Main",
                    "provider": "openai",
                    "model_name": "gpt-5-mini",
                    "base_url": None,
                    "thinking_mode": "default",
                    "api_key_hint": "****3456",
                    "api_key_encrypted": SecretCipher("dev-key").encrypt("sk-openai-3456"),
                    "updated_at": "2026-04-23T00:00:00+00:00",
                },
            },
        )(),
        secret_cipher=SecretCipher("dev-key"),
    )

    detail = service.get_profile("profile-1")

    assert detail["api_key"] == "sk-openai-3456"
    assert service.list_profiles()[0]["api_key_hint"] == "****3456"
    assert "api_key" not in service.list_profiles()[0]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `py -3 -m pytest tests/storage/test_model_profile_repository.py tests/application/test_model_profile_service.py -v`
Expected: `FAIL` with missing repository and service modules

- [ ] **Step 3: Write the minimal implementation**

```python
# src/storage/repositories/model_profile_repository.py
from __future__ import annotations

from typing import Callable
from uuid import UUID

from storage.db.models import ModelProfileRow


class ModelProfileRepository:
    def __init__(self, session_factory: Callable[[], object]):
        self._session_factory = session_factory

    def create_profile(self, **kwargs) -> str:
        with self._session_factory() as session:
            row = ModelProfileRow(**kwargs)
            session.add(row)
            session.commit()
            return str(row.model_profile_id)

    def list_profiles(self) -> list[dict[str, object]]:
        with self._session_factory() as session:
            rows = session.query(ModelProfileRow).order_by(ModelProfileRow.updated_at.desc()).all()
            return [
                {
                    "model_profile_id": str(row.model_profile_id),
                    "name": row.name,
                    "provider": row.provider,
                    "model_name": row.model_name,
                    "base_url": row.base_url,
                    "thinking_mode": row.thinking_mode,
                    "api_key_hint": row.api_key_hint,
                    "updated_at": row.updated_at.isoformat(),
                }
                for row in rows
            ]

    def get_profile(self, profile_id: str) -> dict[str, object]:
        with self._session_factory() as session:
            row = session.query(ModelProfileRow).filter(ModelProfileRow.model_profile_id == UUID(profile_id)).one()
            return {
                "model_profile_id": str(row.model_profile_id),
                "name": row.name,
                "provider": row.provider,
                "model_name": row.model_name,
                "base_url": row.base_url,
                "thinking_mode": row.thinking_mode,
                "api_key_hint": row.api_key_hint,
                "api_key_encrypted": row.api_key_encrypted,
                "updated_at": row.updated_at.isoformat(),
            }
```

```python
# src/application/services/model_profile_service.py
from __future__ import annotations

from application.context import ResolvedModelProfile
from config import get_supported_providers


class ModelProfileService:
    def __init__(self, *, repository, secret_cipher):
        self._repository = repository
        self._secret_cipher = secret_cipher

    def create_profile(self, *, name, provider, model_name, base_url, thinking_mode, api_key):
        self._validate(provider=provider, thinking_mode=thinking_mode, api_key=api_key, name=name, model_name=model_name)
        encrypted = self._secret_cipher.encrypt(api_key)
        profile_id = self._repository.create_profile(
            name=name.strip(),
            provider=provider.strip().lower(),
            model_name=model_name.strip(),
            base_url=(base_url or "").strip() or None,
            thinking_mode=thinking_mode,
            api_key_encrypted=encrypted,
            api_key_hint=self._build_api_key_hint(api_key),
        )
        return self.get_profile(profile_id)

    def list_profiles(self) -> list[dict[str, object]]:
        return self._repository.list_profiles()

    def get_profile(self, profile_id: str) -> dict[str, object]:
        row = self._repository.get_profile(profile_id)
        return {
            "model_profile_id": row["model_profile_id"],
            "name": row["name"],
            "provider": row["provider"],
            "model_name": row["model_name"],
            "base_url": row["base_url"],
            "thinking_mode": row["thinking_mode"],
            "api_key_hint": row["api_key_hint"],
            "api_key": self._secret_cipher.decrypt(row["api_key_encrypted"]),
            "updated_at": row["updated_at"],
        }

    def resolve_runtime_profile(self, profile_id: str) -> ResolvedModelProfile:
        row = self._repository.get_profile(profile_id)
        return ResolvedModelProfile(
            profile_id=row["model_profile_id"],
            name=row["name"],
            provider=row["provider"],
            model_name=row["model_name"],
            api_key=self._secret_cipher.decrypt(row["api_key_encrypted"]),
            base_url=row["base_url"],
            thinking_mode=row["thinking_mode"],
        )

    def _build_api_key_hint(self, api_key: str) -> str:
        cleaned = api_key.strip()
        return f"****{cleaned[-4:]}" if len(cleaned) >= 4 else "****"

    def _validate(self, *, provider: str, thinking_mode: str, api_key: str, name: str, model_name: str) -> None:
        if provider.strip().lower() not in get_supported_providers():
            raise ValueError(f"Unsupported provider: {provider}")
        if thinking_mode not in {"default", "on", "off"}:
            raise ValueError(f"Unsupported thinking_mode: {thinking_mode}")
        if not name.strip() or not model_name.strip() or not api_key.strip():
            raise ValueError("name, model_name, and api_key are required.")
```

```python
# src/storage/repositories/__init__.py
from .execution_repository import ExecutionRepository
from .model_profile_repository import ModelProfileRepository
from .plan_repository import PlanRepository
from .plan_run_repository import PlanRunRepository
```

```python
# src/application/services/__init__.py
from .model_profile_service import ModelProfileService
from .plan_service import PlanService
from .run_service import RunService
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `py -3 -m pytest tests/storage/test_model_profile_repository.py tests/application/test_model_profile_service.py -v`
Expected: both tests `PASS`

- [ ] **Step 5: Commit**

```bash
git add src/storage/repositories/model_profile_repository.py src/storage/repositories/__init__.py src/application/services/__init__.py src/application/services/model_profile_service.py tests/storage/test_model_profile_repository.py tests/application/test_model_profile_service.py
git commit -m "feat: add model profile repository and service"
```

### Task 4: Refactor Plan and Run Services for Request-Scoped Runtime Resolution

**Files:**
- Modify: `src/config/model_provider.py`
- Modify: `src/main.py`
- Modify: `src/application/services/plan_service.py`
- Modify: `src/application/services/run_service.py`
- Modify: `src/agents/planner_agent.py`
- Modify: `src/storage/repositories/plan_repository.py`
- Modify: `src/storage/repositories/plan_run_repository.py`
- Modify: `tests/application/test_plan_service.py`
- Modify: `tests/application/test_run_service.py`
- Modify: `tests/storage/test_plan_repository.py`
- Modify: `tests/storage/test_plan_run_repository.py`
- Modify: `tests/integration/test_console_api_flow.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/application/test_plan_service.py
from application.services.plan_service import PlanService


def test_create_plan_resolves_runtime_profile_before_building_planner():
    captured = {}

    service = PlanService(
        model_profile_service=type(
            "ProfileService",
            (),
            {
                "resolve_runtime_profile": lambda self, profile_id: type(
                    "Profile",
                    (),
                    {
                        "profile_id": profile_id,
                        "provider": "openai",
                        "model_name": "gpt-5-mini",
                        "api_key": "sk-openai-1234",
                        "base_url": None,
                        "thinking_mode": "default",
                    },
                )()
            },
        )(),
        planner_agent_factory=lambda profile: type(
            "PlannerAgent",
            (),
            {
                "run": lambda self, task: captured.update({"provider": profile.provider, "task": task}) or type(
                    "PlannerRunResult",
                    (),
                    {"plan_id": "plan-123"},
                )()
            },
        )(),
        plan_repository=type(
            "PlanRepository",
            (),
            {"get_plan_summary": lambda self, plan_id: {"plan_id": plan_id, "model_profile_id": "profile-1", "tasks": []}},
        )(),
    )

    result = service.create_plan(task="learn console", profile_id="profile-1")

    assert result["plan_id"] == "plan-123"
    assert captured == {"provider": "openai", "task": "learn console"}
```

```python
# tests/application/test_run_service.py
from application.services.run_service import RunService


def test_start_run_uses_selected_profile_and_reuses_created_run_id(monkeypatch):
    calls = []

    class _FakeThread:
        def __init__(self, *, target, args, daemon):
            self._target = target
            self._args = args
            self.daemon = daemon

        def start(self):
            self._target(*self._args)

    monkeypatch.setattr("application.services.run_service.threading.Thread", _FakeThread)

    service = RunService(
        model_profile_service=type(
            "ProfileService",
            (),
            {
                "resolve_runtime_profile": lambda self, profile_id: type(
                    "Profile",
                    (),
                    {
                        "profile_id": profile_id,
                        "provider": "openai",
                        "model_name": "gpt-5-mini",
                        "api_key": "sk-openai-1234",
                        "base_url": None,
                        "thinking_mode": "default",
                    },
                )()
            },
        )(),
        plan_repository=type(
            "PlanRepo",
            (),
            {"get_plan_summary": lambda self, plan_id: {"plan_id": plan_id, "model_profile_id": "profile-plan"}},
        )(),
        plan_run_repository=type(
            "RunRepo",
            (),
            {
                "create_run": lambda self, plan_id, model_profile_id, max_workers, started_at: "run-123",
                "get_run_summary": lambda self, run_id: {"run_id": run_id, "plan_id": "plan-1", "model_profile_id": "profile-2", "max_workers": 2},
            },
        )(),
        execution_repository=type("ExecRepo", (), {"load_by_task_ids": lambda self, ids: []})(),
        plan_runner_factory=lambda profile, max_workers: type(
            "Runner",
            (),
            {"run_from_plan_id": lambda self, plan_id, run_id=None: calls.append((profile.profile_id, plan_id, run_id, max_workers))},
        )(),
        utc_now=lambda: "2026-04-23T00:00:00+00:00",
    )

    service.start_run(plan_id="plan-1", profile_id="profile-2", max_workers=2)

    assert calls == [("profile-2", "plan-1", "run-123", 2)]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `py -3 -m pytest tests/application/test_plan_service.py tests/application/test_run_service.py -v`
Expected: `FAIL` because `create_plan(..., profile_id=...)` and `start_run(..., profile_id=...)` are not implemented

- [ ] **Step 3: Write the minimal implementation**

```python
# src/agents/planner_agent.py
class PlannerAgent:
    def __init__(
        self,
        provider_config: ModelProviderConfig,
        thinking_mode: str = "default",
        plan_repository: PlanRepository | None = None,
        model_profile_id: str | None = None,
    ):
        self.provider_config = provider_config
        self.thinking_mode = thinking_mode
        self.plan_repository = plan_repository or self._build_default_plan_repository()
        self.model_profile_id = model_profile_id

    def run(self, goal: str, path: str | None = None) -> PlannerRunResult:
        cleaned_goal = goal.strip()
        if not cleaned_goal:
            raise ValueError("Goal cannot be empty.")
        if not self.model_profile_id:
            raise RuntimeError("PlannerAgent requires model_profile_id in console mode.")
        plan = self._handle_goal(cleaned_goal)
        plan_id = self.plan_repository.save_plan(
            goal=cleaned_goal,
            model_profile_id=self.model_profile_id,
            provider=self.provider_config.provider,
            model_name=self.provider_config.model_name,
            thinking_mode=self.thinking_mode,
            tasks=plan,
        )
        return PlannerRunResult(plan_id=plan_id, tasks=tuple(plan))
```

```python
# src/config/model_provider.py
def build_provider_config_from_runtime_profile(profile) -> ModelProviderConfig:
    normalized = profile.provider.strip().lower()
    if normalized not in PROVIDER_PRESETS:
        supported = ", ".join(get_supported_providers())
        raise ValueError(f"Unsupported provider: {profile.provider}. Supported providers: {supported}.")

    return ModelProviderConfig(
        provider=normalized,
        model_name=profile.model_name,
        api_key=profile.api_key,
        base_url=profile.base_url or PROVIDER_PRESETS[normalized].default_base_url,
        api_key_env="MODEL_PROFILE",
        default_headers=_build_default_headers(normalized),
    )
```

```python
# src/application/services/plan_service.py
class PlanService:
    def __init__(self, *, model_profile_service, planner_agent_factory, plan_repository):
        self._model_profile_service = model_profile_service
        self._planner_agent_factory = planner_agent_factory
        self._plan_repository = plan_repository

    def create_plan(self, *, task: str, profile_id: str) -> dict[str, object]:
        runtime_profile = self._model_profile_service.resolve_runtime_profile(profile_id)
        planner_agent = self._planner_agent_factory(runtime_profile)
        result = planner_agent.run(task)
        return self._plan_repository.get_plan_summary(result.plan_id)
```

```python
# src/application/services/run_service.py
class RunService:
    def __init__(
        self,
        *,
        model_profile_service,
        plan_repository,
        plan_run_repository,
        execution_repository,
        plan_runner_factory,
        utc_now=None,
    ):
        self._model_profile_service = model_profile_service
        self._plan_repository = plan_repository
        self._plan_run_repository = plan_run_repository
        self._execution_repository = execution_repository
        self._plan_runner_factory = plan_runner_factory
        self._utc_now = utc_now or (lambda: datetime.now(timezone.utc).isoformat())

    def start_run(self, *, plan_id: str, profile_id: str, max_workers: int) -> dict[str, object]:
        self._plan_repository.get_plan_summary(plan_id)
        runtime_profile = self._model_profile_service.resolve_runtime_profile(profile_id)
        run_id = self._plan_run_repository.create_run(
            plan_id=plan_id,
            model_profile_id=profile_id,
            max_workers=max_workers,
            started_at=self._utc_now(),
        )
        plan_runner = self._plan_runner_factory(runtime_profile, max_workers)
        worker = threading.Thread(
            target=plan_runner.run_from_plan_id,
            args=(plan_id, run_id),
            daemon=True,
        )
        worker.start()
        return {"run_id": run_id, "plan_id": plan_id, "model_profile_id": profile_id, "status": "running"}

    def retry_run(self, run_id: str, profile_id: str | None = None) -> dict[str, object]:
        run_summary = self._plan_run_repository.get_run_summary(run_id)
        return self.start_run(
            plan_id=run_summary["plan_id"],
            profile_id=profile_id or run_summary["model_profile_id"],
            max_workers=run_summary["max_workers"],
        )
```

```python
# src/storage/repositories/plan_repository.py
def save_plan(
    self,
    goal: str,
    model_profile_id: str,
    provider: str,
    model_name: str,
    thinking_mode: str,
    tasks: list[PlanTask],
) -> str:
    with self._session_factory() as session:
        plan = PlanRow(
            model_profile_id=UUID(model_profile_id),
            source_goal=goal,
            provider=provider,
            model_name=model_name,
            thinking_mode=thinking_mode,
        )
        session.add(plan)
        session.flush()
        for item in tasks:
            session.add(
                PlanTaskRow(
                    plan_id=plan.plan_id,
                    task_id=item.id,
                    title=item.title,
                    type=item.type,
                    priority=item.priority,
                    status=item.status,
                    depends_on=item.depends_on,
                )
            )
        session.commit()
        return str(plan.plan_id)

def get_plan_summary(self, plan_id: str) -> dict[str, object]:
    with self._session_factory() as session:
        plan_row, profile_row = (
            session.query(PlanRow, ModelProfileRow)
            .join(
                ModelProfileRow,
                ModelProfileRow.model_profile_id == PlanRow.model_profile_id,
            )
            .filter(PlanRow.plan_id == UUID(plan_id))
            .one()
        )
        task_rows = (
            session.query(PlanTaskRow)
            .filter(PlanTaskRow.plan_id == UUID(plan_id))
            .order_by(PlanTaskRow.priority.asc(), PlanTaskRow.task_id.asc())
            .all()
        )
        return {
            "plan_id": str(plan_row.plan_id),
            "model_profile_id": str(plan_row.model_profile_id),
            "model_profile_name": profile_row.name,
            "source_goal": plan_row.source_goal,
            "provider": plan_row.provider,
            "model_name": plan_row.model_name,
            "thinking_mode": plan_row.thinking_mode,
            "tasks": [
                {
                    "task_id": row.task_id,
                    "title": row.title,
                    "type": row.type,
                    "priority": row.priority,
                    "status": row.status,
                    "depends_on": list(row.depends_on),
                }
                for row in task_rows
            ],
        }
```

```python
# src/storage/repositories/plan_run_repository.py
def create_run(
    self,
    plan_id: str,
    model_profile_id: str,
    max_workers: int,
    started_at: str,
) -> str:
    started_at_dt = self._parse_datetime_or_raise(
        value=started_at,
        field_name="started_at",
    )
    with self._session_factory() as session:
        row = PlanRunRow(
            plan_id=UUID(plan_id),
            model_profile_id=UUID(model_profile_id),
            max_workers=max_workers,
            status=TASK_STATUS_RUNNING,
            started_at=started_at_dt,
            ended_at=None,
        )
        session.add(row)
        session.commit()
        return str(row.run_id)

def get_run(self, run_id: str) -> dict[str, object]:
    with self._session_factory() as session:
        row, profile_row = (
            session.query(PlanRunRow, ModelProfileRow)
            .join(
                ModelProfileRow,
                ModelProfileRow.model_profile_id == PlanRunRow.model_profile_id,
            )
            .filter(PlanRunRow.run_id == UUID(run_id))
            .one()
        )
        return {
            "run_id": str(row.run_id),
            "plan_id": str(row.plan_id),
            "model_profile_id": str(row.model_profile_id),
            "model_profile_name": profile_row.name,
            "provider": profile_row.provider,
            "model_name": profile_row.model_name,
            "max_workers": row.max_workers,
            "status": row.status,
            "started_at": row.started_at.isoformat(),
            "ended_at": row.ended_at.isoformat() if row.ended_at else None,
        }
```

```python
# src/main.py
from config import build_provider_config_from_runtime_profile


def build_planner_agent_for_profile(profile, plan_repository: PlanRepository) -> PlannerAgent:
    provider_config = build_provider_config_from_runtime_profile(profile)
    return _build_planner_agent(
        provider_config=provider_config,
        thinking_mode=profile.thinking_mode,
        plan_repository=plan_repository,
        model_profile_id=profile.profile_id,
    )


def build_plan_runner_for_profile(
    profile,
    *,
    database_url: str,
    session_factory,
    max_workers: int,
    plan_repository: PlanRepository,
    plan_run_repository: PlanRunRepository,
) -> PlanRunner:
    provider_config = build_provider_config_from_runtime_profile(profile)
    store = ExecutionStore(database_url=database_url, session_factory=session_factory)
    analysis_agent, implementation_agent, review_agent = _build_worker_agents(
        store=store,
        provider_config=provider_config,
        thinking_mode=profile.thinking_mode,
    )
    dispatcher = _build_dispatcher(
        analysis_agent=analysis_agent,
        implementation_agent=implementation_agent,
        review_agent=review_agent,
    )
    return _build_plan_runner(
        dispatcher=dispatcher,
        max_workers=max_workers,
        plan_repository=plan_repository,
        plan_run_repository=plan_run_repository,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `py -3 -m pytest tests/application/test_plan_service.py tests/application/test_run_service.py tests/storage/test_plan_repository.py tests/storage/test_plan_run_repository.py tests/integration/test_console_api_flow.py -v`
Expected: all targeted tests `PASS`

- [ ] **Step 5: Commit**

```bash
git add src/config/model_provider.py src/main.py src/agents/planner_agent.py src/application/services/plan_service.py src/application/services/run_service.py src/storage/repositories/plan_repository.py src/storage/repositories/plan_run_repository.py tests/application/test_plan_service.py tests/application/test_run_service.py tests/storage/test_plan_repository.py tests/storage/test_plan_run_repository.py tests/integration/test_console_api_flow.py
git commit -m "feat: make plan and run services resolve model profiles per request"
```

### Task 5: Add Profile CRUD API and Profile-Aware Plan and Run Endpoints

**Files:**
- Create: `src/console_api/routers/model_profiles.py`
- Modify: `src/console_api/routers/__init__.py`
- Modify: `src/console_api/routers/plans.py`
- Modify: `src/console_api/routers/runs.py`
- Modify: `src/console_api/schemas.py`
- Modify: `src/console_api/app.py`
- Create: `tests/api/test_model_profiles_api.py`
- Modify: `tests/api/test_plans_api.py`
- Modify: `tests/api/test_runs_api.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/api/test_model_profiles_api.py
from fastapi.testclient import TestClient

from console_api.app import create_app
from console_api.routers.model_profiles import get_model_profile_service


def test_get_model_profiles_returns_profile_list():
    app = create_app()
    app.dependency_overrides[get_model_profile_service] = lambda: type(
        "ModelProfileService",
        (),
        {
            "list_profiles": lambda self: [
                {
                    "model_profile_id": "profile-1",
                    "name": "OpenAI Main",
                    "provider": "openai",
                    "model_name": "gpt-5-mini",
                    "base_url": None,
                    "thinking_mode": "default",
                    "api_key_hint": "****3456",
                    "updated_at": "2026-04-23T00:00:00+00:00",
                }
            ]
        },
    )()
    client = TestClient(app)

    response = client.get("/api/model-profiles")

    assert response.status_code == 200
    assert response.json()[0]["model_profile_id"] == "profile-1"
```

```python
# tests/api/test_plans_api.py
def test_post_plans_requires_profile_id():
    app = create_app()
    app.dependency_overrides[get_plan_service] = lambda: type(
        "PlanService",
        (),
        {
            "create_plan": lambda self, task, profile_id: {
                "plan_id": "plan-123",
                "source_goal": task,
                "model_profile_id": profile_id,
                "tasks": [],
            }
        },
    )()
    client = TestClient(app)

    response = client.post(
        "/api/plans",
        json={"task": "learn multi-agent", "profile_id": "profile-1"},
    )

    assert response.status_code == 201
    assert response.json()["model_profile_id"] == "profile-1"
```

```python
# tests/api/test_runs_api.py
def test_post_runs_requires_profile_id():
    app = create_app()
    app.dependency_overrides[get_run_service] = lambda: type(
        "RunService",
        (),
        {
            "start_run": lambda self, plan_id, profile_id, max_workers: {
                "run_id": "run-456",
                "plan_id": plan_id,
                "model_profile_id": profile_id,
                "status": "running",
            }
        },
    )()
    client = TestClient(app)

    response = client.post(
        "/api/runs",
        json={"plan_id": "plan-1", "profile_id": "profile-1", "max_workers": 1},
    )

    assert response.status_code == 201
    assert response.json()["model_profile_id"] == "profile-1"


def test_post_runs_retry_accepts_profile_override():
    app = create_app()
    app.dependency_overrides[get_run_service] = lambda: type(
        "RunService",
        (),
        {
            "retry_run": lambda self, run_id, profile_id=None: {
                "run_id": "run-789",
                "plan_id": "plan-1",
                "model_profile_id": profile_id or "profile-1",
                "status": "running",
            }
        },
    )()
    client = TestClient(app)

    response = client.post(
        "/api/runs/run-123/retry",
        json={"profile_id": "profile-2"},
    )

    assert response.status_code == 201
    assert response.json()["model_profile_id"] == "profile-2"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `py -3 -m pytest tests/api/test_model_profiles_api.py tests/api/test_plans_api.py tests/api/test_runs_api.py -v`
Expected: `FAIL` because the router, request schema, and new endpoint signatures do not exist

- [ ] **Step 3: Write the minimal implementation**

```python
# src/console_api/schemas.py
from pydantic import BaseModel, Field


class CreateModelProfileRequest(BaseModel):
    name: str = Field(min_length=1)
    provider: str = Field(min_length=1)
    model_name: str = Field(min_length=1)
    base_url: str | None = None
    thinking_mode: str = Field(default="default")
    api_key: str = Field(min_length=1)


class UpdateModelProfileRequest(CreateModelProfileRequest):
    pass


class CreatePlanRequest(BaseModel):
    task: str = Field(min_length=1)
    profile_id: str = Field(min_length=1)


class StartRunRequest(BaseModel):
    plan_id: str = Field(min_length=1)
    profile_id: str = Field(min_length=1)
    max_workers: int = Field(default=1, ge=1)


class RetryRunRequest(BaseModel):
    profile_id: str | None = None
```

```python
# src/console_api/routers/model_profiles.py
from fastapi import APIRouter, Depends, Request, status

from console_api.schemas import CreateModelProfileRequest, UpdateModelProfileRequest

router = APIRouter(prefix="/api/model-profiles", tags=["model-profiles"])


def get_model_profile_service(request: Request):
    return request.app.state.model_profile_service


@router.get("")
def list_model_profiles(service=Depends(get_model_profile_service)):
    return service.list_profiles()


@router.post("", status_code=status.HTTP_201_CREATED)
def create_model_profile(payload: CreateModelProfileRequest, service=Depends(get_model_profile_service)):
    return service.create_profile(**payload.model_dump())


@router.get("/{profile_id}")
def get_model_profile(profile_id: str, service=Depends(get_model_profile_service)):
    return service.get_profile(profile_id)


@router.put("/{profile_id}")
def update_model_profile(profile_id: str, payload: UpdateModelProfileRequest, service=Depends(get_model_profile_service)):
    return service.update_profile(profile_id, **payload.model_dump())


@router.delete("/{profile_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_model_profile(profile_id: str, service=Depends(get_model_profile_service)):
    service.delete_profile(profile_id)


@router.post("/{profile_id}/duplicate", status_code=status.HTTP_201_CREATED)
def duplicate_model_profile(profile_id: str, service=Depends(get_model_profile_service)):
    return service.duplicate_profile(profile_id)
```

```python
# src/console_api/routers/plans.py
@router.post("", status_code=status.HTTP_201_CREATED)
def create_plan(payload: CreatePlanRequest, service=Depends(get_plan_service)):
    return service.create_plan(task=payload.task, profile_id=payload.profile_id)
```

```python
# src/console_api/routers/runs.py
from fastapi import Body

from console_api.schemas import RetryRunRequest, StartRunRequest


@router.post("", status_code=status.HTTP_201_CREATED)
def start_run(payload: StartRunRequest, service=Depends(get_run_service)):
    return service.start_run(
        plan_id=payload.plan_id,
        profile_id=payload.profile_id,
        max_workers=payload.max_workers,
    )


@router.post("/{run_id}/retry", status_code=status.HTTP_201_CREATED)
def retry_run(
    run_id: str,
    payload: RetryRunRequest = Body(default=RetryRunRequest()),
    service=Depends(get_run_service),
):
    return service.retry_run(run_id, profile_id=payload.profile_id)
```

```python
# src/console_api/app.py
from application.context import build_app_context
from application.services import ModelProfileService, PlanService, RunService
from console_api.routers import model_profiles, plans, runs
from main import build_planner_agent_for_profile, build_plan_runner_for_profile
from storage.repositories import ExecutionRepository, ModelProfileRepository, PlanRepository, PlanRunRepository


def _build_services(ctx) -> dict[str, object]:
    model_profile_repository = ModelProfileRepository(session_factory=ctx.session_factory)
    plan_repository = PlanRepository(session_factory=ctx.session_factory)
    plan_run_repository = PlanRunRepository(session_factory=ctx.session_factory)
    execution_repository = ExecutionRepository(session_factory=ctx.session_factory)
    model_profile_service = ModelProfileService(
        repository=model_profile_repository,
        secret_cipher=ctx.secret_cipher,
    )
    return {
        "model_profile_service": model_profile_service,
        "plan_service": PlanService(
            model_profile_service=model_profile_service,
            planner_agent_factory=lambda profile: build_planner_agent_for_profile(profile, plan_repository),
            plan_repository=plan_repository,
        ),
        "run_service": RunService(
            model_profile_service=model_profile_service,
            plan_repository=plan_repository,
            plan_run_repository=plan_run_repository,
            execution_repository=execution_repository,
            plan_runner_factory=lambda profile, max_workers: build_plan_runner_for_profile(
                profile,
                database_url=ctx.database_url,
                session_factory=ctx.session_factory,
                max_workers=max_workers,
                plan_repository=plan_repository,
                plan_run_repository=plan_run_repository,
            ),
        ),
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `py -3 -m pytest tests/api/test_model_profiles_api.py tests/api/test_plans_api.py tests/api/test_runs_api.py -v`
Expected: all API tests `PASS`

- [ ] **Step 5: Commit**

```bash
git add src/console_api/app.py src/console_api/schemas.py src/console_api/routers/__init__.py src/console_api/routers/model_profiles.py src/console_api/routers/plans.py src/console_api/routers/runs.py tests/api/test_model_profiles_api.py tests/api/test_plans_api.py tests/api/test_runs_api.py
git commit -m "feat: add model profile api and profile-aware plan run endpoints"
```

### Task 6: Add Model Profiles Page and Browser CRUD Flow

**Files:**
- Modify: `console/src/App.tsx`
- Modify: `console/src/api/client.ts`
- Modify: `console/src/components/AppShell.tsx`
- Create: `console/src/components/ModelProfileForm.tsx`
- Create: `console/src/routes/ModelProfilesPage.tsx`
- Create: `console/src/test/ModelProfilesPage.test.tsx`
- Modify: `console/src/test/App.test.tsx`

- [ ] **Step 1: Write the failing tests**

```tsx
// console/src/test/ModelProfilesPage.test.tsx
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import ModelProfilesPage from "../routes/ModelProfilesPage";

const client = vi.hoisted(() => ({
  listModelProfiles: vi.fn().mockResolvedValue([]),
  createModelProfile: vi.fn().mockResolvedValue({
    model_profile_id: "profile-1",
    name: "OpenAI Main",
    provider: "openai",
    model_name: "gpt-5-mini",
    base_url: null,
    thinking_mode: "default",
    api_key: "sk-openai-1234",
    api_key_hint: "****1234",
  }),
}));

vi.mock("../api/client", () => client);

test("creates a model profile and keeps api key hidden by default", async () => {
  render(
    <MemoryRouter initialEntries={["/model-profiles"]}>
      <Routes>
        <Route path="/model-profiles" element={<ModelProfilesPage />} />
      </Routes>
    </MemoryRouter>,
  );

  fireEvent.change(screen.getByLabelText(/name/i), { target: { value: "OpenAI Main" } });
  fireEvent.change(screen.getByLabelText(/provider/i), { target: { value: "openai" } });
  fireEvent.change(screen.getByLabelText(/model name/i), { target: { value: "gpt-5-mini" } });
  fireEvent.change(screen.getByLabelText(/api key/i), { target: { value: "sk-openai-1234" } });
  fireEvent.click(screen.getByRole("button", { name: /save profile/i }));

  await waitFor(() => expect(client.createModelProfile).toHaveBeenCalled());
  expect(screen.getByLabelText(/api key/i)).toHaveAttribute("type", "password");
});
```

```tsx
// console/src/test/App.test.tsx
vi.mock("../api/client", () => ({
  listPlans: vi.fn().mockResolvedValue([]),
  listRuns: vi.fn().mockResolvedValue([]),
  listModelProfiles: vi.fn().mockResolvedValue([]),
  getPlan: vi.fn().mockResolvedValue({ plan_id: "plan-1", source_goal: "Learn scheduling", tasks: [] }),
}));

test("app navigation shows model profiles tab", async () => {
  render(
    <MemoryRouter initialEntries={["/"]}>
      <App />
    </MemoryRouter>,
  )

  expect(screen.getByRole("link", { name: /model profiles/i })).toBeTruthy()
})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cmd /c npm --prefix console test -- --run ModelProfilesPage App`
Expected: `FAIL` because the route, form component, and API client methods do not exist

- [ ] **Step 3: Write the minimal implementation**

```tsx
// console/src/api/client.ts
export function listModelProfiles() {
  return readJson("/model-profiles");
}

export function getModelProfile(profileId: string) {
  return readJson(`/model-profiles/${profileId}`);
}

export function createModelProfile(payload: {
  name: string;
  provider: string;
  model_name: string;
  base_url?: string | null;
  thinking_mode: string;
  api_key: string;
}) {
  return readJson("/model-profiles", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export function updateModelProfile(profileId: string, payload: Record<string, unknown>) {
  return readJson(`/model-profiles/${profileId}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export function deleteModelProfile(profileId: string) {
  return fetch(`${API_BASE}/model-profiles/${profileId}`, { method: "DELETE" });
}

export function duplicateModelProfile(profileId: string) {
  return readJson(`/model-profiles/${profileId}/duplicate`, { method: "POST" });
}
```

```tsx
// console/src/components/ModelProfileForm.tsx
import { useState } from "react";

export default function ModelProfileForm({ initialValue, onSubmit }: { initialValue?: any; onSubmit: (payload: any) => Promise<void> }) {
  const [showSecret, setShowSecret] = useState(false);
  const [form, setForm] = useState(
    initialValue ?? {
      name: "",
      provider: "openai",
      model_name: "",
      base_url: "",
      thinking_mode: "default",
      api_key: "",
    },
  );

  return (
    <form
      onSubmit={(event) => {
        event.preventDefault();
        void onSubmit(form);
      }}
    >
      <label>
        Name
        <input value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} />
      </label>
      <label>
        Provider
        <select value={form.provider} onChange={(event) => setForm({ ...form, provider: event.target.value })}>
          <option value="openai">openai</option>
          <option value="openrouter">openrouter</option>
          <option value="qwen">qwen</option>
          <option value="glm">glm</option>
        </select>
      </label>
      <label>
        Model Name
        <input value={form.model_name} onChange={(event) => setForm({ ...form, model_name: event.target.value })} />
      </label>
      <label>
        API Key
        <input
          type={showSecret ? "text" : "password"}
          value={form.api_key}
          onChange={(event) => setForm({ ...form, api_key: event.target.value })}
        />
      </label>
      <button type="button" onClick={() => setShowSecret((current) => !current)}>
        {showSecret ? "Hide" : "Show"}
      </button>
      <button type="submit">Save profile</button>
    </form>
  );
}
```

```tsx
// console/src/routes/ModelProfilesPage.tsx
import { useEffect, useState } from "react";

import ModelProfileForm from "../components/ModelProfileForm";
import {
  createModelProfile,
  deleteModelProfile,
  duplicateModelProfile,
  getModelProfile,
  listModelProfiles,
  updateModelProfile,
} from "../api/client";

export default function ModelProfilesPage() {
  const [profiles, setProfiles] = useState<any[]>([]);
  const [editing, setEditing] = useState<any | null>(null);

  async function refresh() {
    setProfiles(await listModelProfiles());
  }

  useEffect(() => {
    void refresh();
  }, []);

  return (
    <section>
      <h1>Model Profiles</h1>
      <ModelProfileForm
        initialValue={editing ?? undefined}
        onSubmit={async (payload) => {
          if (editing?.model_profile_id) {
            await updateModelProfile(editing.model_profile_id, payload);
          } else {
            await createModelProfile(payload);
          }
          setEditing(null);
          await refresh();
        }}
      />
      <ul>
        {profiles.map((profile) => (
          <li key={profile.model_profile_id}>
            {profile.name} - {profile.provider} - {profile.model_name} - {profile.api_key_hint}
            <button onClick={async () => setEditing(await getModelProfile(profile.model_profile_id))}>Edit</button>
            <button onClick={async () => { await duplicateModelProfile(profile.model_profile_id); await refresh(); }}>Duplicate</button>
            <button onClick={async () => { await deleteModelProfile(profile.model_profile_id); await refresh(); }}>Delete</button>
          </li>
        ))}
      </ul>
    </section>
  );
}
```

```tsx
// console/src/App.tsx
<nav aria-label="Primary">
  <NavLink to="/">Dashboard</NavLink>
  <NavLink to="/model-profiles">Model Profiles</NavLink>
  <NavLink to="/plans">Plans</NavLink>
  <NavLink to="/runs">Runs</NavLink>
</nav>
<Routes>
  <Route path="/" element={<DashboardPage />} />
  <Route path="/model-profiles" element={<ModelProfilesPage />} />
  <Route path="/plans" element={<PlansPage />} />
  <Route path="/plans/:planId" element={<PlanDetailPage />} />
  <Route path="/runs" element={<RunsPage />} />
  <Route path="/runs/:runId" element={<RunDetailPage />} />
</Routes>
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cmd /c npm --prefix console test -- --run ModelProfilesPage App`
Expected: targeted Vitest cases `PASS`

- [ ] **Step 5: Commit**

```bash
git add console/src/App.tsx console/src/api/client.ts console/src/components/AppShell.tsx console/src/components/ModelProfileForm.tsx console/src/routes/ModelProfilesPage.tsx console/src/test/App.test.tsx console/src/test/ModelProfilesPage.test.tsx
git commit -m "feat: add model profiles page and browser crud flow"
```

### Task 7: Require Profile Selection in Plan and Run UI Flows

**Files:**
- Modify: `console/src/api/client.ts`
- Modify: `console/src/routes/DashboardPage.tsx`
- Modify: `console/src/routes/PlansPage.tsx`
- Modify: `console/src/routes/PlanDetailPage.tsx`
- Modify: `console/src/routes/RunsPage.tsx`
- Modify: `console/src/routes/RunDetailPage.tsx`
- Create: `console/src/test/PlansPage.test.tsx`
- Modify: `console/src/test/RunDetailPage.test.tsx`

- [ ] **Step 1: Write the failing tests**

```tsx
// console/src/test/RunDetailPage.test.tsx
const { retryRun, getRunDetail, listModelProfiles } = vi.hoisted(() => ({
  retryRun: vi.fn().mockResolvedValue({ run_id: "run-2" }),
  getRunDetail: vi.fn().mockResolvedValue({
    run_id: "run-1",
    plan_id: "plan-1",
    status: "failed",
    model_profile_id: "profile-1",
    model_profile_name: "OpenAI Main",
    provider: "openai",
    model_name: "gpt-5-mini",
    tasks: [{ task_id: "task-1", status: "failed", agent_name: "ReviewAgent", execution_task_id: "exec-1" }],
    executions: [{ task_id: "exec-1", error: "review failed", output: "" }],
  }),
  listModelProfiles: vi.fn().mockResolvedValue([
    { model_profile_id: "profile-1", name: "OpenAI Main" },
    { model_profile_id: "profile-2", name: "Qwen Backup" },
  ]),
}));

vi.mock("../api/client", () => ({
  getRunDetail,
  retryRun,
  listModelProfiles,
  requestRunControl: vi.fn(),
}));

test("retry run defaults to original profile and can switch before retry", async () => {
  render(
    <MemoryRouter initialEntries={["/runs/run-1"]}>
      <Routes>
        <Route path="/runs/:runId" element={<RunDetailPage />} />
      </Routes>
    </MemoryRouter>,
  );

  await waitFor(() => expect(screen.getByText(/openai main/i)).toBeTruthy());
  fireEvent.change(screen.getByLabelText(/retry profile/i), { target: { value: "profile-2" } });
  fireEvent.click(screen.getByRole("button", { name: /retry run/i }));

  await waitFor(() => expect(retryRun).toHaveBeenCalledWith("run-1", { profile_id: "profile-2" }));
});
```

```tsx
// console/src/test/PlansPage.test.tsx
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import PlansPage from "../routes/PlansPage";

const plansClient = vi.hoisted(() => ({
  listPlans: vi.fn().mockResolvedValue([]),
  listModelProfiles: vi.fn().mockResolvedValue([
    { model_profile_id: "profile-1", name: "OpenAI Main" },
  ]),
  createPlan: vi.fn().mockResolvedValue({
    plan_id: "plan-1",
    source_goal: "learn runtime profiles",
    model_profile_id: "profile-1",
    tasks: [],
  }),
}));

vi.mock("../api/client", () => plansClient);

test("plans page submits selected profile when creating a plan", async () => {
  render(
    <MemoryRouter>
      <PlansPage />
    </MemoryRouter>,
  );

  await waitFor(() => expect(plansClient.listModelProfiles).toHaveBeenCalled());
  fireEvent.change(screen.getByLabelText(/goal/i), { target: { value: "learn runtime profiles" } });
  fireEvent.change(screen.getByLabelText(/model profile/i), { target: { value: "profile-1" } });
  fireEvent.click(screen.getByRole("button", { name: /create plan/i }));

  await waitFor(() => {
    expect(plansClient.createPlan).toHaveBeenCalledWith({
      task: "learn runtime profiles",
      profile_id: "profile-1",
    });
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cmd /c npm --prefix console test -- --run RunDetailPage`
Expected: `FAIL` because plan/run profile selection controls are missing

- [ ] **Step 3: Write the minimal implementation**

```tsx
// console/src/api/client.ts
export function createPlan(payload: { task: string; profile_id: string }) {
  return readJson("/plans", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export function startRun(payload: { plan_id: string; profile_id: string; max_workers: number }) {
  return readJson("/runs", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export function retryRun(runId: string, payload?: { profile_id?: string }) {
  return readJson(`/runs/${runId}/retry`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload ?? {}),
  });
}
```

```tsx
// console/src/routes/PlansPage.tsx
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { createPlan, listModelProfiles, listPlans } from "../api/client";

export default function PlansPage() {
  const [plans, setPlans] = useState<any[]>([]);
  const [profiles, setProfiles] = useState<any[]>([]);
  const [task, setTask] = useState("");
  const [profileId, setProfileId] = useState("");

  useEffect(() => {
    void Promise.all([listPlans(), listModelProfiles()]).then(([nextPlans, nextProfiles]) => {
      setPlans(nextPlans);
      setProfiles(nextProfiles);
      setProfileId(nextProfiles[0]?.model_profile_id ?? "");
    });
  }, []);

  const hasProfiles = profiles.length > 0;

  return (
    <section>
      <h1>Plans</h1>
      {!hasProfiles ? <p>No model profile configured. Create one first.</p> : null}
      <form
        onSubmit={(event) => {
          event.preventDefault();
          if (!profileId) return;
          void createPlan({ task, profile_id: profileId });
        }}
      >
        <label>
          Goal
          <textarea value={task} onChange={(event) => setTask(event.target.value)} />
        </label>
        <label>
          Model Profile
          <select value={profileId} onChange={(event) => setProfileId(event.target.value)} disabled={!hasProfiles}>
            {profiles.map((profile) => (
              <option key={profile.model_profile_id} value={profile.model_profile_id}>
                {profile.name}
              </option>
            ))}
          </select>
        </label>
        <button type="submit" disabled={!hasProfiles}>Create plan</button>
      </form>
      <ul>
        {plans.map((plan) => (
          <li key={plan.plan_id}>
            <Link to={`/plans/${plan.plan_id}`}>{plan.source_goal}</Link>
          </li>
        ))}
      </ul>
    </section>
  );
}
```

```tsx
// console/src/routes/PlanDetailPage.tsx
import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";

import { getPlan, listModelProfiles, startRun } from "../api/client";

export default function PlanDetailPage() {
  const { planId = "" } = useParams();
  const [plan, setPlan] = useState<any | null>(null);
  const [profiles, setProfiles] = useState<any[]>([]);
  const [profileId, setProfileId] = useState("");
  const [maxWorkers, setMaxWorkers] = useState(1);

  useEffect(() => {
    void Promise.all([getPlan(planId), listModelProfiles()]).then(([nextPlan, nextProfiles]) => {
      setPlan(nextPlan);
      setProfiles(nextProfiles);
      setProfileId(nextPlan.model_profile_id ?? nextProfiles[0]?.model_profile_id ?? "");
    });
  }, [planId]);

  if (!plan) {
    return <p>Loading plan</p>;
  }

  return (
    <section>
      <h1>{plan.source_goal}</h1>
      <p>{plan.model_profile_name} - {plan.provider} - {plan.model_name}</p>
      <label>
        Run Profile
        <select value={profileId} onChange={(event) => setProfileId(event.target.value)}>
          {profiles.map((profile) => (
            <option key={profile.model_profile_id} value={profile.model_profile_id}>
              {profile.name}
            </option>
          ))}
        </select>
      </label>
      <label>
        Max Workers
        <input
          type="number"
          min={1}
          value={maxWorkers}
          onChange={(event) => setMaxWorkers(Number(event.target.value))}
        />
      </label>
      <button onClick={() => void startRun({ plan_id: plan.plan_id, profile_id: profileId, max_workers: maxWorkers })}>
        Start run
      </button>
      <ul>
        {plan.tasks.map((task: any) => (
          <li key={task.task_id}>{task.title}</li>
        ))}
      </ul>
    </section>
  );
}
```

```tsx
// console/src/routes/RunsPage.tsx
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { listRuns } from "../api/client";

export default function RunsPage() {
  const [runs, setRuns] = useState<any[]>([]);

  useEffect(() => {
    void listRuns().then(setRuns);
  }, []);

  return (
    <section>
      <h1>Runs</h1>
      <ul>
        {runs.map((run) => (
          <li key={run.run_id}>
            <Link to={`/runs/${run.run_id}`}>
              {run.run_id} - {run.model_profile_name} - {run.provider} - {run.model_name}
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
}
```

```tsx
// console/src/routes/RunDetailPage.tsx
import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";

import { getRunDetail, listModelProfiles, retryRun } from "../api/client";

export default function RunDetailPage() {
  const { runId = "" } = useParams();
  const [detail, setDetail] = useState<any | null>(null);
  const [profiles, setProfiles] = useState<any[]>([]);
  const [retryProfileId, setRetryProfileId] = useState("");

  useEffect(() => {
    void Promise.all([getRunDetail(runId), listModelProfiles()]).then(([nextDetail, nextProfiles]) => {
      setDetail(nextDetail);
      setProfiles(nextProfiles);
      setRetryProfileId(nextDetail.model_profile_id ?? nextProfiles[0]?.model_profile_id ?? "");
    });
  }, [runId]);

  if (!detail) {
    return <p>Loading run detail</p>;
  }

  return (
    <section>
      <h1>Run {detail.run_id}</h1>
      <p>{detail.model_profile_name} - {detail.provider} - {detail.model_name}</p>
      <label>
        Retry Profile
        <select value={retryProfileId} onChange={(event) => setRetryProfileId(event.target.value)}>
          {profiles.map((profile) => (
            <option key={profile.model_profile_id} value={profile.model_profile_id}>
              {profile.name}
            </option>
          ))}
        </select>
      </label>
      <button onClick={() => void retryRun(runId, { profile_id: retryProfileId })}>Retry run</button>
      <button disabled>Pause</button>
      <button disabled>Cancel</button>
      <ul>
        {detail.tasks.map((task: any) => (
          <li key={task.task_id}>
            {task.task_id} - {task.status}
          </li>
        ))}
      </ul>
      <ul>
        {detail.executions.map((execution: any) => (
          <li key={execution.task_id}>{execution.error || execution.output}</li>
        ))}
      </ul>
    </section>
  );
}
```

```tsx
// console/src/routes/DashboardPage.tsx
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { listModelProfiles, listPlans, listRuns } from "../api/client";

export default function DashboardPage() {
  const [profiles, setProfiles] = useState<any[]>([]);
  const [plans, setPlans] = useState<any[]>([]);
  const [runs, setRuns] = useState<any[]>([]);

  useEffect(() => {
    let alive = true;

    async function load() {
      const [nextProfiles, nextPlans, nextRuns] = await Promise.all([
        listModelProfiles(),
        listPlans(),
        listRuns(),
      ]);
      if (alive) {
        setProfiles(nextProfiles);
        setPlans(nextPlans);
        setRuns(nextRuns);
      }
    }

    void load();
    const timer = window.setInterval(load, 5000);
    return () => {
      alive = false;
      window.clearInterval(timer);
    };
  }, []);

  return (
    <section>
      <h1>Dashboard</h1>
      {profiles.length === 0 ? (
        <p>
          No model profile configured. <Link to="/model-profiles">Create one now</Link>.
        </p>
      ) : null}
      <ul>{plans.map((plan) => <li key={plan.plan_id}>{plan.source_goal}</li>)}</ul>
      <ul>{runs.map((run) => <li key={run.run_id}>{run.run_id}</li>)}</ul>
    </section>
  );
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cmd /c npm --prefix console test -- --run RunDetailPage`
Expected: targeted retry/profile-selection test `PASS`

- [ ] **Step 5: Commit**

```bash
git add console/src/api/client.ts console/src/routes/DashboardPage.tsx console/src/routes/PlansPage.tsx console/src/routes/PlanDetailPage.tsx console/src/routes/RunsPage.tsx console/src/routes/RunDetailPage.tsx console/src/test/RunDetailPage.test.tsx
git commit -m "feat: require model profile selection in plan and run flows"
```

### Task 8: Update Documentation and Run End-to-End Verification

**Files:**
- Modify: `README.md`
- Modify: `.env.example`
- Modify: `tests/integration/test_console_api_flow.py`

- [ ] **Step 1: Write the failing integration and doc assertions**

```python
# tests/integration/test_console_api_flow.py
from fastapi.testclient import TestClient

from console_api.app import create_app


def test_console_boots_without_provider_api_envs(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)
    monkeypatch.delenv("ZAI_API_KEY", raising=False)
    monkeypatch.setenv("DATABASE_URL", "postgresql://example/app")
    monkeypatch.setenv("APP_SECRET_KEY", "console-master-key")
    monkeypatch.setattr("console_api.app.build_app_context", lambda **_: type("Ctx", (), {"database_url": "postgresql://example/app", "session_factory": lambda: None, "secret_cipher": object()})())
    monkeypatch.setattr(
        "console_api.app._build_services",
        lambda ctx: {
            "model_profile_service": type("ModelProfileService", (), {"list_profiles": lambda self: []})(),
            "plan_service": object(),
            "run_service": object(),
        },
    )

    with TestClient(create_app()) as client:
        response = client.get("/api/model-profiles")

    assert response.status_code == 200
```

```text
# README.md assertions to satisfy in this task
- setup section shows APP_SECRET_KEY as required
- operations console startup no longer lists OPENAI_API_KEY as boot requirement
- model profiles page is documented as the place to configure provider/model/api key
```

- [ ] **Step 2: Run verification to observe current mismatch**

Run: `py -3 -m pytest tests/integration/test_console_api_flow.py -v`
Expected: `FAIL` or `ERROR` because `create_app` still wires startup-time provider config and the new router is not fully documented

- [ ] **Step 3: Write the minimal implementation**

```text
# .env.example
DATABASE_URL=postgresql+psycopg://user:password@localhost:5432/multi_agent_learning
APP_SECRET_KEY=replace_with_a_local_dev_secret

# Optional CLI-only provider defaults
OPENAI_API_KEY=
OPENAI_MODEL=gpt-5-nano
OPENROUTER_API_KEY=
OPENROUTER_MODEL=qwen/qwen3.6-plus:free
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
DASHSCOPE_API_KEY=
QWEN_MODEL=qwen-plus-latest
QWEN_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
ZAI_API_KEY=
GLM_MODEL=glm-5
GLM_BASE_URL=https://open.bigmodel.cn/api/paas/v4/
```

```text
# README.md
## Operations Console

Start the API:

set PYTHONPATH=src
set DATABASE_URL=postgresql+psycopg://user:password@localhost:5432/multi_agent_learning
set APP_SECRET_KEY=replace_with_a_local_dev_secret
py -3 -m uvicorn console_api.app:app --reload --port 8000

The API can now boot without `OPENAI_API_KEY`, `OPENROUTER_API_KEY`, `DASHSCOPE_API_KEY`, or `ZAI_API_KEY`.
Configure provider, model, base URL, thinking mode, and API key in the browser under `Model Profiles`.
```

- [ ] **Step 4: Run full verification**

Run: `py -3 -m pytest tests/security tests/application tests/storage tests/api tests/integration/test_console_api_flow.py -v`
Expected: all Python verification tests `PASS`

Run: `cmd /c npm --prefix console test -- --run`
Expected: all console Vitest cases `PASS`

Run: `C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe -Command "cmd /c npm --prefix console run build"`
Expected: Vite production build succeeds

- [ ] **Step 5: Commit**

```bash
git add README.md .env.example tests/integration/test_console_api_flow.py
git commit -m "docs: document runtime model profiles and boot requirements"
```

---

## Global Verification Commands

Run: `py -3 -m pytest tests/security tests/application tests/storage tests/api tests/integration/test_console_api_flow.py -v`
Expected: all Python test suites in this feature `PASS`

Run: `cmd /c npm --prefix console test -- --run`
Expected: all console unit tests `PASS`

Run: `C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe -Command "cmd /c npm --prefix console run build"`
Expected: production build `PASS`

Run: `py -3 -m compileall src`
Expected: compile succeeds without syntax errors

---

## Rollback Plan

- Revert by commit granularity from Task 8 back to Task 1 using `git revert <task-commit-sha>`.
- If schema changes were applied to a local database, recreate tables from `Base.metadata.create_all(...)` before rerunning console verification.
- If the frontend is in a broken intermediate state, revert the most recent UI task commit before touching backend code again.

---

## Notes for Implementers

- Keep CLI behavior env-compatible: this feature changes the web console boot path, not the existing `src/main.py --provider ...` contract.
- Do not read plaintext API keys from PostgreSQL anywhere except `ModelProfileService` and the edit/detail API flow.
- Keep list endpoints free of plaintext secrets. Only detail/edit responses may include `api_key`.
- Treat `APP_SECRET_KEY` mismatch as a business error with a clear message; do not mask it as a generic 500 if a more specific validation response is easy to return.
