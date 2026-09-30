---
description: Show the claim ledger with support and verification status.
---

Call `writer.claims_list()` and render each claim as:

```text
✓ MCP uses JSON-RPC                            technical  high
? Adoption claim                               numeric    medium
! Unsupported performance claim                product    high
```

`✓` verified, `?` unverified, `!` failed/unsupported. Sort
high-importance first. Offer to verify a claim (check sources, run code,
then `writer.claims_update`) or add missing ones.
