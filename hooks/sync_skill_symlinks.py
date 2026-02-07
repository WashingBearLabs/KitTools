#!/usr/bin/env python3
"""
sync_skill_symlinks.py - Syncs kit-tools skills to ~/.claude/skills/ for autocomplete visibility.

Trigger: SessionStart (also invocable directly via /kit-tools:sync-symlinks)

Due to a known Claude Code bug, skills from installed plugins don't appear in autocomplete
suggestions. This hook creates symlinks from the plugin's skills directory to ~/.claude/skills/
so they appear in the autocomplete menu.

The script is idempotent and self-healing:
- Creates ~/.claude/skills/ if it doesn't exist
- Creates symlinks for all current plugin skills
- Updates symlinks if they point to wrong location
- Removes orphaned kit-tools-* symlinks for skills that no longer exist
- Verifies $CLAUDE_PLUGIN_ROOT against installed_plugins.json to handle stale env vars
"""
import json
import os
import sys
from pathlib import Path


# Prefix for symlinks to identify kit-tools skills
SYMLINK_PREFIX = "kit-tools-"

# Plugin identifier in installed_plugins.json
PLUGIN_ID = "kit-tools@washingbearlabs"


def get_installed_plugin_path() -> Path | None:
    """Read installed_plugins.json to find the authoritative install path for kit-tools."""
    installed_plugins_file = Path.home() / ".claude" / "plugins" / "installed_plugins.json"
    if not installed_plugins_file.exists():
        return None

    try:
        data = json.loads(installed_plugins_file.read_text())
        plugins = data.get("plugins", {})
        entries = plugins.get(PLUGIN_ID, [])
        if entries:
            install_path = entries[0].get("installPath")
            if install_path:
                path = Path(install_path)
                if path.is_dir():
                    return path
    except (json.JSONDecodeError, KeyError, IndexError, OSError):
        pass

    return None


def get_plugin_skills_dir() -> Path | None:
    """Get the plugin's skills directory, preferring installed_plugins.json over env var.

    Uses installed_plugins.json as the source of truth for the plugin root path.
    Falls back to $CLAUDE_PLUGIN_ROOT if the JSON lookup fails. This handles the case
    where the env var is stale after a plugin update but installed_plugins.json is correct.
    """
    # Primary: read from installed_plugins.json (authoritative after plugin updates)
    installed_path = get_installed_plugin_path()
    if installed_path:
        skills_dir = installed_path / "skills"
        if skills_dir.is_dir():
            return skills_dir

    # Fallback: use environment variable
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
