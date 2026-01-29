#!/usr/bin/env python3
"""
sync_skill_symlinks.py - Syncs kit-tools skills to ~/.claude/skills/ for autocomplete visibility.

Trigger: SessionStart

Due to a known Claude Code bug, skills from installed plugins don't appear in autocomplete
suggestions. This hook creates symlinks from the plugin's skills directory to ~/.claude/skills/
so they appear in the autocomplete menu.

The script is idempotent and self-healing:
- Creates ~/.claude/skills/ if it doesn't exist
- Creates symlinks for all current plugin skills
- Updates symlinks if they point to wrong location
- Removes orphaned kit-tools-* symlinks for skills that no longer exist
"""
import json
import os
import sys
from pathlib import Path


# Prefix for symlinks to identify kit-tools skills
SYMLINK_PREFIX = "kit-tools-"


def get_plugin_skills_dir() -> Path | None:
    """Get the plugin's skills directory from environment."""
    plugin_root = os.environ.get("CLAUDE_PLUGIN_ROOT")
    if not plugin_root:
        return None

    skills_dir = Path(plugin_root) / "skills"
    if skills_dir.is_dir():
        return skills_dir
    return None


def get_user_skills_dir() -> Path:
    """Get the user's skills directory, creating if needed."""
    skills_dir = Path.home() / ".claude" / "skills"
    skills_dir.mkdir(parents=True, exist_ok=True)
    return skills_dir


def get_plugin_skill_names(skills_dir: Path) -> set[str]:
    """Get all skill names from the plugin's skills directory."""
    skill_names = set()

    for item in skills_dir.iterdir():
        if item.is_dir():
            skill_file = item / "SKILL.md"
            if skill_file.exists():
                skill_names.add(item.name)

    return skill_names


def get_existing_kit_tools_symlinks(user_skills_dir: Path) -> dict[str, Path]:
    """Get existing kit-tools-* symlinks and their targets."""
    symlinks = {}

    for item in user_skills_dir.iterdir():
        if item.name.startswith(SYMLINK_PREFIX) and item.is_symlink():
            # Extract skill name from symlink name
            skill_name = item.name[len(SYMLINK_PREFIX):]
            symlinks[skill_name] = item

    return symlinks


def sync_symlinks(plugin_skills_dir: Path, user_skills_dir: Path) -> dict:
    """Sync symlinks between plugin skills and user skills directory.

    Returns a summary of actions taken.
    """
    actions = {
        "created": [],
        "updated": [],
        "removed": [],
        "unchanged": [],
    }

    # Get current state
    plugin_skills = get_plugin_skill_names(plugin_skills_dir)
    existing_symlinks = get_existing_kit_tools_symlinks(user_skills_dir)

    # Create or update symlinks for current plugin skills
    for skill_name in plugin_skills:
        symlink_name = f"{SYMLINK_PREFIX}{skill_name}"
        symlink_path = user_skills_dir / symlink_name
        target_path = plugin_skills_dir / skill_name

        if skill_name in existing_symlinks:
            # Check if symlink points to correct location
            existing_symlink = existing_symlinks[skill_name]
            try:
                current_target = existing_symlink.resolve()
                expected_target = target_path.resolve()

                if current_target != expected_target:
                    # Update symlink
                    existing_symlink.unlink()
                    symlink_path.symlink_to(target_path)
                    actions["updated"].append(skill_name)
                else:
                    actions["unchanged"].append(skill_name)
            except OSError:
                # Broken symlink, recreate it
                existing_symlink.unlink()
                symlink_path.symlink_to(target_path)
                actions["updated"].append(skill_name)
        else:
            # Create new symlink
            symlink_path.symlink_to(target_path)
            actions["created"].append(skill_name)

    # Remove orphaned symlinks for skills that no longer exist
    for skill_name, symlink_path in existing_symlinks.items():
        if skill_name not in plugin_skills:
            symlink_path.unlink()
            actions["removed"].append(skill_name)

    return actions


def main():
    # Read hook input from stdin (required by hook protocol)
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        data = {}

    # Get directories
    plugin_skills_dir = get_plugin_skills_dir()
    if not plugin_skills_dir:
        # Can't determine plugin root, skip silently
        return

    user_skills_dir = get_user_skills_dir()

    # Sync symlinks
    actions = sync_symlinks(plugin_skills_dir, user_skills_dir)

    # Only output a message if we made changes
    changes_made = actions["created"] or actions["updated"] or actions["removed"]

    if changes_made:
        parts = []
        if actions["created"]:
            parts.append(f"added {len(actions['created'])} skill(s)")
        if actions["updated"]:
            parts.append(f"updated {len(actions['updated'])} symlink(s)")
        if actions["removed"]:
            parts.append(f"removed {len(actions['removed'])} orphaned symlink(s)")

        message = f"Kit-tools autocomplete: {', '.join(parts)}."
        print(json.dumps({"message": message}))


if __name__ == "__main__":
    main()
