# Changelog

All notable changes to kit-tools will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.4.2] - 2026-04-24

### Added

- **KitTools commit signing** — Commits created by KitTools agents (story-implementer, feature-fixer) during orchestration now include a `Co-Authored-By: KitTools + Claude` trailer, distinguishing KitTools-originated commits from standard Claude Code commits.

## [2.4.1] - 2026-04-24

### Fixed

- **Dirty-tree self-block on resume** — The orchestrator writes a run header to `EXECUTION_LOG.md` after the clean-worktree check passes, but before story execution begins. If the orchestrator then crashes (timeout, error, killed session), the log is left dirty and every subsequent relaunch fails the dirty-worktree check. Fixed by committing the log header immediately after writing it in both `run_epic()` and `run_single_spec()`, closing the dirty-tree window.

### Added

- **Hybrid model escalation** — New `escalation` model role in `DEFAULT_MODEL_CONFIG` (defaults to `opus`). On retry (`attempt > 1`) for specs marked `size: L` or `size: XL`, the implementation session uses the escalation model instead of the default implementer (Sonnet). First attempt is always Sonnet — cheap exploration that produces learnings. Retry gets Opus for stories where the context is too large for Sonnet to process within the timeout.
- **`size:` frontmatter field** — Feature spec template now includes `size:` in frontmatter (S/M/L/XL). Controls both session timeouts (existing) and model escalation on retry (new). Added to the frontmatter field reference in plan-epic.

### Changed

- **Story sizing raised to 5–7 criteria** — Sweet spot raised from 3–5 to 5–7 acceptance criteria per story across the story-quality-reviewer agent, plan-epic skill, plan-epic reference, and feature spec template. The old 3–5 range caused planners to drop criteria to fit, producing under-specified stories that passed validation but failed execution. The new guidance: more stories with well-defined criteria is always better than fewer stories with compressed scope.
- **Story-quality-reviewer hard ceilings** — Two new critical (execution-blocking) triggers: more than 10 acceptance criteria, or spanning 3+ architectural layers. Previously all oversized stories were warnings (`needs-work`), meaning they could proceed to execution and time out. Stories with 24 criteria (observed in production runs) now hard-block at validation.
- **Plan-epic sizing step** — Step 9 (Final scope check) now includes guidance for setting `size:` frontmatter based on spec complexity: S for simple single-layer specs, M as default, L for integration-heavy or verbose-domain specs, XL for cross-cutting concerns.

## [2.4.0] - 2026-04-17

Foundation refactor. 2.4.0 bundles a deep audit of the whole plugin: hardening, architectural cleanup, consistency across agents, and a full decomposition of the orchestrator. No breaking changes to the user-visible workflow — skills you invoke still behave the same, but the internals are substantially more robust and easier to evolve.

### Added

- **Unified Finding Schema for review agents** — New `agents/FINDING_SCHEMA.md` defines a single canonical shape (`{review_type, target, overall_verdict, findings[], summary}`) used by every review agent. Skills now parse one format instead of three (`FINDING:/END_FINDING`, `DRIFT:/END_DRIFT`, `VALIDATION_RESULT/ISSUE`). Optional per-agent fields (`confidence`, `evidence`, `trade_offs`) handled as schema extensions.
- **Feature spec frontmatter schema doc** — `templates/specs/SCHEMA.md` is the canonical reference for `feature-*.md` and `epic-*.md` frontmatter: every field, type, validation rule, and example. Referenced from both template files.
- **Model configurability** — Orchestrator now accepts a `model_config` block in `.execution-config.json` with per-role keys: `implementer` (default: sonnet), `verifier` (default: opus), `validator` (default: opus). Overrides merge onto defaults. Surfaces in `/kit-tools:execute-epic` Step 2c as an optional user prompt. The `claude -p` subprocess passes the configured model via `--model`.
- **Structured event logging** — New `kit_tools/.execution-events.jsonl` append-only log with structured events for post-mortem grep/jq. `log_event(config, event_type, severity, **fields)` helper; instrumented at critical failure sites (`orchestrator_crashed`, `abort_not_git_repo`, `abort_dirty_worktree`, `abort_state_corrupt`, `abort_git_recovery_failed`). Complements the human-readable `log()` stdout stream.
- **EXECUTION_LOG.md rotation** — `rotate_execution_log_if_large()` keeps a single `.1` backup when the log exceeds 5 MB. Prevents unbounded growth across resumed runs.
- **State schema versioning** — `.execution-state.json` now carries `schema_version: 1`. Older files without the field are tolerated (upgraded on next save); newer-than-supported is a hard abort with explicit remediation. `StateCorrupt` exception + `_validate_state()` catch malformed files before they cause downstream crashes.
- **Git recovery detection** — `check_git_clean_recovery()` + `GitRecoveryFailed` exception surface when `git merge --abort` or `git revert` leaves the repo stuck in MERGING/REVERTING/CHERRY-PICKING/REBASING state. Uses `git rev-parse --git-dir` so it works correctly inside linked worktrees.
- **Clean-worktree precondition** — Orchestrator now verifies `is_git_repo()` + `verify_clean_worktree()` at startup before creating any branches. Aborts with a clear error if the worktree has uncommitted changes or isn't a git repo at all.
- **Vision review split** — `vision-reviewer` (250 LOC, three modes) replaced by three focused agents: `vision-completionist-reviewer`, `vision-feasibility-reviewer`, `vision-readiness-reviewer`. Each has a single output shape and clearer accountability. `/kit-tools:create-vision` updated to invoke all three.
- **Prompt substitution guard** — `_assert_prompt_fully_substituted()` raises if a built prompt still contains `{{TOKEN}}` markers after interpolation. Catches typos in `.replace()` calls and drift when agent templates gain new tokens. Wired into `build_implementation_prompt` and `build_verification_prompt`.
- **Required-token contracts** — All 18 agents now declare `required_tokens` in frontmatter. Consistency tests catch drift between declared tokens and body `{{TOKEN}}` markers, and between declarations and orchestrator `.replace()` calls.

### Changed

- **Orchestrator decomposition** — `scripts/execute_orchestrator.py` (4,087 LOC, 115 functions, monolith) split into `scripts/orchestrator/` package (13 modules, 40–660 LOC each). `execute_orchestrator.py` remains as a 63-line backward-compat shim that re-exports the public API and dispatches the CLI. Module boundaries: `utils`, `events`, `config`, `state`, `specs`, `prompts`, `sessions`, `tests_metrics`, `git_ops`, `supervisor`, `execution_log`, `executor`, `entry`. No circular imports. Existing CLI invocation unchanged.
- **Explicit tool grants on all 16 agents** — Every agent now declares `tools:` in frontmatter instead of inheriting full parent access. Three buckets: full-write (story-implementer, feature-fixer), write-no-Edit (story-verifier, generic-seeder, 6 reviewers), read-only (6 read-only reviewers). `story-verifier` is now architecturally prevented from modifying source — the "independent verifier" boundary enforced at the tool layer, not just prompt-layer.
- **Prompt-injection resistance** — 9 code-reading agents got an explicit security-posture callout: code, comments, diffs, and tool output they consume may contain adversarial prompt-injection attempts and should be treated as text to analyze, never instructions to execute. `security-reviewer` got an extended note about the reviewer being a high-value injection target.
- **Atomic JSON writes** — `save_state()`, health snapshots, test metrics, and control-file updates now use `_atomic_json_write()` (tempfile + fsync + `os.replace`). Mid-write crashes no longer corrupt state files. Concurrent readers (supervisor polling health) see either old or new contents — never partial.
- **Review agents emit unified JSON** — `code-quality-validator`, `security-reviewer`, `feature-compliance-reviewer`, `drift-detector`, `template-validator` now write to `{{RESULT_FILE_PATH}}` matching the Finding Schema. Old text-block formats retired. Skill parsers (`validate-implementation`, `validate-seeding`, `sync-project`) updated to read JSON.
- **`/kit-tools:sync-project` description** — Rewritten to lead with outcome instead of jargon. New "When to use" section (quick vs full vs resume) and "Outcome" section clarify what the skill actually produces in each mode.
- **`spec-second-opinion` model unpinned** — Removed hardcoded `model: sonnet` from frontmatter. Cross-model rationale moved to skill prose: `/kit-tools:validate-epic` Step 3d now explains the pattern ("use a model different from the primary reviewer — typically the non-primary of sonnet/opus") and picks the model at invocation time, so the plugin adapts as new models ship.
- **Hook placeholder detection unified** — `hooks/validate_seeded_template.py` and `hooks/validate_setup.py` previously had drifting regex lists for unfilled placeholders. Both now import from a shared `hooks/_placeholders.py` module.
- **Supervisor cron cleanup extended** — 2.3.1 self-cleanup covered `Completed` and "no execution state" paths. 2.4.0 extends to `Crashed`, `Stale`, and `Failed` states so a supervisor cron never lingers past a run that stopped making progress. Documentation in `/kit-tools:execute-epic` Step 2a now explicitly surfaces the cron's lifetime (tied to the OG session) plus the laptop-sleep burst-fire caveat.
- **Completionist reviewer dimension rename** — The vision completionist's `feasibility` dimension is now `risk_acknowledgment`. Disambiguates from the separate `vision-feasibility-reviewer` which stress-tests actual implementation rather than asking "did the vision mention risks?".
- **`validator` session honors model_config** — Outer session running `/kit-tools:validate-implementation` now passes `--model` from `model_config.validator` (defaults to opus for judgment-heavy aggregation).
- **Null-safe model config merging** — `get_model_config()` treats empty strings, non-string values, and non-dict `model_config` as "use default" rather than passing garbage to `--model`.

