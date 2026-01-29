---
name: seed-project
description: Populate documentation templates for a new or existing project with progress tracking and validation
---

# Seed Project Documentation

I've been asked to explore this codebase and populate the kit_tools documentation templates with accurate, project-specific information.

## Dependencies

This skill requires the following project files:

| File | Required | Purpose |
|------|----------|---------|
| `kit_tools/` directory | Yes | Must exist (run `/kit-tools:init-project` first) |
| `kit_tools/AGENT_README.md` | Yes | Will be customized with project patterns |
| `kit_tools/SYNOPSIS.md` | Yes | Will be populated with project overview |
| `kit_tools/SESSION_LOG.md` | Yes | Will record seeding session |
| All other `kit_tools/*.md` | Yes | Templates to populate |

**Prerequisite skill:**
- `/kit-tools:init-project` — Must be run first to create kit_tools structure

**Updates:**
- All template files in `kit_tools/` with project-specific content
- `kit_tools/SEED_MANIFEST.json` — Progress tracking
- `kit_tools/.seed_cache/` — Exploration cache

## Arguments

| Argument | Description | Example |
|----------|-------------|---------|
| (none) | Seed all templates | `seed-project` |
| `--tier N` | Seed only tier N templates | `seed-project --tier 1` |
| `--resume` | Continue from manifest progress | `seed-project --resume` |
| `--parallel` | Enable parallel seeding within tiers | `seed-project --parallel` |
| `--validate-only` | Run validation without seeding | `seed-project --validate-only` |
| `--dry-run` | Show what would be seeded without doing it | `seed-project --dry-run` |

## Important Instructions

1. **REPLACE all placeholder text** — Don't leave `[brackets]` or `YYYY-MM-DD` in the final docs
2. **DELETE sections that don't apply** — If there's no database, delete database sections entirely
3. **Use today's date** for "Last updated" fields
4. **Be specific** — Use actual file paths, actual tech names, actual patterns found
5. **Cross-reference** — Link between related docs (e.g., SECURITY.md to ENV_REFERENCE.md)
6. **Validate after each template** — Catch unfilled placeholders immediately

---

## Phase 1: Initialize Manifest

### Create or Load Manifest

1. **Check for existing manifest** at `kit_tools/SEED_MANIFEST.json`
   - If exists and `--resume`: Load and continue from last progress
   - If exists and not `--resume`: Ask to reset or resume
   - If doesn't exist: Copy template from plugin and initialize

2. **Initialize manifest fields:**
   ```json
   {
     "created": "[current ISO timestamp]",
     "last_updated": "[current ISO timestamp]",
     "project_root": "[current directory]",
     "config": {
       "parallel_seeding": [--parallel flag],
       "validation_mode": "strict"
     }
   }
   ```

3. **Create cache directory** at `kit_tools/.seed_cache/` if it doesn't exist

### Determine Scope

Based on arguments and manifest state:

| Mode | Scope |
|------|-------|
| Default | All templates, all tiers |
| `--tier N` | Only tier N templates |
| `--resume` | Templates with status "pending" or "failed" |
| `--validate-only` | Run validation on all seeded templates |

---

## Phase 2: Focused Exploration

Instead of one monolithic exploration, run focused explorations based on what templates need.

### Determine Required Explorations

1. Read seeding frontmatter from all pending templates
2. Collect unique `explorer_focus` values needed
3. Check cache for each focus area

### Run Explorations

For each required focus area not in cache (or cache expired):

1. **Display progress:**
   ```
   Exploring: tech-stack... (1/4)
   ```

2. **Run generic-explorer agent** via Task tool:
   - Interpolate focus-specific parameters
   - Capture structured output

3. **Cache results** to `kit_tools/.seed_cache/{focus}_summary.md`

4. **Update manifest** exploration_cache section

### Exploration Focus Areas

