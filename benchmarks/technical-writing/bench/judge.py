"""Independent blind model judge: one dimension per call, no harness leaks.

The judge prompt carries ONLY the two anonymized texts, the task brief
(same input both arms received), and one criterion question. Never:
arm labels, harness metadata, cost/tokens, model names, filenames, paths.
A/B order is randomized per comparison from the experiment seed stream.

V1.2 evidence rule: a verdict is only usable when it quotes a verbatim span
from the article it judged better. Validation is authoritative; a
reasoning/winner contradiction is a warning, never a repair. An invalid
first verdict gets exactly one retry with freshly randomized A/B order.
A second invalid verdict stays invalid — no forced winner, no identity
repair.
"""

from __future__ import annotations

import json
import re
import subprocess
import time
from pathlib import Path

from . import common

#: One retry after an invalid first verdict, then the comparison is invalid.
MAX_JUDGE_ATTEMPTS = 2

#: Evidence must be a short quote. Longer means the judge summarized, not
#: pointed, and a full-article echo is not checkable evidence.
EVIDENCE_MIN_CHARS = 12
EVIDENCE_MAX_CHARS = 400

VERDICT_INSTRUCTIONS = """\
Reply with exactly one JSON object and nothing else, using this shape:
{"winner": "A" | "B" | "tie", "evidence": "...", "reasoning": "...",
 "confidence": 0.0-1.0, "tags": ["..."]} where tags is a possibly-empty
list chosen from: generic-opening, overwritten, too-long, too-polished,
weak-angle, weak-structure, factual-problem, too-much-context, repetitive,
boring, poor-examples, over-researched, under-researched, missed-brief
(you may add a new hyphenated tag if none fits; explain it in reasoning).

"evidence" is mandatory: a verbatim span of 12-400 characters copied
character-for-character from the article you judged better (for "tie", a
verbatim span from either article). No ellipses, no paraphrase, no
re-wrapping of line breaks, no added words. A verdict whose evidence cannot
be found in that article is rejected and the comparison is asked again.

Base the verdict ONLY on the two texts and the stated criterion."""


def judge_prompt(text_a: str, text_b: str, brief: str,
                 criterion: str) -> str:
    return (f"You are an expert technical editor judging two anonymized "
            f"articles. You do not know who or what produced either text.\n\n"
            f"## Task brief (identical input given to both authors)\n\n"
            f"{brief}\n\n"
            f"## Criterion\n\n{criterion}\n\n"
            f"## ARTICLE A\n\n{text_a}\n\n"
            f"## ARTICLE B\n\n{text_b}\n\n"
            f"{VERDICT_INSTRUCTIONS}")


def parse_verdict(raw: str) -> dict:
    """Extract the verdict JSON. Raises ValueError when absent/invalid —
    callers record the error, never a fabricated verdict."""
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.S)
    candidate = match.group(1) if match else None
    if candidate is None:
        start = raw.find("{")
        end = raw.rfind("}")
        if start < 0 or end <= start:
            raise ValueError("no JSON object in judge output")
        candidate = raw[start:end + 1]
    try:
        verdict = json.loads(candidate)
    except ValueError as exc:
        raise ValueError(f"judge output is not JSON: {exc}") from exc
    winner = str(verdict.get("winner", "")).strip().lower()
    mapping = {"a": "A", "first": "A", "b": "B", "second": "B", "tie": "tie"}
    if winner not in mapping:
        raise ValueError(f"judge winner must be A, B, or tie, got {winner!r}")
    confidence = verdict.get("confidence")
    if confidence is not None:
        try:
            confidence = max(0.0, min(1.0, float(confidence)))
        except (TypeError, ValueError):
            confidence = None
    tags = verdict.get("tags") or []
    tags = [str(t) for t in tags] if isinstance(tags, list) else []
    reasoning = verdict.get("reasoning")
    if not isinstance(reasoning, str) or not reasoning.strip():
        raise ValueError("judge verdict has no reasoning")
    evidence = verdict.get("evidence")
    if not isinstance(evidence, str) or not evidence.strip():
        raise ValueError("judge verdict has no evidence span")
    return {"winner": mapping[winner], "reasoning": reasoning.strip(),
            "confidence": confidence, "tags": tags, "evidence": evidence.strip()}


def normalize_span(text: str) -> str:
    """Whitespace-insensitive form so markdown re-wrapping still matches."""
    return re.sub(r"\s+", " ", text).strip()


