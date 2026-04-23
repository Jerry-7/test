# Runtime Model Profile Design

Date: 2026-04-23
Status: Approved in conversation, ready for implementation planning

## 1. Summary

This spec extends the operations console so the web app can start before any
provider-specific API key is configured.

Instead of requiring model credentials from environment variables at startup,
the console will:

- start with only database access and an application secret key
- let the user manage model profiles in the browser
- store provider/model settings in PostgreSQL
- store provider API keys as reversible encrypted values
- require profile selection when creating a plan or starting a run

This is an additive extension to the operations console design from 2026-04-22.
It does not replace the existing CLI contract, but it changes how the web
console resolves runtime model configuration.

## 2. Product Goals

### Goals

- Allow the operations console API and UI to start without `OPENAI_API_KEY`,
  `DASHSCOPE_API_KEY`, or other provider-specific environment variables
- Let users create, edit, view, and delete multiple runtime model profiles in
  the browser
- Encrypt provider API keys before storing them in PostgreSQL
- Decrypt provider API keys only when a specific plan or run needs them
- Let users choose a model profile when creating a plan
- Let users choose a model profile when launching a run
- Persist which model profile was used by each plan and run

### Non-Goals for V1

- Multi-user secret isolation
- Secret rotation workflows
- Secret audit logs
- Automatic API key validation against external provider endpoints
- Fine-grained profile permissions
- Browser-side master-key unlock flow
- External secret manager integration

## 3. User Workflow

V1 user experience should work like this:

1. Start the operations console with only:
   - `DATABASE_URL`
   - `APP_SECRET_KEY`
2. Open the browser UI
3. If no model profiles exist, see an empty-state prompt directing the user to
   configure one
4. Create one or more model profiles from the browser
5. Select a profile when creating a plan
6. Select a profile again when launching a run
7. Inspect which profile, provider, and model were used in plan/run details

This keeps startup and runtime concerns separate.

## 4. Boot and Runtime Separation

### 4.1 App Boot State

The console application must be able to boot without any provider API key in the
environment.

Boot requirements in V1:

- `DATABASE_URL`
- `APP_SECRET_KEY`

Boot must not require:

- `OPENAI_API_KEY`
- `OPENROUTER_API_KEY`
- `DASHSCOPE_API_KEY`
- `ZAI_API_KEY`

This is the central behavior change relative to the current operations console.

### 4.2 Runtime Model State

Actual provider credentials are resolved only when a request needs to call a
model.

Examples:

- `POST /api/plans` with a chosen `profile_id`
- `POST /api/runs` with a chosen `profile_id`

At that point the backend will:

1. load the selected model profile from PostgreSQL
2. decrypt the stored API key using `APP_SECRET_KEY`
3. build a runtime model configuration object
4. create the planner or execution runtime for that request

## 5. Architecture Changes

### 5.1 Replace Startup-Time Provider Resolution for the Web App

The current web console startup path constructs a provider configuration at app
startup. That must change.

The web app should no longer create a single global `provider_config` during
startup. Instead, startup should create only application-level infrastructure:

- database session factory
- encryption/decryption helper
- repository access

Planner and execution runtimes should be created per request from the selected
model profile.

### 5.2 Introduce Two Separate Context Types

#### AppContext

Used at startup. Contains only application-level dependencies:

- `database_url`
- `session_factory`
- `secret_cipher`

#### ResolvedModelProfile

Used per request. Contains the actual runtime model settings:

- `provider`
- `model_name`
- `api_key`
- `base_url`
- `thinking_mode`

This separation prevents the app from confusing "application is bootable" with
"a provider configuration is already available."

### 5.3 Dynamic Runtime Creation

Planner and run execution should use request-scoped model configuration.

That means:

- `create_plan(task, profile_id)` resolves a runtime profile for that request
- `start_run(plan_id, profile_id, max_workers)` resolves a runtime profile for
  that request

The web console should not rely on a process-global provider preset after boot.

## 6. Data Model Design

### 6.1 New Table: `model_profiles`

V1 should introduce a dedicated `model_profiles` table.

Recommended fields:

