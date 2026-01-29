---
name: seed-template
description: Seed a single documentation template with project-specific content
---

# Seed Template

I've been asked to seed a single documentation template with project-specific content.

## Dependencies

This skill requires the following:

| File | Required | Purpose |
|------|----------|---------|
| `kit_tools/` directory | Yes | Must exist (run `/kit-tools:init-project` first) |
| Target template | Yes | Must exist in kit_tools/ |
| `kit_tools/SEED_MANIFEST.json` | No | If present, will be updated with seeding results |
| `kit_tools/.seed_cache/` | No | Exploration cache (created if needed) |

**Related skills:**
- `/kit-tools:seed-project` — Seed all templates
- `/kit-tools:validate-seeding` — Validate seeded templates

## Arguments

This skill requires a template path argument:

| Argument | Description | Example |
|----------|-------------|---------|
| `<template>` | Template path relative to kit_tools/ | `seed-template SYNOPSIS.md` |
| `--force` | Re-seed even if already seeded | `seed-template SYNOPSIS.md --force` |
| `--no-cache` | Force fresh exploration (ignore cache) | `seed-template arch/CODE_ARCH.md --no-cache` |
| `--validate` | Run validation after seeding | `seed-template SYNOPSIS.md --validate` |

**Examples:**
```bash
/kit-tools:seed-template SYNOPSIS.md
/kit-tools:seed-template arch/CODE_ARCH.md
/kit-tools:seed-template docs/LOCAL_DEV.md --force --validate
```

## Seeding Process

### Step 1: Locate Template

1. Parse the template argument
2. Resolve full path: `kit_tools/{argument}`
3. Verify template file exists
4. If not found, show available templates and exit

### Step 2: Read Template and Extract Requirements

Read the template file and parse its seeding frontmatter:

```markdown
<!-- Template Version: 1.1.0 -->
<!-- Seeding:
  explorer_focus: tech-stack, architecture
  required_sections:
    - "What Is This?"
    - "Tech Stack"
  skip_if: no-code
-->
```

Extract:
- `explorer_focus` — Which exploration areas are needed
- `required_sections` — Sections that must be filled
- `skip_if` — Conditions that would skip this template

### Step 3: Check Manifest Status (if exists)

If `kit_tools/SEED_MANIFEST.json` exists:
1. Check if template is already marked as seeded
2. If seeded and not `--force`, ask if user wants to re-seed
3. Check if template was marked as skipped and why

### Step 4: Run Explorations

For each focus area in `explorer_focus`:

1. **Check cache** at `kit_tools/.seed_cache/{focus}_summary.md`
   - If exists and < 60 minutes old (or `--no-cache` not set), use cached
   - Otherwise, run fresh exploration

2. **Run exploration** (if needed):
   - Read `agents/generic-explorer.md` from plugin
   - Interpolate placeholders:
     - `{{EXPLORATION_FOCUS}}` — The focus area
     - `{{WHAT_TO_FIND}}` — Focus-specific guidance (see below)
     - `{{OUTPUT_FORMAT}}` — YAML structure
     - `{{PROJECT_ROOT}}` — Project root path
   - Run via Task tool with Explore subagent
   - Cache results to `.seed_cache/`

3. **Collect all exploration context** for the seeder

### Exploration Focus Definitions

| Focus | What to Find |
|-------|--------------|
| `tech-stack` | Languages, frameworks, databases, package managers, build tools |
| `architecture` | Directory structure, patterns, entry points, module boundaries |
| `infrastructure` | Docker, CI/CD, IaC, cloud provider, deployment configs |
| `security` | Auth mechanisms, permissions, secrets management, validation |
| `testing` | Test frameworks, directories, patterns, coverage setup |
| `operations` | Logging, monitoring, alerting, deployment procedures |
| `dependencies` | External services, APIs, third-party integrations |

### Step 5: Run Seeder

1. Read `agents/generic-seeder.md` from plugin
2. Interpolate placeholders:
   - `{{TEMPLATE_PATH}}` — Full path to template
   - `{{TEMPLATE_NAME}}` — Template filename without .md
   - `{{TEMPLATE_CONTENT}}` — Current template content
   - `{{TEMPLATE_REQUIREMENTS}}` — Extracted frontmatter requirements
   - `{{EXPLORATION_CONTEXT}}` — Combined exploration results
3. Run via Task tool
4. Parse output for seeded content and seeding report

### Step 6: Write Seeded Template

1. Extract the seeded markdown content from seeder output
2. Write to the template file using Edit/Write tool
3. Extract seeding report for manifest

### Step 7: Update Manifest (if exists)

Update `kit_tools/SEED_MANIFEST.json`:

```json
{
  "templates": {
    "SYNOPSIS.md": {
      "status": "seeded",
      "seeded_at": "2024-01-15T10:30:00Z",
      "validated_at": null,
      "validation_result": null
    }
  }
}
```

Also update summary counts.

### Step 8: Validate (if --validate)

If `--validate` flag is set:
1. Run validation on the just-seeded template
2. Report any unfilled placeholders or issues
3. Update manifest with validation results

### Step 9: Report Results

Output seeding summary:

```
┌─────────────────────────────────────────────────────────────────┐
│                    TEMPLATE SEEDED: SYNOPSIS.md                  │
├─────────────────────────────────────────────────────────────────┤
│  Explorations used: tech-stack, architecture                     │
│  Sections populated: 8                                           │
│  Sections removed: 2 (not applicable)                           │
│  Confidence: high                                                │
└─────────────────────────────────────────────────────────────────┘

Gaps (may need manual review):
  - Database connection details not found in code

Next steps:
  - Run `/kit-tools:validate-seeding SYNOPSIS.md` to verify
  - Continue with `/kit-tools:seed-project --resume` for remaining templates
```

## Skip Conditions

Templates may specify `skip_if` conditions:

| Condition | Meaning |
|-----------|---------|
| `no-database` | Skip if project has no database |
| `no-api` | Skip if project has no API |
| `no-frontend` | Skip if project has no frontend |
| `no-infrastructure` | Skip if no infra configs found |
| `never` | Always seed this template |

When a condition is met, the template is marked as "skipped" in manifest with reason.

## Error Handling

- **Template not found:** List available templates, suggest alternatives
- **Exploration fails:** Report what couldn't be explored, continue with available context
- **Seeding incomplete:** Mark as "partial" in manifest, report gaps
- **Validation fails:** Report issues but don't block, suggest fixes

## Cache Management

Exploration cache lives at `kit_tools/.seed_cache/`:

```
.seed_cache/
├── tech-stack_summary.md
├── architecture_summary.md
├── infrastructure_summary.md
└── ...
```

- Cache TTL: 60 minutes (configurable in manifest)
- `--no-cache` forces fresh exploration
- Cache is per-project, survives across sessions
