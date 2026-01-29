---
name: checkpoint
description: Capture work mid-session before context refreshes
---

# Checkpoint Session

Let's checkpoint the current session to make sure nothing gets lost.

## Dependencies

This skill requires the following project files:

| File | Required | Purpose |
|------|----------|---------|
| `kit_tools/SESSION_SCRATCH.md` | Yes | Notes to process |
| `kit_tools/SESSION_LOG.md` | Yes | Session history to update |
| `kit_tools/roadmap/*.md` | Yes | TODO files to update |

**Modifies:**
- `kit_tools/SESSION_SCRATCH.md` — Clears notes section (preserves Active Feature)

**Uses agents:**
- `template-validator.md` — Quick validation on updated docs

**Optionally invokes:**
- `/kit-tools:validate-phase` — If code changes were made since last checkpoint

**Related hooks:**
- `remind_scratchpad_before_compact.py` (PreCompact) — Adds marker before context compaction

## Step 1: Review the scratchpad

- Read `kit_tools/SESSION_SCRATCH.md`
- **Note the "Active Feature" section** — this tells us which TODO file to update
- If it doesn't exist or is empty, ask what has been accomplished so far this session

## Step 2: Process notes into documentation

Using the notes in the scratchpad (or what was discussed), update relevant docs:

- [ ] `kit_tools/SESSION_LOG.md` — Add/update today's entry with work completed so far
- [ ] **The TODO file identified in "Active Feature"** — Mark completed items, add discovered items
- [ ] Other docs as needed (CODE_ARCH.md, GOTCHAS.md, etc.)

## Step 2.5: Quick validation

If any docs beyond SESSION_LOG were updated, run a quick `template-validator` check:

- Verify no placeholder text remains
- Check that file paths referenced are accurate
- Ensure "Last Updated" was set to today

Skip this step if only SESSION_LOG and TODO files were updated.

## Step 3: Clear the scratchpad (preserve Active Feature)

- Clear the **Notes** section of `kit_tools/SESSION_SCRATCH.md` but keep the file (session is still active)
- **Preserve the "Active Feature" section** so we remember what we're working on
- Reset to this structure:

```markdown
# SESSION_SCRATCH.md

> Auto-generated. Append notes as you work. Processed on session close.

## Active Feature

**Working on:** [Keep the current value]
**TODO File:** [Keep the current value]

---

## Notes

```

## Step 4: Run validator (if applicable)

- If code changes were made since the last checkpoint (check `git diff` for non-documentation changes), run `/kit-tools:validate-phase`
- **Skip this step** if the checkpoint is documentation-only (no code files changed)
- Findings are advisory — they do not block the checkpoint from completing
- Note any critical findings for the summary

## Step 5: Confirm

Provide a brief summary of:

- What was captured from the scratchpad
- **Which TODO file was updated**
- Which other docs were updated
- Doc validation status (if run): passed/warnings
- Audit findings count (if code validator was run): N critical, N warning, N info
- Confirmation that we're ready to continue

Don't close the session — we're just checkpointing progress.
