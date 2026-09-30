---
name: editorial-critique
description: Honest editorial critique that finds problems without flattening voice. Use to review drafts before rewriting.
---

# Editorial critique

Identify problems; do not auto-rewrite everything. Look for: boring
sections, weak openings, unclear argument, unsupported assertions,
repetition, generic phrasing, poor transitions, unnecessary abstraction,
polish that removes personality, passages interchangeable with generic AI
output, places where a concrete example beats explanation. Also: low
information density, predictable article structures, overly symmetrical
sections, transitions that add no information, vague examples, unclear
reader payoff, technically correct but uninteresting explanations.

## Detecting "technically sound but editorially flat"

This is the characteristic failure mode: every sentence true, nothing
memorable. Check explicitly:

- Does the piece have a clear thesis statable in one sentence?
- Is there a useful mental model, or only a tour of facts?
- Does the opening create a reason to continue?
- Are facts organized around an idea, or simply listed?
- Does every paragraph feel equally weighted?
- Is the strongest insight buried below setup?
- Is there a memorable compression of the concept?
- Could the piece be mistaken for compressed documentation?
- Does the article tell the reader why the details matter?

Name flatness as flatness, with the same ranked-issue + preserve-list
contract — never rewrite the article to demonstrate the diagnosis.

Preserve good material — name what works and why. Rank issues by reader
impact. Propose the smallest revision that fixes each problem. Never sand
off voice in the name of correctness.

## Subagent recipe (diagnose, don't rewrite)

Spawn with `rlm.spawn(prompt, name="critic", model=<pick>)` where the
model comes from `writer.models_pick_critic(own_selector, await
rlm.find_models(...))` — a different family when available, inherit
otherwise. The child shares `writing/` but must NOT persist drafts: it
returns its critique in its answer and the parent decides what to save.

Require this output contract from the child:

1. Ranked issues (reader impact first), each quoting the offending passage.
2. An explicit preserve list: material worth keeping, and why.
3. The smallest fix per issue — a sentence or direction, never a full
   rewritten article.

The writer performs the repair (`writer.drafts_save(parent=...)`) and may
reject any criticism. Never promote critic prose to a canonical draft.
Criticism that rewrites everything is a failed critique: re-prompt.
