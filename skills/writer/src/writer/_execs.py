"""Executable verification hooks for the Writer harness.

Runs shell commands / code samples via the kernel sandbox (same trust
posture as Prime's `bash` tool: user permissions, not a security
sandbox) and persists `{label, command, exit_status, stdout, stderr}`
records to `traces/exec.jsonl`. Optionally links the record to a claim
(`exec_ref`) so evidence-gated verification can cite it.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from ._store import _append_jsonl, _now, _read_json, _root, _write_json

_OUTPUT_LIMIT = 2000


def _next_exec_id(base: Path) -> str:
    path = base / "traces/exec.jsonl"
    peak = 0
    if path.exists():
        for line in path.read_text().splitlines():
            if not line.strip():
                continue
            try:
                raw = json.loads(line).get("id", "")
            except ValueError:
                continue
            if raw.startswith("exec-"):
                try:
                    peak = max(peak, int(raw[5:]))
                except ValueError:
                    continue
    return f"exec-{peak + 1:03d}"


def exec_check(label: str, command: str, timeout_s: int = 30,
               claim_id: str | None = None,
               root: str | Path | None = None,
               cwd: str | Path | None = None) -> dict:
    """Run `command`, persist the record, optionally link it to a claim.

    Never raises on command failure: a failing check is data (the claim
    it backs should end `failed`/`unsupported`, not crash the run).
    """
    base = _root(root)
    try:
        completed = subprocess.run(
            command, shell=True, capture_output=True, text=True,
            timeout=timeout_s, cwd=cwd or Path.cwd(),
        )
        exit_status, stdout, stderr = (completed.returncode,
                                       completed.stdout or "",
                                       completed.stderr or "")
    except subprocess.TimeoutExpired as exc:
        exit_status = 124
        stdout = (exc.stdout or b"").decode(errors="replace") if isinstance(
            exc.stdout, bytes) else (exc.stdout or "")
        stderr = f"timed out after {timeout_s}s"
    record = {"id": _next_exec_id(base), "label": label, "command": command,
              "exit_status": exit_status,
              "stdout": stdout[-_OUTPUT_LIMIT:], "stderr": stderr[-_OUTPUT_LIMIT:],
              "elapsed_ms": 0, "created_at": _now()}
    _append_jsonl(base / "traces/exec.jsonl", record)
    if claim_id is not None:
        ledger = _read_json(base / "claims/ledger.json", [])
        for claim in ledger:
            if claim["id"] == claim_id:
                claim["exec_ref"] = record["id"]
                break
        else:
            raise KeyError(f"unknown claim {claim_id}")
        _write_json(base / "claims/ledger.json", ledger)
    return record


def exec_list(root: str | Path | None = None) -> list[dict]:
    """Read back exec records."""
    path = _root(root) / "traces/exec.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines()
            if line.strip()]
