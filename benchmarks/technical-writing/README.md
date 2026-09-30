# Technical-writing benchmark

Tests the V1 hypothesis: *given the same frontier model, does Writer's
harness produce better technical writing than vanilla Prime Agent?*

V1.1 adds the measurement loop: N×2-arm orchestration, frozen inputs,
telemetry capture, independent blind judging (model + human), summaries,
and CSV export. No numeric quality scores; no writing capabilities here.

## Tasks

11 tasks under `tasks/<name>/task.md` (brief + audience + constraints +
sources + hard requirements): `explainer`, `tutorial`, `architecture`,
`argument`, `product-education`, `comparison`, `editing`, `shortening`,
`complex-concept`, `thesis`, `jev-explainer`.

## Full experiment

```bash
python3 run.py experiment --model <selector> --runs 3 \
  --judge-model <other-family-selector> [--tasks explainer,tutorial] [--seed 7]
python3 run.py judge --experiment <id> --judge-model <selector>
python3 run.py human-judge --experiment <id> --task <t> --judge-name <you>
python3 run.py summarize --experiment <id>
```

Default: 11 tasks × 2 arms × 3 runs = 66 artifacts under
`experiments/<id>/runs/<task>/<arm>/run-<k>/`
(`prompt.md`, `events.jsonl`, `output.md`, `meta.json`, `economics.json`,
`stderr.txt`), plus `manifest.json` (commit, versions, models, seeds,
input hashes) and isolated `prime-home/` + `sessions/`.

## Input freeze (what each arm receives)

- vanilla: `tasks/<t>/task.md` verbatim + one neutral line
  ("Write the article. Your final message is the article text.").
  No Writer skills, templates, or editorial guidance.
- writer: `writer/prompts/write.md` with `$ARGUMENTS` replaced by
  `task.md` verbatim, plus `--skill` × 6 and `--prompt-template`.
- both: same `--model`, `--thinking`, timeout, fresh workdir, isolated
  `PRIME_AGENT_CODING_AGENT_DIR` / `PRIME_AGENT_SESSION_DIR`.
- `manifest.json` pins sha256 of every input file, so the freeze is
  auditable after the fact.

## Judging

- Pairs are run-index-aligned (vanilla run k ↔ Writer run k): 33 pairs by
  default. A/B order re-randomized per comparison from the seed stream;
  provenance sealed to `judge-state/evals/blind.jsonl`.
- Seven dimensions judged independently (`continuation usefulness
  specificity credibility distinctiveness brief framing`); judge sees only the two
  texts + the brief + one criterion — never labels, models, costs, paths.
- Judge model is independent and should be a different family
  (family = opaque provider segment; mismatches warn, never block).
- Verdicts are `{winner: A|B|tie, reasoning, confidence, tags}`; tags come
  from the failure taxonomy (extensible). Unparseable verdicts are recorded
  as errors — re-run the pair, never fabricate.
- Human flow (`human-judge`) shows ARTICLE A/B, collects the same seven
  dims + tags + notes, reveals mapping only after submit. Human and model
  judgments persist separately (`judgments/human/`, `judgments/model/`).

## Telemetry: what is captured vs unavailable

Captured per run: wall-clock, exit code, token sums from `--mode json`
`message_end` usage (session-file fallback), subagent attributions,
session-artifact subagent dirs, word counts, length-target fit, citation
URL lists, and (writer arm only) ledger metrics from the run workdir
`writing/`. Cost only if a usage object carries it — otherwise null.
Unavailable and nulled: per-call model breakdowns beyond attributions,
judge-call tokens (wall-clock only), broken-citation verdicts (URLs are
listed, not fetched). Null means "Prime did not expose it".

## Single-task workflow (V1, unchanged)

`run --task/--arm`, `blind`, `resolve`, `tally`, `status` work as before
under `runs/<task>/<arm>/`. `selftest` validates the whole loop without
models (blind both parities, verdict parsing, economics parsing, freeze
hashes, tally, prompt blindness).
