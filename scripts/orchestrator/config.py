"""Part of the KitTools orchestrator package (split from the monolithic
execute_orchestrator.py during the 2.4.0 refactor). See the package-level
__init__ for the full public API."""
from __future__ import annotations
import json
import os

DEFAULT_MODEL_CONFIG = {
    "implementer": "sonnet",
    "verifier": "opus",
    # Outer session that runs `/kit-tools:validate-implementation` (which in
    # turn dispatches review agents). Opus because the outer session makes
    # judgment calls about which findings to fix and how to aggregate them —
    # those benefit from the stronger reasoning model.
    "validator": "opus",
    # Used when retrying large stories — Sonnet's first attempt explored and
    # timed out, so the retry benefits from a model that processes large
    # context faster and makes implementation decisions more decisively. A
    # dict, not a flat model name, so the trigger (which attempt, which spec
    # sizes) is data an ablation can vary, not a hardcoded `if` in executor.py.
    "escalation": {"to": "opus", "on_attempt": 2, "sizes": ["L", "XL"]},
}


def load_config(config_path: str) -> dict:
    """Read .execution-config.json written by the skill."""
    with open(config_path, "r") as f:
        return json.load(f)


def load_model_preferences(project_dir: str | None) -> dict:
    """Return the committed project model preferences, if any.

    Reads `<project_dir>/kit_tools/model_preferences.json` and returns its
    `models` block (a dict of role -> model alias/id). This is the shared,
    version-controlled defaults file that the review skills
    (validate-epic / validate-implementation / sync-project) and the
    `configure-models` skill also read, so the whole plugin resolves model
    choices from one source of truth. Returns `{}` when the file is absent,
    unreadable, malformed, or has no `models` object — it is an *optional*
    default layer that sits beneath any per-run `.execution-config.json`
    override, so its absence must never break a run.
    """
    if not project_dir:
        return {}
    path = os.path.join(project_dir, "kit_tools", "model_preferences.json")
    try:
        with open(path, "r") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return {}
    models = data.get("models") if isinstance(data, dict) else None
    return models if isinstance(models, dict) else {}


def _normalise_escalation(value) -> dict:
    """Coerce an `escalation` value into the policy dict shape.

    Back-compat: pre-2.9.0 configs (and any override) could set `escalation`
    to a flat model-name string, which meant "escalate to this model on
    attempt > 1 for L/XL specs" — today's hardcoded trigger. A bare string is
    normalised to that exact policy so existing projects don't change
    behavior on upgrade. A partial dict has its missing keys filled from the
    same defaults — explicit `None` values are treated as missing too (not
    merged in as-is), so e.g. `{"sizes": null}` falls back to the default
    list instead of leaving `sizes` as `None` (which would crash the `in`
    check in executor.py's trigger).
    """
    defaults = DEFAULT_MODEL_CONFIG["escalation"]
    if isinstance(value, str) and value.strip():
        return {**defaults, "to": value.strip()}
    if isinstance(value, dict):
        cleaned = {k: v for k, v in value.items() if v is not None}
        return {**defaults, **cleaned}
    return dict(defaults)  # copy — never hand back the shared module-level dict


def _apply_role_overrides(merged: dict, source) -> None:
    """Copy string role values from `source` onto `merged`, in place.

    Skips `escalation` (normalised separately by the caller), empty or
    whitespace-only strings (treated as "fall through to the layer below"),
    and non-string values (ignored rather than coerced). Unknown keys pass
    through unchanged so future roles survive the merge. A non-dict `source`
    (e.g. a malformed list) is a no-op.
    """
    if not isinstance(source, dict):
        return
    for key, value in source.items():
        if key == "escalation":
            continue
        if isinstance(value, str) and value.strip():
            merged[key] = value.strip()


def get_model_config(config: dict) -> dict:
    """Return the merged model config across all layers.

    Precedence (lowest to highest):
      1. `DEFAULT_MODEL_CONFIG` — the built-in Sonnet/Opus split.
      2. Committed project preferences — `kit_tools/model_preferences.json`
         (`models` block), shared with the review skills so the orchestrator's
         defaults come from the same file the rest of the plugin reads.
      3. Per-run override — `config["model_config"]` from
         `.execution-config.json`, so a single run can still deviate.

    Empty-string values at any layer mean "use the layer below" (prevents
    accidental `--model ""` invocations). `escalation` is always normalised to
    the `{to, on_attempt, sizes}` policy dict shape regardless of which layer
    supplied it or whether it used the legacy flat-string form.
    """
    prefs = load_model_preferences(config.get("project_dir"))
    overrides = config.get("model_config") or {}
    merged = dict(DEFAULT_MODEL_CONFIG)
    # Layer 2: committed project preferences.
    _apply_role_overrides(merged, prefs)
    # Layer 3: per-run override.
    _apply_role_overrides(merged, overrides)
    # Escalation precedence: per-run override, else committed prefs, else default.
    escalation_override = overrides.get("escalation") if isinstance(overrides, dict) else None
    if escalation_override is None and isinstance(prefs, dict):
        escalation_override = prefs.get("escalation")
    merged["escalation"] = _normalise_escalation(
        escalation_override if escalation_override is not None else merged.get("escalation")
    )
    return merged


