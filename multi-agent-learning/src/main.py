import argparse
import sys
from dataclasses import dataclass

from agents.basic_agent import BasicAgent
from agents.planner_agent import PlannerAgent
from config import ModelProviderConfig, resolve_provider_config
from models.plan_constants import (
    TASK_TYPE_ANALYSIS,
    TASK_TYPE_DESIGN,
    TASK_TYPE_IMPLEMENTATION,
    TASK_TYPE_PLANNING,
    TASK_TYPE_REVIEW,
)
from models.plan_task import PlanTask
from scheduler.dispatcher import Dispatcher
from scheduler.plan_runner import PlanRunner
from scheduler.plan_validator import PlanValidator
from models.task import TaskExecution
from storage.execution_store import ExecutionStore
from utils import (
    load_project_env,
    write_error,
    write_key_values,
    write_line,
    write_section,
)


@dataclass
class RuntimeContext:
    """应用运行时依赖对象。"""

    provider_config: ModelProviderConfig
    basic_agent: BasicAgent
    plan_agent: PlannerAgent
    dispatcher: Dispatcher
    plan_runner: PlanRunner


def build_parser() -> argparse.ArgumentParser:
    """构建命令行参数。"""
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
        "--store-path",
        default="data/executions/executions.json",
        help="Path to the execution log JSON file.",
    )
    parser.add_argument(
        "--plan-path",
        default="data/plans/plan.json",
        help="Path to save the generated plan JSON file.",
    )
    return parser


def is_qwen_thinking_tool_choice_error(exc: Exception) -> bool:
    """判断是否是 Qwen thinking 模式与强制工具调用冲突。"""
    message = str(exc).lower()
    return (
        "tool_choice" in message
        and "thinking mode" in message
        and "required" in message
    )


def print_qwen_thinking_hint(args: argparse.Namespace) -> None:
    """打印 Qwen thinking 模式冲突的修复建议。"""
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
    """打印 BasicAgent 执行结果。"""
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
    result: list[PlanTask],
    provider_config: ModelProviderConfig,
    dispatcher: Dispatcher,
    args: argparse.Namespace,
) -> None:
    """打印 PlannerAgent 结果。"""
    write_key_values(
        [
            ("agent", "PlannerAgent"),
            ("provider", provider_config.provider),
            ("model", provider_config.model_name),
            ("thinking", args.thinking),
            ("plan_path", args.plan_path),
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
            for item in result
        ],
    )


def print_plan_runner_result(result: list[TaskExecution], args: argparse.Namespace) -> None:
    """打印 PlanRunner 结果。"""
    write_key_values(
        [
            ("agent", "PlanRunner"),
            ("plan_path", args.plan_path),
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


def build_runtime(args: argparse.Namespace) -> RuntimeContext:
    """构建运行时依赖对象。"""
    provider_config = resolve_provider_config(
        provider=args.provider,
        model_name=args.model,
        base_url=args.base_url,
    )
    
    store = ExecutionStore(args.store_path)
    basic_agent = BasicAgent(
        store=store,
        provider_config=provider_config,
        thinking_mode=args.thinking,
    )
    plan_agent = PlannerAgent(
        provider_config=provider_config,
        thinking_mode=args.thinking,
    )

    dispatcher = Dispatcher()
    dispatcher.register(TASK_TYPE_ANALYSIS, basic_agent)
    dispatcher.register(TASK_TYPE_PLANNING, basic_agent)
    dispatcher.register(TASK_TYPE_DESIGN, basic_agent)
    dispatcher.register(TASK_TYPE_IMPLEMENTATION, basic_agent)
    dispatcher.register(TASK_TYPE_REVIEW, basic_agent)

    plan_validator = PlanValidator()

    plan_runner = PlanRunner(dispatcher, plan_validator)

    return RuntimeContext(
        provider_config=provider_config,
        basic_agent=basic_agent,
        plan_agent=plan_agent,
        dispatcher=dispatcher,
        plan_runner=plan_runner,
    )


def main() -> int:
    """程序入口。"""
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")

    load_project_env()

    parser = build_parser()
    args = parser.parse_args()

    if args.agent in {"basic", "planner"} and not args.task:
        parser.error("--task is required when --agent is basic or planner.")

    try:
        runtime = build_runtime(args)
        provider_config = runtime.provider_config
        basic_agent = runtime.basic_agent
        plan_agent = runtime.plan_agent
        dispatcher = runtime.dispatcher
        plan_runner = runtime.plan_runner

        if args.agent == "basic":
            result = basic_agent.run(args.task)
        elif args.agent == "planner":
            result = plan_agent.run(args.task, path=args.plan_path)
        else:
            result = plan_runner.run_from_path(args.plan_path)
    except Exception as exc:
        write_error(f"error: {type(exc).__name__}: {exc}")
        if is_qwen_thinking_tool_choice_error(exc):
            print_qwen_thinking_hint(args)
        return 1

    if args.agent == "basic":
        return print_basic_execution_result(result)

    if args.agent == "planner":
        print_planner_result(result, provider_config, dispatcher, args)
    else:
        print_plan_runner_result(result, args)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
