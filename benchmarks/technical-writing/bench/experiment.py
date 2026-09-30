"""Experiment orchestration: manifest, isolated runs, economics capture.

Layout:
  experiments/<exp-id>/
    manifest.json
    prime-home/            isolated PRIME_AGENT_CODING_AGENT_DIR
    sessions/              isolated PRIME_AGENT_SESSION_DIR
    runs/<task>/<arm>/run-<k>/
      prompt.md events.jsonl stderr.txt meta.json economics.json output.md
"""

from __future__ import annotations

import hashlib
import json
import random
import shutil
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

from . import common
from .common import ARMS
from . import economics


def new_experiment_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return f"exp-{stamp}-{random.SystemRandom().randrange(16**4):04x}"


def git_commit() -> str | None:
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=common.REPO,
            capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return None
    return proc.stdout.strip() or None


def git_dirty() -> bool | None:
    """True when tracked files differ from HEAD (unknown if git fails)."""
    try:
        proc = subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=no"],
            cwd=common.REPO, capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
    return any(line.strip() for line in proc.stdout.splitlines())


def git_diff_sha256() -> str | None:
    """Digest of the uncommitted diff, so a dirty manifest is still
    reproducible: commit + diff digest reconstructs the behavior tree."""
    try:
        proc = subprocess.run(
            ["git", "diff", "HEAD"], cwd=common.REPO,
            capture_output=True, text=True, timeout=120)
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
    return hashlib.sha256(proc.stdout.encode()).hexdigest()


def prime_version(prime_bin: str) -> str | None:
    try:
        proc = subprocess.run(
            [prime_bin, "--version"], capture_output=True, text=True,
            timeout=60)
    except (OSError, subprocess.SubprocessError):
        return None
    output = (proc.stdout + proc.stderr).strip().splitlines()
    return output[0] if output else None


#: Cheapest possible round trip: a model that cannot answer this is not
#: ready to author 66 articles or judge 231 comparisons.
PROBE_PROMPT = "Reply with exactly the word OK and nothing else."


def probe_model(prime: str, model: str | None, timeout_s: int) -> dict:
    """Readiness probe for one model selector.

    Returns a verdict dict; never raises for a missing model, so a caller
    can report every role's status in one pass instead of stopping at the
    first failure.
    """
    cmd = [prime, "-p", PROBE_PROMPT]
    if model:
        cmd += ["--model", model]
    start = time.time()
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True,
                              timeout=timeout_s)
    except subprocess.TimeoutExpired:
        return {"model": model, "ready": False,
                "error": f"no response within {timeout_s}s"}
    except (OSError, subprocess.SubprocessError) as exc:
        return {"model": model, "ready": False, "error": str(exc)}
    elapsed = round(time.time() - start, 1)
    stdout = (proc.stdout or "").strip()
    stderr = (proc.stderr or "").strip()
    ready = proc.returncode == 0 and "OK" in stdout.upper()
    error = None
    if not ready:
        error = (f"exit={proc.returncode} stdout={stdout[:200]!r} "
                 f"stderr={stderr[:200]!r}")
    return {"model": model, "ready": ready, "elapsed_s": elapsed,
            "exit": proc.returncode, "stdout": stdout[:200], "error": error}


def harness_version() -> str:
    import re

    text = (common.REPO / "crates" / "pa-writer" / "Cargo.toml").read_text()
    match = re.search(r'version\.workspace\s*=\s*true', text)
    root = (common.REPO / "Cargo.toml").read_text()
    version = re.search(r'^version\s*=\s*"([^"]+)"', root, re.M)
    return ("pa-writer@" + version.group(1)) if version else "pa-writer@unknown"


