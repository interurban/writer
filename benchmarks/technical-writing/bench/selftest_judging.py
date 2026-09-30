"""No-model validation for the V1.2 judging evidence contract.

Owns the checks that a verdict must be earned: mandatory verbatim evidence,
validation against the raw candidate texts, reasoning-contradiction
warnings, the single retry with fresh A/B randomization, refusal to force a
winner or repair identity, agreement counting, and the reproducibility
capture. `selftest` calls into this module.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from . import common
from . import judge
from . import report
from .selftest import check


FAKE_JUDGE = '''#!/usr/bin/env python3
import json, os, sys
from pathlib import Path

prompt = sys.argv[sys.argv.index("-p") + 1]
marker = Path(os.environ["FAKE_JUDGE_MODE"])
count = int(marker.read_text()) if marker.exists() else 0
marker.write_text(str(count + 1))
mode = os.environ.get("FAKE_JUDGE_STYLE", "valid")
start = prompt.index("## ARTICLE A") + len("## ARTICLE A")
end = prompt.index("## ARTICLE B")
body_a = prompt[start:end].strip()
if mode == "invalid-first" and count == 0:
    print(json.dumps({"winner": "A", "reasoning": "concrete opener",
                      "confidence": 0.7, "tags": []}))
    sys.exit(0)
if mode == "always-invalid":
    print(json.dumps({"winner": "A", "reasoning": "concrete opener",
                      "evidence": "a sentence that appears in no article",
                      "confidence": 0.7, "tags": []}))
    sys.exit(0)
reasoning = ("Article B opens generically and hides its working"
             if mode == "contradiction" else
             "Article A leads with a real number")
print(json.dumps({"winner": "A", "reasoning": reasoning,
                  "evidence": body_a[:40], "confidence": 0.7,
                  "tags": ["weak-angle"]}))
'''

TEXT_WRITER = ("Alpha leads with a concrete failure mode and a real number, "
               "then shows the fix.")
TEXT_VANILLA = "Beta opens generically and never shows its working."


def _fake_judge(tmp: Path, style: str) -> tuple[str, Path]:
    prime = tmp / f"prime-{style}"
    prime.write_text(FAKE_JUDGE)
    prime.chmod(0o755)
    marker = tmp / f"marker-{style}"
    previous_env = dict(os.environ)
    os.environ["FAKE_JUDGE_MODE"] = str(marker)
    os.environ["FAKE_JUDGE_STYLE"] = style
    return str(prime), marker


def _judge_fixture(tmp: Path, name: str) -> tuple[Path, dict]:
    exp_dir = tmp / name
    (exp_dir / "runs" / "explainer").mkdir(parents=True)
    manifest = {"experiment_id": name, "base_seed": 42,
                "author_model": "openai/gpt-x", "author_family": "openai",
                "judge_model": "anthropic/claude-y"}
    return exp_dir, manifest


def test_judge_identity_in_both_parities(tmp: Path) -> None:
    """Winner label must follow the sealed frame, never the presented slot."""
    exp_dir, manifest = _judge_fixture(tmp, "parity")
    seen = set()
    for base_seed in range(64):
        manifest["base_seed"] = base_seed
        prime, marker = _fake_judge(tmp, "valid")
        if marker.exists():
            marker.unlink()
        record = judge.judge_pair(prime, exp_dir, manifest, "explainer", 1,
                                  "brief", "Which better fulfills the brief?",
                                  TEXT_WRITER, TEXT_VANILLA, "anthropic/y", 30)
        if record.get("invalid"):
            check("fake judge verdict is valid", False, str(record))
        presented_a = record["presented"]["A"]
        seen.add(presented_a)
        check(f"identity resolved (A={presented_a})",
              record["winner_label"] == presented_a
              and record["winner"] == "A",
              f"swapped={record['swapped']} got {record['winner_label']}")
        if len(seen) == 2:
            break
    check("both A/B parities exercised", seen == {"writer", "vanilla"},
          str(seen))
    for name, value in (("FAKE_JUDGE_MODE", None), ("FAKE_JUDGE_STYLE", None)):
        if value is None:
            os.environ.pop(name, None)


def test_judge_retry_then_valid(tmp: Path) -> None:
    exp_dir, manifest = _judge_fixture(tmp, "retry")
    prime, marker = _fake_judge(tmp, "invalid-first")
    if marker.exists():
        marker.unlink()
    record = judge.judge_pair(prime, exp_dir, manifest, "explainer", 1,
                              "brief", "Which is more useful?", TEXT_WRITER,
                              TEXT_VANILLA, "anthropic/y", 30)
    check("invalid first verdict triggers exactly one retry",
          record["attempts_used"] == judge.MAX_JUDGE_ATTEMPTS
          and record["retried"] and not record["invalid"],
          str(record["attempts_used"]))
    first, second = record["attempts"]
    check("first attempt is recorded as invalid",
          not first["valid"] and "evidence" in first["error"])
    check("retry re-randomizes A/B with a new frame",
          second["frame_id"] != first["frame_id"]
          and second["seed"] != first["seed"],
          f"{first['frame_id']} vs {second['frame_id']}")
    check("retry verdict wins with a winner label",
          record["winner_label"] == record["presented"]["A"])
    os.environ.pop("FAKE_JUDGE_MODE", None)
    os.environ.pop("FAKE_JUDGE_STYLE", None)


def test_judge_invalid_after_retry(tmp: Path) -> None:
    """Two invalid verdicts stay invalid: no forced winner, no tie."""
    exp_dir, manifest = _judge_fixture(tmp, "invalid")
    prime, marker = _fake_judge(tmp, "always-invalid")
    if marker.exists():
        marker.unlink()
    record = judge.judge_pair(prime, exp_dir, manifest, "explainer", 1,
                              "credibility", "Which is more credible?",
                              TEXT_WRITER, TEXT_VANILLA, "anthropic/y", 30)
    check("unfixable verdict stays invalid", record["invalid"]
          and record["winner_label"] is None and record["winner"] is None,
          str(record.get("error")))
    check("both invalid attempts are persisted",
          len(record["attempts"]) == judge.MAX_JUDGE_ATTEMPTS
          and all(not a["valid"] for a in record["attempts"]))
    summary = report.summarize_judgments(report.load_model_judgments(exp_dir))
    check("invalid verdicts are never counted as ties",
          not any(counts["tie"] for counts in summary["by_dim"].values()),
          str(summary["by_dim"]))
    quality = report.summarize_quality(report.load_all_model_judgments(
        exp_dir))
    check("invalid verdict is reported, not hidden",
          quality["invalid"] == 1 and quality["retried"] == 1
          and quality["invalid_reasons"], str(quality["invalid_reasons"]))
    os.environ.pop("FAKE_JUDGE_MODE", None)
    os.environ.pop("FAKE_JUDGE_STYLE", None)


def test_judge_reasoning_conflict_recorded(tmp: Path) -> None:
    exp_dir, manifest = _judge_fixture(tmp, "conflict")
    prime, marker = _fake_judge(tmp, "contradiction")
    if marker.exists():
        marker.unlink()
    record = judge.judge_pair(prime, exp_dir, manifest, "explainer", 1,
                              "framing", "Which frames the subject better?",
                              TEXT_WRITER, TEXT_VANILLA, "anthropic/y", 30)
    check("reasoning contradiction is a warning, not a rejection",
          not record["invalid"] and record.get("warnings"),
          str(record.get("warnings")))
    check("warning names the conflict",
          any("article B" in w for w in record["warnings"]),
          str(record["warnings"]))
    os.environ.pop("FAKE_JUDGE_MODE", None)
    os.environ.pop("FAKE_JUDGE_STYLE", None)


def test_jsonl_export_keeps_invalid(tmp: Path) -> None:
    exp_dir = tmp / "jsonl"
    exp_dir.mkdir()
    records = [{"experiment_id": "e", "task": "explainer", "pair": 1,
                "dim": "brief", "judge_kind": "model",
                "judge_model": "anthropic/y", "invalid": False,
                "retried": True, "attempts_used": 2, "winner": "A",
                "winner_label": "writer", "evidence": "quoted span",
                "evidence_matched_side": "A", "error": None,
                "warnings": [], "attempts": [
                    {"attempt": 1, "frame_id": "f1", "valid": False,
                     "error": "judge verdict has no evidence span"},
                    {"attempt": 2, "frame_id": "f2", "valid": True,
                     "winner": "A", "error": None,
                     "evidence": "quoted span"}]},
               {"experiment_id": "e", "task": "explainer", "pair": 2,
                "dim": "brief", "judge_kind": "model",
                "judge_model": "anthropic/y", "invalid": True,
                "retried": True, "attempts_used": 2, "winner": None,
                "winner_label": None, "error": "evidence not found",
                "warnings": [], "attempts": [
                    {"attempt": 1, "frame_id": "f3", "valid": False,
                     "error": "no JSON object in judge output"},
                    {"attempt": 2, "frame_id": "f4", "valid": False,
                     "error": "evidence not found"}]}]
    path = report.write_judgments_jsonl(exp_dir, records)
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    check("jsonl has one row per attempt", len(rows) == 4, str(len(rows)))
    check("jsonl keeps rejected attempts",
          sum(1 for r in rows if not r["attempt_valid"]) == 3
          and any(r["invalid"] for r in rows))


def test_agreement_table() -> None:
    model = [{"task": "explainer", "pair": 1, "dim": "usefulness",
              "judge_model": "j", "winner_label": "writer"},
             {"task": "explainer", "pair": 2, "dim": "usefulness",
              "judge_model": "j", "winner_label": "vanilla"},
             {"task": "explainer", "pair": 3, "dim": "usefulness",
              "judge_model": "j", "winner_label": "writer"}]
    human = [{"task": "explainer", "pair": 1, "dim": "usefulness",
              "judge_name": "ann", "winner_label": "writer"},
             {"task": "explainer", "pair": 2, "dim": "usefulness",
              "judge_name": "ann", "winner_label": "writer"},
             {"task": "explainer", "pair": 4, "dim": "continuation",
              "judge_name": "ann", "winner_label": "writer"}]
    table = report.agreement_table(model, human)
    entry = table["usefulness"]
    check("agreement counted on shared comparisons",
          entry["comparisons"] == 2 and entry["agree"] == 1
          and entry["disagree"] == 1, str(entry))
    check("agreement rate reported", entry["agreement_rate"] == 0.5)
    check("dimensions without overlap are omitted, not zero-filled",
          "continuation" not in table, str(sorted(table)))


def test_manifest_behavior_capture(tmp: Path) -> None:
    from . import experiment as exp

    manifest = exp.build_manifest("exp-beh", ["explainer"], "openai/gpt-x",
                                  "medium", 3, 7, "true", "anthropic/y")
    check("manifest records the behavior freeze",
          manifest["behavior_version"] == common.behavior_version()
          and len(manifest["behavior_version"]) == 16)
    check("behavior hashes cover framing",
          any("framing" in key for key in manifest["behavior_hashes"]),
          str(sorted(manifest["behavior_hashes"])))
    check("manifest states tree state",
          "git_dirty" in manifest and "git_diff_sha256" in manifest)
    path = exp.capture_behavior(tmp / "exp-beh", manifest)
    text = path.read_text()
    check("behavior.md states the freeze",
          manifest["behavior_version"] in text
          and "writer/prompts/write.md" in text)
    if manifest.get("git_dirty"):
        check("dirty tree is disclosed in behavior.md",
              "uncommitted working tree" in text)


def test_human_evidence_contract(tmp: Path, monkeypatch=None) -> None:
    from . import human as human_mod

    answers = iter(["a", "0.9", "1", "",
                    "Alpha leads with a concrete failure mode"])
    import builtins

    original = builtins.input
    builtins.input = lambda _prompt="": next(answers)
    try:
        entry = human_mod._collect_verdict(TEXT_WRITER, TEXT_VANILLA, "ann")
    finally:
        builtins.input = original
    check("human verdict kept when evidence validates",
          entry["winner"] == "A" and not entry.get("invalid")
          and entry["evidence"].startswith("Alpha"), str(entry))
    answers = iter(["b", "", "", "", "Alpha leads with a concrete failure mode",
                    "still not from article B"])
    builtins.input = lambda _prompt="": next(answers)
    try:
        entry = human_mod._collect_verdict(TEXT_WRITER, TEXT_VANILLA, "ann")
    finally:
        builtins.input = original
    check("human verdict rejected when evidence is from the loser",
          entry.get("invalid") and "winner" not in entry, str(entry))
    answers = iter(["skip"])
    builtins.input = lambda _prompt="": next(answers)
    try:
        entry = human_mod._collect_verdict(TEXT_WRITER, TEXT_VANILLA, "ann")
    finally:
        builtins.input = original
    check("skip records an abstention, not a tie",
          entry.get("skipped") and entry.get("winner_label") is None,
          str(entry))



def test_verdict_parsing() -> None:
    verdict = judge.parse_verdict(
        'Intro\n```json\n{"winner": "B", "reasoning": "more specific", '
        '"confidence": 0.8, "tags": ["generic-opening"], '
        '"evidence": "the exact sentence it quoted"}\n```\nOutro')
    check("verdict parses fenced JSON",
          verdict["winner"] == "B" and verdict["confidence"] == 0.8
          and verdict["tags"] == ["generic-opening"]
          and verdict["evidence"] == "the exact sentence it quoted")
    verdict = judge.parse_verdict(
        '{"winner": "tie", "reasoning": "equal", '
        '"evidence": "a shared sentence from either side"}')
    check("verdict parses bare JSON", verdict["winner"] == "tie"
          and verdict["confidence"] is None)
    for bad in ('no json here',
                '{"winner": "C", "reasoning": "x", "evidence": "abcdefghijkl"}',
                '{"winner": "A"}',
                '{"winner": "A", "reasoning": "x"}',
                '{"winner": "A", "reasoning": "x", "evidence": "   "}'):
        try:
            judge.parse_verdict(bad)
        except ValueError:
            continue
        check("verdict rejects invalid", False, bad)
    check("verdict rejects invalid", True)
    check("verdict requires evidence",
          "evidence" in judge.VERDICT_INSTRUCTIONS)


def test_evidence_validation() -> None:
    text_a = "Alpha leads with a concrete failure mode and a real number."
    text_b = "Beta opens generically and never shows its working."
    exact = judge.check_evidence(
        "Alpha leads with a concrete failure mode", "A", text_a, text_b)
    check("evidence in winning article is valid",
          exact["evidence_valid"] and exact["evidence_matched_side"] == "A",
          str(exact))
    wrong = judge.check_evidence(
        "Alpha leads with a concrete failure mode", "B", text_a, text_b)
    check("evidence from the losing article is rejected",
          not wrong["evidence_valid"] and "B" in wrong["evidence_error"],
          str(wrong))
    tie = judge.check_evidence(
        "Beta opens generically", "tie", text_a, text_b)
    check("tie may quote either article", tie["evidence_valid"])
    short = judge.check_evidence("Alpha", "A", text_a, text_b)
    check("trivially short evidence rejected", not short["evidence_valid"])
    long_quote = "x" * (judge.EVIDENCE_MAX_CHARS + 1)
    check("over-long evidence rejected",
          not judge.check_evidence(long_quote, "A", text_a, text_b)[
              "evidence_valid"])
    absent = judge.check_evidence(
        "a sentence that appears in neither article at all", "A",
        text_a, text_b)
    check("fabricated evidence rejected",
          not absent["evidence_valid"] and "neither" in absent["evidence_error"],
          str(absent))
    wrapped = judge.check_evidence(
        "Alpha leads with a concrete\nfailure mode and a real number.",
        "A", text_a, text_b)
    check("re-wrapped evidence matches after normalization",
          wrapped["evidence_valid"], str(wrapped))


def test_reasoning_conflict_warning() -> None:
    conflict = judge.reasoning_conflict(
        "Article B opens generically and never shows its working.", "A")
    check("contradictory reasoning warns", conflict is not None, str(conflict))
    consistent = judge.reasoning_conflict(
        "Article A leads with a real number.", "A")
    check("consistent reasoning is silent", consistent is None)
    both = judge.reasoning_conflict(
        "Article B is tighter, but article A has the better example.", "A")
    check("reasoning mentioning both sides is silent", both is None)
    check("tie never conflicts", judge.reasoning_conflict(
        "Article B is fine, as is A", "tie") is None)




def test_report_renders_invalid_and_exports(tmp: Path) -> None:
    exp_dir = tmp / "report-exp"
    (exp_dir / "judgments" / "model" / "explainer" / "pair-1").mkdir(
        parents=True)
    (exp_dir / "runs" / "explainer" / "writer" / "run-1").mkdir(parents=True)
    manifest = {"experiment_id": "report-exp", "author_model": "openai/x",
                "judge_model": "anthropic/y", "runs_per_arm": 1,
                "tasks": ["explainer"], "git_commit": "abc123",
                "git_dirty": True, "benchmark_version": common.BENCHMARK_VERSION,
                "behavior_version": common.behavior_version()}
    (exp_dir / "manifest.json").write_text(json.dumps(manifest))
    valid = {"experiment_id": "report-exp", "task": "explainer", "pair": 1,
             "dim": "usefulness", "judge_kind": "model",
             "judge_model": "anthropic/y", "author_model": "openai/x",
             "family_match": False, "winner": "A", "winner_label": "writer",
             "confidence": 0.8, "tags": ["weak-angle"],
             "reasoning": "more specific", "evidence": "quoted span here",
             "evidence_matched_side": "A", "invalid": False, "retried": True,
             "attempts_used": 2, "swapped": False, "warnings": [],
             "attempts": [{"attempt": 1, "frame_id": "f1", "valid": False,
                           "error": "judge verdict has no evidence span"}]}
    invalid = {"experiment_id": "report-exp", "task": "explainer", "pair": 1,
               "dim": "credibility", "judge_kind": "model",
               "judge_model": "anthropic/y", "author_model": "openai/x",
               "winner": None, "winner_label": None, "invalid": True,
               "retried": True, "attempts_used": 2,
               "error": "evidence not found in the A article",
               "attempts": []}
    for record in (valid, invalid):
        name = ("usefulness" if record["dim"] == "usefulness" else "credibility")
        (exp_dir / "judgments" / "model" / "explainer" / "pair-1"
         / f"{name}.json").write_text(json.dumps(record))
    (exp_dir / "runs" / "explainer" / "writer" / "run-1" / "economics.json"
     ).write_text(json.dumps({"arm": "writer", "total_tokens": 100,
                              "cost_usd": 0.01, "elapsed_s": 5.0,
                              "output_words": 900, "drafts": 2,
                              "subagent_attributions": 0,
                              "telemetry_method": "events"}))
    path = report.summarize_experiment(exp_dir)
    text = path.read_text()
    check("report counts only validated verdicts",
          "Writer wins: 1" in text and "Vanilla wins: 0" in text)
    check("report discloses invalid comparisons",
          "Invalid comparisons" in text
          and "evidence not found in the A article" in text)
    check("report discloses the dirty tree",
          "uncommitted working tree" in text)
    check("report states the behavior freeze",
          manifest["behavior_version"] in text)
    for name in ("export.csv", "economics.csv", "judgments.jsonl"):
        check(f"export written: {name}", (exp_dir / name).exists())


def run_all(tmp: Path) -> None:
    test_verdict_parsing()
    test_evidence_validation()
    test_reasoning_conflict_warning()
    test_judge_identity_in_both_parities(tmp)
    test_judge_retry_then_valid(tmp)
    test_judge_invalid_after_retry(tmp)
    test_judge_reasoning_conflict_recorded(tmp)
    test_jsonl_export_keeps_invalid(tmp)
    test_agreement_table()
    test_manifest_behavior_capture(tmp)
    test_human_evidence_contract(tmp)
    test_report_renders_invalid_and_exports(tmp)
