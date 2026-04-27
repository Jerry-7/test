from __future__ import annotations

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


def test_post_model_profiles_creates_profile():
    app = create_app()
    app.dependency_overrides[get_model_profile_service] = lambda: type(
        "ModelProfileService",
        (),
        {
            "create_profile": lambda self, **kwargs: {
                "model_profile_id": "profile-1",
                **kwargs,
                "api_key_hint": "****3456",
                "updated_at": "2026-04-23T00:00:00+00:00",
            }
        },
    )()
    client = TestClient(app)

    response = client.post(
        "/api/model-profiles",
        json={
            "name": "OpenAI Main",
            "provider": "openai",
            "model_name": "gpt-5-mini",
            "base_url": None,
            "thinking_mode": "default",
            "api_key": "sk-openai-3456",
        },
    )

    assert response.status_code == 201
    assert response.json()["model_profile_id"] == "profile-1"


def test_put_model_profiles_updates_profile():
    app = create_app()
    app.dependency_overrides[get_model_profile_service] = lambda: type(
        "ModelProfileService",
        (),
        {
            "update_profile": lambda self, profile_id, **kwargs: {
                "model_profile_id": profile_id,
                **kwargs,
                "api_key_hint": "****9999",
                "updated_at": "2026-04-23T01:00:00+00:00",
            }
        },
    )()
    client = TestClient(app)

    response = client.put(
        "/api/model-profiles/profile-1",
        json={
            "name": "OpenAI Main 2",
            "provider": "openai",
            "model_name": "gpt-5",
            "base_url": None,
            "thinking_mode": "default",
            "api_key": "sk-openai-9999",
        },
    )

    assert response.status_code == 200
    assert response.json()["model_profile_id"] == "profile-1"
    assert response.json()["model_name"] == "gpt-5"


def test_delete_model_profiles_returns_204():
    deleted: list[str] = []
    app = create_app()
    app.dependency_overrides[get_model_profile_service] = lambda: type(
        "ModelProfileService",
        (),
        {
            "delete_profile": lambda self, profile_id: deleted.append(profile_id),
        },
    )()
    client = TestClient(app)

    response = client.delete("/api/model-profiles/profile-1")

    assert response.status_code == 204
    assert deleted == ["profile-1"]


def test_post_model_profiles_duplicate_returns_new_profile():
    app = create_app()
    app.dependency_overrides[get_model_profile_service] = lambda: type(
        "ModelProfileService",
        (),
        {
            "duplicate_profile": lambda self, profile_id: {
                "model_profile_id": "profile-2",
                "name": "OpenAI Main Copy",
                "provider": "openai",
                "model_name": "gpt-5-mini",
                "base_url": None,
                "thinking_mode": "default",
                "api_key": "sk-openai-3456",
                "api_key_hint": "****3456",
                "updated_at": "2026-04-23T01:00:00+00:00",
            }
        },
    )()
    client = TestClient(app)

    response = client.post("/api/model-profiles/profile-1/duplicate")

    assert response.status_code == 201
    assert response.json()["model_profile_id"] == "profile-2"
