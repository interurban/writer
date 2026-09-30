"""Experiment summary: per-criterion counts, task/category splits,
economics medians + ratios, CSV/JSON export for correlation exploration.
Never a single global quality score."""

from __future__ import annotations

import csv
import json
import statistics
from pathlib import Path

from . import common


def load_model_judgments(exp_dir: Path) -> list[dict]:
    """Only validated verdicts (`winner_label` set) count as results."""
    return [r for r in load_all_model_judgments(exp_dir) if r.get("winner_label")]


def load_all_model_judgments(exp_dir: Path) -> list[dict]:
    """Every persisted model record, including invalid ones."""
    base = exp_dir / "judgments" / "model"
    if not base.exists():
        return []
    records = []
    for path in sorted(base.rglob("*.json")):
        try:
            records.append(json.loads(path.read_text()))
        except ValueError:
            continue
    return records


def load_human_judgments(exp_dir: Path) -> list[dict]:
    """Flatten human pair files (dims dict) into per-dim rows."""
    base = exp_dir / "judgments" / "human"
    rows = []
    if not base.exists():
        return rows
    for path in sorted(base.rglob("pair-*.json")):
        try:
            pair = json.loads(path.read_text())
        except ValueError:
            continue
        for dim_key, judgment in (pair.get("dims") or {}).items():
            if "winner_label" not in judgment or not judgment.get(
                    "winner_label"):
                continue
            rows.append({
                "experiment_id": pair.get("experiment_id"),
                "task": pair.get("task"), "pair": pair.get("pair"),
                "dim": dim_key, "judge_kind": "human",
                "judge_name": pair.get("judge_name"),
                "author_model": pair.get("author_model"),
                "winner_label": judgment["winner_label"],
                "confidence": judgment.get("confidence"),
                "tags": judgment.get("tags", []),
                "reasoning": judgment.get("notes", ""),
                "evidence": judgment.get("evidence", ""),
            })
    return rows


def agreement_table(model: list[dict], human: list[dict]) -> dict:
    """Inter-judge agreement per dimension, over comparable comparisons.

    A pair of rows is comparable when model and human judged the same
    (task, pair, dim). Only full-agreeing rows contribute; each counted
    comparison is one observation, and a dimension with no overlap reports
    n=0 rather than a fabricated rate.
    """
    by_key: dict = {}
    for row in model:
        key = (row.get("task"), row.get("pair"), row.get("dim"))
        by_key.setdefault(key, {})[f"model:{row.get('judge_model')}"] = (
            row.get("winner_label"))
    for row in human:
        key = (row.get("task"), row.get("pair"), row.get("dim"))
        by_key.setdefault(key, {})[f"human:{row.get('judge_name')}"] = (
            row.get("winner_label"))
    table: dict = {}
    for (task, _pair, dim), verdicts in by_key.items():
        if len(verdicts) < 2:
            continue
        labels = list(verdicts.values())
        entry = table.setdefault(dim, {"comparisons": 0, "agree": 0,
                                       "disagree": 0, "rows": {}})
        entry["comparisons"] += 1
        if len(set(labels)) == 1:
            entry["agree"] += 1
        else:
            entry["disagree"] += 1
        entry["rows"][f"{task}"] = verdicts
    for entry in table.values():
        entry["agreement_rate"] = (
            entry["agree"] / entry["comparisons"] if entry["comparisons"]
            else None)
    return table


def load_economics(exp_dir: Path) -> list[dict]:
    rows = []
    for path in sorted((exp_dir / "runs").rglob("economics.json")):
        try:
            rows.append(json.loads(path.read_text()))
        except ValueError:
            continue
    return rows


def summarize_judgments(records: list[dict]) -> dict:
    """{dim: {writer, vanilla, tie}}, {task: {...}}, {category: {...}}."""
    by_dim: dict = {}
    by_task: dict = {}
    by_category: dict = {}
    for record in records:
        label = record.get("winner_label")
        if label not in ("writer", "vanilla", "tie"):
            continue
        dim = record.get("dim", "unknown")
        task = record.get("task", "unknown")
        category = common.CATEGORIES.get(task, "other")
        for bucket, key in ((by_dim, dim), (by_task, task),
                            (by_category, category)):
            entry = bucket.setdefault(
                key, {"writer": 0, "vanilla": 0, "tie": 0})
            entry[label] += 1
    return {"by_dim": by_dim, "by_task": by_task,
            "by_category": by_category}


