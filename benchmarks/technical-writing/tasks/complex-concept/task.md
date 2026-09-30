# Task: complex-concept — RLM recursion and the host bridge

## Brief

Explain recursive language models to experienced engineers: what it means
for context to be a variable, for subagents to be function calls, and how
a host process bridges a Python REPL to supervised child sessions. About
1,200–1,800 words.

## Audience

Senior engineers fluent in processes, IPC, and REPLs, skeptical of agent
hype, unfamiliar with RLM specifics.

## Constraints

- Build from primitives they know (pipes, eval loops, namespaces,
  admission queues); introduce one new concept at a time.
- One worked trace of a parent spawning a child and collecting its result,
  including what crosses the boundary and what does not.
- No anthropomorphism of subagents ("the child thinks...").

## Sources

No supplied material. Cite the RLM paper/blog for terminology.

## Hard requirements

- Distinguishes the REPL namespace (persistent) from the message log
  (append-only) and says what survives a restart for each.
- The worked trace names the wire events involved (request/reply,
  host-request, display) at least schematically.
