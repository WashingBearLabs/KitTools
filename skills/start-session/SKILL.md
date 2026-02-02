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
| `kit_tools/prd/*.md` | Yes | PRDs for active features |
| `kit_tools/roadmap/MVP_TODO.md` | Yes | Milestone tracking |
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

## Step 1: Create fresh scratchpad

Create `kit_tools/SESSION_SCRATCH.md` with this content:

```markdown
# SESSION_SCRATCH.md

> Auto-generated. Append notes as you work. Processed on session close.

## Active Feature

**Working on:** [Feature name or "General" if not feature-specific]
**PRD:** [e.g., `prd-auth.md` or "N/A" if not feature-specific]

---

## Notes

```

This file will be used to capture work throughout the session.

## Step 2: Read the navigation guide

Read `kit_tools/AGENT_README.md` — this tells you how to navigate this repo and what patterns to follow.

## Step 3: Read project status

Read `kit_tools/SYNOPSIS.md` to understand the current project state.

## Step 4: Check active work

### PRDs (Product Requirements Documents)

Check `kit_tools/prd/` for active features:

- Look for `prd-*.md` files (excluding `archive/` subdirectory)
- Read the YAML frontmatter to check `status: active`
- For each active PRD, note:
  - Feature name
  - How many user stories are complete vs total (count `- [x]` vs `- [ ]` in acceptance criteria)

### Milestone tracking

Review `kit_tools/roadmap/`:

- `MVP_TODO.md` — High-level milestone tasks
- `BACKLOG.md` — Future work items and planned features

List any active PRDs and their progress so we know what's being worked on.

## Step 5: Architecture refresh

Skim `kit_tools/arch/CODE_ARCH.md` and `kit_tools/arch/INFRA_ARCH.md` to refresh on the structure.

## Step 6: Check gotchas

Read `kit_tools/docs/GOTCHAS.md` for any landmines relevant to today's work.

## Step 7: Review open audit findings

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

- Any recovered notes from orphaned scratchpad (if applicable)
- Current project status (from SYNOPSIS.md)
- **Active PRDs and their progress** (list each with story completion count, e.g., "prd-auth.md: 3/5 stories complete")
- Milestone progress from MVP_TODO.md
- Open audit findings count (N critical, N warning, N info) — if any exist
- Any concerns or inconsistencies noticed

**Ask the user:** Which feature or area will we be working on today? (This helps track work to the correct PRD)

Then we're ready to get started!
