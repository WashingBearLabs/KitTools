---
name: bump-version
description: Bump project version using the project's BUMP_VERSION.md runbook
---

# Bump Version

Bump the project version using the project-specific runbook at `kit_tools/BUMP_VERSION.md`. The runbook tells this skill where the version lives, what extra files or repos need updating, and how to commit the result.

This skill is also invoked as an optional final step by `/kit-tools:complete-implementation`.

## Dependencies

| File | Required | Purpose |
|------|----------|---------|
| `kit_tools/BUMP_VERSION.md` | Yes | Project-specific version runbook |

---

## Step 1: Read the Runbook

Read `kit_tools/BUMP_VERSION.md`. If it doesn't exist, tell the user:

> "No version runbook found at `kit_tools/BUMP_VERSION.md`. Run `/kit-tools:seed-template BUMP_VERSION.md` to create one, or create it manually from the template."

Stop.

Parse the runbook to extract:
- **Version source**: file path, format, and field path
- **Changelog**: file path and format (if any)
- **Pre-bump steps**: commands or checks to run before bumping
- **Additional version locations**: other files or external repos to update
- **Post-bump steps**: commands to run after updating versions
- **Commit convention**: message format, tag, and branch strategy

---

## Step 2: Read Current Version

Read the version source file identified in the runbook. Extract the current version using the format and field path specified.

Display:

```
Current version: X.Y.Z
Source: [file path] → [field path]
```

---

## Step 3: Determine New Version

Ask the user:

```
Current version: X.Y.Z

What should the new version be?
  A. Patch (X.Y.Z+1) — bug fixes, cleanup
  B. Minor (X.Y+1.0) — new features, non-breaking changes
  C. Major (X+1.0.0) — breaking changes
  D. Custom — specify version
```

If the runbook's Versioning Strategy section has project-specific guidance (not the default semver boilerplate), include it as context above the options.

Store the new version as `$NEW_VERSION`.

---

## Step 4: Run Pre-Bump Steps

If the runbook defines pre-bump steps, execute them in order. If any step fails, report the failure and ask the user whether to continue or abort.

If no pre-bump steps are defined, skip this step.

---

## Step 5: Update Version Source

Update the canonical version file identified in Step 1.

For common formats:
- **json**: Update the field at the specified path (preserve formatting)
- **toml**: Update the field at the specified path
- **yaml**: Update the field at the specified path
- **plain**: Replace the version string

---

## Step 6: Update Changelog

If the runbook specifies a changelog file:

1. Check if a `$NEW_VERSION` entry already exists
2. **If it exists**: Show it to the user and confirm it looks correct
3. **If it doesn't exist**: Ask the user to describe what changed, then create the entry following the changelog's existing format and conventions

If no changelog is configured, skip this step.

---

## Step 7: Update Additional Version Locations

If the runbook defines additional version locations, update each one in order.

### Files in this repo

Update each listed file at the specified location. Show each update as it happens.

### External repos

For each external repo listed:
1. Verify the repo path exists
2. Read the file and find the current version reference
3. Update it to `$NEW_VERSION`
4. Show what was changed

**Do not commit or push external repos** — just make the edits. The commit step handles this repo; external repos are noted in the summary for the user to commit separately, or the runbook's commit convention may specify how to handle them.

---

## Step 8: Run Post-Bump Steps

If the runbook defines post-bump steps, execute them in order. If any step fails, report the failure and ask the user whether to continue or abort.

If no post-bump steps are defined, skip this step.

---

## Step 9: Commit

Using the commit convention from the runbook:

1. Stage all modified files in this repo
2. Create the commit with the configured message format (interpolate `$NEW_VERSION`)
3. If a tag is specified, create it
4. If the convention says to create a release branch, do so

If no commit convention is configured, use the default:
```
release: v$NEW_VERSION
```

---

## Step 10: Summary

```
Version bumped: [OLD] → [NEW_VERSION]

This repo:
  - [version source file] ✓
  - [changelog file] ✓ (or skipped)
  - [additional file 1] ✓
  - [additional file 2] ✓
  Committed: [commit hash] "[commit message]"

External repos (uncommitted — review and push manually):
  - [repo path]: [file] updated
  - [repo path]: [file] updated

Next steps:
  - Push this repo: git push
  - Review and commit external repos listed above
```

If no external repos were involved, omit that section.

---

## Related Skills

| Skill | When to use |
|-------|-------------|
| `/kit-tools:complete-implementation` | Invokes bump-version as an optional final step |
| `/kit-tools:seed-template` | Seed the BUMP_VERSION.md template if it doesn't exist |
