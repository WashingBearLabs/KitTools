# Execute Epic — Reference

Detailed formats, schemas, and examples for the execute-epic workflow. Read this for edge cases and detailed field descriptions.

---

## Execution Config Schema

### Standalone Feature Spec (legacy/fallback path)

Used when no `epic-*.md` is found and a feature spec is selected directly. This is a backwards-compatibility path — epic config is now standard.

```json
{
  "spec_path": "kit_tools/specs/feature-auth.md",
  "project_dir": "/absolute/path/to/project",
  "branch_name": "feature/auth",
  "feature_name": "auth",
  "mode": "autonomous",
  "max_retries": null,
  "tmux_session": "kit-exec-auth",
  "completion_strategy": "pr",
  "implementer_template": "... raw story-implementer.md content ...",
  "verifier_template": "... raw story-verifier.md content ...",
  "project_context": {
    "synopsis": "kit_tools/SYNOPSIS.md",
    "code_arch": "kit_tools/arch/CODE_ARCH.md",
    "conventions": "kit_tools/docs/CONVENTIONS.md",
    "gotchas": "kit_tools/docs/GOTCHAS.md",
    "spec_overview": "... feature spec overview section ..."
  }
}
```

### Epic (multiple feature specs in sequence)

This is the standard path. Derived from the selected `epic-*.md` wrapper.

```json
{
  "project_dir": "/absolute/path/to/project",
  "branch_name": "epic/arxiv",
  "mode": "autonomous",
  "max_retries": null,
  "tmux_session": "kit-exec-arxiv",
  "completion_strategy": "pr",
  "implementer_template": "... raw story-implementer.md content ...",
  "verifier_template": "... raw story-verifier.md content ...",
  "project_context": {
    "synopsis": "kit_tools/SYNOPSIS.md",
    "code_arch": "kit_tools/arch/CODE_ARCH.md",
    "conventions": "kit_tools/docs/CONVENTIONS.md",
    "gotchas": "kit_tools/docs/GOTCHAS.md",
    "spec_overview": "... feature spec overview section ..."
  },
  "epic_name": "arxiv",
  "epic_pause_between_specs": true,
  "epic_specs": [
    {
      "spec_path": "/abs/path/kit_tools/specs/feature-arxiv-source.md",
      "feature_name": "arxiv-source",
      "epic_seq": 1,
      "epic_final": false
    },
    {
      "spec_path": "/abs/path/kit_tools/specs/feature-arxiv-api.md",
      "feature_name": "arxiv-api",
      "epic_seq": 2,
      "epic_final": false
    },
    {
      "spec_path": "/abs/path/kit_tools/specs/feature-arxiv-ui.md",
      "feature_name": "arxiv-ui",
      "epic_seq": 3,
      "epic_final": true
    }
  ]
}
```

When `epic_specs` is present, the orchestrator runs in epic mode. When absent, it runs in single-feature-spec mode. Exclude already-completed/archived feature specs from `epic_specs`.

`completion_strategy` controls post-execution behavior: `"pr"` (push + create GitHub PR, recommended), `"merge"` (auto-merge to main, blocked if validation finds critical issues), or `"none"` (leave branch as-is). Default: `"pr"`.

---

## Config Creation Pattern

**Always use Python to create `.execution-config.json`.** Never use shell heredocs or `$(cat ...)` to embed template content — single-quoted heredocs suppress command substitution entirely, and double-quoted heredocs break on backslashes, backticks, and `$` signs in the template files.

The correct approach reads agent templates via Python file I/O:

```python
import json, os, sys

plugin_root = sys.argv[1]   # passed as first argument from the skill
project_dir = sys.argv[2]   # absolute path to the project

with open(f"{plugin_root}/agents/story-implementer.md") as f:
    impl_template = f.read()
with open(f"{plugin_root}/agents/story-verifier.md") as f:
    verif_template = f.read()

config = {
    # --- fill remaining fields from skill context ---
    "project_dir": project_dir,
    "mode": "autonomous",           # or "guarded"
    "max_retries": None,
    "tmux_session": "kit-exec-<name>",
    "completion_strategy": "pr",
    "implementer_template": impl_template,
    "verifier_template": verif_template,
    "project_context": {
        "synopsis": "kit_tools/SYNOPSIS.md",
        "code_arch": "kit_tools/arch/CODE_ARCH.md",
        "conventions": "kit_tools/docs/CONVENTIONS.md",
        "gotchas": "kit_tools/docs/GOTCHAS.md",
        "spec_overview": "... inline overview text ..."
    },
    # epic fields (omit for standalone):
    # "epic_name": "...",
    # "epic_pause_between_specs": True,
    # "epic_specs": [...]
}

output_path = f"{project_dir}/kit_tools/specs/.execution-config.json"
with open(output_path, "w") as f:
    json.dump(config, f, indent=2)

print(f"Config written to {output_path}")
```