- `profile_id`: UUID primary key
- `name`: user-facing profile label
- `provider`: one of `openai`, `openrouter`, `qwen`, `glm`
- `model_name`: concrete model string
- `base_url`: nullable override
- `thinking_mode`: `default`, `on`, or `off`
- `api_key_encrypted`: encrypted API key ciphertext
- `api_key_hint`: masked display hint such as last four characters
- `created_at`
- `updated_at`

### 6.2 Persist Profile Usage

To keep runs explainable and reproducible, the system should also persist which
profile was used.

Recommended additions:

- `plans.model_profile_id`
- `plan_runs.model_profile_id`

This enables the console to answer:

- which profile created this plan
- which profile executed this run

### 6.3 Why Profile IDs Matter

Persisting only `provider` and `model_name` is not enough because:

- two profiles may use the same provider/model with different API keys
- two profiles may use different base URLs
- the console needs a stable entity to display and manage

The profile itself is the correct unit of traceability.

## 7. Secret Storage Design

### 7.1 Master Key Source

The reversible encryption master key will come from an environment variable:

- `APP_SECRET_KEY`

V1 intentionally keeps the master key outside the database.

### 7.2 Encryption Boundary

The backend should encrypt API keys before writing them to PostgreSQL and
decrypt them only when needed for runtime execution.

Recommended component:

- `SecretCipher` or similarly named helper under a dedicated security module

Responsibilities:

- `encrypt(plaintext) -> ciphertext`
- `decrypt(ciphertext) -> plaintext`

This helper should encapsulate all encryption details so application services
never manipulate raw crypto primitives directly.

### 7.3 Display Behavior

The browser UI may support showing the plaintext API key while editing a saved
profile, but that plaintext should still originate from a backend decrypt
operation and never be stored unencrypted in the database.

V1 accepted UX:

- profile edit page receives the decrypted API key
- UI renders it in a hidden/password field by default
- user must click `Show` before plaintext becomes visible
- user can edit and save the new plaintext value

### 7.4 Security Tradeoff

This design intentionally favors local single-user usability over stronger
separation controls. Because the user explicitly requested editable plaintext
recall, V1 accepts that the browser can receive decrypted secrets during edit
flows.

This is acceptable for the current local-first, single-user operations console,
but it should be documented as a conscious tradeoff rather than an implicit one.

## 8. Profile UX and Interaction Design

### 8.1 New Console Section: Model Profiles

The operations console should gain a dedicated `Model Profiles` page.

It should not be folded into Dashboard, Plans, or Runs. Profiles are a distinct
system concern.

### 8.2 Profiles List View

The list page should show:

- `name`
- `provider`
- `model_name`
- `base_url` summary
- `thinking_mode`
- `api_key_hint`
- `updated_at`

Primary actions:

- create profile
- edit profile
- delete profile
- duplicate profile

### 8.3 Profile Editor

The editor should support:

- `name`
- `provider`
- `model_name`
- `base_url`
- `thinking_mode`
- `api_key`

API key behavior:

- default hidden/password mode
- explicit `Show` / `Hide` toggle
- existing profile values may be loaded and edited

### 8.4 Empty State Behavior

When no profiles exist:

- Dashboard should show a "No model profile configured" prompt
- plan/run creation flows should block gracefully
- the UI should provide a direct link to the `Model Profiles` page

The app should remain booted and navigable even when no runtime model profiles
exist.

## 9. Plan and Run Interaction Changes

### 9.1 Plan Creation

Plan creation should require a selected `profile_id`.

Flow:

1. user enters task goal
2. user selects a model profile
3. backend resolves and decrypts that profile
4. planner runtime is created for that request
5. resulting plan stores `model_profile_id`

### 9.2 Run Launch

Run launch should also require a selected `profile_id`.

The selected profile may differ from the profile that created the plan.

V1 should support:

- defaulting to the plan's original profile in the UI
- allowing the user to choose a different profile before starting the run

This supports experimentation across providers and models.

### 9.3 Plan and Run Detail Pages

Plan detail should display:

- model profile name
- provider
- model name

Run detail should display:

- model profile name
- provider
- model name

This keeps execution behavior understandable from the UI.

## 10. Backend Service Design

### 10.1 ModelProfileService

Introduce a dedicated service for profile lifecycle and resolution.

Responsibilities:

- create profile
- list profiles
- get profile detail
- update profile
- delete profile
- duplicate profile
- resolve runtime profile by decrypting stored API key
- generate `api_key_hint`

