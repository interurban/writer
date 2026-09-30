---
description: Archive the current project and start fresh on a new topic.
argument-hint: <new topic or brief>
---

Start a NEW writing project on: `$ARGUMENTS`

Topics never share state. Old briefs, claims, sources, and drafts belong
to the old topic and must not leak into the new one.

1. If a project exists here, `writer.project_new(topic, goal)` — it
   archives the old project beside itself (`writing.archive.<timestamp>/`)
   and starts fresh. Report where the old project went.
2. `writer.brief_set(objective, constraints, label, background)` from the
   request above. If it reads like one line, infer audience + constraints
   and write them down rather than interrogating the user.
3. Confirm: new project name, what was archived (or "nothing to archive"),
   and that claims/sources start empty. Never carry ledger entries across
   topics unless the user explicitly asks.
