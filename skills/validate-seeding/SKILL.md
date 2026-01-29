---
name: validate-seeding
description: Validate seeded templates for unfilled placeholders and incomplete sections
---

# Validate Seeding

I've been asked to validate documentation templates for unfilled placeholders and incomplete sections.

## Dependencies

This skill requires the following:

| File | Required | Purpose |
|------|----------|---------|
| `kit_tools/` directory | Yes | Must exist with seeded templates |
| `kit_tools/SEED_MANIFEST.json` | No | If present, will be updated with validation results |

**Related skills:**
- `/kit-tools:seed-project` — Creates and seeds templates
- `/kit-tools:seed-template` — Seeds individual templates

## Arguments

This skill accepts optional arguments:

| Argument | Description | Example |
|----------|-------------|---------|
| `<path>` | Specific template to validate | `validate-seeding SYNOPSIS.md` |
| `--all` | Validate all templates (default) | `validate-seeding --all` |
| `--tier N` | Validate only tier N templates | `validate-seeding --tier 1` |
| `--strict` | Fail on any warning | `validate-seeding --strict` |
| `--update-manifest` | Update manifest with results (default if manifest exists) | |

## Placeholder Patterns to Detect

The validator looks for these unfilled placeholder patterns:

| Pattern | Example | Severity |
|---------|---------|----------|
| `[brackets]` | `[PROJECT_NAME]` | error |
| `YYYY-MM-DD` in content | `Last updated: YYYY-MM-DD` | error |
| `{{mustache}}` | `{{variable}}` | error |
| `[path to ...]` | `[path to config]` | error |
| `[type: x / y]` | `[type: web app / CLI]` | error |
| Empty required sections | Section with < 10 words | warning |
| Placeholder lists | `- [Feature 1 — description]` | error |

**NOT flagged:**
- `<!-- Template Version: X.X.X -->` — Expected version comment
- `<!-- FILL: ... -->` — Instruction comments (should be deleted but not an error)
- Actual `N/A` or `None` values — Valid when section doesn't apply

## Validation Process

### Step 1: Determine Scope

Based on arguments, determine which templates to validate:

```
If <path> provided:
  → Validate single template at kit_tools/<path>

If --tier N provided:
  → Validate all templates in tier N

If --all or no arguments:
  → Validate all templates in kit_tools/
```

### Step 2: Load Manifest (if exists)

If `kit_tools/SEED_MANIFEST.json` exists:
1. Read current manifest
2. Filter templates based on arguments
3. Skip templates with status "skipped" unless explicitly requested

### Step 3: Validate Each Template

For each template to validate:

1. **Read the template file**
   - Get full content including any seeding frontmatter

2. **Extract requirements from frontmatter**
   - Parse `<!-- Seeding: ... -->` block if present
   - Get `required_sections` list

3. **Run validation checks**
   - Check for placeholder patterns
   - Check for empty sections
   - Verify required sections have content
   - Note line numbers for all issues

4. **Determine result**
   - `PASS` — No errors, may have minor warnings
   - `WARNING` — Has warnings but no errors
   - `FAIL` — Has one or more errors

### Step 4: Generate Validator Prompt

For each template, I'll read the template-validator agent and interpolate:

- `{{TEMPLATE_PATH}}` — Path to the template
- `{{TEMPLATE_CONTENT}}` — Full template content
- `{{TEMPLATE_REQUIREMENTS}}` — Extracted requirements from frontmatter

Then run the validator via Task tool with the interpolated prompt.

### Step 5: Collect Results

Parse validator output for each template:

```
VALIDATION_RESULT: [PASS|WARNING|FAIL]
SUMMARY: [summary text]
ISSUES:
  ISSUE:
    severity: [error|warning]
    type: [placeholder|empty-section|missing-required|inconsistency]
    line: [line number]
    content: [problematic text]
    description: [what's wrong]
  END_ISSUE
  ...
```

### Step 6: Update Manifest

If manifest exists, update each validated template:

```json
{
  "validated_at": "2024-01-15T10:30:00Z",
  "validation_result": "PASS|WARNING|FAIL",
  "validation_issues": [
    {
      "severity": "error|warning",
      "type": "placeholder|empty-section|...",
      "line": 15,
      "content": "...",
      "description": "..."
    }
  ]
}
```

Also update the summary counts.

### Step 7: Report Results

Output a summary report:

```
┌─────────────────────────────────────────────────────────────────┐
│                    SEEDING VALIDATION REPORT                     │
├─────────────────────────────────────────────────────────────────┤
│  Templates Validated: 23                                         │
│  ✓ Passed: 18    ⚠ Warnings: 3    ✗ Failed: 2                  │
└─────────────────────────────────────────────────────────────────┘

FAILED TEMPLATES:

  ✗ SYNOPSIS.md
    Line 15: [PROJECT_NAME] — unfilled placeholder
    Line 24: YYYY-MM-DD — date placeholder

  ✗ arch/CODE_ARCH.md
    Line 8-20: "What Is This?" section is empty

WARNINGS:

  ⚠ docs/API_GUIDE.md
    Line 45: Optional "Rate Limits" section appears empty

PASSED: 18 templates validated successfully
```

## Validation Without Manifest

If no manifest exists, validation still works:
- Uses hardcoded template list
- Results displayed but not persisted
- Suggests creating manifest: "Run `/kit-tools:seed-project` to create a manifest for tracking"

## Exit Behavior

- **All PASS**: Report success, exit cleanly
- **Any WARNING**: Report warnings, suggest review
- **Any FAIL**: Report failures with actionable fix instructions
- **--strict mode**: Treat warnings as failures

## Quick Reference

```bash
# Validate all seeded templates
/kit-tools:validate-seeding

# Validate specific template
/kit-tools:validate-seeding SYNOPSIS.md
/kit-tools:validate-seeding arch/CODE_ARCH.md

# Validate by tier
/kit-tools:validate-seeding --tier 1

# Strict mode (warnings = failures)
/kit-tools:validate-seeding --strict
```
