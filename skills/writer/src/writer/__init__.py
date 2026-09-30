"""Editorial project state for the Writer harness (Prime Agent RLM skill).

File-backed access to `writing/` so writing state survives compaction,
restarts, subagents, and model changes. Same on-disk format as the
`pa-writer` Rust crate: JSON records plus sibling markdown bodies.

Resolution: `$WRITER_DIR` wins, else `<cwd>/writing` (legacy `<cwd>/.writer`
auto-migrates on first open).
"""

from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Any

from ._store import (
    _append_jsonl,
    _next_id,
    _now,
    _read_json,
    _root,
    _write_json,
    WRITER_DIR_NAME,
)


# ---------------------------------------------------------------- project ---

def project_init(name: str, goal: str | None = None, root: str | Path | None = None) -> dict:
    """Create a fresh `writing/` layout. Errors when one already exists."""
    base = _root(root)
    if (base / "project.json").exists():
        raise FileExistsError(f"writer project already exists at {base}")
    for sub in ["brief", "sources", "claims", "voice/examples",
                "drafts", "evals", "preferences", "traces"]:
        (base / sub).mkdir(parents=True, exist_ok=True)
    now = _now()
    project = {"name": name, "goal": goal, "current_draft_id": None,
               "final_draft_id": None, "created_at": now, "updated_at": now}
    _write_json(base / "project.json", project)
    _defaults(base)
    return project


def project_archive(root: str | Path | None = None) -> dict:
    """Archive the current project beside itself, non-destructively.

    Renames the store root to `writing.archive.<UTC-timestamp>/` (numeric
    suffix on collision) and returns `{"archived_from", "archived_to"}`.
    Errors when no project exists. The archive is ordinary project state:
    reopen it anytime by pointing `$WRITER_DIR` at it or moving it back.
    """
    base = _root(root)
    if not (base / "project.json").exists():
        raise FileNotFoundError(f"no project to archive at {base}")
    stamp = "".join(ch for ch in _now()[:19] if ch.isdigit())
    target = base.parent / f"{base.name}.archive.{stamp}"
    counter = 2
    while target.exists():
        target = base.parent / f"{base.name}.archive.{stamp}-{counter}"
        counter += 1
    base.rename(target)
    return {"archived_from": str(base), "archived_to": str(target)}


def project_new(name: str, goal: str | None = None, archive: bool = True,
                root: str | Path | None = None) -> dict:
    """Start a fresh project for a new topic in this directory.

    With `archive=True` (default) an existing project is archived first
    via `project_archive` — nothing is ever overwritten. With
    `archive=False` an existing project raises `FileExistsError`, same as
    `project_init`. Returns `{"project", "archived"}` where `archived` is
    the archive record or `None`.
    """
    base = _root(root)
    archived = None
    if (base / "project.json").exists():
        if not archive:
            raise FileExistsError(f"writer project already exists at {base}")
        archived = project_archive(base)
    return {"project": project_init(name, goal=goal, root=base),
            "archived": archived}


def _defaults(base: Path) -> None:
    seeds = {
        "brief/objective.md": "# Objective\n",
        "brief/audience.md": "# Audience\n",
        "brief/constraints.md": "# Constraints\n",
        "brief/brief.json": '{"label":"","background":"","notes":""}',
        "sources/index.json": "[]",
        "claims/ledger.json": "[]",
        "voice/profile.json": '{"vocabulary":"","cadence":"","formality":"",'
                               '"technical_density":"","point_of_view":"","humor":"","structure":""}',
        "voice/avoid.md": "# Avoid\n",
        "drafts/index.json": "[]",
    }
    for rel, contents in seeds.items():
        path = base / rel
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(contents)


def project_get(root: str | Path | None = None) -> dict:
    """Load the project record."""
    return _read_json(_root(root) / "project.json", None) or _missing()


