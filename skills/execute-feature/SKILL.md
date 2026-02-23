---
name: execute-feature
description: Execute PRD user stories autonomously, with supervision, or in guarded mode
---

# Execute Feature

Execute user stories from a PRD. Supports three modes: supervised (in-session with review between stories), autonomous (multi-session, runs until complete), and guarded (multi-session, pauses on failures).

Read `REFERENCE.md` in this skill directory for detailed schemas, token tables, and edge cases.

## Dependencies

| File | Required | Purpose |
|------|----------|---------|
| `kit_tools/prd/prd-*.md` | Yes | PRD with user stories to execute |
| `$CLAUDE_PLUGIN_ROOT/agents/story-implementer.md` | Yes | Implementation agent template |
| `$CLAUDE_PLUGIN_ROOT/agents/story-verifier.md` | Yes | Verification agent template |
| `$CLAUDE_PLUGIN_ROOT/scripts/execute_orchestrator.py` | For autonomous/guarded | Python orchestrator script |

**Creates:** `.execution-state.json`, `.execution-config.json`, `EXECUTION_LOG.md`
**Modifies:** PRD checkboxes as stories complete

---

## Step 1: Select PRD

Check `kit_tools/prd/.execution-state.json`:
- **`status: running`** — Report progress table, offer monitoring commands
- **`status: completed`** — Report completion, suggest `/kit-tools:validate-feature`
- **`status: failed/paused`** — Offer: resume, start fresh, or abort

**If no state:** List active PRDs from `kit_tools/prd/` with completion counts, ask which to execute.

### Epic Detection

If selected PRD has `epic` field: scan for all PRDs in the epic, present options:
- **A.** Execute all remaining, pause between each (recommended)
- **B.** Execute all remaining non-stop
- **C.** Execute just this PRD
- **D.** Cancel

---

## Step 2: Permission Level

- **A. Supervised** — In-session, review between stories
- **B. Autonomous** — Multi-session, unlimited retries (show warning + confirmation)
- **C. Autonomous with limit** — Ask for max retries (suggest 5)
- **D. Guarded** — Pause after 3 failed retries (adjustable)

---

## Step 3: Pre-flight Checks

Run checks and report pass/fail for each:

1. **Session readiness** — `session_ready: true` in frontmatter
2. **Dependency check** — `depends_on` PRDs archived
3. **Clean working tree** — `git status --porcelain` empty
4. **Uncompleted stories** — At least one story with unchecked criteria
5. **No concurrent execution** — State not `running`
6. **Branch base** — New branch from `main`, or existing branch based on `main`
7. **Epic dependency gate** — Hard gate: all `depends_on` PRDs must be archived

---

## Step 4: Git Branch Setup

- **Epic PRD:** Branch `epic/[epic-name]`
- **Standalone PRD:** Branch `feature/[feature-name]`

Create new or checkout existing. Feature/epic name from PRD frontmatter.

---

## Step 5: Context Assembly

Discover paths (do NOT inline file contents):

| File | Context Key |
|------|-------------|
| `kit_tools/SYNOPSIS.md` | `synopsis` |
| `kit_tools/arch/CODE_ARCH.md` | `code_arch` |
| `kit_tools/docs/CONVENTIONS.md` | `conventions` |
| `kit_tools/docs/GOTCHAS.md` | `gotchas` |
| PRD: Overview, Goals, Tech, Non-Goals | `prd_overview` (inline — small) |

Agents read context files on-demand via their Read tool.

---

## Step 6: Initialize State

Create `.execution-state.json` and append run header to `EXECUTION_LOG.md`.

---

## Step 7: Execution Loop

### Supervised Mode

For each uncompleted story:
1. Read + interpolate `story-implementer.md`, spawn via Task tool
2. Read implementer JSON result file
3. Get files changed from `git diff --name-only`
4. Read + interpolate `story-verifier.md`, spawn via Task tool
5. Read verifier JSON result file
6. **PASS:** Update PRD checkboxes, commit, log success, ask to continue
7. **FAIL:** Log failure, present to user, ask: retry / adjust / stop

### Autonomous/Guarded Mode

1. Write `.execution-config.json` (see REFERENCE.md for schema)
2. Launch orchestrator in background:
   ```bash
   python3 "$CLAUDE_PLUGIN_ROOT/scripts/execute_orchestrator.py" \
     --config "kit_tools/prd/.execution-config.json"
   ```
3. Report monitoring commands to user

---

## Step 8: Completion

- Update state to `completed`
- Write summary to `EXECUTION_LOG.md`
- Report: stories completed, total attempts, session count
- Suggest `/kit-tools:validate-feature`

---

## Related Skills

| Skill | When to use |
|-------|-------------|
| `/kit-tools:plan-feature` | To create a PRD before executing |
| `/kit-tools:complete-feature` | To archive PRD after all stories pass |
| `/kit-tools:validate-feature` | To validate the full feature branch against its PRD |
