import argparse
import sys
from dataclasses import dataclass

from application.context import build_service_context
from agents.basic_agent import BasicAgent
from agents.planner_agent import PlannerAgent
from agents.worker_agents import AnalysisAgent, ImplementationAgent, ReviewAgent
from config import (
    ModelProviderConfig,
    build_provider_config_from_runtime_profile,
)
from models.plan_constants import (
    TASK_TYPE_ANALYSIS,
    TASK_TYPE_DESIGN,
    TASK_TYPE_IMPLEMENTATION,
    TASK_TYPE_PLANNING,
    TASK_TYPE_REVIEW,
)
from models.planner_run_result import PlannerRunResult
from scheduler.batch_executor import SerialBatchExecutor, ThreadPoolBatchExecutor
from scheduler.dispatcher import Dispatcher
from scheduler.plan_task_renderer import PlanTaskRenderer
from scheduler.plan_runner import PlanRunner
from scheduler.plan_validator import PlanValidator
from scheduler.task_selection_policy import PriorityTaskSelectionPolicy
from models.task import TaskExecution
from storage.execution_store import ExecutionStore
from storage.repositories.plan_repository import PlanRepository
from storage.repositories.plan_run_repository import PlanRunRepository
from utils import (
    load_project_env,
    write_error,
    write_key_values,
    write_line,
    write_section,
)


@dataclass
class RuntimeContext:
    """应用运行时依赖对象。

    作用：
    - 汇总 main 流程会用到的核心组件
    - 根据 `--agent` 按需初始化对应字段
    """

    provider_config: ModelProviderConfig
    basic_agent: BasicAgent | None = None
    plan_agent: PlannerAgent | None = None
    dispatcher: Dispatcher | None = None
    plan_runner: PlanRunner | None = None


def build_parser() -> argparse.ArgumentParser:
    """构建命令行参数解析器。

    这里定义了三种运行模式：
    - basic: 直接执行单任务
    - planner: 生成并保存计划
    - run-plan: 读取计划并调度执行
    """
    parser = argparse.ArgumentParser(description="Run the LangChain learning agents.")
    parser.add_argument("--task", default=None, help="The user task to execute.")
    parser.add_argument(
        "--agent",
        default="basic",
        choices=["basic", "planner", "run-plan"],
        help="Which agent to run.",
    )
    parser.add_argument(
        "--provider",
        default="openai",
        help="Model provider: openai, openrouter, qwen, glm.",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Override the provider default model name.",
    )
    parser.add_argument(
        "--base-url",
        default=None,
        help="Override the provider default OpenAI-compatible base URL.",
    )
    parser.add_argument(
        "--thinking",
        default="default",
        choices=["default", "on", "off"],
        help="Thinking mode for compatible providers such as qwen.",
    )
    parser.add_argument(
        "--database-url",
        default=None,
        help=(
            "Optional database URL override. "
            "Default uses DATABASE_URL env or runtime JSON config."
        ),
    )
    parser.add_argument(
        "--runtime-config",
        default="config/runtime.json",
        help=(
            "Runtime JSON config path (optional). "
            "Supports key `database_url`."
        ),
    )
    parser.add_argument(
        "--plan-path",
        default="data/plans/plan.json",
        help="Deprecated legacy path option. Kept for backward compatibility.",
    )
    parser.add_argument(
        "--plan-id",
        default=None,
        help="Plan ID to execute in run-plan mode.",
    )
    parser.add_argument(
        "--store-path",
        default="data/executions/executions.json",
        help="Deprecated legacy option in db-only mode.",
    )
    parser.add_argument(
        "--max-workers",
        type=int,
        default=1,
        help="Max tasks selected per scheduling round in run-plan mode.",
    )
    return parser


def is_qwen_thinking_tool_choice_error(exc: Exception) -> bool:
    """判断异常是否属于 Qwen thinking 与工具调用冲突。"""
    message = str(exc).lower()
    return (
        "tool_choice" in message
        and "thinking mode" in message
        and "required" in message
    )


def print_qwen_thinking_hint(args: argparse.Namespace) -> None:
    """在特定错误场景下打印可执行的修复建议。"""
    if args.provider.strip().lower() == "qwen" and args.thinking == "default":
        write_error(
            "hint: Qwen thinking mode conflicts with LangChain structured output "
            "because structured output uses tool calling."
        )
        write_error(
            "hint: rerun with `--thinking off`, for example: "
            "py -3 src/main.py --agent planner --provider qwen --thinking off "
            '--task "解释多 Agent 调度"'
        )


