# Task: product-education — Model catalog pinning and offline use

## Brief

Developer-education piece: how a compiled fallback model catalog plus
pinning and offline modes keep an AI CLI working when the network or the
model API does not. About 1,000–1,500 words.

## Audience

Developers shipping AI-powered CLIs or IDE extensions who worry about
model availability, version drift, and air-gapped users.

## Constraints

- Teach the pattern, not the product: pinning, fallback catalogs,
  refresh cadence, offline degradation.
- Any product behavior described must be version-pinned and checkable.
- No marketing voice.

## Sources

No supplied material.

## Hard requirements

- Distinguishes catalog freshness from availability with at least one
  concrete failure scenario for each.
- Every product/version assertion is a ledger claim with a source.