### Fixed

- **`proc.wait()` timeout after SIGKILL** — `run_claude_session()` and `run_regression_check()` now bound the final wait at 10 seconds. Previously, if SIGKILL didn't take (zombie, permissions, uninterruptible sleep), the orchestrator could hang indefinitely. Prefers a leaked PID over a hung 24h autonomous run.
- **`git merge --abort` / `git revert --abort` stuck state** — Previously, if the abort itself failed (corrupt index, conflicts during revert), the orchestrator would log a warning and immediately retry the next checkout, which would also fail. Now each abort is followed by a recovery check; stuck state raises `GitRecoveryFailed` with explicit manual-remediation guidance.
- **`_atomic_json_write` bare-filename handling** — Crashed on paths without a directory component (`os.path.dirname("state.json")` returns `""`, `os.makedirs("")` fails). Now falls back to CWD.
- **Worktree indirection in git recovery** — `check_git_clean_recovery()` previously looked at `project_dir/.git/MERGE_HEAD`, which fails in linked worktrees where `.git` is a file, not a directory. Now uses `git rev-parse --git-dir` to follow the indirection.
- **Pre-existing `feature-fixer` Edit access** — Confirmed the agent has Edit via tool inheritance; previously flagged as a latent bug during the audit.
- **Stale `hooks.json` reference in `/kit-tools:init-project`** — The "Do NOT copy" guidance referenced a file that no longer exists in the plugin. Rewritten to describe the actual project-vs-plugin hook-registration rule.

### Removed

- **`/kit-tools:sync-symlinks` skill + `hooks/sync_skill_symlinks.py` hook** — Claude 3.5-era workaround for stale autocomplete symlinks after `/plugin update`. No longer needed; the plugin's skill autodiscovery works correctly without the symlink sync. Hook registration removed from `plugin.json`.
- **`/kit-tools:update-kit-tools` skill** — Workflow pre-dated the standard `/plugin update kit-tools@washingbearlabs` command, which does the same thing natively. Initializing new templates/hooks in an existing project: re-run `/kit-tools:init-project`, choose the merge/partial option.

### Internal

- **Test infrastructure bootstrapped** — `tests/` directory (gitignored per distribution hygiene) with pytest and shared `conftest.py`. 125 tests across 6 suites cover: atomic writes, schema validation, git recovery helpers + worktree behaviour, model config merging, prompt substitution guards + required_tokens consistency for all 18 agents, placeholder detection, structured event logging, and log rotation. Not shipped to users.
- **Consistency tests for agent contracts** — Parametrized tests verify each agent's declared `required_tokens` matches the `{{TOKEN}}` markers in its body, and that every token the orchestrator substitutes is declared by the agents it targets. Future drift fails CI.

## [2.3.1] - 2026-04-10

### Fixed
- **Supervisor cron cleanup** — The supervisor monitoring cron job created by `/kit-tools:execute-epic` now self-cleans when `/kit-tools:execution-status` detects no active execution or a completed state. Previously, the cron kept polling indefinitely after orchestration finished.

## [2.3.0] - 2026-04-06

### Added
- **Supervisor monitoring mode** — Optional `--monitor` flag for autonomous and guarded execution modes. When enabled, the OG Claude session stays active as a supervisor, polling orchestrator health every 30 minutes via CronCreate. The supervisor reads a health snapshot file (`.execution-health.json`) and can write control actions to a control file (`.execution-control.json`) — no system commands needed from the permission-bound session.
- **Health snapshots** — Orchestrator writes `.execution-health.json` after every story attempt with heartbeat timestamp, memory usage, child PIDs, current story, consecutive failures, and completion progress. Supervisor reads this to assess orchestrator health without running system commands.
- **Supervisor control file** — Orchestrator checks `.execution-control.json` between story attempts and executes supervisor instructions: `split_story`, `pause`, `skip_story`, or `abort`. Control file is consumed (deleted) after reading to prevent re-processing.
- **Story splitting** — Supervisor can split oversized stories by writing a `split_story` control action with full story definitions. Orchestrator applies the split to the feature spec, updates execution state, and commits. New stories must use major IDs (US-010, not US-003a).
- **Graduated intervention** — Supervisor follows an escalation path: 1-2 failures → observe, 3+ failures (retries exhausted) → split or correct, intervention fails → pause and escalate to user.
- **24-hour safety net** — Orchestrator self-terminates after 24 hours of continuous execution with a critical notification.
- **Test metrics tracking** — New `kit_tools/testing/test-metrics.json` file tracks per-file test pass/fail counts, durations, timeouts, and last run dates across orchestration runs. Aggregated deterministically by the orchestrator from verifier results and regression checks. Portable JSON — no external dependencies.
- **Verifier: `tests_run` result field** — Verifier result schema extended with a `tests_run` array reporting which test files were executed, pass/fail status, and duration. Fed into test metrics for observability.

### Fixed
- **Orchestrator: orphaned process cleanup on normal exit** — `run_claude_session()` now kills the entire process group after every session completes, not just on timeout. Previously, child processes (pytest, vitest, node workers) spawned by Claude sessions survived after the session exited normally, accumulating across stories and eventually exhausting system memory.
- **Orchestrator: regression check process handling** — `run_regression_check()` rewritten to use `Popen` with `start_new_session=True` instead of `subprocess.run(shell=True)`. Timeout now kills pytest and all its children via process group cleanup instead of only killing the shell wrapper.
- **Orchestrator: graceful process termination** — New `_kill_process_group()` helper sends SIGTERM with a 0.5s grace period before SIGKILL, allowing child processes to clean up instead of being killed immediately.
- **Orchestrator: tmux cleanup timeout** — `kill_tmux_session()` now has a 10s timeout to prevent hanging if tmux is unresponsive.

### Added
- **Test metrics tracking** — New `kit_tools/testing/test-metrics.json` file tracks per-file test pass/fail counts, durations, timeouts, and last run dates across orchestration runs. Aggregated deterministically by the orchestrator from verifier results and regression checks. Portable JSON — no external dependencies.
- **Verifier: `tests_run` result field** — Verifier result schema extended with a `tests_run` array reporting which test files were executed, pass/fail status, and duration. Fed into test metrics for observability.

### Changed
- **Verifier: no more full-suite fallback** — When targeted test detection (T0/T1) finds no matches, the verifier is now instructed to identify and run only relevant tests from the diff rather than falling back to the full test suite. Prevents multi-minute test runs in large codebases during story verification. Broader test coverage is still enforced by the regression check and end-of-epic validation.

