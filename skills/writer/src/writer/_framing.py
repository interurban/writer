"""Editorial framing state: candidate theses, selection, handoff.

Framings are cheap idea-selection artifacts, not prose. Candidates are
proposed (2-4 paragraphs), compared with the existing pairwise machinery
on candidate pitches, selected with reasoning, and handed to the writer
as a north star. Persisted under `framings/` so selection survives
compaction, restarts, and subagents.
"""

from __future__ import annotations

import re
from pathlib import Path

from ._store import _next_id, _now, _read_json, _root, _write_json

CANDIDATE_FIELDS = ("thesis", "why_matters", "contrast", "mental_model", "risk")


def _candidates_path(base: Path) -> Path:
    return base / "framings" / "candidates.json"


def _selected_path(base: Path) -> Path:
    return base / "framings" / "selected.json"


def framings_propose(candidates: list[dict],
                     root: str | Path | None = None) -> list[dict]:
    """Persist 2-4 candidate framings. Each needs at least a thesis;
    missing fields default to empty strings. Returns the stored records
    with `frame-NNN` ids and `candidate` status."""
    base = _root(root)
    stored = _read_json(_candidates_path(base), [])
    added = []
    for candidate in candidates:
        record = {"id": _next_id(stored, "frame"),
                  "status": "candidate", "created_at": _now()}
        for field in CANDIDATE_FIELDS:
            record[field] = str(candidate.get(field, "") or "")
        stored.append(record)
        added.append(record)
    _write_json(_candidates_path(base), stored)
    return added


def framings_list(root: str | Path | None = None) -> list[dict]:
    """All candidates, oldest first."""
    return _read_json(_candidates_path(_root(root)), [])


def framing_pitch(candidate: dict) -> str:
    """One comparable paragraph per candidate (for pairwise machinery)."""
    return (f"Thesis: {candidate.get('thesis', '')} "
            f"Why it matters: {candidate.get('why_matters', '')} "
            f"Contrast: {candidate.get('contrast', '')} "
            f"Mental model: {candidate.get('mental_model', '')}".strip())


def framings_select(frame_id: str, criterion: str, reasoning: str,
                    judge: str | None = None,
                    root: str | Path | None = None) -> dict:
    """Record the winning framing with selection reasoning. The losers keep
    `candidate` status; the winner becomes `selected`. Cleverness alone
    must not win — say why in `reasoning`."""
    base = _root(root)
    stored = _read_json(_candidates_path(base), [])
    if not any(c["id"] == frame_id for c in stored):
        raise KeyError(f"unknown framing {frame_id}")
    for candidate in stored:
        candidate["status"] = ("selected" if candidate["id"] == frame_id
                               else candidate.get("status", "candidate"))
    _write_json(_candidates_path(base), stored)
    selection = {"frame_id": frame_id, "criterion": criterion,
                 "reasoning": reasoning, "judge": judge,
                 "created_at": _now()}
    _write_json(_selected_path(base), selection)
    return selection


def framing_get(root: str | Path | None = None) -> dict | None:
    """Selected framing merged with its candidate record, else None."""
    base = _root(root)
    selection = _read_json(_selected_path(base), None)
    if not selection:
        return None
    for candidate in _read_json(_candidates_path(base), []):
        if candidate["id"] == selection.get("frame_id"):
            return {**candidate, "selection": selection}
    return {"selection": selection}


def framing_brief(root: str | Path | None = None,
                  keep: list[str] | None = None) -> str:
    """North-star handoff for the writer: thesis, payoff, model, and an
    explicit do-not-lose list (high-importance ledger claims by default).
    Guidance, not a template — the writer owns the prose."""
    selected = framing_get(root)
    if selected is None:
        raise FileNotFoundError("no framing selected; run framings_select first")
    if keep is None:
        from . import claims_list

        keep = [c["text"] for c in claims_list(root)
                if c.get("importance") == "high"]
    lines = ["Core thesis:", selected.get("thesis", ""),
             "", "Reader payoff:", selected.get("why_matters", ""),
             "", "Mental model:", selected.get("mental_model", ""),
             "", "Do not lose:"]
    lines.extend(f"- {item}" for item in keep)
    return "\n".join(lines).strip() + "\n"


def _content_words(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", text.lower()) if len(w) > 3}


def claims_coverage(parent_draft_id: str, revised_draft_id: str,
                    root: str | Path | None = None,
                    threshold: float = 0.5) -> dict:
    """Mechanical density check: which parent-draft claims still surface in
    the revision. A claim counts as preserved when at least `threshold` of
    its content words appear in the revised body. Heuristic triage for the
    "more engaging but less useful" verdict — not a proof."""
    from . import claims_list, drafts_get

    base = _root(root)
    revised_body = drafts_get(revised_draft_id, base).get("body", "")
    revised_words: set[str] = set()
    for sentence in re.split(r"[.!?]+", revised_body.lower()):
        revised_words.update(_content_words(sentence))
    preserved, possibly_lost = [], []
    for claim in claims_list(base):
        if claim.get("draft_id") != parent_draft_id:
            continue
        words = _content_words(claim.get("text", ""))
        if not words:
            continue
        (preserved if len(words & revised_words) / len(words) >= threshold
         else possibly_lost).append(claim["id"])
    return {"parent": parent_draft_id, "revised": revised_draft_id,
            "preserved": preserved, "possibly_lost": possibly_lost}
