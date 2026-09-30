---
description: List drafts with ids, parents, and final flags.
---

Use the `writer` Python skill to list drafts. Call `writer.drafts_list()`,
then render approximately like:

```text
Drafts

● draft-003   current
  draft-002
  draft-001   final
```

Offer to inspect one, make one current (`writer.drafts_make_current`),
compare two, or mark one final (`writer.drafts_mark_final`). Do not paste
full bodies unless asked; summarize each in one line.
