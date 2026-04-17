---
name: execute-epic
description: Execute an epic's feature specs autonomously, supervised, or guarded
---

# Execute Epic

Execute user stories from an epic's feature specs. Supports three modes: supervised (in-session with review between stories), autonomous (multi-session, runs until complete), and guarded (multi-session, pauses on failures).

Read `REFERENCE.md` in this skill directory for detailed schemas, token tables, and edge cases.

## Dependencies

| File | Required | Purpose |
|------|----------|---------|
| `kit_tools/specs/epic-*.md` | Yes (primary) | Epic wrapper with decomposition table |
| `kit_tools/specs/feature-*.md` | Yes | Feature specs with user stories to execute |
| `$CLAUDE_PLUGIN_ROOT/agents/story-implementer.md` | Yes | Implementation agent template |
| `$CLAUDE_PLUGIN_ROOT/agents/story-verifier.md` | Yes | Verification agent template |
| `$CLAUDE_PLUGIN_ROOT/scripts/execute_orchestrator.py` | For autonomous/guarded | Python orchestrator script |

**Creates:** `.execution-state.json`, `.execution-config.json`, `EXECUTION_LOG.md`
**Modifies:** Feature spec checkboxes (updated by orchestrator/skill after verification passes)

---

## Step 1: Select Epic

Check `kit_tools/specs/.execution-state.json`:
- **`status: running`** — Report progress table, offer monitoring commands
- **`status: completed`** — Report completion, suggest `/kit-tools:validate-implementation`
- **`status: failed/paused`** — Offer: resume, start fresh, or abort

**If no state:** Check `kit_tools/specs/` for `epic-*.md` files. If found, list them with status (how many specs completed vs. remaining). User selects which epic to execute.

From the selected `epic-*.md`, read the Decomposition table to get the ordered list of feature specs. Check `.execution-state.json` for any running/paused/completed state for each spec.

Present options:
- **A.** Execute all remaining specs, pause between each (recommended)
- **B.** Execute all remaining specs non-stop
- **C.** Execute just one specific spec (ask which)
- **D.** Cancel

**Fallback:** If no `epic-*.md` files are found, fall back to listing feature specs directly from `kit_tools/specs/`. This is a backwards-compatibility path for projects that predate the epic-wrapper convention. In fallback mode, if a selected feature spec has an `epic` frontmatter field, scan for sibling specs by that field to assemble the execution order.

---

## Step 2: Permission Level

- **A. Supervised** — In-session, review between stories
- **B. Autonomous** — Multi-session, unlimited retries (show warning + confirmation)
- **C. Autonomous with limit** — Ask for max retries (suggest 5)
- **D. Guarded** — Pause after 3 failed retries (adjustable)

---

## Step 2a: Monitoring (Autonomous/Guarded only)

If the user selected Autonomous or Guarded mode, ask:

> **Enable supervisor monitoring?** This keeps the current Claude session active as a supervisor, checking orchestrator health every 30 minutes. The supervisor can detect crashes, kill runaway processes, split oversized stories, and pause execution if problems persist.
>
> - **A. Yes** (recommended for long-running epics)
> - **B. No** — fire and forget

Store as `monitor: true/false` in `.execution-config.json`. Default: `false`.

**Important lifetime note to surface to the user if they pick Yes:**

> The supervisor runs via a cron scheduled to your current Claude Code session. It only fires while *this session is alive* — if you close this terminal / Claude Code window, the supervisor stops checking. The orchestrator itself keeps running in tmux regardless, but no one's watching for crashes or hung processes while the session is closed. For overnight runs where you'll close your laptop: either leave this session open, or pick "fire and forget" and rely on the 24-hour orchestrator safety net + execution notifications on your next session.
>
> Known quirk: if your laptop sleeps mid-run, cron fires queued during sleep may all run in quick succession on wake. This is usually harmless (each one just re-reads the health snapshot) but can produce a burst of supervisor log lines after your laptop wakes.

Skip this step for Supervised mode (the user is already present).

---

## Step 2b: Completion Strategy

