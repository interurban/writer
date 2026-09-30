"""Prime Agent model access for the Writer harness (read-only introspection).

Reuse, not duplication: authentication, model catalogs, selection,
thinking levels, and request handling stay owned by Prime. This module
only READS Prime's own on-disk state and live registry surfaces so the
Writer RLM knows what model resources exist:

- settings: `<agent>/settings.json` + `<cwd>/.prime/agent/settings.json`
  (`defaultProvider`, `defaultModel`, `subagentDefaultModel`, thinking).
- auth presence: provider IDs in `<agent>/auth.json` (IDs only — values
  are never read) plus env-key presence for the three Writer-relevant
  providers (mirrors Prime's `env_api_keys`; other providers surface via
  auth.json automatically).
- catalog metadata: `<agent>/models/*.json` caches when present, else
  unknown (never fabricated).

Agent-dir resolution mirrors Prime's `get_agent_dir`:
`$PRIME_AGENT_CODING_AGENT_DIR`, else `~/.prime/agent`.
"""

from __future__ import annotations

import json
import os
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from ._store import _read_json, _root, _write_json

# Minimal env-key mirror for Writer-relevant providers (Prime's
# `env_api_keys.rs` is authoritative; openai-codex is OAuth-only and has
# no env var by design — subscription vs API billing stay distinct).
_PROVIDER_ENV_VARS = {
    "openai-codex": (),
    "openrouter": ("OPENROUTER_API_KEY",),
    "openai": ("OPENAI_API_KEY",),
}

#: Canonical Writer roles (single source in `_models`). Every role
#: defaults to inherit, so Writer works with exactly one configured model.
from ._models import ROLES

OPENROUTER_MODELS_URL = "https://openrouter.ai/api/v1/models"


def prime_agent_dir() -> Path:
    """Prime agent dir (mirrors `get_agent_dir`, no Prime import)."""
    override = os.environ.get("PRIME_AGENT_CODING_AGENT_DIR", "").strip()
    if override:
        return Path(override)
    return Path.home() / ".prime" / "agent"


def prime_settings(cwd: str | Path | None = None) -> dict:
    """Merged Prime settings (project over global); unknown keys ignored."""
    agent_dir = prime_agent_dir()
    merged: dict = {}
    for path in (agent_dir / "settings.json",
                 Path(cwd or Path.cwd()) / ".prime" / "agent" / "settings.json"):
        if path.exists():
            try:
                data = json.loads(path.read_text())
            except ValueError:
                continue
            if isinstance(data, dict):
                merged.update(data)
    return {
        "default_provider": merged.get("defaultProvider"),
        "default_model": merged.get("defaultModel"),
        "subagent_default_model": merged.get("subagentDefaultModel"),
        "thinking": merged.get("defaultThinkingLevel",
                               merged.get("thinking")),
    }


def prime_auth_providers() -> list[str]:
    """Provider IDs with stored Prime credentials (IDs only, never values)."""
    data = _read_json(prime_agent_dir() / "auth.json", {})
    if not isinstance(data, dict):
        return []
    return sorted(key for key in data)


def env_credential_present(provider: str) -> str | None:
    """Name of a set env var for provider, else None (values never read)."""
    for var in _PROVIDER_ENV_VARS.get(provider, ()):
        if os.environ.get(var, "").strip():
            return var
    return None


def models_providers() -> list[dict]:
    """Authenticated providers: stored login and/or env key (no secrets)."""
    providers = []
    stored = set(prime_auth_providers())
    for provider in sorted(stored | set(_PROVIDER_ENV_VARS)):
        via_login = provider in stored
        via_env = env_credential_present(provider)
        if via_login or via_env:
            providers.append({"provider": provider,
                              "via_login": via_login,
                              "via_env": via_env})
    return providers


def models_available() -> list[str]:
    """Provider IDs with any credential (login or env)."""
    return [p["provider"] for p in models_providers()]


def models_ready() -> dict:
    """Readiness: usable model configured? Never blocks; explains."""
    available = models_available()
    settings = prime_settings()
    ready = bool(available)
    reasons = []
    if not ready:
        reasons = ["No usable model is currently configured.",
                   "Run /login for subscription providers",
                   "or set OPENROUTER_API_KEY."]
    return {"ready": ready, "providers": available,
            "default_provider": settings["default_provider"],
            "default_model": settings["default_model"], "reasons": reasons}


def models_current(selector: str | None = None,
                   thinking: str | None = None) -> dict:
    """Primary model status. The kernel cannot see its own session model,
    so the orchestrator passes what it knows (`/model` shows it); settings
    defaults fill the rest, unknown stays unknown."""
    settings = prime_settings()
    provider = model = None
    if selector and "/" in selector:
        provider, _, model = selector.partition("/")
    return {
        "provider": provider or settings["default_provider"],
        "model": model or settings["default_model"],
        "thinking": thinking or settings["thinking"],
        "subagent_default":
            settings["subagent_default_model"] or "inherit",
        "selector_known": bool(selector),
    }


def _catalog_models() -> list[dict]:
    """Prime catalog caches on disk (both cache files beside models.json)."""
    models: list = []
    models_dir = prime_agent_dir() / "models"
    if not models_dir.is_dir():
        return models
    for path in sorted(models_dir.glob("*.json")):
        try:
            data = json.loads(path.read_text())
        except ValueError:
            continue
        items = data if isinstance(data, list) else data.get("models", [])
        for item in items if isinstance(items, list) else []:
            if isinstance(item, dict) and item.get("provider") and item.get("id"):
                models.append(item)
    return models