def check_evidence(evidence: str, winner: str, text_a: str,
                   text_b: str) -> dict:
    """Authoritative evidence check against the raw candidate texts.

    Returns `{"evidence_valid", "evidence_matched_side", "evidence_error"}`.
    A tie may quote either article; a win must quote the winning article.
    Whitespace-normalized containment counts as a match, and is reported as
    a `evidence_whitespace_repaired` warning by the caller.
    """
    if not evidence or len(evidence) < EVIDENCE_MIN_CHARS:
        return {"evidence_valid": False, "evidence_matched_side": None,
                "evidence_error": "evidence span too short to be checkable"}
    if len(evidence) > EVIDENCE_MAX_CHARS:
        return {"evidence_valid": False, "evidence_matched_side": None,
                "evidence_error": f"evidence span over {EVIDENCE_MAX_CHARS} "
                                  "characters is a summary, not a span"}
    sides = {"A": "A", "B": "B"}
    if winner in sides:
        targets = [sides[winner]]
    else:
        targets = ["A", "B"]
    quoted = normalize_span(evidence)
    exact = [side for side in targets
             if evidence in {"A": text_a, "B": text_b}[side]]
    if exact:
        return {"evidence_valid": True, "evidence_matched_side": exact[0],
                "evidence_error": None}
    repaired = [side for side in targets
                if quoted in normalize_span({"A": text_a, "B": text_b}[side])]
    if repaired:
        return {"evidence_valid": True, "evidence_matched_side": repaired[0],
                "evidence_error": None}
    in_other = False
    for side, text in (("A", text_a), ("B", text_b)):
        if side in targets:
            continue
        if quoted in normalize_span(text):
            in_other = True
            break
    quoted_side = "the other" if in_other else "neither"
    return {"evidence_valid": False, "evidence_matched_side": None,
            "evidence_error": f"evidence not found in the {winner} article "
                              f"(found in {quoted_side} article or nowhere)"}


def reasoning_conflict(reasoning: str, winner: str) -> str | None:
    """Warning when the reasoning names only the article the judge lost.

    Deliberately conservative: only an explicit single-side mention that
    contradicts the winner counts. Ambiguity stays silent — a warning is
    never grounds to discard a validated verdict.
    """
    text = reasoning.lower()
    if winner not in ("A", "B"):
        return None
    other = "B" if winner == "A" else "A"
    patterns = ("article {}", "candidate {}", "text {}", "side {}",
                "version {}", "option {}", "the first", "the second")
    def mentioned(side: str) -> bool:
        if side == "A":
            own = any(p.format("a") in text for p in patterns)
        else:
            own = any(p.format("b") in text for p in patterns)
        if own:
            return True
        if side == "A":
            return "the first" in text
        return "the second" in text
    if mentioned(other) and not mentioned(winner):
        return (f"reasoning names only article {other} but the winner is "
                f"article {winner}")
    return None


def invoke_judge(prime: str, prompt: str, judge_model: str | None,
                 timeout_s: int) -> tuple[str, float, int]:
    """Run the judge in text mode (short verdict; stdout is the answer)."""
    cmd = [prime, "-p", prompt]
    if judge_model:
        cmd += ["--model", judge_model]
    start = time.time()
    proc = subprocess.run(cmd, capture_output=True, text=True,
                          timeout=timeout_s)
    return (proc.stdout, time.time() - start, proc.returncode)