def print_basic_execution_result(result: TaskExecution) -> int:
    """输出 basic 模式执行结果。

    返回：
    - 0: 成功
    - 1: 失败（存在 error）
    """
    write_key_values(
        [
            ("task_id", result.task_id),
            ("status", result.status),
            ("agent", result.agent_name),
            ("provider", result.metadata.get("provider", "")),
            ("model", result.metadata.get("requested_model", "")),
            ("thinking", result.metadata.get("thinking_mode", "")),
            ("started_at", result.started_at),
            ("ended_at", result.ended_at),
        ]
    )
    write_line()
    write_section("output:", [result.output])

    if result.error:
        write_line()
        write_section("error:", [result.error], file=sys.stderr)
        return 1

    return 0


def print_planner_result(
    result: PlannerRunResult,
    provider_config: ModelProviderConfig,
    dispatcher: Dispatcher,
    args: argparse.Namespace,
) -> None:
    """输出 planner 模式结果（计划摘要 + 分发目标）。"""
    write_key_values(
        [
            ("agent", "PlannerAgent"),
            ("provider", provider_config.provider),
            ("model", provider_config.model_name),
            ("thinking", args.thinking),
            ("plan_id", result.plan_id),
        ]
    )
    write_line()
    write_section(
        "plan:",
        [
            (
                f"- {item.id} | {item.type} | priority={item.priority} | {item.title} | "
                f"agent={dispatcher.dispatch(item).name} | "
                f"depends_on={item.depends_on}"
            )
            for item in result.tasks
        ],
    )


def print_plan_runner_result(result: list[TaskExecution], args: argparse.Namespace) -> None:
    """输出 run-plan 模式结果（执行列表与状态快照）。"""
    write_key_values(
        [
            ("agent", "PlanRunner"),
            ("plan_id", args.plan_id),
            ("max_workers", args.max_workers),
        ]
    )
    write_line()
    write_section(
        "executions:",
        [
            (
                f"- {execution.task_id} | {execution.agent_name} | "
                f"{execution.status} | {execution.metadata.get('plan_task_id', '')} | "
                f"{execution.metadata.get('plan_task_title', '')} | "
                f"state={execution.metadata.get('plan_task_state', '')} | "
                f"states={execution.metadata.get('plan_task_states', {})}"
            )
            for execution in result
        ],
    )


def _build_basic_agent(
    store: ExecutionStore,
    provider_config: ModelProviderConfig,
    thinking_mode: str,
) -> BasicAgent:
    """构建 basic 模式使用的单 Agent。"""
    return BasicAgent(
        store=store,
        provider_config=provider_config,
        thinking_mode=thinking_mode,
    )


def _build_planner_agent(
    provider_config: ModelProviderConfig,
    thinking_mode: str,
    plan_repository: PlanRepository,
    model_profile_id: str | None = None,
) -> PlannerAgent:
    """构建 planner 模式使用的规划 Agent。"""
    return PlannerAgent(
        provider_config=provider_config,
        thinking_mode=thinking_mode,
        plan_repository=plan_repository,
        model_profile_id=model_profile_id,
    )


def _build_worker_agents(
    store: ExecutionStore,
    provider_config: ModelProviderConfig,
    thinking_mode: str,
) -> tuple[AnalysisAgent, ImplementationAgent, ReviewAgent]:
    """构建 run-plan/planner 共用的三类 Worker。"""
    analysis_agent = AnalysisAgent(
        store=store,
        provider_config=provider_config,
        thinking_mode=thinking_mode,
    )
    implementation_agent = ImplementationAgent(
        store=store,
        provider_config=provider_config,
        thinking_mode=thinking_mode,
    )
    review_agent = ReviewAgent(
        store=store,
        provider_config=provider_config,
        thinking_mode=thinking_mode,
    )
    return analysis_agent, implementation_agent, review_agent


def _build_dispatcher(
    analysis_agent: AnalysisAgent,
    implementation_agent: ImplementationAgent,
    review_agent: ReviewAgent,
) -> Dispatcher:
    """构建并注册任务类型到 Agent 的分发器。"""
    dispatcher = Dispatcher()
    dispatcher.register(TASK_TYPE_ANALYSIS, analysis_agent)
    dispatcher.register(TASK_TYPE_PLANNING, analysis_agent)
    dispatcher.register(TASK_TYPE_DESIGN, analysis_agent)
    dispatcher.register(TASK_TYPE_IMPLEMENTATION, implementation_agent)
    dispatcher.register(TASK_TYPE_REVIEW, review_agent)
    return dispatcher


