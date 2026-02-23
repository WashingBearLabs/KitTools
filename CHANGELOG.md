# Changelog

All notable changes to kit-tools will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
- **Test Execution in Validation** — `/kit-tools:validate-feature` Step 4b runs the test suite
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
  - `validate-feature`: 414 -> 141 lines SKILL.md + 159 lines REFERENCE.md
  - `complete-feature`: 293 -> 101 lines SKILL.md + 127 lines REFERENCE.md
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
- **Epic-Aware Completion** — `/kit-tools:complete-feature` handles mid-epic and final-epic PRDs
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
- **New Skill: `/kit-tools:validate-feature`** — Full branch-level validation against PRD
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
- **`execute-feature/SKILL.md`** — Completion messaging now directs to validate-feature
- **`complete-feature/SKILL.md`** — Added execution artifact cleanup (Step 7), feature branch handling with PR/merge option (Step 8), validate-feature in Related Skills
- **`close-session/SKILL.md`** — Replaced validate-feature invocation with inline quality check using code-quality-validator agent directly (session-level diff, not branch-level)
- **`checkpoint/SKILL.md`** — Replaced validate-feature invocation with inline quality check using code-quality-validator agent directly
- **`detect_phase_completion.py`** — Suggests validate-feature instead of validate-phase
- **`init-project/SKILL.md`** — References updated to validate-feature
- **`README.md`** — Skills table, hooks table, and "Code Quality Validation" section rewritten as "Feature Validation"
- **`templates/AUDIT_FINDINGS.md`** — References updated to validate-feature

### Removed
- **`/kit-tools:validate-phase`** — Replaced by validate-feature (branch-level validation)

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
- **`/kit-tools:complete-feature`** — Removed Ralph cleanup step, updated Related Skills

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
- **New Skill: `/kit-tools:complete-feature`** — Mark PRD as completed and archive it
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
