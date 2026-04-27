from storage.db.models import Base, ModelProfileRow, PlanRow, PlanRunRow


def test_schema_contains_required_tables():
    table_names = set(Base.metadata.tables.keys())
    assert "executions" in table_names
    assert "plans" in table_names
    assert "plan_tasks" in table_names
    assert "plan_runs" in table_names
    assert "plan_run_tasks" in table_names


def test_schema_contains_model_profile_table_and_relationship_columns():
    table_names = set(Base.metadata.tables.keys())

    assert "model_profiles" in table_names
    assert "model_profile_id" in ModelProfileRow.__table__.primary_key.columns.keys()
    assert "model_profile_id" in PlanRow.__table__.columns.keys()
    assert "model_profile_id" in PlanRunRow.__table__.columns.keys()