## [2.2.2] - 2026-04-04

### Added
- **New Skill: `/kit-tools:optimize-tests`** — Full test suite audit with six dimensions: mapping completeness, stale test detection, coverage overlap, performance profiling, KitTools convention alignment, and suite verification. Produces a structured report with actionable findings.
- **New Agent: `test-optimizer`** — Audits project test suites and produces structured JSON reports. Reports findings but does not modify files.
- **Orchestrator: failure type classification** — New `classify_failure()` function categorizes failures into `TIMEOUT_IMPL`, `TIMEOUT_VERIFY`, `TEST_FAILURE`, `VERDICT_FAIL`, `SESSION_ERROR`, or `UNKNOWN`. Stored in execution state for structured retry context.
- **Orchestrator: structured retry context** — New `build_retry_context()` replaces generic retry messages with failure-type-specific guidance. Timeout failures suggest scope reduction; test failures include the failing test name; verdict failures include per-criterion status.
- **Orchestrator: pre-flight checks** — New `pre_flight_check()` runs before each story's first attempt. Warns about oversized stories (>6 criteria) and test mapping gaps for files referenced in acceptance criteria.
- **Orchestrator: cross-story regression detection** — New `run_regression_check()` runs after story merge. Tests prior stories' changed files via direct subprocess (not a Claude session). On regression: reverts merge, halts execution with critical notification. Capped at 10 prior stories and 30 test files.
- **Orchestrator: learnings persistence across epics** — New JSONL-based persistent learnings file (`kit_tools/.execution-learnings.jsonl`). Up to 10 learnings persisted per execution, 5 injected into future epics. File-locked for concurrent safety, capped at 50 entries.
- **Orchestrator: test mapping gap detection** — New `check_test_mapping_gaps()` warns about changed source files without explicit test_mapping entries. Uses fnmatch for glob pattern matching. Deduplicated across stories within an epic.
- **Verifier: `pass_with_warnings` verdict** — Verifier can now return a third verdict for non-blocking concerns (style, naming, minor optimization). Triggers merge like `pass` but accumulates warnings in execution state for later review.
- **Verifier: `tests_passed` boolean** — Verifier result schema now includes a structured `tests_passed` field for reliable failure classification (replaces prose-scraping heuristic).

### Changed
- **Orchestrator: `detect_related_tests()` rewrite** — Complete rewrite with three-tier matching: T0 (explicit test_mapping), T1 (heuristic). Returns a dict with separate `t0`/`t1` commands instead of a single string. Directory-scoped matching preferred over global `**/` globs. Match caps: 3 for global heuristic, 5 for directory-scoped.
- **Orchestrator: extended source file filter** — `__init__.py`, migration files, Dockerfiles, Makefiles, CI config, and other non-logic files are now excluded from test detection.
- **Orchestrator: adaptive session timeouts** — New `run_claude_session()` timeout parameter with separate `IMPL_SESSION_TIMEOUT` (900s) and `VERIFY_SESSION_TIMEOUT` (600s) defaults. Optional `size: S/M/L/XL` in spec frontmatter scales timeouts.
- **Orchestrator: `update_state_story()` extended** — Now accepts `failure_type`, `warnings`, and `files_changed` parameters for richer execution state.
- **Verifier prompt: tiered test commands** — Test section now presents T0 and T1 commands separately with priority guidance. Full suite labeled as T2 (feature validation only).
- **`spec-completionist-reviewer` agent** — New dimension 5: "Integration & Wiring Completeness" checks for UI gaps, unwired artifacts, cross-layer connection breaks, missing configuration, and scope narrowness.
- **`story-quality-reviewer` agent** — New dimensions: "Anti-Pattern Detection" (vague verbs, compound criteria, unbounded scope) and "Story Ordering" (dependency ordering checks between stories).

## [2.2.1] - 2026-04-03

### Changed
- **`/kit-tools:validate-feature` → `/kit-tools:validate-implementation`** — Renamed to better reflect that this skill validates the implementation (code on a branch), not the feature spec itself. No behavioral changes.
- **`/kit-tools:complete-feature` → `/kit-tools:complete-implementation`** — Renamed for consistency with the epic-forward workflow. No behavioral changes.
- All cross-references updated across skills, agents, hooks, orchestrator, templates, and documentation.

## [2.2.0] - 2026-04-01

### Added
- **New Skill: `/kit-tools:plan-epic`** — Replaces `/kit-tools:plan-feature`. All work is now structured as an epic, even single-spec features. Removes the binary "epic detection" gate in favor of a "scope assessment" step that determines how many feature specs are needed (1 for simple, 2-5+ for complex). Always generates an `epic-*.md` wrapper alongside feature specs.
- **New Skill: `/kit-tools:validate-epic`** — Pre-execution spec validation. Runs four sequential agent reviews on every feature spec in an epic before handing off to `/kit-tools:execute-epic`. Interactive: presents findings after each agent, lets user revise specs and re-run reviews before proceeding. Produces a go/no-go readiness verdict.
- **New Skill: `/kit-tools:execute-epic`** — Replaces `/kit-tools:execute-feature`. Epic-first entry point: selects the epic from `epic-*.md` files, derives execution order from the Decomposition table. Retains all three execution modes (supervised, autonomous, guarded) and backwards compatibility for projects without epic files.
- **New Agent: `spec-completionist-reviewer`** — Reviews a feature spec for completeness: goals with no implementing stories, missing user flows, scope coherence gaps, and vision alignment issues. Writes structured JSON findings.
- **New Agent: `story-quality-reviewer`** — Reviews each user story for size (split recommendations), detail quality (flags vague criteria), ID format (rejects `US-001a`/`US-001b` — orchestrator incompatible), and integration scope (endpoint, auth, errors, data mapping must all be specified). Per-story verdict table in findings.
- **New Agent: `salty-engineer-reviewer`** — Adversarial pre-execution review using GAN-style discriminator thinking. Five lenses: "Yeah But What About" (error/loading/empty/scale states), "That's Not How It Works" (integration depth), "PM Said It Would Be Easy" (scope naivety flags), "Deployment Day Nightmare" (migrations, flags, backfill), and "Who Maintains This" (logging, ops, monitoring). Findings written in direct engineer voice.
- **New Agent: `spec-second-opinion`** — Independent cross-model review using Sonnet. Evaluates architecture decisions, feasibility, over-engineering, and alternative approaches. All alternative and over-engineering findings require explicit trade-off statements. Runs as the 4th review in the validate-epic pipeline.

- **`READ_ME.html`** — Single-file HTML5 documentation page with interactive 8-phase workflow flowchart, skills grid, hooks table, and install guide. Dark theme with phase-colored cards and agent badges.

### Changed
- **`/kit-tools:plan-epic` (formerly `plan-feature`)** — Step 3 "Epic Detection" removed. Replaced with "Scope Assessment & Decomposition" that always produces an `epic-*.md`. Single-spec epics get a minimal wrapper. All feature specs now use `type: epic-child` frontmatter. Step 13 prompts to run `/kit-tools:validate-epic` before execution.
- **`/kit-tools:execute-epic` (formerly `execute-feature`)** — Primary entry point is now epic selection from `epic-*.md` files, not individual feature spec selection. Falls back to direct spec listing for backwards compatibility.
- **`/kit-tools:execution-status`** — Description and body updated to reference `execute-epic`.
- **`/kit-tools:complete-implementation`** — Enhanced learnings capture (Step 3): gotchas → GOTCHAS.md, conventions → CONVENTIONS.md, spec-writing notes → Implementation Notes. Added context-aware next steps and updated Related Skills.
- **`/kit-tools:seed-project`** — Added Next Steps section and Related Skills table for clear handoff to create-vision or plan-epic.
- **`/kit-tools:start-session`** — Added guidance when no feature specs exist: suggests plan-epic or create-vision.
- **`/kit-tools:init-project`**, **`/kit-tools:create-vision`** — Related skill references updated.
- **`agents/story-implementer.md`**, **`agents/story-verifier.md`** — NOTE blocks updated to reference `execute-epic`.
- **`scripts/execute_orchestrator.py`** — Desktop notifications on macOS (osascript) and Linux (notify-send) for story failures, execution completion, crashes, and pauses. Fires automatically for critical/warning severity events.
- **`templates/PRODUCT_VISION.md`**, **`templates/specs/EPIC.md`** — References updated.
- **`README.md`**, **`KITTOOLS_UI_SPEC.md`** — All `plan-feature`/`execute-feature` references updated. `validate-epic` added to skill table and agents table. Repositioned from "documentation framework" to "framework for AI-assisted development."
- **`.claude-plugin/plugin.json`** — Description updated to reflect framework positioning.

