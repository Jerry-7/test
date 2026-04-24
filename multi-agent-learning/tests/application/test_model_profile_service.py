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
