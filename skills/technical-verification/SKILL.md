---
name: technical-verification
description: Verify technical claims — versions, commands, APIs, code, outputs, citations. Use after drafting, before marking final.
---

# Technical verification

Work from the claim ledger: high-importance claims first. For each claim
check versions, commands, API signatures, code examples (run them where
possible), expected outputs, and citations. Update the ledger
(`writer.claims_update`) to `verified` / `failed`; never leave a
high-importance claim `unverified` in a final draft.

 Executable checks beat rereading. When a check needs a different model or
deterministic tools, spawn a verification subagent rather than trusting one
pass. Quote the source, not your memory of it.