def judge_pair(prime: str, exp_dir: Path, manifest: dict, task: str,
               pair: int, dim_key: str, criterion: str,
               text_writer: str, text_vanilla: str,
               judge_model: str, timeout_s: int) -> dict:
    """Judge one pair on one dimension; persist the sealed record.

    Attempt 1 uses the V1.1 seed so prior experiments stay comparable; the
    retry uses a distinct seed, so A/B order is re-randomized.
    """
    import sys

    sys.path.insert(0, str(common.REPO / "skills" / "writer" / "src"))
    import writer

    bench_root = exp_dir / "judge-state"
    family_match = (manifest["author_family"] is not None
                    and manifest["author_family"] == common.family_of(judge_model))
    record = {
        "experiment_id": manifest["experiment_id"], "task": task,
        "pair": pair, "dim": dim_key, "criterion": criterion,
        "judge_kind": "model",
        "author_model": manifest["author_model"],
        "author_family": manifest["author_family"],
        "judge_model": judge_model,
        "judge_family": common.family_of(judge_model),
        "family_match": family_match,
        "max_attempts": MAX_JUDGE_ATTEMPTS,
        "attempts": [],
    }
    if family_match:
        record["warning"] = ("judge family matches author family; "
                             "prefer a different-family judge")
    for attempt in range(1, MAX_JUDGE_ATTEMPTS + 1):
        seed = pair_seed(manifest, task, pair,
                         dim_key if attempt == 1 else f"{dim_key}-retry{attempt}")
        frame_id = (f"{task}-p{pair}-{dim_key}" if attempt == 1
                    else f"{task}-p{pair}-{dim_key}-a{attempt}")
        frame_id = _unique_frame_id(bench_root, frame_id)
        frame = writer.blind_present(
            text_writer, text_vanilla, "writer", "vanilla", criterion,
            seed=seed, frame_id=frame_id, root=bench_root)
        # Presented order comes from the sealed frame itself (single source).
        presented_a, presented_b = frame["first"], frame["second"]
        swapped = _sealed_swapped(bench_root, frame["frame_id"])
        prompt = judge_prompt(presented_a, presented_b,
                              common.task_brief(task), criterion)
        raw, elapsed, exit_code = invoke_judge(
            prime, prompt, judge_model, timeout_s)
        entry = {"attempt": attempt, "frame_id": frame["frame_id"],
                 "seed": seed, "swapped": swapped,
                 "presented": {"A": "vanilla" if swapped else "writer",
                               "B": "writer" if swapped else "vanilla"},
                 "judge_elapsed_s": round(elapsed, 1), "judge_exit": exit_code,
                 "judge_raw": raw, "warnings": []}
        verdict = None
        try:
            verdict = parse_verdict(raw)
        except ValueError as exc:
            entry["error"] = str(exc)
        if verdict is not None:
            entry["winner"] = verdict["winner"]
            entry["reasoning"] = verdict["reasoning"]
            entry["confidence"] = verdict["confidence"]
            entry["tags"] = verdict["tags"]
            entry["evidence"] = verdict["evidence"]
            evidence = check_evidence(verdict["evidence"], verdict["winner"],
                                      presented_a, presented_b)
            entry.update(evidence)
            entry["evidence_whitespace_repaired"] = (
                evidence["evidence_valid"]
                and normalize_span(verdict["evidence"]) != verdict["evidence"])
            if not evidence["evidence_valid"]:
                entry["error"] = evidence["evidence_error"]
            conflict = reasoning_conflict(verdict["reasoning"],
                                          verdict["winner"])
            if conflict:
                entry["reasoning_conflict"] = conflict
                entry["warnings"].append(conflict)
        entry["valid"] = "error" not in entry
        record["attempts"].append(entry)
        if entry["valid"]:
            break
    final = record["attempts"][-1]
    record["attempts_used"] = len(record["attempts"])
    record["retried"] = len(record["attempts"]) > 1
    record["invalid"] = not final["valid"]
    record["judge_raw"] = final["judge_raw"]
    record["judge_elapsed_s"] = final["judge_elapsed_s"]
    record["judge_exit"] = final["judge_exit"]
    if record["invalid"]:
        record["error"] = final["error"]
        record["winner"] = None
        record["winner_label"] = None
    else:
        # Map presented A/B back through the sealed frame.
        frame_winner = {"A": "first", "B": "second",
                        "tie": "tie"}[final["winner"]]
        resolved = writer.blind_resolve(
            final["frame_id"], frame_winner, final["reasoning"],
            final["confidence"], root=bench_root)
        record["frame_id"] = final["frame_id"]
        record["seed"] = final["seed"]
        record["swapped"] = final["swapped"]
        record["presented"] = final["presented"]
        record["winner"] = final["winner"]
        record["winner_label"] = resolved["winner_label"]
        record["reasoning"] = final["reasoning"]
        record["confidence"] = final["confidence"]
        record["tags"] = final["tags"]
        record["evidence"] = final["evidence"]
        record["evidence_matched_side"] = final["evidence_matched_side"]
        record["warnings"] = final["warnings"] + (
            ["evidence matched only after whitespace normalization"]
            if final.get("evidence_whitespace_repaired") else [])
    outdir = (exp_dir / "judgments" / "model" / task / f"pair-{pair}")
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / f"{dim_key}.json").write_text(
        json.dumps(record, indent=2) + "\n")
    return record


def _unique_frame_id(bench_root: Path, frame_id: str) -> str:
    """Never reuse a frame id: the sealed log is append-only, and a
    duplicate id would make the mapping lookup ambiguous for anyone
    re-judging a comparison."""
    path = bench_root / "evals" / "blind.jsonl"
    if not path.exists():
        return frame_id
    taken = {json.loads(line).get("frame_id")
             for line in path.read_text().splitlines() if line.strip()}
    if frame_id not in taken:
        return frame_id
    suffix = 2
    while f"{frame_id}-r{suffix}" in taken:
        suffix += 1
    return f"{frame_id}-r{suffix}"


def _sealed_swapped(bench_root: Path, frame_id: str) -> bool:
    """Read the sealed mapping (robust even for identical texts)."""
    path = bench_root / "evals" / "blind.jsonl"
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        mapping = json.loads(line)
        if mapping.get("frame_id") == frame_id:
            return bool(mapping.get("swapped"))
    raise KeyError(f"no sealed mapping for {frame_id}")


def pair_seed(manifest: dict, task: str, pair: int, dim: str) -> int:
    from .experiment import pair_seed as seeded

    return seeded(manifest, task, pair, dim)
