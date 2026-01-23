#!/usr/bin/env python3
"""
validate_setup.py - Validates kit_tools setup.

This script can be called to verify the kit_tools setup is complete and valid.
It checks for required files, unfilled placeholders, and common issues.

Currently called by: init-project skill (Step 7)
Can also be run manually: python3 hooks/validate_setup.py
"""
import json
import os
import re
from pathlib import Path


def check_required_files(kit_tools_dir: Path) -> list[str]:
    """Check that core required files exist."""
    required = [
        "AGENT_README.md",
        "SYNOPSIS.md",
        "SESSION_LOG.md",
        "arch/CODE_ARCH.md",
        "docs/LOCAL_DEV.md",
        "docs/GOTCHAS.md",
        "roadmap/MVP_TODO.md",
        "roadmap/BACKLOG.md",
    ]

    missing = []
    for file in required:
        if not (kit_tools_dir / file).exists():
            missing.append(file)

    return missing


def check_placeholders(kit_tools_dir: Path) -> list[str]:
    """Check for unfilled placeholder text in files."""
    placeholder_patterns = [
        r'\[Feature Name\]',
        r'\[Project Name\]',
        r'\[Your Name\]',
        r'\[TODO\]',
        r'YYYY-MM-DD',  # Unfilled dates
    ]

    files_with_placeholders = []

    for md_file in kit_tools_dir.rglob("*.md"):
        # Skip scratchpad and progress files
        if "SCRATCH" in md_file.name or "PROGRESS" in md_file.name:
            continue

        try:
            content = md_file.read_text()
            for pattern in placeholder_patterns:
                if re.search(pattern, content):
                    rel_path = md_file.relative_to(kit_tools_dir)
                    if str(rel_path) not in files_with_placeholders:
                        files_with_placeholders.append(str(rel_path))
                    break
        except Exception:
            pass

    return files_with_placeholders


def check_claude_md(project_dir: Path) -> bool:
    """Check if CLAUDE.md exists and has scratchpad instructions."""
    claude_md = project_dir / "CLAUDE.md"
    if not claude_md.exists():
        return False

    content = claude_md.read_text()
    return "SESSION_SCRATCH" in content or "scratchpad" in content.lower()


def main():
    # Get tool input from stdin
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        return

    # Only run after init-project skill
    tool_name = data.get("tool_name", "")
    if "init-project" not in str(data.get("tool_input", {})).lower():
        # Check if this was a skill invocation for init-project
        session_id = data.get("session_id", "")
        # This is a simple heuristic - in practice, we'd need better detection
        pass

    project_dir = os.environ.get("CLAUDE_PROJECT_DIR", "")
    if not project_dir:
        return

    project_path = Path(project_dir)
    kit_tools_dir = project_path / "kit_tools"

    # Only validate if kit_tools exists
    if not kit_tools_dir.is_dir():
        return

    issues = []

    # Check required files
    missing = check_required_files(kit_tools_dir)
    if missing:
        issues.append(f"Missing core files: {', '.join(missing)}")

    # Check CLAUDE.md
    if not check_claude_md(project_path):
        issues.append("CLAUDE.md missing or doesn't have scratchpad instructions")

    # Check for placeholders (informational, not blocking)
    placeholders = check_placeholders(kit_tools_dir)

    # Build response
    if issues:
        print(json.dumps({
            "message": f"kit_tools setup issues: {'; '.join(issues)}. Run /kit-tools:seed-project to populate."
        }))
    elif placeholders:
        print(json.dumps({
            "message": f"kit_tools initialized. {len(placeholders)} files have placeholder text - run /kit-tools:seed-project to populate."
        }))
    else:
        print(json.dumps({
            "message": "kit_tools setup validated successfully."
        }))


# Need to import sys for stdin
import sys

if __name__ == "__main__":
    main()
