import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv
from agents.basic_agent import BasicAgent
from agents.planner_agent import PlannerAgent
from config import resolve_provider_config
from scheduler import DagScheduler, Dispatcher
from storage.execution_store import ExecutionStore


def load_env_file() -> None:
    """Load environment variables from project .env file if present."""
    project_root = Path(__file__).resolve().parents[1]
    env_path = project_root / ".env"
    load_dotenv(dotenv_path=env_path, override=False)


def build_parser() -> argparse.ArgumentParser:
    """构建命令行参数。

    这里先只保留阶段一真正需要的三个参数：
    - task: 用户输入的任务
    - model: 调用的 OpenAI 模型名
    - store-path: 执行日志落盘位置
    """
    parser = argparse.ArgumentParser(
        description="Run the phase-1 LangChain basic agent."
    )
    parser.add_argument("--task", required=True, help="The user task to execute.")
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
        "--mode",
        default="build",
        choices=("build", "plan"),
        help="Execution mode: build (run BasicAgent) or plan (run PlannerAgent).",
    )
    parser.add_argument(
        "--planner-backend",
        default="rule",
        choices=("rule", "llm"),
        help="Planner backend: rule or llm.",
    )
    parser.add_argument(
        "--base-url",
        default=None,
        help="Override the provider default OpenAI-compatible base URL.",
    )
    parser.add_argument(
        "--store-path",
        default="data/executions/executions.json",
        help="Path to the execution log JSON file.",
    )
    return parser


def main() -> int:
    """程序入口。

    当前入口做的事情非常少，目的是让你能清楚看到一条最小执行链路：
    1. 读取命令行参数
    2. 创建日志存储对象
    3. 创建 Agent
    4. 执行任务
    5. 打印结果
    """
    # Windows 终端默认编码经常不是 UTF-8。
    # 这里主动重设 stdout/stderr，避免中文输出出现乱码。
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")

    # 统一解析命令行参数，后续新增 Planner / Dispatcher 时仍然沿用这里。
    load_env_file()
    parser = build_parser()
    args = parser.parse_args()

    try:
        # ExecutionStore 负责把每次任务执行结果写入本地 JSON。
        store = ExecutionStore(args.store_path)

        if args.mode == "plan":
            planner_provider_config = None
            if args.planner_backend == "llm":
                planner_provider_config = resolve_provider_config(
                    provider=args.provider,
                    model_name=args.model,
                    base_url=args.base_url,
                )

            planner = PlannerAgent(
                store=store,
                backend=args.planner_backend,
                provider_config=planner_provider_config,
            )
            result = planner.run(args.task)
            plan = result.metadata.get("plan", [])
            assignments = Dispatcher().dispatch(plan)
            schedule_result = DagScheduler().run(plan, assignments)

            print("mode: plan")
            print(f"planner_backend: {args.planner_backend}")
            print(f"status: {result.status}")
            print(f"plan_tasks: {len(plan)}")
            if result.metadata.get("planner_debug", {}).get("fallback"):
                print(f"fallback_reason: {result.metadata['planner_debug']['reason']}")
            print("output:")
            for item in plan:
                print(
                    f"- {item['id']} | {item['type']} | depends_on={item['depends_on']} | {item['title']}"
                )
            print()
            print("dispatch:")
            for item in assignments:
                print(
                    f"- {item['task_id']} -> {item['agent_name']} | type={item['task_type']} | depends_on={item['depends_on']}"
                )
            print()
            print("schedule:")
            for item in schedule_result["tasks"]:
                print(
                    f"- {item['id']} | status={item['status']} | depends_on={item['depends_on']} | {item['title']}"
                )
            print()
            print("trace:")
            for item in schedule_result["trace"]:
                print(
                    f"- {item['task_id']} | event={item['event']} | agent={item['agent_name']}"
                )
            return 0

        # 先根据 provider 解析模型配置。
        # 这样 BasicAgent 不需要关心环境变量细节，只关心“拿到什么配置”。
        provider_config = resolve_provider_config(
            provider=args.provider,
            model_name=args.model,
            base_url=args.base_url,
        )

        # BasicAgent 是当前阶段的最小可运行 Agent。
        # 它内部已经接好了 LangChain + ChatOpenAI。
        agent = BasicAgent(store=store, provider_config=provider_config)

        # run(...) 是我们约定的统一执行入口。
        # 后续多 Agent 版本也会尽量保留这个调用习惯。
        result = agent.run(args.task)
    except Exception as exc:
        # 阶段一优先追求“易懂、好排查”，因此在入口统一兜底错误。
        print(f"error: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    # 下面这些输出既是给用户看的，也是给你学习执行生命周期看的。
    print(f"task_id: {result.task_id}")
    print(f"status: {result.status}")
    print(f"agent: {result.agent_name}")
    print(f"provider: {result.metadata.get('provider', '')}")
    print(f"model: {result.metadata.get('requested_model', '')}")
    print(f"started_at: {result.started_at}")
    print(f"ended_at: {result.ended_at}")
    print()
    print("output:")
    print(result.output)

    if result.error:
        # 理论上这里大多不会走到，因为前面的异常已在 Agent 内或入口处处理。
        # 保留它是为了让结果对象本身也具备明确的失败语义。
        print()
        print("error:")
        print(result.error, file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
