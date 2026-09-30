# Task: jev-explainer — framing with density

## Brief

Write a ~300-word technical explainer of Jev (TypeSafe AI's "System One"
model: typed decisions over state, not prose generation) for experienced
developers who have never used it. About 280–330 words.

## Audience

Experienced software engineers. They understand APIs, JSON, thresholds,
and application boundaries. They have not used Jev or TypeSafe AI.

## Constraints

- About 280–330 words (the observed failure ran at ~300).
- Lead with a memorable architectural framing, not a feature tour: the
  reader should leave with one mental model, statable in a sentence.
- No generic scene-setting intro; no "In today's rapidly evolving" opening.
- Do not mimic any known article's wording — clarity must be your own.

## Sources

No supplied material. Primary sources expected (TypeSafe AI docs).

## Hard requirements (all must survive in the text)

- Typed decision behavior: state plus Choice / Score / Noul questions.
- Probability distributions (and derived confidence) in responses.
- Confidence handling: what confidence means and does not mean.
- Parallel, independent evaluation of questions sharing one state.
- Limitations: text-only input; closed answer spaces hide bad taxonomies.
- Calibration guidance: thresholds from representative data and
  error consequence.
- Versioning caution: moving aliases (e.g. `jev-latest`) vs pinned versions.

## Regression reference

`reference-writer-draft-001.md` is a pre-fix harness output for this
brief: technically dense and fully sourced, but editorially flat (no
thesis, inventory structure, forgettable opening). New harness output
should match or exceed its technical content while beating it on
framing — verified by the `framing` pairwise criterion plus the
specificity/credibility/density regression check.
