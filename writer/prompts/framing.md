---
description: Find the strongest framing before drafting — candidate theses, pairwise selection, writer handoff.
argument-hint: <topic or draft-id>
---

Find the framing first. Do not draft prose until a thesis is selected —
idea selection is cheap, full drafts are expensive.

1. If the argument names a draft, load it (`writer.drafts_get`) and frame
   *its* material. Otherwise frame the topic from the brief.
2. Generate 2–4 candidate framings with `writer.framings_propose` (thesis,
   why it matters, useful contrast, possible mental model, risk/weakness
   each). The `editorial-framing` skill governs what makes a candidate.
3. Compare candidates with the existing pairwise machinery on
   `writer.framing_pitch` texts: conceptual clarity, usefulness to the
   audience, distinctiveness, technical truthfulness, explanatory power,
   ability to organize the article. Memorable-but-misleading loses — say
   so in the reasoning. Persist via `writer.framings_select`.
4. Hand off with `writer.framing_brief()`: the writer gets thesis, payoff,
   mental model, and the do-not-lose list — never verbatim wording
   requirements. The writer still owns the prose.
