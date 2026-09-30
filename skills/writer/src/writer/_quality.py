"""Run-level quality summaries derived from editorial state.

Token/cost fields stay empty unless the caller merges Prime's own tracing
figures in — this module never duplicates Prime telemetry, it only
summarizes what the writing layer persisted.
"""

from __future__ import annotations

from pathlib import Path

from ._store import _root


def trace_summary(root: str | Path | None = None,
                  tokens_approx: int | None = None,
                  cost_usd_approx: float | None = None) -> dict:
    """Count sources, claims by status, drafts, evals from state on disk."""
    from . import claims_list, drafts_list, evals_list, sources_list

    base = _root(root)
    claims = claims_list(base)
    quality = {
        "sources_captured": len(sources_list(base)),
        "claims_extracted": len(claims),
        "claims_verified": sum(1 for c in claims
                               if c.get("verification") == "verified"),
        "claims_unverified": sum(1 for c in claims
                                 if c.get("verification") == "unverified"),
        "claims_failed": sum(1 for c in claims
                             if c.get("verification") == "failed"),
        "drafts_created_count": len(drafts_list(base)),
        "evals_performed": len(evals_list(base)),
        "tokens_approx": tokens_approx,
        "cost_usd_approx": cost_usd_approx,
    }
    return {k: v for k, v in quality.items() if v is not None}
