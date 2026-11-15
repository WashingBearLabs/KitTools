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


class ConfigError(ValueError):
    """The execution config is missing or has malformed required fields."""


_VALID_MODES = ("autonomous", "guarded", "supervised")


def _normalise_spec_entry(raw, index: int, count: int, project_dir: str) -> dict | str:
    """Return an ``epic_specs`` entry in dict form, or an error message.

    A plain string entry is a spec path (issue #16). A bare filename resolves
    under ``kit_tools/specs/``; any other relative path resolves against
    ``project_dir``. Missing ``feature_name``/``epic_seq``/``epic_final`` are
    filled from the path and position.
    """
    if isinstance(raw, str):
        raw = {"spec_path": raw}
    if not isinstance(raw, dict):
        return f"epic_specs[{index}] must be a spec path or an object, got {type(raw).__name__}"
    entry: dict = dict(raw)
    spec_path = entry.get("spec_path")
    if not isinstance(spec_path, str) or not spec_path.strip():
        return f"epic_specs[{index}] has no spec_path"
    spec_path = spec_path.strip()
    if not os.path.isabs(spec_path):
        if os.path.dirname(spec_path):
            spec_path = os.path.join(project_dir, spec_path)
        else:
            spec_path = os.path.join(project_dir, "kit_tools", "specs", spec_path)
    entry["spec_path"] = spec_path
    if not entry.get("feature_name"):
        name = os.path.splitext(os.path.basename(spec_path))[0]
        entry["feature_name"] = name[len("feature-"):] if name.startswith("feature-") else name
    entry.setdefault("epic_seq", index + 1)
    entry.setdefault("epic_final", index == count - 1)
    return entry


def validate_config(
    config, current_branch: str = "", default_branch: str = "",
) -> dict:
    """Check the required fields up front and normalise the forgiving ones.

    A config assembled by hand or from an incomplete template used to pass
    load_config and then crash mid-launch with a bare KeyError or TypeError
    (issues #15, #16). Every problem is collected into one ConfigError instead.

    - ``branch_name`` missing: derived from ``current_branch`` (the branch the
      worktree is on), unless that is empty (detached HEAD) or the default
      branch, which the orchestrator must never commit to directly.
    - ``epic_specs`` entries may be plain spec paths; they become dicts.
    """
    if not isinstance(config, dict):
        raise ConfigError("the config must be a JSON object")
    problems = []

    project_dir = config.get("project_dir")
    if not isinstance(project_dir, str) or not project_dir.strip():
        problems.append("project_dir is missing")
        project_dir = ""

    mode = config.get("mode")
    if mode not in _VALID_MODES:
        problems.append(f"mode must be one of {', '.join(_VALID_MODES)} (got {mode!r})")

    branch = config.get("branch_name")
    if not isinstance(branch, str) or not branch.strip():
        if current_branch and current_branch != default_branch:
            config["branch_name"] = current_branch
        else:
            where = "HEAD is detached" if not current_branch else f"HEAD is on {current_branch!r}"
            problems.append(
                f"branch_name is missing and can't be derived ({where}). "
                f"Set it to the execution branch, e.g. \"epic/<name>\""
            )

    if "epic_specs" in config:
        specs = config.get("epic_specs")
        if not isinstance(specs, list) or not specs:
            problems.append("epic_specs must be a non-empty list")
        else:
            normalised = []
            for i, entry in enumerate(specs):
                result = _normalise_spec_entry(entry, i, len(specs), project_dir)
                if isinstance(result, str):
                    problems.append(result)
                else:
                    normalised.append(result)
            if len(normalised) == len(specs):
                config["epic_specs"] = normalised
        epic_name = config.get("epic_name")
        if not isinstance(epic_name, str) or not epic_name.strip():
            problems.append("epic_name is missing (required with epic_specs)")
    else:
        spec_path = config.get("spec_path")
        if not isinstance(spec_path, str) or not spec_path.strip():
            problems.append("set either epic_specs (epic run) or spec_path (single-spec run)")

    if problems:
        raise ConfigError(
            "Invalid .execution-config.json:\n" + "\n".join(f"  - {p}" for p in problems)
        )
    return config


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


# Role values that mean "no preference here, use the layer below", like an
# empty string. "auto" is the KitToolsCopilot default and is invalid for
# `claude --model`; a project set up with the Copilot build carries it over
# into model_preferences.json (issue #18).
_FALLTHROUGH_MODEL_VALUES = frozenset({"auto", "default"})


def _is_set_model(value) -> bool:
    """True for a non-empty model string that isn't a fall-through value."""
    return (
        isinstance(value, str)
        and bool(value.strip())
        and value.strip().lower() not in _FALLTHROUGH_MODEL_VALUES
    )


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
    if _is_set_model(value):
        return {**defaults, "to": value.strip()}
    if isinstance(value, dict):
        cleaned = {k: v for k, v in value.items() if v is not None}
        if "to" in cleaned and not _is_set_model(cleaned["to"]):
            del cleaned["to"]
        return {**defaults, **cleaned}
    return dict(defaults)  # copy — never hand back the shared module-level dict


def _apply_role_overrides(merged: dict, source) -> None:
    """Copy string role values from `source` onto `merged`, in place.

    Skips `escalation` (normalised separately by the caller), empty or
    whitespace-only strings and "auto"/"default" (all treated as "fall
    through to the layer below"),
    and non-string values (ignored rather than coerced). Unknown keys pass
    through unchanged so future roles survive the merge. A non-dict `source`
    (e.g. a malformed list) is a no-op.
    """
    if not isinstance(source, dict):
        return
    for key, value in source.items():
        if key == "escalation":
            continue
        if _is_set_model(value):
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

    Empty-string, "auto" and "default" values at any layer mean "use the layer
    below" (prevents `--model ""` and `--model auto` invocations). `escalation` is always normalised to
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
    def _escalation_at(layer):
        value = layer.get("escalation") if isinstance(layer, dict) else None
        # A bare "auto"/"default"/"" falls through to the layer below.
        if isinstance(value, str) and not _is_set_model(value):
            return None
        return value

    escalation_override = _escalation_at(overrides)
    if escalation_override is None:
        escalation_override = _escalation_at(prefs)
    merged["escalation"] = _normalise_escalation(
        escalation_override if escalation_override is not None else merged.get("escalation")
    )
    return merged


