---
name: complete-implementation
description: Mark a feature spec as completed and archive it
---

# Complete Implementation

Mark a feature spec as completed and move it to the archive. Run when all user stories are implemented and verified.

> **Note:** In autonomous/guarded mode, the orchestrator handles completion directly via the `completion_strategy` config option (`"pr"`, `"merge"`, or `"none"`). This skill is for manual/supervised use or as a fallback when the orchestrator's completion fails.

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

## Step 3: Capture learnings

Ask the user: "Any learnings from this feature worth capturing? Things like patterns that worked well, gotchas discovered during implementation, or spec-writing improvements for next time."

If the user has learnings:
- **Gotchas or landmines** → Append to `kit_tools/docs/GOTCHAS.md`
- **Code patterns or conventions** → Append to `kit_tools/docs/CONVENTIONS.md`
- **Spec-writing notes** (e.g., "integration stories need error-handling criteria") → Add to the feature spec's Implementation Notes section before archiving

If the user has nothing, move on — don't force it.

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

### Next Steps

Based on the context:

**If this was the final spec in an epic:**
> "Epic complete! To start your next piece of work, run `/kit-tools:plan-epic`."
> If milestones exist, add: "Check `kit_tools/roadmap/MILESTONES.md` for what's planned next."

**If more specs remain in the epic:**
> "Next spec in the epic is ready. Run `/kit-tools:execute-epic` to continue, or `/kit-tools:validate-epic` if specs have been revised."

**If standalone feature:**
> "Feature complete. Run `/kit-tools:plan-epic` to plan your next feature."

---

## Related Skills

| Skill | When to use |
|-------|-------------|
| `/kit-tools:validate-implementation` | Run before completing |
| `/kit-tools:plan-epic` | Plan the next feature or epic |
| `/kit-tools:execute-epic` | Continue executing remaining specs in an epic |
| `/kit-tools:validate-epic` | Re-validate if specs were revised during this feature |
