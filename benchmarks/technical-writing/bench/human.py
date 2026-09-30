"""Human blind judging: interactive, labels revealed only after submit.

Same evidence contract as the model judge: a verdict is recorded only with a
verbatim span from the winning article, validated against the raw text
before the identity is unsealed. `skip` records an explicit abstention
instead of a guess.
"""

from __future__ import annotations

import json
from pathlib import Path

from . import common
from . import judge as judge_mod


def completed_pairs(exp_dir: Path, task: str) -> list[int]:
    """Pair indices with both arm outputs present and non-empty."""
    pairs = []
    index = 1
    while True:
        writer_out = exp_dir / "runs" / task / "writer" / f"run-{index}" / "output.md"
        vanilla_out = exp_dir / "runs" / task / "vanilla" / f"run-{index}" / "output.md"
        if not (writer_out.exists() and vanilla_out.exists()):
            return pairs
        if writer_out.read_text().strip() and vanilla_out.read_text().strip():
            pairs.append(index)
        index += 1


def run_human_judge(exp_dir: Path, manifest: dict, task: str,
                    judge_name: str, pairs: list[int] | None = None) -> None:
    import sys

    sys.path.insert(0, str(common.REPO / "skills" / "writer" / "src"))
    import writer

    available = completed_pairs(exp_dir, task)
    selected = [p for p in (pairs or available) if p in available]
    if not selected:
        raise SystemExit(f"no completed pairs for {task}")
    bench_root = exp_dir / "judge-state-human"
    for pair in selected:
        text_writer = (exp_dir / "runs" / task / "writer" / f"run-{pair}"
                       / "output.md").read_text()
        text_vanilla = (exp_dir / "runs" / task / "vanilla" / f"run-{pair}"
                        / "output.md").read_text()
        judgments: dict = {"experiment_id": manifest["experiment_id"],
                           "task": task, "pair": pair,
                           "judge_kind": "human", "judge_name": judge_name,
                           "author_model": manifest["author_model"],
                           "author_family": manifest["author_family"],
                           "dims": {}}
        for dim_key, criterion in common.DIMENSIONS:
            from .experiment import pair_seed

            seed = pair_seed(manifest, task, pair, f"human-{judge_name}-{dim_key}")
            frame = writer.blind_present(
                text_writer, text_vanilla, "writer", "vanilla", criterion,
                seed=seed, frame_id=f"{task}-p{pair}-human-{judge_name}-{dim_key}",
                root=bench_root)
            print(f"\n=== {task} pair {pair} — {dim_key} ===")
            print(f"Criterion: {criterion}\n")
            print("--- ARTICLE A ---\n")
            print(frame["first"])
            print("\n--- ARTICLE B ---\n")
            print(frame["second"])
            entry = _collect_verdict(
                frame["first"], frame["second"], f"{judge_name}")
            entry["frame_id"] = frame["frame_id"]
            entry["seed"] = seed
            entry["judge_kind"] = "human"
            judgments["dims"][dim_key] = entry
            if entry.get("skipped"):
                print("Skipped (explicit abstention, not a tie).")
                continue
            if entry.get("invalid"):
                print(f"Invalid: {entry['error']} — no winner recorded.")
                continue
            # Map presented A/B through the sealed frame (never shown above).
            frame_winner = {"A": "first", "B": "second",
                            "tie": "tie"}[entry["winner"]]
            resolved = writer.blind_resolve(
                frame["frame_id"], frame_winner,
                entry.get("notes") or f"human judgment by {judge_name}",
                entry.get("confidence"), root=bench_root)
            entry["winner_label"] = resolved["winner_label"]
            print(f"Recorded: {entry['winner']} "
                  f"(identity sealed until all done).")
        outdir = exp_dir / "judgments" / "human" / judge_name / task
        outdir.mkdir(parents=True, exist_ok=True)
        (outdir / f"pair-{pair}.json").write_text(
            json.dumps(judgments, indent=2) + "\n")
        # Reveal only after this pair is fully submitted and persisted.
        print(f"\nPair {pair} submitted. Mapping was: "
              f"{judgments['dims']} "
              f"(see file for per-dim winner_label).")


def _collect_verdict(text_a: str, text_b: str, judge_name: str) -> dict:
    """Ask for winner + evidence; validate the quote before it counts."""
    answer = _ask("Winner (A/B/tie/skip): ",
                  {"a": "A", "b": "B", "tie": "tie", "s": "skip", "skip": "skip"})
    if answer == "skip":
        return {"skipped": True, "winner": None, "winner_label": None,
                "judge_name": judge_name}
    confidence = _ask_float("Confidence 0-1 (blank to skip): ")
    print("Failure tags (comma-separated numbers, blank for none):")
    for number, tag in enumerate(common.FAILURE_TAGS, 1):
        print(f"  {number}. {tag}")
    tags = _ask_tags()
    notes = input("Freeform notes (blank to skip): ").strip()
    entry = {"winner": answer, "winner_label": None, "confidence": confidence,
             "tags": tags, "notes": notes, "judge_name": judge_name}
    evidence, error = _ask_evidence(text_a, text_b, answer)
    if error:
        entry.pop("winner")
        entry.update({"invalid": True, "error": error, "evidence": evidence})
        return entry
    entry["evidence"] = evidence
    return entry


def _ask_evidence(text_a: str, text_b: str, winner: str) -> tuple[str, str | None]:
    """One required quote, re-asked once; never accepted unvalidated."""
    last_error = None
    for _ in range(2):
        evidence = input(
            "Verbatim span (12-400 chars) copied from the article you "
            "judged better: ").strip()
        result = judge_mod.check_evidence(evidence, winner, text_a, text_b)
        if result["evidence_valid"]:
            return (evidence, None)
        last_error = result["evidence_error"]
        print(f"Rejected: {last_error}")
    return ("", last_error or "no evidence span supplied")


def _ask(prompt: str, mapping: dict) -> str:
    while True:
        answer = input(prompt).strip().lower()
        if answer in mapping:
            return mapping[answer]
        print("Please answer one of: " + "/".join(sorted(mapping)))


def _ask_float(prompt: str) -> float | None:
    while True:
        answer = input(prompt).strip()
        if not answer:
            return None
        try:
            value = max(0.0, min(1.0, float(answer)))
        except ValueError:
            print("Enter a number 0-1 or leave blank.")
            continue
        return value


def _ask_tags() -> list[str]:
    answer = input("Tags: ").strip()
    if not answer:
        return []
    tags = []
    for part in answer.split(","):
        part = part.strip().lower().replace(" ", "-")
        if part.isdigit() and 1 <= int(part) <= len(common.FAILURE_TAGS):
            tags.append(common.FAILURE_TAGS[int(part) - 1])
        elif part:
            tags.append(part)  # taxonomy is extensible
    return tags