After all stories pass and validation completes, how should the feature be finalized?

- **A. Create PR** (recommended) — Push branch, create GitHub PR for review
- **B. Merge to main** — Auto-merge to main and delete branch (blocked if validation finds critical issues)
- **C. None** — Leave branch as-is, clean up tmux only

Store as `completion_strategy` in `.execution-config.json`: `"pr"`, `"merge"`, or `"none"`. Default: `"pr"`.

---

## Step 2c: Model Selection (optional)

The orchestrator can use different models for each role. Defaults:

- **implementer** — Sonnet (cost-optimized for bulk code generation)
- **verifier** — Opus (quality-critical independent review)
- **validator** — Opus (the session that runs `/kit-tools:validate-implementation` after all stories pass; it makes judgment calls about finding severity and fix prioritization)

Offer the user a chance to override:

> **Model configuration for this run?**
>
> - **A. Defaults** — Sonnet for implementation, Opus for verification and validation (recommended)
> - **B. All Opus** — Every role on Opus (highest cost, highest quality)
> - **C. All Sonnet** — Every role on Sonnet (lowest cost, suitable for low-risk features)
> - **D. Custom** — Specify each role individually

If the user picks an option, store as `model_config` in `.execution-config.json`:

```json
{
  "model_config": {
    "implementer": "sonnet",
    "verifier": "opus",
    "validator": "opus"
  }
}
```

If `model_config` is omitted, the orchestrator falls back to its `DEFAULT_MODEL_CONFIG` (same as option A). Partial overrides are supported — missing keys keep their defaults. Values must be aliases the local `claude` CLI accepts (e.g., `sonnet`, `opus`, or full model IDs like `claude-sonnet-4-6`).

Skip this step if the user just wants defaults — the orchestrator behaves the same as before.

---

## Step 3: Pre-flight Checks

Run checks and report pass/fail for each:

1. **Session readiness** — `session_ready: true` in frontmatter
2. **Dependency check** — `depends_on` feature specs archived
3. **Clean working tree** — `git status --porcelain` empty
4. **Uncompleted stories** — At least one story with unchecked criteria
5. **No concurrent execution** — State not `running`
6. **Branch base** — New branch from `main`, or existing branch based on `main`
7. **Epic dependency gate** — Hard gate: all `depends_on` feature specs must be archived
8. **tmux available** (autonomous/guarded only) — `which tmux` succeeds
   - If not installed: warn, offer manual launch fallback (print command for separate terminal)
9. **Story quality check** — Scan uncompleted stories for potential issues:
   - Stories with fewer than 2 acceptance criteria (may be under-specified)
   - Acceptance criteria that are vague (e.g., "works correctly", "is fast", "looks good")
   - If issues found: warn with specifics, ask user to confirm or refine before proceeding
10. **gh auth** (if `completion_strategy` is `"pr"`) — Run `gh auth status`. If fails, warn and ask user to pick a different strategy or fix auth.

---

## Step 4: Git Branch Setup

- **Epic feature spec:** Branch `epic/[epic-name]`
- **Standalone feature spec (fallback):** Branch `feature/[feature-name]`

Create new or checkout existing. Feature/epic name from feature spec frontmatter.

---

## Step 5: Context Assembly

Discover paths (do NOT inline file contents):

| File | Context Key |
|------|-------------|
| `kit_tools/SYNOPSIS.md` | `synopsis` |
| `kit_tools/arch/CODE_ARCH.md` | `code_arch` |
| `kit_tools/docs/CONVENTIONS.md` | `conventions` |
| `kit_tools/docs/GOTCHAS.md` | `gotchas` |
| Feature spec: Overview, Goals, Tech, Out of Scope | `spec_overview` (inline — small) |

Agents read context files on-demand via their Read tool.

---

## Step 6: Initialize State

**Autonomous/Guarded mode:** Do NOT create `.execution-state.json`. The orchestrator creates it with the correct schema (single-spec or epic) on first run. Pre-creating state causes schema mismatches.

