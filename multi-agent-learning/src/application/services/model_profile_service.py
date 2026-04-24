from __future__ import annotations

from application.context import ResolvedModelProfile
from config.model_provider import get_supported_providers


class ModelProfileService:
    def __init__(self, *, repository, secret_cipher):
        self._repository = repository
        self._secret_cipher = secret_cipher

    def create_profile(
        self,
        *,
        name,
        provider,
        model_name,
        base_url,
        thinking_mode,
        api_key,
    ):
        self._validate(
            provider=provider,
            thinking_mode=thinking_mode,
            api_key=api_key,
            name=name,
            model_name=model_name,
        )
        profile_id = self._repository.create_profile(
            name=name.strip(),
            provider=provider.strip().lower(),
            model_name=model_name.strip(),
            base_url=(base_url or "").strip() or None,
            thinking_mode=thinking_mode,
            api_key_encrypted=self._secret_cipher.encrypt(api_key),
            api_key_hint=self._build_api_key_hint(api_key),
        )
        return self.get_profile(profile_id)

    def update_profile(
        self,
        profile_id: str,
        *,
        name,
        provider,
        model_name,
        base_url,
        thinking_mode,
        api_key,
    ):
        self._validate(
            provider=provider,
            thinking_mode=thinking_mode,
            api_key=api_key,
            name=name,
            model_name=model_name,
        )
        self._repository.update_profile(
            profile_id,
            name=name.strip(),
            provider=provider.strip().lower(),
            model_name=model_name.strip(),
            base_url=(base_url or "").strip() or None,
            thinking_mode=thinking_mode,
            api_key_encrypted=self._secret_cipher.encrypt(api_key),
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

    def delete_profile(self, profile_id: str) -> None:
        self._repository.delete_profile(profile_id)

    def duplicate_profile(self, profile_id: str) -> dict[str, object]:
        profile = self.get_profile(profile_id)
        return self.create_profile(
            name=self._build_copy_name(profile["name"]),
            provider=profile["provider"],
            model_name=profile["model_name"],
            base_url=profile["base_url"],
            thinking_mode=profile["thinking_mode"],
            api_key=profile["api_key"],
        )

    def _build_api_key_hint(self, api_key: str) -> str:
        cleaned = api_key.strip()
        return f"****{cleaned[-4:]}" if len(cleaned) >= 4 else "****"

    def _build_copy_name(self, name: str) -> str:
        return f"{name.strip()} Copy"

    def _validate(
        self,
        *,
        provider: str,
        thinking_mode: str,
        api_key: str,
        name: str,
        model_name: str,
    ) -> None:
        if provider.strip().lower() not in get_supported_providers():
            raise ValueError(f"Unsupported provider: {provider}")
        if thinking_mode not in {"default", "on", "off"}:
            raise ValueError(f"Unsupported thinking_mode: {thinking_mode}")
        if not name.strip() or not model_name.strip() or not api_key.strip():
            raise ValueError("name, model_name, and api_key are required.")
