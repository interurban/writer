# Task: editing — Rescue a poor draft about compaction

## Brief

Edit the supplied draft into a publishable article for the same audience.
Keep the correct technical content; fix everything else. 800–1,200 words.

## Audience

Engineers using long-context coding agents who have watched context
windows fill up.

## Constraints

- Preserve every technically correct assertion; cut or fix the rest.
- Final piece must not resemble the original's structure.
- Do not add new unverified technical claims.

## Supplied draft (do not publish as-is)

```markdown
# Context Compaction in Modern AI Systems

In today's rapidly evolving world of artificial intelligence, context
management is more important than ever. This article will explore
compaction in three parts: what it is, why it matters, and what's next.

## What is compaction?

Compaction is the process of summarizing conversation history when the
context window fills up. It's notX, it'sY: it's not forgetting, it's
remembering smarter. Here's the thing — long conversations don't fit, so
something has to give.

## Why does it matter?

First, it saves tokens. Second, it saves money. Third, it saves time.
Without compaction, agents stall. With compaction, agents thrive. As we
all know, read on to discover the amazing benefits below.

## What's next?

In conclusion, compaction summarizes the past so agents can face the
future. The future of compaction is bright, and the possibilities are
endless. Stay tuned for more innovations in this exciting space.
```

## Sources

The supplied draft only. No new technical claims permitted.

## Hard requirements

- Output contains zero sentences from the "generic patterns" list
  (rapidly-evolving opener, lists of three, "Here's the thing",
  "It's not X, it's Y", summarize-only conclusion).
- Explains what survives compaction (goals, decisions, harness state)
  vs what is summarized away.
