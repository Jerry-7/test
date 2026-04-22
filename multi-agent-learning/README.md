# Multi-Agent Learning

一个用于学习多 Agent 规划与调度的 Python 项目。  
当前版本采用 **PostgreSQL DB-only** 持久化契约。

## DB-Only 契约

- `planner`：生成计划并持久化到数据库，输出 `plan_id`
- `run-plan`：通过 `--plan-id` 执行计划
- `ExecutionStore` / `PlanRepository` / `PlanRunRepository` 都使用同一个数据库连接
- `--plan-path` / `--store-path` 仅保留迁移期兼容，不再作为主路径

## 环境准备

1. Python 3.10+
2. PostgreSQL（已创建可访问库）
3. 安装依赖：

```bash
py -3 -m pip install -r requirements.txt
```

4. 复制环境变量模板：

```bash
copy .env.example .env
```

5. 至少配置：

```bash
set DATABASE_URL=postgresql+psycopg://user:password@localhost:5432/multi_agent_learning
set OPENAI_API_KEY=your_openai_api_key
```

## 常用命令

### 1) 生成计划（planner）

```bash
py -3 src/main.py --agent planner --provider openai --database-url postgresql+psycopg://user:password@localhost:5432/multi_agent_learning --task "学习多 Agent 调度"
```

输出中会包含 `plan_id`。

### 2) 执行计划（run-plan）

```bash
py -3 src/main.py --agent run-plan --provider openai --database-url postgresql+psycopg://user:password@localhost:5432/multi_agent_learning --plan-id <plan_id> --max-workers 2
```

### 3) 单任务执行（basic）

```bash
py -3 src/main.py --agent basic --provider openai --database-url postgresql+psycopg://user:password@localhost:5432/multi_agent_learning --task "解释多 Agent 调度流程"
```

## Provider

支持：`openai` / `openrouter` / `qwen` / `glm`  
通过 `--provider` 切换，模型名与 `base_url` 可用参数覆盖。

## 目录概览

```text
src/
  main.py
  agents/
  scheduler/
  storage/
    db/
    repositories/
  models/
tests/
data/
```

## 测试

需要设置 `TEST_DATABASE_URL`（指向可写 PostgreSQL）：

```bash
set TEST_DATABASE_URL=postgresql+psycopg://postgres:123456@localhost:5432/postgres
py -3 -m pytest tests/storage/test_db_models.py tests/storage/test_execution_repository.py tests/storage/test_plan_repository.py tests/storage/test_plan_run_repository.py tests/scheduler/test_plan_runner_persistence.py tests/storage/test_cli_contract.py -q
```