def _median(values: list) -> float | None:
    numbers = [v for v in values if isinstance(v, (int, float))]
    return statistics.median(numbers) if numbers else None


def summarize_economics(rows: list[dict]) -> dict:
    """Medians per arm + Writer/Vanilla ratios. Nulls stay null."""
    arms = {}
    for arm in ("vanilla", "writer"):
        subset = [r for r in rows if r.get("arm") == arm]
        arms[arm] = {
            "n": len(subset),
            "median_total_tokens": _median(
                [r.get("total_tokens") for r in subset]),
            "median_cost_usd": _median(
                [r.get("cost_usd") for r in subset]),
            "median_elapsed_s": _median(
                [r.get("elapsed_s") for r in subset]),
            "median_output_words": _median(
                [r.get("output_words") for r in subset]),
            "median_drafts": _median(
                [r.get("drafts") for r in subset]),
            "median_subagents": _median([
                r.get("subagent_attributions") for r in subset]),
        }
    ratios = {}
    for key in ("median_total_tokens", "median_cost_usd",
                "median_elapsed_s"):
        vanilla, writer = arms["vanilla"][key], arms["writer"][key]
        ratios[key.replace("median_", "writer_over_vanilla_")] = (
            writer / vanilla if isinstance(writer, (int, float))
            and isinstance(vanilla, (int, float)) and vanilla else None)
    return {"arms": arms, "ratios": ratios}


def summarize_quality(records: list[dict]) -> dict:
    """Invalid/retry/warning accounting for the model judge.

    Invalid means "no usable verdict": never silently counted as a tie.
    """
    invalid = [r for r in records if r.get("invalid") or not r.get(
        "winner_label")]
    retried = [r for r in records if r.get("retried")]
    reasons: dict = {}
    for record in invalid:
        reason = str(record.get("error") or "unknown")
        reasons[reason] = reasons.get(reason, 0) + 1
    warnings: dict = {}
    for record in records:
        for warning in record.get("warnings") or []:
            warnings[warning] = warnings.get(warning, 0) + 1
        if record.get("warning"):
            key = record["warning"]
            warnings[key] = warnings.get(key, 0) + 1
    return {"total": len(records), "valid": len(records) - len(invalid),
            "invalid": len(invalid), "retried": len(retried),
            "invalid_reasons": reasons, "warnings": warnings,
            "invalid_records": [
                {"task": r.get("task"), "pair": r.get("pair"),
                 "dim": r.get("dim"), "error": r.get("error"),
                 "attempts_used": r.get("attempts_used")}
                for r in invalid]}


def write_export_csv(exp_dir: Path, model: list[dict],
                     human: list[dict]) -> Path:
    path = exp_dir / "export.csv"
    fields = ["experiment_id", "task", "category", "pair", "dim",
              "judge_kind", "judge_name", "author_model", "judge_model",
              "family_match", "seed", "winner_label", "confidence",
              "tags", "reasoning", "evidence", "evidence_matched_side",
              "invalid", "retried", "attempts_used", "swapped", "warnings"]
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields,
                                extrasaction="ignore")
        writer.writeheader()
        for record in model + human:
            row = dict(record)
            row["category"] = common.CATEGORIES.get(
                record.get("task", ""), "other")
            tags = row.get("tags") or []
            row["tags"] = ";".join(tags)
            row["warnings"] = ";".join(row.get("warnings") or [])
            writer.writerow(row)
    return path


