"""Shared constants and helpers for the V1.1 evaluation loop.

V1 `run.py` commands are preserved untouched; everything here is imported
by the new `experiment`/`judge`/`human-judge`/`summarize`/`selftest`
subcommands. No writing capabilities live here — only measurement.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
TASKS = HERE / "tasks"
RUNS = HERE / "runs"
EXPERIMENTS = HERE / "experiments"
REPO = HERE.parent.parent
WRITER_SKILLS = [
    REPO / "skills" / name for name in (
        "writer", "technical-writing", "research", "editorial-critique",
        "technical-verification", "voice")
]
PROMPTS = REPO / "writer" / "prompts"

BENCHMARK_VERSION = "v1.2"
ARMS = ("vanilla", "writer")

# Task -> reporting category.
CATEGORIES = {
    "explainer": "explainers",
    "tutorial": "tutorials",
    "architecture": "architecture",
    "argument": "argument",
    "product-education": "education",
    "comparison": "comparison",
    "editing": "editing",
    "shortening": "editing",
    "complex-concept": "explainers",
    "thesis": "argument",
    "jev-explainer": "explainers",
}

# Seven independent editorial dimensions. Never combined into one score.
DIMENSIONS = (
    ("continuation",
     "Which article would an experienced member of the stated audience "
     "be more likely to voluntarily continue reading?"),
    ("usefulness",
     "Which article is more useful to the stated audience?"),
    ("specificity",
     "Which article contains more concrete, specific, useful information "
     "without unnecessary filler?"),
    ("credibility",
     "Which article demonstrates stronger technical credibility and "
     "appropriate precision?"),
    ("distinctiveness",
     "Which article feels more distinctive, less generic, and less "
     "interchangeable with typical AI-generated technical content?"),
    ("brief",
     "Which article better fulfills the actual brief and constraints?"),
    ("framing",
     "Which version gives the target reader a stronger and more useful "
     "mental model for understanding the subject?"),
)

# Extensible failure taxonomy for loss tags (judges may add new tags).
FAILURE_TAGS = (
    "generic-opening", "overwritten", "too-long", "too-polished",
    "weak-angle", "weak-structure", "factual-problem", "too-much-context",
    "repetitive", "boring", "poor-examples", "over-researched",
    "under-researched", "missed-brief",
)


def task_names() -> list[str]:
    return sorted(p.name for p in TASKS.iterdir() if (p / "task.md").exists())


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def family_of(selector: str | None) -> str | None:
    """Opaque family = provider segment. No vendor knowledge."""
    if not selector:
        return None
    return selector.split("/", 1)[0] or None


def task_brief(task: str) -> str:
    """The frozen task input both arms receive (task.md verbatim)."""
    return (TASKS / task / "task.md").read_text()


def expand_template(name: str, arguments: str) -> str:
    """Single-pass template expansion (argument values never re-scanned)."""
    raw = (PROMPTS / f"{name}.md").read_text()
    body = raw.split("---", 2)[2] if raw.startswith("---") else raw
    return re.sub(r"\$ARGUMENTS|\$@|\$1", lambda _m: arguments, body)


def build_prompt(task: str, arm: str) -> str:
    """Exact per-arm context (the input freeze — see INPUTS doc below).

    vanilla: task.md verbatim + one neutral closing line.
    writer: expanded /write template with task.md substituted.
    """
    brief = task_brief(task)
    if arm == "writer":
        return expand_template("write", brief)
    if arm == "vanilla":
        return (f"{brief}\n\nWrite the article. Your final message is the "
                "article text.")
    raise ValueError("arm must be vanilla or writer")


#: What each arm receives (kept in code so the freeze is auditable).
INPUTS_DOC = """\
vanilla arm receives: tasks/<t>/task.md verbatim, plus the single line
"Write the article. Your final message is the article text." No Writer
skills, no Writer prompt templates, no editorial guidance.

writer arm receives: writer/prompts/write.md with $ARGUMENTS replaced by
tasks/<t>/task.md verbatim, plus --skill flags for the six Writer skills
and --prompt-template for writer/prompts. The harness capabilities in
write.md are the only additional context.

Both arms: same --model selector, same --thinking level, same timeout,
fresh isolated workdir, isolated PRIME_AGENT_CODING_AGENT_DIR and
PRIME_AGENT_SESSION_DIR under the experiment directory.
"""


def parse_length_target(task_md: str) -> tuple[int, int] | None:
    """First `N–M words` range in the brief, else None (never guessed)."""
    match = re.search(r"(\d[\d,]*)\s*[–-]\s*(\d[\d,]*)\s*words", task_md)
    if not match:
        return None
    return (int(match.group(1).replace(",", "")),
            int(match.group(2).replace(",", "")))


def word_count(text: str) -> int:
    return len(text.split())


def task_input_hashes(task: str) -> dict:
    """Hashes proving both arms saw identical task inputs."""
    return {"task.md": sha256_file(TASKS / task / "task.md")}


def harness_hashes() -> dict:
    """Hashes of every Writer-side context file (the harness delta)."""
    files = {"prompts/write.md": PROMPTS / "write.md"}
    for skill in ("writer", "technical-writing", "research",
                  "editorial-critique", "technical-verification", "voice"):
        files[f"skills/{skill}/SKILL.md"] = REPO / "skills" / skill / "SKILL.md"
    return {key: sha256_file(path) for key, path in files.items()}


#: Everything that can change Writer behavior without changing the task
#: input: prompt templates, skills, and the framing implementation.
BEHAVIOR_FILES = {
    "skills/editorial-framing/SKILL.md": REPO / "skills" / "editorial-framing" / "SKILL.md",
    "crates/pa-writer/src/framing.rs": REPO / "crates" / "pa-writer" / "src" / "framing.rs",
    "skills/writer/src/writer/_framing.py": REPO / "skills" / "writer" / "src" / "writer" / "_framing.py",
}


def behavior_hashes() -> dict:
    """Hashes of the behavior-defining files: the freeze plus framing.

    `behavior_version` is the digest of this map, so a results report can
    state which Writer behavior produced the numbers even when the git
    commit is a dirty tree that does not describe the run.
    """
    files = {f"prompts/{path.name}": path
             for path in sorted(PROMPTS.glob("*.md"))}
    for skill in ("writer", "technical-writing", "research",
                  "editorial-critique", "technical-verification", "voice"):
        files[f"skills/{skill}/SKILL.md"] = REPO / "skills" / skill / "SKILL.md"
    files.update(BEHAVIOR_FILES)
    return {key: sha256_file(path) for key, path in files.items()}


def behavior_version() -> str:
    """Short digest of `behavior_hashes` — the behavior freeze identifier."""
    return hashlib.sha256(
        json.dumps(behavior_hashes(), sort_keys=True).encode()).hexdigest()[:16]

