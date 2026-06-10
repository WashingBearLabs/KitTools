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
**Creates (autonomous/guarded):** an isolated git worktree under `~/.kit/worktrees/<project-id>/<epic>/` and a registry entry in `.kit/executions/<epic>.json` (main checkout). The orchestrator runs in the worktree; your main checkout is left untouched.
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
- **A.** Execute all remaining specs (recommended)
- **B.** Execute just one specific spec (ask which)
- **C.** Cancel

> **Pause behavior is determined by mode, not by this choice.** Supervised mode always pauses between specs (the user is reviewing in-session). Autonomous and guarded modes never pause between specs — they run continuously. The `epic_pause_between_specs` config field must match the mode: `true` for supervised, `false` for autonomous/guarded.

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

- **A. Create PR** (recommended) — Push branch, create GitHub PR for review. **Needs a remote + authenticated `gh`.**
- **B. Merge** — For worktree (autonomous/guarded) executions this is a **server-side merge** (push → `gh pr merge`), because the orchestrator can't safely check out the integration branch in its worktree. **It needs a remote + `gh`.** Blocked if validation finds critical issues.
- **C. None** — Leave the branch as-is, clean up tmux only. The user merges/PRs it themselves later.

Store as `completion_strategy` in `.execution-config.json`: `"pr"`, `"merge"`, or `"none"`. Default: `"pr"`.

