"""Blind pairwise comparison for benchmark outputs.

The judge sees randomized first/second texts plus one criterion question;
provenance labels (`writer`, `vanilla`, draft ids) are sealed to
`evals/blind.jsonl` at presentation time and unsealed only in
`blind_resolve`. Tallies count label wins — never a 1–10 score.
"""

from __future__ import annotations

import random
from pathlib import Path

from ._store import _append_jsonl, _now, _root

_STANDARD_CRITERIA = (
    "Which would you voluntarily continue reading?",
    "Which is more useful to the target audience?",
    "Which contains more specific information?",
    "Which demonstrates stronger technical credibility?",
    "Which feels more distinctive and less generic?",
    "Which better fulfills the brief?",
    "Which gives the target reader a stronger and more useful mental "
    "model for understanding the subject?",
)


def standard_criteria() -> tuple[str, ...]:
    """The benchmark comparison questions."""
    return _STANDARD_CRITERIA


def blind_present(text_a: str, text_b: str, label_a: str, label_b: str,
                  criterion: str, seed: int | None = None,
                  frame_id: str | None = None,
                  root: str | Path | None = None) -> dict:
    """Randomize order, seal the mapping, return the judge-facing frame."""
    base = _root(root)
    swapped = random.Random(seed).choice([True, False])
    sealed = _read_sealed(base)
    frame_id = frame_id or f"blind-{len(sealed) + 1:03d}"
    _append_jsonl(base / "evals/blind.jsonl",
                  {"frame_id": frame_id, "criterion": criterion,
                   "label_a": label_a, "label_b": label_b,
                   "swapped": swapped, "created_at": _now()})
    return {"frame_id": frame_id, "criterion": criterion,
            "first": text_b if swapped else text_a,
            "second": text_a if swapped else text_b}


def blind_resolve(frame_id: str, frame_winner: str, reasoning: str,
                  confidence: float | None = None,
                  root: str | Path | None = None) -> dict:
    """Unseal the frame, map to provenance labels, persist the judgment."""
    base = _root(root)
    if frame_winner not in ("first", "second", "tie"):
        raise ValueError("frame_winner must be first, second, or tie")
    mapping = next((m for m in _read_sealed(base)
                    if m.get("frame_id") == frame_id), None)
    if mapping is None:
        raise KeyError(f"unknown blind frame {frame_id}")
    swapped = mapping["swapped"]
    winner = {"tie": "tie", "first": "B" if swapped else "A",
              "second": "A" if swapped else "B"}[frame_winner]
    evaluation = {"name": "pairwise-blind", "criterion": mapping["criterion"],
                  "winner": winner, "reasoning": reasoning,
                  "confidence": confidence, "created_at": _now(),
                  "swapped": swapped}
    _append_jsonl(base / "evals/evaluations.jsonl",
                  {"criterion": mapping["criterion"],
                   "subjects": [mapping["label_a"], mapping["label_b"]],
                   "evaluation": evaluation})
    return {**evaluation, "winner_label":
            {"A": mapping["label_a"], "B": mapping["label_b"],
             "tie": "tie"}[winner]}


def blind_tally(root: str | Path | None = None) -> dict:
    """Count blind wins per provenance label across resolved frames."""
    import json

    base = _root(root)
    path = base / "evals/evaluations.jsonl"
    tally: dict[str, dict] = {}
    if not path.exists():
        return tally
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        evaluation = record.get("evaluation", {})
        if evaluation.get("name") != "pairwise-blind":
            continue
        subjects = record.get("subjects", [])
        if len(subjects) != 2:
            continue
        winner = evaluation.get("winner")
        label = {"A": subjects[0], "B": subjects[1],
                 "tie": "tie"}.get(winner, "unknown")
        entry = tally.setdefault(label, {"wins": 0, "judgments": 0})
        entry["judgments"] += 1
        if winner in ("A", "B"):
            entry["wins"] += 1
    return tally


def _read_sealed(base: Path) -> list[dict]:
    import json

    path = base / "evals/blind.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines()
            if line.strip()]
