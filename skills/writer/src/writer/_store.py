"""Shared file-backed helpers for the Writer harness skill.

Same on-disk format as the `pa-writer` Rust crate. Resolution:
`$WRITER_DIR` wins, else `<cwd>/writing`.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

WRITER_DIR_NAME = "writing"

#: Pre-rename state directory. Auto-migrated on open (see `_migrate`).
LEGACY_DIR_NAME = ".writer"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _root(explicit: str | Path | None = None) -> Path:
    if explicit is not None:
        return Path(explicit)
    override = os.environ.get("WRITER_DIR", "").strip()
    if override:
        return Path(override)
    return _migrate(Path.cwd() / WRITER_DIR_NAME)


def _migrate(base: Path) -> Path:
    """Rename a legacy `.writer/` project into `writing/` on first open.

    Only when the new location has no project yet; when both exist the
    new one wins and nothing is merged. A failed rename (permissions,
    cross-mount) keeps serving the legacy directory rather than losing
    data. Explicit roots are never touched.
    """
    if (base / "project.json").exists():
        return base
    legacy = base.parent / LEGACY_DIR_NAME
    if (legacy / "project.json").exists():
        try:
            legacy.rename(base)
        except OSError:
            return legacy
    return base


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text())


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp-writer")
    tmp.write_text(json.dumps(value, indent=2) + "\n")
    tmp.replace(path)


def _append_jsonl(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as fh:
        fh.write(json.dumps(value) + "\n")


def _next_id(items: list[dict], prefix: str, width: int = 3) -> str:
    peak = 0
    for item in items:
        raw = str(item.get("id", ""))
        if raw.startswith(prefix + "-"):
            try:
                peak = max(peak, int(raw[len(prefix) + 1 :]))
            except ValueError:
                continue
    return f"{prefix}-{peak + 1:0{width}d}"
