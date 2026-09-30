# Your agent's sessions should outlive its process

Last month I watched a twelve-hour research run die because someone closed a laptop lid. The agent had done eleven hours of good work — fetched sources, built a comparison table, drafted half a report — and all of it lived in a process attached to a terminal that went to sleep. When the machine woke up, the SSH session was gone, the process was gone, and the "session" was a transcript fragment in a scrollback buffer nobody could resume. The work wasn't lost because the model forgot. It was lost because the harness kept a week-long unit of work inside a minute-long unit of failure.

This is the normal way to build an agent harness, and it stops being acceptable the moment runs get long. The fix is old technology: treat every session as a supervised worker process whose state lives on disk, so killing any single process — the UI, the worker, the supervisor itself — never kills the work.

## What "session" actually contains

Before arguing about where sessions live, inventory what dies when a process dies. A serious agent session has at least four kinds of state, and they fail differently:

1. **The message log.** Every prompt, tool call, and result, in order. Losing the tail means the agent repeats work; losing the middle means it contradicts itself.
2. **The execution namespace.** In a REPL-based harness the model has variables, open handles, cached data. This is the working memory that makes long tasks efficient — recomputing it costs real money.
3. **Schedules and goals.** Heartbeats, cron jobs, persistent objectives that are supposed to fire while nobody watches. These are the entire point of detaching.
4. **The roster.** Child subagents, their handles, what they were asked. A parent that forgets its children orphans them.

An in-process design keeps all four in heap memory and persists on good days. A supervised design treats disk as the truth and memory as a cache. That single inversion decides everything downstream.

## The supervisor pattern, concretely

Run a small supervisor process. For each active session it spawns one worker process. The supervisor's job is narrow: watch workers, restart the ones that exit unexpectedly with backoff, give up after a consecutive-failure budget, and route clients (TUIs, CLIs, RPC callers) to the right worker. It holds no session state itself, which is what makes it restartable: a supervisor with no state has nothing to lose.

Prime Agent's Rust implementation is a clean instance. Its supervision module states the contract in one line — watch a worker process and restart it with backoff on unexpected exit — with a cap on consecutive failures so a poisoned session can't hot-loop the machine forever. Session transcripts persist as append-only JSONL files, one per session id. The Python REPL namespace is snapshotted separately (serialized with dill, debounced to 1500ms after successful executions so every keystroke doesn't pay a serialization tax). Goals, heartbeats, and cron jobs live in their own stores under the same agent directory. When the supervisor restarts, it re-reads the directory: sessions, schedules, and the subagent roster are all re-adopted from disk rather than reconstructed from memory.

The append-only detail matters more than it sounds. A session file you only append to can be tailed, repaired after a torn write, and read by a new worker mid-flight. A file you rewrite on every turn is a corruption waiting for a power outage — and "the laptop lid closed" is a power outage with better branding.

## A worked trace: spawn, die, resume

Here is the failure the pattern exists for, step by step. A user asks for a literature survey that will take six hours. The orchestrator spawns a research child for one sub-question:

```python
handle = await rlm.spawn(survey_prompt, name="research-1980s-caches")
```

Admission is immediate — the parent gets a handle with a child id and keeps working. The child runs in its own session, its own transcript file, its own REPL namespace. Suppose the machine reboots at hour three. What survives depends entirely on the architecture:

- **In-process:** the child thread dies with the parent process. The transcript exists only if something flushed it. The parent's handle points at nothing. The survey restarts from zero, minus whatever the user remembers to paste back in.
- **Supervised:** the supervisor process also died — but it restarts on boot and re-adopts every session file on disk, including the child's. The child's transcript has everything up to the last appended message; its REPL namespace restores from the last dill snapshot (at most ~1.5 seconds of execution stale, plus whatever was mid-flight). The parent re-lists its roster, finds the child alive again, and collects the result with a bounded poll. Nothing re-runs except the interrupted cell.

Note what crossed the process boundary during all of this: files. The transcript, the namespace snapshot, the roster entry. No distributed consensus, no shared memory, no graceful shutdown handshake that the reboot would have ignored anyway. Crash-only design — software that expects to be killed — keeps working precisely in the situations where graceful designs discover their shutdown hooks never ran.

## The failure-mode table

This is the whole argument in one place. Rows are things that actually happen; columns are the two architectures.

| Failure | In-process session | Supervised worker + disk state |
|---|---|---|
| Terminal/SSH disconnect | run dies with the PTY | run continues; reattach later |
| Worker crash (OOM, segfault, panic) | all four state kinds lost | supervisor restarts worker; transcript + snapshot restore it |
| Supervisor crash/reboot | everything lost | supervisor restarts stateless; re-adopts sessions from disk |
| Laptop sleep / power loss | process frozen or killed mid-write | append-only log repairable; at most one cell re-runs |
| Poisoned session (crash loop) | takes the harness down or hangs it | consecutive-failure budget stops restarts; session file preserved for inspection |
| User opens second client | second view of maybe-stale memory, or a lock fight | both clients route to the same worker via the supervisor |
| Model provider outage mid-run | in-flight turn lost; resume is manual | transcript intact; retry the turn, keep the history |

The in-process column isn't a strawman. It is how most demo harnesses work, and it is fine for ten-minute tasks. The supervised column is what you need when the task outlasts the median time between the rows in the left column.

## What it costs

Nothing here is free, and anyone selling supervision as pure upside is skipping the invoice:

- **A process per session is heavy.** Each worker carries its own interpreter, model client, and namespace. A hundred idle sessions is a hundred resident interpreters. You mitigate with idle reaping (freeze-dry the namespace to disk, kill the worker, revive on demand), but that is a real subsystem, not a flag.
- **Disk state is a schema.** Append-only JSONL plus dill snapshots plus roster files is three formats that must stay mutually intelligible across upgrades. Every format change needs migration or version tolerance, and "the supervisor re-adopts everything on boot" becomes "the supervisor re-adopts everything it still understands."
- **Restart is not resume.** A restored namespace has the variables but not the open sockets, not the half-read streams, not the browser session. Code that holds live resources across cells breaks on restore; the harness has to revive carefully (rebinding functions into the live namespace) and the model has to learn that a restored variable holding a dead connection needs reconnecting, not reuse.
- **Backoff budgets hide failures.** A consecutive-failure cap converts a hot loop into a quiet dead session. If nothing pages on it, "supervised" degrades into "supervised into silence." The roster needs a visible dead-letter state, not just a counter.

These costs are worth paying past a certain run length and not before it. My rule of thumb: if losing the run costs more than an engineer's interrupted hour, supervise it. Below that, in-process is cheaper and its failures are at least obvious.

## The one-sentence version

Keep session truth on disk in append-only form, snapshot the namespace on a debounce, supervise workers with backoff and a failure budget, and make every component restartable from files alone — then the only unrecoverable failure left is losing the disk itself, which is somebody else's department.
