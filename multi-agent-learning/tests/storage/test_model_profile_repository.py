import pytest

from storage.repositories.model_profile_repository import ModelProfileRepository


@pytest.mark.postgres
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
