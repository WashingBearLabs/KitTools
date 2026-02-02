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
  - kit_tools/prd/
  - kit_tools/prd/archive/
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

## Step 0: Project Discovery

Before setting up templates, gather context about the project through auto-detection and conversation.

### 0a: Auto-detect project signals

Scan for files that reveal project context:

| File | What it tells us |
|------|------------------|
| `README.md`, `README.*` | Project description, purpose |
| `package.json` | Node.js project, dependencies hint at type (React → Web App, Express → API) |
| `Cargo.toml` | Rust project, check if lib or bin |
| `pyproject.toml`, `setup.py` | Python project, check for framework hints |
| `go.mod` | Go project |
| `*.csproj`, `*.sln` | .NET project |
| `Podfile`, `*.xcodeproj` | iOS project |
| `build.gradle`, `settings.gradle` | Android/JVM project |
| `docs/`, `wiki/`, `documentation/` | Existing documentation to potentially migrate |
| `src/`, `lib/`, `app/` | Existing code structure |
| `.github/workflows/`, `.gitlab-ci.yml` | CI/CD already set up |

### 0b: Summarize findings and confirm

**If existing README or docs found:**
- Read the README (first 100 lines or so)
- Summarize what you understand about the project
- Present to user: "I found a README. It looks like this project is [summary]. Does that sound right, or would you like to clarify?"

**If package manifest found (package.json, Cargo.toml, etc.):**
- Note the project name, description if present
- Check dependencies for framework hints (e.g., `react` → Web App, `express`/`fastify` → API)
- Include in your summary: "Based on package.json, this looks like a [type] project using [frameworks]."

**If truly blank (no README, no manifest, no code):**
- Ask: "This looks like a fresh project. What are you building? Give me a brief description."
- Follow up if needed: "What's the main goal or purpose?"

### 0c: Special considerations

Ask about context that affects setup:

> "Any special considerations I should know about?"
>
> For example:
> - Personal project vs team/production
> - Specific deployment target (serverless, containers, static hosting)
> - Existing patterns or conventions to follow

This is optional — user can skip if nothing special.

### 0d: Existing documentation check

**If `docs/`, `wiki/`, or similar directories found:**
- Ask: "I found existing documentation in `[directory]`. Would you like me to migrate it into the kit_tools structure? (I can run `/kit-tools:migrate` instead)"
- If yes, stop init and suggest running migrate skill instead

**If kit_tools/ already exists:**
- Proceed to Step 1 (existing setup handling)

### 0e: Collect project summary

This is the most important context for seeding — get a clear picture of what this project is.

**If you found a README or existing docs:**
- Summarize what you learned: "Based on what I found, here's my understanding: [summary]. Is this accurate, or would you like to add/correct anything?"
- Let the user refine or confirm

**If blank project or sparse documentation:**
- Ask directly: "Give me a quick summary of this project — what is it, what does it do, and who is it for? This will help me set up your documentation."
- Follow up if the answer is vague: "Can you tell me a bit more about [specific aspect]?"

**Aim to capture:**
- What the project does (core functionality)
- Who it's for (users, developers, internal team)
- Key technologies or constraints (if not already detected)
- Current status (greenfield, MVP, mature, etc.)

This summary will be used to pre-populate `SYNOPSIS.md` during seeding, so it's worth getting right.

### 0f: Store gathered context

Keep the following in memory for later steps:
- **Project summary** (from user input, refined from README, or both)
- **Project description** (brief, from README or manifest)
- **Detected type** (your best guess based on signals)
- **Frameworks/tech stack** (from dependencies)
- **Special considerations** (from user input)
- **Existing docs** (whether migration was declined)

This context will be used to:
1. Pre-select project type in Step 2
2. Influence template recommendations
3. Pre-populate SYNOPSIS during seeding (especially the project summary)

---

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

Use the context gathered in Step 0 to suggest a project type, then confirm with the user.

### Suggest based on discovered context

**If you detected signals in Step 0**, lead with a suggestion:

> "Based on what I found, this looks like a **[suggested type]** project. Does that sound right?"
>
> Options: **Yes, that's right** / **Actually, it's more of a...** / **Show me all options**

Map your findings to types:
- React, Vue, Next.js, Svelte → **Web App**
- Express, Fastify, Flask, Django REST, Go net/http → **API/Backend**
- Both frontend framework AND backend framework → **Full Stack**
- `bin` target, CLI frameworks (clap, commander, click) → **CLI Tool**
- `lib` target, published to npm/PyPI/crates → **Library**
- iOS/Android frameworks, React Native, Flutter → **Mobile**

**If blank project or unclear**, show the full list and ask:

> "What type of project is this?"

### Project Types

| Type | Description |
|------|-------------|
| **API/Backend** | Server-side service (REST, GraphQL, microservices) |
| **Web App** | Frontend application (React, Vue, Next.js) |
| **Full Stack** | Frontend + Backend together |
| **CLI Tool** | Command-line application |
| **Library** | Reusable package (npm, PyPI, crates) |
| **Mobile** | iOS/Android application |
| **Everything** | Include all templates (recommended if unsure) |
| **Custom** | Pick templates manually |

**Note:** "Everything" is always available if the user wants comprehensive documentation regardless of project type.

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
- prd/PRODUCT_REQ_DOC.md

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
- (All templates from API/Backend + Web App)

**Everything:**
- All templates from all categories (same as Full Stack, explicit option for "give me everything")

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

After type selection, ask about pattern templates. **Use Step 0 context to guide suggestions:**

- If user mentioned authentication/login → suggest AUTH.md
- If user mentioned error handling or reliability → suggest ERROR_HANDLING.md
- If user mentioned logging, debugging, or observability → suggest LOGGING.md
- If API/Backend or Full Stack type → patterns are often useful, lean toward suggesting them

**If context suggests specific patterns:**

> "Since you mentioned [auth/error handling/logging], would you like to include the pattern templates? I'd suggest at least [relevant ones]."
>
> Options: **Yes, include suggested** / **Include all patterns** / **Let me pick** / **No patterns**

**Otherwise, general ask:**

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
├── prd/
│   └── archive/      (for completed PRDs)
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
  - The project context gathered in Step 0 (description, tech stack, special considerations) will help seed SYNOPSIS and other templates more accurately
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
| `/kit-tools:plan-feature` | To create a PRD for a new feature in `kit_tools/prd/` |
| `/kit-tools:update-kit-tools` | Later, to update hooks/templates from newer plugin versions |
| `/kit-tools:migrate` | Instead of init, if project has existing documentation to preserve |