### Removed
- **`/kit-tools:plan-feature`** — Replaced by `/kit-tools:plan-epic`
- **`/kit-tools:execute-feature`** — Replaced by `/kit-tools:execute-epic`
- **`/kit-tools:migrate`** — Removed. v1.x → v2.0 migration is no longer supported as a dedicated skill.

## [2.1.4] - 2026-03-18

### Fixed
- **Orphaned subprocess cleanup on timeout** — `run_claude_session()` now uses `Popen` with `start_new_session=True` and kills the entire process group (`os.killpg`) on timeout. Previously, timed-out sessions only killed the direct `claude` child process, leaving grandchild processes (pytest, node, etc.) running indefinitely and consuming CPU.

## [2.1.3] - 2026-03-13

### Changed
- **Smart test scoping** — Story verification now runs only related tests instead of the full suite. Tests are matched by naming convention (e.g., `foo.py` → `test_foo.py`) or explicit `test_mapping` in `TESTING_GUIDE.md`. Full suite runs only at the validate-implementation gate, with quiet flags (`-q --tb=line`, `--silent`, `--reporter=dot`).
- **Test output control** — Agent test runs use quiet flags to suppress per-test PASSED noise while preserving full failure tracebacks. Safety-net `| head -200` caps runaway output without hiding failure details.

## [2.1.2] - 2026-03-11

### Added
- **Inline diff for verifier** — Verifier agent now receives the full diff content inline (up to 20KB), reducing tool calls and speeding up verification. Truncated diffs include a stat summary and instruct the verifier to use the Read tool for full files.
- **Fail-fast test flags** — Verifier test commands now include fail-fast flags for known runners: pytest (`-x`), jest/npm test (`--bail`), vitest (`--bail 1`). The full test suite (without fail-fast) is preserved for validate-implementation.
- **Completion strategy** — New `completion_strategy` config option (`"pr"`, `"merge"`, or `"none"`) controls post-execution behavior. The orchestrator now handles completion directly in Python instead of spawning a `claude -p` session for `/kit-tools:complete-implementation`.
  - `"pr"` (default): pushes branch and creates a GitHub PR via `gh`
  - `"merge"`: auto-merges to main (blocked if validation finds critical issues, falls back to PR)
  - `"none"`: leaves branch as-is
  - All strategies include artifact cleanup and tmux session teardown

### Changed
- **Pre-attempt HEAD capture** — Diff commands for the verifier now use explicit two-dot syntax (`{pre_attempt_head}..HEAD`) instead of three-dot merge-base syntax, eliminating ambiguity in multi-commit scenarios
- **Verifier review instructions** — Step 1 updated from "Read Changed Files" to "Review Changes", reflecting the inline diff workflow
- **`complete-implementation` skill** — Added note that autonomous/guarded mode handles completion via the orchestrator; skill is for manual/supervised use or fallback
- **`execute-feature` skill** — Added Step 2b (completion strategy selection) and pre-flight check 10 (gh auth verification when PR strategy selected)
- **Epic completion** — `run_epic()` no longer spawns a `claude -p` complete-implementation session; uses `complete_feature()` directly

## [2.1.1] - 2026-03-07

### Fixed
- **Epic automation state mismatch** — Skill no longer pre-creates `.execution-state.json` for autonomous/guarded modes. The orchestrator owns state creation with the correct schema (single-spec or epic), preventing schema mismatch crashes when running epics.
- **Epic state schema undocumented** — Added epic state schema to `execute-feature/REFERENCE.md` alongside the single-spec schema
- **Orchestrator crash handler timing** — Crash handler now registers before config load; config parse failures produce notifications instead of silent crashes
- **Leaked attempt branches on crash** — New `cleanup_attempt_branches()` runs at startup; `create_attempt_branch()` handles pre-existing branches from previous crashes
- **Archive spec safety** — `archive_spec()` now writes updated content to archive destination first, removes original only after success (prevents corruption if move fails)
- **Verify session errors unchecked** — Added `is_session_error()` check before reading verification result file (prevents reading stale results from previous stories)
- **Agent JSON output brittleness** — `read_json_result()` now handles markdown fences, preamble text, and trailing commas in agent output
- **Unbounded learnings accumulation** — Per-story learnings capped at 20 at write time (was only pruned to 15 at read time)
- **Scratchpad creation silent failures** — `create_scratchpad.py` now reports failure messages instead of silently swallowing errors
- **Placeholder validation false positives** — `validate_seeded_template.py` uses strict whitelist patterns (`[FILL:`, `[TODO:`, 3+ char ALL_CAPS) instead of broad regex that caught legitimate markdown
- **Checkbox detection inconsistency** — `detect_phase_completion.py` now uses consistent case matching for checked/unchecked boxes; removed stale `prd/` path support
- **Manifest gaps** — Added missing templates to SEED_MANIFEST (BACKLOG, AUDIT_FINDINGS, SESSION_LOG) and SYNC_MANIFEST (MILESTONES, BACKLOG, pattern docs)

### Changed
- **`execute-feature` skill (Step 6)** — State initialization split by mode: autonomous/guarded defer to orchestrator, supervised creates single-spec state directly
- **`execution-status` skill** — Token estimates display conditional on field existence
- **Network retry logic** — Rewrote `run_claude_session()` with clearer flow; explicit network vs non-network error handling
- **Duplicate code extraction** — Extracted `_store_attempt_diff()` helper, replacing 3 duplicate spec_key conditional blocks
- **Template versions normalized** — All 30 templates updated to version `2.0.0`
- **Story quality pre-flight check** — `execute-feature` skill Step 3 now includes story quality validation (vague criteria, under-specified stories)
- **`release-version` skill** — Now checks for template version changes during release

### Removed
- **Dead code** — Removed unused `summarize_diff_for_prompt()` function, unused `shutil` and `Path` imports from orchestrator

## [2.1.0] - 2025-03-04

### Added
- **New Skill: `/kit-tools:create-vision`** — Interactive, iterative product vision definition
  - Guided conversation to capture vision, users, value proposition, success criteria, and feature areas
  - Two-pass AI review: completeness scoring across 6 dimensions, then feasibility assessment
  - Surfaces gaps and suggestions between review rounds for user refinement
  - Produces `kit_tools/PRODUCT_VISION.md` — a singular strategic document per project
- **New Agent: `vision-reviewer.md`** — Reviews Product Vision documents for completeness, feasibility, and clarity
  - Scores across 6 dimensions: target users, value proposition, success criteria, feature areas, constraints, feasibility
  - Two modes: `completeness` (gap detection) and `feasibility` (implementation concerns)
  - Returns structured JSON with per-dimension scores, findings, gotchas, and open questions
- **New Template: `PRODUCT_VISION.md`** — Root-level strategic document (replaces `PRODUCT_BRIEF.md`)
  - Sections: Vision Statement, Target Users & Personas, Value Proposition, Success Criteria, High-Level Feature Areas, Constraints & Assumptions, Open Questions
  - `skip_if: always` — created interactively by `create-vision` skill, not auto-seeded

