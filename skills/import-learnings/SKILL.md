---
name: import-learnings
description: Import ralph progress.txt learnings back into a KitTools PRD
---

# Import Ralph Learnings

After ralph completes a feature (or makes significant progress), import the learnings from `progress.txt` back into your KitTools PRD's Implementation Notes section.

## Dependencies

This skill requires:

| File | Required | Purpose |
|------|----------|---------|
| `progress.txt` | Yes | Ralph's learnings log (at project root) |
| `prd.json` | Yes | To identify which PRD to update |
| `kit_tools/prd/prd-*.md` | Yes | Target PRD for learnings |

**Modifies:**
- `kit_tools/prd/prd-*.md` — Adds learnings to Implementation Notes section

**Related:**
- `/kit-tools:export-ralph` — Exports PRD to ralph format (run before ralph)
- `/kit-tools:complete-feature` — Archives PRD when all stories complete

## When to Use

Run this skill:

1. **After ralph completes** all stories (`<promise>COMPLETE</promise>`)
2. **After a ralph session** when you want to capture partial progress
3. **Before archiving** a PRD that was implemented via ralph

## Step 1: Read ralph state

### Read prd.json

```json
{
  "branchName": "ralph/auth",
  "userStories": [...]
}
```

Extract:
- Feature name from `branchName` (strip `ralph/` prefix)
- Story completion status

### Read progress.txt

Look for:
- **Codebase Patterns section** — General learnings to preserve
- **Per-story entries** — Specific learnings from each iteration
- **Gotchas and warnings** — Things that tripped up the agent

## Step 2: Find the matching PRD

Based on the feature name from `prd.json`:

1. Look for `kit_tools/prd/prd-[feature-name].md`
2. If not found, list available PRDs and ask user which one corresponds

## Step 3: Extract learnings

From `progress.txt`, extract valuable learnings:

### Codebase Patterns
These are general, reusable patterns. Examples:
- "Use `sql<number>` template for aggregations"
- "Always use `IF NOT EXISTS` for migrations"
- "Export types from actions.ts for UI components"

### Per-Story Learnings
From each story entry, look for:
- "Learnings for future iterations"
- Gotchas encountered
- Patterns discovered
- Files that needed coordination

### Filter out noise
Don't import:
- Routine "what was implemented" logs
- File lists without context
- Timestamps without meaningful content

## Step 4: Update PRD Implementation Notes

Add the extracted learnings to the PRD's `## Implementation Notes` section:

```markdown
## Implementation Notes

<!-- Imported from ralph progress.txt on YYYY-MM-DD -->

### Codebase Patterns Discovered
- Pattern 1 from progress.txt
- Pattern 2 from progress.txt

### Gotchas Encountered
- Gotcha 1: description
- Gotcha 2: description

### Implementation Details
- Story-specific learning 1
- Story-specific learning 2
```

### Formatting guidelines:
- Group related learnings together
- Use clear, actionable language
- Remove ralph-specific jargon (make it readable for humans)
- Add date of import as a comment

## Step 5: Sync story status

If prd.json shows stories as complete that aren't marked in the PRD:

1. Update acceptance criteria checkboxes to match prd.json
2. Mark `- [x]` for all criteria in passing stories

This keeps the PRD in sync with what ralph accomplished.

## Step 6: Update PRD frontmatter

Update the `updated:` date in the PRD's YAML frontmatter.

If all stories are now complete, suggest running `/kit-tools:complete-feature`.

## Step 7: Optionally update GOTCHAS.md

If any learnings are **project-wide** (not feature-specific):

> "Some learnings look like they apply project-wide. Would you like to add them to kit_tools/docs/GOTCHAS.md?"

If yes, append to GOTCHAS.md under an appropriate section.

## Step 8: Summary

Report:

```
Imported learnings from ralph progress.txt

PRD updated: kit_tools/prd/prd-auth.md
- Added X codebase patterns to Implementation Notes
- Added Y gotchas to Implementation Notes
- Updated Z story statuses to match prd.json

Story status: 5/5 complete

Suggested next step:
  /kit-tools:complete-feature prd-auth
```

## Handling Edge Cases

### No progress.txt found
```
No progress.txt found at project root.
Ralph either hasn't run yet, or the file was deleted.

Nothing to import.
```

### progress.txt is minimal
If progress.txt only has the header and no meaningful content:
```
progress.txt exists but has no learnings to import.
Ralph may not have completed any iterations yet.
```

### PRD already has Implementation Notes
Append new learnings, don't overwrite:
```markdown
## Implementation Notes

### Manual Implementation (before ralph)
- Existing notes...

### Ralph Learnings (imported YYYY-MM-DD)
- New learnings from progress.txt...
```

## Related Skills

| Skill | When to use |
|-------|-------------|
| `/kit-tools:export-ralph` | Before running ralph |
| `/kit-tools:complete-feature` | After all stories complete |
| `/kit-tools:sync-project` | To verify docs are up to date |
