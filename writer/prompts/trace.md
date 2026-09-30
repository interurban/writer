---
description: Show the current run trace — models, skills, subagents, drafts.
---

Call `writer.evals_list()` (latest evaluations) and summarize the run:
task, model, skills invoked (`rlm` subagents with per-role models), drafts
created, final pick, elapsed time. Prime's own daemon/session tracing
remains the record for tokens/cost; this is the writing-level summary.
Persist run boundaries with `writer.trace_begin` / `writer.trace_finish`.
