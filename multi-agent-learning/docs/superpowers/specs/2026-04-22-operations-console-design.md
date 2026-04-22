# Multi-Agent Learning Operations Console Design

Date: 2026-04-22
Status: Approved in conversation, ready for implementation planning

## 1. Summary

This spec defines the first visual operations console for `multi-agent-learning`.

The console is not a replacement for the current CLI. It is a local-first web control
surface that sits on top of the existing execution core:

- `PlannerAgent` creates plans
- `PlanRunner` executes plans
- PostgreSQL remains the source of truth
- CLI remains available for scripting, debugging, and low-level verification

The first version prioritizes two user goals:

1. run control
2. run observability

The rollout strategy is:

- build for local single-user operation first
- keep clean API and service boundaries
- preserve a path to future service deployment without rewriting the UI

## 2. Product Goals

### Goals

- Create plans from a web UI
- Start plan runs from a web UI
- Observe run lifecycle and task-level execution state visually
- Inspect failure details without digging through raw CLI output
- Keep the implementation aligned with the existing DB-only architecture
- Separate UI concerns from execution concerns so service deployment remains viable later

### Non-Goals for V1

- Multi-user auth, roles, or permissions
- Distributed workers or a queue-based execution platform
- Real interruption of already-running tasks
- Full workflow editing in the browser
- WebSocket or event-stream delivery
- Agent management, provider admin, or system settings pages

## 3. User Scope and Operating Model

V1 targets a local developer workflow:

- one user
- one local browser session
- one local API process
- one PostgreSQL database

The design must still avoid hard-coding a purely desktop-only architecture. The frontend
should talk to a stable HTTP API rather than directly reading the database or shelling out
to CLI commands.

## 4. Recommended Architecture

### 4.1 High-Level Shape

The system will be split into three layers:

1. execution core
2. local API layer
3. browser console

#### Execution Core

This remains the existing Python application logic and database persistence:

- `PlannerAgent`
- `PlanRunner`
- repositories
- DB session factory
- PostgreSQL tables

This layer remains the source of truth for plan creation and execution semantics.

#### Local API Layer

A small Python web service will expose console-focused use cases:

- create plan
- list plans
- get plan details
- start run
- list runs
- get run details
- request retry
- receive unsupported control requests such as pause and cancel

This layer owns request validation, response shaping, and orchestration of application
services. It should not duplicate execution logic that already exists in the CLI path.

#### Browser Console

A lightweight browser UI will call the API only. It must not:

- connect to PostgreSQL directly
- construct raw SQL
- call `main.py`
- reimplement scheduler behavior

### 4.2 Technology Direction

The backend should stay in Python to maximize reuse of the existing codebase.

Recommended V1 direction:

- Python HTTP service, preferably FastAPI
- thin application service layer under the API
- small SPA frontend, preferably React, focused on polling-based state refresh

Reasoning:

- FastAPI fits the existing Python stack and clear REST contract
- a small SPA keeps the frontend decoupled from Python templates
- React is justified here because the product is a stateful control console, not a static site

This is intentionally not the smallest possible stack, but it best supports the chosen
"local first, serviceable later" direction.

## 5. System Boundaries

### 5.1 CLI Relationship

The CLI remains supported. The console is an additional entry point, not a rewrite.

Both CLI and web paths should converge on shared application services where possible.

This avoids creating two incompatible systems:

- CLI-only logic in `main.py`
- web-only logic elsewhere

### 5.2 Application Service Boundary

Add explicit use-case-oriented services between API handlers and the current agents/runners.

Examples:

- `PlanCreationService`
- `RunLaunchService`
- `RunQueryService`
- `RunControlService`

These services should depend on:

- repositories
- session factory
- planner agent
- plan runner

They should not depend on browser-specific concerns.

## 6. Information Architecture

V1 will ship with four primary views.

### 6.1 Dashboard

Purpose:

- provide current system awareness
- act as the default landing page

