---
description: Update documentation before ending a development session
---

# Close Development Session

Great work today! Before we close out, let's make sure documentation stays in sync.

## Step 0: Process scratchpad

- Read `kit_tools/SESSION_SCRATCH.md`
- **Identify which feature/TODO was being worked on** from the "Active Feature" section
- Use these notes to inform the documentation updates below
- If the scratchpad is empty, that's okay — proceed with what you remember from this session

## Step 1: Update the correct TODO file(s)

Based on the scratchpad's "Active Feature" section and the work done:

1. **Identify the relevant TODO file(s):**
   - `kit_tools/roadmap/MVP_TODO.md` — For high-level MVP tasks
   - `kit_tools/roadmap/FEATURE_TODO_[name].md` — For feature-specific tasks
   - `kit_tools/roadmap/BACKLOG.md` — For future work items

2. **Update the identified file(s):**
   - Mark completed items with [x]
   - Add any new items discovered
   - Update the "Session Tracking" table in FEATURE_TODO files
   - If a TODO file is 100% complete, update its Status to "Complete"

3. **If work touched multiple features**, update each relevant TODO file

## Step 2: Documentation sweep

Using the checklist in `kit_tools/AGENT_README.md` and the scratchpad notes, review and update any files affected by today's work:

- [ ] `kit_tools/SYNOPSIS.md` — Did project status/scope change?
- [ ] `kit_tools/arch/CODE_ARCH.md` — Did we add modules, services, or change structure?
- [ ] `kit_tools/arch/INFRA_ARCH.md` — Did we add/change cloud resources?
- [ ] `kit_tools/arch/DATA_MODEL.md` — Did we change the schema?
- [ ] `kit_tools/arch/DECISIONS.md` — Did we make a "why" decision worth recording?
- [ ] `kit_tools/docs/API_GUIDE.md` — Did we add/change API endpoints?
- [ ] `kit_tools/docs/ENV_REFERENCE.md` — Did we add environment variables?
- [ ] `kit_tools/docs/feature_guides/` — Did we add/significantly change a feature?
- [ ] `kit_tools/docs/GOTCHAS.md` — Did we discover any landmines?
- [ ] `kit_tools/testing/TESTING_GUIDE.md` — Did testing approach change?

## Step 3: Update Session Log

Add an entry to `kit_tools/SESSION_LOG.md` with:

- Today's date
- **Which feature(s)/TODO(s) were worked on**
- What was accomplished (use scratchpad notes as reference)
- Which docs were updated
- Open items for next session

## Step 4: Delete scratchpad

- Delete `kit_tools/SESSION_SCRATCH.md` entirely
- This signals the session closed cleanly

## Step 5: Summary

Provide a brief summary of:

- What was accomplished today
- **Which TODO file(s) were updated**
- What documentation was updated
- Any open items or recommended next steps