### 10.2 PlanService Changes

Plan creation should move from:

- `create_plan(task)`

to:

- `create_plan(task, profile_id)`

Internally it should:

1. resolve the selected runtime model profile
2. instantiate the planner runtime for that request
3. persist the plan with `model_profile_id`

### 10.3 RunService Changes

Run launching should move from:

- `start_run(plan_id, max_workers)`

to:

- `start_run(plan_id, profile_id, max_workers)`

Internally it should:

1. resolve the selected runtime model profile
2. instantiate execution agents for that request
3. persist the run with `model_profile_id`

### 10.4 Request-Scoped Agent Assembly

Planner and worker agents should be built from the selected model profile at
request time, not during app boot.

This is a key architectural requirement for this feature.

## 11. API Design

### 11.1 New Profile CRUD Endpoints

Recommended endpoints:

- `GET /api/model-profiles`
- `POST /api/model-profiles`
- `GET /api/model-profiles/{profile_id}`
- `PUT /api/model-profiles/{profile_id}`
- `DELETE /api/model-profiles/{profile_id}`
- `POST /api/model-profiles/{profile_id}/duplicate`

### 11.2 Request Fields

Profile create/update requests should include:

- `name`
- `provider`
- `model_name`
- `base_url`
- `thinking_mode`
- `api_key`

### 11.3 Response Shapes

List responses should include:

- `profile_id`
- `name`
- `provider`
- `model_name`
- `base_url`
- `thinking_mode`
- `api_key_hint`
- `updated_at`

Detail responses may include:

- same fields as list
- decrypted `api_key`

Because the user explicitly requested editable recall, V1 may return the
plaintext API key in detail/edit responses. However, list responses should never
return plaintext.

### 11.4 Plan and Run API Changes

Update these existing endpoints:

- `POST /api/plans` must require `profile_id`
- `POST /api/runs` must require `profile_id`

This ensures runtime model selection is explicit.

## 12. Error Handling

### 12.1 Boot Errors

The app should fail to boot when:

- `DATABASE_URL` is missing
- `APP_SECRET_KEY` is missing

The app should not fail to boot when:

- no model profile exists
- no provider API key exists in the environment

### 12.2 Profile Validation Errors

The backend should return explicit business errors for:

- unsupported provider
- missing required fields
- malformed encrypted payload
- decryption failure
- invalid or unsupported `thinking_mode`

### 12.3 Runtime Selection Errors

Plan/run requests should return explainable errors for:

- missing `profile_id`
- nonexistent profile
- profile cannot be decrypted with current `APP_SECRET_KEY`
- incomplete profile data

### 12.4 Model Execution Errors

Provider runtime failures remain distinct from profile-management failures.

Examples:

- invalid provider API key
- invalid model name
- wrong base URL
- provider authentication failure

These should appear as run-time execution failures, not profile CRUD failures.

## 13. State Semantics

V1 should distinguish:

- application boot state
- model profile validity state
- runtime execution state

Even if no valid profile exists, the application should still be considered
"booted" if the API/UI can run.

This distinction is important to satisfy the "start first, configure later"
requirement.

## 14. Scope for V1

V1 includes:

- model profiles stored in PostgreSQL
- reversible encrypted provider API key storage
- `APP_SECRET_KEY` from environment
- profile management UI
- required profile selection during plan creation
- required profile selection during run launch
- `plans.model_profile_id`
- `plan_runs.model_profile_id`
- plaintext recall in edit flow, hidden by default and shown on demand

V1 excludes:

- multi-user secret isolation
- master-key rotation
- external secret manager support
- profile permissions
- provider-side key validation
- browser unlock/passphrase flow
- secret audit log

## 15. Risks and Tradeoffs

- Returning decrypted API keys to the browser during edit flows is a deliberate
  local-first usability tradeoff.
- Request-scoped runtime assembly is more complex than static startup wiring,
  but it is required to support late-bound configuration.
- Schema changes must stay narrow and focused so they do not destabilize the
  existing operations-console rollout.

## 16. Final Recommendation

Extend the operations console with database-backed runtime model profiles,
encrypt provider API keys with an application secret from the environment, and
resolve provider credentials only at request time.

This keeps startup lightweight, preserves local usability, and matches the
user's goal of booting the console before any provider model configuration
exists.
