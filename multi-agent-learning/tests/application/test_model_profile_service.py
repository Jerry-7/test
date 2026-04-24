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


def test_service_update_duplicate_and_delete_profiles():
    calls: dict[str, object] = {}
    cipher = SecretCipher("dev-key")
    store = {
        "profile-1": {
            "model_profile_id": "profile-1",
            "name": "OpenAI Main",
            "provider": "openai",
            "model_name": "gpt-5-mini",
            "base_url": None,
            "thinking_mode": "default",
            "api_key_hint": "****3456",
            "api_key_encrypted": cipher.encrypt("sk-openai-3456"),
            "updated_at": "2026-04-23T00:00:00+00:00",
        }
    }

    service = ModelProfileService(
        repository=type(
            "Repo",
            (),
            {
                "get_profile": lambda self, profile_id: dict(store[profile_id]),
                "update_profile": lambda self, profile_id, **kwargs: calls.update(
                    {"updated": (profile_id, kwargs)}
                )
                or store[profile_id].update(
                    {
                        **kwargs,
                        "updated_at": "2026-04-23T01:00:00+00:00",
                    }
                ),
                "create_profile": lambda self, **kwargs: calls.update(
                    {"duplicated": kwargs}
                )
                or store.update(
                    {
                        "profile-2": {
                            "model_profile_id": "profile-2",
                            **kwargs,
                            "updated_at": "2026-04-23T01:30:00+00:00",
                        }
                    }
                )
                or "profile-2",
                "delete_profile": lambda self, profile_id: calls.update(
                    {"deleted": profile_id}
                )
                or store.pop(profile_id, None),
                "list_profiles": lambda self: [
                    {
                        key: value
                        for key, value in row.items()
                        if key != "api_key_encrypted"
                    }
                    for row in store.values()
                ],
                "get_profile_or_none": lambda self, profile_id: dict(store[profile_id])
                if profile_id in store
                else None,
            },
        )(),
        secret_cipher=cipher,
    )

    updated = service.update_profile(
        "profile-1",
        name="OpenAI Main 2",
        provider="openai",
        model_name="gpt-5",
        base_url=None,
        thinking_mode="default",
        api_key="sk-openai-9999",
    )
    duplicated = service.duplicate_profile("profile-1")
    service.delete_profile("profile-1")

    assert calls["updated"][0] == "profile-1"
    assert calls["updated"][1]["api_key_hint"] == "****9999"
    assert calls["deleted"] == "profile-1"
    assert calls["duplicated"]["name"] == "OpenAI Main 2 Copy"
    assert updated["api_key"] == "sk-openai-9999"
    assert duplicated["model_profile_id"] == "profile-2"
    assert duplicated["api_key"] == "sk-openai-9999"
    assert service.list_profiles()[0]["model_profile_id"] == "profile-2"
