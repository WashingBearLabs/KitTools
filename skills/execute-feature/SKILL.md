---
name: execute-feature
description: Execute PRD user stories autonomously, with supervision, or in guarded mode
---

# Execute Feature

Execute user stories from a PRD. Supports three modes: supervised (in-session with review between stories), autonomous (multi-session, runs until complete), and guarded (multi-session, pauses on failures).

## Dependencies

This skill requires:

| File | Required | Purpose |
|------|----------|---------|
| `kit_tools/prd/prd-*.md` | Yes | PRD with user stories to execute |
| `$CLAUDE_PLUGIN_ROOT/agents/story-implementer.md` | Yes | Implementation agent template |
| `$CLAUDE_PLUGIN_ROOT/agents/story-verifier.md` | Yes | Verification agent template |
| `$CLAUDE_PLUGIN_ROOT/scripts/execute_orchestrator.py` | For autonomous/guarded | Python orchestrator script |

**Creates:**
- `kit_tools/prd/.execution-state.json` — Machine-readable execution state (gitignored)
- `kit_tools/prd/.execution-config.json` — Orchestrator config (gitignored)
- `kit_tools/EXECUTION_LOG.md` — Human-readable execution log

**Modifies:**
- `kit_tools/prd/prd-*.md` — Checks off acceptance criteria as stories complete

## Arguments

| Argument | Description |
|----------|-------------|
| `[prd-name]` | Optional: specific PRD to execute (e.g., `prd-auth`) |

---

## Step 1: Select PRD (or check status)

### Check for existing execution state

First, check if `kit_tools/prd/.execution-state.json` exists:

**If it exists and `status: running`:**
> Read the state file and report progress:
> ```
> Execution in progress for [prd-name]:
>
> | Story | Status | Attempts |
> |-------|--------|----------|
> | US-001 | completed | 1 |
> | US-002 | in_progress | 2 |
> | US-003 | pending | — |
>
> Monitor: tail -f kit_tools/EXECUTION_LOG.md
> Pause: touch kit_tools/.pause_execution
> ```

**If it exists and `status: completed`:**
> ```
> Execution complete for [prd-name]!
>
> All stories implemented and verified.
> Branch: feature/[name]
>
> Next step: Run `/kit-tools:validate-feature` to validate the implementation
> ```

**If it exists and `status: failed` or `status: paused`:**
> ```
> Previous execution for [prd-name] stopped.
> Status: [failed/paused]
> Progress: [N/M] stories completed
>
> Would you like to:
> 1. Resume execution
> 2. Start fresh (resets state)
> 3. Abort (keep current state)
> ```

### If no existing state (or starting fresh)

**If argument provided:**
Look for `kit_tools/prd/prd-[argument].md` or `kit_tools/prd/[argument].md`

**If no argument:**
List active PRDs from `kit_tools/prd/` (exclude `archive/`):

```
Active PRDs:

1. prd-auth.md (2/5 stories complete)
2. prd-payments.md (0/4 stories complete)

Which PRD would you like to execute?
```

Show story completion progress for each PRD by counting `- [ ]` vs `- [x]` checkboxes.

### Epic Detection

After selecting a PRD, read its frontmatter. If the `epic` field is present and non-empty:

1. Scan `kit_tools/prd/` (non-archived) for all PRDs with the same `epic` value
2. Also scan `kit_tools/prd/archive/` for completed PRDs in the same epic
3. Order all by `epic_seq`
4. Determine which are already completed (archived)

Present to user:

```
This PRD is part of epic "[epic-name]" ([N] PRDs):

  1. prd-[name-1].md  [completed - archived]
  2. prd-[name-2].md  [next]  ← you are here
  3. prd-[name-3].md  [pending]

How would you like to proceed?
  A. Execute all remaining PRDs, pause between each for review (recommended)
  B. Execute all remaining PRDs non-stop
  C. Execute just this PRD
  D. Cancel
```

**If option A:** Same as B, but sets `epic_pause_between_prds: true` in the config. The orchestrator will pause after each PRD completes (validate + tag + archive), giving you a chance to review before the next PRD starts. Resume by removing the pause file.

**If option B:** The orchestrator will be configured with `epic_prds` (all non-archived PRDs) and will execute them in sequence on a shared `epic/[name]` branch with no stops between PRDs.