Contents:

- recent runs
- counts for running, completed, and failed runs
- recent failed tasks
- recent plans
- a clear "create plan" and "run plan" entry point

### 6.2 Plans

Purpose:

- manage plan entities
- inspect what a generated plan contains before executing it

Contents:

- plan list
- source goal
- provider
- model
- created time
- number of tasks

Plan detail shows:

- plan metadata
- ordered task list
- dependency information
- task priority
- assigned agent type based on dispatcher rules

V1 actions:

- create plan
- inspect plan
- launch a run from a plan

### 6.3 Runs

Purpose:

- observe execution history
- navigate to active or failed work quickly

Contents:

- run list with `run_id`, `plan_id`, status, time range, and `max_workers`
- status filters
- quick access to retry

### 6.4 Run Detail

Purpose:

- serve as the primary observability and control surface for a single run

Sections:

- top summary bar
- task flow/status section
- execution detail inspector

Top summary bar:

- run metadata
- current execution status
- optional control status
- start/end timestamps
- actions such as retry, pause, cancel

Task flow/status section:

- task cards or rows
- dependencies
- task state
- assigned agent
- last update time

Execution detail inspector:

- output summary
- raw error text
- metadata snapshot
- state snapshot

## 7. Core User Flows

### 7.1 Create Plan

1. user enters a task goal in the console
2. user optionally selects provider/model options
3. frontend calls `POST /api/plans`
4. backend invokes planner workflow
5. plan is persisted to `plans` and `plan_tasks`
6. UI navigates to plan detail

V1 keeps this form intentionally small and aligned with current CLI semantics.

### 7.2 Start Run

1. user clicks "Run this plan" from Dashboard or Plan Detail
2. user chooses a small number of execution options, such as `max_workers`
3. frontend calls `POST /api/runs`
4. backend creates a run and starts execution in a background-capable local process path
5. UI navigates to Run Detail and begins polling

V1 does not require streaming progress transport. Polling is sufficient.

### 7.3 Observe Run

1. user opens Run Detail
2. UI polls run summary and task details
3. user inspects failed tasks, outputs, and metadata
4. user optionally retries the run from the console

### 7.4 Retry Run

V1 retry semantics are intentionally simple:

- retry creates a new run for the same `plan_id`
- it does not resume a partially completed run
- it does not retry only the failed subset

This keeps the first implementation aligned with the current fail-fast execution model.

## 8. API Design

### 8.1 Endpoints

#### `POST /api/plans`

Request:

- `task`
- `provider`
- optional `model`
- optional `thinking`

Behavior:

- create a plan through the planner workflow
- persist to DB
- return `plan_id` and summary data

#### `GET /api/plans`

Behavior:

- return plan summaries for list view

#### `GET /api/plans/{plan_id}`

Behavior:

- return plan metadata and task list

#### `POST /api/runs`

Request:

- `plan_id`
- `max_workers`

Behavior:

- create a run
- start execution
- return `run_id`

#### `GET /api/runs`

Behavior:

- return run summaries

#### `GET /api/runs/{run_id}`

Behavior:

- return run summary fields and aggregate task counters

#### `GET /api/runs/{run_id}/tasks`

Behavior:

- return task-level state, execution linkage, and state snapshots

#### `POST /api/runs/{run_id}/retry`

Behavior:

- create a new run for the same plan
- return the new `run_id`

#### `POST /api/runs/{run_id}/pause`
#### `POST /api/runs/{run_id}/cancel`

Behavior in V1:

- return a structured unsupported response
- record or expose intent only if the backend schema supports it

Recommended status code:

- `409 Conflict` with a clear explanation that the current execution model does not support
  mid-run interruption

### 8.2 Response Principles

Responses should be designed for the console rather than mirroring raw ORM rows.

They should:

- expose stable field names
- include timestamps in ISO format
- include concise error summaries where available
- avoid leaking internal-only persistence details

## 9. Data Model Direction