def build_manifest(exp_id: str, tasks: list[str], author_model: str | None,
                   thinking: str | None, runs: int, seed: int,
                   prime_bin: str, judge_model: str | None) -> dict:
    return {
        "experiment_id": exp_id,
        "benchmark_version": common.BENCHMARK_VERSION,
        "behavior_version": common.behavior_version(),
        "behavior_hashes": common.behavior_hashes(),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "git_commit": git_commit(),
        "git_dirty": git_dirty(),
        "git_diff_sha256": git_diff_sha256(),
        "harness_version": harness_version(),
        "prime_version": prime_version(prime_bin),
        "prime_bin": prime_bin,
        "tasks": tasks,
        "arms": list(ARMS),
        "runs_per_arm": runs,
        "author_model": author_model,
        "author_family": common.family_of(author_model),
        "thinking": thinking,
        "judge_model": judge_model,
        "judge_family": common.family_of(judge_model),
        "base_seed": seed,
        "task_input_hashes": {t: common.task_input_hashes(t) for t in tasks},
        "harness_hashes": common.harness_hashes(),
        "writer_policy": {
            "writer": {"model": "inherit"},
            "critic": {"strategy": "different-family-if-available"},
            "verification": {"strategy": "reasoning"},
            "framing": {"strategy": "editorial-framing-skill"},
        },
        "inputs_doc": common.INPUTS_DOC,
    }


def capture_behavior(exp_dir: Path, manifest: dict) -> Path:
    """Write behavior.md: what Writer could do during this experiment.

    Recorded next to the numbers so a report never implies a behavior the
    run did not have, and so a reviewer can diff two experiments' behavior
    without rerunning either.
    """
    dirty = manifest.get("git_dirty")
    lines = [
        f"# Behavior freeze — {manifest['experiment_id']}",
        "",
        f"benchmark_version: {manifest.get('benchmark_version')}",
        f"behavior_version: {manifest.get('behavior_version')}",
        f"harness_version: {manifest.get('harness_version')}",
        f"prime_version: {manifest.get('prime_version')}",
        f"git_commit: {manifest.get('git_commit')}",
        f"git_dirty: {dirty}",
        f"git_diff_sha256: {manifest.get('git_diff_sha256')}",
        f"author_model: {manifest.get('author_model')}",
        f"judge_model: {manifest.get('judge_model')}",
        f"thinking: {manifest.get('thinking')}",
        "",
        "## Arms",
        "",
        common.INPUTS_DOC,
        "",
        "## Writer-side files (behavior-defining hashes)",
        "",
    ]
    for key, digest in sorted(manifest.get("behavior_hashes", {}).items()):
        lines.append(f"- {key}: {digest}")
    lines += [
        "",
        "## Task input hashes (identical across arms)",
        "",
    ]
    for task, hashes in sorted(manifest.get("task_input_hashes", {}).items()):
        lines.append(f"- {task}/task.md: {hashes['task.md']}")
    if dirty:
        lines += [
            "",
            "NOTE: this experiment ran against an uncommitted working tree.",
            "The commit above does not describe the behavior; the diff digest",
            "and behavior_version do. Re-run with a frozen commit to remove",
            "this caveat.",
        ]
    exp_dir.mkdir(parents=True, exist_ok=True)
    path = exp_dir / "behavior.md"
    path.write_text("\n".join(lines) + "\n")
    return path



def pair_seed(manifest: dict, task: str, pair: int, dim: str) -> int:
    """Independent randomization seed per comparison."""
    digest = hashlib.sha256(
        f"{manifest['base_seed']}/{task}/{pair}/{dim}".encode()).digest()
    return int.from_bytes(digest[:8], "big")


def find_prime(explicit: str | None) -> str:
    if explicit:
        return explicit
    found = shutil.which("prime-agent")
    if found:
        return found
    raise SystemExit("no prime-agent binary: pass --prime-bin or install prime-agent")


def author_command(prime: str, prompt: str, arm: str,
                   author_model: str | None, thinking: str | None) -> list[str]:
    cmd = [prime, "--mode", "json", "-p", prompt]
    if author_model:
        cmd += ["--model", author_model]
    if thinking:
        cmd += ["--thinking", thinking]
    if arm == "writer":
        for skill in common.WRITER_SKILLS:
            cmd += ["--skill", str(skill)]
        cmd += ["--prompt-template", str(common.PROMPTS)]
    return cmd


