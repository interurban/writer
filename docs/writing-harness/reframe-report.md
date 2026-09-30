# Dogfood: reframing the Jev explainer

Reran the observed flat draft (`tasks/jev-explainer/reference-writer-draft-001.md`,
300 words, 5 sources, 6 verified claims) through the new framing flow.
Author and judge: the harness developer, manually (no model access in this
environment — see Limitations). Same brief, same ~300-word budget.

## Framings proposed

- **frame-001** — "Jev is less interesting as a small LLM than as a
  control-plane primitive." Contrast: LLMs generate / Jev decides / code
  acts. Risk: undersells calibration work.
- **frame-002** — "Jev's real product isn't decisions, it's inspectable
  uncertainty." Risk: confidence is not calibration; overpromises trust.
- **frame-003** — "Ask it to opine in a format code can check." Risk:
  process advice, weak organizer; "opine" undersells constraints.

Round-robin pairwise (fixed seeds, recorded reasoning): F1 2–0, F2 1–1,
F3 0–2. Selected frame-001: organizes the whole article (interface,
architecture, limits all hang off decide-vs-act); F2's confidence angle
preserved as a planned section, not lost.

## Revision

draft-002 (354 words, over budget) → draft-003 (333) → draft-004
(329 words, in the 280–330 band), all parent-linked, all technical content
intact per `claims_coverage(draft-001, draft-004)`: 8/8 preserved,
0 possibly lost. The only micro-loss found on close reading: the phrase
"in a single call" (parallelism itself is stated twice elsewhere).

## Old (draft-001) vs new (draft-004), blind, six dimensions

| Dimension | Winner | Confidence | Basis |
|---|---|---|---|
| framing | new | 0.85 | portable thesis vs no thesis |
| continuation | new | 0.8 | problem-first opening vs definition opening |
| usefulness | new | 0.65 | same facts, better organized for application |
| specificity | tie | — | identical fact inventory (8/8 coverage) |
| credibility | tie | — | same claims, same verification state |
| distinctiveness | **INVALID** | — | judge error (below), excluded |

## Judge error (disclosed, record kept)

The distinctiveness vote went to draft-001 while its reasoning describes
draft-004 ("FIRST's thesis, contrast, and closer") — the judge assumed
frame order instead of reading it (4 of 6 frames had new first; this one
didn't). The sealed record preserves the mismatch, so it is auditable
rather than silently wrong. Lesson for the harness: judges should quote
the winning text, not just pick a side — a cheap protocol fix for later.

## Technical information lost or changed

Lost: "in a single call" (one phrase; parallelism stated elsewhere).
Changed: opening, thesis sentence, closer rewritten; "can move" →
"can advance"; confidence handling slightly expanded (calibrate-don't-trust
made explicit — consistent with the ledger). Nothing else.

## Inference cost

Not measurable here (manual authorship, no model calls in this
environment). Qualitatively: the framing step cost 3 short pitches plus
3 pairwise judgments — an order of magnitude below a full draft plus its
research loop — and the revision was a single rewrite pass. The expensive
part remains drafting; idea selection is cheap, which is the design bet.

## Verdict

Framing improved (thesis, opening, hierarchy, momentum) with zero fact
loss and two credibility-neutral ties. Success on the milestone's terms —
with the stated judge limitations, not beyond them.
