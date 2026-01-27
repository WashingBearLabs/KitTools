---
name: migrate
description: Migrate existing documentation to kit_tools structure
---

# Migrate Existing Documentation

This skill helps projects with existing documentation adopt the kit_tools framework without losing their current docs.

## Step 1: Discovery

Scan the project for existing documentation:

### Common locations to check:
- `README.md` — Project overview
- `docs/` or `documentation/` — Documentation folder
- `CONTRIBUTING.md` — Contribution guidelines
- `CHANGELOG.md` — Version history
- `API.md` or `api/` — API documentation
- `.env.example` — Environment variables
- `ARCHITECTURE.md` or `architecture/` — Architecture docs
- `DEVELOPMENT.md` or `SETUP.md` — Local dev setup
- `DEPLOYMENT.md` — Deployment docs
- `wiki/` — GitHub wiki content
- Inline docs (JSDoc, docstrings, etc.)
- OpenAPI/Swagger specs

### Report findings:

```
Existing Documentation Found:

📄 README.md (2.3kb) - Project overview, setup instructions
📄 docs/api.md (5.1kb) - REST API documentation
📄 docs/architecture.md (1.8kb) - System architecture
📄 .env.example (0.4kb) - 12 environment variables
📄 CONTRIBUTING.md (1.2kb) - Contribution guidelines
📁 docs/guides/ - 3 feature guides

No existing docs found for:
- Data model/schema
- Deployment procedures
- Testing guide
- Security documentation
```

## Step 2: Mapping

Present a mapping of existing docs to kit_tools structure:

```
Proposed Migration:

Existing File              → kit_tools Location              Action
─────────────────────────────────────────────────────────────────────
README.md                  → kit_tools/SYNOPSIS.md           Merge content
docs/api.md                → kit_tools/docs/API_GUIDE.md     Migrate
docs/architecture.md       → kit_tools/arch/CODE_ARCH.md     Migrate
.env.example               → kit_tools/docs/ENV_REFERENCE.md Extract & expand
CONTRIBUTING.md            → kit_tools/docs/CONVENTIONS.md   Merge relevant parts
docs/guides/*.md           → kit_tools/docs/feature_guides/  Move & rename

Will create new (no existing source):
- kit_tools/AGENT_README.md (AI navigation guide)
- kit_tools/arch/DECISIONS.md (will be empty, fill over time)
- kit_tools/docs/GOTCHAS.md (will be empty, fill over time)
- kit_tools/SESSION_LOG.md (session tracking)
- kit_tools/roadmap/*.md (task tracking)
```

Ask user to confirm or adjust the mapping.

## Step 3: Choose migration strategy

Ask user:

> **How should we handle existing documentation?**
>
> 1. **Copy & Enhance** — Copy content into kit_tools templates, keep originals
> 2. **Move & Redirect** — Move to kit_tools, leave redirect notes in original locations
> 3. **Merge Only** — Merge into kit_tools but don't touch originals
> 4. **Custom** — Let me specify per-file

## Step 4: Select project type

Since we're creating kit_tools structure, ask for project type (same as init-project):

- API/Backend
- Web App
- Full Stack
- CLI Tool
- Library
- Mobile
- Custom

This determines which additional templates to create beyond migrated content.

## Step 5: Execute migration

For each file in the mapping:

### For "Migrate" actions:
1. Read existing content
2. Create kit_tools file from template
3. Intelligently merge existing content into appropriate sections
4. Preserve important details, restructure to fit template format
5. Update "Last updated" date

### For "Merge" actions:
1. Read existing content
2. Extract relevant portions
3. Add to appropriate sections in kit_tools file
4. Note the source in a comment

### For "Extract" actions (like .env.example):
1. Parse existing file
2. Create structured documentation
3. Add descriptions where inferable

### For new files:
1. Copy template
2. Leave as template for user to fill

## Step 6: Handle originals

Based on chosen strategy:

**Copy & Enhance:**
- Leave originals untouched
- Add note to kit_tools docs: "Migrated from [original location]"

**Move & Redirect:**
- Replace original with redirect note:
```markdown
# [Original Title]

This documentation has moved to `kit_tools/[new location]`.

Please update your bookmarks.
```

**Merge Only:**
- Leave originals completely untouched

## Step 7: Create CLAUDE.md

Set up CLAUDE.md with scratchpad instructions (same as init-project).

## Step 8: Summary

Report:

- **Migrated**: Files that were migrated with content
- **Created**: New template files (empty or minimal)
- **Skipped**: Files that weren't migrated (and why)
- **Originals**: What happened to original files

**Recommend next steps:**
- Review migrated content for accuracy
- Run `/kit-tools:seed-project` to fill in gaps
- Run `/kit-tools:sync-project --quick` to verify nothing was missed

## Migration Notes

### Handling conflicts

If existing content doesn't fit neatly into kit_tools structure:
- Ask user where it should go
- Create a custom section if needed
- Note in DECISIONS.md why structure was adjusted

### Preserving history

If existing docs have valuable history (dates, authors, changelog):
- Preserve in a "History" section at bottom of migrated file
- Or note in kit_tools/arch/DECISIONS.md

### Large documentation sets

For projects with extensive existing docs:
- Migrate in batches
- Start with core docs (README, architecture, API)
- Add secondary docs in follow-up sessions
- Use SYNC_PROGRESS.md to track migration progress
