---
name: close-session
description: Update documentation before ending a development session
---

# Close Development Session

Great job today Claude! Before we close out, let's make sure documentation stays in sync.

## Dependencies

This skill requires the following project files:

| File | Required | Purpose |
|------|----------|---------|
| `kit_tools/SESSION_SCRATCH.md` | Yes | Notes captured during session |
| `kit_tools/SESSION_LOG.md` | Yes | Session history to update |
| `kit_tools/prd/*.md` | Yes | PRDs to update with progress |
| `kit_tools/roadmap/MVP_TODO.md` | Yes | Milestone tracking |
| `kit_tools/AGENT_README.md` | Yes | Documentation checklist reference |
| `kit_tools/AUDIT_FINDINGS.md` | Optional | Created if code quality check runs |

**Deletes:**
- `kit_tools/SESSION_SCRATCH.md` — Removed after processing notes

**Uses agents:**
- `template-validator.md` — Validates docs updated during session (Step 2.5)
- `code-quality-validator.md` — Inline quality check on session changes (Step 3)

**Related hooks:**
- `remind_close_session.py` (Stop) — Reminds to run this skill if scratchpad has notes

## Step 0: Process scratchpad

- Read `kit_tools/SESSION_SCRATCH.md`
- **Identify which feature/PRD was being worked on** from the "Active Feature" section
- Use these notes to inform the documentation updates below
- If the scratchpad is empty, that's okay — proceed with what you remember from this session

## Step 1: Update PRD and tracking files

Based on the scratchpad's "Active Feature" section and the work done:

### 1a: Update the active PRD

If working on a feature with a PRD (`kit_tools/prd/prd-*.md`):

- Mark completed acceptance criteria with `[x]`
- Update the `updated:` date in the frontmatter
- **Capture Implementation Notes** — Ask the user:
  > "Any learnings or gotchas from today's work that should be captured in the PRD's Implementation Notes section?"
- Add any discovered learnings to the `## Implementation Notes` section
- If all user stories are complete, note that the PRD may be ready for `/kit-tools:complete-feature`

### 1b: Update milestone tracking

- `kit_tools/roadmap/MVP_TODO.md` — Update milestone progress if applicable
- `kit_tools/roadmap/BACKLOG.md` — Add any new feature ideas discovered

### 1c: Multiple features

If work touched multiple PRDs, update each relevant one

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

## Step 2.5: Validate updated docs

For each doc updated in Step 2, run a quick validation using `template-validator`:

- Check no placeholder text was accidentally left behind
- Verify file paths and references are accurate
- Ensure "Last Updated" date was set

If validation finds issues, fix them before proceeding. This prevents incomplete documentation from accumulating.

## Step 3: Quick code quality check

Run a lightweight quality check on the session's code changes. This is NOT the full feature validation — use `/kit-tools:validate-feature` for that after executing a feature.

### 3a: Get the session diff

- Run `git diff` to capture uncommitted changes
- If no uncommitted changes, use `git diff HEAD~1` to capture the last commit
- Run `git diff --name-only` (or `HEAD~1`) for the file list
- If no code changes (only documentation), skip to Step 4

### 3b: Run quality check

1. Read `$CLAUDE_PLUGIN_ROOT/agents/code-quality-validator.md`
2. Read project context files if they exist: `kit_tools/docs/CONVENTIONS.md`, `kit_tools/docs/GOTCHAS.md`, `kit_tools/arch/CODE_ARCH.md`
3. Interpolate `{{GIT_DIFF}}`, `{{CHANGED_FILES}}`, `{{CONVENTIONS}}`, `{{GOTCHAS}}`, `{{CODE_ARCH}}` into the template
4. Spawn via Task tool with `subagent_type: "general-purpose"`
5. Parse findings from the response

### 3c: Log findings

- If findings exist, write them to `kit_tools/AUDIT_FINDINGS.md` (create from template if missing)
- Critical findings should be noted in the session log's "Open Items" section
- Findings are advisory — they do not block the session from closing

## Step 4: Update Session Log

Add an entry to `kit_tools/SESSION_LOG.md` with:

- Today's date
- **Which PRD(s)/feature(s) were worked on**
- What was accomplished (use scratchpad notes as reference)
- Which docs were updated
- Open items for next session

## Step 5: Delete scratchpad

- Delete `kit_tools/SESSION_SCRATCH.md` entirely
- This signals the session closed cleanly

## Step 6: Summary

Provide a brief summary of:

- What was accomplished today
- **Which PRD(s) were updated** and their progress (e.g., "prd-auth.md: 4/5 stories complete")
- Implementation Notes captured (if any)
- What documentation was updated
- Audit findings summary (N critical, N warning, N info) — if validator was run
- Any open items or recommended next steps
- If a PRD is complete, remind user about `/kit-tools:complete-feature`
