#!/usr/bin/env python3
"""
remind_close_session.py - Reminds to run /kit-tools:close-session if scratchpad has notes.

Trigger: Stop
"""
import json
import os
import sys
from pathlib import Path


def main():
    # Consume stdin per hook protocol
    try:
        json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        pass

    project_dir = os.environ.get("CLAUDE_PROJECT_DIR", "")
    if not project_dir:
        return

    scratchpad = Path(project_dir) / "kit_tools" / "SESSION_SCRATCH.md"

    if not scratchpad.exists():
        return

    # Check for actual content below the ## Notes header
    content = scratchpad.read_text()

    # Find the ## Notes section and check if there's content below it
    notes_idx = content.find("## Notes")
    if notes_idx == -1:
        return

    notes_content = content[notes_idx + len("## Notes"):].strip()
    # Filter out compaction markers and blank lines
    meaningful_lines = [
        line for line in notes_content.split("\n")
        if line.strip() and "Context compacted" not in line
    ]

    if meaningful_lines:
        print(json.dumps({
            "message": "SESSION_SCRATCH.md has notes. Run /kit-tools:close-session when done."
        }))


if __name__ == "__main__":
    main()
