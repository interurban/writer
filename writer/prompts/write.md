---
description: Write a complete technical article autonomously — research, draft, verify, critique, revise as needed.
argument-hint: <brief or objective> [--words N]
---

Write: `$ARGUMENTS`

This is not a pipeline. There is no required sequence of
research → outline → draft → edit. You are the orchestrator: decide what
this piece needs. A simple task may need one draft. A hard one may need
branching, research, critics, verification, and comparison. Do not recurse
to demonstrate recursion — recurse when the piece gets better.

## Setup

1. Parse the request into a working brief. If it reads like a full brief,
   use it; if it is one line, infer audience + constraints and confirm by
   writing them down (not by interrogating the user).
2. `writer.project_init(name, goal)` (or open the existing `writing/`),
   then `writer.brief_set(objective, constraints, label, background)`.
3. `run_id = "run-<date>-<slug>"`; `writer.trace_begin(run_id, task, model)`.
   Record subagents as `{"name": role, "model": selector}` when you spawn
   them. Close with `writer.trace_finish(..., quality=writer.trace_summary())`
   when you select the final draft.

## Capabilities (use what the piece needs)

- Angles: explore 2–3 candidate angles when the brief is open; commit fast
  when it is not.
- Framing (for pieces needing a mental model — explainers, arguments,
  architecture, thought leadership): `/framing` before drafting.
  Propose cheap candidate theses, pairwise-select for clarity and
  truthfulness (never cleverness alone), hand the winner to the writer
  via `writer.framing_brief()`. Skip for reference docs and procedures.
- Research: primary sources first (`research` skill); every consequential
  source goes to `writer.sources_add` with excerpts, never full documents.
- Drafting: `writer.drafts_save(body, reason, model)` — every substantial
  revision is a new `draft-NNN` with `parent=` set. Never overwrite.
- Claims: `writer.claims_extract(draft_id)`, review the candidates, then
  `/verify`. `verified` requires evidence (source ids or exec records);
  otherwise weaken, qualify, or remove the language.
- Executable checks: `writer.exec_check(label, command, claim_id=...)` for
  commands/code samples that can run safely in the kernel sandbox.
- Criticism: spawn a critic per the `editorial-critique` skill recipe
  (diagnose, don't rewrite; different model family when available via
  `writer.models_pick_critic`). The critic returns findings; YOU perform
  the repair as a new revision. Never promote critic prose to canonical.
- Comparison: `writer.evals_compare` + resolve, or `/compare`, before
  declaring a winner. Latest is not best until judged.
- Revision density rule: improve thesis, framing, opening, structure, and
  momentum while preserving substantive technical content. Cut only what
  is redundant, unsupported, or irrelevant — a more readable draft with
  fewer facts, dropped caveats, or vaguer guidance is a regression.
  Check with `writer.claims_coverage(parent, revised)` and the
  revision-regression section of `/compare`.
- Preferences: ask the user when taste decides; `writer.preference_record`.

## Subagents

`handle = await rlm.spawn(prompt, name="<role>", model=<selector?>)`,
then `await rlm.collect(handle, timeout_ms=...)`. Roles and models follow
`writer.models_get()`: writer inherits, critic prefers a different family
if one is listed by `rlm.find_models`, verification prefers reasoning.
Children share `writing/` but must not persist ledger/draft writes —
they return findings; the parent persists (one writer per file).

## Finish

`writer.drafts_mark_final(id)` only when high-importance claims are
`verified` (or the language no longer asserts them) and a comparison
supports the pick — or the user picks. Report: `writer.status_line()`,
verification counts, evals, and the trace. Show progress as activity
states (`writer.activity("researching")`), never chain-of-thought.
