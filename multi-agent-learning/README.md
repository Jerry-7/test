# Multi-Agent Learning

这是一个配合 `multi-agent-learning-plan.md` 使用的 Python 学习项目。

当前已完成：

- 阶段 1：基于 LangChain 的单 Agent 基础任务执行

你将从这里开始，逐步扩展到 Planner、Dispatcher、DAG 调度、多 Worker Agent、Review 和 Memory。

## 当前技术选型

- Python 3.10+
- `langchain==1.2.15`
- `langchain-openai==1.1.12`

以上版本是我按 2026-04-07 查询 PyPI 后选用的近期稳定版本。
当前代码采用 LangChain v1 风格：

- 用 `langchain.agents.create_agent` 创建 Agent
- 用 `langchain_openai.ChatOpenAI` 接 OpenAI 模型

同时，这个项目现在支持通过 OpenAI 兼容接口切换多种提供方：

- `openai`
- `openrouter`
- `qwen`
- `glm`

## 为什么这样设计

这份项目是用来学习多 Agent 的，所以我尽量把“模型接入层”和“调度层”拆开：

- `src/config/model_provider.py` 负责解析不同提供方的配置
- `src/agents/basic_agent.py` 只负责执行，不直接读取复杂环境变量
- 这样你后面写 `PlannerAgent`、`Dispatcher` 时，可以复用同一套模型配置

## 当前目录结构

```text
multi-agent-learning/
  .env.example
  .gitignore
  README.md
  requirements.txt
  src/
    main.py
    agents/
      __init__.py
      base_agent.py
      basic_agent.py
    config/
      __init__.py
      model_provider.py
    models/
      __init__.py
      task.py
    storage/
      __init__.py
      execution_store.py
    utils/
      __init__.py
      time_utils.py
  data/
    executions/
  examples/
    task_01_basic.md
```

## 阶段 1 学习目标

- 理解一个最小 LangChain Agent 的输入、执行、输出流程
- 学会把任务执行记录写入本地 JSON
- 为后续多 Agent 调度预留清晰结构

## 安装依赖

在 `multi-agent-learning` 目录下运行：

```bash
pip install -r requirements.txt
```

或：

```bash
py -3 -m pip install -r requirements.txt
```

## 配置环境变量

### 1. 使用 OpenAI

```bash
set OPENAI_API_KEY=你的密钥
set OPENAI_MODEL=gpt-5-nano
```

### 2. 使用 OpenRouter

```bash
set OPENROUTER_API_KEY=你的密钥
set OPENROUTER_MODEL=openai/gpt-5.2
set OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
```

可选：

```bash
set OPENROUTER_HTTP_REFERER=https://your-site.example
set OPENROUTER_X_TITLE=multi-agent-learning
```

### 3. 使用 Qwen

```bash
set DASHSCOPE_API_KEY=你的密钥
set QWEN_MODEL=qwen-plus-latest
set QWEN_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
```
```powershell
$env:DASHSCOPE_API_KEY=""
$env:QWEN_MODEL="qwen3.6-plus"
$env:QWEN_BASE_URL="https://dashscope.aliyuncs.com/compatible-mode/v1"
```
### 4. 使用 GLM

```bash
set ZAI_API_KEY=你的密钥
set GLM_MODEL=glm-5
set GLM_BASE_URL=https://open.bigmodel.cn/api/paas/v4/
```

### 5. 最少需要配置什么

你至少要准备“与你当前 provider 匹配的 API Key”。

例如：

```bash
set OPENAI_API_KEY=你的密钥
```

## 运行方式

### OpenAI

```bash
py -3 src/main.py --provider openai --task "请总结多 Agent 系统的核心组成"
```

### OpenRouter

```bash
py -3 src/main.py --provider openrouter --task "解释多 Agent 调度最小闭环"
```

### Qwen

```bash
py -3 src/main.py --provider qwen --task "解释多 Agent 调度最小闭环"
```

### GLM

```bash
py -3 src/main.py --provider glm --task "解释多 Agent 调度最小闭环"
```

### 手动覆盖模型名

```bash
py -3 src/main.py --provider qwen --model qwen-max-latest --task "比较规划器和执行器"
```

### 手动覆盖 base_url

例如你想切换到 Qwen 国际站区：

```bash
py -3 src/main.py --provider qwen --base-url https://dashscope-intl.aliyuncs.com/compatible-mode/v1 --task "解释调度器"
```

## 当前代码包含什么

- `BaseAgent`：统一 Agent 接口
- `BasicAgent`：内部使用 LangChain `create_agent`
- `model_provider.py`：统一解析 `openai / openrouter / qwen / glm` 配置
- `Task` / `TaskExecution`：任务与执行记录模型
- `ExecutionStore`：把执行记录持久化到本地 JSON
- `main.py`：命令行入口

## 建议学习顺序

1. 看 `src/main.py`，理解 CLI 参数如何进入系统
2. 看 `src/config/model_provider.py`，理解不同提供方如何统一配置
3. 看 `src/agents/basic_agent.py`，理解 LangChain Agent 如何创建和调用
4. 看 `src/models/task.py` 和 `src/storage/execution_store.py`，理解执行记录如何落盘
5. 运行一次后打开 `data/executions/executions.json`，观察任务轨迹

## 学习提醒

- `ChatOpenAI` 官方文档明确说明，它优先面向 OpenAI 官方规范
- 当你把 `base_url` 指向 OpenRouter、Qwen、GLM 这类兼容接口时，基础聊天通常可工作
- 但第三方提供方扩展的非标准字段，LangChain 可能不会完整保留
- 对当前阶段的学习项目来说，这个折中是合理的：你先学清楚统一接口，再逐步学习 provider-specific 差异

## 下一阶段建议

你学完这一阶段后，可以继续实现：

1. `PlannerAgent`：把复杂任务拆成多个子任务
2. `Dispatcher`：根据 `task.type` 分配 Agent
3. `plan.json`：保存结构化任务计划
