from storage.db.models import Base


def test_schema_contains_required_tables():
    table_names = set(Base.metadata.tables.keys())
    assert "executions" in table_names
    assert "plans" in table_names
    assert "plan_tasks" in table_names
    assert "plan_runs" in table_names
    assert "plan_run_tasks" in table_names
