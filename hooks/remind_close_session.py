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

    # Count lines - if more than the header (6 lines), there are notes
    content = scratchpad.read_text()
    lines = content.strip().split("\n")

    if len(lines) > 6:
        print(json.dumps({
            "message": "SESSION_SCRATCH.md has notes. Run /kit-tools:close-session when done."
        }))


if __name__ == "__main__":
    main()
