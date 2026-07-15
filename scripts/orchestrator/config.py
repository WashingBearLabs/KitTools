"""Part of the KitTools orchestrator package (split from the monolithic
execute_orchestrator.py during the 2.4.0 refactor). See the package-level
__init__ for the full public API."""
from __future__ import annotations
import json

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


def get_model_config(config: dict) -> dict:
    """Return the merged model config (defaults + per-run overrides).

    Reads `config["model_config"]` if present and merges it over
    `DEFAULT_MODEL_CONFIG`. Empty-string values are treated as "use default"
    (prevents accidental `--model ""` invocations). `escalation` is always
    normalised to the `{to, on_attempt, sizes}` policy dict shape regardless
    of whether the override (or the default) used the legacy flat-string form.
    """
    overrides = config.get("model_config") or {}
    merged = dict(DEFAULT_MODEL_CONFIG)
    if isinstance(overrides, dict):
        for key, value in overrides.items():
            if key == "escalation":
                continue  # handled below regardless of string/dict shape
            if isinstance(value, str) and value.strip():
                merged[key] = value.strip()
    escalation_override = overrides.get("escalation") if isinstance(overrides, dict) else None
    merged["escalation"] = _normalise_escalation(
        escalation_override if escalation_override is not None else merged.get("escalation")
    )
    return merged


