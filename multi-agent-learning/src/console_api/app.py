from __future__ import annotations

from fastapi import FastAPI

from agents.planner_agent import PlannerAgent
from application.context import build_service_context
from application.services import PlanService, RunService
from console_api.routers import plans, runs
from main import _build_dispatcher, _build_plan_runner, _build_worker_agents
from storage.execution_store import ExecutionStore
from storage.repositories.execution_repository import ExecutionRepository
from storage.repositories.plan_repository import PlanRepository
from storage.repositories.plan_run_repository import PlanRunRepository


def _build_services(ctx) -> dict[str, object]:
    plan_repository = PlanRepository(session_factory=ctx.session_factory)
    plan_run_repository = PlanRunRepository(session_factory=ctx.session_factory)
    execution_repository = ExecutionRepository(session_factory=ctx.session_factory)
    store = ExecutionStore(
        database_url=ctx.database_url,
        session_factory=ctx.session_factory,
    )
    plan_agent = PlannerAgent(
        provider_config=ctx.provider_config,
        thinking_mode=ctx.thinking_mode,
        plan_repository=plan_repository,
    )
    analysis_agent, implementation_agent, review_agent = _build_worker_agents(
        store=store,
        provider_config=ctx.provider_config,
        thinking_mode=ctx.thinking_mode,
    )
    dispatcher = _build_dispatcher(
        analysis_agent=analysis_agent,
        implementation_agent=implementation_agent,
        review_agent=review_agent,
    )
    plan_runner = _build_plan_runner(
        dispatcher=dispatcher,
        max_workers=1,
        plan_repository=plan_repository,
        plan_run_repository=plan_run_repository,
    )
    return {
        "plan_service": PlanService(
            plan_agent=plan_agent,
            plan_repository=plan_repository,
        ),
        "run_service": RunService(
            plan_repository=plan_repository,
            plan_run_repository=plan_run_repository,
            execution_repository=execution_repository,
            plan_runner=plan_runner,
        ),
    }


def create_app() -> FastAPI:
    app = FastAPI(title="Multi-Agent Learning Console API")
    app.state.plan_service = None
    app.state.run_service = None
    app.include_router(plans.router)
    app.include_router(runs.router)

    @app.on_event("startup")
    def _wire_dependencies() -> None:
        ctx = build_service_context(
            provider="openai",
            model=None,
            base_url=None,
            thinking="default",
            database_url=None,
            runtime_config="config/runtime.json",
        )
        services = _build_services(ctx)
        app.state.plan_service = services["plan_service"]
        app.state.run_service = services["run_service"]

    return app


app = create_app()
