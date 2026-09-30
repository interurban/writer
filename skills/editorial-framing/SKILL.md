---
name: editorial-framing
description: Find the strongest conceptual framing before drafting — candidate theses, mental models, contrasts. Use for explainers, arguments, architecture pieces, and anything needing a reader mental model; skip for reference docs and procedures.
---

# Editorial framing

Most flat technical writing fails before a single sentence is drafted: no
angle was ever selected. This skill finds the idea first and produces
candidate framings — not prose.

## When to invoke

Consider it for explainers, technical arguments, architecture pieces,
thought leadership, product/developer education, and comparisons — any
piece where the reader needs a useful mental model. Skip it for reference
documentation and step-by-step procedures, where completeness beats angle.

## Framing questions

- What is the actual idea here, in one sentence?
- What changes for the reader if they understand this?
- What is the most useful contrast? (before/after, X-vs-Y, boundary)
- What misconception does this correct?
- What architectural consequence matters?
- What is the shortest memorable mental model?
- Is there a strong abstraction boundary to name?
- What would make an experienced engineer say "oh, that's the point"?

## Candidates (cheap: 2–4, a paragraph each, no full drafts)

Each candidate records:

```text
Thesis:
Why it matters:
Useful contrast:
Possible mental model:
Risk/weakness:
```

Persist with `writer.framings_propose([...])`. Then compare candidates
with the existing pairwise machinery (`writer.evals_compare` on the
candidate pitches) against: conceptual clarity, usefulness to the
audience, distinctiveness, technical truthfulness, explanatory power,
ability to organize the rest of the article. Select with
`writer.framings_select(...)` — never for cleverness alone. A framing
that is memorable but technically misleading must lose; record why in
the selection reasoning.

## Handoff

Hand the winner to the writer via `writer.framing_brief()`: core thesis,
reader payoff, mental model, and an explicit do-not-lose list (facts,
caveats, limitations). The writer owns the prose — never require the
thesis wording to appear literally.

## Non-goals (explicit)

This is editorial judgment, not surface texture. Do NOT add: AI-detector
gaming, sentence-randomness passes, fake imperfections, synonym
replacement, forced contractions, forced humor, forced rhetorical
questions, or any other style noise. If a candidate needs quirk to be
memorable, it is a weak candidate.
