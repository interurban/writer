"""Heuristic claim extraction for the Writer harness.

Mirrors the `pa-writer` `extract` signals: sentence splitting plus keyword
classification into the existing claim-type vocabulary. Useful, persisted,
inspectable — never perfect. The model reviews candidates; the ledger is
the source of truth.
"""

from __future__ import annotations

import re
from pathlib import Path

from ._store import _next_id, _read_json, _write_json, _root

_FILLER = (
    "in this article", "in conclusion", "let's dive", "tl;dr", "read on to",
    "in today's", "without further ado", "as we all know",
)
_OPINION = (
    "i think", "in my view", "arguably", "in my opinion", "the best",
    "should be", "ought to",
)
_INFERENCE = (
    "suggests that", "likely to", "probably", "implies that", "this means",
    "we can infer",
)
_MEASURE_SUBSTR = (
    "%", "percent", "seconds", "x faster", "x slower", "million", "billion",
)
_MEASURE_TOKENS = {"ms", "mb", "gb", "kb", "tps", "qps"}
_GLUED_UNIT_RE = re.compile(r"\d+\s?(ms|mb|gb|kb|tps|qps|%|x)\b")
_PRODUCT = (
    "supports", "provides", "offers", "includes", "pricing", "free tier",
    "beta", "generally available", "enterprise",
)
_HISTORICAL = (
    "announced", "launched", "acquired", "founded", "released",
    "introduced in", "shipped",
)
_TECHNICAL = (
    "uses", "requires", "returns", "sends", "exposes", "implements",
    "runs on", "built on", "protocol", "api", "default", "always", "never",
)
_VERSION_RE = re.compile(r"\d+\.\d+")
_YEAR_RE = re.compile(r"\b(199\d|20[0-3]\d)\b")
_SENTENCE_END = re.compile(r"[.!;]")


def _split_sentences(paragraph: str) -> list[str]:
    sentences, start = [], 0
    for match in _SENTENCE_END.finditer(paragraph):
        rest = paragraph[match.end():]
        stripped = rest.lstrip()
        gap = rest[: len(rest) - len(stripped)]
        boundary = ("\n" in gap) or not stripped or (
            stripped[0].isupper() or stripped[0] in "\"`"
        )
        if boundary:
            sentences.append(paragraph[start: match.end()].strip())
            start = match.end()
    tail = paragraph[start:].strip()
    if tail:
        sentences.append(tail)
    return [s for s in sentences if s]


def _classify(lowered: str) -> tuple[str, str] | None:
    if any(f in lowered for f in _FILLER):
        return None
    if any(k in lowered for k in _OPINION):
        return ("opinion", "low")
    if any(k in lowered for k in _INFERENCE):
        return ("inference", "low")
    tokens = set(re.split(r"[^a-z0-9]+", lowered))
    if (_VERSION_RE.search(lowered) or _YEAR_RE.search(lowered)
            or _GLUED_UNIT_RE.search(lowered)
            or any(k in lowered for k in _MEASURE_SUBSTR)
            or tokens & _MEASURE_TOKENS):
        return ("numeric", "high")
    if any(k in lowered for k in _PRODUCT):
        return ("product", "high")
    if any(k in lowered for k in _HISTORICAL):
        return ("historical", "medium")
    if any(k in lowered for k in _TECHNICAL):
        return ("technical", "medium")
    return None


def extract_candidates(body: str, draft_id: str) -> list[dict]:
    """Classify sentences without persisting. Returns candidate dicts."""
    out = []
    para_no = 0
    for paragraph in body.split("\n\n"):
        paragraph = paragraph.strip()
        if not paragraph:
            continue
        para_no += 1
        if paragraph.startswith("#") or paragraph.startswith("```"):
            continue
        for sentence in _split_sentences(paragraph):
            text = sentence.strip()
            if len(text) < 32 or text.endswith("?"):
                continue
            classified = _classify(text.lower())
            if classified is None:
                continue
            claim_type, importance = classified
            out.append({"text": text, "type": claim_type,
                        "importance": importance,
                        "location": f"{draft_id} §{para_no}"})
    return out


def claims_extract(draft_id: str, persist: bool = True,
                   root: str | Path | None = None) -> list[dict]:
    """Extract claims from a stored draft into the ledger.

    Skips sentences already ledgered for the same draft (normalized-text
    dedupe). New entries start `unknown`/`unverified`. Returns the added
    (or, with `persist=False`, candidate) claims.
    """
    from . import drafts_get

    base = _root(root)
    draft = drafts_get(draft_id, base)
    candidates = extract_candidates(draft.get("body", ""), draft_id)
    if not persist:
        return candidates
    ledger = _read_json(base / "claims/ledger.json", [])
    seen = {re.sub(r"\s+", " ", c.get("text", "")).strip().lower()
            for c in ledger if c.get("draft_id") == draft_id}
    added = []
    for candidate in candidates:
        normalized = re.sub(r"\s+", " ", candidate["text"]).strip().lower()
        if normalized in seen:
            continue
        seen.add(normalized)
        claim = {"id": _next_id(ledger, "claim"), **candidate,
                 "source_ids": [], "support": "unknown",
                 "verification": "unverified", "draft_id": draft_id}
        ledger.append(claim)
        added.append(claim)
    _write_json(base / "claims/ledger.json", ledger)
    return added
