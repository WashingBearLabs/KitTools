#!/usr/bin/env python3
"""
create_scratchpad.py - Creates SESSION_SCRATCH.md on session start.

Trigger: SessionStart
"""
import json
import os
import sys
from pathlib import Path


def main():
    project_dir = os.environ.get("CLAUDE_PROJECT_DIR", "")
    if not project_dir:
        return

    kit_tools_dir = Path(project_dir) / "kit_tools"
    scratchpad = kit_tools_dir / "SESSION_SCRATCH.md"

    # Only create if kit_tools exists but scratchpad doesn't
    if kit_tools_dir.is_dir() and not scratchpad.exists():
        content = """# SESSION_SCRATCH.md

> Auto-generated. Append notes as you work. Processed on session close.

## Active Feature

**Working on:** [Feature name or "General" if not feature-specific]
**TODO File:** [e.g., `FEATURE_TODO_auth.md` or `MVP_TODO.md`]

---

## Notes

"""
        scratchpad.write_text(content)
        print(json.dumps({"message": "Created SESSION_SCRATCH.md - ready to capture notes"}))


if __name__ == "__main__":
    main()
