---
description: Verify technical claims in a draft against sources.
argument-hint: [draft-id]
---

Verify draft `$1` (default: current draft):

1. Extract first: `writer.claims_extract(draft_id)` (heuristic candidates;
   review and delete junk — the ledger is the truth, not the extractor).
   Triage with `writer.verify_draft(draft_id)` (high-importance first).
2. For each claim: re-read cited excerpts (`writer.sources_get`), check
   versions/commands/APIs. Run code samples with `writer.exec_check(label,
   command, claim_id=...)` where practical; a failing check is data, not a
   crash. For load-bearing claims, spawn a verification subagent (reasoning
   strategy per `writer.models_get()`) — it returns findings, you persist.
3. Record with `writer.claims_verify(id, support, verification,
   evidence_source_ids=[...], note=...)`. `verified` without evidence is
   refused: cite source ids or exec records, or leave the claim
   `unverified`/`unsupported` and weaken, qualify, or remove the language.
4. Report: verified/total, failures with fixes, remaining unverified. Never
   mark a draft final with high-importance claims still `unverified`.
