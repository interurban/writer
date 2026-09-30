---
name: writer
description: Editorial project state for technical writing — drafts, sources, claims, voice, pairwise evals, preferences, traces. Import writer in the Python kernel and call writer.drafts_save / sources_add / claims_add / evals_compare.
---

# Writer state

Persistent editorial state in `writing/` (survives compaction, restarts,
subagents, model changes). Same on-disk format as the `pa-writer` Rust
crate. Resolve root via `$WRITER_DIR`, else `<cwd>/writing` (legacy `.writer` auto-migrates).

```python
import writer

writer.project_init("MCP explainer", goal="Explain MCP to API veterans")
writer.project_new("New topic")   # archives current project first; never overwrites
writer.brief_set(objective="...", constraints="...",
                 label="experienced engineers", background="knows APIs, not MCP")

d1 = writer.drafts_save("# Opening A\n...", reason="thesis-first attempt", model="gpt-5.6")
d2 = writer.drafts_save("# Opening B\n...", parent=d1["id"], reason="concrete tension")
writer.drafts_compare(d1["id"], d2["id"])

src = writer.sources_add("MCP spec", url="https://spec.modelcontextprotocol.io", origin="spec",
                         excerpts=[{"text": "MCP uses JSON-RPC 2.0", "locator": "transport"}])
claim = writer.claims_add("MCP uses JSON-RPC", claim_type="technical",
                          importance="high", source_ids=[src["id"]], support="supported")
writer.claims_update(claim["id"], verification="verified")

frame = writer.evals_compare(d1["body"], d2["body"],
                             "Which opening keeps an experienced developer reading?",
                             subjects=[d1["id"], d2["id"]], seed=7)
# show frame["first"] / frame["second"], judge, then:
writer.evals_resolve(frame["criterion"], frame["subjects"], frame["swapped"],
                     frame_winner="second", reasoning="...", confidence=0.7)
writer.preference_record(d1["id"], d2["id"], winner="B", reasons=["more-specific"])
print(writer.status_line(model="gpt-5.6"))
```

Subagents share the project: they inherit `cwd`, so they read/write the
same `writing/`. Pass an explicit `model=` per subagent role (orchestrator:
strongest reasoning; research: inexpensive capable; critic: different family
from writer; verification: reasoning + deterministic tools). Never hard-code
vendors here — policy lives with the caller.

## V1 capabilities

```python
# Claim extraction (heuristic candidates; you review, ledger decides)
new = writer.claims_extract(draft_id)          # dedupes against the ledger
writer.extract_candidates(body, draft_id)      # preview without persisting

# Evidence-gated verification (verified without evidence raises)
writer.claims_verify(cid, "supported", "verified",
                     evidence_source_ids=[src["id"]], note="spec §transport")
writer.verify_draft(draft_id)                  # triage: high-importance first

# Executable checks (kernel sandbox; failures are data, not crashes)
rec = writer.exec_check("install snippet", "sh -c '...'", claim_id=cid)
writer.exec_list()

# Model routing (family = opaque provider segment, never vendor names)
policy = writer.models_policy()                # 5 roles, all inherit by default
writer.models_set_policy({"critic": {"model": "openrouter/m"}})
pick = writer.models_pick_critic(own_selector, await rlm.find_models("...", limit=8))
role = writer.models_role("critic", own_selector, candidates)  # → {selector|None, thinking_hint}
handle = await rlm.spawn(critic_prompt, name="critic", model=pick)  # or omit model= to inherit

# Prime access status (read-only; IDs and env names only, never secrets)
writer.models_status()                         # {primary, providers, ready, reasons, policy}
writer.models_current(selector, thinking)      # merge orchestrator-known + Prime settings
writer.models_describe("openrouter/<id>")      # catalog metadata or {known: False}
writer.models_refresh_openrouter()             # live listing via $OPENROUTER_API_KEY, cached
writer.models_cached_openrouter()              # last listing + fetched_at

# Blind comparison (judge sees first/second; labels sealed until resolve)
frame = writer.blind_present(a_text, b_text, "writer", "vanilla", criterion, seed=7)
judgment = writer.blind_resolve(frame["frame_id"], "first", reasoning="...")
writer.blind_tally()                           # per-label wins, no scores

# Run quality (derived from state; tokens/cost merged from Prime tracing)
writer.trace_summary()
writer.trace_finish(run_id, ..., quality=writer.trace_summary())
print(writer.standard_criteria())              # benchmark comparison questions
```

Children return findings via `rlm.collect`; the parent persists ledger and
draft writes (one writer per file).
