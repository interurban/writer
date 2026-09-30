---
description: Compare two drafts pairwise against one criterion.
argument-hint: <draft-a> <draft-b> [criterion]
---

Compare draft `$1` vs draft `$2` (criterion: `$ARGUMENTS`, default: "Which
better serves an experienced developer: specificity, interest, credibility?").

1. Load both bodies with `writer.drafts_get`.
2. Build a randomized frame: `writer.evals_compare(a, b, criterion, subjects=[a_id, b_id], seed=<random>)`.
3. Judge the *frame* (first/second/tie) with reasoning; prefer the draft
   that establishes concrete technical tension sooner and avoids generic
   openings. Consider a different-model critic subagent for distance.
4. Persist with `writer.evals_resolve` and ask the user for their own
   preference (`writer.preference_record`), rendering:

```text
Compare drafts

A: <id-a>
B: <id-b>

Criterion:
<criterion>

Agent preference: <A/B/tie>

Reason:
<reasoning>

Your preference?

[A] Draft A
[B] Draft B
[T] Tie
```

## Revision regression (parent vs revision)

When B revises A, judge four dimensions independently — framing,
specificity, credibility, density — and conclude per dimension. Watch
for: lost technical facts, removed caveats, weaker operational guidance,
unsupported simplification. The harness must be able to conclude "more
engaging but materially less useful" and revert (`writer.drafts_make_current`
or mark the parent final). Run `writer.claims_coverage(a, b)` as
mechanical triage first; it flags possibly-lost claims, it does not
decide. Never assume latest is best.