### Changed
- **`/kit-tools:plan-feature`** — Step 1 now checks for Product Vision instead of Product Briefs
  - Reads `kit_tools/PRODUCT_VISION.md` for strategic context if it exists
  - Suggests `/kit-tools:create-vision` if no vision doc found (non-blocking)
  - Step 12 now updates both `BACKLOG.md` and `MILESTONES.md` with priority confirmation
  - Feature specs use `vision_ref:` instead of `brief:` frontmatter field
- **`/kit-tools:init-project`** — Template list updated: `PRODUCT_VISION.md` replaces `PRODUCT_BRIEF.md`
  - Summary now recommends `create-vision` after seeding
  - Suggested workflow: init → seed → create-vision → plan-feature
- **`/kit-tools:migrate`** — Added vision/brief migration steps (12b–12e)
  - 12b: Creates blank `PRODUCT_VISION.md` if missing
  - 12c: Flags legacy `brief-*.md` files for user review (no auto-delete)
  - 12d: Notes feature specs with `brief:` fields (harmless, recommends `vision_ref:` for new features)
  - 12e: Completeness check for all expected v2.0 files
- **Feature Spec template** — `brief:` frontmatter field replaced with `vision_ref:` (references section in PRODUCT_VISION.md)
- **Epic template** — `brief:` frontmatter field replaced with `vision_ref:`
- **SEED_MANIFEST.json** — Added `PRODUCT_VISION.md` as Tier 1 (24 templates, 5 in Tier 1)
- **SYNC_MANIFEST.json** — Added `PRODUCT_VISION.md` to document tracking (20 documents)

### Removed
- **`templates/specs/PRODUCT_BRIEF.md`** — Replaced by `templates/PRODUCT_VISION.md`

## [2.0.0] - 2026-03-01

### Breaking Changes
- **`kit_tools/prd/` → `kit_tools/specs/`** — The feature specs directory has been renamed. All internal paths, config keys, state keys, and tokens updated to match.
  - Config keys: `prd_path` → `spec_path`, `epic_prds` → `epic_specs`, `epic_pause_between_prds` → `epic_pause_between_specs`
  - State keys: `prd` → `spec`, `prds` → `specs`, `current_prd` → `current_spec`
  - Agent tokens: `{{PRD_OVERVIEW}}` → `{{SPEC_OVERVIEW}}`, `{{PRD_PATH}}` → `{{SPEC_PATH}}`
  - Orchestrator functions: `parse_prd_frontmatter` → `parse_spec_frontmatter`, `parse_stories_from_prd` → `parse_stories_from_spec`, `update_prd_checkboxes` → `update_spec_checkboxes`, `archive_prd` → `archive_spec`, `execute_prd_stories` → `execute_spec_stories`, `run_single_prd` → `run_single_spec`
  - Template directory: `templates/prd/` → `templates/specs/`
- **Run `/kit-tools:migrate` to update existing projects** — The migrate skill has been rewritten to handle the v1.x → v2.0 transition automatically.

### Changed
- **`/kit-tools:migrate` rewritten** — Now handles v1.x → v2.0 migration instead of the defunct dev-tools migration. Covers directory rename, file renames (`prd-*.md` → `feature-*.md`), config/state key migration, hook path updates, and documentation path sweep. All steps are idempotent.
- **`detect_phase_completion` hook** — Now checks both `kit_tools/specs/` and `kit_tools/prd/` paths for backwards compatibility with unmigrated projects.

### Unchanged
- `kit_tools/` top-level directory name
- `feature-*.md` filenames (renamed in v1.7.0)
- Frontmatter field names (`feature`, `status`, `epic`, `epic_seq`, etc.)
- Archive backwards-compat: `check_dependencies_archived()` still checks for `prd-{dep}.md` in archive

## [1.7.0] - 2026-03-01

### Changed
- **Agile Alignment Refactor** — Corrected agile hierarchy throughout the plugin
  - **"PRD" → "Feature Spec"** — What kit-tools called a "PRD" was actually a feature-level spec, not a product-level document. All user-facing references updated.
  - **New: Product Brief** (`brief-*.md`) — Optional strategic planning document for new product areas. Integrated into `plan-feature` as Step 1.
  - **New: Epic files** (`epic-*.md`) — Explicit epic decomposition documents with goal, feature spec table, and completion criteria. Replaces implicit `epic:` frontmatter scanning.
  - **Feature Spec template** (`FEATURE_SPEC.md`) — Replaces `PRODUCT_REQ_DOC.md`. Removes Functional Requirements (FR-X) section and Success Metrics (moved to Product Brief). Renames "Non-Goals" → "Out of Scope". Adds `brief:` and `type:` frontmatter fields.
  - **`MILESTONES.md`** — Replaces `MVP_TODO.md` for milestone tracking
  - **`FEATURE_TODO.md` removed** — Superseded by feature specs since v1.3.0
  - **Generated files** — `prd-[name].md` → `feature-[name].md`
  - **`prd-compliance-reviewer` agent** → `feature-compliance-reviewer` — FR-X coverage check removed
  - **Backwards compatibility** — Orchestrator `check_dependencies_archived()` checks both `feature-*.md` and `prd-*.md` patterns. Internal variable/config key names unchanged.
  - **`/kit-tools:migrate`** — New "Agile Alignment Migration" step renames `prd-*.md` → `feature-*.md`, generates epic files, renames `MVP_TODO.md` → `MILESTONES.md`

## [1.6.6] - 2026-03-01

### Added
- **New Agent: `prd-compliance-reviewer.md`** — Dedicated PRD compliance review agent
  - Checks acceptance criteria coverage, functional requirements, scope creep, and intent alignment
  - Runs as a parallel subagent in validate-implementation (previously inline in the skill session)
  - Standard FINDING output format with `category: compliance`
- **Diff summarization for validators** — Large diffs are now truncated per-file before being passed to validator agents
  - 60KB budget split across files; truncation notice instructs agents to Read full files
  - Agents (code-quality, security, fixer, compliance) include a note about truncated diffs
- **Prompt size guard** — Implementation and verification prompts are trimmed if they exceed 480K chars
  - Intelligently removes prior learnings and previous attempt diffs first
  - Hard-truncate fallback prevents context window blowouts
- **Result schema validation** — Implementation and verification result JSON files are validated on read
  - Implementation: requires `story_id` and valid `status` (complete/partial/failed)
  - Verification: requires valid `verdict` (pass/fail) and `criteria` list
  - Missing optional fields logged as notes instead of causing failures

### Fixed
- **Permanent error classification** — Context/token limit errors now cause immediate failure instead of infinite retries
  - New `SESSION_ERROR_PERMANENT:` prefix for errors matching context/token limit patterns
  - Orchestrator exits with notification instead of wasting retries on unrecoverable errors
- **PRD checkbox false positives** — `update_prd_checkboxes()` now uses `re.sub` with line-start anchoring instead of `str.replace`
  - Prevents matching `- [ ]` inside descriptions or hint text
- **Git operation visibility** — All bare `subprocess.run(["git", ...])` calls replaced with `run_git()` helper
  - Logs warnings on failures (non-fatal) instead of silently ignoring errors
- **Pause hang prevention** — `wait_for_pause_removal()` now has a 24-hour timeout with periodic log reminders
  - Auto-resumes and writes a notification after timeout

### Changed
- **validate-implementation Step 5** — PRD compliance review now runs as a subagent (prd-compliance-reviewer) instead of inline
  - Steps 3, 4, and 5 can all run in parallel
- **validate-implementation/REFERENCE.md** — Added PRD compliance agent interpolation table and large diff handling section

## [1.6.5] - 2026-02-26

### Fixed
- **Nested `claude -p` sessions** — Orchestrator now strips the `CLAUDECODE` environment variable before spawning subprocesses, preventing "cannot be launched inside another Claude Code session" errors
  - `run_claude_session()` passes a clean `env` dict to `subprocess.run`
  - tmux launch command also unsets `CLAUDECODE` as defense-in-depth
- **Orchestrator cleanup on error exits** — All `sys.exit()` paths now properly clean up tmux sessions, commit tracking files, and remove result files
  - Crash handler (`atexit`) kills the tmux session on unexpected exits
  - Guarded mode Ctrl+C, max retries exceeded, and epic dependency failure all run cleanup before exiting
