#!/usr/bin/env python3
"""
validate_setup.py - Validates kit_tools setup.

This script can be called to verify the kit_tools setup is complete and valid.
It checks for required files, unfilled placeholders, and common issues.

Currently called by: init-project skill (Step 7)
Can also be run manually: python3 hooks/validate_setup.py

Placeholder detection logic is shared with validate_seeded_template.py
via _placeholders.py so both hooks see the same coverage.
"""
import json
import os
from pathlib import Path

from _placeholders import file_has_placeholders, should_validate_path


def check_required_files(kit_tools_dir: Path) -> list[str]:
    """Check that core required files exist."""
    required = [
        "AGENT_README.md",
        "SYNOPSIS.md",
        "SESSION_LOG.md",
        "arch/CODE_ARCH.md",
        "docs/LOCAL_DEV.md",
        "docs/GOTCHAS.md",
        "roadmap/MILESTONES.md",
        "roadmap/BACKLOG.md",
    ]

    missing = []
    for file in required:
        if not (kit_tools_dir / file).exists():
            missing.append(file)
    return missing


def check_placeholders(kit_tools_dir: Path) -> list[str]:
    """Return list of kit_tools-relative paths that contain placeholders."""
    files_with_placeholders: list[str] = []
    for md_file in kit_tools_dir.rglob("*.md"):
        # Delegate path-level exclusion to the shared module.
        if not should_validate_path(str(md_file)):
            continue
        if file_has_placeholders(md_file):
            rel_path = str(md_file.relative_to(kit_tools_dir))
            if rel_path not in files_with_placeholders:
                files_with_placeholders.append(rel_path)
    return files_with_placeholders


def check_claude_md(project_dir: Path) -> bool:
    """Check if CLAUDE.md exists and has scratchpad instructions."""
    claude_md = project_dir / "CLAUDE.md"
    if not claude_md.exists():
        return False

    content = claude_md.read_text()
    return "SESSION_SCRATCH" in content or "scratchpad" in content.lower()


def main():
    # validate_setup.py is a script (called by /kit-tools:init-project), not a
    # registered hook — no stdin protocol to consume.
    project_dir = os.environ.get("CLAUDE_PROJECT_DIR", "")
    if not project_dir:
        return

    project_path = Path(project_dir)
    kit_tools_dir = project_path / "kit_tools"

    # Only validate if kit_tools exists
    if not kit_tools_dir.is_dir():
        return

    issues = []

    missing = check_required_files(kit_tools_dir)
    if missing:
        issues.append(f"Missing core files: {', '.join(missing)}")

    if not check_claude_md(project_path):
        issues.append("CLAUDE.md missing or doesn't have scratchpad instructions")

    placeholders = check_placeholders(kit_tools_dir)

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


if __name__ == "__main__":
    main()