> **Local-only / no GitHub?** Both `pr` and worktree-`merge` require a remote + `gh`. If the project has no remote, they degrade to "branch pushed/left for manual merge" — which strands a novice. For a purely local repo, prefer **`none`**, and merge from your own checkout afterward (`git merge <epic-branch>`), or use `/kit-tools:complete-implementation` which can guide the merge. (Offline auto-merge into your live checkout is intentionally *not* done — that's the contamination worktree isolation prevents.)

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

**Git readiness (hard gate — check first).** Autonomous/guarded execution creates branches and worktrees off the integration branch, so before anything else:
- `git rev-parse --git-dir` must succeed. If it fails, **stop** and tell the user this isn't a git repository — run `/kit-tools:init-project` (which can initialize one on `main`) or `git init` first. Don't attempt to launch; the orchestrator would just abort.
- There must be at least one commit (`git rev-parse HEAD` succeeds) — a branch with no commits can't be branched into a worktree. If there are none, tell the user to make an initial commit.
- Resolve the integration branch: `git symbolic-ref --short refs/remotes/origin/HEAD 2>/dev/null` (remote default) else a local `main`/`master`. KitTools uses this automatically; just report it so the user knows what the epic branches from and merges into.

Then run these checks and report pass/fail for each:

1. **Session readiness** — `session_ready: true` in frontmatter
2. **Dependency check** — `depends_on` feature specs archived
3. **Specs committed** — The autonomous/guarded worktree is created from committed `main`, so uncommitted spec/doc edits won't reach it. **Supervised mode:** require a clean tree (`git status --porcelain` empty) as before, since it runs in the main checkout. **Autonomous/guarded mode:** the main checkout no longer needs to be clean (the orchestrator runs in a separate worktree), but the selected `epic-*.md` / `feature-*.md` and the `kit_tools/` context docs **must be committed** — warn and offer to commit if `git status --porcelain` shows uncommitted changes to those files.
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

## Step 4: Working Directory & Branch Setup

Branch naming (all modes):
- **Epic feature spec:** Branch `epic/[epic-name]`
- **Standalone feature spec (fallback):** Branch `feature/[feature-name]`

The *working directory* depends on mode.

### Supervised mode — main checkout (unchanged)

Supervised execution runs in **this** session — you are the single writer — so it works directly in the main checkout, as before. Create the branch new (`git checkout -b epic/[name] main`) or check out the existing branch. Skip the rest of this step.

### Autonomous / Guarded mode — isolated worktree

Autonomous and guarded modes spawn a background orchestrator: a **second writer** in the repo. Sharing the user's live directory is exactly what caused commit contamination (unrelated untracked files scooped into a commit) and checkout collisions. So the orchestrator runs in its own **git worktree**.

The deterministic git/registry mechanics (resolve main → `git worktree add` → symlink secrets → register) are done in **one tested command**, `registry.py provision-worktree`, so this skill doesn't orchestrate them through fragile multi-step shell. The only parts that stay here are the genuinely project-specific ones: reading the contract and the **echo-and-confirm gate** for bootstrap commands.

0. **Retrofit safety (pre-2.6.0 projects).** Before anything, make sure this repo has the worktree-isolation furniture — a project that predates 2.6.0 won't:
   - **Ensure `.kit/` is gitignored** (silent, non-negotiable — otherwise a `git add -A` could commit the registry):
     ```bash
     python3 "$CLAUDE_PLUGIN_ROOT/scripts/orchestrator/registry.py" ensure-gitignore
     ```
     If it reports `modified: true`, mention you added the KitTools `.gitignore` block. If `untracked` is non-empty, mention you untracked stale run artifacts (e.g. a previously-committed `EXECUTION_LOG.md`) — a tracked, mid-run-rewritten log is the dirty-tree trigger behind the silent-merge data loss, so this is a real fix, not cosmetic.
   - **If `kit_tools/worktree.yaml` is missing,** offer to scaffold it from `$CLAUDE_PLUGIN_ROOT/templates/worktree.yaml` (or point the user to re-run `/kit-tools:init-project`). Don't silently proceed with no contract on a project that clearly has dependencies.

1. **Read the contract** `kit_tools/worktree.yaml` for `root`, `env_bootstrap`, `env_link`, `path_links`. If it's still missing after step 0, use empty values and the default root. Let `<key>` = the epic name (or feature name in standalone fallback).

   **⚠️ Dependency reality check.** A fresh worktree does **not** inherit gitignored files — `.venv`, `node_modules`, build outputs are absent. If `env_bootstrap` is **empty** *and* the repo has a dependency manifest (`package.json`, `pyproject.toml`, `requirements.txt`, `Cargo.toml`, `go.mod`, `Gemfile`, …), the worktree won't have installed dependencies and **verification tests will fail with import/module errors**. Warn the user and recommend they add the install command(s) to `env_bootstrap` (e.g. `uv sync`, `npm install` — KitTools is language-agnostic, so the command is theirs to specify). Ask whether to proceed anyway (fine for dependency-free projects or vendored deps).

   **⚠️ Local path-dependency check.** If a manifest declares a **local sibling dependency** (e.g. `pyproject.toml` `path = "../Roots"`, a pnpm/yarn workspace pointing at `../shared`, a Cargo `path = "../crate"`), a fresh worktree has no sibling to resolve it against and the install fails. Add those sibling paths to `path_links` in `kit_tools/worktree.yaml` (e.g. `path_links: ["../Roots"]`) — provisioning symlinks them at the worktree's matching relative path, portably.

2. **Derive the tmux session name** now: `kit-exec-<key>`. Check for a collision — `tmux has-session -t kit-exec-<key> 2>/dev/null`; if it exists, **do NOT kill it** (another execution may own it) — append a suffix (`-2`) or ask the user. You'll pass the final name to provisioning so the registry record carries it.

3. **Echo & confirm `env_bootstrap` — SECURITY GATE.** If `env_bootstrap` is non-empty, those commands run shell in the new worktree. Because the contract is committed (PR-mutable), surface them before anything runs:
   > These bootstrap commands from `kit_tools/worktree.yaml` will run in the new worktree:
   >   - `<command 1>`
   >   - `<command 2>`
   - **Guarded:** require explicit confirmation before proceeding.
   - **Autonomous:** log the exact commands prominently to `EXECUTION_LOG.md` and proceed (trusted contract, but never run hidden).

4. **Provision the worktree** — one call creates the worktree (new branch or resume), symlinks each `env_link` secret (copy-fallback where unavailable) and each `path_links` sibling, and registers the execution:
   ```bash
   python3 "$CLAUDE_PLUGIN_ROOT/scripts/orchestrator/registry.py" provision-worktree \
     "<key>" --branch "epic/<key>" --mode "<autonomous|guarded>" --tmux "kit-exec-<key>" \
     [--root "<contract root>"] [--link ".env" --link ".env.vault"] \
     [--link-path "../Roots" --link-path "../shared"]
   ```
   Pass one `--link` per `env_link` entry and one `--link-path` per `path_links` entry from the contract. It prints JSON: `{worktree, branch, created, linked, copied, skipped, path_linked, path_skipped, registered, messages}`. **Read the `worktree` value from that JSON and use it as a literal absolute path in every later command** (do not rely on a shell variable surviving between commands — it won't). If `created` is `false` (e.g. the branch is already checked out in another worktree → a live execution), **stop and report** the `messages`; don't force. If any `path_skipped` entries appear, warn that those sibling deps weren't found and the install may fail.

5. **Bootstrap env:** run each confirmed `env_bootstrap` command with cwd = the worktree path from step 4, in order, stopping at the first failure. On failure, warn that the worktree may not be runnable (verification could fail) and ask whether to continue. (Provisioning records `env_link` in the registry so teardown/close-session can scrub copied secrets later — a no-op for symlinks.)

> From here on the orchestrator's working directory is the provisioned worktree. The user keeps working in the main checkout, undisturbed, and finds the execution via the `.kit/` registry.

**Legacy / in-flight executions:** if `.execution-state.json` shows `status: running` but there is **no** registry entry (`registry.py get <key>` returns nothing), this is a pre-worktree execution started by an older KitTools. Do **not** launch a second one — report it and let it finish (or have the user stop it) before starting a worktree-isolated run.

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

> The worktree was created in Step 4. The config below is written **into the worktree** (`<worktree>/kit_tools/specs/.execution-config.json`) and its `project_dir` points there, so the orchestrator operates entirely inside the worktree.

> Use the **literal absolute worktree path** from Step 4's `provision-worktree` JSON (shown as `<worktree>` below) and the main checkout from `resolve-main` (`<main>`). Don't rely on shell variables persisting between commands.

1. Write `.execution-config.json` using a Python inline script that reads the agent templates via Python file I/O — **never use shell heredocs or `$(cat ...)` substitution to embed template content** (single-quoted heredocs suppress expansion; double-quoted heredocs break on special characters). Pass the script `<worktree>` (as `project_dir`) and `<main>` (as `main_repo`); it writes the config into the worktree. Registration already happened in Step 4 (provision-worktree). The tmux session name (step 3) must match what you passed to `--tmux` at provision time. See REFERENCE.md for the schema and creation pattern.
2. Check for tmux: `which tmux`
3. **tmux session name:** reuse the `kit-exec-<key>` name you chose and passed to `provision-worktree --tmux` in Step 4 (collision already handled there). Set it as `tmux_session` in the config so it matches the registry record.
4. **If tmux available:** Launch the orchestrator in a detached tmux session whose working directory is the worktree (`-c <worktree>`):
   ```bash
   tmux new-session -d -s {session_name} -c "<worktree>" \
     "unset CLAUDECODE; python3 \"$CLAUDE_PLUGIN_ROOT/scripts/execute_orchestrator.py\" \
     --config \"<worktree>/kit_tools/specs/.execution-config.json\""
   ```
   The orchestrator kills its own tmux session on completion. Progress is reported to the parent Claude session via file-based notifications (surfaced on the user's next prompt).
5. **If no tmux:** Print the command for the user to run in a separate terminal (use the resolved absolute worktree path):
   ```
   Run this in a separate terminal window:

   cd "<worktree_path>" && \
   python3 "<plugin_root>/scripts/execute_orchestrator.py" \
     --config "<worktree_path>/kit_tools/specs/.execution-config.json"
   ```
6. Report monitoring commands. The state/log/pause files live in the worktree, so prefer the registry-resolved status skill; print absolute worktree paths for the raw commands:
   - `/kit-tools:execution-status` — check progress, errors, and available actions (resolves the worktree via the registry — run from anywhere)
   - `tmux attach -t {session_name}` — attach to watch live output
   - `tail -f "<worktree_path>/kit_tools/EXECUTION_LOG.md"` — follow the execution log
   - `cat "<worktree_path>/kit_tools/specs/.execution-state.json"` — check current state
   - `touch "<worktree_path>/kit_tools/.pause_execution"` — pause after current story
7. **If `monitor: true` in config:** Set up the supervisor loop using CronCreate:
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
