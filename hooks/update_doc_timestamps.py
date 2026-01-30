#!/usr/bin/env python3
"""
update_doc_timestamps.py - Updates "Last updated:" in kit_tools docs.

Trigger: PostToolUse (Edit|Write)
"""
import json
import re
import sys
from datetime import date
from pathlib import Path


def main():
    # Read hook input from stdin
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        return

    # Get the file path from tool input
    file_path = data.get("tool_input", {}).get("file_path", "")
    if not file_path:
        return

    path = Path(file_path)

    # Only process markdown files in kit_tools/ (but not SESSION_SCRATCH)
    if not path.suffix == ".md":
        return
    if "kit_tools" not in path.parts:
        return
    if "SESSION_SCRATCH" in path.name:
        return

    # Check if file exists and has a "Last updated:" line
    if not path.exists():
        return

    content = path.read_text()
    today = date.today().isoformat()

    # Replace "Last updated: YYYY-MM-DD" or similar
    # Handles: "> Last updated: ...", "Last Updated: ...", etc.
    new_content, count = re.subn(
        r"^(>\s*)?Last [Uu]pdated:.*$",
        rf"\g<1>Last updated: {today}",
        content,
        flags=re.MULTILINE
    )

    if count > 0 and new_content != content:
        path.write_text(new_content)


if __name__ == "__main__":
    main()
