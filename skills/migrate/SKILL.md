---
name: migrate
description: Migrate a v1.x kit_tools project to v2.0 structure
---

# Migrate to v2.0

Migrate a project's `kit_tools/` directory from v1.x structure to v2.0. Handles the `prd/` → `specs/` directory rename, file renames, config/state key migration, and path updates.

## Dependencies

| File | Required | Purpose |
|------|----------|---------|
| `kit_tools/` | Yes | Existing kit_tools setup to migrate |

**Modifies:**
- `kit_tools/prd/` → `kit_tools/specs/` (directory rename)
- `.execution-config.json` (config key migration)
- `.execution-state.json` (state key migration)
- `.claude/settings.local.json` (hook path updates)
- `kit_tools/.kit_tools_sync.json` (sync marker update)
- All `.md` files under `kit_tools/` (path references)

---

## Step 1: Version Detection

Determine current project state:

- **`kit_tools/specs/` exists** → Already v2.0. Report "Already migrated" and stop.
- **`kit_tools/prd/` exists** → v1.x detected. Continue migration.
- **Neither exists** → No kit_tools setup found. Suggest `/kit-tools:init-project` and stop.

---

## Step 2: Pre-migration Safety

1. Run `git status --porcelain`
2. If working tree is dirty, warn:
   > "You have uncommitted changes. I recommend committing or stashing before migrating. Continue anyway?"
3. Wait for user confirmation before proceeding.

---

## Step 3: Directory Rename

Rename the feature specs directory:

```bash
git mv kit_tools/prd/ kit_tools/specs/
```

If `git mv` fails (untracked files), fall back to:

```bash
mv kit_tools/prd/ kit_tools/specs/
git add kit_tools/specs/
```

**Verify:** `ls kit_tools/specs/` shows files; `kit_tools/prd/` is gone.

---

## Step 4: File Renames

Rename any `prd-*.md` files to `feature-*.md` (idempotent — skip files already named `feature-*`):

### In `kit_tools/specs/`:
```bash
for f in kit_tools/specs/prd-*.md; do
  [ -f "$f" ] && git mv "$f" "${f/prd-/feature-}"
done
```

### In `kit_tools/specs/archive/`:
```bash
for f in kit_tools/specs/archive/prd-*.md; do
  [ -f "$f" ] && git mv "$f" "${f/prd-/feature-}"
done
```

---

## Step 5: Roadmap Migration

Rename `MVP_TODO.md` → `MILESTONES.md` if it exists (idempotent):

```bash
[ -f kit_tools/roadmap/MVP_TODO.md ] && git mv kit_tools/roadmap/MVP_TODO.md kit_tools/roadmap/MILESTONES.md
```

---

## Step 6: Epic File Generation

Scan all feature specs in `kit_tools/specs/` for shared `epic:` frontmatter values.

For each unique epic name found:
1. Check if `kit_tools/specs/epic-[name].md` already exists (idempotent)
2. If not, read `$CLAUDE_PLUGIN_ROOT/templates/specs/EPIC.md`
3. Generate `kit_tools/specs/epic-[name].md` with:
   - Epic name from frontmatter
   - Feature spec table populated from `epic_seq` ordering
   - Dependencies from `depends_on` fields

---

## Step 7: Config Migration

If `kit_tools/specs/.execution-config.json` exists (or `kit_tools/prd/.execution-config.json` was just moved), rewrite config keys:

| Old Key | New Key |
|---------|---------|
| `prd_path` | `spec_path` |
| `prd_overview` | `spec_overview` |
| `epic_prds` | `epic_specs` |
| `epic_pause_between_prds` | `epic_pause_between_specs` |

Within `epic_specs` entries:
| Old Key | New Key |
|---------|---------|
| `prd_path` | `spec_path` |

Within `project_context`:
| Old Key | New Key |
|---------|---------|
| `prd_overview` | `spec_overview` |

Also update path values: replace `kit_tools/prd/` with `kit_tools/specs/` in all string values.

Read the file, apply key renames and path updates, write it back.

---

## Step 8: State Migration

If `kit_tools/specs/.execution-state.json` exists, rewrite state keys:

| Old Key | New Key |
|---------|---------|
| `prd` | `spec` |
| `prds` | `specs` |
| `current_prd` | `current_spec` |

Read the file, apply key renames, write it back.

---

## Step 9: Project Hook Paths

If `.claude/settings.local.json` exists, update hook commands:

- Replace `kit_tools/prd/` with `kit_tools/specs/` in all command strings

Read the file, apply replacements, write it back.

---

## Step 10: Documentation Path Sweep

Update all `.md` files under `kit_tools/` that reference `kit_tools/prd/`:

```bash
# Find files with old paths
grep -rl 'kit_tools/prd/' kit_tools/ --include='*.md'
```

For each file found, replace:
- `kit_tools/prd/` → `kit_tools/specs/`
- `prd/archive/` → `specs/archive/`
- `prd/*.md` → `specs/*.md`
- `../prd/` → `../specs/`

Do NOT modify:
- `prd-{dep}.md` patterns (backwards-compat archive lookups)
- CHANGELOG entries (historical records)

---

## Step 11: Sync Marker Update

If `kit_tools/.kit_tools_sync.json` exists:

1. Update any path values containing `kit_tools/prd/` → `kit_tools/specs/`
2. Update `version` field to `"2.0.0"` if present

---

## Step 12: Summary Report

Report all changes made:

```
Migration Complete: v1.x → v2.0

Directory:
  - kit_tools/prd/ → kit_tools/specs/ ✓

Files renamed:
  - [list any prd-*.md → feature-*.md renames]
  - [MVP_TODO.md → MILESTONES.md if applicable]

Epic files generated:
  - [list any epic-*.md files created]

Config migrated:
  - .execution-config.json: [N] keys renamed ✓  (or "not found")
  - .execution-state.json: [N] keys renamed ✓  (or "not found")

Paths updated:
  - .claude/settings.local.json: [N] commands updated ✓  (or "not found")
  - [N] .md files updated with new paths

Recommended next steps:
  1. Review changes: git diff --stat
  2. Commit: git add -A && git commit -m "chore: migrate kit_tools to v2.0 structure"
  3. Run /kit-tools:start-session to verify everything works
```

---

## Idempotency

Every step is idempotent. Running this skill twice produces the same result:

- Step 1 detects v2.0 and stops if already migrated
- Steps 3-5 use `git mv` which fails safely on already-renamed files
- Steps 6-11 check for existing state before modifying

Safe to run multiple times.

---

## Related Skills

| Skill | When to use |
|-------|-------------|
| `/kit-tools:init-project` | For new projects without existing kit_tools |
| `/kit-tools:start-session` | After migration to verify everything works |
| `/kit-tools:update-kit-tools` | To update hooks and templates from latest plugin |