def project_update(root: str | Path | None = None, **fields: Any) -> dict:
    """Update project fields (name, goal, current_draft_id, ...)."""
    base = _root(root)
    project = project_get(base)
    project.update({k: v for k, v in fields.items() if v is not None or k in project})
    project["updated_at"] = _now()
    _write_json(base / "project.json", project)
    return project


def _missing() -> dict:
    raise FileNotFoundError("no writing/project.json here; call writer.project_init(name) first")


# ------------------------------------------------------------------ brief ---

def brief_get(root: str | Path | None = None) -> dict:
    """Load objective/audience/constraints."""
    base = _root(root)
    audience = _read_json(base / "brief/brief.json",
                          {"label": "", "background": "", "notes": ""})
    return {
        "objective": (base / "brief/objective.md").read_text()
        if (base / "brief/objective.md").exists() else "",
        "audience": audience,
        "constraints": (base / "brief/constraints.md").read_text()
        if (base / "brief/constraints.md").exists() else "",
    }


def brief_set(objective: str | None = None, constraints: str | None = None,
              root: str | Path | None = None, **audience: Any) -> dict:
    """Save brief bodies and/or audience fields (label, background, notes)."""
    base = _root(root)
    if objective is not None:
        (base / "brief/objective.md").write_text(objective)
    if constraints is not None:
        (base / "brief/constraints.md").write_text(constraints)
    if audience:
        current = _read_json(base / "brief/brief.json",
                             {"label": "", "background": "", "notes": ""})
        current.update(audience)
        _write_json(base / "brief/brief.json", current)
        (base / "brief/audience.md").write_text(
            f"# Audience: {current.get('label','')}\n\n"
            f"{current.get('background','')}\n\n{current.get('notes','')}\n")
    return brief_get(base)


# ----------------------------------------------------------------- drafts ---

def _draft_index(base: Path) -> list[dict]:
    return _read_json(base / "drafts/index.json", [])


def drafts_list(root: str | Path | None = None) -> list[dict]:
    """List drafts oldest-first, bodies hydrated from `draft-NNN.md`."""
    base = _root(root)
    drafts = _draft_index(base)
    for draft in drafts:
        body = base / f"drafts/{draft['id']}.md"
        draft["body"] = body.read_text() if body.exists() else draft.get("body", "")
    return sorted(drafts, key=lambda d: d["id"])


def drafts_get(draft_id: str, root: str | Path | None = None) -> dict:
    """Fetch one draft by stable id."""
    for draft in drafts_list(root):
        if draft["id"] == draft_id:
            return draft
    raise KeyError(f"unknown draft {draft_id}")


def drafts_save(body: str, parent: str | None = None, reason: str | None = None,
                model: str | None = None, run_id: str | None = None,
                root: str | Path | None = None) -> dict:
    """Save a new immutable revision (never overwrites). Returns the draft."""
    base = _root(root)
    drafts = _draft_index(base)
    draft_id = _next_id(drafts, "draft")
    draft = {"id": draft_id, "parent": parent, "model": model,
             "created_at": _now(), "reason": reason, "run_id": run_id,
             "is_final": False, "body": ""}
    (base / f"drafts/{draft_id}.md").write_text(body)
    drafts.append(draft)
    _write_json(base / "drafts/index.json", drafts)
    project_update(base, current_draft_id=draft_id)
    return {**draft, "body": body}


def drafts_make_current(draft_id: str, root: str | Path | None = None) -> dict:
    """Revert the working pointer to an older draft (no deletion)."""
    base = _root(root)
    draft = drafts_get(draft_id, base)
    project_update(base, current_draft_id=draft_id)
    return draft


def drafts_mark_final(draft_id: str, root: str | Path | None = None) -> dict:
    """Mark one draft final (clears any previous flag)."""
    base = _root(root)
    drafts = _draft_index(base)
    if not any(d["id"] == draft_id for d in drafts):
        raise KeyError(f"unknown draft {draft_id}")
    for draft in drafts:
        draft["is_final"] = draft["id"] == draft_id
    _write_json(base / "drafts/index.json", drafts)
    project_update(base, final_draft_id=draft_id, current_draft_id=draft_id)
    return drafts_get(draft_id, base)


