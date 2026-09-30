# Task: architecture — Supervisor-per-session agent daemons

## Brief

Architecture piece: why run each agent session as a supervised worker
process (supervisor pattern with restart/backoff and disk-persisted
sessions) instead of hosting sessions in-process. About 1,200–1,800 words.

## Audience

Engineers who have built or operated long-running services: CLIs, daemons,
or agent harnesses. Familiar with processes, crash recovery, and state.

## Constraints

- Compare at least two architectures concretely (in-process vs supervised
  workers); name what each survives (crash, restart, disconnect).
- No generic "reliability is important" filler; argue from failure modes.
- Diagrams optional; failure-mode table encouraged.

## Sources

No supplied material. OS/process supervision concepts are fair game;
cite anything version- or product-specific.

## Hard requirements

- Explains where session state lives and how reattach works after a
  supervisor restart.
- Names at least one tradeoff of the supervisor pattern (cost paid).
