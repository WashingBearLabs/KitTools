---
name: complete-feature
description: Mark a PRD as completed and archive it
---

# Complete Feature

Mark a PRD as completed and move it to the archive. Run when all user stories are implemented and verified.

Read `REFERENCE.md` in this skill directory for epic handling details, PR formats, and edge cases.

## Dependencies

| File | Required | Purpose |
|------|----------|---------|
| `kit_tools/prd/prd-*.md` | Yes | PRD to complete |
| `kit_tools/prd/archive/` | Yes | Archive destination |
| `kit_tools/roadmap/MVP_TODO.md` | Optional | Update milestone |
| `kit_tools/roadmap/BACKLOG.md` | Optional | Remove from backlog |

## Arguments

| Argument | Description |
|----------|-------------|
| `[prd-name]` | Optional: specific PRD to complete |

---

## Step 1: Select PRD

If argument provided, find matching PRD. Otherwise list active PRDs with completion counts.

### Epic Detection

If PRD has `epic` field:
- **Mid-epic (not `epic_final`):** Warn that orchestrator normally handles this. Offer manual completion (tag + archive only, no PR/merge/cleanup).
- **Final epic (`epic_final: true`):** Full completion with epic PR.
- **Standalone:** Normal flow.

---

## Step 2: Verify completion

Count acceptance criteria checkboxes. If not 100% complete, warn and ask to confirm.

---

## Step 3: Capture final notes

Ask user for any final learnings to add to Implementation Notes.

---

## Step 4: Update frontmatter

Set `status: completed`, update date, add `completed: [today]`.

---

## Step 5: Archive the PRD

Move to `kit_tools/prd/archive/`. Create directory if needed.

---

## Step 6: Update tracking files

- **MVP_TODO.md:** Mark feature complete, update link to archive
- **BACKLOG.md:** Remove from planned, optionally add to completed

---

## Step 7: Clean up execution artifacts

**Standalone or final epic PRD:** Delete `.execution-state.json`, `.execution-config.json`, `.pause_execution`.

**Mid-epic PRD:** Skip cleanup.

---

## Step 8: Feature branch

- **Standalone:** Offer: create PR, merge to main, or leave
- **Final epic:** Offer epic PR referencing all completed PRDs and checkpoint tags
- **Mid-epic:** Skip branch handling

---

## Step 9: Summary

Report: PRD archived, completion stats, branch status, files updated, artifacts cleaned.

---

## Related Skills

| Skill | When to use |
|-------|-------------|
| `/kit-tools:validate-feature` | Run before completing |
| `/kit-tools:execute-feature` | To execute PRD stories |
| `/kit-tools:plan-feature` | To start a new feature |
