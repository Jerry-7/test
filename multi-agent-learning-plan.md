# 多 Agent 学习项目计划（已对齐当前代码，2026-04-22）

## 一、项目目标（当前版本）

围绕 `multi-agent-learning/` 持续迭代一个“可学习、可扩展、可追踪”的多 Agent 调度系统：

- 以 `PlannerAgent` 生成结构化计划
- 以 `Dispatcher` 负责任务分发
- 以 `PlanRunner` 负责依赖调度与执行推进
- 以 PostgreSQL 作为唯一持久化后端（DB-only）
- 逐步补齐初始化、迁移、并发、质量控制与可观测性

---

## 二、当前状态总览

### 已完成（Done）

1. **多 Agent 基础链路**
   - `basic` / `planner` / `run-plan` 三条运行路径已打通
   - `AnalysisAgent` / `ImplementationAgent` / `ReviewAgent` 已接入
   - `AgentTask(plan_task, rendered_task)` 已用于结构化任务输入

2. **调度与类型化**
   - `PlanTask` 强类型链路落地
   - `PlanRunner` 支持按依赖与 `priority` 推进
   - `PlanValidator` 已覆盖基础合法性校验

3. **持久化升级（核心）**
   - 已完成 PostgreSQL DB-only 迁移
   - 新增 `storage/db` 与 `storage/repositories` 分层
   - `ExecutionStore` 已基于 DB repository
   - `run-plan` 生命周期落库（`plan_runs` / `plan_run_tasks`）

4. **启动与配置**
   - 默认不再要求手动传 `--database-url`
   - DB 连接解析顺序：
     1) `--database-url`（可选覆盖）
     2) `DATABASE_URL` 环境变量
     3) `config/runtime.json` 的 `database_url`
   - 若都未配置，运行时按真实调用直接报错

5. **测试与文档**
   - storage / scheduler / cli contract 测试已补齐核心覆盖
   - README 已更新为 DB-only 运行说明与初始化步骤
   - `SESSION_HANDOFF.md` 已可用于下一轮快速恢复上下文

---

## 三、阶段计划（按优先级）

## 阶段 A（近期必做）：数据库初始化与迁移规范化

### 目标

把“手动 Python 命令建表”升级为项目内标准能力，降低使用门槛。

### 任务

1. 增加 `--init-db` CLI 子流程（或独立命令）
2. 提供一次性建表与幂等初始化
3. 接入 Alembic（迁移版本管理）
4. README 改为“初始化命令优先，脚本兜底”

### 验收标准

- 新同学只需配置连接后执行一条命令即可初始化
- 可以通过迁移脚本回放到最新 schema
- 不再依赖长 `python -c` 命令

---

## 阶段 B（近期必做）：run-plan 稳定性增强

### 目标

提升调度链路在失败场景下的可恢复性和可解释性。

### 任务

1. 增强任务失败语义（明确失败原因字段）
2. 增加失败重试策略（可配置最大重试次数）
3. 明确“部分失败”的 run 总状态规则
4. 补充 `plan_runs` / `plan_run_tasks` 的失败回放查询

### 验收标准

- 能回答“哪个任务为什么失败”
- 重试行为可预测且可追踪
- `run-plan` 总状态与明细状态一致

---

## 阶段 C（中期）：并发调度与资源控制

### 目标

从串行主路径平滑演进到可控并发执行。

### 任务

1. 基于 `max_workers` 强化并发执行边界
2. 引入超时控制与取消机制
3. 并发下保持状态写入一致性
4. 增加并发调度测试（竞态与顺序断言）

### 验收标准

- 无依赖任务可并发执行
- 并发数不超过配置值
- 状态流转无冲突、无覆盖错误

---

## 阶段 D（中期）：上下文传递与结果汇总

### 目标

让多 Agent 输出可复用、可汇总、可审阅。

### 任务

1. 标准化 `PlanTaskRenderer` 输出模板
2. 增加依赖任务摘要注入策略
3. 引入聚合器（Aggregator）输出最终报告
4. 增加摘要长度/上下文裁剪策略

### 验收标准

- 后续任务能消费前置结果摘要
- 最终报告不只是拼接，而是结构化整合
- 上下文大小可控

---

## 阶段 E（后续）：质量闭环与返工机制

### 目标

建立 Reviewer 驱动的自动质量提升回路。

### 任务

1. `ReviewAgent` 输出结构化评审结果
2. 返工策略（批准/驳回/建议）与最大返工次数
3. 返工过程状态建模与日志沉淀
4. 增加质量门槛（例如最低评分）

### 验收标准

- 低质量输出能自动触发返工
- 返工次数受控，不会无限循环
- 返工前后结果可追踪对比

---

## 四、当前建议学习节奏（结合你当前进度）

### 第 1 周（本周）

- 完成 `--init-db` 命令与 README 对齐
- 引入 Alembic 基础迁移

### 第 2 周

- 完成 run-plan 失败重试与状态细化
- 补齐失败路径测试

### 第 3 周

- 推进并发调度稳定性
- 完成并发下持久化一致性验证

### 第 4 周

- 引入 Aggregator + 上下文摘要策略
- 产出端到端“计划执行报告”

---

## 五、当前里程碑与提交锚点

- `6961442`：PostgreSQL DB-only 持久化迁移完成
- `9502a14`：默认 DB 连接改为 env/json 配置解析

建议后续按阶段单独提交，保持“一阶段一主题”：

- `feat: add init-db command and schema bootstrap`
- `feat: add alembic migrations baseline`
- `feat: add run-plan retry and failure policy`
- `feat: harden concurrent execution state persistence`

---

## 六、风险与注意事项

1. 当前仍存在本机 `pytest` 临时目录权限 warning，不影响主结论，但影响测试体验。
2. 目前尚未正式引入迁移版本控制，跨环境一致性风险较高。
3. 并发执行前需优先确认状态机与持久化写入的幂等性。
4. 工作区存在未跟踪文件（如 `data/plans/`），提交时需避免混入运行时产物。

---

## 七、下一步默认执行项（可直接开始）

1. 设计并实现 `--init-db` CLI
2. 补第一版 Alembic 初始化迁移
3. 将 README 的建表说明切换为“CLI 优先”

> 以上三项完成后，再进入 run-plan 失败重试阶段。
