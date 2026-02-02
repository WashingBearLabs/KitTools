# Changelog

All notable changes to kit-tools will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