**If option C:** Execute only this PRD as a standalone, but still use the `epic/[name]` branch.

**If no `epic` field:** Continue with standalone behavior (no change).

---

## Step 2: Permission Level

Present mode selection:

```
How should execution run?

A. Supervised — Review each story before continuing
   (runs in this session, you approve each step)

B. Autonomous — Run until complete
   (spawns separate Claude sessions, unlimited retries by default)

C. Autonomous with limit — Run with a max retry count per story
   (spawns separate sessions, stops when limit exceeded)

D. Guarded — Run autonomously, pause on failures for your input
   (spawns separate sessions, pauses after 3 failed retries by default)
```

**For option B:** Show warning and ask for confirmation:
```
WARNING: Autonomous execution will spawn separate Claude sessions for each story.
Estimated: [N stories x ~2 sessions each] = ~[2N] sessions minimum.
Retries will increase session count. Monitor: tail -f kit_tools/EXECUTION_LOG.md
Pause anytime: touch kit_tools/.pause_execution

Proceed with unlimited retries? (yes/no)
```

**For option C:** Ask for max retries per story (suggest default of 5).

**For option D:** Confirm default 3 retries before pausing, or let user adjust.

---

## Step 3: Pre-flight Checks

Run these checks before starting execution:

### 1. Session readiness
Read the PRD frontmatter. Check for `session_ready: true`.
- If `session_ready: false`: Warn and ask to continue anyway.
- If field missing: Proceed with a note.

### 2. Dependency check
Read `depends_on` from PRD frontmatter. For each dependency:
- Check if a completed PRD exists in `kit_tools/prd/archive/prd-[dep].md`
- If dependencies not met: Warn with specific missing deps, ask to continue.

### 3. Clean working tree
Run `git status --porcelain` via Bash.
- If output is non-empty: Stop and ask user to commit or stash changes first.

### 4. Uncompleted stories exist
Parse PRD for stories with unchecked criteria.
- If all stories complete: Report that nothing to execute, suggest `/kit-tools:complete-feature`.

### 5. No concurrent execution
Check `.execution-state.json` for `status: running`.
- If running: Report existing execution and abort.

### 6. Branch base point (new branch only)
If the feature/epic branch does NOT already exist:
- Verify current branch is `main` by running `git branch --show-current`
- If not on main: switch to main first with `git checkout main`
- This ensures the new branch will be based on main, not on another feature branch

If the branch already exists (resuming):
- Verify the branch is based on main: `git merge-base --is-ancestor main [branch-name]`
- If check fails: Warn that the branch may contain commits from another feature. Ask whether to continue or rebase first.

### 7. Dependency gate (epic PRDs)
For PRDs with an `epic` field: this is a **hard gate**.
- All PRDs listed in `depends_on` **must** be archived in `kit_tools/prd/archive/`
- If any dependency is not archived, **block execution** and report which are missing

For standalone PRDs (no `epic` field): soft warning only (existing behavior from check 2).

Report results:

```
Pre-flight checks:

[PASS] Session ready: true
[PASS] Dependencies met: none required
[PASS] Working tree clean
[PASS] 4 uncompleted stories found
[PASS] No concurrent execution
[PASS] Branch base: will branch from main
[PASS] Epic dependencies: arxiv-source (archived)

Ready to execute.
```

---

## Step 4: Git Branch Setup

### Epic PRD (has `epic` field)

Branch name: `epic/[epic-name]` (e.g., `epic/arxiv`)

**New epic:**
```bash
git checkout main
git checkout -b epic/[epic-name]
```

**Resuming (branch exists):**
```bash
git checkout epic/[epic-name]
```

### Standalone PRD (no `epic` field)

Branch name: `feature/[prd-feature-name]` (unchanged)

**New branch:**
```bash
git checkout main
git checkout -b feature/[prd-feature-name]
```

**Resuming (branch exists):**
```bash
git checkout feature/[prd-feature-name]
```

- Feature name comes from the PRD frontmatter `feature` field
- Epic name comes from the PRD frontmatter `epic` field
- Record branch name for state tracking

---

## Step 5: Context Assembly

Read the following project files to build execution context. Tag each as "Not available" if the file doesn't exist:

| File | Context Key |
|------|-------------|
| `kit_tools/SYNOPSIS.md` | `synopsis` |
| `kit_tools/arch/CODE_ARCH.md` | `code_arch` |
| `kit_tools/docs/CONVENTIONS.md` | `conventions` |
| `kit_tools/docs/GOTCHAS.md` | `gotchas` |
| PRD: Overview, Goals, Technical Considerations, Non-Goals | `prd_overview` |
| `kit_tools/EXECUTION_LOG.md` (prior learnings, if resuming) | `prior_learnings` |

**Context pruning:** For stories beyond the 3rd, summarize earlier learnings to a bullet list. Keep only the 3 most recent stories' full learnings in the prompt.

---

## Step 6: Initialize State Files

Create or update execution state:

### `.execution-state.json`
```json
{
  "prd": "prd-auth.md",
  "branch": "feature/auth",
  "mode": "autonomous",
  "max_retries": null,
  "started_at": "2026-02-06T10:30:00Z",
  "updated_at": "2026-02-06T10:30:00Z",
  "status": "running",
  "stories": {},
  "sessions": {
    "total": 0,
    "implementation": 0,
    "verification": 0,
    "validation": 0
  }
}
```

### `EXECUTION_LOG.md`
Append a run header (create file if needed):
```markdown
# Execution Log
> Last updated: 2026-02-06

## Run: auth — 2026-02-06
- **PRD:** prd-auth.md
- **Branch:** feature/auth
- **Mode:** autonomous (unlimited retries)
- **Stories:** 5 total, 0 complete at start
```

---

## Step 7: Execution Loop

### Supervised Mode (in-session)

For each uncompleted story (in PRD order):

1. **Read agent templates:**
   - Read `$CLAUDE_PLUGIN_ROOT/agents/story-implementer.md`
   - Interpolate `{{PLACEHOLDERS}}` with story + project context + learnings

2. **Spawn implementer:**
   - Use Task tool with `subagent_type: "general-purpose"`
   - Pass the interpolated prompt
   - Parse `IMPLEMENTATION_RESULT` from response

3. **Read verifier template:**
   - Read `$CLAUDE_PLUGIN_ROOT/agents/story-verifier.md`
   - Interpolate with implementation results

4. **Spawn verifier:**
   - Use Task tool with `subagent_type: "general-purpose"`
   - Parse `VERIFICATION_RESULT` from response

5. **If PASS:**
   - Update PRD checkboxes to `[x]` for this story
   - Append learnings to PRD Implementation Notes
   - Update `.execution-state.json`
   - Append success entry to `EXECUTION_LOG.md`
   - Git commit: `feat([feature]): [story-id] - [story-title]`
   - Present results to user, ask to continue

6. **If FAIL:**
   - Log failure details + learnings to `EXECUTION_LOG.md` and state JSON
   - Present failure to user with verifier's notes
   - Ask: retry with learnings, adjust approach, or stop?

### Autonomous/Guarded Mode (multi-session)

