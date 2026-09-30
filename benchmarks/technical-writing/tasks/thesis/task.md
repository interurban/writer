# Task: thesis — From research notes to an argument

## Brief

Develop the most interesting defensible thesis you can from the supplied
research notes, then write the article that argues it (1,000–1,500 words).
The notes are raw; the thesis is your contribution.

## Audience

Engineering leaders deciding where to invest in agent infrastructure.

## Constraints

- State the thesis in one sentence early; everything else serves it.
- Notes may be incomplete or contradictory — say where you go beyond them
  (inference, labeled as such in the claim ledger).
- Surprise is rewarded only if the argument earns it.

## Supplied research notes

- Session files append-only JSONL; kernel namespace snapshotted via dill;
  harness state in JSON files. Three persistence mechanisms, three formats.
- Compaction summarizer runs with its own system prompt; summaries are
  lossy by design. Goals/heartbeat/cron state re-injected post-compaction.
- Subagent admission is immediate (never blocks parent); results arrive via
  agent messages or files; parent polls with bounded timeout.
- `/refine` edits supplemental state only; base prompt immutable; every
  refinement recorded with rollback.
- Daemon owns the loop; TUI detaches freely. Reattach works because
  sessions persist on disk.
- Token/cost accounting lives in daemon tracing, not in session files.
- Contradiction in notes: "subagents share cwd" (writer project) vs
  "each child gets own session dir" — both true, different scopes.
- Open question in notes: does verification evidence (source ids, exec
  records) belong in session files or project state? Currently project
  state; sessions reference drafts by id.

## Sources

The notes above; primary sources optional.

## Hard requirements

- One-sentence thesis present and non-obvious (not "persistence matters").
- Every claim from the notes is ledgered; every inference beyond the
  notes is typed `inference` and at least one is explicitly qualified or
  cut in the final text.
