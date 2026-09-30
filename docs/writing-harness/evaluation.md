# Evaluation

V0 deliberately has no 1–10 "human writing" scores and no giant rubric.
The primitive is **pairwise comparison** against one criterion question:

```text
Which opening is more likely to make an experienced developer continue reading?
→ {winner: A | B | tie, reasoning, confidence?}
```

## How it works

1. Caller loads two texts (usually `drafts_get` bodies).
2. `evals_compare` (Python) / `PairwiseComparison::randomize` (Rust)
   flips A/B internally (seeded RNG; production passes fresh entropy).
3. The judge — orchestrating model, critic subagent (ideally a different
   model family from the writer), or human — picks first/second/tie with
   reasoning.
4. `evals_resolve` maps the frame winner back to caller ids and appends
   the result to `evals/evaluations.jsonl` with the `swapped` flag.

## Blind comparison (V1)

For benchmark outputs, provenance labels (`writer`, `vanilla`, draft ids)
are sealed at presentation time (`blind_present` → `evals/blind.jsonl`)
and unsealed only in `blind_resolve`, which persists a `pairwise-blind`
evaluation with `subjects=[label_a, label_b]`. `blind_tally` counts
per-label wins. The seven standard benchmark questions are listed by
`writer.standard_criteria()`. Judge blind; resolve; tally — never a score.

## Human preferences

`preference_record({draftA, draftB, winner, reasons[]})` persists
observations like `more-interesting / better-rhythm / more-specific` to
`preferences/preferences.jsonl`. No ML in V0; the file is the dataset the
future refinement scope (`writer:<name>`) will learn from.

## Future evaluators (interfaces reserved)

`Evaluator { name, evaluate(input) }` in Rust; same shape planned for
Python. Candidate kinds: `factual technical source-support voice
specificity engagement originality corpus-diversity`. Each should stay a
small, single-criterion judge with persisted reasoning — never a scalar
that pretends to measure "quality".