1. **Write execution config** to `kit_tools/prd/.execution-config.json`:

   **Standalone PRD (no epic):**
   ```json
   {
     "prd_path": "kit_tools/prd/prd-auth.md",
     "project_dir": "/absolute/path/to/project",
     "branch_name": "feature/auth",
     "feature_name": "auth",
     "mode": "autonomous",
     "max_retries": null,
     "implementer_template": "... raw story-implementer.md content ...",
     "verifier_template": "... raw story-verifier.md content ...",
     "project_context": {
       "synopsis": "... SYNOPSIS.md content ...",
       "code_arch": "... CODE_ARCH.md content ...",
       "conventions": "... CONVENTIONS.md content ...",
       "gotchas": "... GOTCHAS.md content ...",
       "prd_overview": "... PRD overview section ..."
     }
   }
   ```

   **Epic PRD (user chose "Execute remaining epic PRDs in sequence"):**
   ```json
   {
     "project_dir": "/absolute/path/to/project",
     "branch_name": "epic/arxiv",
     "mode": "autonomous",
     "max_retries": null,
     "implementer_template": "... raw story-implementer.md content ...",
     "verifier_template": "... raw story-verifier.md content ...",
     "project_context": {
       "synopsis": "... SYNOPSIS.md content ...",
       "code_arch": "... CODE_ARCH.md content ...",
       "conventions": "... CONVENTIONS.md content ...",
       "gotchas": "... GOTCHAS.md content ...",
       "prd_overview": "... PRD overview section ..."
     },
     "epic_name": "arxiv",
     "epic_pause_between_prds": true,
     "epic_prds": [
       {
         "prd_path": "/abs/path/kit_tools/prd/prd-arxiv-source.md",
         "feature_name": "arxiv-source",
         "epic_seq": 1,
         "epic_final": false
       },
       {
         "prd_path": "/abs/path/kit_tools/prd/prd-arxiv-api.md",
         "feature_name": "arxiv-api",
         "epic_seq": 2,
         "epic_final": false
       },
       {
         "prd_path": "/abs/path/kit_tools/prd/prd-arxiv-ui.md",
         "feature_name": "arxiv-ui",
         "epic_seq": 3,
         "epic_final": true
       }
     ]
   }
   ```

   When `epic_prds` is present, the orchestrator runs in epic mode — executing each PRD's stories in sequence on the shared branch, with tagging and archiving between PRDs.

   When `epic_prds` is absent, the orchestrator runs in single-PRD mode (backwards compatible — uses `prd_path`/`feature_name` top-level fields).

   **Important:** Exclude already-completed/archived PRDs from `epic_prds`. Only include PRDs that still need execution.

2. **Launch orchestrator** via Bash (run_in_background):
   ```bash
   python3 "$CLAUDE_PLUGIN_ROOT/scripts/execute_orchestrator.py" \
     --config "kit_tools/prd/.execution-config.json"
   ```

3. **Report to user:**
   ```
   Execution started on branch feature/[name]

   Monitor progress: tail -f kit_tools/EXECUTION_LOG.md
   Pause execution: touch kit_tools/.pause_execution
   Check status: re-run /kit-tools:execute-feature

   The orchestrator is running in the background. You can continue
   working in this session or close it — execution will continue.
   ```

---

## Step 8: Completion

When all stories are done (detected by supervised loop finishing, or by status check):

- Update `.execution-state.json` status to `completed`
- Write final summary entry to `EXECUTION_LOG.md`
- Report to user:

```
Execution complete!

PRD: prd-auth.md
Branch: feature/auth
Stories: 5/5 completed
Total attempts: 7 (2 retries)
Sessions: 12 (5 implementation + 5 verification + 2 retry)

Learnings captured in:
- PRD Implementation Notes
- kit_tools/EXECUTION_LOG.md

Next step: Run `/kit-tools:validate-feature` to validate the implementation
```

---

## Placeholder Token Reference

These tokens are used in the agent templates and interpolated by this skill (supervised) or the orchestrator (autonomous/guarded):

| Token | Source |
|-------|--------|
| `{{STORY_ID}}` | Story ID (e.g., "US-003") |
| `{{STORY_TITLE}}` | Story title from PRD |
| `{{STORY_DESCRIPTION}}` | Full story description |
| `{{ACCEPTANCE_CRITERIA}}` | Checkbox list from PRD |
| `{{FEATURE}}` | Feature name from PRD frontmatter |
| `{{PRD_OVERVIEW}}` | Overview + goals + tech considerations + non-goals |
| `{{PROJECT_SYNOPSIS}}` | SYNOPSIS.md contents |
| `{{CODE_ARCH}}` | CODE_ARCH.md contents |
| `{{CONVENTIONS}}` | CONVENTIONS.md contents |
| `{{GOTCHAS}}` | GOTCHAS.md contents |
| `{{PRIOR_LEARNINGS}}` | Learnings from completed stories (pruned) |
| `{{RETRY_CONTEXT}}` | Empty on first attempt; failure details on retry |
| `{{FILES_CHANGED}}` | Files changed by implementer (verifier only) |
| `{{IMPLEMENTATION_EVIDENCE}}` | Evidence claims from implementer (verifier only) |

---

## Related Skills

| Skill | When to use |
|-------|-------------|
| `/kit-tools:plan-feature` | To create a PRD before executing |
| `/kit-tools:complete-feature` | To archive PRD after all stories pass |
| `/kit-tools:start-session` | To orient on active PRDs at session start |
| `/kit-tools:validate-feature` | To validate the full feature branch against its PRD |