- **Merge conflict handling** — Failed merges of attempt branches now abort cleanly and retry instead of silently marking the story as completed with an orphaned branch
- **Result file cleanup** — `.story-impl-result.json` and `.story-verify-result.json` are now cleaned on all retry paths, not just on success
- **Hook error handling** — All hooks now wrap file I/O in try/except to prevent tracebacks on encoding errors or permission issues
  - `update_doc_timestamps.py`, `create_scratchpad.py`, `remind_scratchpad_before_compact.py`, `sync_skill_symlinks.py`
- **Execution status tmux fallback** — Fixed session name fallback from hardcoded `kit-execute` to `kit-exec-{feature_name}` pattern

### Changed
- **Notifications** — Removed macOS `osascript` notifications; all progress is now reported through file-based notifications surfaced by the `UserPromptSubmit` hook in the parent Claude session
- **tmux lifecycle** — Orchestrator now kills its own tmux session on completion via `kill_tmux_session()`; no more `; echo ...; read` suffix keeping sessions open

### Added
- **Git health check in start-session** — `/kit-tools:start-session` now runs a git status check (branch, uncommitted changes, stash, remote sync, recent commits) before orienting on docs
- **Plugin discoverability** — SYNOPSIS template now includes a KitTools install note so new contributors to a project can find and install the plugin
- **Scratchpad behavior docs** — `checkpoint` and `close-session` skills now document their different scratchpad handling (preserve vs. delete)

## [1.6.4] - 2026-02-23

### Added
- **Execution Notification System** — Two-pronged notifications for autonomous/guarded execution
  - **macOS native alerts** via `osascript` for immediate awareness on completions, failures, crashes, and pauses
  - **`UserPromptSubmit` hook** surfaces batched notifications the next time the user interacts with Claude
  - Nine notification points: story pass, story failure (max retries), single-PRD complete, validation pause, epic PRD complete, between-PRD pause, all epic PRDs complete, dependency blocked, crash
  - **Crash handler** (`atexit` + `SIGTERM`) detects unexpected orchestrator exits, sets state to `crashed`, writes notification, and sends OS alert
- **Crashed status** — `/kit-tools:execution-status` now recognizes `crashed` state with resume/reset actions

### Changed
- **Repo distribution hygiene** — Removed test files and dev dependencies from the distributed plugin
  - `tests/` directory and `.pytest_cache/` no longer tracked by git
  - `pytest` removed from `requirements.txt` (dev-only dependency)
  - Added `tests/` and `kit_tools/.execution-notifications` to `.gitignore`

## [1.6.3] - 2026-02-23

### Fixed
- **Unique tmux session names** — Autonomous execution now uses `kit-exec-{feature_name}` instead of a hardcoded `kit-execute` session name
  - Prevents collisions when running multiple projects concurrently
  - Never kills existing tmux sessions — checks for name conflicts and appends a suffix if needed
  - Session name stored in `.execution-config.json` so `execution-status` can find it
  - Falls back to `kit-execute` for older runs missing the field

## [1.6.2] - 2026-02-23

### Added
- **New Skill: `/kit-tools:execution-status`** — Check progress of autonomous execution
  - Shows completion percentage, per-story status table, session stats
  - Detects stale state (orchestrator crashed/exited)
  - Offers contextual actions: pause, resume, attach to tmux, retry

## [1.6.1] - 2026-02-23

### Fixed
- **Autonomous execution launch** — Orchestrator now launches in a detached tmux session instead of `run_in_background`
  - Fixes nested `claude -p` calls being blocked when launched from inside a Claude session
  - Fallback: prints a copy-pasteable command if tmux is not installed
  - Pre-flight check #8 verifies tmux availability for autonomous/guarded modes
  - Monitoring commands reported after launch (tmux attach, tail log, check state, pause)

## [1.6.0] - 2026-02-22

### Added
- **Unit Test Suite** — 72 tests for the execute orchestrator (`tests/test_orchestrator.py`)
  - Covers PRD parsing, frontmatter extraction, story parsing with hints, result reading, prompt building, test command detection
  - PyYAML and pytest added as dependencies (`requirements.txt`)
- **File-Based Agent Results** — Agents write structured JSON result files instead of stdout parsing
  - Implementation: `.story-impl-result.json` with status, criteria met, files changed, learnings
  - Verification: `.story-verify-result.json` with verdict, criteria details, recommendations
  - Eliminates ~33% false failure rate from regex parsing of LLM output
- **Branch-per-Attempt Strategy** — Each implementation attempt runs on a temporary branch
  - Creates `[feature-branch]-[story-id]-attempt-[N]` branches
  - Successful attempts merge into the feature branch; failed attempts are deleted
  - Replaces destructive `git reset --hard` + `git clean -fd`
- **Patch-Based Retry Context** — Failed attempt diffs captured and included in retry prompts
  - Shows the implementer what was tried before so it can take a different approach
- **Token Estimation** — Per-session input/output token tracking (~4 chars/token)
  - Logged per session and accumulated in execution state
- **Auto-Detect Test Command** — `detect_test_command()` finds the project's test runner
  - Checks: `package.json`, `pyproject.toml`, `pytest.ini`, `Makefile`, `TESTING_GUIDE.md`
  - Skips npm default "no test specified" placeholder
- **Test Execution in Validation** — `/kit-tools:validate-implementation` Step 4b runs the test suite
  - Failed tests logged as critical findings; passing tests noted in summary
  - Graceful fallback if no test command detected
- **Auto-Injected Test Criteria** — `/kit-tools:plan-feature` adds test criteria to every code story
  - "Tests written/updated for new functionality" and "Full test suite passes" auto-appended
  - Doc/config-only stories exempt
- **Implementation Hints** — Per-story hints flow from planning to implementation
  - `plan-feature` generates hints during refinement (key files, patterns, gotchas)
  - `parse_stories_from_prd()` extracts `**Implementation Hints:**` blocks
  - Implementer agent receives hints to reduce exploration time
- **Pause on Critical Findings** — Autonomous execution pauses when validation finds critical issues
  - Creates `.pause_execution` file referencing `AUDIT_FINDINGS.md`
  - Resumes when file is removed after review
  - Only in autonomous mode; supervised/guarded modes just report

### Changed
- **YAML Parsing** — Replaced hand-rolled frontmatter parser with PyYAML (`yaml.safe_load()`)
  - Properly handles lists, booleans, nested values, edge cases
  - Dates auto-converted to ISO strings for backward compatibility
- **Verifier Independence** — Verifier receives git-sourced file lists, not implementer claims
  - `build_verification_prompt()` takes `files_changed_from_git` from `git diff --name-only`
  - "Evidence from Implementer" section removed from verifier template
- **Reference-Based Context** — All agent prompts reference file paths instead of inlining full contents
  - `{{CODE_ARCH_PATH}}`, `{{CONVENTIONS_PATH}}`, etc. replace `{{CODE_ARCH}}`, `{{CONVENTIONS}}`
  - Applies to implementer, verifier, code-quality-validator, security-reviewer, and feature-fixer agents
  - Agents read context on-demand via their Read tool
  - Prompts shrink ~80% for large projects
- **Skill Structure** — 4 pipeline skills split into SKILL.md (workflow) + REFERENCE.md (details)
  - `execute-feature`: 509 -> 139 lines SKILL.md + 226 lines REFERENCE.md
  - `plan-feature`: 647 -> 177 lines SKILL.md + 211 lines REFERENCE.md
  - `validate-implementation`: 414 -> 141 lines SKILL.md + 159 lines REFERENCE.md
  - `complete-implementation`: 293 -> 101 lines SKILL.md + 127 lines REFERENCE.md
- **PRD Template** — Updated to v1.3.0 with Implementation Hints section and test criteria

### Fixed
- **`validate_setup.py`** — No longer silently exits when called without stdin (e.g., from init-project Step 7)
- **`remind_close_session.py`** — Checks for actual content below `## Notes` instead of line count heuristic, preventing false positives after context compactions
- **`test_normalizes_verdict_to_lowercase`** — Fixed broken test that passed a directory instead of using the actual result file path