def _build_plan_runner(
    dispatcher: Dispatcher,
    max_workers: int,
    plan_repository: PlanRepository,
    plan_run_repository: PlanRunRepository,
) -> PlanRunner:
    """构建 run-plan 模式使用的计划执行器。"""
    task_renderer = PlanTaskRenderer()
    if max_workers > 1:
        batch_executor = ThreadPoolBatchExecutor(
            dispatcher=dispatcher,
            task_renderer=task_renderer,
        )
    else:
        batch_executor = SerialBatchExecutor(
            dispatcher=dispatcher,
            task_renderer=task_renderer,
        )

    return PlanRunner(
        dispatcher=dispatcher,
        plan_validator=PlanValidator(),
        plan_repository=plan_repository,
        plan_run_repository=plan_run_repository,
        task_renderer=task_renderer,
        task_selection_policy=PriorityTaskSelectionPolicy(),
        batch_executor=batch_executor,
        max_workers=max_workers,
    )


def build_planner_agent_for_profile(profile, plan_repository: PlanRepository) -> PlannerAgent:
    provider_config = build_provider_config_from_runtime_profile(profile)
    return _build_planner_agent(
        provider_config=provider_config,
        thinking_mode=profile.thinking_mode,
        plan_repository=plan_repository,
        model_profile_id=profile.profile_id,
    )


def build_plan_runner_for_profile(
    profile,
    *,
    database_url: str,
    session_factory,
    max_workers: int,
    plan_repository: PlanRepository,
    plan_run_repository: PlanRunRepository,
) -> PlanRunner:
    provider_config = build_provider_config_from_runtime_profile(profile)
    store = ExecutionStore(
        database_url=database_url,
        session_factory=session_factory,
    )
    analysis_agent, implementation_agent, review_agent = _build_worker_agents(
        store=store,
        provider_config=provider_config,
        thinking_mode=profile.thinking_mode,
    )
    dispatcher = _build_dispatcher(
        analysis_agent=analysis_agent,
        implementation_agent=implementation_agent,
        review_agent=review_agent,
    )
    return _build_plan_runner(
        dispatcher=dispatcher,
        max_workers=max_workers,
        plan_repository=plan_repository,
        plan_run_repository=plan_run_repository,
    )


def build_runtime(args: argparse.Namespace) -> RuntimeContext:
    """按 `args.agent` 构建运行时依赖。

    说明：
    - basic: 只初始化 BasicAgent
    - planner: 初始化 Worker + Dispatcher + PlannerAgent
    - run-plan: 初始化 Worker + Dispatcher + PlanRunner
    """
    service_context = build_service_context(
        provider=args.provider,
        model=args.model,
        base_url=args.base_url,
        thinking=args.thinking,
        database_url=args.database_url,
        runtime_config=getattr(args, "runtime_config", None),
    )
    provider_config = service_context.provider_config
    session_factory = service_context.session_factory
    database_url = service_context.database_url

    store = ExecutionStore(
        database_url=database_url,
        session_factory=session_factory,
    )
    basic_agent: BasicAgent | None = None
    plan_agent: PlannerAgent | None = None
    dispatcher: Dispatcher | None = None
    plan_runner: PlanRunner | None = None
    plan_repository: PlanRepository | None = None

    if args.agent == "basic":
        basic_agent = _build_basic_agent(
            store=store,
            provider_config=provider_config,
            thinking_mode=args.thinking,
        )
    else:
        plan_repository = PlanRepository(session_factory=session_factory)
        analysis_agent, implementation_agent, review_agent = _build_worker_agents(
            store=store,
            provider_config=provider_config,
            thinking_mode=args.thinking,
        )
        dispatcher = _build_dispatcher(
            analysis_agent=analysis_agent,
            implementation_agent=implementation_agent,
            review_agent=review_agent,
        )

        if args.agent == "planner":
            plan_agent = _build_planner_agent(
                provider_config=provider_config,
                thinking_mode=args.thinking,
                plan_repository=plan_repository,
            )
        else:
            plan_run_repository = PlanRunRepository(session_factory=session_factory)
            plan_runner = _build_plan_runner(
                dispatcher=dispatcher,
                max_workers=args.max_workers,
                plan_repository=plan_repository,
                plan_run_repository=plan_run_repository,
            )

    return RuntimeContext(
        provider_config=provider_config,
        basic_agent=basic_agent,
        plan_agent=plan_agent,
        dispatcher=dispatcher,
        plan_runner=plan_runner,
    )


