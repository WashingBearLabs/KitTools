# Execute Feature — Reference

Detailed formats, schemas, and examples for the execute-feature workflow. Read this for edge cases and detailed field descriptions.

---

## Execution Config Schema

### Standalone PRD (no epic)

```json
{
  "prd_path": "kit_tools/prd/prd-auth.md",
  "project_dir": "/absolute/path/to/project",
  "branch_name": "feature/auth",
  "feature_name": "auth",
  "mode": "autonomous",
  "max_retries": null,
  "tmux_session": "kit-exec-auth",
  "implementer_template": "... raw story-implementer.md content ...",
  "verifier_template": "... raw story-verifier.md content ...",
  "project_context": {
    "synopsis": "kit_tools/SYNOPSIS.md",
    "code_arch": "kit_tools/arch/CODE_ARCH.md",
    "conventions": "kit_tools/docs/CONVENTIONS.md",
    "gotchas": "kit_tools/docs/GOTCHAS.md",
    "prd_overview": "... PRD overview section ..."
  }
}
```

### Epic PRD (multiple PRDs in sequence)

```json
{
  "project_dir": "/absolute/path/to/project",
  "branch_name": "epic/arxiv",
  "mode": "autonomous",
  "max_retries": null,
  "tmux_session": "kit-exec-arxiv",
  "implementer_template": "... raw story-implementer.md content ...",
  "verifier_template": "... raw story-verifier.md content ...",
  "project_context": {
    "synopsis": "kit_tools/SYNOPSIS.md",
    "code_arch": "kit_tools/arch/CODE_ARCH.md",
    "conventions": "kit_tools/docs/CONVENTIONS.md",
    "gotchas": "kit_tools/docs/GOTCHAS.md",
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

When `epic_prds` is present, the orchestrator runs in epic mode. When absent, it runs in single-PRD mode. Exclude already-completed/archived PRDs from `epic_prds`.

---

## Execution State Schema

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
  },
  "token_estimates": {
    "input": 0,
    "output": 0
  }
}
```

---

## Placeholder Token Reference

These tokens are used in the agent templates and interpolated by this skill (supervised) or the orchestrator (autonomous/guarded):

| Token | Source |
|-------|--------|
| `{{STORY_ID}}` | Story ID (e.g., "US-003") |
| `{{STORY_TITLE}}` | Story title from PRD |
| `{{STORY_DESCRIPTION}}` | Full story description |
| `{{IMPLEMENTATION_HINTS}}` | Per-story hints from planning (or fallback message) |
| `{{ACCEPTANCE_CRITERIA}}` | Checkbox list from PRD |
| `{{FEATURE}}` | Feature name from PRD frontmatter |
| `{{PRD_OVERVIEW}}` | Overview + goals + tech considerations + non-goals |
| `{{SYNOPSIS_PATH}}` | Path to SYNOPSIS.md |
| `{{CODE_ARCH_PATH}}` | Path to CODE_ARCH.md |
| `{{CONVENTIONS_PATH}}` | Path to CONVENTIONS.md |
| `{{GOTCHAS_PATH}}` | Path to GOTCHAS.md |
| `{{PRIOR_LEARNINGS}}` | Learnings from completed stories (pruned) |
| `{{RETRY_CONTEXT}}` | Empty on first attempt; failure details on retry |
| `{{PREVIOUS_ATTEMPT_DIFF}}` | Git diff from last failed attempt (for retries) |
| `{{FILES_CHANGED}}` | Files changed from git diff (verifier only) |
| `{{RESULT_FILE_PATH}}` | Path where agent should write its JSON result |

---

## Epic Flow Details

### Epic detection

After selecting a PRD, read its frontmatter. If the `epic` field is present and non-empty:

1. Scan `kit_tools/prd/` (non-archived) for all PRDs with the same `epic` value
2. Also scan `kit_tools/prd/archive/` for completed PRDs in the same epic
3. Order all by `epic_seq`
4. Determine which are already completed (archived)

### Epic user options

- **A. Execute all remaining, pause between each** — Sets `epic_pause_between_prds: true`. Pauses after each PRD (validate + tag + archive).
- **B. Execute all remaining non-stop** — No stops between PRDs.
- **C. Execute just this PRD** — Standalone on the `epic/[name]` branch.

