---
name: start-session
description: Orient yourself at the start of a development session
---

# Start Development Session

Hey Claude! Let's get oriented before we start today's session.

## Dependencies

This skill requires the following project files:

| File | Required | Purpose |
|------|----------|---------|
| `kit_tools/AGENT_README.md` | Yes | Navigation guide and patterns |
| `kit_tools/SYNOPSIS.md` | Yes | Project status overview |
| `kit_tools/SESSION_LOG.md` | Yes | Session history |
| `kit_tools/specs/*.md` | Yes | Feature specs for active features |
| `kit_tools/roadmap/MILESTONES.md` | Yes | Milestone tracking |
| `kit_tools/arch/CODE_ARCH.md` | Recommended | Code architecture reference |
| `kit_tools/arch/INFRA_ARCH.md` | Optional | Infrastructure reference |
| `kit_tools/docs/GOTCHAS.md` | Recommended | Known issues and landmines |
| `kit_tools/AUDIT_FINDINGS.md` | Optional | Open code quality findings |

**Creates:**
- `kit_tools/SESSION_SCRATCH.md` — Session scratchpad for notes

**Related hooks:**
- `create_scratchpad.py` (SessionStart) — Auto-creates scratchpad on session start

## Step 0: Check for orphaned scratchpad

- Check if `kit_tools/SESSION_SCRATCH.md` exists
- If it exists and has content, the previous session didn't close cleanly:
  1. Read the scratchpad notes
  2. Process them into `kit_tools/SESSION_LOG.md` (add an entry noting this was recovered from an orphaned scratchpad)
  3. Update any other relevant docs based on the notes
  4. Delete the scratchpad file
  5. Let the user know what was recovered before continuing

## Step 1: Git health check

Run the following git commands and report a concise summary:

1. **Branch info:** `git branch --show-current` — report the current branch name.
2. **Uncommitted changes:** `git status --short` — report modified, staged, and untracked file counts. If there are changes, list them briefly.
3. **Stash:** `git stash list` — note if there are stashed changes the user may have forgotten about.
4. **Remote sync:** `git fetch --quiet` then `git status --short --branch` — check if the branch is behind, ahead, or diverged from its upstream.
5. **Recent commits:** `git log --oneline -5` — show the last 5 commits for context on where things left off.

### Reporting

Present the findings as a compact status block, for example:

```
Git Status:
  Branch:      feature/auth (3 ahead, 1 behind origin/feature/auth)
  Uncommitted: 2 modified, 1 untracked
  Stash:       1 entry
  Last commit: a1b2c3d "Add login endpoint" (2 hours ago)
```

### If issues are found

Flag any of these to the user and let them decide how to proceed:

- **Behind remote** — suggest `git pull` or `git pull --rebase` before starting work
- **Uncommitted changes** — note them and ask if the user wants to commit, stash, or continue as-is
- **Diverged from upstream** — warn that a merge/rebase will be needed
- **Detached HEAD** — warn and suggest checking out a branch
- **Stashed changes** — mention them in case the user forgot about prior work

Do not take any git actions automatically — just report and let the user choose. If everything is clean, say so and move on.

## Step 2: Create fresh scratchpad

Create `kit_tools/SESSION_SCRATCH.md` with this content:

```markdown
# SESSION_SCRATCH.md

> Auto-generated. Append notes as you work. Processed on session close.

## Active Feature

**Working on:** [Feature name or "General" if not feature-specific]
**Feature Spec:** [e.g., `feature-auth.md` or "N/A" if not feature-specific]

---

## Notes

```

This file will be used to capture work throughout the session.

## Step 3: Read the navigation guide

Read `kit_tools/AGENT_README.md` — this tells you how to navigate this repo and what patterns to follow.

## Step 4: Read project status

Read `kit_tools/SYNOPSIS.md` to understand the current project state.

## Step 5: Check active work

### Feature Specs

Check `kit_tools/specs/` for active features:

- Look for `feature-*.md` files (excluding `archive/` subdirectory)
- Read the YAML frontmatter to check `status: active`
- For each active feature spec, note:
  - Feature name
  - How many user stories are complete vs total (count `- [x]` vs `- [ ]` in acceptance criteria)

**If no feature specs exist** (no `feature-*.md` or `epic-*.md` files in `kit_tools/specs/`):
- Note this in the summary: "No active feature specs found."
- Suggest: "Run `/kit-tools:plan-epic` to plan your first feature, or `/kit-tools:create-vision` to define your product vision first."

### Milestone tracking

Review `kit_tools/roadmap/`:

- `MILESTONES.md` — High-level milestone tracking
- `BACKLOG.md` — Future work items and planned features

List any active feature specs and their progress so we know what's being worked on.

## Step 6: Architecture refresh

Skim `kit_tools/arch/CODE_ARCH.md` and `kit_tools/arch/INFRA_ARCH.md` to refresh on the structure.

## Step 7: Check gotchas

Read `kit_tools/docs/GOTCHAS.md` for any landmines relevant to today's work.

## Step 8: Review open audit findings

- Check if `kit_tools/AUDIT_FINDINGS.md` exists
- If it exists, read the **Active Findings** section
- Note any `critical` severity findings — these should be mentioned in the summary
- Count open findings by severity (critical / warning / info)
- If no findings file exists or no active findings, skip this step

## As you review, flag anything that looks like:

- Security concerns
- Code that violates patterns documented in AGENT_README.md
- Documentation that looks stale or inconsistent with the code

## Summary

Once oriented, provide a quick summary of:

- **Git status** — branch, sync state, uncommitted changes (with any warnings/suggestions)
- Any recovered notes from orphaned scratchpad (if applicable)
- Current project status (from SYNOPSIS.md)
- **Active feature specs and their progress** (list each with story completion count, e.g., "feature-auth.md: 3/5 stories complete")
- Milestone progress from MILESTONES.md
- Open audit findings count (N critical, N warning, N info) — if any exist
- Any concerns or inconsistencies noticed

**Ask the user:** Which feature or area will we be working on today? (This helps track work to the correct feature spec)

Then we're ready to get started!
