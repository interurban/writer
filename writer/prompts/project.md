---
description: Show project status — brief, drafts, claims, evals.
---

Call `writer.project_get()`, `writer.brief_get()`, and
`writer.status_line()`. Render the compact status line plus: goal, audience
label, current/final draft, counts, latest evaluation. This is the same
state the TUI status bar summarizes. Offer next actions (draft, compare,
verify) instead of dumping full bodies.
