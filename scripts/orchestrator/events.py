"""Part of the KitTools orchestrator package (split from the monolithic
execute_orchestrator.py during the 2.4.0 refactor). See the package-level
__init__ for the full public API."""
from __future__ import annotations
import json
import os
import platform
import subprocess
import uuid

from .utils import now_iso

NOTIFICATION_FILE = os.path.join("kit_tools", ".execution-notifications")
EVENTS_FILE = os.path.join("kit_tools", ".execution-events.jsonl")
DESKTOP_NOTIFY_SEVERITIES = {"critical", "warning"}
DESKTOP_NOTIFY_TYPES = {"execution_complete", "execution_crashed", "epic_complete"}

# Trace event envelope. Bump on a breaking change (field removed/renamed);
# additions are non-breaking because every reader ignores unknown fields.
# See docs/trace-schema.md for the compatibility contract.
EVENT_SCHEMA_VERSION = "1"

# Monotonic per-process counter so event_ids are unique even when two events
# land in the same microsecond. event_id sorts lexically (ISO prefix), giving a
# stable total order within a run for the reducer. The per-process suffix keeps
# ids from colliding across processes / a module reload that resets the counter
# (the suffix is constant within a process, so it doesn't disturb sort order).
_EVENT_SEQ = 0
_PROC_SUFFIX = uuid.uuid4().hex[:6]


def _next_event_id() -> str:
    global _EVENT_SEQ
    _EVENT_SEQ += 1
    return f"{now_iso()}#{_EVENT_SEQ:06d}-{_PROC_SUFFIX}"


def new_run_id() -> str:
    """Mint a sortable, collision-resistant id for one orchestrator run.

    Shape: ``run-<compact-utc>-<8hex>``. The timestamp prefix keeps runs
    lexically sortable; the random suffix disambiguates same-second launches.
    Minted once at ``run.started`` and stamped on every event + the harvested
    record so the reducer can upsert idempotently (the Stop hook fires once per
    session, but a run spans many sessions).
    """
    compact = now_iso()[:19].replace("-", "").replace(":", "")
    return f"run-{compact}-{uuid.uuid4().hex[:8]}"


def get_notification_path(config: dict) -> str:
    """Return absolute path to the notification file."""
    return os.path.join(config["project_dir"], NOTIFICATION_FILE)


def send_desktop_notification(title: str, message: str) -> None:
    """Send an OS-level desktop notification. Best-effort — swallows all errors."""
    try:
        system = platform.system()
        if system == "Darwin":
            # macOS: use osascript
            escaped_title = title.replace('"', '\\"')
            escaped_msg = message.replace('"', '\\"')
            subprocess.run(
                ["osascript", "-e",
                 f'display notification "{escaped_msg}" with title "{escaped_title}"'],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=5,
            )
        elif system == "Linux":
            # Linux: use notify-send if available
            subprocess.run(
                ["notify-send", title, message],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=5,
            )
    except Exception:
        pass


def write_notification(
    config: dict, ntype: str, title: str, details: str, severity: str = "info"
) -> None:
    """Append a JSON Lines notification entry and send desktop notification for
    important events. Best-effort — swallows OSError."""
    try:
        path = get_notification_path(config)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        entry = {
            "type": ntype,
            "title": title,
            "details": details,
            "severity": severity,
            "feature": config.get("feature_name") or config.get("epic_name", ""),
            "timestamp": now_iso(),
        }
        with open(path, "a") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception:
        # Best-effort (guardrail 1): never raise into the run. Covers OSError
        # and a non-serializable payload (json.dumps TypeError).
        pass

    # Send desktop notification for important events
    if severity in DESKTOP_NOTIFY_SEVERITIES or ntype in DESKTOP_NOTIFY_TYPES:
        feature = config.get("feature_name") or config.get("epic_name", "")
        desktop_title = f"KitTools — {feature}" if feature else "KitTools"
        send_desktop_notification(desktop_title, details)


def log_event(
    config: dict | None, event_type: str, severity: str = "info",
    *, actor: dict | None = None, spec: str | None = None,
    story: str | None = None, **fields,
) -> None:
    """Append a structured trace event to `kit_tools/.execution-events.jsonl`.

    This is the single append-only event stream a run reduces into metrics
    (`harvest_signals`) and a future retrospective loop reduces into "what
    helped." Complement to the human-readable `log()` stdout stream: enables
    grep/jq post-mortems (e.g., `jq 'select(.severity=="error")' ...`).
    Best-effort — swallows OSError so a write failure never stops execution.

    Envelope (see docs/trace-schema.md): `schema_version`, `event_id` (sortable
    unique), `event_type`, `severity`, `at` (ISO-8601 UTC; `timestamp` kept as a
    one-version alias), `run` ({run_id, feature, spec, story}), optional `actor`
    ({kind, id, model}), and `payload` (everything else).

    `config` may be `None` for very-early events (before config load); in that
    case pass `project_dir=...` so the event file can be located.

    Reserved kwargs: `actor`, `spec`, `story`. Any other keyword args become
    `payload` fields. Don't pass huge payloads (diffs, full prompts) — this is
    for machine-grep, not transcripts.
    """
    try:
        project_dir = (
            config.get("project_dir") if isinstance(config, dict) else None
        ) or fields.pop("project_dir", None)
        if not project_dir:
            return

        run: dict = {}
        if isinstance(config, dict):
            run_id = config.get("run_id")
            if run_id:
                run["run_id"] = run_id
            feat = config.get("feature_name") or config.get("epic_name")
            if feat:
                run["feature"] = feat
        if spec:
            run["spec"] = spec
        if story:
            run["story"] = story

        now = now_iso()
        entry: dict = {
            "schema_version": EVENT_SCHEMA_VERSION,
            "event_id": _next_event_id(),
            "event_type": event_type,
            "severity": severity,
            "at": now,
            "timestamp": now,  # back-compat alias for `at` (one version)
        }
        if run:
            entry["run"] = run
        if actor:
            entry["actor"] = actor
        entry["payload"] = fields

        path = os.path.join(project_dir, EVENTS_FILE)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "a") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception:
        # Best-effort (guardrail 1): a trace write must never raise into the
        # execution path. Broad on purpose — covers OSError on write AND
        # json.dumps TypeError if a payload value is ever non-serializable.
        pass


