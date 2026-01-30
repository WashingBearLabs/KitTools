---
name: update-kit-tools
description: Check for plugin updates and sync new components to your project
---

# Update Kit-Tools

Check for kit-tools plugin updates and sync new components (templates, agents, hooks) to your project.

## Dependencies

| Component | Location | Purpose |
|-----------|----------|---------|
| **Plugin manifest** | `$CLAUDE_PLUGIN_ROOT/.claude-plugin/plugin.json` | Current installed plugin version |
| **Plugin components** | `$CLAUDE_PLUGIN_ROOT/` | Templates, agents, hooks, skills to sync |
| **Project kit_tools** | `kit_tools/` | Project's documentation directory |
| **Sync marker** | `kit_tools/.kit_tools_sync.json` | Tracks last synced version |

**Related commands:**
- `/plugin marketplace update` — Updates the plugin itself from marketplace
- `/kit-tools:init-project` — Initial project setup (this skill is for updates)
- `/kit-tools:seed-project` — Populate templates after adding new ones

## Quick Reference

```bash
# Check what's new and sync
/kit-tools:update-kit-tools

# Just check, don't sync
/kit-tools:update-kit-tools --check

# Force sync even if versions match
/kit-tools:update-kit-tools --force

# Sync specific component type only
/kit-tools:update-kit-tools templates
/kit-tools:update-kit-tools hooks
```

---

## Step 1: Check Plugin Version Status

### 1a: Read current installed version

Read `$CLAUDE_PLUGIN_ROOT/.claude-plugin/plugin.json` to get the installed plugin version.

### 1b: Read last synced version

Check for `kit_tools/.kit_tools_sync.json` in the project:

```json
{
  "last_synced_version": "1.1.0",
  "last_synced_at": "2024-01-15T10:30:00Z",
  "synced_components": {
    "templates": ["SYNOPSIS.md", "arch/CODE_ARCH.md", ...],
    "agents": ["code-quality-validator.md"],
    "hooks": ["create_scratchpad.py", ...]
  }
}
```

If this file doesn't exist, this is the first sync — treat all components as new.

### 1c: Report version status

```
┌─────────────────────────────────────────────────────────────────┐
│                    KIT-TOOLS UPDATE CHECK                        │
├─────────────────────────────────────────────────────────────────┤
│  Installed plugin version: 1.2.0                                │
│  Last synced to project:   1.1.0 (2024-01-15)                  │
│  Status: Updates available                                       │
└─────────────────────────────────────────────────────────────────┘
```

If versions match and `--force` not specified:
```
Your project is up to date with the installed plugin (v1.2.0).

To check for newer plugin versions from the marketplace:
  /plugin marketplace update kit-tools
```

---

## Step 2: Inventory New Components

Compare the plugin's components against what was last synced.

### 2a: Check for new/updated templates

Compare `$CLAUDE_PLUGIN_ROOT/templates/` against sync marker:

| Status | Meaning |
|--------|---------|
| **New** | Template exists in plugin but not in sync marker |
| **Updated** | Template version comment changed (e.g., `<!-- Template Version: 1.2.0 -->`) |
| **Unchanged** | Template matches synced version |

### 2b: Check for new/updated agents

Compare `$CLAUDE_PLUGIN_ROOT/agents/` against sync marker.

### 2c: Check for new/updated hooks

Compare `$CLAUDE_PLUGIN_ROOT/hooks/*.py` against sync marker.

### 2d: Check for new skills

Compare `$CLAUDE_PLUGIN_ROOT/skills/` directories against sync marker.

### 2e: Report what's new

```
What's New in v1.2.0 (since your last sync v1.1.0):

SKILLS (2 new):
  + validate-seeding    — Validate seeded templates for placeholders
  + seed-template       — Seed a single template

AGENTS (4 new):
  + template-validator.md   — Validates seeded templates
  + generic-explorer.md     — Parameterized codebase exploration
  + generic-seeder.md       — Parameterized template seeding
  + drift-detector.md       — Doc-to-code drift detection

TEMPLATES (2 new):
  + SEED_MANIFEST.json      — Seeding progress tracking
  + SYNC_MANIFEST.json      — Sync progress tracking

TEMPLATES (28 updated):
  All templates updated with seeding frontmatter

HOOKS (1 new):
  + validate_seeded_template.py  — Post-edit placeholder check

PLUGIN-ONLY (not synced to projects):
  • sync_skill_symlinks.py — Autocomplete symlink sync (uses ${CLAUDE_PLUGIN_ROOT})
```

---

## Step 3: Present Sync Options

If `--check` flag was provided, stop here and don't make changes.

Otherwise, present options:

### Sync options:

```
What would you like to sync?

1. Sync everything (recommended)
   - Adds new templates to kit_tools/
   - Updates hooks configuration
   - Note: Won't overwrite customized templates

2. Sync templates only
   - Adds new templates to kit_tools/
   - Existing templates preserved

3. Sync hooks only
   - Updates .claude/settings.local.json with new hooks
   - Copies new hook scripts

4. Preview changes (dry run)
   - Show what would be synced without making changes

5. Skip for now
```

---

## Step 4: Execute Sync

Based on user selection:

### 4a: Sync templates

For each new template:
1. Check if file already exists in `kit_tools/`
2. If exists: Skip (don't overwrite project customizations)
3. If new: Copy from plugin to `kit_tools/`

```
Syncing templates...
  + kit_tools/SEED_MANIFEST.json (new)
  + kit_tools/SYNC_MANIFEST.json (new)
  ○ kit_tools/SYNOPSIS.md (exists, skipped)
  ○ kit_tools/arch/CODE_ARCH.md (exists, skipped)
```

### 4b: Sync hooks

For hooks, we need to update the project's hook configuration:

1. Read current `.claude/settings.local.json` (create if missing)
2. Compare hooks section against plugin's hook configuration
3. Add any missing hook entries
4. Copy new hook script files to project's `kit_tools/hooks/` directory

**Important:** Hook paths in `.claude/settings.local.json` must use `kit_tools/hooks/` prefix (not just `hooks/`).

```
Syncing hooks...
  + kit_tools/hooks/validate_seeded_template.py (new script)
  + .claude/settings.local.json (validate_seeded_template.py hook added)
  ○ create_scratchpad.py (already configured)
```

**Note:** `sync_skill_symlinks.py` is plugin-only (uses `${CLAUDE_PLUGIN_ROOT}`) — don't sync to projects.

### 4c: Note about skills and agents

Skills and agents don't need to be synced to the project — they live in the plugin and are available automatically. Just inform the user:

```
Note: New skills and agents are automatically available from the plugin.
No project-level sync needed for:
  - Skills: validate-seeding, seed-template
  - Agents: template-validator, generic-explorer, generic-seeder, drift-detector

Run /skills to see all available skills.
```

---

## Step 5: Update Sync Marker

After successful sync, update `kit_tools/.kit_tools_sync.json`:

```json
{
  "last_synced_version": "1.2.0",
  "last_synced_at": "2024-01-29T14:30:00Z",
  "synced_components": {
    "templates": [
      "SYNOPSIS.md",
      "SEED_MANIFEST.json",
      "SYNC_MANIFEST.json",
      ...
    ],
    "hooks": [
      "kit_tools/hooks/create_scratchpad.py",
      "kit_tools/hooks/update_doc_timestamps.py",
      "kit_tools/hooks/validate_seeded_template.py",
      ...
    ]
  }
}
```

---

## Step 6: Final Report

```
┌─────────────────────────────────────────────────────────────────┐
│                    SYNC COMPLETE                                 │
├─────────────────────────────────────────────────────────────────┤
│  Synced from: v1.1.0 → v1.2.0                                   │
│  Templates added: 2                                              │
│  Hooks configured: 2                                             │
└─────────────────────────────────────────────────────────────────┘

New templates added to kit_tools/:
  • SEED_MANIFEST.json
  • SYNC_MANIFEST.json

Next steps:
  • Run /kit-tools:seed-project to populate new templates
  • New skills available: /kit-tools:validate-seeding, /kit-tools:seed-template
  • Run /skills to see all available skills
```

---

## Handling Edge Cases

### Project doesn't have kit_tools/

```
No kit_tools/ directory found.

Run /kit-tools:init-project first to set up kit_tools.
```

### First time sync (no marker file)

Treat as initial sync:
- Create sync marker
- Don't copy templates (they were added by init-project)
- Just record current state

```
First sync detected. Recording current state...

Your project is now tracking kit-tools v1.2.0.
Future updates will show what's new.
```

### Template exists but has project customizations

Never overwrite existing templates. The user seeded them with project-specific content.

```
Template kit_tools/SYNOPSIS.md already exists (skipped).

To get the updated template structure:
1. Review changes: Compare plugin template vs your version
2. Manually merge any structural improvements you want
```

### Hook script modified by user

If a hook script exists in project and differs from plugin:

```
Hook remind_close_session.py differs from plugin version.

Options:
1. Keep your version (recommended if you customized it)
2. Replace with plugin version
3. Show diff
```

---

## Arguments

| Argument | Description |
|----------|-------------|
| (none) | Full update check and sync |
| `--check` | Check only, don't sync |
| `--force` | Sync even if versions match |
| `templates` | Sync templates only |
| `hooks` | Sync hooks only |
| `--dry-run` | Preview changes without applying |

---

## Checking for Marketplace Updates

This skill syncs from the **installed plugin** to your **project**.

To check if a newer plugin version is available from the marketplace:

```
/plugin marketplace update kit-tools
```

If a newer version is installed, run this skill again to sync the new components.
