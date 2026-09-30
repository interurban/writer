# Writer model access

Writer creates no provider framework. Prime owns authentication, catalogs,
selection, thinking levels, and request handling; Writer only reads Prime
state and chooses among Prime-resolved models.

## Authentication paths (all Prime-native)

- **ChatGPT Plus/Pro**: `/login` → Codex subscription OAuth; credentials
  under provider id `openai-codex` in `<agent>/auth.json` (refresh owned
  by Prime). Separate billing from API keys by construction.
- **OpenRouter**: `OPENROUTER_API_KEY` env or `/login` → OpenRouter
  (provider id `openrouter`); model ids are opaque `provider/id`
  selectors (e.g. `openrouter/moonshotai/kimi-k2.6`).
- **Direct OpenAI**: `OPENAI_API_KEY` env or `/login` (provider id
  `openai`). Works wherever Writer runs; never a silent fallback target.

## What Writer adds (`skills/writer/src/writer/_prime.py`)

- `models_status()` → `{primary, providers, ready, reasons, policy}`:
  the readiness snapshot for the `writer` shim banner and the RLM.
  Never blocks; never prints secrets (auth IDs only, env names only).
- `models_current(selector?, thinking?)`: the kernel cannot see its own
  session model, so the orchestrator passes what `/model` shows; Prime
  settings defaults (`defaultProvider/defaultModel/…`) fill the rest.
- `models_describe(selector)`: catalog metadata from Prime's on-disk
  caches; unknown stays unknown.
- `models_refresh_openrouter()` / `models_cached_openrouter()`: live
  OpenRouter listing via env key only (Prime-login credentials never
  read), cached to `writing/cache/` (metadata only). Prime's static
  catalog remains the selection path (`/model`); this is the freshness
  complement, not a hard-coded list.
- Five-role policy in `writing/models.json` (`primary research critic
  verification judge`, all inherit by default; V1 `writer` key honored
  as `primary`). `models_role()` resolves to a spawn selector or inherit
  (+ `thinking_hint: high` for the `reasoning` strategy).
- `/model-test` (`writer/prompts/model-test.md`): tiny-request smoke test
  through the current session model with actionable errors.

## Family rule

Family = opaque provider segment (`models_family`). Critic diversity,
judge independence, and telemetry all compare strings — no vendor names
anywhere, including future code.