### Removed
- **Deprecated functions** — Removed `parse_verification_result()`, `_fallback_verdict_scan()`, `extract_combined_learnings()`, `extract_section()`, `reset_to_commit()` from orchestrator (superseded by file-based JSON and branch-per-attempt)
- **`hooks/hooks.json`** — Removed legacy hook config file (superseded by `plugin.json` hooks section since v1.1.0)

## [1.5.4] - 2026-02-19

### Fixed
- **Hook path resolution** — Project-level hook commands now use `$CLAUDE_PROJECT_DIR` instead of relative paths
  - Hooks previously used `python3 kit_tools/hooks/...` which breaks when shell CWD drifts during a session
  - Now uses `python3 "$CLAUDE_PROJECT_DIR/kit_tools/hooks/..."` which resolves correctly regardless of CWD
  - Fixes infinite loop where a Stop hook file-not-found error re-triggers the Stop event
  - `/kit-tools:init-project` writes the correct absolute-path commands into `.claude/settings.local.json`
  - `/kit-tools:update-kit-tools` documentation updated to reflect the new path convention

## [1.5.3] - 2026-02-09

### Added
- **Epic Chaining for Execute-Feature Pipeline** — Multi-PRD epics now execute automatically on a shared branch
  - PRD template gains `epic`, `epic_seq`, `epic_final` frontmatter fields
  - `/kit-tools:execute-feature` detects epic PRDs, offers sequential execution with pause-between-PRDs option
  - Orchestrator chains PRDs: stories → validate → tag checkpoint → archive → next PRD
  - Hard dependency gate: blocks PRD execution if `depends_on` PRDs aren't archived
  - Git tags mark each PRD checkpoint (`[epic]/[feature]-complete`)
  - Resume support: skips already-completed PRDs on restart
  - Cross-PRD learnings carried forward to subsequent PRD story prompts
- **Epic-Aware Completion** — `/kit-tools:complete-implementation` handles mid-epic and final-epic PRDs
  - Mid-epic: tag + archive only, no PR or artifact cleanup
  - Final epic PRD: PR references all PRDs and checkpoint tags
- **Pause Between PRDs** — New `epic_pause_between_prds` config option
  - Drops a pause file after each PRD completes for user review
  - Recommended default for epic execution

### Fixed
- **Verifier structured output parsing** — `parse_verification_result()` now strips markdown code fences before regex search, fixing ~33% false failure rate when LLMs wrap output in triple backticks
  - Added fallback verdict detection: scans for `verdict: pass` and natural language pass/fail signals when structured block is missing
  - Logs raw verifier output tail on parse failure for diagnosis
- **Verification-only retry** — When implementation succeeded but verifier output couldn't be parsed, retries now skip re-implementation and only re-run verification (saves a full implementation session per retry)
- **Failure detail sanitization** — `log_story_failure()` no longer dumps raw template/session content into `EXECUTION_LOG.md`; extracts first meaningful line and truncates
- **Verifier template hardening** — `story-verifier.md` now explicitly instructs the LLM to output the structured block as plain text, not inside code fences

### Changed
- **`execute_orchestrator.py`** — Refactored into `run_single_prd()` and `run_epic()` with shared `execute_prd_stories()` loop
  - `update_state_story()` accepts `prd_key` for epic nested state
  - `build_implementation_prompt()` gathers cross-PRD learnings in epic mode
  - `log_completion()` aggregates stats across all PRDs in epic mode
- **`/kit-tools:plan-feature`** — Step 2b now sets epic chaining fields; Step 10 includes epic fields in frontmatter template
- **`/kit-tools:execute-feature`** — Epic detection in Step 1, dependency hard gate in Step 3, `epic/[name]` branching in Step 4, `epic_prds` config format in Step 7

## [1.5.2] - 2026-02-07

### Added
- **New Skill: `/kit-tools:validate-implementation`** — Full branch-level validation against PRD
  - Reviews entire `git diff main...HEAD` — all changes across the feature, not just recent edits
  - Three independent review passes: code quality, security, and PRD compliance
  - PRD compliance checks acceptance criteria coverage, functional requirements, and scope creep
  - Automatic fix loop (max 3 iterations) for critical findings
  - Autonomous mode: spawns fixer agent; supervised mode: fixes inline
  - Logs remaining findings to `kit_tools/AUDIT_FINDINGS.md`
- **New Agent: `security-reviewer.md`** — Dedicated security review agent
  - Focused on injection vulns, auth gaps, secrets, input validation, insecure defaults, dependency risks
  - Extracted from code-quality-validator Pass 2 for focused attention
- **New Agent: `feature-fixer.md`** — Targeted fix agent for autonomous mode
  - Parses validation findings and applies minimal, focused fixes
  - Self-verifies and commits with structured output
- **Autonomous validation in orchestrator** — `execute_orchestrator.py` now spawns a validation session after all stories complete

### Changed
- **`code-quality-validator.md`** — Narrowed to quality-only (removed security and intent alignment passes)
- **`execute-feature/SKILL.md`** — Completion messaging now directs to validate-implementation
- **`complete-implementation/SKILL.md`** — Added execution artifact cleanup (Step 7), feature branch handling with PR/merge option (Step 8), validate-implementation in Related Skills
- **`close-session/SKILL.md`** — Replaced validate-implementation invocation with inline quality check using code-quality-validator agent directly (session-level diff, not branch-level)
- **`checkpoint/SKILL.md`** — Replaced validate-implementation invocation with inline quality check using code-quality-validator agent directly
- **`detect_phase_completion.py`** — Suggests validate-implementation instead of validate-phase
- **`init-project/SKILL.md`** — References updated to validate-implementation
- **`README.md`** — Skills table, hooks table, and "Code Quality Validation" section rewritten as "Feature Validation"
- **`templates/AUDIT_FINDINGS.md`** — References updated to validate-implementation

### Removed
- **`/kit-tools:validate-phase`** — Replaced by validate-implementation (branch-level validation)

## [1.5.1] - 2026-02-06

### Added
- **New Skill: `/kit-tools:sync-symlinks`** — Force-refresh skill symlinks after a plugin update
  - Reads `installed_plugins.json` to find correct install path
  - Runs sync script with the authoritative path
  - Useful when skills appear stale after `/plugin update`

### Fixed
- **`sync_skill_symlinks` hook** — Now reads `~/.claude/plugins/installed_plugins.json` as the source of truth for the plugin install path, instead of solely trusting `$CLAUDE_PLUGIN_ROOT`
  - Fixes issue where skill symlinks remained pointed at the previous version after a plugin update
  - Falls back to `$CLAUDE_PLUGIN_ROOT` if `installed_plugins.json` is unavailable

## [1.5.0] - 2026-02-06

### Added
- **Native Autonomous Execution** — `/kit-tools:execute-feature` replaces Ralph integration
  - Three execution modes: Supervised, Autonomous, and Guarded
  - Supervised: in-session with user review between stories
  - Autonomous: spawns independent `claude -p` sessions per story (unlimited retries by default)
  - Guarded: autonomous with human oversight on failures (3 retries default)
- **Story Implementer Agent** — `agents/story-implementer.md` implements a single user story
  - Explores codebase, implements changes, self-verifies, commits
  - Structured output format for orchestrator parsing
- **Story Verifier Agent** — `agents/story-verifier.md` independently verifies acceptance criteria
  - Skeptical assessment — reads actual code, doesn't trust implementer claims
  - Runs typecheck/lint/tests as specified in criteria
- **Execution Orchestrator** — `scripts/execute_orchestrator.py` manages multi-session execution
  - Spawns fresh Claude sessions per story (implementation + verification)
  - Pause/resume via `touch kit_tools/.pause_execution`
  - Dual-track state: PRD checkboxes + JSON sidecar
  - Execution log at `kit_tools/EXECUTION_LOG.md`
