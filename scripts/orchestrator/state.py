"""Part of the KitTools orchestrator package (split from the monolithic
execute_orchestrator.py during the 2.4.0 refactor). See the package-level
__init__ for the full public API."""
from __future__ import annotations
import json
import os
from .utils import _atomic_json_write, now_iso

STATE_SCHEMA_VERSION = 1
_REQUIRED_STATE_FIELDS_COMMON = {"status", "branch", "mode", "started_at", "updated_at", "sessions"}
_REQUIRED_STATE_FIELDS_SINGLE = _REQUIRED_STATE_FIELDS_COMMON | {"spec", "stories"}
_REQUIRED_STATE_FIELDS_EPIC = _REQUIRED_STATE_FIELDS_COMMON | {"epic", "specs"}


class StateCorrupt(Exception):
    """Raised when `.execution-state.json` cannot be parsed or is malformed.

    Caught at orchestrator entry (`main()`), which writes a critical
    notification and aborts rather than proceeding with unknown state.
    """


def _validate_state(state, expected_mode: str, state_path: str) -> None:
    """Validate state-file shape before use. Raises StateCorrupt on mismatch.

    `expected_mode`: "single" or "epic" — determines required field set.
    `state_path`: included in error messages so the user knows which file to fix.
    """
    if not isinstance(state, dict):
        raise StateCorrupt(
            f"State file {state_path} is not a JSON object (got {type(state).__name__}). "
            "Delete it to start fresh."
        )
    schema = state.get("schema_version")
    if schema is not None and isinstance(schema, int) and schema > STATE_SCHEMA_VERSION:
        raise StateCorrupt(
            f"State schema version {schema} in {state_path} is newer than this orchestrator "
            f"(supports v{STATE_SCHEMA_VERSION}). Update the kit-tools plugin, or delete "
            "the state file to start fresh."
        )
    # Missing schema_version: legacy state from pre-2.4.0. Tolerated — the
    # field will be added on the next save via save_state().
    required = _REQUIRED_STATE_FIELDS_SINGLE if expected_mode == "single" else _REQUIRED_STATE_FIELDS_EPIC
    missing = required - set(state.keys())
    if missing:
        raise StateCorrupt(
            f"State file {state_path} is missing required fields: {sorted(missing)}. "
            f"It may be corrupt or from a different orchestrator mode (expected {expected_mode}). "
            "Delete it to start fresh."
        )


def _read_state_file(state_path: str):
    """Read and parse state file. Raises StateCorrupt on JSON or IO errors."""
    try:
        with open(state_path, "r") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        raise StateCorrupt(
            f"State file {state_path} is not valid JSON ({e}). "
            "This may be from a crash mid-write. Delete it to start fresh."
        ) from e
    except OSError as e:
        raise StateCorrupt(
            f"Could not read state file {state_path}: {e}"
        ) from e


def load_or_create_state(config: dict) -> tuple[dict, bool]:
    """Read or create .execution-state.json for single mode. Returns (state, is_rerun)."""
    state_path = get_state_path(config)
    if os.path.exists(state_path):
        state = _read_state_file(state_path)
        _validate_state(state, "single", state_path)
        # If resuming a completed/failed run, reset status
        if state.get("status") in ("completed", "failed"):
            state["status"] = "running"
            return state, True
        return state, False

    return {
        "schema_version": STATE_SCHEMA_VERSION,
        "spec": os.path.basename(config["spec_path"]),
        "branch": config["branch_name"],
        "mode": config["mode"],
        "max_retries": config.get("max_retries"),
        "started_at": now_iso(),
        "updated_at": now_iso(),
        "status": "running",
        "stories": {},
        "sessions": {"total": 0, "implementation": 0, "verification": 0, "validation": 0},
    }, False


def load_or_create_epic_state(config: dict) -> tuple[dict, bool]:
    """Read or create .execution-state.json for epic mode. Returns (state, is_rerun)."""
    state_path = get_state_path(config)
    if os.path.exists(state_path):
        state = _read_state_file(state_path)
        _validate_state(state, "epic", state_path)
        if state.get("status") in ("completed", "failed"):
            state["status"] = "running"
            return state, True
        return state, False

    return {
        "schema_version": STATE_SCHEMA_VERSION,
        "epic": config["epic_name"],
        "branch": config["branch_name"],
        "mode": config["mode"],
        "max_retries": config.get("max_retries"),
        "started_at": now_iso(),
        "updated_at": now_iso(),
        "status": "running",
        "current_spec": None,
        "specs": {},
        "sessions": {"total": 0, "implementation": 0, "verification": 0, "validation": 0},
    }, False


def save_state(state: dict, config: dict) -> None:
    """Write .execution-state.json atomically.

    Called on the order of 20+ times per story attempt; atomic writes prevent
    mid-write crashes from corrupting the state file and losing story
    completion records. Also stamps the current schema version on every save
    so legacy state gets upgraded transparently.
    """
    state["updated_at"] = now_iso()
    state["schema_version"] = STATE_SCHEMA_VERSION
    state_path = get_state_path(config)
    _atomic_json_write(state_path, state)


def get_state_path(config: dict) -> str:
    """Return path to .execution-state.json in the project."""
    return os.path.join(config["project_dir"], "kit_tools", "specs", ".execution-state.json")


def update_state_story(
    state: dict, story_id: str, status: str, attempt: int,
    learnings: list | None = None, failure: str | None = None,
    spec_key: str | None = None, failure_type: str | None = None,
    warnings: list | None = None, files_changed: list | None = None,
) -> None:
    """Update a story's entry in the execution state.

    Args:
        spec_key: If set, update state["specs"][spec_key]["stories"][story_id] (epic mode).
                 If None, update state["stories"][story_id] (single mode).
        failure_type: Classified failure type (TIMEOUT_IMPL, TIMEOUT_VERIFY, etc.)
        warnings: List of non-blocking warning strings from pass_with_warnings verdicts.
        files_changed: List of changed file paths (stored for regression detection).
    """
    if spec_key is not None:
        stories_dict = state["specs"][spec_key].setdefault("stories", {})
    else:
        stories_dict = state.setdefault("stories", {})

    entry = stories_dict.get(story_id, {})
    entry["status"] = status
    entry["attempts"] = attempt

    if status == "completed":
        entry["completed_at"] = now_iso()
    if learnings:
        # Cap per-story learnings to prevent unbounded growth (fix #7)
        existing = entry.setdefault("learnings", [])
        existing.extend(learnings)
        if len(existing) > 20:
            entry["learnings"] = existing[-20:]
    if failure:
        entry["last_failure"] = failure
    if failure_type:
        entry["failure_type"] = failure_type
    if warnings is not None:
        entry["warnings"] = warnings
    if files_changed is not None:
        entry["files_changed"] = files_changed

    stories_dict[story_id] = entry


def _store_attempt_diff(state: dict, story_id: str, diff: str, spec_key: str | None) -> None:
    """Store last_attempt_diff in the correct location (single or epic mode)."""
    if spec_key is not None:
        state["specs"][spec_key].setdefault("stories", {}).setdefault(story_id, {})["last_attempt_diff"] = diff
    else:
        state.setdefault("stories", {}).setdefault(story_id, {})["last_attempt_diff"] = diff


