#!/usr/bin/env python3
"""
check_execution_notifications.py - Surface execution notifications on next user prompt.

Trigger: UserPromptSubmit

Reads JSON Lines entries from kit_tools/.execution-notifications, deletes the file,
and outputs a batched summary message so the user knows about execution events
without needing to manually run /kit-tools:execution-status.
"""
import json
import os
import sys


def format_notification_summary(entries: list[dict]) -> str:
    """Format a list of notification entries into a human-readable summary.

    Groups story completions together, shows critical/warning items individually,
    and always ends with a hint to run execution-status.
    """
    if not entries:
        return ""

    critical = []
    warnings = []
    story_completions = []
    other = []

    for entry in entries:
        severity = entry.get("severity", "info")
        ntype = entry.get("type", "")
        if ntype == "story_complete":
            story_completions.append(entry)
        elif severity == "critical":
            critical.append(entry)
        elif severity == "warning":
            warnings.append(entry)
        else:
            other.append(entry)

    lines = ["**Execution update:**"]

    # Critical items first, individually
    for entry in critical:
        feature = entry.get("feature", "")
        feature_suffix = f" [{feature}]" if feature else ""
        lines.append(f"- CRITICAL: {entry['title']}{feature_suffix} — {entry['details']}")

    # Warning items individually
    for entry in warnings:
        feature = entry.get("feature", "")
        feature_suffix = f" [{feature}]" if feature else ""
        lines.append(f"- WARNING: {entry['title']}{feature_suffix} — {entry['details']}")

    # Story completions batched
    if story_completions:
        ids = []
        for entry in story_completions:
            # Extract story ID from title like "Story US-001 passed"
            title = entry.get("title", "")
            parts = title.split()
            for part in parts:
                if part.startswith("US-"):
                    ids.append(part)
                    break
            else:
                ids.append(title)
        lines.append(f"- {len(story_completions)} stories completed: {', '.join(ids)}")

    # Other info items individually
    for entry in other:
        feature = entry.get("feature", "")
        feature_suffix = f" [{feature}]" if feature else ""
        lines.append(f"- {entry['title']}{feature_suffix} — {entry['details']}")

    lines.append("")
    lines.append("Run `/kit-tools:execution-status` for full details.")

    return "\n".join(lines)


def main():
    # Consume stdin per hook protocol
    try:
        json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        pass

    project_dir = os.environ.get("CLAUDE_PROJECT_DIR", "")
    if not project_dir:
        return

    notification_path = os.path.join(project_dir, "kit_tools", ".execution-notifications")

    # Fast path: no notification file
    if not os.path.exists(notification_path):
        return

    # Read all entries
    entries = []
    try:
        with open(notification_path, "r") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
    except OSError:
        return

    if not entries:
        # Empty file — clean up
        try:
            os.remove(notification_path)
        except OSError:
            pass
        return

    # Delete the file (consume notifications)
    try:
        os.remove(notification_path)
    except OSError:
        pass

    # Format and output
    summary = format_notification_summary(entries)
    if summary:
        print(json.dumps({"message": summary}))


if __name__ == "__main__":
    main()
