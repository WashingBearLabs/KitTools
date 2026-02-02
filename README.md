# kit-tools

A documentation framework for AI-assisted development by [WashingBearLabs](https://github.com/WashingBearLabs).

## What is kit-tools?

kit-tools is a Claude Code plugin that provides:

- **Structured documentation templates** — Consistent docs across projects
- **Session management** — Track work across context refreshes
- **Automation hooks** — Auto-timestamps, scratchpad reminders
- **Feature planning** — Brainstorm and plan features with guided workflows

Think of it as a "documentation kit" for your projects, with AI-aware features built in.

## Installation

From inside Claude Code:

```
# 1. Add the WashingBearLabs marketplace
/plugin marketplace add WashingBearLabs/WashingBearLabsMarketplace

# 2. Install the plugin
/plugin install kit-tools@washingbearlabs
```

Or install from a local clone:

```bash
git clone https://github.com/WashingBearLabs/KitTools.git
```
```
/plugin install ./KitTools
```

## Quick Start

1. **Initialize** — Set up kit_tools in your project:
   ```
   /kit-tools:init-project
   ```
   Select your project type (API, Web App, CLI, etc.) and templates will be tailored accordingly.

2. **Seed** — Populate templates with project-specific content:
   ```
   /kit-tools:seed-project
   ```
   Claude explores your codebase and fills in the documentation.

3. **Work** — Start a development session:
   ```
   /kit-tools:start-session
   ```
   Claude orients itself using your docs and creates a scratchpad for notes.

4. **Close** — End your session cleanly:
   ```
   /kit-tools:close-session
   ```
   Notes are processed into permanent documentation.

## Skills

| Skill | Description |
|-------|-------------|
| `/kit-tools:init-project` | Initialize kit_tools with project-type presets |
| `/kit-tools:seed-project` | Populate templates from codebase exploration |
| `/kit-tools:seed-template` | Seed a single template with project-specific content |
| `/kit-tools:validate-seeding` | Validate seeded templates for unfilled placeholders |
| `/kit-tools:migrate` | Migrate existing docs to kit_tools structure |
| `/kit-tools:start-session` | Orient and create scratchpad for a work session |
| `/kit-tools:close-session` | Process notes and update docs at session end |
| `/kit-tools:checkpoint` | Mid-session checkpoint without closing |
| `/kit-tools:plan-feature` | Create a Product Requirements Document (PRD) for a new feature |
| `/kit-tools:complete-feature` | Mark a PRD as completed and archive it |
| `/kit-tools:sync-project` | Full sync between code and docs (`--quick` for audit) |
| `/kit-tools:validate-phase` | Run code quality, security, and intent alignment validation |
| `/kit-tools:update-kit-tools` | Update project components from latest plugin versions |
| `/kit-tools:export-ralph` | Export PRD to ralph's prd.json format (optional ralph integration) |
| `/kit-tools:import-learnings` | Import ralph progress.txt learnings back to PRD |

## Hooks

kit-tools includes automation hooks that run automatically:

| Hook | Trigger | What it does |
|------|---------|--------------|
| `create_scratchpad` | SessionStart | Creates SESSION_SCRATCH.md if kit_tools exists |
| `sync_skill_symlinks` | SessionStart | Syncs skill symlinks for the plugin |
| `update_doc_timestamps` | PostToolUse (Edit/Write) | Updates "Last Updated" in kit_tools docs |
| `detect_phase_completion` | PostToolUse (Edit/Write) | Suggests running validate-phase when PRD criteria or TODO tasks are completed |
| `validate_seeded_template` | PostToolUse (Edit/Write) | Validates seeded templates for unfilled placeholders |
| `remind_scratchpad_before_compact` | PreCompact | Reminds to capture notes, adds compaction marker |
| `remind_close_session` | Stop | Reminds to run close-session if scratchpad has notes |

*Note: Setup validation is built into `/kit-tools:init-project` as a final step.*

## Project Types

When initializing, select your project type for tailored templates:

| Type | Description | Templates |
|------|-------------|-----------|
| **API/Backend** | REST, GraphQL, microservices | Core + API + Data + Ops |
| **Web App** | React, Vue, Next.js | Core + Deployment + CI |
| **Full Stack** | Frontend + Backend | Everything |
| **CLI Tool** | Command-line apps | Core (minimal) |
| **Library** | npm, PyPI packages | Core + API docs |
| **Mobile** | iOS/Android apps | Core + Services |
| **Custom** | Pick templates manually | Your choice |

## Templates

kit-tools provides 29 documentation templates organized by category:

**Core** — Always included:
- `AGENT_README.md` — AI navigation guide
- `SYNOPSIS.md` — Project overview
- `SESSION_LOG.md` — Session history
- `AUDIT_FINDINGS.md` — Code quality findings log
- `CODE_ARCH.md` — Code architecture
- `DECISIONS.md` — Architecture decision records
- `LOCAL_DEV.md` — Local development setup
- `GOTCHAS.md` — Known issues and gotchas
- `CONVENTIONS.md` — Code conventions and standards
- `TROUBLESHOOTING.md` — Common issues and solutions
- `TESTING_GUIDE.md` — Testing strategy and patterns
- `prd/*` — Product Requirements Documents
- `roadmap/*` — Milestone tracking and backlog

**API** — For backend services:
- `API_GUIDE.md`, `DATA_MODEL.md`, `ENV_REFERENCE.md`, `SERVICE_MAP.md`

**Ops** — For deployed services:
- `DEPLOYMENT.md`, `CI_CD.md`, `MONITORING.md`, `INFRA_ARCH.md`, `SECURITY.md`

**UI** — For frontend applications:
- `UI_STYLE_GUIDE.md`, `feature_guides/FEATURE_TEMPLATE.md`

**Patterns** — Optional deep-dives:
- `AUTH.md`, `ERROR_HANDLING.md`, `LOGGING.md`

## Project Structure

After initialization, your project will have:

```
your-project/
├── kit_tools/
│   ├── AGENT_README.md      # AI navigation guide
│   ├── SYNOPSIS.md          # Project overview
│   ├── SESSION_LOG.md       # Session history
│   ├── AUDIT_FINDINGS.md    # Code quality findings
│   ├── arch/                # Architecture docs
│   ├── docs/                # Operational docs
│   ├── testing/             # Testing docs
│   ├── prd/                 # Product Requirements Documents
│   │   └── archive/         # Completed PRDs
│   └── roadmap/             # Milestone tracking
└── CLAUDE.md                # Claude Code instructions
```

## Session Workflow

kit-tools encourages a session-based workflow:

```
┌─────────────────┐
│  start-session  │  ← Orient, check for orphaned notes
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│     Work...     │  ← Scratchpad captures notes automatically
│                 │  ← Hooks update timestamps, remind on compact
└────────┬────────┘
         │
    ┌────┴────┐
    │         │
    ▼         ▼
┌────────┐ ┌─────────────┐
│checkpoint│ │close-session│
└────────┘ └─────────────┘
    │              │
    │              ▼
    │         Notes → permanent docs
    │         Scratchpad deleted
    ▼
  Continue
  working...
```

## Code Quality Validation

Use `/kit-tools:validate-phase` to review recent code changes:

1. Gathers git diff, phase intent from TODO files, and project rulebook docs
2. Runs a code quality agent with three review passes:
   - **Quality & Conventions** — naming, patterns, code smells, error handling
   - **Security** — injection, auth gaps, secrets, input validation
   - **Intent Alignment** — implementation vs plan, scope creep, completeness
3. Writes findings to `kit_tools/AUDIT_FINDINGS.md` with unique IDs and severity levels
4. All findings are advisory — they inform but never block workflows

Validation runs automatically during `/kit-tools:checkpoint` (for code changes) and `/kit-tools:close-session`. Open findings are reviewed at `/kit-tools:start-session`.

## Feature Planning with PRDs

Use `/kit-tools:plan-feature` to create Product Requirements Documents (PRDs):

1. Interactive questions refine scope and requirements
2. **Epic detection** — Large features are automatically decomposed into multiple PRDs
3. Generates `prd-[name].md` with:
   - Overview and goals
   - User stories with acceptance criteria (US-XXX format)
   - Functional requirements (FR-X format)
   - Non-goals and scope boundaries
   - Technical considerations
4. Links to backlog and milestone tracking
5. Captures implementation notes as you work

### Ralph-Ready Guidelines

PRDs are sized for reliable autonomous execution:

| Guideline | Target |
|-----------|--------|
| Stories per PRD | 5-7 (max 7) |
| Criteria per story | 3-5 (max 6) |
| Total criteria | ≤35 |

PRDs exceeding these limits are flagged as `ralph_ready: false` and should be decomposed.

### Epic Decomposition

Large features ("epics") are automatically split into focused PRDs:

```
"OAuth Authentication" (epic)
         ↓ decomposed into:
├── prd-oauth-schema.md    (3 stories, no dependencies)
├── prd-oauth-provider.md  (4 stories, depends_on: [oauth-schema])
├── prd-oauth-api.md       (4 stories, depends_on: [oauth-provider])
└── prd-oauth-ui.md        (4 stories, depends_on: [oauth-api])
```

### PRD Lifecycle

```
/plan-feature → prd-auth.md (status: active, ralph_ready: true)
       ↓
    Work on feature, check off acceptance criteria
       ↓
/complete-feature → prd-auth.md moves to prd/archive/
```

### Ralph Integration (Optional)

kit-tools PRDs can be exported for use with the [ralph](https://github.com/snarktank/ralph) autonomous agent system:

```
/kit-tools:export-ralph    # Validates scope, converts PRD → prd.json
./ralph.sh --tool claude   # Run ralph autonomous loop
/kit-tools:import-learnings # Pull learnings back to PRD
```

The `export-ralph` skill validates PRD scope before export, warning if a PRD is too large for reliable autonomous execution.

This allows hybrid workflows: plan with kit-tools, execute with ralph, preserve learnings in your PRD.

## Template Versioning

All templates include version comments:
```markdown
<!-- Template Version: 1.1.0 -->
```

Use `/kit-tools:update-kit-tools` to see if your project components (hooks, templates) are behind the plugin versions and selectively update.

## Philosophy

This framework is built around a key insight: **AI assistants are most effective when they have structured, comprehensive context about a codebase.**

Instead of repeatedly explaining your project in chat, maintain living documentation that:
- Gives AI immediate understanding of architecture and patterns
- Prevents AI from making decisions that violate existing conventions
- Enables effective troubleshooting with log locations and debug procedures
- Reduces errors by documenting gotchas and known issues

The documentation also benefits human developers, but it's optimized for AI consumption.

## Template vs Instance

A key design principle:

- **Plugin templates** = Canonical versions, updated with the plugin
- **Project kit_tools/** = Your project's documentation, can diverge and customize

This means:
- Plugin updates don't overwrite your customized docs
- You can selectively pull in template improvements
- Each project's documentation is independent

## Contributing

Contributions welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

GPL-3.0 License — see [LICENSE](LICENSE) file for details.

---

Built with care by [WashingBearLabs](https://github.com/WashingBearLabs)
