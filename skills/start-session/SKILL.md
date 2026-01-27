---
name: start-session
description: Orient yourself at the start of a development session
---

# Start Development Session

Hey Claude! Let's get oriented before we start today's session.

## Step 0: Check for orphaned scratchpad

- Check if `kit_tools/SESSION_SCRATCH.md` exists
- If it exists and has content, the previous session didn't close cleanly:
  1. Read the scratchpad notes
  2. Process them into `kit_tools/SESSION_LOG.md` (add an entry noting this was recovered from an orphaned scratchpad)
  3. Update any other relevant docs based on the notes
  4. Delete the scratchpad file
  5. Let the user know what was recovered before continuing

## Step 1: Create fresh scratchpad

Create `kit_tools/SESSION_SCRATCH.md` with this content:

```markdown
# SESSION_SCRATCH.md

> Auto-generated. Append notes as you work. Processed on session close.

## Active Feature

**Working on:** [Feature name or "General" if not feature-specific]
**TODO File:** [e.g., `FEATURE_TODO_auth.md` or `MVP_TODO.md`]

---

## Notes

```

This file will be used to capture work throughout the session.

## Step 2: Read the navigation guide

Read `kit_tools/AGENT_README.md` — this tells you how to navigate this repo and what patterns to follow.

## Step 3: Read project status

Read `kit_tools/SYNOPSIS.md` to understand the current project state.

## Step 4: Check active work

Review all TODO files in `kit_tools/roadmap/`:

- `MVP_TODO.md` — High-level MVP tasks
- `BACKLOG.md` — Future work items
- `FEATURE_TODO_*.md` — Feature-specific task lists (there may be multiple)

List any active features (TODO files with in-progress items) so we know what's being worked on.

## Step 5: Architecture refresh

Skim `kit_tools/arch/CODE_ARCH.md` and `kit_tools/arch/INFRA_ARCH.md` to refresh on the structure.

## Step 6: Check gotchas

Read `kit_tools/docs/GOTCHAS.md` for any landmines relevant to today's work.

## As you review, flag anything that looks like:

- Security concerns
- Code that violates patterns documented in AGENT_README.md
- Documentation that looks stale or inconsistent with the code

## Summary

Once oriented, provide a quick summary of:

- Any recovered notes from orphaned scratchpad (if applicable)
- Current project status (from SYNOPSIS.md)
- **Active TODO files and their status** (list each with in-progress item count)
- Any concerns or inconsistencies noticed

**Ask the user:** Which feature or area will we be working on today? (This helps track work to the correct TODO file)

Then we're ready to get started!