| Focus | Templates That Use It |
|-------|----------------------|
| tech-stack | SYNOPSIS, CODE_ARCH, LOCAL_DEV, CONVENTIONS |
| architecture | CODE_ARCH, SERVICE_MAP, DECISIONS |
| infrastructure | INFRA_ARCH, DEPLOYMENT, CI_CD, MONITORING |
| security | SECURITY, AUTH patterns |
| testing | TESTING_GUIDE |
| operations | TROUBLESHOOTING, MONITORING, DEPLOYMENT |
| dependencies | SERVICE_MAP, API_GUIDE, ENV_REFERENCE |

---

## Phase 3: Template Seeding

### Template Tiers

Process templates in tier order. Within each tier, can run in parallel if `--parallel`.

#### Tier 1: Core Understanding (Always fill these)
1. `SYNOPSIS.md` — Project overview, current state, tech stack
2. `arch/CODE_ARCH.md` — Code structure and patterns
3. `arch/SERVICE_MAP.md` — Dependencies and integrations
4. `docs/LOCAL_DEV.md` — Complete local setup guide

#### Tier 2: Operations (Fill if applicable)
5. `arch/INFRA_ARCH.md` — Infrastructure documentation
6. `arch/SECURITY.md` — Security architecture
7. `docs/MONITORING.md` — Observability
8. `docs/CI_CD.md` — Pipeline documentation
9. `docs/TROUBLESHOOTING.md` — Debugging guide

#### Tier 3: Reference (Fill what applies)
10. `arch/DATA_MODEL.md` — Database schema (if applicable)
11. `docs/API_GUIDE.md` — API documentation
12. `docs/ENV_REFERENCE.md` — Environment variables
13. `docs/CONVENTIONS.md` — Coding standards
14. `docs/DEPLOYMENT.md` — Deploy procedures
15. `testing/TESTING_GUIDE.md` — Testing documentation
16. `docs/UI_STYLE_GUIDE.md` — UI patterns (if applicable)
17. `arch/patterns/AUTH.md` — Auth patterns (if applicable)
18. `arch/patterns/ERROR_HANDLING.md` — Error handling patterns
19. `arch/patterns/LOGGING.md` — Logging patterns

#### Tier 4: Ongoing Documentation
20. `docs/GOTCHAS.md` — Document anything non-obvious discovered
21. `arch/DECISIONS.md` — Architectural decisions
22. `roadmap/MVP_TODO.md` — Incomplete features, TODOs in code

#### Tier 5: Meta (Always last)
23. `AGENT_README.md` — Customized AI navigation guide

### Seeding Process for Each Template

1. **Display progress:**
   ```
   Seeding Progress: ████████░░░░░░░░ 8/23 templates

   Tier 1 (Core):     [####] 4/4 complete
   Tier 2 (Ops):      [##--] 2/5 in progress
   Tier 3 (Ref):      [----] 0/10 pending

   Current: Seeding arch/SECURITY.md...
   ```

2. **Check skip conditions** from template frontmatter
   - If skip condition met, mark as "skipped" with reason

3. **Gather exploration context** from cache for this template's required focus areas

4. **Run generic-seeder agent** via Task tool:
   - Provide template content and requirements
   - Provide relevant exploration context
   - Parse seeded content from output

5. **Write seeded template** to file

6. **Run quick validation** (via hook or inline check)
   - Check for remaining placeholders
   - Warn immediately if any found

7. **Update manifest:**
   ```json
   {
     "status": "seeded",
     "seeded_at": "[timestamp]",
     "validation_result": "PASS|WARNING|FAIL",
     "validation_issues": [...]
   }
   ```

### Skip Handling

When exploration reveals a template doesn't apply:
- Mark status as "skipped" in manifest
- Record reason: "No database found", "No API endpoints", etc.
- Continue to next template

---

## Phase 4: AGENT_README Customization

After all other templates are seeded, customize `AGENT_README.md`:

1. **Read all seeded templates** to understand project patterns
2. **Replace example patterns** with ACTUAL patterns from codebase
3. **Update Off-Limits section** with actual sensitive areas
4. **Add project-specific conventions** discovered during seeding
5. **Update read order** based on which templates are applicable

---

## Phase 5: Validation

### Run Full Validation

After seeding completes:

1. **Run `/kit-tools:validate-seeding` logic** on all seeded templates
2. **Collect validation results** per template
3. **Update manifest** with validation data

### Validation Report

```
┌─────────────────────────────────────────────────────────────────┐
│                    SEEDING VALIDATION REPORT                     │
├─────────────────────────────────────────────────────────────────┤
│  Templates Seeded: 20                                            │
│  Templates Skipped: 3 (not applicable)                          │
│  ✓ Validated: 18    ⚠ Warnings: 1    ✗ Failed: 1               │
└─────────────────────────────────────────────────────────────────┘

FAILED (must fix):
  ✗ arch/SECURITY.md
    Line 24: [authentication method] — unfilled placeholder

WARNINGS (review recommended):
  ⚠ docs/API_GUIDE.md
    Line 87: Rate limits section appears minimal

SKIPPED:
  - arch/DATA_MODEL.md — No database detected
  - docs/UI_STYLE_GUIDE.md — No frontend detected
  - arch/patterns/AUTH.md — No auth implementation found

ACTION REQUIRED:
  Fix failed templates with: /kit-tools:seed-template arch/SECURITY.md
```

### Tier 1 Enforcement

**Tier 1 templates MUST pass validation.** If any Tier 1 template fails:
- Report prominently
- Suggest immediate fix
- Do not mark seeding as complete

---

## Phase 6: Session Log

Add an entry to `kit_tools/SESSION_LOG.md` documenting:

- Today's date
- That this was the initial seeding session (or resume)
- Summary of project (type, tech stack, state)
- Templates seeded vs skipped
- Validation results summary
- Any concerns or recommendations

---

## Final Report

When done, provide:

1. **Project Summary** — What type of project? Tech stack? Current state?
2. **Seeding Summary:**
   - Templates seeded: X
   - Templates skipped: Y (with reasons)
   - Validation passed: Z
3. **Issues Found** — Any templates that need attention
4. **Gaps** — What couldn't be documented without more information
5. **Recommended Next Steps** — Templates to review, information to add

---

## Resume Behavior

When `--resume` is used:

1. Load existing manifest
2. Find templates with status "pending" or "failed"
3. Skip templates with status "seeded" and validation "PASS"
4. Retry failed templates with fresh exploration if needed
5. Continue progress display from where it left off

---

## Progress Display

Throughout seeding, maintain a progress display:

```
┌─────────────────────────────────────────────────────────────────┐
│                    SEED PROJECT PROGRESS                         │
├─────────────────────────────────────────────────────────────────┤
│  Overall: ████████████░░░░░░░░ 12/23 templates (52%)            │
│                                                                  │
│  Tier 1 (Core):     [████] 4/4 ✓                                │
│  Tier 2 (Ops):      [███░] 3/5                                  │
│  Tier 3 (Ref):      [██░░░░░░░░] 2/10                           │
│  Tier 4 (Ongoing):  [░░░] 0/3                                   │
│  Tier 5 (Meta):     [░] 0/1                                     │
│                                                                  │
│  Current: Seeding docs/MONITORING.md...                         │
│  Exploration cache: 5/6 focus areas cached                       │
└─────────────────────────────────────────────────────────────────┘
```

---

## Quick Reference

```bash
# Full seeding (all tiers)
/kit-tools:seed-project

# Seed only core templates
/kit-tools:seed-project --tier 1

# Resume interrupted seeding
/kit-tools:seed-project --resume

# Check validation status
/kit-tools:seed-project --validate-only

# Preview what would be seeded
/kit-tools:seed-project --dry-run
```