def drafts_compare(a: str, b: str, root: str | Path | None = None) -> dict:
    """Structural diff summary (line counts + newer id)."""
    left, right = drafts_get(a, root), drafts_get(b, root)
    return {"a": left["id"], "b": right["id"],
            "a_lines": len(left.get("body", "").splitlines()),
            "b_lines": len(right.get("body", "").splitlines()),
            "newer": max(left["id"], right["id"])}


# ---------------------------------------------------------------- sources ---

def sources_list(root: str | Path | None = None) -> list[dict]:
    """List all sources oldest-first."""
    return sorted(_read_json(_root(root) / "sources/index.json", []),
                  key=lambda s: s.get("id", ""))


def sources_get(source_id: str, root: str | Path | None = None) -> dict:
    """Fetch one source by id."""
    for source in sources_list(root):
        if source["id"] == source_id:
            return source
    raise KeyError(f"unknown source {source_id}")


def sources_add(title: str, url: str | None = None, origin: str | None = None,
                notes: str | None = None, excerpts: list[dict] | None = None,
                root: str | Path | None = None) -> dict:
    """Record a source with optional excerpts [{text, locator?}]."""
    base = _root(root)
    sources = _read_json(base / "sources/index.json", [])
    source = {"id": _next_id(sources, "src"), "title": title, "url": url,
              "origin": origin, "captured_at": _now(), "notes": notes,
              "excerpts": excerpts or []}
    sources.append(source)
    _write_json(base / "sources/index.json", sources)
    return source


# ----------------------------------------------------------------- claims ---

def claims_list(root: str | Path | None = None) -> list[dict]:
    """List all claims oldest-first."""
    return sorted(_read_json(_root(root) / "claims/ledger.json", []),
                  key=lambda c: c.get("id", ""))


def claims_add(text: str, claim_type: str = "technical", importance: str = "medium",
               source_ids: list[str] | None = None, support: str = "unknown",
               verification: str = "unverified", draft_id: str | None = None,
               location: str | None = None,
               root: str | Path | None = None) -> dict:
    """Add a claim linked to source ids."""
    base = _root(root)
    claims = _read_json(base / "claims/ledger.json", [])
    claim = {"id": _next_id(claims, "claim"), "text": text, "type": claim_type,
             "importance": importance, "source_ids": source_ids or [],
             "support": support, "verification": verification,
             "draft_id": draft_id, "location": location}
    claims.append(claim)
    _write_json(base / "claims/ledger.json", claims)
    return claim


def claims_update(claim_id: str, support: str | None = None,
                  verification: str | None = None,
                  root: str | Path | None = None) -> dict:
    """Update a claim's support and/or verification status."""
    base = _root(root)
    claims = _read_json(base / "claims/ledger.json", [])
    for claim in claims:
        if claim["id"] == claim_id:
            if support is not None:
                claim["support"] = support
            if verification is not None:
                claim["verification"] = verification
            _write_json(base / "claims/ledger.json", claims)
            return claim
    raise KeyError(f"unknown claim {claim_id}")


def claims_needing_support(root: str | Path | None = None) -> list[dict]:
    """Triage queue: claims with no sources or weak support."""
    return [c for c in claims_list(root)
            if not c.get("source_ids") or c.get("support") in ("unsupported", "unknown")]


