# Editorial framing

The observed quality failure was: technically dense, fully sourced,
editorially flat — no thesis, inventory structure, forgettable opening.
The failure happens before prose (angle/thesis/architecture), so the fix
is idea selection, not a polish pass. No "humanizer" exists anywhere in
this harness by explicit decision.

## Flow

1. `/framing` (or the `editorial-framing` skill): 2–4 cheap candidate
   framings (`writer.framings_propose`), each a thesis + why-it-matters +
   contrast + mental model + risk. No full drafts at this stage.
2. Compare candidate pitches with the existing pairwise machinery on
   clarity, usefulness, distinctiveness, truthfulness, explanatory power,
   and organizing ability. Memorable-but-misleading loses; the reasoning
   says why. Persist via `writer.framings_select`.
3. Hand off with `writer.framing_brief()`: thesis, payoff, model, and a
   do-not-lose list drawn from high-importance ledger claims. The writer
   owns the prose — wording is never mandated.

## Density preservation

Revision objective: improve thesis, framing, opening, structure, and
momentum while preserving substantive content; cut only the redundant,
unsupported, or irrelevant. `/compare` carries a revision-regression
section (framing, specificity, credibility, density) backed by the
mechanical `writer.claims_coverage(parent, revised)` triage. The harness
can conclude "more engaging but materially less useful" and revert —
latest is never assumed best.

## Benchmarking

The `framing` pairwise criterion ("stronger and more useful mental
model?") sits alongside the other six dimensions, never merged into a
score. The `jev-explainer` task pins the regression case: the pre-fix
draft ships as a fixture, and new output must beat it on framing while
matching it on specificity/credibility/density.