def _run_basic(runtime: RuntimeContext, args: argparse.Namespace) -> TaskExecution:
    """执行 basic 分支。"""
    basic_agent = runtime.basic_agent
    if basic_agent is None:
        raise RuntimeError("BasicAgent is not initialized.")
    return basic_agent.run(args.task)


def _run_planner(
    runtime: RuntimeContext,
    args: argparse.Namespace,
) -> PlannerRunResult:
    """执行 planner 分支。"""
    plan_agent = runtime.plan_agent
    if plan_agent is None:
        raise RuntimeError("PlannerAgent is not initialized.")
    if getattr(args, "_plan_path_provided", False):
        return plan_agent.run(args.task, path=args.plan_path)
    return plan_agent.run(args.task)


def _run_plan(runtime: RuntimeContext, args: argparse.Namespace) -> list[TaskExecution]:
    """执行 run-plan 分支。"""
    plan_runner = runtime.plan_runner
    if plan_runner is None:
        raise RuntimeError("PlanRunner is not initialized.")
    plan_id = (args.plan_id or "").strip()
    if not plan_id:
        raise RuntimeError("run-plan requires --plan-id.")
    return plan_runner.run_from_plan_id(plan_id)


def _execute_by_agent(
    runtime: RuntimeContext,
    args: argparse.Namespace,
) -> TaskExecution | PlannerRunResult | list[TaskExecution]:
    """按 agent 路由到对应执行函数。"""
    if args.agent == "basic":
        return _run_basic(runtime, args)
    if args.agent == "planner":
        return _run_planner(runtime, args)
    return _run_plan(runtime, args)


def _print_by_agent(
    runtime: RuntimeContext,
    args: argparse.Namespace,
    result: TaskExecution | PlannerRunResult | list[TaskExecution],
) -> int:
    """按 agent 路由到对应输出函数。"""
    if args.agent == "basic":
        if not isinstance(result, TaskExecution):
            raise RuntimeError("Unexpected result type for basic mode.")
        return print_basic_execution_result(result)

    if args.agent == "planner":
        if not isinstance(result, PlannerRunResult):
            raise RuntimeError("Unexpected result type for planner mode.")
        dispatcher = runtime.dispatcher
        if dispatcher is None:
            raise RuntimeError("Dispatcher is not initialized.")
        print_planner_result(result, runtime.provider_config, dispatcher, args)
        return 0

    if not isinstance(result, list):
        raise RuntimeError("Unexpected result type for run-plan mode.")
    print_plan_runner_result(result, args)
    return 0


def main() -> int:
    """程序入口函数。

    流程：
    1) 加载环境变量和 CLI 参数
    2) 根据模式执行 basic / planner / run-plan
    3) 输出结果并返回退出码
    """
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")

    load_project_env()

    parser = build_parser()
    args = parser.parse_args()
    args._plan_path_provided = "--plan-path" in sys.argv
    args._store_path_provided = "--store-path" in sys.argv

    if args.agent in {"basic", "planner"} and not args.task:
        parser.error("--task is required when --agent is basic or planner.")
    if args.agent == "run-plan" and not (args.plan_id or "").strip():
        parser.error("--plan-id is required when --agent is run-plan.")
    if args._plan_path_provided:
        if args.agent == "planner":
            write_error(
                "warning: --plan-path is deprecated and kept only for migration."
            )
        else:
            write_error(
                "warning: --plan-path is deprecated in db-only mode and ignored here."
            )
    if args._store_path_provided:
        write_error(
            "warning: --store-path is deprecated in db-only mode and is ignored."
        )

    try:
        runtime = build_runtime(args)
        result = _execute_by_agent(runtime, args)
    except Exception as exc:
        write_error(f"error: {type(exc).__name__}: {exc}")
        if is_qwen_thinking_tool_choice_error(exc):
            print_qwen_thinking_hint(args)
        return 1

    return _print_by_agent(runtime, args, result)


if __name__ == "__main__":
    raise SystemExit(main())
