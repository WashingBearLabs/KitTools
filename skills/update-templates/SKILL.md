---
description: Update project templates from the latest plugin versions
---

# Update Templates

Compare and selectively update the project's kit_tools templates against the latest versions from this plugin.

## Step 1: Inventory

List all templates in both locations:

- **Plugin templates**: The canonical templates bundled with this plugin
- **Project templates**: The templates in `kit_tools/` (may be customized)

## Step 2: Compare versions

For each template, determine its status:

| Status | Meaning |
|--------|---------|
| **Identical** | Project template matches plugin template exactly |
| **Customized** | Project template differs (user has modified it) |
| **Missing** | Template exists in plugin but not in project |
| **Extra** | File exists in project but not in plugin (user-created) |

## Step 3: Show diff summary

Present a summary like:

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

## Step 4: Ask for action

Present options to the user:

1. **Preview changes** for a specific file (show diff)
2. **Update specific file** (overwrite with plugin version)
3. **Add missing templates** (copy new templates only)
4. **Update all** (replace all templates - WARNING: loses customizations)
5. **Skip** (make no changes)

## Step 5: Execute updates

Based on user selection:

- For **Update specific file**: Replace the project file with plugin version
- For **Add missing**: Copy only templates that don't exist in project
- For **Update all**: Replace all templates (confirm this destructive action first)

## Step 6: Report

After making changes:

- List files that were updated
- List files that were added
- Remind user to review changes and re-apply any customizations if needed
- Suggest running `/kit-tools:seed-project` if new templates were added

## Handling customized files

When updating a customized file:

1. Show the diff first
2. Warn that customizations will be lost
3. Suggest the user could:
   - Copy their customizations somewhere first
   - Manually merge the changes
   - Skip this file

## Arguments

If `$ARGUMENTS` contains a filename, jump directly to showing the diff for that file.

Examples:
- `/kit-tools:update-templates` - Show full inventory
- `/kit-tools:update-templates SYNOPSIS.md` - Show diff for SYNOPSIS.md