**Supervised mode:** Create `.execution-state.json` using the single-spec schema from REFERENCE.md (supervised mode does not support epics).

**All modes:** Append a run header to `EXECUTION_LOG.md`.

---

## Step 7: Execution Loop

### Supervised Mode

For each uncompleted story:
1. Read + interpolate `story-implementer.md`, spawn via Task tool
2. Read implementer JSON result file
3. Get files changed from `git diff --name-only` and `git diff --stat`
4. Read + interpolate `story-verifier.md` (with diff stat, test command, full context paths), spawn via Task tool
5. Read verifier JSON result file
6. **PASS:** Update feature spec checkboxes (orchestrator/skill handles this), commit, log success, ask to continue
7. **FAIL:** Log failure, present to user, ask: retry / adjust / stop

> The implementer does NOT self-verify or update feature spec checkboxes. The verifier is the sole quality gate. Feature spec checkboxes are updated by the orchestrator (autonomous/guarded) or this skill (supervised) after verification passes.

### Autonomous/Guarded Mode

1. Write `.execution-config.json` using a Python inline script that reads the agent templates via Python file I/O — **never use shell heredocs or `$(cat ...)` substitution to embed template content** (single-quoted heredocs suppress expansion; double-quoted heredocs break on special characters). See REFERENCE.md for the schema and the correct creation pattern.
2. Check for tmux: `which tmux`
3. **Derive tmux session name:** `kit-exec-{epic_name}` (e.g., `kit-exec-oauth`, `kit-exec-auth`). Store as `tmux_session` in `.execution-config.json`.
4. **Check for name collision:** Run `tmux has-session -t {session_name} 2>/dev/null`. If it exists, **do NOT kill it** — warn the user and append a short suffix (e.g., `-2`) or ask them to choose a name.
5. **If tmux available:** Launch orchestrator in a detached tmux session:
   ```bash
   tmux new-session -d -s {session_name} \
     "unset CLAUDECODE; python3 \"$CLAUDE_PLUGIN_ROOT/scripts/execute_orchestrator.py\" \
     --config \"$(pwd)/kit_tools/specs/.execution-config.json\""
   ```
   The orchestrator kills its own tmux session on completion. Progress is reported to the parent Claude session via file-based notifications (surfaced on the user's next prompt).
6. **If no tmux:** Print the command for the user to run in a separate terminal:
   ```
   Run this in a separate terminal window:

   python3 "<plugin_root>/scripts/execute_orchestrator.py" \
     --config "<project_dir>/kit_tools/specs/.execution-config.json"
   ```
7. Report monitoring commands (using the actual session name):
   - `/kit-tools:execution-status` — check progress, errors, and available actions
   - `tmux attach -t {session_name}` — attach to watch live output
   - `tail -f kit_tools/EXECUTION_LOG.md` — follow the execution log
   - `cat kit_tools/specs/.execution-state.json` — check current state
   - `touch kit_tools/.pause_execution` — pause after current story
8. **If `monitor: true` in config:** Set up the supervisor loop using CronCreate:
   ```
   CronCreate(cron: "*/30 * * * *", prompt: "/kit-tools:execution-status", recurring: true)
   ```
   Then run `/kit-tools:execution-status` immediately for the first check.
   
   Tell the user:
   > Supervisor monitoring active. I'll check orchestrator health every 30 minutes and intervene if needed (restart crashes, split oversized stories, pause on repeated failures). You can close this session to stop monitoring — the orchestrator will continue running independently.

---

## Step 8: Completion

- Update state to `completed`
- Write summary to `EXECUTION_LOG.md`
- Report: stories completed, total attempts, session count
- Suggest `/kit-tools:validate-implementation`

---

## Related Skills

| Skill | When to use |
|-------|-------------|
| `/kit-tools:plan-epic` | To create an epic and feature specs before executing |
| `/kit-tools:validate-epic` | To validate epic specs before execution |
| `/kit-tools:complete-implementation` | To archive feature spec after all stories pass |
| `/kit-tools:validate-implementation` | To validate the full feature branch against its feature spec |