def claims_verify(claim_id: str, support: str,
                  verification: str, evidence_source_ids: list[str] | None = None,
                  exec_ref: str | None = None, note: str | None = None,
                  root: str | Path | None = None) -> dict:
    """Verify a claim against stored evidence.

    `verified` requires evidence (source ids or an exec record): an LLM may
    not declare truth by memory. Merges new source ids into the claim and
    records what was consulted in `verification_note`.
    """
    if verification == "verified" and not evidence_source_ids and not exec_ref:
        raise ValueError(
            f"claim {claim_id}: verified requires evidence (source ids or exec record)")
    base = _root(root)
    claims = _read_json(base / "claims/ledger.json", [])
    for claim in claims:
        if claim["id"] == claim_id:
            claim["support"] = support
            claim["verification"] = verification
            for source_id in evidence_source_ids or []:
                if source_id not in claim.get("source_ids", []):
                    claim.setdefault("source_ids", []).append(source_id)
            if exec_ref is not None:
                claim["exec_ref"] = exec_ref
            if note is not None:
                claim["verification_note"] = note
            _write_json(base / "claims/ledger.json", claims)
            return claim
    raise KeyError(f"unknown claim {claim_id}")


_IMPORTANCE_RANK = {"high": 0, "medium": 1, "low": 2}


def verify_draft(draft_id: str, root: str | Path | None = None) -> list[dict]:
    """Triage queue for one draft: unverified claims, high-importance first."""
    claims = [c for c in claims_list(root)
              if c.get("draft_id") == draft_id and c.get("verification") == "unverified"]
    return sorted(claims,
                  key=lambda c: (_IMPORTANCE_RANK.get(c.get("importance"), 9), c.get("id", "")))


# ------------------------------------------------------------------ voice ---

def voice_get(root: str | Path | None = None) -> dict:
    """Load the voice profile (+ avoid.md)."""
    base = _root(root)
    profile = _read_json(base / "voice/profile.json", {})
    avoid = (base / "voice/avoid.md").read_text() if (base / "voice/avoid.md").exists() else ""
    return {**profile, "avoid": avoid}


def voice_save(profile: dict, avoid: str | None = None,
               root: str | Path | None = None) -> dict:
    """Persist voice tendencies (vocabulary, cadence, formality, ...)."""
    base = _root(root)
    _write_json(base / "voice/profile.json", profile)
    if avoid is not None:
        (base / "voice/avoid.md").write_text(avoid)
    return voice_get(base)


# ------------------------------------------------------------------ evals ---

def evals_compare(a_text: str, b_text: str, criterion: str,
                  subjects: list[str] | None = None,
                  seed: int | None = None,
                  root: str | Path | None = None) -> dict:
    """Prepare a randomized pairwise frame. Returns {first, second, swapped}."""
    rng = random.Random(seed)
    swapped = rng.choice([True, False])
    return {"criterion": criterion,
            "subjects": subjects or ["A", "B"],
            "first": b_text if swapped else a_text,
            "second": a_text if swapped else b_text,
            "swapped": swapped}


def evals_resolve(criterion: str, subjects: list[str], swapped: bool,
                  frame_winner: str, reasoning: str,
                  confidence: float | None = None,
                  root: str | Path | None = None) -> dict:
    """Record a judgment from a randomized frame (first/second/tie)."""
    if frame_winner not in ("first", "second", "tie"):
        raise ValueError("frame_winner must be first, second, or tie")
    winner = {"tie": "tie", "first": "B" if swapped else "A",
              "second": "A" if swapped else "B"}[frame_winner]
    record = {"criterion": criterion, "subjects": subjects,
              "evaluation": {"name": "pairwise", "criterion": criterion,
                             "winner": winner, "reasoning": reasoning,
                             "confidence": confidence,
                             "created_at": _now(), "swapped": swapped}}
    _append_jsonl(_root(root) / "evals/evaluations.jsonl", record)
    return record["evaluation"]


def evals_list(root: str | Path | None = None) -> list[dict]:
    """Read back persisted evaluations."""
    path = _root(root) / "evals/evaluations.jsonl"
    if not path.exists():
        return []
    out = []
    for line in path.read_text().splitlines():
        if line.strip():
            out.append(json.loads(line).get("evaluation", {}))
    return out


# ------------------------------------------------------------ preferences ---

