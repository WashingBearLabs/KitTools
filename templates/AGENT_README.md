<!-- Template Version: 1.0.0 -->
# AGENT_README.md

> **TEMPLATE_INTENT:** Navigation guide for AI assistants. Defines read order, patterns to follow, and areas to avoid.

---

## Quick Start — Read Order

**For general orientation:**
1. **This file** — How to navigate and update docs
2. **SYNOPSIS.md** — What is this project, current state, tech stack
3. **arch/CODE_ARCH.md** — Code structure, patterns, key abstractions
4. **arch/SERVICE_MAP.md** — Dependencies, external integrations, what calls what

**For troubleshooting:**
5. **docs/TROUBLESHOOTING.md** — How to debug, access logs, common fixes
6. **docs/MONITORING.md** — Logs, metrics, alerts, tracing

**For making changes:**
7. **arch/SECURITY.md** — Auth flows, secrets, permissions
8. **docs/GOTCHAS.md** — Known landmines, tech debt, non-obvious behaviors
9. **roadmap/*_TODO.md** — Current work in progress

**For infrastructure:**
10. **arch/INFRA_ARCH.md** — Cloud resources, networking, IAM
11. **docs/CI_CD.md** — Pipeline, deployments

---

## Session Start Checklist

Before starting any work session:

- [ ] Read `SYNOPSIS.md` to understand current project state
- [ ] Check `roadmap/*_TODO.md` for active work items
- [ ] Review `arch/CODE_ARCH.md` for structure and patterns
- [ ] Scan `docs/GOTCHAS.md` for relevant landmines
- [ ] Check `AUDIT_FINDINGS.md` for open findings
- [ ] Check `arch/SERVICE_MAP.md` if working with integrations

**For troubleshooting tasks, also read:**
- [ ] `docs/TROUBLESHOOTING.md` for debugging procedures
- [ ] `docs/MONITORING.md` for log access

**Flag anything that looks like:**
- Security concerns → Document in `arch/SECURITY.md`
- Code that violates documented patterns
- Documentation that appears stale or inconsistent with code

---

## Session End Checklist

Before closing any session, use this checklist to prevent documentation drift:

### Always Update
| File | Update If... |
|------|--------------|
| `SESSION_LOG.md` | Always — log what was done this session |
| `roadmap/*_TODO.md` | Any task was completed, modified, or discovered |

### Architecture Changes
| File | Update If... |
|------|--------------|
| `SYNOPSIS.md` | Project scope, status, or purpose changed |
| `arch/CODE_ARCH.md` | New modules, patterns, workers, or caching added |
| `arch/SERVICE_MAP.md` | New dependencies or integrations added |
| `arch/INFRA_ARCH.md` | New cloud resources, networking, or IAM changes |
| `arch/DATA_MODEL.md` | Schema changes, new tables, new relationships |
| `arch/SECURITY.md` | Auth changes, new secrets, permission changes |
| `arch/DECISIONS.md` | A non-trivial "why" decision was made |

### Operations Changes
| File | Update If... |
|------|--------------|
| `docs/CI_CD.md` | Pipeline changes, new checks, deploy process changes |
| `docs/MONITORING.md` | New metrics, alerts, or log locations |
| `docs/TROUBLESHOOTING.md` | Discovered new common issues or debug procedures |
| `docs/DEPLOYMENT.md` | Deploy process changed |

### Reference Changes
| File | Update If... |
|------|--------------|
| `docs/API_GUIDE.md` | New endpoints, changed contracts, new parameters |
| `docs/ENV_REFERENCE.md` | New environment variables or secrets |
| `docs/LOCAL_DEV.md` | Setup process changed |
| `docs/feature_guides/*` | New feature added or existing feature significantly changed |
| `docs/GOTCHAS.md` | Discovered a landmine or tech debt worth noting |
| `testing/TESTING_GUIDE.md` | Testing approach changed, new test patterns |

---

## Patterns to Follow

<!--
CUSTOMIZE THIS SECTION: Replace these placeholder examples with actual
patterns from this codebase. Delete categories that don't apply.
-->

### Code Organization
<!-- FILL: Where do different types of code live? -->
- [Pattern 1: e.g., "All API routes go in `/routes/`"]
- [Pattern 2: e.g., "Business logic lives in `/services/`"]
- [Pattern 3: e.g., "Database queries go through `/repositories/`"]

### Naming Conventions
<!-- FILL: How are things named in this project? -->
- [Files: e.g., "snake_case for Python, camelCase for JS"]
- [Classes/Functions: e.g., "PascalCase classes, camelCase functions"]
- [Environment variables: e.g., "SCREAMING_SNAKE_CASE"]

### Security Patterns
<!-- FILL: How is security handled? Delete if not applicable -->
- [Input validation: e.g., "All user input validated with..."]
- [SQL: e.g., "Parameterized statements only"]
- [Secrets: e.g., "Never logged, stored in..."]

See `arch/SECURITY.md` for detailed security documentation.

### Error Handling
<!-- FILL: How are errors handled? -->
- [Pattern: e.g., "Custom exception classes in `/exceptions/`"]
- [Logging: e.g., "All errors logged with correlation ID"]
- [User-facing: e.g., "Sanitized of internal details"]

See `arch/patterns/ERROR_HANDLING.md` for details.

---

## Off-Limits / Requires Human Review

The following changes should be drafted but **not applied** without human approval:

<!-- CUSTOMIZE: Update this list based on actual sensitive areas in this project -->

- [ ] **Authentication/Authorization flows** — Security-critical, needs review
- [ ] **Database migrations** — Schema changes can be destructive
- [ ] **Infrastructure changes** — IaC plans need human approval
- [ ] **Dependency updates** — Major version bumps need testing
- [ ] **Files marked `# HUMAN-REVIEW-REQUIRED`** — Explicitly flagged
- [ ] **Secrets or API keys** — Never commit, always use secret management
- [ ] **[Add project-specific sensitive areas]**

When in doubt, ask before applying.

---

## Documentation Structure

```
kit_tools/
├── AGENT_README.md          # This file - AI assistant guide
├── SYNOPSIS.md              # Project overview and current state
├── SESSION_LOG.md           # Development session history
├── AUDIT_FINDINGS.md        # Code quality validation findings
│
├── arch/                    # Architecture documentation
│   ├── CODE_ARCH.md         # Code structure, patterns, modules
│   ├── SERVICE_MAP.md       # Dependencies, integrations, topology
│   ├── INFRA_ARCH.md        # Cloud resources, networking, IAM
│   ├── DATA_MODEL.md        # Database schema
│   ├── SECURITY.md          # Auth, secrets, permissions
│   ├── DECISIONS.md         # Architectural decision records
│   └── patterns/            # Detailed pattern documentation
│
├── docs/                    # Operational documentation
│   ├── LOCAL_DEV.md         # Local development setup
│   ├── TROUBLESHOOTING.md   # Debugging guide
│   ├── MONITORING.md        # Logs, metrics, alerts
│   ├── CI_CD.md             # Pipeline documentation
│   ├── DEPLOYMENT.md        # Deploy procedures
│   ├── API_GUIDE.md         # API documentation
│   ├── ENV_REFERENCE.md     # Environment variables
│   ├── CONVENTIONS.md       # Code style guide
│   ├── GOTCHAS.md           # Known issues and landmines
│   └── feature_guides/      # Feature-specific docs
│
├── testing/                 # Test documentation
├── roadmap/                 # TODOs and backlog
└── prompts/                 # AI session prompts
```

---

## File Naming Conventions

| Type | Pattern | Example |
|------|---------|---------|
| Feature guides | `FEATURENAME_FEATURE_GUIDE.md` | `AUTH_FEATURE_GUIDE.md` |
| TODO lists | `SCOPE_TODO.md` | `MVP_TODO.md`, `V2_TODO.md` |
| Architecture patterns | `PATTERNNAME.md` | `LOGGING.md`, `AUTH.md` |
| Decision records | Date prefix in `DECISIONS.md` | `2024-01-15: Chose X over Y` |

---

## Documentation Standards

### Required Metadata
Every documentation file should include at the top:

```markdown
# FILENAME.md
> Last updated: YYYY-MM-DD
> Updated by: [Human/Claude]
```

### Cross-References
Link related documentation:
- Security info → `arch/SECURITY.md`
- Environment variables → `docs/ENV_REFERENCE.md`
- Debugging → `docs/TROUBLESHOOTING.md`

### Staleness Indicator
If a doc hasn't been updated in 30+ days and the related code has changed, it should be flagged for review.

---

## How to Update This File

This `AGENT_README.md` should be updated when:
- New patterns are established
- New off-limits areas are identified
- The documentation structure changes
- New file naming conventions are adopted

Keep this file accurate — it's the source of truth for AI assistants working in this codebase.
