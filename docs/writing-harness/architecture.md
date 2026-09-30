# Writer harness architecture

Writer is an experimental writing-native agent harness built on Prime
Agent. It explores whether recursive reasoning, persistent editorial
state, verification, model diversity, and continual harness refinement can
make frontier models produce more reliable and distinctive technical
writing.

## What we inherited from Prime Agent (untouched)

- **Agent loop** (`pa-agent`): turn loop over model stream + tool batch
  exec. No function-calling tools inside the kernel path; everything the
  model does runs as Python in the REPL.
- **RLM / Python REPL** (`prime-agent-runtime/src/rlm/`, `pa-core/src/kernel/`):
  persistent `__main__` namespace, NDJSON stdio protocol v3, `rlm.spawn`
  recursion bridge, `bash`/`mcp` imports, per-skill bootstrap injection.
- **Subagents** (`rlm.spawn/collect/list_subagents`, daemon supervisor):
  admission-immediate handles, `session-artifacts/<parent>/sub-<id>/`
  persistence, `find_models` fuzzy model search — model-per-subagent
  routing is native, no vendor hard-coding in V0.
- **Providers / models** (`pa-ai`, `pa-models`): registry + transports;
  orchestrator/research/writer/critic/verification policies are expressed
  by the caller at spawn time.
- **Sessions** (`pa-core/src/session/`, daemon `session_store`): append-only
  JSONL, kernel dill snapshots, harness `harness_state.json` (local vs
  global) — compaction-safe by construction.
- **Skills** (markdown + optional Python, `SKILL.md` frontmatter,
  user → project → `--skill` precedence, editable venv install).
- **Prompts** (slash-expandable `prompts/*.md`, `$1/$@/$ARGUMENTS`).
- **Continual harness** (`/refine`: planner → evidence-backed edits to
  supplemental state, immutable base prompt, rollback + history).
- **Tracing/telemetry** (`tracing` macros, `pa-telemetry` primitives-only
  events, agent-traces upload). V0 adds writing summaries, not a parallel
  pipeline.
- **CLI/TUI** (`pa-cli`, `pa-daemon`, `pa-tui`): daemon-backed interactive
  TUI is the primary surface; headless `-p` is the secondary interface.

## What the writing layer adds (all new, clearly separated)

| Path | Owns |
| --- | --- |
| `crates/pa-writer/` | Canonical editorial state: `Project Brief Audience Source Claim Draft VoiceProfile Evaluation Preference RunTrace RunQuality ExecRecord` + file-backed `drafts/sources/claims/evals/preferences/traces/status` APIs plus V1 `extract` (heuristic candidates), evidence-gated `claims::verify`, `execs` records, `models` routing policy, blind `evals::blind_*`, and `traces::summarize` quality counters over `writing/`. Leaf crate, no workspace deps. |
| `skills/writer/` | Python RLM skill (`import writer`) over the same `writing/` format: V0 state APIs plus `claims_extract`/`extract_candidates`, `claims_verify`/`verify_draft`, `exec_check`/`exec_list`, `models_policy`/`models_set_policy`/`models_pick_critic`/`models_role`, Prime introspection (`models_status/current/describe/providers/ready`, OpenRouter live refresh + cache), `blind_present`/`blind_resolve`/`blind_tally`, `trace_summary` (split into `_store`/`_extract`/`_execs`/`_models`/`_prime`/`_blind`/`_quality` by responsibility). Bootstrap auto-imports it; no `runtime_code.rs` change. |
| `skills/{technical-writing,research,editorial-critique,technical-verification,voice}/` | Markdown principles, not step micromanagement. `editorial-critique` additionally carries the critic-subagent spawn recipe (diagnose contract, parent-persists rule, model-diversity wiring). |
| `writer/prompts/` | Slash commands `/drafts /sources /claims /compare /verify /voice /project /trace` plus `/write` (autonomous capability orchestrator: brief → trace → decide → persist → final) as prompt templates (render via agent + `writer` skill, reusing Prime TUI rendering). |
| `writer/writer` | `writer` entrypoint: bare → interactive TUI with writer skills wired in; `-p`/subcommands → headless passthrough + local state helpers. |
| `benchmarks/technical-writing/` | 11-task suite + `run.py` A/B runner (vanilla vs writer, same model) with blind-judging commands. Tests the harness-effect hypothesis; no numeric scores. |
| `dogfood/supervisor-sessions/` | V1 dogfood article + critique (worked example of the full loop). |
| `docs/writing-harness/` | This documentation. |

## Boundaries

- Editorial logic lives in `pa-writer` + `skills/writer`, never in TUI
  components. The TUI is a client: `TUI → writing agent APIs → editorial
  state → Prime runtime/RLM`.
- Same harness from TUI, headless CLI, RPC, SDK, future web UI — only the
  renderer changes.
- No rigid pipeline (research → outline → draft → ...) anywhere. Skills
  and state are capabilities; the orchestrating model decides when to
  research, spawn a critic, verify, compare, or stop.

## State flow (ASCII)

```text
                +-------------------+
                |   writer (TUI)    |
                |  conversational   |
                +--------+----------+
                         |  /drafts /compare ... (prompt templates)
                         v
                +--------+----------+
                | orchestrator model|
                |  (any provider)   |
                +--+-----+-----+----+
                   |     |     |
        +----------+  +--+--+  +----------+
        | research |  |critic|  | verify   |   rlm.spawn(model per role)
        | subagent |  |  ... |  | subagent |
        +----+-----+  +--+--+  +-----+----+
             |           |           |
             +-----+-----+-----+-----+
                   |  import writer  |
                   v                 v
            +------+-----------------+------+
             |      writing/ (disk)          |
            | project brief sources claims  |
            | voice drafts evals prefs traces|
            +------+-----------------+------+
                   ^                 ^
                   |  same format    |
            +------+--------+  +-----+-------+
            | pa-writer     |  | Prime       |
            | (Rust tests,  |  | sessions /  |
            | future clients)|  | harness /   |
            +----------------+  | telemetry   |
                                +-------------+
```

Compaction/restart safety: conversation summarizers keep working context;
`writing/` files are re-read on demand, and subagents inherit `cwd` so
they share one project. Nothing load-bearing lives only in chat history.
