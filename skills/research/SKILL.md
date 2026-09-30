---
name: research
description: Source-grounded research — primary sources, provenance, fact vs interpretation. Use before drafting technical claims.
---

# Research

Prefer primary sources: specs, official docs, source code, RFCs, papers.
Secondary coverage is a pointer, not evidence. Record every consequential
source in project state (`writer.sources_add`) with title, URL, origin, and
short excerpts — never paste whole documents.

Distinguish fact from interpretation in notes. Capture version numbers and
access dates for anything that drifts (APIs, CLIs, pricing, benchmarks).
When sources conflict, say so and cite both. A claim without a source goes
to the ledger as `unsupported` until grounded.