### 9.1 Existing Tables to Reuse

V1 should continue to rely on:

- `plans`
- `plan_tasks`
- `plan_runs`
- `plan_run_tasks`
- `executions`

### 9.2 Minimal Schema Additions

V1 may extend `plan_runs` with optional console-related fields:

- `trigger_source`
- `requested_by`
- `control_status`

Recommended meanings:

- `trigger_source`: `cli` or `dashboard`
- `requested_by`: reserved for future multi-user use, nullable in V1
- `control_status`: UI-side control intent, separate from execution result

### 9.3 State Separation

Execution state and control intent must remain separate.

Examples:

- `status = running`
- `control_status = cancel_requested`

This is important because V1 will not support real interruption of already-running work.
The UI must not falsely report that a run was cancelled if the engine is still executing.

## 10. Execution and Control Semantics

### 10.1 Execution Status

The system should continue using the real execution state as the authoritative run state.

Expected run states in V1:

- `running`
- `completed`
- `failed`

Task states should continue aligning with the current scheduler behavior.

### 10.2 Control Actions in V1

Control buttons will exist in the UI, but only some actions are real in V1.

Supported:

- create plan
- start run
- retry run as a brand-new run

Not truly supported yet:

- pause active run
- cancel active run
- manually alter task state in an active run

The console should present these unsupported controls honestly:

- disabled buttons with explanatory text, or
- active buttons that return a structured unsupported message

The product should not imply capabilities the engine does not yet have.

## 11. Polling and Refresh Strategy

V1 uses polling only.

Recommended intervals:

- Dashboard: every 5 seconds
- Runs list: every 5 seconds
- Run Detail: every 2 seconds

V1 explicitly does not include:

- WebSocket
- SSE
- push notifications

These can be introduced later if run volume or UI responsiveness requires them.

## 12. Error Handling

The console must make failures understandable.

### 12.1 Error Classes to Distinguish

- plan creation failure
- run launch failure
- task execution failure
- unsupported control action
- infrastructure failure such as database connection failure

### 12.2 UI Behavior

List pages:

- show short error summaries and status markers

Detail pages:

- show raw error text when available
- show which task failed
- show which agent ran it
- show related timestamps and metadata

The UI should prefer clarity over log-volume. It should not bury the failure in unstructured
dump output.

## 13. Testing Strategy

V1 testing should focus on behavior that protects the control and observability contract.

### 13.1 API Contract Tests

Verify:

- request validation
- status codes
- response shapes
- unsupported-control responses

### 13.2 Application Service Tests

Verify:

- plan creation
- run start
- run detail query
- retry behavior

### 13.3 Integration Tests

Verify:

- create plan through API
- start run through API
- query run summary and task details
- observe failure details when a task fails

### 13.4 Out of Scope for V1 Tests

- browser E2E automation
- real pause/cancel interruption behavior
- streaming update transport

## 14. Rollout Plan

### Phase 1

Deliver:

- local API layer
- Dashboard
- Plans
- Runs
- Run Detail
- create plan
- start run
- retry as new run
- polling-based observability

### Phase 2

Deliver:

- control intent fields and richer UI states
- pause/cancel placeholders or request tracking
- stronger dependency visualization
- richer run summaries and failure inspection

## 15. Risks and Constraints

- The current `PlanRunner` is synchronous and effectively fail-fast, which limits real-time
  control semantics in V1.
- The repository currently has no web stack, so adding a frontend toolchain is a real scope
  increase and must be kept small.
- Schema additions should remain tightly scoped so they do not distract from the existing
  DB-only persistence work.
- The console must not outpace backend truth. Honest unsupported states are better than fake
  controls.

## 16. Final Recommendation

Build the first visual direction of `multi-agent-learning` as a local-first operations
console with a thin Python API layer and a small SPA frontend.

This gives the project a real control and observability surface without rewriting the
execution core, and it preserves a clean path from local use to future service deployment.