def write_judgments_jsonl(exp_dir: Path, records: list[dict]) -> Path:
    """One row per judgment attempt, valid and invalid alike.

    The JSONL is the audit trail: excluded verdicts stay visible so a
    reader can see what the judge did with every comparison, not only the
    ones that produced a usable winner.
    """
    path = exp_dir / "judgments.jsonl"
    rows = []
    for record in records:
        base = {key: record.get(key) for key in
                ("experiment_id", "task", "pair", "dim", "judge_kind",
                 "judge_model", "author_model", "invalid", "retried",
                 "attempts_used", "winner", "winner_label", "confidence",
                 "tags", "evidence", "evidence_matched_side", "error",
                 "family_match", "swapped", "warnings")}
        attempts = record.get("attempts") or []
        if not attempts:
            rows.append({**base, "attempt": None, "frame_id":
                         record.get("frame_id"),
                         "attempt_valid": not base["invalid"]})
            continue
        for attempt in attempts:
            rows.append({**base, "attempt": attempt.get("attempt"),
                         "frame_id": attempt.get("frame_id"),
                         "attempt_valid": bool(attempt.get("valid")),
                         "attempt_winner": attempt.get("winner"),
                         "attempt_error": attempt.get("error"),
                         "attempt_evidence": attempt.get("evidence"),
                         "attempt_reasoning": attempt.get("reasoning"),
                         "attempt_elapsed_s": attempt.get("judge_elapsed_s"),
                         "attempt_exit": attempt.get("judge_exit")})
    with path.open("w") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")
    return path


def write_economics_csv(exp_dir: Path, rows: list[dict]) -> Path:
    path = exp_dir / "economics.csv"
    fields = ["experiment_id", "task", "arm", "run", "input_tokens",
              "output_tokens", "total_tokens", "cost_usd",
              "telemetry_method", "assistant_messages",
              "subagent_attributions", "subagent_dirs", "elapsed_s",
              "exit", "timed_out", "output_words", "length_target",
               "length_in_range", "sources", "claims_extracted",
               "claims_verified", "claims_unverified", "claims_failed",
               "claims_high_unsupported", "drafts", "revisions",
               "comparisons", "exec_checks", "exec_failed",
               "framings_proposed", "framing_selected", "framing_components"]
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields,
                                extrasaction="ignore")
        writer.writeheader()
        for record in sorted(rows, key=lambda r: (
                r.get("task", ""), r.get("arm", ""), r.get("run", 0))):
            row = dict(record)
            target = row.get("length_target")
            row["length_target"] = (
                f"{target[0]}-{target[1]}" if target else None)
            writer.writerow(row)
    return path


