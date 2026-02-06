---
name: complete-feature
description: Mark a PRD as completed and archive it
---

# Complete Feature

Mark a PRD as completed and move it to the archive. This skill should be run when all user stories in a PRD have been implemented and verified.

## Dependencies

This skill requires:

| File | Required | Purpose |
|------|----------|---------|
| `kit_tools/prd/prd-*.md` | Yes | PRD to complete |
| `kit_tools/prd/archive/` | Yes | Archive destination |
| `kit_tools/roadmap/MVP_TODO.md` | Optional | Update milestone if linked |
| `kit_tools/roadmap/BACKLOG.md` | Optional | Remove from backlog |

**Modifies:**
- `kit_tools/prd/prd-*.md` — Updates status to `completed`
- Moves PRD to `kit_tools/prd/archive/`

**Optionally modifies:**
- `kit_tools/roadmap/MVP_TODO.md` — Marks milestone item complete
- `kit_tools/roadmap/BACKLOG.md` — Removes or updates feature reference

## Arguments

| Argument | Description |
|----------|-------------|
| `[prd-name]` | Optional: specific PRD to complete (e.g., `prd-auth`) |

If no argument provided, will list PRDs and ask which to complete.

## Step 1: Select PRD to complete

### If argument provided:
Look for `kit_tools/prd/prd-[argument].md` or `kit_tools/prd/[argument].md`

### If no argument:
List all active PRDs and ask:

```
Active PRDs:

1. prd-auth.md (5/5 stories complete)
2. prd-payments.md (3/4 stories complete)

Which PRD would you like to mark as completed?
```

## Step 2: Verify completion

Before archiving, verify the PRD is actually complete:

### Check acceptance criteria
- Count total acceptance criteria checkboxes
- Count completed checkboxes (`[x]`)
- Calculate completion percentage

### If not 100% complete:

```
Warning: prd-payments.md is only 75% complete (3/4 stories)

Incomplete stories:
- US-004: Add payment history page (0/4 criteria done)

Are you sure you want to mark this as completed?
  1. Yes, mark complete anyway
  2. No, let me finish the remaining work
```

### If 100% complete:
Proceed without warning.

## Step 3: Capture final Implementation Notes

Ask the user:

> "Any final learnings or notes to add to the Implementation Notes before archiving?"

If yes, append to the `## Implementation Notes` section.

## Step 4: Update PRD frontmatter

Update the PRD's YAML frontmatter:

```yaml
---
feature: auth
status: completed      # Changed from 'active'
created: 2025-01-15
updated: 2025-02-01    # Today's date
completed: 2025-02-01  # Add completion date
---
```

## Step 5: Archive the PRD

Move the PRD to the archive:

```
kit_tools/prd/prd-auth.md → kit_tools/prd/archive/prd-auth.md
```

### If archive directory doesn't exist:
Create `kit_tools/prd/archive/` first.

### If file already exists in archive:
This shouldn't happen, but if it does:
- Rename existing to `prd-auth-[date].md`
- Then move current PRD to archive

## Step 6: Update tracking files

### MVP_TODO.md
If the feature was linked in MVP_TODO.md:
- Find the line referencing this PRD
- Mark it complete: `- [x] Feature Name ([PRD](../prd/archive/prd-auth.md))`
- Update the link to point to archive location

### BACKLOG.md
If the feature was listed in BACKLOG.md:
- Remove it from "Planned Features" section
- Optionally add to a "Completed Features" section (if one exists)

## Step 7: Summary

```
Feature completed and archived!

PRD: prd-auth.md
- Status: completed
- Archived to: kit_tools/prd/archive/prd-auth.md
- Completion: 5/5 stories (100%)

Updated:
- kit_tools/roadmap/MVP_TODO.md (marked feature complete)
- kit_tools/roadmap/BACKLOG.md (removed from planned)

The feature is now archived. Great work!
```

## Archival Best Practices

### Why archive instead of delete?
- Preserves Implementation Notes for future reference
- Maintains history of completed features
- Useful for similar future features
- Audit trail of what was built

### Archive organization
Over time, the archive may grow. Consider:
- Organizing by date: `archive/2025-01/prd-auth.md`
- Organizing by category: `archive/auth/prd-login.md`

For now, flat structure is fine. Reorganize when needed.

## Related Skills

| Skill | When to use |
|-------|-------------|
| `/kit-tools:execute-feature` | To execute PRD stories autonomously or with supervision |
| `/kit-tools:plan-feature` | To start a new feature |
| `/kit-tools:start-session` | To see remaining active PRDs |
