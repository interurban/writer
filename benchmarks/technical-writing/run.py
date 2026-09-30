#!/usr/bin/env python3
"""Harness comparison runner: same benchmark task, vanilla vs Writer.

Isolates model effect from harness effect by running one task under two
arms with the same primary model:

  A (vanilla): prime-agent -p "<brief>" with default skills (no Writer).
  B (writer):  prime-agent -p "/write <brief>" with Writer skills wired in.

Outputs and metadata persist separately under runs/<task>/<arm>/.
Requires a prime-agent binary and model credentials; --dry-run shows the
invocations without running. Judging uses the writer skill's blind
comparison (labels sealed until resolve) — no numeric scores.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
TASKS = HERE / "tasks"
RUNS = HERE / "runs"
REPO = HERE.parent.parent

sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "skills" / "writer" / "src"))

# V1.1: shared freeze/prompts live in bench.common; V1 command behavior
# below is unchanged (same names, same outputs).
from bench.common import (  # noqa: E402
    PROMPTS, WRITER_SKILLS, build_prompt, expand_template, task_names,
)


def find_prime(explicit: str | None) -> str:
    if explicit:
        return explicit
    found = shutil.which("prime-agent")
    if found:
        return found
    raise SystemExit("no prime-agent binary: pass --prime-bin or install prime-agent")


def cmd_run(args) -> None:
    prime = find_prime(args.prime_bin) if not args.dry_run else (
        args.prime_bin or "prime-agent")
    prompt = build_prompt(args.task, args.arm)
    outdir = RUNS / args.task / args.arm
    cmd = [prime, "-p", prompt]
    if args.model:
        cmd += ["--model", args.model]
    if args.arm == "writer":
        for skill in WRITER_SKILLS:
            cmd += ["--skill", str(skill)]
        cmd += ["--prompt-template", str(PROMPTS)]
    print("$", " ".join(cmd))
    print("cwd:", args.workdir or "<fresh tempdir>")
    if args.dry_run:
        return
    workdir = args.workdir or tempfile.mkdtemp(prefix=f"bench-{args.task}-{args.arm}-")
    start = time.time()
    proc = subprocess.run(cmd, cwd=workdir, capture_output=True, text=True)
    elapsed = time.time() - start
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / "output.md").write_text(proc.stdout)
    (outdir / "stderr.txt").write_text(proc.stderr)
    (outdir / "prompt.md").write_text(prompt)
    (outdir / "meta.json").write_text(json.dumps({
        "task": args.task, "arm": args.arm, "model": args.model,
        "elapsed_s": round(elapsed, 1), "exit": proc.returncode,
        "workdir": workdir}, indent=2) + "\n")
    print(f"wrote {outdir} exit={proc.returncode} elapsed={elapsed:.1f}s")


def bench_root(task: str) -> Path:
    return RUNS / task / "bench"


def cmd_blind(args) -> None:
    import writer

    a = RUNS / args.task / "writer" / "output.md"
    b = RUNS / args.task / "vanilla" / "output.md"
    for path in (a, b):
        if not path.exists():
            raise SystemExit(f"missing {path}: run both arms first")
    frame = writer.blind_present(
        a.read_text(), b.read_text(), "writer", "vanilla",
        args.criterion, seed=args.seed, root=bench_root(args.task))
    print("frame_id:", frame["frame_id"])
    print("criterion:", frame["criterion"])
    print(f"--- FIRST ({len(frame['first'])} chars) ---")
    print(frame["first"][: 4000])
    print(f"--- SECOND ({len(frame['second'])} chars) ---")
    print(frame["second"][: 4000])
    print("Judge first/second/tie, then: run.py resolve --task "
          f"{args.task} --frame {frame['frame_id']} --winner ... --reasoning ...")


def cmd_resolve(args) -> None:
    import writer

    judgment = writer.blind_resolve(
        args.frame, args.winner, args.reasoning,
        root=bench_root(args.task))
    print("winner:", judgment["winner"], "->", judgment["winner_label"])
    print("reasoning:", judgment["reasoning"])


def cmd_tally(args) -> None:
    import writer

    print(json.dumps(writer.blind_tally(root=bench_root(args.task)), indent=2))


def cmd_status(_args) -> None:
    for task in task_names():
        arms = {arm: (RUNS / task / arm / "output.md").exists()
                for arm in ("vanilla", "writer")}
        print(f"{task}: vanilla={'yes' if arms['vanilla'] else 'no'} "
              f"writer={'yes' if arms['writer'] else 'no'}")


# ------------------------------------------------------- V1.1 experiment ---

from bench.common import DIMENSIONS  # noqa: E402


def cmd_experiment(args) -> None:
    from bench import experiment as exp

    prime = exp.find_prime(args.prime_bin) if not args.dry_run else (
        args.prime_bin or "prime-agent")
    tasks = args.tasks.split(",") if args.tasks else task_names()
    unknown = [t for t in tasks if t not in task_names()]
    if unknown:
        raise SystemExit(f"unknown tasks: {unknown}")
    exp_id = f"exp-dryrun" if args.dry_run else exp.new_experiment_id()
    exp_dir = HERE / "experiments" / exp_id
    manifest = exp.build_manifest(
        exp_id, tasks, args.model, args.thinking, args.runs,
        args.seed, prime, args.judge_model)
    if args.dry_run:
        print(f"experiment {exp_id} (dry run): "
              f"{len(tasks)} tasks x 2 arms x {args.runs} runs = "
              f"{len(tasks) * 2 * args.runs} runs")
        for task in tasks:
            for arm in ("vanilla", "writer"):
                cmd = exp.author_command(
                    prime, "<prompt>", arm, args.model, args.thinking)
                print(f"  {task}/{arm}: {' '.join(cmd[:6])} ...")
        print("manifest preview: "
              + json.dumps({k: manifest[k] for k in
                            ("experiment_id", "author_model", "judge_model",
                             "runs_per_arm", "base_seed")}, indent=2))
        return
    exp_dir.mkdir(parents=True, exist_ok=True)
    (exp_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n")
    exp.capture_behavior(exp_dir, manifest)
    print(f"experiment {exp_id}: manifest written "
          f"(behavior {manifest['behavior_version']})")
    if manifest.get("git_dirty"):
        print("WARNING: working tree is dirty; the commit does not describe "
              "this run's behavior (see behavior.md).")
    if not manifest.get("judge_model"):
        print("NOTE: no --judge-model recorded; author runs will finish "
              "before judging, so a family-mismatched judge can be picked "
              "after the fact.")
    for task in tasks:
        for arm in ("vanilla", "writer"):
            for run_index in range(1, args.runs + 1):
                run_dir = exp.run_one(
                    prime, exp_dir, manifest, task, arm, run_index,
                    args.timeout)
                meta = json.loads((run_dir / "meta.json").read_text())
                print(f"  {task}/{arm}/run-{run_index}: exit={meta['exit']} "
                      f"elapsed={meta['elapsed_s']}s "
                      f"words={meta['output_words']} "
                      f"method={meta['output_method']}")
    print(f"done: {exp_dir}")


def _load_manifest(exp_id: str) -> tuple[Path, dict]:
    exp_dir = HERE / "experiments" / exp_id
    manifest_path = exp_dir / "manifest.json"
    if not manifest_path.exists():
        raise SystemExit(f"unknown experiment {exp_id}")
    return exp_dir, json.loads(manifest_path.read_text())


def cmd_judge(args) -> None:
    from bench import experiment as exp
    from bench import judge as judge_mod

    exp_dir, manifest = _load_manifest(args.experiment)
    prime = exp.find_prime(args.prime_bin)
    judge_model = args.judge_model or manifest.get("judge_model")
    if not judge_model:
        raise SystemExit("pass --judge-model (no judge configured)")
    tasks = args.tasks.split(",") if args.tasks else manifest["tasks"]
    dims = args.dims.split(",") if args.dims else [
        key for key, _ in DIMENSIONS]
    for task in tasks:
        for pair in range(1, manifest["runs_per_arm"] + 1):
            writer_out = (exp_dir / "runs" / task / "writer" / f"run-{pair}"
                          / "output.md")
            vanilla_out = (exp_dir / "runs" / task / "vanilla" / f"run-{pair}"
                           / "output.md")
            if not (writer_out.exists() and vanilla_out.exists()
                    and writer_out.read_text().strip()
                    and vanilla_out.read_text().strip()):
                print(f"  skip {task} pair {pair}: incomplete outputs")
                continue
            for dim_key, criterion in DIMENSIONS:
                if dim_key not in dims:
                    continue
                record = judge_mod.judge_pair(
                    prime, exp_dir, manifest, task, pair, dim_key,
                    criterion, writer_out.read_text(),
                    vanilla_out.read_text(), judge_model, args.timeout)
                if record.get("invalid"):
                    print(f"  {task} pair {pair} {dim_key}: INVALID after "
                          f"{record.get('attempts_used')} attempt(s) — "
                          f"{record.get('error')}")
                else:
                    print(f"  {task} pair {pair} {dim_key}: "
                          f"{record.get('winner_label')} "
                          f"(raw {record.get('winner')}, "
                          f"attempts {record.get('attempts_used')})")


def cmd_check_models(args) -> None:
    """Cheap author/judge readiness gate before spending 66 generations."""
    from bench import experiment as exp

    prime = exp.find_prime(args.prime_bin)
    roles = [("author", args.model), ("judge", args.judge_model)]
    results = []
    for role, model in roles:
        if not model:
            print(f"{role}: no model configured")
            results.append({"role": role, "model": None, "ready": False,
                            "error": "no model configured"})
            continue
        verdict = exp.probe_model(prime, model, args.timeout)
        verdict["role"] = role
        results.append(verdict)
        status = "ready" if verdict["ready"] else "NOT READY"
        print(f"{role} ({model}): {status}"
              + (f" in {verdict.get('elapsed_s')}s" if verdict["ready"] else "")
              + (f" — {verdict['error']}" if verdict.get("error") else ""))
    if all(r["ready"] for r in results):
        print("all configured models answered the probe")
        return
    raise SystemExit("model readiness check failed; no runs were started")


def cmd_human_judge(args) -> None:
    from bench import human as human_mod

    exp_dir, manifest = _load_manifest(args.experiment)
    pairs = ([int(p) for p in args.pairs.split(",")]
             if args.pairs else None)
    human_mod.run_human_judge(
        exp_dir, manifest, args.task, args.judge_name, pairs)


def cmd_summarize(args) -> None:
    from bench import report as report_mod

    exp_dir, _ = _load_manifest(args.experiment)
    path = report_mod.summarize_experiment(exp_dir)
    print(path.read_text())


def cmd_selftest(_args) -> None:
    from bench import selftest as selftest_mod

    selftest_mod.main()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run", help="run one arm of one task")
    run.add_argument("--task", required=True, choices=task_names())
    run.add_argument("--arm", required=True, choices=("vanilla", "writer"))
    run.add_argument("--model", default=None, help="same selector for both arms")
    run.add_argument("--prime-bin", default=None)
    run.add_argument("--workdir", default=None)
    run.add_argument("--dry-run", action="store_true")
    run.set_defaults(func=cmd_run)
    blind = sub.add_parser("blind", help="present both outputs blind")
    blind.add_argument("--task", required=True, choices=task_names())
    blind.add_argument("--criterion", required=True)
    blind.add_argument("--seed", type=int, default=7)
    blind.set_defaults(func=cmd_blind)
    resolve = sub.add_parser("resolve", help="record a blind judgment")
    resolve.add_argument("--task", required=True, choices=task_names())
    resolve.add_argument("--frame", required=True)
    resolve.add_argument("--winner", required=True, choices=("first", "second", "tie"))
    resolve.add_argument("--reasoning", required=True)
    resolve.set_defaults(func=cmd_resolve)
    tally = sub.add_parser("tally", help="count blind wins per arm")
    tally.add_argument("--task", required=True, choices=task_names())
    tally.set_defaults(func=cmd_tally)
    status = sub.add_parser("status", help="list tasks and arm outputs")
    status.set_defaults(func=cmd_status)
    experiment = sub.add_parser(
        "experiment", help="run N x (vanilla, writer) per task")
    experiment.add_argument("--model", default=None,
                            help="author model selector (same both arms)")
    experiment.add_argument("--runs", type=int, default=3)
    experiment.add_argument("--tasks", default=None,
                            help="comma-separated subset (default: all)")
    experiment.add_argument("--prime-bin", default=None)
    experiment.add_argument("--thinking", default=None)
    experiment.add_argument("--judge-model", default=None,
                            help="recorded in manifest; used by judge phase")
    experiment.add_argument("--seed", type=int, default=7)
    experiment.add_argument("--timeout", type=int, default=3600)
    experiment.add_argument("--dry-run", action="store_true")
    experiment.set_defaults(func=cmd_experiment)
    judge = sub.add_parser("judge", help="blind model judging per pair x dim")
    judge.add_argument("--experiment", required=True)
    judge.add_argument("--judge-model", default=None)
    judge.add_argument("--tasks", default=None)
    judge.add_argument("--dims", default=None,
                       help="comma-separated subset of the seven dimensions")
    judge.add_argument("--prime-bin", default=None)
    judge.add_argument("--timeout", type=int, default=600)
    judge.set_defaults(func=cmd_judge)
    human_judge = sub.add_parser("human-judge",
                                 help="interactive blind human judging")
    human_judge.add_argument("--experiment", required=True)
    human_judge.add_argument("--task", required=True, choices=task_names())
    human_judge.add_argument("--judge-name", required=True)
    human_judge.add_argument("--pairs", default=None,
                             help="comma-separated pair indices")
    human_judge.set_defaults(func=cmd_human_judge)
    summarize = sub.add_parser("summarize",
                               help="report counts, economics, CSVs")
    summarize.add_argument("--experiment", required=True)
    summarize.set_defaults(func=cmd_summarize)
    selftest = sub.add_parser("selftest",
                              help="validate the loop without models")
    selftest.set_defaults(func=cmd_selftest)
    check = sub.add_parser(
        "check-models", help="probe author and judge models before a run")
    check.add_argument("--model", default=None, help="author model selector")
    check.add_argument("--judge-model", default=None)
    check.add_argument("--prime-bin", default=None)
    check.add_argument("--timeout", type=int, default=120)
    check.set_defaults(func=cmd_check_models)
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
