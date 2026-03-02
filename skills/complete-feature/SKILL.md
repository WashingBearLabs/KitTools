---
name: complete-feature
description: Mark a feature spec as completed and archive it
---

# Complete Feature

Mark a feature spec as completed and move it to the archive. Run when all user stories are implemented and verified.

Read `REFERENCE.md` in this skill directory for epic handling details, PR formats, and edge cases.

## Dependencies

| File | Required | Purpose |
|------|----------|---------|
| `kit_tools/specs/feature-*.md` | Yes | Feature spec to complete |
| `kit_tools/specs/archive/` | Yes | Archive destination |
| `kit_tools/roadmap/MILESTONES.md` | Optional | Update milestone |
| `kit_tools/roadmap/BACKLOG.md` | Optional | Remove from backlog |

## Arguments

| Argument | Description |
|----------|-------------|
| `[feature-name]` | Optional: specific feature spec to complete |

---

## Step 1: Select Feature Spec

If argument provided, find matching feature spec. Otherwise list active feature specs with completion counts.

### Epic Detection

If feature spec has `epic` field:
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

## Step 5: Archive the feature spec

Move to `kit_tools/specs/archive/`. Create directory if needed.

---

## Step 6: Update tracking files

- **MILESTONES.md:** Mark feature complete, update link to archive
- **BACKLOG.md:** Remove from planned, optionally add to completed
- **Epic file:** If feature spec belongs to an epic (`epic-*.md`), update the decomposition table to mark this feature spec as completed

---

## Step 7: Clean up execution artifacts

**Standalone or final epic feature spec:** Delete `.execution-state.json`, `.execution-config.json`, `.pause_execution`.

**Mid-epic feature spec:** Skip cleanup.

---

## Step 8: Feature branch

- **Standalone:** Offer: create PR, merge to main, or leave
- **Final epic:** Offer epic PR referencing all completed feature specs and checkpoint tags
- **Mid-epic:** Skip branch handling

---

## Step 9: Summary

Report: feature spec archived, completion stats, branch status, files updated, artifacts cleaned.

---

## Related Skills

| Skill | When to use |
|-------|-------------|
| `/kit-tools:validate-feature` | Run before completing |
| `/kit-tools:execute-feature` | To execute feature spec stories |
| `/kit-tools:plan-feature` | To start a new feature |
