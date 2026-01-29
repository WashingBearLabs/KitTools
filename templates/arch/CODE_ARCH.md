<!-- Template Version: 1.1.0 -->
<!-- Seeding:
  explorer_focus: tech-stack, architecture
  required_sections:
    - "Overview"
    - "Directory Structure"
    - "Key Modules"
  skip_if: never
-->
# CODE_ARCH.md

> **TEMPLATE_INTENT:** Document the code structure, key modules, and architectural patterns. The map of how code is organized.

> Last updated: YYYY-MM-DD
> Updated by: [Human/Claude]

---

## Overview

<!-- FILL: High-level description of the codebase structure and philosophy -->

[Describe the overall architecture: monolith, microservices, modular monolith, serverless, library, CLI tool, etc.]

The primary design principles are:

1. [Principle 1]
2. [Principle 2]
3. [Principle 3]

---

## Directory Structure

<!-- FILL: Run `tree -L 2` or similar and document the actual structure -->

```
/
├── [directory]/         # [Purpose]
│   └── [subdirectory]/  # [Purpose]
├── [directory]/         # [Purpose]
└── kit_tools/           # Documentation and tooling
```

---

## Key Modules

<!-- FILL: Document the main modules/packages in your codebase -->

| Module | Purpose | Key Files |
|--------|---------|-----------|
| `[module]/` | [What it does] | `[key_file]` |
| `[module]/` | [What it does] | `[key_file]` |

---

## Data Flow

<!-- FILL: Describe how data moves through the system. Delete if not applicable (e.g., for libraries) -->

```
[Request/Input]
       │
       ▼
[Component A]
       │
       ▼
[Component B]
       │
       ▼
[Response/Output]
```

---

## Key Patterns

<!-- FILL: Document the main patterns used. Delete sections that don't apply -->

### Authentication Flow
<!-- Delete if no auth -->
[Describe auth flow, or delete this section]

See `arch/SECURITY.md` for detailed security documentation.

### Error Handling
[Describe how errors are handled]

See `arch/patterns/ERROR_HANDLING.md` for details.

### Logging
[Describe logging approach]

See `arch/patterns/LOGGING.md` for details.

---

## Background Jobs / Async Workers

<!-- FILL: Scheduled tasks, queue workers, cron jobs. Delete if none -->

### Job Types

| Job | Trigger | Purpose | Location |
|-----|---------|---------|----------|
| [Job name] | [Cron / Queue / Event] | [What it does] | `[file path]` |

### Queue Workers

| Worker | Queue | Processes | Location |
|--------|-------|-----------|----------|
| [Worker name] | [Queue name] | [Message type] | `[file path]` |

### Scheduled Tasks

| Task | Schedule | Purpose |
|------|----------|---------|
| [Task name] | [Cron expression] | [What it does] |

### Job Patterns

```
# How to add a new background job
[Code example or pattern]
```

---

## Caching Strategy

<!-- FILL: Where and how caching is used. Delete if no caching -->

### Cache Locations

| Cache | Technology | Purpose | TTL |
|-------|------------|---------|-----|
| [Name] | [Redis / Memory / etc.] | [What's cached] | [Duration] |

### Cache Keys

| Pattern | Example | Used For |
|---------|---------|----------|
| `[pattern]` | `[example]` | [What it caches] |

### Cache Invalidation

```
# How/when caches are invalidated
[Description or code example]
```

### Cache Patterns

- **Cache-aside:** [Where used, if applicable]
- **Write-through:** [Where used, if applicable]
- **TTL-based expiry:** [Where used, if applicable]

---

## Important Classes / Functions

<!-- FILL: List the most important code artifacts an AI should know about -->

| Name | Location | Purpose |
|------|----------|---------|
| `[name]` | `[path/to/file]` | [What it does] |
| `[name]` | `[path/to/file]` | [What it does] |

---

## State Management

<!-- FILL: How application state is managed. Delete if not applicable -->

### Frontend State

[Describe state management approach: Redux, Context, Zustand, etc.]

### Backend State

[Describe where state lives: database, cache, sessions, etc.]

### Session Management

[Describe how user sessions work]

---

## External Service Integrations

<!-- FILL: Third-party services integrated. Delete if none -->

| Service | Purpose | Integration Point | Docs |
|---------|---------|-------------------|------|
| [Service] | [What we use it for] | `[file path]` | [Link] |

See `arch/SERVICE_MAP.md` for detailed dependency information.

---

## Dependencies Worth Noting

<!-- FILL: External libraries with non-obvious usage or gotchas -->

| Dependency | Purpose | Gotchas |
|------------|---------|---------|
| [Library] | [What it's used for] | [Any quirks or important notes] |

---

## Code Style Quick Reference

<!-- FILL: Document formatting/linting tools used -->

- **[Language]**: [Formatter/linter] — run `[command]` before committing
- **Commits**: [Commit message convention, if any]

See `docs/CONVENTIONS.md` for full style guide.
