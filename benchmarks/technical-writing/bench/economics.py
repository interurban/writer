"""Inference economics: parse Prime telemetry + Writer ledger metrics.

Sources, in order of preference:
1. `--mode json` event stream (`events.jsonl`): `message_end` assistant
   messages carrying `usage` objects (`totalTokens` or
   input/output/cacheRead/cacheWrite sums; cost keys when present).
2. Session-file fallback: the session header id (`{"type":"session"}`)
   locates `<sessions>/<id>.jsonl`; usage objects are scanned recursively,
   as are `child_usage` attributions (subagent counts/models when present).
3. Writer workdir `writing/`: ledger-derived metrics for the writer arm
   (vanilla has no ledger — those fields stay null, honestly asymmetric).

Anything Prime does not expose stays null/unknown. Nothing is estimated
except wall-clock (measured) and word counts (counted).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

USAGE_KEYS = ("totalTokens", "input", "output", "cacheRead", "cacheWrite")
COST_KEYS = ("cost", "totalCost", "costUsd", "price", "totalPrice")


def _walk(node, found: list) -> None:
    if isinstance(node, dict):
        if isinstance(node.get("usage"), dict):
            found.append(node["usage"])
        for value in node.values():
            _walk(value, found)
    elif isinstance(node, list):
        for value in node:
            _walk(value, found)


def usage_totals(usage: dict) -> tuple[int, int, int, float | None]:
    """(input, output, total, cost-or-None) from one usage object."""
    if not isinstance(usage, dict):
        return (0, 0, 0, None)
    total = usage.get("totalTokens")
    inputs = _num(usage.get("input"))
    outputs = _num(usage.get("output"))
    if not isinstance(total, (int, float)) or total <= 0:
        total = (inputs + outputs + _num(usage.get("cacheRead"))
                 + _num(usage.get("cacheWrite")))
    cost = None
    for key in COST_KEYS:
        value = usage.get(key)
        if isinstance(value, (int, float)):
            cost = float(value)
            break
    return (inputs, outputs, int(total), cost)


def _num(value) -> int:
    return value if isinstance(value, (int, float)) and value > 0 else 0


def parse_events(events_path: Path) -> dict:
    """Sum usage over `message_end` assistant messages (no double count:
    `turn_end`/`agent_end` repeat the same messages and are ignored)."""
    result = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0,
              "cost_usd": None, "assistant_messages": 0, "session_id": None,
              "method": "events"}
    if not events_path.exists():
        result["method"] = "no-events-file"
        return result
    usages: list = []
    for line in events_path.read_text().splitlines():
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if not isinstance(event, dict):
            continue
        if event.get("type") == "session" and result["session_id"] is None:
            session_id = event.get("id")
            if isinstance(session_id, str):
                result["session_id"] = session_id
        if event.get("type") != "message_end":
            continue
        message = event.get("message")
        if not isinstance(message, dict) or message.get("role") != "assistant":
            continue
        result["assistant_messages"] += 1
        usage = message.get("usage")
        if isinstance(usage, dict):
            usages.append(usage)
    for usage in usages:
        inputs, outputs, total, cost = usage_totals(usage)
        result["input_tokens"] += inputs
        result["output_tokens"] += outputs
        result["total_tokens"] += total
        if cost is not None:
            result["cost_usd"] = (result["cost_usd"] or 0.0) + cost
    if result["assistant_messages"] == 0:
        result["method"] = "events-no-usage"
    return result


def find_session_file(sessions_dir: Path, session_id: str | None) -> Path | None:
    """Locate the session transcript: header id first, newest fallback."""
    if session_id:
        candidate = sessions_dir / f"{session_id}.jsonl"
        if candidate.exists():
            return candidate
    if not sessions_dir.exists():
        return None
    files = sorted(sessions_dir.glob("*.jsonl"),
                   key=lambda p: p.stat().st_mtime)
    return files[-1] if files else None


def parse_session_file(path: Path | None) -> dict:
    """Fallback usage scan + subagent attribution count from transcript."""
    result = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0,
              "cost_usd": None, "subagent_attributions": 0,
              "attributed_models": [], "method": "session-file"}
    if path is None or not path.exists():
        result["method"] = "no-session-file"
        return result
    usages: list = []
    attributions = 0
    models: list = []
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
        except ValueError:
            continue
        found: list = []
        _walk(entry, found)
        usages.extend(found)
        attributions += _count_key(entry, "child_usage")
        models.extend(_collect_models(entry))
    for usage in usages:
        inputs, outputs, total, cost = usage_totals(usage)
        result["input_tokens"] += inputs
        result["output_tokens"] += outputs
        result["total_tokens"] += total
        if cost is not None:
            result["cost_usd"] = (result["cost_usd"] or 0.0) + cost
    result["subagent_attributions"] = attributions
    result["attributed_models"] = sorted(set(models))
    return result


def _count_key(node, key: str) -> int:
    if isinstance(node, dict):
        return (1 if key in node else 0) + sum(
            _count_key(v, key) for v in node.values())
    if isinstance(node, list):
        return sum(_count_key(v, key) for v in node)
    return 0


def _collect_models(node) -> list:
    """Model selectors mentioned inside attribution entries, if any."""
    found = []
    if isinstance(node, dict):
        if "child_usage" in node:
            for key in ("model", "selector", "model_id"):
                value = node.get(key)
                if isinstance(value, str) and value:
                    found.append(value)
        for value in node.values():
            found.extend(_collect_models(value))
    elif isinstance(node, list):
        for value in node:
            found.extend(_collect_models(value))
    return found


def count_subagent_dirs(agent_dir: Path) -> int | None:
    """Session-artifact `sub-*` dirs under the isolated agent home."""
    if not agent_dir.exists():
        return None
    return sum(1 for p in agent_dir.rglob("sub-*") if p.is_dir())


def writer_metrics(workdir: Path) -> dict:
    """Ledger-derived metrics from the run workdir (writer arm only)."""
    import sys

    nulls = {"sources": None, "claims_extracted": None,
             "claims_verified": None, "claims_unverified": None,
             "claims_failed": None, "claims_high_unsupported": None,
             "drafts": None, "revisions": None, "comparisons": None,
             "exec_checks": None, "exec_failed": None,
             "framings_proposed": None, "framing_selected": None,
             "framing_components": None, "method": None}
    from .common import REPO
    sys.path.insert(0, str(REPO / "skills" / "writer" / "src"))
    import writer

    from writer import WRITER_DIR_NAME

    root = workdir / WRITER_DIR_NAME
    if not (root / "project.json").exists():
        # Workdirs written before the visible-directory rename keep
        # working: read-only fallback, never a migration (benchmark
        # artifacts stay byte-stable).
        legacy = workdir / ".writer"
        if (legacy / "project.json").exists():
            root = legacy
        else:
            nulls["method"] = "no-writer-state"
            return nulls
    claims = writer.claims_list(root)
    drafts = writer.drafts_list(root)
    evals = writer.evals_list(root)
    execs = writer.exec_list(root)
    framings = writer.framings_list(root)
    selected = writer.framing_get(root)
    components = (sum(1 for field in ("thesis", "why_it_matters", "contrast",
                                      "mental_model")
                      if str(selected.get(field, "")).strip())
                  if selected else None)
    metrics = {
        "sources": len(writer.sources_list(root)),
        "claims_extracted": len(claims),
        "claims_verified": sum(1 for c in claims
                               if c.get("verification") == "verified"),
        "claims_unverified": sum(1 for c in claims
                                 if c.get("verification") == "unverified"),
        "claims_failed": sum(1 for c in claims
                             if c.get("verification") == "failed"),
        "claims_high_unsupported": sum(
            1 for c in claims
            if c.get("importance") == "high"
            and (not c.get("source_ids")
                 or c.get("support") in ("unsupported", "unknown"))),
        "drafts": len(drafts),
        "revisions": sum(1 for d in drafts if d.get("parent")),
        "comparisons": sum(1 for e in evals
                           if str(e.get("name", "")).startswith("pairwise")),
        "exec_checks": len(execs),
        "exec_failed": sum(1 for e in execs if e.get("exit_status") != 0),
        "framings_proposed": len(framings),
        "framing_selected": 1 if selected else 0,
        "framing_components": components,
        "method": "writer-ledger",
    }
    return metrics


def citation_urls(text: str) -> list[str]:
    """URLs appearing in output (reported, not verified, by default)."""
    import re

    return sorted(set(re.findall(r"https?://[^\s)>\]]+", text)))