def preference_record(draft_a: str, draft_b: str, winner: str,
                      reasons: list[str] | None = None,
                      root: str | Path | None = None) -> dict:
    """Persist a human preference observation (A/B/tie + reason tags)."""
    if winner not in ("A", "B", "tie"):
        raise ValueError("winner must be A, B, or tie")
    pref = {"draft_a": draft_a, "draft_b": draft_b, "winner": winner,
            "reasons": reasons or [], "created_at": _now()}
    _append_jsonl(_root(root) / "preferences/preferences.jsonl", pref)
    return pref


# ----------------------------------------------------------------- traces ---

def trace_begin(run_id: str, task: str, model: str | None = None,
                root: str | Path | None = None) -> dict:
    """Open a run trace envelope."""
    trace = {"run_id": run_id, "task": task, "model": model, "skills": [],
             "subagents": [], "drafts_created": [], "final_draft": None,
             "elapsed_ms": None, "started_at": _now(), "finished_at": None}
    _append_jsonl(_root(root) / "traces/runs.jsonl", trace)
    return trace


def trace_finish(run_id: str, skills: list | None = None,
                 subagents: list | None = None, drafts_created: list | None = None,
                 final_draft: str | None = None, elapsed_ms: int | None = None,
                 quality: dict | None = None,
                 root: str | Path | None = None) -> dict:
    """Append the completed envelope for a run (readers take last per id)."""
    trace = {"run_id": run_id, "skills": skills or [], "subagents": subagents or [],
             "drafts_created": drafts_created or [], "final_draft": final_draft,
             "elapsed_ms": elapsed_ms, "finished_at": _now(),
             "quality": quality or {}}
    _append_jsonl(_root(root) / "traces/runs.jsonl", trace)
    return trace


# ----------------------------------------------------------------- status ---

ACTIVITIES = {
    "researching": "Researching...",
    "verifying": "Verifying claims...",
    "exploring": "Exploring alternatives...",
    "comparing": "Comparing drafts...",
    "testing": "Testing code...",
    "checking_sources": "Checking sources...",
    "revising": "Revising...",
}


def activity(label: str) -> str:
    """Map an activity key to its display label (no chain-of-thought)."""
    return ACTIVITIES.get(label, label)


def status_line(model: str | None = None, root: str | Path | None = None) -> str:
    """Compact writing status for TUI chrome."""
    base = _root(root)
    try:
        drafts = drafts_list(base)
    except Exception:
        drafts = []
    sources = sources_list(base) if (base / "sources/index.json").exists() else []
    claims = claims_list(base) if (base / "claims/ledger.json").exists() else []
    verified = sum(1 for c in claims if c.get("verification") == "verified")
    try:
        current = (project_get(base) or {}).get("current_draft_id") or "-"
    except Exception:
        current = "-"
    parts = [f"Draft: {current} ({len(drafts)} total)",
             f"Sources: {len(sources)}",
             f"Claims: {verified}/{len(claims)} verified"]
    if model:
        parts.append(f"Model: {model}")
    return " | ".join(parts)


def run(*args: Any, **kwargs: Any) -> str:
    """Skill entrypoint: `await writer()` reports the compact status line."""
    return status_line(kwargs.get("model"), kwargs.get("root"))


# V1 capability modules (same `writer.*` API; split by responsibility).
from ._blind import blind_present, blind_resolve, blind_tally, standard_criteria
from ._execs import exec_check, exec_list
from ._extract import claims_extract, extract_candidates
from ._framing import (claims_coverage, framing_brief, framing_get,
                       framing_pitch, framings_list, framings_propose,
                       framings_select)
from ._models import models_family, models_get, models_pick_critic, models_set
from ._prime import (models_available, models_cached_openrouter,
                     models_current, models_describe, models_policy,
                     models_providers, models_ready, models_refresh_openrouter,
                     models_role, models_set_policy, models_status,
                     prime_agent_dir, prime_auth_providers, prime_settings)
from ._quality import trace_summary
