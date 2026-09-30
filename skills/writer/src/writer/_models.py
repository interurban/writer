"""Model-routing policy for Writer roles (`models.json`).

Prime resolves subagent models from free-form `provider/model-id`
selectors passed to `rlm.spawn(model=...)`, discoverable via
`rlm.find_models` (which returns `{provider, id, name, selector}`).
Family means the opaque provider segment: string inequality only, no
vendor knowledge. The kernel cannot see its own selector, so the
orchestrator passes it in — the smallest compatible mechanism.

```yaml
primary:
  model: inherit
research:
  model: inherit
critic:
  strategy: different-family-if-available
verification:
  strategy: reasoning
judge:
  model: inherit
```

Every role defaults to inherit: Writer works with exactly one configured
model. Overrides are opaque `provider/model-id` selectors Prime resolves
at spawn (errors surface actionably); strategies are interpreted by
`models_role` in `_prime.py`.
"""

from __future__ import annotations

from pathlib import Path

from ._store import _read_json, _root, _write_json

#: Canonical Writer roles.
ROLES = ("primary", "research", "critic", "verification", "judge")

DEFAULT_POLICY = {
    "primary": {"model": "inherit"},
    "research": {"model": "inherit"},
    "critic": {"strategy": "different-family-if-available"},
    "verification": {"strategy": "reasoning"},
    "judge": {"model": "inherit"},
}

#: V1 role name, honored as `primary` when `primary` is absent.
LEGACY_WRITER_ROLE = "writer"


def models_policy(root: str | Path | None = None) -> dict:
    """Five-role policy (defaults when absent; legacy `writer` → primary)."""
    stored = _read_json(_root(root) / "models.json", {})
    stored = stored if isinstance(stored, dict) else {}
    policy = {role: dict(DEFAULT_POLICY[role]) for role in ROLES}
    for role in ROLES:
        spec = stored.get(role)
        if isinstance(spec, dict):
            policy[role] = spec
    legacy = stored.get(LEGACY_WRITER_ROLE)
    if "primary" not in stored and isinstance(legacy, dict):
        policy["primary"] = legacy
    return policy


def models_set_policy(policy: dict,
                       root: str | Path | None = None) -> dict:
    """Persist role overrides. Returns the effective policy."""
    base = _root(root)
    cleaned = {role: spec for role, spec in policy.items()
               if role in ROLES and isinstance(spec, dict)}
    _write_json(base / "models.json", cleaned)
    return models_policy(base)


def models_get(root: str | Path | None = None) -> dict:
    """Load the routing policy (defaults when absent)."""
    return models_policy(root)


def models_set(policy: dict, root: str | Path | None = None) -> dict:
    """Persist the routing policy. Returns the effective policy."""
    return models_set_policy(policy, root)


def models_family(selector: str) -> str:
    """Opaque family of a `provider/model-id` selector."""
    return selector.split("/", 1)[0] if selector else ""


def _selector_of(candidate: dict | str) -> str:
    if isinstance(candidate, str):
        return candidate
    return candidate.get("selector") or (
        f"{candidate.get('provider', '')}/{candidate.get('id', '')}".strip("/"))


def models_pick_critic(own_selector: str,
                       candidates: list[dict | str]) -> str | None:
    """First candidate from a different family, else None (inherit).

    `candidates` are `rlm.find_models` rows or bare selectors. Returns a
    selector suitable for `rlm.spawn(model=...)`, or None when no
    different-family model is available — diversity is preferred, never
    mandatory.
    """
    own = models_family(own_selector)
    for candidate in candidates:
        selector = _selector_of(candidate)
        if selector and models_family(selector) != own:
            return selector
    return None
