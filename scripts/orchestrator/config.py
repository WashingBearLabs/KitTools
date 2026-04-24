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
    # Used when retrying size-L/XL stories — Sonnet's first attempt explored
    # and timed out, so the retry benefits from a model that processes large
    # context faster and makes implementation decisions more decisively.
    "escalation": "opus",
}


def load_config(config_path: str) -> dict:
    """Read .execution-config.json written by the skill."""
    with open(config_path, "r") as f:
        return json.load(f)


def get_model_config(config: dict) -> dict:
    """Return the merged model config (defaults + per-run overrides).

    Reads `config["model_config"]` if present and merges it over
    `DEFAULT_MODEL_CONFIG`. Empty-string values are treated as "use default"
    (prevents accidental `--model ""` invocations).
    """
    overrides = config.get("model_config") or {}
    merged = dict(DEFAULT_MODEL_CONFIG)
    if isinstance(overrides, dict):
        for key, value in overrides.items():
            if isinstance(value, str) and value.strip():
                merged[key] = value.strip()
    return merged


