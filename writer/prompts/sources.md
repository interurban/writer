---
description: Show known sources with provenance and excerpts.
---

Call `writer.sources_list()` and render each source with id, title, origin,
support signal (`✓` primary/spec/docs, `?` unverified secondary,
`!` missing provenance), plus one-line excerpt counts. Offer to inspect a
source (`writer.sources_get`) or add one (`writer.sources_add`). Keep it
compact.
