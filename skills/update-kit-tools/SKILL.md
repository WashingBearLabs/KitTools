---
name: update-kit-tools
description: Update project kit-tools components (hooks, templates) from the latest plugin versions
---

# Update Kit-Tools

Compare and selectively update the project's kit-tools components against the latest versions from this plugin.

## Components Checked

| Component | Location | Description |
|-----------|----------|-------------|
| **Hooks** | `hooks/` | Automation scripts triggered by Claude Code events |
| **Templates** | `kit_tools/` | Documentation templates |
| **Agents** | `agents/` | Custom agents for specialized tasks |

## Step 1: Check hooks

Compare the project's `hooks/` directory against the plugin's hooks:

### 1a: Inventory hooks

| Status | Meaning |
|--------|---------|
| **Identical** | Project hook matches plugin exactly |
| **Modified** | Project hook differs (user has customized) |
| **Missing** | Hook exists in plugin but not in project |
| **Outdated config** | `hooks.json` or `.claude/settings.local.json` differs |

### 1b: Report hook status

```
Hook Status Report:

Scripts:
  ✓ create_scratchpad.py (identical)
  ✓ update_doc_timestamps.py (identical)
  ⚠ remind_close_session.py (modified - 5 lines differ)
  ✗ remind_scratchpad_before_compact.py (missing)
  ✓ validate_setup.py (identical)

Configuration:
  ⚠ .claude/settings.local.json (missing PreCompact hook)
```

## Step 2: Check templates

Compare the project's `kit_tools/` directory against the plugin's templates:

### 2a: Inventory templates

| Status | Meaning |
|--------|---------|
| **Identical** | Project template matches plugin exactly |
| **Customized** | Project template differs (user has modified) |
| **Missing** | Template exists in plugin but not in project |
| **Extra** | File exists in project but not in plugin (user-created) |

### 2b: Report template status

```
Template Status Report:

Identical (no action needed):
  - arch/CODE_ARCH.md
  - docs/LOCAL_DEV.md

Customized (review before updating):
  - SYNOPSIS.md (12 lines differ)
  - arch/SECURITY.md (8 lines differ)

Missing (can be added):
  - arch/patterns/CACHING.md (new in plugin v1.1)

Extra (project-specific, will be preserved):
  - docs/feature_guides/AUTH_FLOW.md
```

## Step 3: Check subagent components

Check the status of subagent-related components in the project:

### 3a: Hook script

Check `detect_phase_completion.py` in the project's `hooks/` directory:

| Status | Meaning |
|--------|---------|
| **Identical** | Project script matches plugin exactly |
| **Modified** | Project script differs (user has customized) |
| **Missing** | Script exists in plugin but not in project |

### 3b: Audit findings template

Check if `kit_tools/AUDIT_FINDINGS.md` exists in the project:
- If present, note its status (template or populated with findings)
- If missing, note it can be added

### 3c: Skill integration status

Verify that the validate-phase skill integrations are present in the project's session lifecycle skills:
- `checkpoint/SKILL.md` — Should include "Run validator" step
- `close-session/SKILL.md` — Should include "Run validator" step
- `start-session/SKILL.md` — Should include "Review open audit findings" step

Report integration status for each.

## Step 4: Present update options

After showing all status reports, present options:

### Hook options:
1. **Update all hooks** - Replace all hook scripts with plugin versions
2. **Update specific hook** - Choose which scripts to update
3. **Add missing hooks** - Only add hooks that don't exist
4. **Update hook config** - Sync `.claude/settings.local.json` with plugin

### Template options:
5. **Preview changes** for a specific template (show diff)
6. **Update specific template** - Replace with plugin version
7. **Add missing templates** - Copy new templates only
8. **Update all templates** - Replace all (WARNING: loses customizations)

### Subagent options:
9. **Add/update phase completion hook** - Install or update `detect_phase_completion.py`
10. **Add audit findings template** - Copy `AUDIT_FINDINGS.md` template to project
11. **Update skill integrations** - Sync validator steps in checkpoint, close-session, start-session

### Global options:
12. **Update everything** - Full sync of all components (confirm first)
13. **Skip** - Make no changes

## Step 5: Execute updates

Based on user selection:

### For hooks:
- Copy selected Python scripts from plugin to project `hooks/`
- Update `.claude/settings.local.json` if hook config selected
- Preserve `hooks.json` in project (it's a reference copy)

### For templates:
- Replace selected templates with plugin versions
- For customized files, warn that customizations will be lost

## Step 6: Report changes

After making changes:

```
Update Complete:

Hooks updated:
  - remind_scratchpad_before_compact.py (added)
  - .claude/settings.local.json (PreCompact hook added)

Templates updated:
  - arch/SECURITY.md (replaced)

Templates added:
  - arch/patterns/CACHING.md

No changes:
  - remind_close_session.py (kept modified version)
  - SYNOPSIS.md (kept customized version)
```

Remind user:
- Review any replaced files to re-apply customizations if needed
- Run `/kit-tools:seed-project` if new templates were added
- Test hooks by starting a new session

## Handling modified/customized files

When updating a file that has local modifications:

1. Show the diff first
2. Warn that customizations will be lost
3. Offer options:
   - Copy customizations somewhere first
   - Manually merge the changes
   - Skip this file
   - Replace anyway

## Arguments

If `$ARGUMENTS` contains a component or filename, jump directly to that:

Examples:
- `/kit-tools:update-kit-tools` - Full inventory of all components
- `/kit-tools:update-kit-tools hooks` - Check hooks only
- `/kit-tools:update-kit-tools templates` - Check templates only
- `/kit-tools:update-kit-tools SYNOPSIS.md` - Show diff for specific template
- `/kit-tools:update-kit-tools remind_close_session.py` - Show diff for specific hook

## Quick mode

If `$ARGUMENTS` contains `--quick`:

- Skip identical files in the report
- Only show files that need attention (missing, modified, outdated)

Example: `/kit-tools:update-kit-tools --quick`
