---
name: complete-implementation
description: Mark a feature spec as completed and archive it
---

# Complete Implementation

Mark a feature spec as completed and move it to the archive. Run when all user stories are implemented and verified.

> **Note:** In autonomous/guarded mode, the orchestrator handles completion directly via the `completion_strategy` config option (`"pr"`, `"merge"`, or `"none"`). For worktree-isolated executions, `"merge"` is performed **server-side** (push → `gh pr merge`) — the orchestrator never checks out main in its worktree. This skill is for manual/supervised use, for **tearing down the execution worktree** after a finished run (Step 8), or as a fallback when the orchestrator's completion fails.

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

First, determine how this execution ran. Resolve the registry record (`<key>` = epic name, or feature name for a standalone fallback):

```bash
python3 "$CLAUDE_PLUGIN_ROOT/scripts/orchestrator/registry.py" get "<key>"
```

- **A record exists →** this was a worktree-isolated (autonomous/guarded) execution. Its `.execution-*` state files live *inside the worktree*, so removing the worktree (Step 8) cleans them up — don't hunt for them in the main checkout.
  - **If you are running INSIDE the execution worktree** (check: `registry.py is-worktree` exits 0) — e.g. the orchestrator auto-invoked this skill during a single-spec run — do **NOT** remove the worktree (you can't delete your own cwd). Just mark the record completed and stop here; teardown happens later from the main checkout:
    ```bash
    python3 "$CLAUDE_PLUGIN_ROOT/scripts/orchestrator/registry.py" set-status "<key>" completed
    ```
- **No record (legacy / in-dir execution) →** delete `.execution-state.json`, `.execution-config.json`, `.pause_execution` from `kit_tools/specs/` as before.

**Mid-epic feature spec:** Skip cleanup and teardown (later specs still need the branch/worktree).

---

## Step 8: Feature branch & worktree teardown

Resolve the branch decision first, then tear down the worktree (teardown is safe — git refuses to remove a dirty tree or delete an unmerged branch).

**Branch options:**
- **Standalone:** Offer: create PR, merge to main, or leave as-is.
- **Final epic:** Offer an epic PR referencing all completed feature specs and checkpoint tags.
- **Mid-epic:** Skip branch handling and teardown.

> For worktree executions, run `gh`/`git push` from the worktree path (resolve it from the record's `worktree` field), **not** the main checkout. Never `git checkout main` to merge a worktree branch — merge via `gh pr merge` or let the user merge from their own checkout.

**Worktree teardown** (only when running from the **main checkout**, and only for standalone / final-epic completion — never mid-epic, never from inside the worktree):

- If the user chose **PR** or **merge**, tear down now:
  ```bash
  python3 "$CLAUDE_PLUGIN_ROOT/scripts/orchestrator/registry.py" teardown "<key>"
  ```
  - **Exit 0** — worktree removed, the (merged) branch deleted, registry entry cleared. (An unmerged branch behind an open PR is kept and flagged — that's expected; the PR lives on the remote.)
  - **Exit 3** — **kept and flagged.** The worktree had uncommitted/untracked work, or the branch was unmerged. Report the `messages` from the JSON output to the user verbatim. Do **not** force. Let them save/commit/merge, then re-run teardown (or, only on explicit say-so, `teardown --force` / `git branch -D`).
- If the user chose **leave as-is**, do not tear down. Mark the record completed (`set-status "<key>" completed`) and tell them the worktree path so they can inspect it; `/kit-tools:close-session` will offer to reap it later.

---

## Step 9: Offer Version Bump

If `kit_tools/BUMP_VERSION.md` exists, ask the user:

> "Would you like to bump the project version for this release?"

If yes, invoke `/kit-tools:bump-version`. The bump-version skill handles the full flow (reading the runbook, determining the new version, updating files, committing).

If no, or if `BUMP_VERSION.md` doesn't exist, skip this step.

---

## Step 10: Summary

Report: feature spec archived, completion stats, branch status, files updated, artifacts cleaned, and — for worktree executions — teardown outcome (worktree removed / kept-and-flagged with the reason).

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
