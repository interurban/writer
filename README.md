# Writer

A writing-native harness for technical content: persistent project state,
evidence-gated claims, immutable drafts, voice, editorial framing, and a
blind pairwise evaluation loop that measures whether the harness actually
helps at a fixed model.

## What is here

| Path | What it owns |
| --- | --- |
| `skills/writer/` | The Writer skill: the Python API behind `/write`, plus the state store (project, brief, sources, claims, drafts, voice, evals, trace). |
| `skills/technical-writing/` | Craft rules for technical prose: concreteness, density, no filler. |
| `skills/editorial-critique/` | The critic pass that argues against the draft. |
| `skills/technical-verification/` | Verification, gated on evidence rather than assertion. |
| `skills/editorial-framing/` | Competing mental models proposed and selected before drafting. |
| `skills/research/` | Source intake. |
| `skills/voice/` | Voice profile capture and reuse. |
| `writer/prompts/` | Prompt templates: `write`, `drafts`, `sources`, `claims`, `compare`, `verify`, `voice`, `framing`, `model-test`, `new-topic`, `project`, `trace`. |
| `writer/writer` | Interactive launcher and local state/model commands. |
| `benchmarks/technical-writing/` | The evaluation loop: 11 tasks, 2 arms, 7 blind judgment dimensions, economics capture, reports. |
| `docs/writing-harness/` | Architecture, framing, models, and the V1 → V1.2 evaluation write-ups. |

## The idea

Most "improve the output" work changes the model or the prompt. This changes
the *process*: claims are extracted and must be backed by sources, drafts are
immutable, framings compete before a word is written, and revisions record
what was lost. The benchmark exists to check that this earns its cost — see
`docs/writing-harness/v1-2.md`.

## Evaluation loop

```sh
# validate the loop without any model
python3 benchmarks/technical-writing/run.py selftest

# check the author and judge models answer before spending a run
python3 benchmarks/technical-writing/run.py check-models \
    --model <author> --judge-model <judge>

# 11 tasks x 2 arms x 3 runs, then blind judging, then the report
python3 benchmarks/technical-writing/run.py experiment \
    --model <author> --judge-model <judge> --thinking medium --runs 3
python3 benchmarks/technical-writing/run.py judge --experiment <exp-id> \
    --judge-model <judge>
python3 benchmarks/technical-writing/run.py summarize --experiment <exp-id>
```

Judgments are blind and evidence-backed: a verdict must quote the article it
claims is better, and the quote is validated against the raw text. An
invalid verdict gets one retry; a second invalid verdict is recorded as
invalid rather than turned into a win or a tie.

## License

MIT — Copyright (c) 2025-2026 Prime Intellect Ltd. See [LICENSE](LICENSE) and
[NOTICE](NOTICE).
