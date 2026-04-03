---
name: execution-status
description: Check progress and status of autonomous epic execution
---

# Execution Status

Check on the progress of an autonomous or guarded execution launched by `/kit-tools:execute-epic`. Read-only — this skill inspects state files and logs without modifying anything.

---

## Step 1: Check for Active Execution

Read `kit_tools/specs/.execution-state.json`:

- **Not found:** Report "No execution state found. Run `/kit-tools:execute-epic` to start." and stop.
- **Found:** Continue to Step 2.

Also read `kit_tools/specs/.execution-config.json` to get the `tmux_session` field (the session name used at launch). Check if it's alive:

```bash
tmux has-session -t {tmux_session} 2>/dev/null
```

If `tmux_session` is missing from the config (older runs), fall back to `kit-exec-{feature_name}` derived from the state file's `spec` field (strip the `feature-` or `prd-` prefix and `.md` suffix).

Record whether the session is running or not — this affects the status report.

---

## Step 2: Build Status Report

Parse the state file and present a structured report.

### Overall Status

Determine the effective status:

| State JSON `status` | tmux alive? | Effective Status |
|---------------------|-------------|------------------|
| `running` | Yes | **Running** |
| `running` | No | **Stale** (orchestrator not running) |
| `crashed` | — | **Crashed** |
| `completed` | — | **Completed** |
| `failed` | — | **Failed** |
| `paused` | — | **Paused** |

Check for pause file: `kit_tools/.pause_execution` — if present, status is **Paused** regardless of state JSON.

> **Note:** Execution notifications are surfaced automatically via a `UserPromptSubmit` hook — when the orchestrator completes, fails, crashes, or pauses, you will see a summary the next time the user sends a message. The tmux session is cleaned up automatically on completion. This skill provides full details on demand.

### Progress

Parse the feature spec file referenced in the state (`state.spec`) to get the total story count using the same `### US-XXX:` pattern the orchestrator uses.

Count from `state.stories` (or `state.specs[current_spec].stories` in epic mode):
- **Completed:** stories with `status: "completed"`
- **Failed/Retrying:** stories with `status: "retrying"` or `status: "failed"`
- **In Progress:** stories with `status: "in_progress"`
- **Pending:** stories not yet in the state dict

Calculate and display: `completed / total * 100`%

Show the current story (the one with `status: "in_progress"` or `"retrying"`).

### Per-Story Table

```
| Story | Status | Attempts | Last Result |
|-------|--------|----------|-------------|
| US-001 | completed | 1 | PASS |
| US-002 | retrying | 2 | FAIL: criterion 3 not met |
| US-003 | in_progress | 1 | — |
| US-004 | pending | 0 | — |
```

For each story from the feature spec (in order):
- Look up the story in the state dict
- **Status:** from state, or `pending` if not present
- **Attempts:** from `entry.attempts`, or `0` if not present
- **Last Result:** `PASS` if completed, `FAIL: <entry.last_failure>` if failed/retrying, `—` if pending/in_progress

### Session Stats

From the state file:
- **Sessions spawned:** `state.sessions.total` (breakdown: `state.sessions.implementation` impl, `state.sessions.verification` verify, `state.sessions.validation` validation)
- **Estimated tokens:** `state.token_estimates.input` input, `state.token_estimates.output` output (display in k units: `value / 1000`). If `token_estimates` is missing, omit this line.
- **Time elapsed:** `state.started_at` to now
- **Last activity:** `state.updated_at` — flag as **stale** if more than 5 minutes ago

### Epic Mode

If `state.specs` exists (epic mode), show a per-feature-spec progress table:

```
| Feature Spec | Status | Stories | Progress |
|--------------|--------|---------|----------|
| feature-oauth-schema.md | completed | 3/3 | 100% |
| feature-oauth-provider.md | in_progress | 1/4 | 25% |
| feature-oauth-api.md | pending | 0/5 | 0% |
```

- **Current feature spec:** `state.current_spec`
- For each feature spec in `state.specs`: count completed vs total stories

---

## Step 3: Recent Activity

Read the last 20 lines of `kit_tools/EXECUTION_LOG.md` and display them under a "Recent Activity" heading. This shows the latest story attempts, pass/fail results, and any error messages.

If the file doesn't exist, report "No execution log found."

---

## Step 4: Available Actions

Present available actions based on current state using AskUserQuestion:

### If Running (tmux alive)

- **Pause** — `touch kit_tools/.pause_execution` (pauses after current story completes)
- **Attach to tmux** — Print `tmux attach -t {tmux_session}` for user to run
- **Refresh** — Re-read state and show updated status

### If Crashed (status is `crashed`)

Warn: "The orchestrator crashed. The process exited unexpectedly."

- **Resume execution** — Suggest running `/kit-tools:execute-epic` (it will detect the existing state and resume)
- **Reset state** — Delete `.execution-state.json` to start fresh
- **View log** — Show full `EXECUTION_LOG.md`

### If Stale (tmux dead but status is `running`)

Warn: "The orchestrator is not running but state shows `running`. The process may have crashed or been interrupted."

- **Resume execution** — Suggest running `/kit-tools:execute-epic` (it will detect the existing state and resume)
- **Reset state** — Delete `.execution-state.json` to start fresh
- **View log** — Show full `EXECUTION_LOG.md`

### If Paused

- **Resume** — `rm kit_tools/.pause_execution`
- **Attach to tmux** — Print `tmux attach -t {tmux_session}` for user to run
- **View findings** — If `.pause_execution` references `AUDIT_FINDINGS.md`, suggest reading it

### If Completed

- **Validate** — Suggest `/kit-tools:validate-implementation`
- **Complete** — Suggest `/kit-tools:complete-implementation`
- **View log** — Show full execution log

### If Failed

- Show failure details from the last story with `status: "failed"` or `status: "retrying"`
- **Retry** — Suggest `/kit-tools:execute-epic` to resume
- **View log** — Show full execution log

Ask the user which action to take, then execute it.

---

## Related Skills

| Skill | When to use |
|-------|-------------|
| `/kit-tools:execute-epic` | To start or resume autonomous execution |
| `/kit-tools:validate-implementation` | To validate the full feature branch after execution |
| `/kit-tools:complete-implementation` | To archive feature spec after all stories pass |
