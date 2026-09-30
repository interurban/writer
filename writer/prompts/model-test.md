---
description: Test the current model connection with a tiny request.
---

Test the CURRENT session model (do not switch models for this):

1. `writer.models_status()` — report provider, model, thinking level, and
   how this session was told about them (selector passed in vs Prime
   settings default vs unknown). If nothing is configured, stop and say
   exactly which of these applies:
   - `OPENROUTER_API_KEY not found` (and no Prime login for openrouter)
   - `ChatGPT subscription login required. Run /login.`
   - `OPENAI_API_KEY not found` (and no Prime login for openai)
   Do not print secrets. Do not guess credentials exist.
2. Ask the model to reply with exactly: `ok` (no tools, minimal tokens).
3. Report, each on its own line with ✓/✗:
   - `Provider: <provider>` / `Model: <id>` / `Authentication: found|missing`
   - connection (request accepted, provider-specific errors quoted verbatim)
   - response received (exact text echoed)
   - usage metadata visible (input/output tokens if the turn exposes them,
     else `unknown` — never estimated)
4. On failure, quote the provider error and map it to the action:
   sign-in refusal → `/login`; unknown model id → `/model`; rejected
   reasoning level → retry at a lower thinking level or omit it.
   Never silently retry on a different provider: subscription and API-key
   billing are separate, and the user must always see which one answered.
