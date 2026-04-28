from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from application.context import build_app_context
from application.services import ModelProfileService, PlanService, RunService
from console_api.routers import model_profiles, plans, runs
from main import build_plan_runner_for_profile, build_planner_agent_for_profile
from storage.repositories import (
    ExecutionRepository,
    ModelProfileRepository,
    PlanRepository,
    PlanRunRepository,
)


def _build_services(ctx) -> dict[str, object]:
    model_profile_repository = ModelProfileRepository(session_factory=ctx.session_factory)
    plan_repository = PlanRepository(session_factory=ctx.session_factory)
    plan_run_repository = PlanRunRepository(session_factory=ctx.session_factory)
    execution_repository = ExecutionRepository(session_factory=ctx.session_factory)
    model_profile_service = ModelProfileService(
        repository=model_profile_repository,
        secret_cipher=ctx.secret_cipher,
    )
    return {
        "model_profile_service": model_profile_service,
        "plan_service": PlanService(
            model_profile_service=model_profile_service,
            planner_agent_factory=lambda profile: build_planner_agent_for_profile(
                profile,
                plan_repository,
            ),
            plan_repository=plan_repository,
        ),
        "run_service": RunService(
            model_profile_service=model_profile_service,
            plan_repository=plan_repository,
            plan_run_repository=plan_run_repository,
            execution_repository=execution_repository,
            plan_runner_factory=lambda profile, max_workers: build_plan_runner_for_profile(
                profile,
                database_url=ctx.database_url,
                session_factory=ctx.session_factory,
                max_workers=max_workers,
                plan_repository=plan_repository,
                plan_run_repository=plan_run_repository,
            ),
        ),
    }


def create_app() -> FastAPI:
    app = FastAPI(title="Multi-Agent Learning Console API")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://127.0.0.1:5173",
            "http://localhost:5173",
        ],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.state.model_profile_service = None
    app.state.plan_service = None
    app.state.run_service = None
    app.include_router(model_profiles.router)
    app.include_router(plans.router)
    app.include_router(runs.router)

    @app.on_event("startup")
    def _wire_dependencies() -> None:
        ctx = build_app_context(
            database_url=None,
            runtime_config="config/runtime.json",
            app_secret_key=None,
        )
        services = _build_services(ctx)
        app.state.model_profile_service = services["model_profile_service"]
        app.state.plan_service = services["plan_service"]
        app.state.run_service = services["run_service"]

    return app


app = create_app()
