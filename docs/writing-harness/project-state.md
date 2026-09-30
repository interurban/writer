# Project state

Root: `<workdir>/writing/` (`$WRITER_DIR` overrides for tests/tools;
legacy `<workdir>/.writer` auto-migrates on first open, never merged).
Shared verbatim between the Rust `pa-writer` crate and the Python `writer`
RLM skill — either side can read what the other wrote.

```text
writing/
  project.json            {name, goal?, current_draft_id?, final_draft_id?, created_at, updated_at}
  brief/objective.md      working objective (markdown)
  brief/audience.md       rendered audience notes (markdown)
  brief/constraints.md    constraints (markdown)
  brief/brief.json        {label, background, notes}
  sources/index.json      [Source{id,title,url?,origin?,captured_at,notes?,excerpts[]}]
  claims/ledger.json      [Claim{id,text,type,importance,source_ids,support,verification,draft_id?,location?}]
  voice/profile.json      {vocabulary,cadence,formality,technical_density,point_of_view,humor,structure}
  voice/avoid.md          anti-patterns for this writer
  voice/examples/         approved samples (markdown, optional in V0)
  drafts/index.json       [DraftMeta...] (bodies live alongside)
  drafts/draft-001.md     immutable revision bodies
  framings/candidates.json  [{thesis,why_matters,contrast,mental_model,risk,status}]
  framings/selected.json    {frame_id,criterion,reasoning,judge} (winner + why)
  models.json             {primary,research,critic,verification,judge} routing policy (absent = all inherit)
  evals/evaluations.jsonl {criterion, subjects, evaluation{...}} per line
  evals/blind.jsonl       sealed {frame_id, label_a, label_b, swapped} mappings (V1)
  preferences/preferences.jsonl {draft_a,draft_b,winner,reasons,created_at} per line
  traces/runs.jsonl       run envelopes incl. quality counters (readers take last per run_id)
  traces/exec.jsonl       exec-check records {id,label,command,exit_status,stdout,stderr} (V1)
  traces/critiques/       critic outputs as markdown (trace-adjacent; never drafts) (V1)
```

## Rules

- Drafts are immutable: `drafts_save` always mints `draft-NNN`; "revert"
  repoints `current_draft_id`. `mark_final` is exclusive.
- Claims link to sources by id; high-importance claims verify first;
  `claims_needing_support` is the triage queue.
- Evaluations record the *randomized* frame (`swapped`) plus the
  un-swapped winner, so position bias is auditable.
- Writes are atomic (write + rename); JSONL appends are the only
  append-only surfaces, matching Prime session conventions.
- Subagents share state by inheriting `cwd`. No session-artifact copy is
  authoritative; `writing/` in the workdir is.
- A new prompt in a project directory never wipes state: `project_init`
  refuses when `project.json` exists. A fresh project means a fresh
  directory (or moving the old state dir aside first).
- A completely new topic means a new project, not a wiped one:
  `project_new` archives the current project beside itself as
  `writing.archive.<timestamp>/` and starts fresh. Archives stay ordinary
  readable projects (reopen via `$WRITER_DIR`, or move back). Ledger
  entries never cross topics unless explicitly asked.