**How to invoke from the skill:**

Write the script to a temp file, then execute it — avoid inline `-c` strings for multi-line scripts:

```bash
cat > /tmp/kit_write_config.py << 'PYEOF'
<script content — safe because PYEOF wraps Python source, not file contents>
PYEOF
python3 /tmp/kit_write_config.py "$CLAUDE_PLUGIN_ROOT" "$(pwd)"
rm /tmp/kit_write_config.py
```

The critical constraint is that `implementer_template` and `verifier_template` are populated by Python `open()` calls inside the script, not by shell substitution before the script runs.

---

## Execution State Schema

**Important:** For autonomous/guarded mode, the skill must NOT pre-create `.execution-state.json`. The orchestrator creates it with the correct schema on first run. Pre-creating state with the wrong schema causes crashes. Only create state for supervised mode (single-spec only).

### Single Feature Spec State

Created by the orchestrator's `load_or_create_state()`:

```json
{
  "spec": "feature-auth.md",
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

### Epic State

Created by the orchestrator's `load_or_create_epic_state()`:

```json
{
  "epic": "arxiv",
  "branch": "epic/arxiv",
  "mode": "autonomous",
  "max_retries": null,
  "started_at": "2026-02-06T10:30:00Z",
  "updated_at": "2026-02-06T10:30:00Z",
  "status": "running",
  "current_spec": null,
  "specs": {},
  "sessions": {
    "total": 0,
    "implementation": 0,
    "verification": 0,
    "validation": 0
  }
}
```

Key differences from single-spec: `epic` instead of `spec`, `specs` dict instead of `stories`, `current_spec` tracking field. The orchestrator populates `specs[basename]` entries as each feature spec starts.

Note: The orchestrator also tracks `token_estimates` at the top level (rough char/4 approximation), added via `setdefault` during execution. This field is not pre-created.

---

## Placeholder Token Reference

These tokens are used in the agent templates and interpolated by this skill (supervised) or the orchestrator (autonomous/guarded):

| Token | Source |
|-------|--------|
| `{{STORY_ID}}` | Story ID (e.g., "US-003") |
| `{{STORY_TITLE}}` | Story title from feature spec |
| `{{STORY_DESCRIPTION}}` | Full story description |
| `{{IMPLEMENTATION_HINTS}}` | Per-story hints from planning (or fallback message) |
| `{{ACCEPTANCE_CRITERIA}}` | Checkbox list from feature spec |
| `{{FEATURE}}` | Feature name from feature spec frontmatter |
| `{{SPEC_OVERVIEW}}` | Overview + goals + tech considerations + out of scope |
| `{{SYNOPSIS_PATH}}` | Path to SYNOPSIS.md |
| `{{CODE_ARCH_PATH}}` | Path to CODE_ARCH.md |
| `{{CONVENTIONS_PATH}}` | Path to CONVENTIONS.md |
| `{{GOTCHAS_PATH}}` | Path to GOTCHAS.md |
| `{{PRIOR_LEARNINGS}}` | Learnings from completed stories (pruned) |
| `{{RETRY_CONTEXT}}` | Empty on first attempt; failure details on retry |
| `{{PREVIOUS_ATTEMPT_DIFF}}` | Git diff from last failed attempt (for retries) |
| `{{DIFF_STAT}}` | `git diff --stat` output showing scale of changes (verifier only) |
| `{{DIFF_CONTENT}}` | Inline diff content, truncated at 20KB (verifier only) |
| `{{FILES_CHANGED}}` | Files changed from git diff (verifier only) |
| `{{SPEC_PATH}}` | Path to the feature spec file for cross-reference (verifier only) |
| `{{TEST_COMMAND}}` | Auto-detected test command or skip instruction (verifier only) |
| `{{RESULT_FILE_PATH}}` | Path where agent should write its JSON result |

---

## Epic Flow Details

### Epic selection

Check `kit_tools/specs/` for `epic-*.md` files. Each epic wrapper contains a Decomposition table listing the ordered feature specs. Read the wrapper to get:

1. Epic name and description
2. Ordered list of feature specs with `epic_seq`
3. Which specs are already completed (check `kit_tools/specs/archive/` for archived copies)

Present the list with completion status so the user can choose an epic to execute.

### Epic user options

- **A. Execute all remaining, pause between each** — Sets `epic_pause_between_specs: true`. Pauses after each feature spec (validate + tag + archive).
- **B. Execute all remaining non-stop** — No stops between feature specs.
- **C. Execute just one specific spec** — Standalone on the `epic/[name]` branch.

### Epic orchestrator behavior

The orchestrator chains feature spec execution:
1. Execute all stories in feature spec N
2. Validate feature spec N
3. Tag checkpoint: `[epic-name]/[feature-name]-complete`
4. Archive feature spec N (update frontmatter, move to archive/)
5. Commit: `chore([epic-name]): complete [feature-name]`
6. (Optional: pause between feature specs)
7. Move to feature spec N+1

---

## Pre-flight Check Details

### 1. Session readiness
Read the feature spec frontmatter. Check for `session_ready: true`.
- If `session_ready: false`: Warn and ask to continue anyway.
- If field missing: Proceed with a note.

### 2. Dependency check
Read `depends_on` from feature spec frontmatter. For each dependency:
- Check if a completed feature spec exists in `kit_tools/specs/archive/` (check both `feature-[dep].md` and `prd-[dep].md` for backwards compatibility)
- If dependencies not met: Warn with specific missing deps, ask to continue.

### 3. Clean working tree
Run `git status --porcelain` via Bash.
- If output is non-empty: Stop and ask user to commit or stash changes first.

### 4. Uncompleted stories exist
Parse feature spec for stories with unchecked criteria.
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

### 7. Dependency gate (epic feature specs)
For feature specs with an `epic` field: this is a **hard gate**.
- All feature specs listed in `depends_on` **must** be archived in `kit_tools/specs/archive/`
- If any dependency is not archived, **block execution**

For standalone feature specs (no `epic` field): soft warning only.

---

## Supervised Mode Details

For each uncompleted story (in feature spec order):

1. **Read agent templates:** Read `$CLAUDE_PLUGIN_ROOT/agents/story-implementer.md`, interpolate placeholders
2. **Spawn implementer:** Task tool with `subagent_type: "general-purpose"`, read JSON result file
3. **Gather verifier context:** `git diff --name-only` + `git diff --stat`, detect test command
4. **Read verifier template:** Interpolate with git-sourced file list, diff stat, test command, context paths, and feature spec path
5. **Spawn verifier:** Task tool, read JSON result file
6. **If PASS:** Update feature spec checkboxes (skill/orchestrator handles this after verification), update state, log success, commit
7. **If FAIL:** Log failure, present to user with verifier's notes, ask: retry, adjust, or stop?

> The implementer does NOT self-verify or update feature spec checkboxes. The verifier is the sole quality gate.

---

## Autonomous Launch Details

### Why tmux?

Claude Code prevents running `claude -p` from within an existing Claude session to avoid infinite recursion. Since the orchestrator spawns `claude -p` subprocesses, launching it via `run_in_background` from inside a skill fails. A detached tmux session runs in a completely separate process tree, bypassing this restriction.

### tmux session naming

- **Session name pattern:** `kit-exec-{epic_name}` (e.g., `kit-exec-oauth`, `kit-exec-processing-pipeline`). For fallback single-spec mode: `kit-exec-{feature_name}`.
- The session name is stored in `.execution-config.json` as `tmux_session` so that `execution-status` can find it.
- If the derived session name already exists (`tmux has-session -t {name}`), append a suffix (e.g., `-2`) or ask the user.
- The orchestrator kills its own tmux session on completion via `kill_tmux_session()`, so no manual cleanup is needed.

### Launch command

```bash
tmux new-session -d -s {session_name} \
  "unset CLAUDECODE; python3 \"$CLAUDE_PLUGIN_ROOT/scripts/execute_orchestrator.py\" \
  --config \"$(pwd)/kit_tools/specs/.execution-config.json\""
```

### Fallback (no tmux)

If `which tmux` fails, print a copy-pasteable command for the user to run in a separate terminal window. Use the actual resolved paths (not environment variables) so the command works standalone:

```
python3 "/resolved/plugin/root/scripts/execute_orchestrator.py" \
  --config "/resolved/project/dir/kit_tools/specs/.execution-config.json"
```

### Monitoring commands

After launching, report these to the user (using the actual session name):

| Command | Purpose |
|---------|---------|
| `/kit-tools:execution-status` | Full status report with progress, errors, and actions |
| `tmux attach -t {session_name}` | Attach to watch live output |
| `tail -f kit_tools/EXECUTION_LOG.md` | Follow the execution log |
| `cat kit_tools/specs/.execution-state.json` | Check current state |
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
