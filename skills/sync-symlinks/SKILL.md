---
name: sync-symlinks
description: Force-refresh kit-tools skill symlinks after a plugin update
---

# Sync Symlinks

Force-refresh the skill symlinks in `~/.claude/skills/` to match the currently installed kit-tools version. Use this when skills appear stale after a `/plugin update` (e.g., old skills still showing, new skills missing).

## Step 1: Detect current state

Read `~/.claude/plugins/installed_plugins.json` and find the `kit-tools@washingbearlabs` entry.

Extract the `installPath` and `version` fields. Report:

```
Installed version: [version]
Install path: [installPath]
```

Then list the current symlinks in `~/.claude/skills/` that start with `kit-tools-`. For each, note what version path it points to.

If all symlinks already point to the correct install path, report that everything is in sync and stop.

## Step 2: Run the sync script

Run the sync script with the correct plugin root from Step 1:

```bash
CLAUDE_PLUGIN_ROOT="[installPath]" echo '{}' | python3 "[installPath]/hooks/sync_skill_symlinks.py"
```

## Step 3: Verify and report

List the symlinks again to confirm they now point to the correct version. Report a summary:

```
Symlinks updated to [version]:
- Added: [list of new skills, if any]
- Updated: [list of re-pointed skills, if any]
- Removed: [list of orphaned skills cleaned up, if any]

Restart Claude Code for the updated skills to take effect in your session.
```

If the script produced no output (no changes needed), report that symlinks were already correct.
