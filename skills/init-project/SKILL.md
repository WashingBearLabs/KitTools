---
name: init-project
description: Initialize kit_tools documentation framework in the current project
---

# Initialize Project Documentation

Setting up the kit_tools documentation framework in this project.

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
└── roadmap/
```

Only create directories that will have files.

## Step 5: Copy selected templates

Copy only the templates selected based on project type and pattern choices.

## Step 6: Install automation hooks

Copy the hooks from this plugin to the target project and configure them.

### 6a: Copy hook scripts

Copy the entire `hooks/` directory from this plugin to the project root:

```
project/
└── hooks/
    ├── hooks.json
    ├── create_scratchpad.py
    ├── update_doc_timestamps.py
    ├── remind_scratchpad_before_compact.py
    ├── remind_close_session.py
    ├── detect_phase_completion.py
    └── validate_setup.py
```

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
            "command": "python3 hooks/create_scratchpad.py"
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
            "command": "python3 hooks/update_doc_timestamps.py"
          }
        ]
      },
      {
        "matcher": "Edit|Write",
        "hooks": [
          {
            "type": "command",
            "command": "python3 hooks/detect_phase_completion.py"
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
            "command": "python3 hooks/remind_scratchpad_before_compact.py"
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
            "command": "python3 hooks/remind_close_session.py"
          }
        ]
      }
    ]
  }
}
```

If `.claude/settings.local.json` already exists, merge the hooks configuration (preserving any existing settings).

### 6c: Verify hook installation

- Confirm all 5 Python scripts were copied
- Confirm hooks.json was copied
- Confirm .claude/settings.local.json has the hooks configured

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
- [ ] hooks/ directory exists with all 6 Python scripts
- [ ] .claude/settings.local.json exists with hooks configured

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