def render_report(manifest: dict, summary: dict, human_summary: dict,
                  econ: dict, econ_rows: list[dict],
                  export_path: Path, econ_path: Path,
                  exp_dir: Path, quality: dict,
                  agreement: dict, jsonl_path: Path) -> str:
    """Concise report: counts by criterion, task splits, economics."""
    lines = [f"# Experiment {manifest['experiment_id']}", "",
             f"Model: {manifest['author_model']} | "
             f"Judge: {manifest.get('judge_model')} | "
             f"Runs/arm: {manifest['runs_per_arm']} | "
             f"Tasks: {len(manifest['tasks'])}",
             f"Commit: {manifest.get('git_commit')} | "
             f"Dirty: {manifest.get('git_dirty')} | "
             f"Behavior: {manifest.get('behavior_version')} | "
             f"Benchmark: {manifest.get('benchmark_version')}"]
    if manifest.get("git_dirty"):
        lines.append(
            "WARNING: this experiment ran against an uncommitted working "
            "tree; the commit does not describe the behavior (see "
            "behavior.md).")
    if quality["warnings"]:
        for warning, count in sorted(quality["warnings"].items()):
            lines.append(f"WARNING ({count}x): {warning}")
    if quality["invalid"]:
        lines.append(
            f"NOTE: {quality['invalid']} of {quality['total']} comparisons "
            f"produced no usable verdict (never counted as ties); "
            f"{quality['retried']} needed a retry.")
    lines.append("")
    lines.append("## Model judgments by criterion (no global score)")
    for dim_key, _ in common.DIMENSIONS:
        counts = summary["by_dim"].get(dim_key, {})
        lines.append(
            f"\n### {dim_key}\nWriter wins: {counts.get('writer', 0)}\n"
            f"Vanilla wins: {counts.get('vanilla', 0)}\n"
            f"Ties: {counts.get('tie', 0)}")
    lines.append("\n## By task")
    for task in manifest["tasks"]:
        counts = summary["by_task"].get(task, {})
        lines.append(
            f"{task}: Writer {counts.get('writer', 0)} / "
            f"Vanilla {counts.get('vanilla', 0)} / "
            f"Tie {counts.get('tie', 0)}")
    lines.append("\n## By category")
    for category, counts in sorted(summary["by_category"].items()):
        lines.append(
            f"{category}: Writer {counts.get('writer', 0)} / "
            f"Vanilla {counts.get('vanilla', 0)} / "
            f"Tie {counts.get('tie', 0)}")
    if human_summary["by_dim"]:
        lines.append("\n## Human judgments by criterion")
        for dim_key, counts in sorted(human_summary["by_dim"].items()):
            lines.append(
                f"{dim_key}: Writer {counts.get('writer', 0)} / "
                f"Vanilla {counts.get('vanilla', 0)} / "
                f"Tie {counts.get('tie', 0)}")
    lines.append("\n## Economics (medians)")
    for arm in ("vanilla", "writer"):
        medians = econ["arms"][arm]
        lines.append(
            f"{arm}: n={medians['n']} tokens={medians['median_total_tokens']} "
            f"cost={medians['median_cost_usd']} "
            f"time={medians['median_elapsed_s']}s "
            f"words={medians['median_output_words']} "
            f"drafts={medians['median_drafts']} "
            f"subagents={medians['median_subagents']}")
    lines.append("\n## Ratios (Writer / Vanilla)")
    for key, value in econ["ratios"].items():
        lines.append(f"{key}: {value}")
    unavailable = sorted({method for method in
                          (r.get("telemetry_method") for r in econ_rows)
                          if method and method != "events"})
    if unavailable:
        lines.append("\n## Telemetry notes")
        lines.append("Non-event telemetry sources used: "
                     + ", ".join(unavailable))
        lines.append("Nulls mean Prime did not expose the metric.")
    if quality["invalid_records"]:
        lines.append("\n## Invalid comparisons (no verdict recorded)")
        for row in quality["invalid_records"]:
            lines.append(
                f"- {row['task']} pair {row['pair']} {row['dim']} "
                f"(attempts={row['attempts_used']}): {row['error']}")
    if agreement:
        lines.append("\n## Inter-judge agreement (model vs human)")
        for dim_key, entry in sorted(agreement.items()):
            rate = entry["agreement_rate"]
            lines.append(
                f"{dim_key}: {entry['agree']}/{entry['comparisons']} agree"
                + (f" ({rate:.0%})" if rate is not None else ""))
        lines.append("Only dimensions where model and human judged the same "
                     "comparison appear here; n=0 dimensions are omitted "
                     "rather than assumed.")
    lines.append(f"\nExports: {export_path.name}, {econ_path.name}, "
                 f"{jsonl_path.name} (per-judgment, per-run, and "
                 "per-attempt rows for correlation exploration: drafts vs "
                 "outcome, tokens vs outcome, retries vs outcome, etc.)")
    return "\n".join(lines) + "\n"


def summarize_experiment(exp_dir: Path) -> Path:
    """Load everything, write report.md + CSVs, return the report path."""
    manifest = json.loads((exp_dir / "manifest.json").read_text())
    all_records = load_all_model_judgments(exp_dir)
    model = [r for r in all_records if r.get("winner_label")]
    human = load_human_judgments(exp_dir)
    econ_rows = load_economics(exp_dir)
    summary = summarize_judgments(model)
    human_summary = summarize_judgments(human)
    econ = summarize_economics(econ_rows)
    quality = summarize_quality(all_records)
    agreement = agreement_table(model, human)
    export_path = write_export_csv(exp_dir, model, human)
    econ_path = write_economics_csv(exp_dir, econ_rows)
    jsonl_path = write_judgments_jsonl(exp_dir, all_records)
    report = render_report(manifest, summary, human_summary, econ,
                           econ_rows, export_path, econ_path, exp_dir,
                           quality, agreement, jsonl_path)
    path = exp_dir / "report.md"
    path.write_text(report)
    return path