- **Git Branch Isolation** — All execution happens on `feature/[prd-name]` branches
  - Failed retries reset working tree, never touch main
  - Branch ready for user review when all stories complete

### Changed
- **PRD Template** — `ralph_ready` field renamed to `session_ready`
- **`/kit-tools:plan-feature`** — Removed Ralph references, uses `session_ready` and `execute-feature`
- **`/kit-tools:complete-implementation`** — Removed Ralph cleanup step, updated Related Skills

### Removed
- **`/kit-tools:export-ralph`** — Replaced by native `execute-feature`
- **`/kit-tools:import-learnings`** — Learnings captured natively during execution

## [1.4.0] - 2025-02-02

### Added
- **Epic Detection & Decomposition** — `/kit-tools:plan-feature` now detects large features and decomposes them
  - Automatic detection of epic-sized scope (>7 stories, multiple subsystems, scope keywords)
  - Proposes breakdown into multiple focused PRDs
  - Tracks dependencies between related PRDs with `depends_on` field
- **Ralph-Ready Validation** — `/kit-tools:export-ralph` now validates PRD scope before export
  - Checks story count (target ≤7), acceptance criteria count (target ≤35)
  - Soft warning with strong recommendation if PRD exceeds limits
  - Suggests decomposition via `plan-feature` if PRD is too large
- **Senior Dev Persona** — Both skills now act as senior dev reviewers
  - Push back on scope creep and poorly-scoped PRDs
  - Ensure PRDs are set up for implementation success

### Changed
- **PRD Template** — Updated to v1.1.0 with new frontmatter fields
  - `ralph_ready: true/false` — Indicates if PRD is properly scoped for Ralph
  - `depends_on: []` — Array of feature names this PRD depends on
  - Added Ralph-ready guidelines in template comments
- **`/kit-tools:plan-feature`** — Enhanced with scope validation
  - Final scope check before generating PRD
  - Story count limits (5-7 ideal, 8+ triggers warning)
  - Acceptance criteria limits (3-5 per story, ≤35 total)
- **`/kit-tools:export-ralph`** — Enhanced with pre-export validation
  - Checks `ralph_ready` frontmatter field
  - Validates story and criteria counts
  - Warns on dependency PRDs not yet completed

## [1.3.0] - 2025-02-01

### Added
- **PRD (Product Requirements Document) System** — New workflow for feature planning
  - `kit_tools/prd/` directory for PRD files with YAML frontmatter
  - `kit_tools/prd/archive/` for completed PRDs
  - PRD template with user stories (US-XXX), acceptance criteria, functional requirements (FR-X)
- **New Skill: `/kit-tools:complete-implementation`** — Mark PRD as completed and archive it
- **New Skill: `/kit-tools:export-ralph`** — Convert KitTools PRD to ralph's prd.json format
- **New Skill: `/kit-tools:import-learnings`** — Import ralph progress.txt learnings back to PRD
- **Ralph Integration** — Optional integration with the ralph autonomous agent system
  - Export PRDs for autonomous execution
  - Import learnings back to preserve context

### Changed
- **`/kit-tools:plan-feature`** — Now generates PRDs (`prd-[name].md`) instead of `FEATURE_TODO_*.md`
  - User story format with acceptance criteria
  - Functional requirements in FR-X format
  - Implementation Notes section for capturing learnings
- **`/kit-tools:start-session`** — Now checks `kit_tools/prd/` for active features instead of `FEATURE_TODO_*.md`
- **`/kit-tools:close-session`** — Prompts for Implementation Notes when working on a PRD
- **`/kit-tools:checkpoint`** — Captures learnings to active PRD's Implementation Notes
- **`/kit-tools:migrate`** — Now converts existing `FEATURE_TODO_*.md` files to PRD format
- **`/kit-tools:init-project`** — Includes `prd/` directory and PRD template in project setup
- **`detect_phase_completion` hook** — Now detects completions in both PRDs and roadmap TODO files
- **`templates/AGENT_README.md`** — Updated to document PRD structure and workflow (v1.3.0)

### Deprecated
- **`FEATURE_TODO_*.md` files** — Replaced by PRDs; migrate skill converts existing files

## [1.1.0] - 2025-01-28

### Added
- **New Skill: `/kit-tools:validate-phase`** — Code quality, security, and intent alignment validation
  - Three-pass review: quality & conventions, security, intent alignment
  - Findings written to persistent `AUDIT_FINDINGS.md` with unique IDs and severity tracking
  - Can be run manually or is invoked automatically by checkpoint and close-session
- **New Subagent: `code-quality-validator.md`** — Prompt template for the validation subagent
  - Located in new `agents/` directory
  - Defines structured output format for findings
  - Supports placeholder interpolation for project context
- **New Template: `AUDIT_FINDINGS.md`** — Persistent audit findings log
  - Status tracking (open / resolved / dismissed)
  - Severity levels (critical / warning / info)
  - Active and archived findings sections
- **New Hook: `detect_phase_completion`** — Advisory hook for TODO task completions
  - Detects `- [ ]` → `- [x]` transitions in roadmap TODO files
  - Suggests running validate-phase when tasks are completed

### Changed
- **`.claude-plugin/plugin.json`** — Bumped version to 1.1.0, added `agents` field
- **`agents/` directory** — Renamed from `subagents/` to follow Claude Code plugin conventions; added YAML frontmatter to agent files
- **`README.md`** — Updated install instructions to reference WashingBearLabsMarketplace
- **`CONTRIBUTING.md`** — Updated install instructions for local development
- **`checkpoint/SKILL.md`** — Added Step 4 (Run validator) for code changes; renumbered Step 4 → Step 5
- **`close-session/SKILL.md`** — Added Step 3 (Run validator); renumbered Steps 3-5 → Steps 4-6
- **`start-session/SKILL.md`** — Added Step 7 (Review open audit findings); summary includes findings count
- **`init-project/SKILL.md`** — Added `AUDIT_FINDINGS.md` to core templates, `detect_phase_completion.py` to hooks, updated verification to 6 Python scripts
- **`update-kit-tools/SKILL.md`** — Replaced agent placeholder (Step 3) with actual agent inventory and update options
- **`templates/AGENT_README.md`** — Added `AUDIT_FINDINGS.md` to documentation structure tree and session start checklist
- **`hooks/hooks.json`** — Added `detect_phase_completion.py` PostToolUse hook entry

## [1.0.0] - 2025-01-27

### Added
- Initial public release
- **Core Skills**
  - `/kit-tools:init-project` - Initialize kit_tools with project-type presets
  - `/kit-tools:seed-project` - Populate templates from codebase exploration
  - `/kit-tools:migrate` - Migrate existing docs to kit_tools structure
  - `/kit-tools:start-session` - Orient and create scratchpad for work sessions
  - `/kit-tools:close-session` - Process notes and update docs at session end
  - `/kit-tools:checkpoint` - Mid-session checkpoint without closing
  - `/kit-tools:plan-feature` - Interactive feature brainstorming and planning
  - `/kit-tools:sync-project` - Full sync between code and docs
  - `/kit-tools:update-kit-tools` - Update project components from latest plugin versions
- **Automation Hooks**
  - `create_scratchpad` - Creates SESSION_SCRATCH.md on session start
  - `update_doc_timestamps` - Auto-updates "Last Updated" in kit_tools docs
  - `remind_scratchpad_before_compact` - Reminds to capture notes before context compaction
  - `remind_close_session` - Reminds to close session if scratchpad has notes
- **Project Type Presets**
  - API/Backend, Web App, Full Stack, CLI Tool, Library, Mobile, Custom
- **25+ Documentation Templates**
  - Core templates (AGENT_README, SYNOPSIS, CODE_ARCH, LOCAL_DEV, GOTCHAS, SESSION_LOG)
  - API templates (API_GUIDE, DATA_MODEL, ENV_REFERENCE)
  - Ops templates (DEPLOYMENT, CI_CD, MONITORING, INFRA_ARCH)
  - Pattern templates (AUTH, ERROR_HANDLING, LOGGING)
  - Roadmap templates for task tracking
