import pytest

from models.plan_task import PlanTask
from storage.db.models import ModelProfileRow
from storage.repositories.plan_repository import PlanRepository


@pytest.mark.postgres
def test_save_and_load_plan_roundtrip(db_session):
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
        goal="build feature",
        model_profile_id=str(profile.model_profile_id),
        provider="openai",
        model_name="gpt-5-nano",
        thinking_mode="default",
        tasks=[
            PlanTask(
                id="task-1",
                title="Analyze",
                type="analysis",
                depends_on=[],
                status="pending",
                priority=1,
            ),
            PlanTask(
                id="task-2",
                title="Implement",
                type="implementation",
                depends_on=["task-1"],
                status="pending",
                priority=2,
            ),
        ],
    )

    loaded = repo.load_plan(plan_id)

    assert [item.id for item in loaded] == ["task-1", "task-2"]
    assert loaded[1].depends_on == ["task-1"]


@pytest.mark.postgres
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
        tasks=[
            PlanTask(
                id="task-1",
                title="Analyze",
                type="analysis",
                depends_on=[],
                status="pending",
                priority=1,
            )
        ],
    )

    summary = repo.get_plan_summary(plan_id)

    assert summary["model_profile_id"] == str(profile.model_profile_id)
