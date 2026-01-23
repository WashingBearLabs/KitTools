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

```bash
# Via Claude Code plugin marketplace (coming soon)
claude plugins install kit-tools

# Or clone and install locally
git clone https://github.com/WashingBearLabs/kit-tools.git
claude plugins install ./kit-tools
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
| `/kit-tools:migrate` | Migrate existing docs to kit_tools structure |
| `/kit-tools:start-session` | Orient and create scratchpad for a work session |
| `/kit-tools:close-session` | Process notes and update docs at session end |
| `/kit-tools:checkpoint` | Mid-session checkpoint without closing |
| `/kit-tools:plan-feature` | Interactive feature brainstorming and planning |
| `/kit-tools:sync-project` | Full sync between code and docs (`--quick` for audit) |
| `/kit-tools:update-templates` | Update project templates from latest plugin versions |

## Hooks

kit-tools includes automation hooks that run automatically:

| Hook | Trigger | What it does |
|------|---------|--------------|
| `create_scratchpad` | SessionStart | Creates SESSION_SCRATCH.md if kit_tools exists |
| `update_doc_timestamps` | PostToolUse (Edit/Write) | Updates "Last Updated" in kit_tools docs |
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

kit-tools provides 25+ documentation templates organized by category:

**Core** — Always included:
- `AGENT_README.md` — AI navigation guide
- `SYNOPSIS.md` — Project overview
- `CODE_ARCH.md` — Code architecture
- `LOCAL_DEV.md` — Local development setup
- `GOTCHAS.md` — Known issues and gotchas
- `SESSION_LOG.md` — Session history
- `roadmap/*` — Task and feature tracking

**API** — For backend services:
- `API_GUIDE.md`, `DATA_MODEL.md`, `ENV_REFERENCE.md`

**Ops** — For deployed services:
- `DEPLOYMENT.md`, `CI_CD.md`, `MONITORING.md`, `INFRA_ARCH.md`

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
│   ├── arch/                # Architecture docs
│   ├── docs/                # Operational docs
│   ├── testing/             # Testing docs
│   └── roadmap/             # Task tracking
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

## Feature Planning

Use `/kit-tools:plan-feature` to brainstorm new features:

1. Interactive questions refine scope and requirements
2. Generates `FEATURE_TODO_[name].md` with:
   - Feature scope (Goal, Non-Goals, Success Criteria)
   - Origin context (Why now? What triggered this?)
   - Phased tasks with intent statements
   - Pre-flight checklists per phase
3. Adds reference to backlog
4. Preserves brainstorming context for future sessions

## Template Versioning

All templates include version comments:
```markdown
<!-- Template Version: 1.1.0 -->
```

Use `/kit-tools:update-templates` to see if your project templates are behind the plugin versions and selectively update.

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

Contributions welcome! Please see our contributing guidelines (coming soon).

## License

MIT License — see LICENSE file for details.

---

Built with care by [WashingBearLabs](https://github.com/WashingBearLabs)
