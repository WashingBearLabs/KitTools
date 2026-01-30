---
name: init-project
description: Initialize kit_tools documentation framework in the current project
---

# Initialize Project Documentation

Setting up the kit_tools documentation framework in this project.

## Dependencies

This skill requires the following plugin components:

| Component | Location | Purpose |
|-----------|----------|---------|
| **Templates** | `$CLAUDE_PLUGIN_ROOT/templates/` | Source templates to copy |
| **Hook scripts** | `$CLAUDE_PLUGIN_ROOT/hooks/*.py` | Automation scripts to install |
| **hooks.json** | `$CLAUDE_PLUGIN_ROOT/hooks/hooks.json` | Hook configuration reference |

**Creates in project:**
- `kit_tools/` directory with selected templates
- `hooks/` directory with Python automation scripts
- `.claude/settings.local.json` with hook configuration
- `CLAUDE.md` with scratchpad instructions

## Arguments

| Argument | Description |
|----------|-------------|
| `--dry-run` | Preview what would be created without making changes |

### Dry Run Mode

If `$ARGUMENTS` contains `--dry-run`:

1. Perform all analysis steps (existing setup check, project type selection, etc.)
2. Instead of creating files, output a detailed preview:

```
Dry Run Preview — No changes will be made

Directories to create:
  - kit_tools/
  - kit_tools/arch/
  - kit_tools/docs/
  - kit_tools/roadmap/
  - kit_tools/hooks/
  - .claude/

Templates to copy (14 files):
  - AGENT_README.md
  - SYNOPSIS.md
  - SESSION_LOG.md
  ... (list all)

Hooks to install (7 files in kit_tools/hooks/):
  - create_scratchpad.py
  - update_doc_timestamps.py
  - remind_scratchpad_before_compact.py
  - remind_close_session.py
  - detect_phase_completion.py
  - validate_seeded_template.py
  - validate_setup.py

Settings to create/update:
  - .claude/settings.local.json (hooks configuration)

CLAUDE.md:
  - Will be created with scratchpad instructions

Run without --dry-run to apply these changes.
```

3. Exit without modifying any files

## Step 1: Check for existing setup

- Check if `kit_tools/` directory already exists in this project
- If it exists:
  - Ask the user if they want to:
    1. **Skip** - Keep existing docs, don't overwrite
    2. **Merge** - Add missing templates only (preserve existing content)
    3. **Replace** - Start fresh (will lose existing customizations)
  - Wait for user response before proceeding
  - **Note**: This choice only affects templates (Steps 4-5). Hooks (Step 6) and CLAUDE.md (Step 7) are always installed/updated regardless of this choice.

## Step 2: Select project type

Ask the user to select their project type:

### Project Types

| Type | Description |
|------|-------------|
| **API/Backend** | Server-side service (REST, GraphQL, microservices) |
| **Web App** | Frontend application (React, Vue, Next.js) |
| **Full Stack** | Frontend + Backend together |
| **CLI Tool** | Command-line application |
| **Library** | Reusable package (npm, PyPI, crates) |
| **Mobile** | iOS/Android application |
| **Custom** | Pick templates manually |

### Template Mapping

Based on selection, include these templates:

**Core (all types):**
- AGENT_README.md
- SYNOPSIS.md
- SESSION_LOG.md
- AUDIT_FINDINGS.md
- arch/CODE_ARCH.md
- arch/DECISIONS.md
- docs/LOCAL_DEV.md
- docs/GOTCHAS.md
- docs/CONVENTIONS.md
- docs/TROUBLESHOOTING.md
- docs/feature_guides/FEATURE_TEMPLATE.md
- testing/TESTING_GUIDE.md
- roadmap/BACKLOG.md
- roadmap/MVP_TODO.md
- roadmap/FEATURE_TODO.md

**API/Backend adds:**
- arch/DATA_MODEL.md
- arch/INFRA_ARCH.md
- arch/SECURITY.md
- arch/SERVICE_MAP.md
- docs/API_GUIDE.md
- docs/ENV_REFERENCE.md
- docs/DEPLOYMENT.md
- docs/CI_CD.md
- docs/MONITORING.md

**Web App adds:**
- docs/ENV_REFERENCE.md
- docs/DEPLOYMENT.md
- docs/CI_CD.md
- docs/UI_STYLE_GUIDE.md

**Full Stack adds:**
- (Everything - all templates)

**CLI Tool adds:**
- docs/ENV_REFERENCE.md (if config needed)

**Library adds:**
- docs/API_GUIDE.md (for library API docs)
- docs/ENV_REFERENCE.md

**Mobile adds:**
- arch/SERVICE_MAP.md (backend integrations)
- docs/ENV_REFERENCE.md
- docs/DEPLOYMENT.md (app store deployment)
- docs/UI_STYLE_GUIDE.md

**Custom:**
- Show all available templates grouped by category
- Let user select which to include

## Step 3: Optional patterns

After type selection, ask:

> "Would you like to include pattern templates? These provide documented patterns for common concerns."
>
> - AUTH.md - Authentication patterns
> - ERROR_HANDLING.md - Error handling patterns
> - LOGGING.md - Logging patterns
>
> Options: **Yes (all)** / **Pick specific** / **No**