def extract_output(events_path: Path, sessions_dir: Path,
                   session_id: str | None) -> tuple[str, str]:
    """Recover the article text: last assistant message in events, else
    session-file fallback. Returns (text, method). Never synthesized."""
    text = _last_assistant_text(_iter_event_messages(events_path))
    if text:
        return (text, "events-last-assistant")
    session_file = economics.find_session_file(sessions_dir, session_id)
    if session_file is not None:
        text = _last_assistant_text(_iter_session_messages(session_file))
        if text:
            return (text, "session-file-last-assistant")
    return ("", "missing")


def _iter_event_messages(events_path: Path):
    if not events_path.exists():
        return
    for line in events_path.read_text().splitlines():
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if (isinstance(event, dict)
                and event.get("type") == "message_end"
                and isinstance(event.get("message"), dict)
                and event["message"].get("role") == "assistant"):
            yield event["message"]


def _iter_session_messages(session_file: Path):
    for line in session_file.read_text().splitlines():
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
        except ValueError:
            continue
        for message in _entry_messages(entry):
            if message.get("role") == "assistant":
                yield message


def _entry_messages(entry) -> list:
    if isinstance(entry, dict):
        if entry.get("role") in ("assistant", "user"):
            return [entry]
        if isinstance(entry.get("message"), dict):
            return _entry_messages(entry["message"])
        messages = entry.get("messages")
        if isinstance(messages, list):
            return [m for m in messages if isinstance(m, dict)]
    return []


def message_text(message: dict) -> str:
    """Text parts of an assistant message (thinking/code parts excluded)."""
    content = message.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if not isinstance(block, dict):
                continue
            if block.get("type") in ("text",) and isinstance(
                    block.get("text"), str):
                parts.append(block["text"])
            elif isinstance(block.get("content"), str) and block.get(
                    "type", "") != "thinking":
                parts.append(block["content"])
        return "\n".join(parts).strip()
    return ""


def _last_assistant_text(messages) -> str:
    last = ""
    for message in messages:
        text = message_text(message)
        if text:
            last = text
    return last


def run_one(prime: str, exp_dir: Path, manifest: dict, task: str, arm: str,
            run_index: int, timeout_s: int, dry_run: bool = False) -> Path:
    """Execute one authoring run; returns its directory."""
    run_dir = exp_dir / "runs" / task / arm / f"run-{run_index}"
    run_dir.mkdir(parents=True, exist_ok=True)
    prompt = common.build_prompt(task, arm)
    (run_dir / "prompt.md").write_text(prompt)
    cmd = author_command(prime, prompt, arm, manifest["author_model"],
                         manifest["thinking"])
    (run_dir / "command.txt").write_text(" ".join(cmd) + "\n")
    workdir = run_dir / "workdir"
    workdir.mkdir(exist_ok=True)
    env = {
        "PRIME_AGENT_CODING_AGENT_DIR": str(exp_dir / "prime-home"),
        "PRIME_AGENT_SESSION_DIR": str(exp_dir / "sessions"),
    }
    if dry_run:
        (run_dir / "meta.json").write_text(json.dumps(
            {"dry_run": True, "command": cmd}, indent=2))
        return run_dir
    import os

    merged = dict(os.environ)
    merged.update(env)
    start = time.time()
    try:
        proc = subprocess.run(cmd, cwd=workdir, capture_output=True,
                              text=True, timeout=timeout_s, env=merged)
        elapsed = time.time() - start
        exit_code, stderr, timed_out = proc.returncode, proc.stderr, False
        (run_dir / "events.jsonl").write_text(proc.stdout)
    except subprocess.TimeoutExpired as exc:
        elapsed = time.time() - start
        exit_code, timed_out = 124, True
        partial = (exc.stdout or b"").decode(errors="replace") if isinstance(
            exc.stdout, bytes) else (exc.stdout or "")
        (run_dir / "events.jsonl").write_text(partial)
        stderr = (exc.stderr or "")
    (run_dir / "stderr.txt").write_text(stderr or "")
    events = economics.parse_events(run_dir / "events.jsonl")
    sessions_dir = exp_dir / "sessions"
    output_text = ""
    output_method = "missing"
    if not timed_out and exit_code == 0:
        output_text, output_method = extract_output(
            run_dir / "events.jsonl", sessions_dir, events.get("session_id"))
    (run_dir / "output.md").write_text(output_text)
    economics_path = collect_economics(
        manifest["experiment_id"], exp_dir, run_dir, task, arm, run_index,
        events, sessions_dir, workdir, elapsed, exit_code, timed_out,
        output_method)
    (run_dir / "meta.json").write_text(json.dumps({
        "experiment_id": manifest["experiment_id"], "task": task, "arm": arm,
        "run": run_index, "model": manifest["author_model"],
        "elapsed_s": round(elapsed, 1), "exit": exit_code,
        "timed_out": timed_out,
        "session_id": events.get("session_id"),
        "output_method": output_method,
        "output_words": common.word_count(output_text),
        "economics": economics_path.name,
    }, indent=2) + "\n")
    return run_dir


