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
set APP_SECRET_KEY=replace_with_a_local_dev_secret
```

6. 可选：也可以把配置写到 JSON（不想配环境变量时使用）

```bash
mkdir config
```

创建 `config/runtime.json`：

```json
{
  "database_url": "postgresql+psycopg://user:password@localhost:5432/multi_agent_learning"
}
```

7. 首次使用先初始化表结构（当前版本未接入自动迁移）：

```bash
set PYTHONPATH=src
py -3 -c "from pathlib import Path; from sqlalchemy import create_engine; from storage.db.models import Base; import json, os; url=os.getenv('DATABASE_URL','').strip(); cfg=Path('config/runtime.json'); url=url or (json.loads(cfg.read_text(encoding='utf-8')).get('database_url','').strip() if cfg.exists() else ''); engine=create_engine(url, future=True); Base.metadata.create_all(engine); engine.dispose(); print('tables created')"
```

## 常用命令

### 1) 生成计划（planner）

```bash
py -3 src/main.py --agent planner --provider openai --task "学习多 Agent 调度"
```

输出中会包含 `plan_id`。

### 2) 执行计划（run-plan）

```bash
py -3 src/main.py --agent run-plan --provider openai --plan-id <plan_id> --max-workers 2
```

### 3) 单任务执行（basic）

```bash
py -3 src/main.py --agent basic --provider openai --task "解释多 Agent 调度流程"
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

## Operations Console

Start the API:

```bash
set PYTHONPATH=src
set DATABASE_URL=postgresql+psycopg://user:password@localhost:5432/multi_agent_learning
set APP_SECRET_KEY=replace_with_a_local_dev_secret
py -3 -m uvicorn console_api.app:app --reload --port 8000
```

The operations console can now boot without `OPENAI_API_KEY`, `OPENROUTER_API_KEY`, `DASHSCOPE_API_KEY`, or `ZAI_API_KEY`.
Configure provider, model, base URL, thinking mode, and API key in the browser under `Model Profiles`.

Start the UI:

```bash
cmd /c npm --prefix console install
cmd /c npm --prefix console run dev
```

The console currently supports:

- create, edit, duplicate, and delete model profiles
- create plan
- start run
- inspect runs and task state
- retry a run as a new run
- view pause/cancel as unsupported control placeholders