If yes/pick, add selected patterns from `arch/patterns/`.

## Step 4: Create directory structure

Create directories based on selected templates:

```
kit_tools/
├── arch/
│   └── patterns/     (if patterns selected)
├── docs/
│   └── feature_guides/
├── testing/
├── roadmap/
└── hooks/            (automation scripts)
```

Only create directories that will have files.

## Step 5: Copy selected templates

Copy only the templates selected based on project type and pattern choices.

## Step 6: Install automation hooks

Copy the hooks from this plugin to the target project and configure them.

### 6a: Copy hook scripts

Copy the Python hook scripts from `$CLAUDE_PLUGIN_ROOT/hooks/` to `kit_tools/hooks/`:

```
project/
└── kit_tools/
    └── hooks/
        ├── create_scratchpad.py
        ├── update_doc_timestamps.py
        ├── remind_scratchpad_before_compact.py
        ├── remind_close_session.py
        ├── detect_phase_completion.py
        ├── validate_seeded_template.py
        └── validate_setup.py
```

**Do NOT copy:** `hooks.json` and `sync_skill_symlinks.py` — these are plugin-specific and use `${CLAUDE_PLUGIN_ROOT}` which only works in plugins, not project settings.

### 6b: Configure hooks in project settings

Create or update `.claude/settings.local.json` to register the hooks:

```json
{
  "hooks": {
    "SessionStart": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "python3 kit_tools/hooks/create_scratchpad.py"
          }
        ]
      }
    ],
    "PostToolUse": [
      {
        "matcher": "Edit|Write",
        "hooks": [
          {
            "type": "command",
            "command": "python3 kit_tools/hooks/update_doc_timestamps.py"
          }
        ]
      },
      {
        "matcher": "Edit|Write",
        "hooks": [
          {
            "type": "command",
            "command": "python3 kit_tools/hooks/detect_phase_completion.py"
          }
        ]
      },
      {
        "matcher": "Edit|Write",
        "hooks": [
          {
            "type": "command",
            "command": "python3 kit_tools/hooks/validate_seeded_template.py"
          }
        ]
      }
    ],
    "PreCompact": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "python3 kit_tools/hooks/remind_scratchpad_before_compact.py"
          }
        ]
      }
    ],
    "Stop": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "python3 kit_tools/hooks/remind_close_session.py"
          }
        ]
      }
    ]
  }
}
```

If `.claude/settings.local.json` already exists, merge the hooks configuration (preserving any existing settings).

### 6c: Verify hook installation

- Confirm all 7 Python scripts were copied to `kit_tools/hooks/`
- Confirm `.claude/settings.local.json` exists with hooks configured
- Verify paths in settings use `kit_tools/hooks/` prefix

## Step 7: Set up CLAUDE.md

If `CLAUDE.md` doesn't exist in the project root, create it with scratchpad instructions:

```markdown
# CLAUDE.md

Project-specific instructions for Claude Code.

## Session Scratchpad

After completing significant work (feature, bug fix, refactor, investigation, decision), append a note to `kit_tools/SESSION_SCRATCH.md`:

\`\`\`
[HH:MM] Brief description of what was done
- Files: key files changed (if any)
- Decision: any non-obvious choices (if applicable)
\`\`\`

Keep notes terse — one line plus optional details. This file survives context refreshes and gets processed on session close.
```

If `CLAUDE.md` already exists, append the scratchpad section if it's not already present.

## Step 8: Validate setup

Run a quick validation to ensure everything is in place:

**Check for:**
- [ ] All selected templates were copied successfully
- [ ] CLAUDE.md exists and has scratchpad instructions
- [ ] Directory structure is correct
- [ ] No obvious errors in template copying
- [ ] `kit_tools/hooks/` directory exists with all 7 Python scripts
- [ ] `.claude/settings.local.json` exists with hooks configured using `kit_tools/hooks/` paths

**Report any issues** — if validation finds problems, list them clearly.

## Step 9: Summary

Report to the user:

- Project type selected
- Templates copied (list them)
- Templates NOT copied (mention they can be added later)
- Whether patterns were included
- Hooks installed (list the 4 automation hooks)
- Whether CLAUDE.md was created/updated
- Validation status (pass/issues found)

**Remind the user:**
- Run `/kit-tools:seed-project` next to populate templates with project-specific content
- Run `/kit-tools:update-kit-tools` later to update hooks, templates, or other components as the project grows
- Run `/kit-tools:validate-phase` anytime to review code changes for quality, security, and intent alignment

## Adding Templates Later

If the project expands and needs templates that weren't initially selected:

1. Run `/kit-tools:update-kit-tools`
2. It will show missing hooks, templates, and other components
3. Select which components to add or update

This allows the documentation to grow with the project.

## Note on Template Source

The templates come from this plugin's `templates/` directory. They are canonical versions that can be updated independently of any project's documentation.

## Related Skills

| Skill | When to use |
|-------|-------------|
| `/kit-tools:seed-project` | After init, to populate templates with project-specific content |
| `/kit-tools:update-kit-tools` | Later, to update hooks/templates from newer plugin versions |
| `/kit-tools:migrate` | Instead of init, if project has existing documentation to preserve |
