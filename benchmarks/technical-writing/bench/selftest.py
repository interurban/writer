"""No-model validation for the V1.2 evaluation loop.

Exercises: blind resolution under both parities, economics parsing on
synthetic telemetry, manifest hashing, length-target coverage on all task
fixtures, tally/summarize, per-comparison seeds, and the ledger directory
lookup. The judging evidence contract lives in `selftest_judging`.
Run: `python run.py selftest`. Exit non-zero on any failure.
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

from . import common
from . import economics
from . import judge
from . import report


def check(name: str, condition: bool, detail: str = "") -> None:
    print(("PASS " if condition else "FAIL ") + name
          + (f" — {detail}" if detail and not condition else ""))
    if not condition:
        raise SystemExit(f"selftest failed: {name} {detail}")


def _writer():
    sys.path.insert(0, str(common.REPO / "skills" / "writer" / "src"))
    import writer

    return writer


def test_blind_both_parities(tmp: Path) -> None:
    writer = _writer()
    root = tmp / "w"
    parities: dict = {}
    for seed in range(64):
        frame = writer.blind_present(
            "writer text", "vanilla text", "writer", "vanilla",
            "Which is more specific?", seed=seed,
            frame_id=f"s-{seed}", root=root)
        mapping = [json.loads(line) for line in
                   (root / "evals" / "blind.jsonl").read_text().splitlines()
                   if json.loads(line)["frame_id"] == frame["frame_id"]][0]
        parities[mapping["swapped"]] = (frame, seed)
        if len(parities) == 2:
            break
    check("blind covers both parities", len(parities) == 2)
    for swapped, (frame, seed) in sorted(parities.items()):
        resolved = writer.blind_resolve(
            frame["frame_id"], "first", "concrete sooner", root=root)
        expected = "vanilla" if swapped else "writer"
        check(f"blind resolves swapped={swapped}",
              resolved["winner_label"] == expected,
              f"seed={seed} got {resolved['winner_label']}")
    tally = writer.blind_tally(root=root)
    check("blind tally counts labels",
          tally.get("writer", {}).get("judgments", 0) == 1
          and tally.get("vanilla", {}).get("judgments", 0) == 1, str(tally))


#: A fake `prime-agent` that answers the judge probe from the prompt it is
#: given, so evidence validation and retry are exercised without a model.
def test_economics_parsing(tmp: Path) -> None:
    events = tmp / "events.jsonl"
    events.write_text("\n".join([
        json.dumps({"type": "session", "id": "sess-1"}),
        json.dumps({"type": "message_end",
                    "message": {"role": "assistant", "content": "hi",
                                "usage": {"input": 100, "output": 50,
                                          "totalTokens": 160,
                                          "cost": 0.002}}}),
        json.dumps({"type": "turn_end",
                    "message": {"role": "assistant", "content": "hi",
                                "usage": {"input": 100, "output": 50,
                                          "totalTokens": 160}}}),
        json.dumps({"type": "message_end",
                    "message": {"role": "user", "content": "q"}}),
    ]))
    parsed = economics.parse_events(events)
    check("events count once (no turn_end double)",
          parsed["total_tokens"] == 160, str(parsed))
    check("events session id", parsed["session_id"] == "sess-1")
    check("events cost", parsed["cost_usd"] == 0.002)
    session = tmp / "sess-1.jsonl"
    session.write_text("\n".join([
        json.dumps({"message": {"role": "assistant", "usage": {"input": 10,
                                                              "output": 5}}}),
        json.dumps({"child_usage": {"input": 3}, "model": "fam-x/m1"}),
    ]))
    fallback = economics.parse_session_file(session)
    check("session fallback sums (child_usage excluded)",
          fallback["total_tokens"] == 15, str(fallback))
    check("attributions counted", fallback["subagent_attributions"] == 1)
    check("attributed models", fallback["attributed_models"] == ["fam-x/m1"])
    missing = economics.parse_events(tmp / "nope.jsonl")
    check("missing events honest", missing["method"] == "no-events-file"
          and missing["total_tokens"] == 0)


def test_freeze_and_targets() -> None:
    tasks = common.task_names()
    check("eleven tasks", len(tasks) == 11, str(tasks))
    for task in tasks:
        target = common.parse_length_target(common.task_brief(task))
        check(f"length target parses: {task}", target is not None
              and target[0] < target[1], str(target))
        hashes = common.task_input_hashes(task)
        check(f"input hash: {task}", len(hashes["task.md"]) == 64)
    harness = common.harness_hashes()
    check("harness hashes cover write+6 skills", len(harness) == 7,
          str(sorted(harness)))
    check("seven dims, no score", len(common.DIMENSIONS) == 7)
    check("tags extensible", len(common.FAILURE_TAGS) >= 10)


def test_seeds_and_tally(tmp: Path) -> None:
    manifest = {"base_seed": 42, "experiment_id": "selftest"}
    from .experiment import pair_seed

    seeds = {pair_seed(manifest, "explainer", 1, dim)
             for dim, _ in common.DIMENSIONS}
    check("per-comparison seeds independent", len(seeds) == len(common.DIMENSIONS))
    check("seeds deterministic",
          pair_seed(manifest, "explainer", 1, "brief") == pair_seed(
              manifest, "explainer", 1, "brief"))
    exp = tmp / "exp"
    (exp / "judgments" / "model" / "explainer" / "pair-1").mkdir(parents=True)
    (exp / "judgments" / "model" / "explainer" / "pair-1" / "brief.json").write_text(
        json.dumps({"task": "explainer", "pair": 1, "dim": "brief",
                    "winner_label": "writer", "judge_kind": "model",
                    "family_match": False}))
    summary = report.summarize_judgments(
        report.load_model_judgments(exp))
    check("tally by dim", summary["by_dim"]["brief"]["writer"] == 1)
    check("tally by task", summary["by_task"]["explainer"]["writer"] == 1)
    check("tally by category",
          summary["by_category"]["explainers"]["writer"] == 1)
    econ = report.summarize_economics([
        {"arm": "vanilla", "total_tokens": 100, "cost_usd": 0.01,
         "elapsed_s": 10.0, "output_words": 500, "drafts": None,
         "subagent_attributions": None},
        {"arm": "vanilla", "total_tokens": 300, "cost_usd": None,
         "elapsed_s": 30.0, "output_words": 700, "drafts": None,
         "subagent_attributions": None},
        {"arm": "writer", "total_tokens": 400, "cost_usd": 0.04,
         "elapsed_s": 60.0, "output_words": 600, "drafts": 3,
         "subagent_attributions": 1},
    ])
    check("median tokens", econ["arms"]["vanilla"]["median_total_tokens"] == 200)
    check("null cost median", econ["arms"]["vanilla"]["median_cost_usd"] == 0.01)
    check("token ratio",
          econ["ratios"]["writer_over_vanilla_total_tokens"] == 2.0)
    check("time ratio",
          econ["ratios"]["writer_over_vanilla_elapsed_s"] == 3.0)


def test_missing_output_length_null(tmp: Path) -> None:
    from . import experiment as exp_mod

    run_dir = tmp / "run"
    run_dir.mkdir()
    (run_dir / "output.md").write_text("")
    path = exp_mod.collect_economics(
        "exp-synth", tmp, run_dir, "editing", "vanilla", 1,
        {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0,
         "cost_usd": None, "method": "events-no-usage",
         "assistant_messages": 0, "session_id": None},
        tmp / "sessions", run_dir / "workdir",
        0.0, 1, False, "missing")
    import json

    record = json.loads(path.read_text())
    check("missing output is null, not false",
          record["length_in_range"] is None, str(record["length_in_range"]))
    check("failed-run economics honest",
          record["total_tokens"] == 0 and record["cost_usd"] is None
          and record["exit"] == 1)


def test_judge_prompt_blindness() -> None:
    prompt = judge.judge_prompt("AAA", "BBB", "brief text",
                                "Which is better?")
    for leak in ("writer", "vanilla", "harness", "tokens", "cost",
                 "output.md", ".writer", "writing/"):
        check(f"judge prompt hides {leak!r}", leak not in prompt.lower())
    check("judge prompt has both texts",
          "AAA" in prompt and "BBB" in prompt)


def test_writer_metrics_dir_lookup(tmp: Path) -> None:
    from . import economics as econ

    new = tmp / "new-work"
    (new / "writing").mkdir(parents=True)
    (new / "writing" / "project.json").write_text("{}")
    (new / "writing" / "sources").mkdir()
    (new / "writing" / "sources" / "index.json").write_text("[]")
    (new / "writing" / "claims").mkdir()
    (new / "writing" / "claims" / "ledger.json").write_text("[]")
    (new / "writing" / "drafts").mkdir()
    (new / "writing" / "drafts" / "index.json").write_text("[]")
    metrics = econ.writer_metrics(new)
    check("metrics read from writing/", metrics["method"] == "writer-ledger",
          metrics["method"])

    legacy = tmp / "old-work"
    (legacy / ".writer").mkdir(parents=True)
    (legacy / ".writer" / "project.json").write_text("{}")
    for sub in ("sources", "claims", "drafts"):
        (legacy / ".writer" / sub).mkdir()
        name = {"sources": "index.json", "claims": "ledger.json",
                "drafts": "index.json"}[sub]
        (legacy / ".writer" / sub / name).write_text("[]")
    metrics = econ.writer_metrics(legacy)
    check("metrics fall back to legacy .writer/",
          metrics["method"] == "writer-ledger", metrics["method"])

    empty = tmp / "empty-work"
    empty.mkdir()
    check("metrics honest when absent",
          econ.writer_metrics(empty)["method"] == "no-writer-state")


def main() -> None:
    # Imported here, not at module scope: selftest_judging reuses `check`.
    from . import selftest_judging

    with tempfile.TemporaryDirectory(prefix="bench-selftest-") as tmpdir:
        tmp = Path(tmpdir)
        test_blind_both_parities(tmp)
        test_economics_parsing(tmp)
        test_freeze_and_targets()
        test_seeds_and_tally(tmp)
        test_missing_output_length_null(tmp)
        test_writer_metrics_dir_lookup(tmp)
        test_judge_prompt_blindness()
        selftest_judging.run_all(tmp)
    print("selftest: all checks passed")


if __name__ == "__main__":
    main()
