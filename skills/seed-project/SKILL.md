---
description: Populate documentation templates for a new or existing project
---

# Seed Project Documentation

I've been asked to explore this codebase and populate the kit_tools documentation templates with accurate, project-specific information.

## Important Instructions

1. **REPLACE all placeholder text** — Don't leave `[brackets]` or `YYYY-MM-DD` in the final docs
2. **DELETE sections that don't apply** — If there's no database, delete database sections entirely
3. **Use today's date** for "Last updated" fields
4. **Be specific** — Use actual file paths, actual tech names, actual patterns found
5. **Cross-reference** — Link between related docs (e.g., SECURITY.md to ENV_REFERENCE.md)

## Phase 1: Exploration

Thoroughly explore the codebase to understand:

1. **Project type** — Is this a web app, API, CLI tool, library, mobile app, monorepo?
2. **Directory structure** — Explore key directories
3. **Tech stack** — Check package.json, requirements.txt, go.mod, Cargo.toml, etc.
4. **Entry points** — Find main files, app initialization, CLI entry points
5. **Configuration** — Look for .env.example, config files, environment variables
6. **Existing docs** — Check for README.md, existing documentation
7. **Tests** — Find test directories and testing frameworks
8. **Infrastructure** — Look for Dockerfile, terraform/, k8s/, CI configs
9. **External services** — Look for API clients, SDK usage, webhooks
10. **Background jobs** — Look for workers, cron jobs, queue consumers
11. **Current state** — What features exist? What looks incomplete?

## Phase 2: Documentation Population

Fill in the template files based on what was discovered. Work in this order:

### Tier 1: Core Understanding (Always fill these)

1. **kit_tools/SYNOPSIS.md** — Project overview, current state, tech stack
2. **kit_tools/arch/CODE_ARCH.md** — Code structure and patterns
3. **kit_tools/arch/SERVICE_MAP.md** — Dependencies and integrations
4. **kit_tools/docs/LOCAL_DEV.md** — Complete local setup guide

### Tier 2: Operations (Fill if applicable)

5. **kit_tools/arch/INFRA_ARCH.md** — Infrastructure documentation
6. **kit_tools/arch/SECURITY.md** — Security architecture
7. **kit_tools/docs/MONITORING.md** — Observability
8. **kit_tools/docs/CI_CD.md** — Pipeline documentation
9. **kit_tools/docs/TROUBLESHOOTING.md** — Debugging guide

### Tier 3: Reference (Fill what applies)

10. **kit_tools/arch/DATA_MODEL.md** — Database schema (if applicable)
11. **kit_tools/docs/API_GUIDE.md** — API documentation
12. **kit_tools/docs/ENV_REFERENCE.md** — Environment variables
13. **kit_tools/docs/CONVENTIONS.md** — Coding standards
14. **kit_tools/docs/DEPLOYMENT.md** — Deploy procedures
15. **kit_tools/testing/TESTING_GUIDE.md** — Testing documentation

### Tier 4: Ongoing Documentation

16. **kit_tools/docs/GOTCHAS.md** — Document anything non-obvious discovered
17. **kit_tools/arch/DECISIONS.md** — Document architectural decisions you can infer
18. **kit_tools/roadmap/MVP_TODO.md** — Note incomplete features, TODOs in code

## Phase 3: Customize AGENT_README.md

Update `kit_tools/AGENT_README.md` with project-specific information:

- Replace example patterns with ACTUAL patterns from this codebase
- Update "Off-Limits" section with actual sensitive areas
- Add project-specific conventions
- Update the read order if some docs aren't applicable

## Phase 4: Session Log

Add an entry to `kit_tools/SESSION_LOG.md` documenting:

- Today's date
- That this was the initial seeding session
- Summary of project (type, tech stack, state)
- What was documented
- Any concerns or recommendations

## Final Report

When done, provide:

1. **Project Summary** — What type of project? Tech stack? Current state?
2. **Files Updated** — List every file modified
3. **Files Deleted/Marked N/A** — What wasn't applicable
4. **Concerns** — Any issues, inconsistencies, security concerns, or tech debt found
5. **Gaps** — What couldn't be documented without more information
6. **Recommended Next Steps** — What should be documented further or investigated

## Before You Begin

Before starting Phase 1:

1. Briefly review the phases above
2. Ask any clarifying questions about the project or documentation preferences
3. Confirm ready to proceed

Only begin exploration after questions have been answered (or confirmed there are none).
