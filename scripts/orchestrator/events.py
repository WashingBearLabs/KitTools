"""Part of the KitTools orchestrator package (split from the monolithic
execute_orchestrator.py during the 2.4.0 refactor). See the package-level
__init__ for the full public API."""
from __future__ import annotations
import json
import os
import platform
import subprocess

from .utils import now_iso

NOTIFICATION_FILE = os.path.join("kit_tools", ".execution-notifications")
EVENTS_FILE = os.path.join("kit_tools", ".execution-events.jsonl")
DESKTOP_NOTIFY_SEVERITIES = {"critical", "warning"}
DESKTOP_NOTIFY_TYPES = {"execution_complete", "execution_crashed", "epic_complete"}


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
    except OSError:
        pass

    # Send desktop notification for important events
    if severity in DESKTOP_NOTIFY_SEVERITIES or ntype in DESKTOP_NOTIFY_TYPES:
        feature = config.get("feature_name") or config.get("epic_name", "")
        desktop_title = f"KitTools — {feature}" if feature else "KitTools"
        send_desktop_notification(desktop_title, details)


def log_event(
    config: dict | None, event_type: str, severity: str = "info", **fields,
) -> None:
    """Append a structured JSONL event to `kit_tools/.execution-events.jsonl`.

    Complement to the human-readable `log()` stdout stream: enables grep/jq
    post-mortems across runs (e.g., `jq 'select(.severity=="error")' ...`).
    Best-effort — swallows OSError so a write failure never stops execution.

    `config` may be `None` for very-early events (before config load); in that
    case `fields` must include a `project_dir` so the event file can be located.

    Extra keyword args become additional structured fields. Don't pass huge
    payloads (diffs, full prompts) — this is for machine-grep, not transcripts.
    """
    try:
        project_dir = (
            config.get("project_dir") if isinstance(config, dict) else None
        ) or fields.pop("project_dir", None)
        if not project_dir:
            return
        entry = {
            "event_type": event_type,
            "severity": severity,
            "timestamp": now_iso(),
        }
        if isinstance(config, dict):
            feat = config.get("feature_name") or config.get("epic_name")
            if feat:
                entry["feature"] = feat
        entry.update(fields)
        path = os.path.join(project_dir, EVENTS_FILE)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "a") as f:
            f.write(json.dumps(entry) + "\n")
    except OSError:
        pass


