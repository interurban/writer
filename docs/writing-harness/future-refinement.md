# Future refinement (ADR)

## Status

Proposed, not implemented. V0 ships the *evidence* refinement will learn
from (evals + preferences + traces); it does not change `/refine`.

## How `/refine` works today (Prime, unchanged)

Planner reviews the trajectory tail + current harness state and proposes
small edits to supplemental state only (prompt notes, memories, skill
descriptions, subagent specs). The base system prompt is immutable;
history supports rollback; scope is `local` (session) or `global`.

## Where editorial learning plugs in

Scoped lessons, most-specific-wins, with counts before promotion:

```json
{
  "lesson": "Prefer concrete openings over thesis-first openings",
  "scope": "writer:someone",
  "evidenceCount": 7,
  "wins": 6,
  "losses": 1,
  "status": "candidate"
}
```

Proposed scope ladder: `global → writer → organization → publication →
client → project → task`. One correction never becomes a global rule:
`candidate` requires repeated wins in the same scope; promotion to a
broader scope needs wins across distinct narrower scopes; conflicts
resolve to the narrowest applicable lesson.

## Signals (already persisted in V0)

- `evals/evaluations.jsonl`: pairwise wins/losses per criterion.
- `preferences/preferences.jsonl`: human A/B choices + reason tags.
- `traces/runs.jsonl`: which skills/subagents/models produced finals.
- Claim ledger deltas: which verification habits prevent `failed` claims.

## Next step (not this milestone)

A `writer-refine` planner that reads those files, proposes scoped lessons
in the `/refine` edit format, and records them under the writer scope —
reusing `refinement/{planner,executor}` and the harness digest, not a
second learning system.