### Epic orchestrator behavior

The orchestrator chains PRD execution:
1. Execute all stories in PRD N
2. Validate PRD N
3. Tag checkpoint: `[epic-name]/[feature-name]-complete`
4. Archive PRD N (update frontmatter, move to archive/)
5. Commit: `chore([epic-name]): complete [feature-name]`
6. (Optional: pause between PRDs)
7. Move to PRD N+1

---

## Pre-flight Check Details

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

If the branch already exists (resuming):
- Verify the branch is based on main: `git merge-base --is-ancestor main [branch-name]`
- If check fails: Warn that the branch may contain commits from another feature.

### 7. Dependency gate (epic PRDs)
For PRDs with an `epic` field: this is a **hard gate**.
- All PRDs listed in `depends_on` **must** be archived in `kit_tools/prd/archive/`
- If any dependency is not archived, **block execution**

For standalone PRDs (no `epic` field): soft warning only.

---

## Supervised Mode Details

For each uncompleted story (in PRD order):

1. **Read agent templates:** Read `$CLAUDE_PLUGIN_ROOT/agents/story-implementer.md`, interpolate placeholders
2. **Spawn implementer:** Task tool with `subagent_type: "general-purpose"`, read JSON result file
3. **Read verifier template:** Interpolate with git-sourced file list
4. **Spawn verifier:** Task tool, read JSON result file
5. **If PASS:** Update PRD checkboxes, update state, log success, commit
6. **If FAIL:** Log failure, present to user with verifier's notes, ask: retry, adjust, or stop?

---

## Autonomous Launch Details

### Why tmux?

Claude Code prevents running `claude -p` from within an existing Claude session to avoid infinite recursion. Since the orchestrator spawns `claude -p` subprocesses, launching it via `run_in_background` from inside a skill fails. A detached tmux session runs in a completely separate process tree, bypassing this restriction.

### tmux session naming

- **Session name pattern:** `kit-exec-{feature_name}` (e.g., `kit-exec-auth`, `kit-exec-processing-pipeline`). For epics: `kit-exec-{epic_name}`.
- The session name is stored in `.execution-config.json` as `tmux_session` so that `execution-status` can find it.
- If the derived session name already exists (`tmux has-session -t {name}`), append a suffix (e.g., `-2`) or ask the user.
- The orchestrator kills its own tmux session on completion via `kill_tmux_session()`, so no manual cleanup is needed.

### Launch command

```bash
tmux new-session -d -s {session_name} \
  "unset CLAUDECODE; python3 \"$CLAUDE_PLUGIN_ROOT/scripts/execute_orchestrator.py\" \
  --config \"$(pwd)/kit_tools/prd/.execution-config.json\""
```

### Fallback (no tmux)

If `which tmux` fails, print a copy-pasteable command for the user to run in a separate terminal window. Use the actual resolved paths (not environment variables) so the command works standalone:

```
python3 "/resolved/plugin/root/scripts/execute_orchestrator.py" \
  --config "/resolved/project/dir/kit_tools/prd/.execution-config.json"
```

### Monitoring commands

After launching, report these to the user (using the actual session name):

| Command | Purpose |
|---------|---------|
| `/kit-tools:execution-status` | Full status report with progress, errors, and actions |
| `tmux attach -t {session_name}` | Attach to watch live output |
| `tail -f kit_tools/EXECUTION_LOG.md` | Follow the execution log |
| `cat kit_tools/prd/.execution-state.json` | Check current state |
| `touch kit_tools/.pause_execution` | Pause after current story |

---

## Branch-per-Attempt Strategy

The orchestrator uses temporary branches for each implementation attempt:

1. **Before attempt:** Create `[feature-branch]-[story-id]-attempt-[N]` from the feature branch
2. **Implementation runs** on the attempt branch
3. **If PASS:** Merge attempt branch into feature branch, delete attempt branch
4. **If FAIL:** Capture diff for retry context, delete attempt branch, retry on new branch

This replaces the old `git reset --hard` + `git clean -fd` approach, preserving:
- Clean feature branch history
- Diff context for retries
- No risk of losing tracking files
