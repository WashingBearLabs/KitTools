#!/usr/bin/env python3
"""
remind_scratchpad_before_compact.py - Reminds and logs before context compaction.

Trigger: PreCompact

This hook:
1. Reminds Claude to capture notes before context is lost
2. Auto-appends a compaction marker to the scratchpad for breadcrumb tracking
"""
import json
import os
from datetime import datetime
from pathlib import Path


def main():
    project_dir = os.environ.get("CLAUDE_PROJECT_DIR", "")
    if not project_dir:
        return

    kit_tools_dir = Path(project_dir) / "kit_tools"
    scratchpad = kit_tools_dir / "SESSION_SCRATCH.md"

    # Only trigger if kit_tools is set up
    if not kit_tools_dir.is_dir():
        return

    # Get current time for the marker
    now = datetime.now().strftime("%H:%M")

    # If scratchpad exists, append compaction marker
    if scratchpad.exists():
        content = scratchpad.read_text()
        marker = f"\n[{now}] --- Context compacted, session continuing ---\n"

        # Only add marker if not already the last thing added
        if "Context compacted" not in content.strip().split("\n")[-3:]:
            scratchpad.write_text(content + marker)

    # Always remind before compaction
    print(json.dumps({
        "message": f"Context compacting at {now}. Ensure SESSION_SCRATCH.md captures work done so far."
    }))


if __name__ == "__main__":
    main()
