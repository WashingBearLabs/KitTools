---
description: Capture work mid-session before context refreshes
---

# Checkpoint Session

Let's checkpoint the current session to make sure nothing gets lost.

## Step 1: Review the scratchpad

- Read `kit_tools/SESSION_SCRATCH.md`
- **Note the "Active Feature" section** — this tells us which TODO file to update
- If it doesn't exist or is empty, ask what has been accomplished so far this session

## Step 2: Process notes into documentation

Using the notes in the scratchpad (or what was discussed), update relevant docs:

- [ ] `kit_tools/SESSION_LOG.md` — Add/update today's entry with work completed so far
- [ ] **The TODO file identified in "Active Feature"** — Mark completed items, add discovered items
- [ ] Other docs as needed (CODE_ARCH.md, GOTCHAS.md, etc.)

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

## Step 4: Confirm

Provide a brief summary of:

- What was captured from the scratchpad
- **Which TODO file was updated**
- Which other docs were updated
- Confirmation that we're ready to continue

Don't close the session — we're just checkpointing progress.