def collect_economics(experiment_id: str, exp_dir: Path, run_dir: Path,
                      task: str, arm: str, run_index: int,
                      events: dict, sessions_dir: Path, workdir: Path,
                      elapsed: float, exit_code: int, timed_out: bool,
                      output_method: str) -> Path:
    """Merge Prime telemetry + Writer ledger metrics into economics.json."""
    session_file = economics.find_session_file(
        sessions_dir, events.get("session_id"))
    fallback = economics.parse_session_file(session_file)
    # Prefer events; fall back to session file when events carry nothing.
    if events.get("total_tokens", 0) > 0:
        telemetry, telemetry_method = events, events.get("method")
    elif fallback.get("total_tokens", 0) > 0:
        telemetry, telemetry_method = fallback, "session-file-fallback"
    else:
        telemetry, telemetry_method = events, events.get("method")
    output_text = (run_dir / "output.md").read_text()
    target = common.parse_length_target(common.task_brief(task))
    words = common.word_count(output_text)
    # Missing output is not "out of range" — it is missing (null).
    in_range = (target[0] <= words <= target[1]
                if target and output_text.strip() else None)
    writer = economics.writer_metrics(workdir) if arm == "writer" else {
        "sources": None, "claims_extracted": None, "claims_verified": None,
        "claims_unverified": None, "claims_failed": None,
        "claims_high_unsupported": None, "drafts": None, "revisions": None,
        "comparisons": None, "exec_checks": None, "exec_failed": None,
        "method": "not-applicable-vanilla",
    }
    record = {
        "experiment_id": experiment_id, "task": task, "arm": arm,
        "run": run_index,
        "input_tokens": events.get("input_tokens") if events.get(
            "total_tokens", 0) > 0 else fallback.get("input_tokens"),
        "output_tokens": events.get("output_tokens") if events.get(
            "total_tokens", 0) > 0 else fallback.get("output_tokens"),
        "total_tokens": telemetry.get("total_tokens"),
        "cost_usd": telemetry.get("cost_usd"),
        "telemetry_method": telemetry_method,
        "telemetry_unavailable": [
            key for key, value in
            (("input_tokens", telemetry.get("input_tokens")),
             ("output_tokens", telemetry.get("output_tokens")),
             ("total_tokens", telemetry.get("total_tokens")),
             ("cost_usd", telemetry.get("cost_usd"))) if not value],
        "assistant_messages": events.get("assistant_messages"),
        "subagent_attributions": fallback.get("subagent_attributions"),
        "attributed_models": fallback.get("attributed_models"),
        "subagent_dirs": economics.count_subagent_dirs(
            exp_dir / "prime-home"),
        "elapsed_s": round(elapsed, 1),
        "exit": exit_code, "timed_out": timed_out,
        "output_words": words,
        "length_target": list(target) if target else None,
        "length_in_range": in_range,
        "citation_urls": economics.citation_urls(output_text),
        **writer,
    }
    path = run_dir / "economics.json"
    path.write_text(json.dumps(record, indent=2) + "\n")
    return path
