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

**Cleans up:**
- `kit_tools/prd/.execution-state.json` — Removes execution state sidecar
- `kit_tools/prd/.execution-config.json` — Removes orchestrator config
- `kit_tools/.pause_execution` — Removes pause file if present

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

## Step 1b: Epic Detection

After selecting a PRD, read its frontmatter. If the `epic` field is present and non-empty:

### Mid-epic PRD (not `epic_final`)

The orchestrator handles mid-epic completion automatically (tag + archive). If manually invoked:

```
Warning: This PRD is part of epic "[epic-name]" and is NOT the final PRD.
Mid-epic completion is normally handled by the orchestrator during epic execution.

Are you sure you want to complete it manually?
  1. Yes — tag checkpoint, archive PRD, skip PR/merge, skip artifact cleanup
  2. No — cancel
```

If yes:
- Tag checkpoint: `git tag [epic-name]/[feature-name]-complete`
- Archive PRD (update frontmatter, move to archive/)
- **Do NOT** create a PR or merge
- **Do NOT** clean up execution artifacts (other PRDs may still need them)

### Final PRD (`epic_final: true`)

- Tag checkpoint
- Archive PRD
- Offer PR for the entire `epic/[name]` branch (see Step 8 epic variant)
- Clean up all execution artifacts

### Standalone PRD (no `epic` field)

Existing behavior, no changes — proceed to Step 2.

---

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

## Step 7: Clean up execution artifacts

**Standalone PRD or final epic PRD (`epic_final: true`):**

Remove files created by execute-feature that are no longer needed:

- Delete `kit_tools/prd/.execution-state.json` if it exists
- Delete `kit_tools/prd/.execution-config.json` if it exists
- Delete `kit_tools/.pause_execution` if it exists

These are transient files used during execution and should not persist after completion.

**Mid-epic PRD (has `epic` but not `epic_final`):**

Do NOT clean up execution artifacts — they are still needed for subsequent PRDs in the epic.

## Step 8: Feature branch

Check if the feature was implemented on a branch:

```bash
git branch --show-current
```

### Standalone PRD (no `epic` field)

Read the PRD frontmatter `feature` field. If a `feature/[name]` branch exists:

- **Autonomous mode** (auto-invoked by validate-feature): Note the branch in the summary. The user should merge or create a PR after reviewing.
- **Supervised/manual mode**: Ask the user what to do:

```
Feature branch: feature/auth

What would you like to do with the branch?
  1. Create a PR (recommended)
  2. Merge to main now
  3. Leave it — I'll handle it myself
```

If the user chooses option 1, create a PR using `gh pr create` with a summary drawn from the PRD overview and stories completed.

If the user chooses option 2, merge with `git checkout main && git merge feature/[name]`.

### Epic PRD (`epic_final: true`)

For the final PRD in an epic, the PR should reference **all PRDs** in the epic. Scan `kit_tools/prd/archive/` for all PRDs with the same `epic` field, and `git tag -l` for checkpoint tags.

```
Epic branch: epic/arxiv

What would you like to do with the branch?
  1. Create a PR for the epic (recommended)
  2. Merge to main now
  3. Leave it — I'll handle it myself
```

If creating a PR, use this format:

```
PR title: feat([epic-name]): complete epic

PR body:
## Summary
- prd-[name-1]: [N stories]
- prd-[name-2]: [N stories]
- prd-[name-3]: [N stories]

## Checkpoints
- [epic-name]/[feature-1]-complete
- [epic-name]/[feature-2]-complete
- [epic-name]/[feature-3]-complete
```

### Mid-epic PRD (has `epic` but not `epic_final`)

Skip branch handling entirely — the branch is shared and still in use by subsequent PRDs.

## Step 9: Summary

```
Feature completed and archived!

PRD: prd-auth.md
- Status: completed
- Archived to: kit_tools/prd/archive/prd-auth.md
- Completion: 5/5 stories (100%)
- Branch: feature/auth [merged / PR created / user will handle]

Updated:
- kit_tools/roadmap/MVP_TODO.md (marked feature complete)
- kit_tools/roadmap/BACKLOG.md (removed from planned)

Cleaned up:
- .execution-state.json (removed)
- .execution-config.json (removed)

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
| `/kit-tools:validate-feature` | Run this before completing to validate the full branch |
| `/kit-tools:execute-feature` | To execute PRD stories autonomously or with supervision |
| `/kit-tools:plan-feature` | To start a new feature |
| `/kit-tools:start-session` | To see remaining active PRDs |