def models_describe(selector: str) -> dict:
    """Capability metadata for a `provider/id` selector from Prime's own
    catalog caches. Unknown stays unknown — never fabricated."""
    provider, _, model_id = selector.partition("/") if "/" in selector else ("", "", selector)
    for item in _catalog_models():
        if (str(item.get("provider")) == provider
                and str(item.get("id")) == model_id):
            cost = item.get("cost") or {}
            return {"known": True, "provider": provider, "id": model_id,
                    "display_name": item.get("name"),
                    "reasoning": item.get("reasoning"),
                    "thinking_levels": ((item.get("thinking_level_map") or {}).get("levels")
                                        if isinstance(item.get("thinking_level_map"), dict)
                                        else item.get("thinking_levels")),
                    "context_window": item.get("contextWindow",
                                               item.get("context_window")),
                    "max_output": item.get("maxTokens", item.get("max_tokens")),
                    "input_modalities": item.get("input"),
                    "cost": cost or None}
    return {"known": False, "provider": provider or None,
            "id": model_id or None}


def models_policy(root: str | Path | None = None) -> dict:
    """Five-role policy (single source in `_models`; legacy V1 files work)."""
    from ._models import models_policy as policy

    return policy(root)


def models_set_policy(policy: dict,
                       root: str | Path | None = None) -> dict:
    """Persist role overrides (`inherit` or `provider/id` selectors;
    resolution happens Prime-side at spawn — errors surface actionably)."""
    from ._models import models_set_policy as set_policy

    return set_policy(policy, root)


def models_role(role: str, own_selector: str | None = None,
                candidates: list | None = None,
                root: str | Path | None = None) -> dict:
    """Resolve one role to a spawn selector (None = inherit).

    - `inherit` (or unknown role): None.
    - explicit `provider/id`: the selector (Prime resolves/validates).
    - `different-family-if-available`: first candidate of another family
      (needs `own_selector` + `candidates` from `rlm.find_models`), else
      None — diversity preferred, never mandatory.
    - `reasoning`: None with `thinking_hint: high` — same model, stronger
      effort (caller passes `thinking=` to spawn).
    """
    from ._models import models_pick_critic

    if role not in ROLES:
        return {"selector": None, "thinking_hint": None,
                "note": f"unknown role {role!r}; inheriting"}
    spec = models_policy(root).get(role, {})
    if spec.get("model", "inherit") != "inherit":
        return {"selector": spec["model"], "thinking_hint": None,
                "note": "explicit override"}
    strategy = spec.get("strategy")
    if strategy == "different-family-if-available":
        pick = (models_pick_critic(own_selector, candidates or [])
                if own_selector else None)
        return {"selector": pick, "thinking_hint": None,
                "note": "different family" if pick else
                "no other family available; inheriting"}
    if strategy == "reasoning":
        return {"selector": None, "thinking_hint": "high",
                "note": "inherit model, high thinking"}
    if role == "primary" and own_selector:
        return {"selector": own_selector, "thinking_hint": None,
                "note": "current session model"}
    return {"selector": None, "thinking_hint": None, "note": "inherit"}


def models_refresh_openrouter(root: str | Path | None = None,
                              timeout_s: int = 30) -> dict:
    """Live OpenRouter model listing (metadata only, cached, no secrets).

    Uses `$OPENROUTER_API_KEY` only; Prime `/login`-stored credentials are
    never read. When no env key exists but Prime knows openrouter auth,
    reports authenticated-without-live instead of failing. Writes
    `writing/cache/openrouter-models.json`; never a hard-coded ID list.
    """
    base = _root(root)
    key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if not key:
        authed = "openrouter" in prime_auth_providers()
        return {"live": False, "authenticated": authed, "models": [],
                "reason": ("OPENROUTER_API_KEY not found" + (
                    "; Prime login present — browse via /model or export "
                    "the key for live listing" if authed else ""))}
    request = urllib.request.Request(
        OPENROUTER_MODELS_URL,
        headers={"Authorization": f"Bearer {key}"})
    try:
        with urllib.request.urlopen(request, timeout=timeout_s) as response:
            payload = json.loads(response.read().decode())
    except Exception as exc:
        return {"live": False, "authenticated": True, "models": [],
                "reason": f"OpenRouter request failed: {exc}"}
    items = payload.get("data", []) if isinstance(payload, dict) else []
    entries = [{"id": item.get("id"), "name": item.get("name"),
                "context_length": item.get("context_length"),
                "pricing": item.get("pricing")}
               for item in items if isinstance(item, dict) and item.get("id")]
    cache = base / "cache" / "openrouter-models.json"
    cache.parent.mkdir(parents=True, exist_ok=True)
    _write_json(cache, {"fetched_at": datetime.now(timezone.utc).isoformat(),
                        "count": len(entries), "models": entries})
    return {"live": True, "authenticated": True, "count": len(entries),
            "models": entries,
            "note": "cached to writing/cache/openrouter-models.json; "
                    "select via Prime /model, reference as openrouter/<id>"}


def models_cached_openrouter(root: str | Path | None = None) -> dict:
    """Last live listing (may be stale; `fetched_at` says when)."""
    cached = _read_json(
        _root(root) / "cache" / "openrouter-models.json", None)
    if not cached:
        return {"cached": False, "models": [],
                "reason": "no cached listing; run models_refresh_openrouter"}
    return {"cached": True, **cached}


def models_status(selector: str | None = None,
                  thinking: str | None = None,
                  root: str | Path | None = None) -> dict:
    """One readiness snapshot for banners and the RLM."""
    ready = models_ready()
    return {"primary": models_current(selector, thinking),
            "providers": models_providers(),
            "ready": ready["ready"], "reasons": ready["reasons"],
            "policy": models_policy(root)}
