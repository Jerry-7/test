# PostgreSQL (db-only) 全量入库设计文档

**日期**: 2026-04-21  
**项目**: `multi-agent-learning`  
**范围**: 将现有 JSON 持久化（executions/plan/run 状态）迁移为 PostgreSQL，同步访问，db-only。

---

## 1. 目标与边界

### 1.1 目标
- 以 PostgreSQL 替代 `data/executions/executions.json` 与 `data/plans/plan.json`。
- 保持现有业务调用链（`main -> agents/scheduler -> storage`）稳定，优先最小侵入。
- 建立可扩展的存储边界，避免 SQL 散落在业务层。

### 1.2 非目标
- 本阶段不实现 `json/pg` 双模式切换。
- 本阶段不引入异步 ORM/异步驱动。
- 本阶段不做历史 JSON 自动迁移工具（可后续补）。

---

## 2. 架构方案（A：分层仓储化）

### 2.1 分层职责
- `main.py`
  - 负责运行时装配：数据库连接、仓储实例、agent/runner 注入。
- `storage/db/*`
  - 负责数据库基础设施：`engine`、`session`、表模型。
- `storage/repositories/*`
  - 负责持久化读写：
    - `ExecutionRepository`
    - `PlanRepository`
    - `PlanRunRepository`
- `agents/*`, `scheduler/*`
  - 不直接执行 SQL，仅依赖仓储接口。

### 2.2 兼容策略
- 保留 `ExecutionStore` 类名与上层调用方式。
- `ExecutionStore` 内部改为委托 `ExecutionRepository`，减少对现有代码改动范围。

---

## 3. 数据模型设计

### 3.1 executions
用途：记录每次 agent 任务执行快照（替代 executions.json）。

建议字段：
- `task_id` TEXT PK
- `task_text` TEXT NOT NULL
- `agent_name` TEXT NOT NULL
- `status` TEXT NOT NULL
- `output` TEXT NOT NULL DEFAULT ''
- `error` TEXT NOT NULL DEFAULT ''
- `traceback` TEXT NOT NULL DEFAULT ''
- `started_at` TIMESTAMPTZ NOT NULL
- `ended_at` TIMESTAMPTZ NOT NULL
- `metadata` JSONB NOT NULL DEFAULT '{}'::jsonb
- `created_at` TIMESTAMPTZ NOT NULL DEFAULT now()

索引建议：
- `idx_executions_started_at`
- `idx_executions_agent_name`

### 3.2 plans
用途：Planner 生成的一次计划头信息。

建议字段：
- `plan_id` UUID PK
- `source_goal` TEXT NOT NULL
- `provider` TEXT NOT NULL
- `model_name` TEXT NOT NULL
- `thinking_mode` TEXT NOT NULL
- `created_at` TIMESTAMPTZ NOT NULL DEFAULT now()

### 3.3 plan_tasks
用途：计划任务明细（替代 plan.json 列表）。

建议字段：
- `plan_id` UUID NOT NULL FK -> `plans.plan_id`
- `task_id` TEXT NOT NULL
- `title` TEXT NOT NULL
- `type` TEXT NOT NULL
- `priority` INTEGER NOT NULL
- `status` TEXT NOT NULL
- `depends_on` TEXT[] NOT NULL DEFAULT '{}'

约束：
- PK: (`plan_id`, `task_id`)

索引建议：
- `idx_plan_tasks_plan_id_priority`

### 3.4 plan_runs
用途：一次 `run-plan` 执行实例。

建议字段：
- `run_id` UUID PK
- `plan_id` UUID NOT NULL FK -> `plans.plan_id`
- `max_workers` INTEGER NOT NULL
- `status` TEXT NOT NULL
- `started_at` TIMESTAMPTZ NOT NULL
- `ended_at` TIMESTAMPTZ

索引建议：
- `idx_plan_runs_plan_id_started_at`

### 3.5 plan_run_tasks
用途：run 过程中每个任务的状态推进与快照。

建议字段：
- `run_id` UUID NOT NULL FK -> `plan_runs.run_id`
- `task_id` TEXT NOT NULL
- `agent_name` TEXT NOT NULL
- `status` TEXT NOT NULL
- `execution_task_id` TEXT FK -> `executions.task_id`
- `state_snapshot` JSONB NOT NULL DEFAULT '{}'::jsonb
- `updated_at` TIMESTAMPTZ NOT NULL DEFAULT now()

约束：
- PK: (`run_id`, `task_id`)

索引建议：
- `idx_plan_run_tasks_run_id_status`

---

## 4. 调用链与数据流调整

### 4.1 planner 分支
1. `PlannerAgent.run(goal)` 生成 `list[PlanTask]`。
2. `PlanRepository.save_plan(...)` 写入 `plans + plan_tasks`。
3. 返回 `plan_id`（并可保留任务摘要输出）。

### 4.2 run-plan 分支
1. CLI 输入 `--plan-id`。
2. `PlanRepository.load_plan(plan_id)` 读出计划任务。
3. `PlanRunRepository.create_run(plan_id, max_workers)` 建立 run。
4. `PlanRunner.run(..., run_id=...)` 在状态推进点写 `plan_run_tasks`。
5. 子任务执行后继续写 `executions`。
6. `PlanRunRepository.finish_run(run_id, status, ended_at)` 收尾。

### 4.3 basic 分支
- `BasicAgent.run(task_text)` 流程不变，仅持久化目标改为 `executions` 表。

---

## 5. CLI 约定变更（db-only）

### 5.1 新增参数
- `--database-url`：PostgreSQL 连接串（示例：`postgresql+psycopg://user:pwd@host:5432/dbname`）
- `--plan-id`：`run-plan` 模式必填

### 5.2 弱化/移除参数
- `--store-path`：不再作为主路径
- `--plan-path`：不再作为主路径

---

## 6. 实施阶段

1. 数据库基础设施（engine/session/models）
2. ExecutionRepository 替换 ExecutionStore 内部实现
3. PlanRepository 接管 planner 持久化
4. PlanRunRepository 接入 PlanRunner 状态推进
5. main/README/参数文档更新
6. 最小回归验证（basic/planner/run-plan 串行与并发）

---

## 7. 风险与缓解

- 风险：一次性 db-only 改造可能导致 CLI 使用方式断层。  
  缓解：在 README 中明确新参数与最小运行示例。

- 风险：并发写状态可能出现顺序观察差异。  
  缓解：以任务级最终状态为准，快照字段记录每步状态。

- 风险：没有迁移工具时，旧 JSON 历史数据不可直接查询。  
  缓解：后续单独补 `json -> pg` 导入脚本。

---

## 8. 验收标准

- `basic` 模式可以写入并查询 `executions`。
- `planner` 模式生成 `plan_id` 且 `plan_tasks` 正确。
- `run-plan` 模式可基于 `--plan-id` 执行并写入 `plan_runs/plan_run_tasks`。
- `--max-workers=1/2` 均可运行，任务最终状态一致（并发下允许中间顺序差异）。
- 不再依赖 JSON 文件作为主存储。
