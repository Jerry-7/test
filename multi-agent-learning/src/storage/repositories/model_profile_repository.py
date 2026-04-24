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
            rows = (
                session.query(ModelProfileRow)
                .order_by(ModelProfileRow.updated_at.desc())
                .all()
            )
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
            row = (
                session.query(ModelProfileRow)
                .filter(ModelProfileRow.model_profile_id == UUID(profile_id))
                .one()
            )
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
