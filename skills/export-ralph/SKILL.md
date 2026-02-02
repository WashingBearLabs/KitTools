---
name: export-ralph
description: Convert a KitTools PRD to ralph's prd.json format for autonomous execution
---

# Export to Ralph

Convert a KitTools PRD to ralph's `prd.json` format for use with the ralph autonomous agent system.

## Your Role as Senior Dev

**You are the gatekeeper for Ralph exports.** Your job is to ensure PRDs are properly scoped for autonomous execution. This means:

- **Validate before exporting** — Check that the PRD meets Ralph-ready criteria
- **Warn on scope issues** — Large PRDs will fail; flag them clearly
- **Recommend decomposition** — If a PRD is too big, suggest running `plan-feature` to split it

When you identify issues, be direct:
> "This PRD has 12 user stories and 48 acceptance criteria. Ralph will likely exhaust context before completing. I strongly recommend decomposing this into smaller PRDs first."

Your goal is successful Ralph executions, not just exports.

---

## Dependencies

This skill requires:

| File | Required | Purpose |
|------|----------|---------|
| `kit_tools/prd/prd-*.md` | Yes | Source PRD to convert |
| Ralph installation | Yes | Target system for prd.json |

**Creates:**
- `prd.json` — Ralph-format task list at project root
- `progress.txt` — Ralph learnings log (if doesn't exist)

**Related:**
- `/kit-tools:plan-feature` — Creates the source PRD
- `/kit-tools:import-learnings` — Imports ralph learnings back to PRD after completion

---

## Prerequisites

Before using this skill:

1. **Ralph must be installed** in your project or globally
2. **A KitTools PRD must exist** with `status: active` in frontmatter
3. **User stories must be properly formatted** with US-XXX IDs and acceptance criteria

---

## Step 1: Select the PRD to export

Check `kit_tools/prd/` for active PRDs:

- List all `prd-*.md` files (excluding `archive/`)
- Show their status and `ralph_ready` flag from frontmatter
- Ask user which PRD to export (or confirm if only one is active)

```
Active PRDs found:

1. prd-auth-schema.md (0/3 stories) — ralph_ready: ✓
2. prd-auth-api.md (0/5 stories) — ralph_ready: ✓
3. prd-payments.md (0/12 stories) — ralph_ready: ✗ (needs decomposition)

Which PRD would you like to export to ralph?
```

---

## Step 2: Ralph-readiness validation (CRITICAL)

**Before converting, validate the PRD is properly scoped for Ralph.**

### Check 1: Frontmatter `ralph_ready` field

```yaml
ralph_ready: true   # ✓ Proceed
ralph_ready: false  # ⚠️ Warning required
# missing field      # Treat as needing validation
```

### Check 2: Story count

| Stories | Assessment | Action |
|---------|------------|--------|
| 1-4 | Excellent | Proceed |
| 5-7 | Good | Proceed |
| 8-10 | Warning | Soft warning, recommend split |
| 11+ | Too large | Strong warning, recommend decomposition |

### Check 3: Acceptance criteria count

| Total Criteria | Assessment | Action |
|----------------|------------|--------|
| ≤25 | Good | Proceed |
| 26-35 | Warning | Soft warning |
| 36+ | Too large | Strong warning |

### Check 4: Story complexity

Flag if ANY story has:
- More than 6 acceptance criteria (story too big)
- Multiple layers mentioned (DB + API + UI in one story)
- Vague criteria ("works correctly", "handles properly")

### Validation output

**If all checks pass:**
```
✓ PRD validation passed
  - 5 user stories
  - 18 acceptance criteria
  - ralph_ready: true

Proceeding with export...
```

**If warnings detected:**
```
⚠️ PRD validation warnings

This PRD may be too large for reliable Ralph execution:

| Check | Value | Target | Status |
|-------|-------|--------|--------|
| Stories | 12 | ≤7 | ⚠️ Over limit |
| Criteria | 48 | ≤35 | ⚠️ Over limit |
| ralph_ready | false | true | ⚠️ Not ready |

**Risk:** Ralph may exhaust context before completing all stories,
leading to incomplete implementation or errors.

**Recommendation:** Run `/kit-tools:plan-feature` to decompose this
into 2-3 smaller PRDs before exporting.

Do you want to:
A. Export anyway (not recommended)
B. Cancel and decompose first (recommended)
```

### If user chooses to export anyway

Proceed but add a warning to the summary:
> "⚠️ Exported with warnings. Monitor Ralph closely for context exhaustion."

---

## Step 3: Validate PRD structure

Before converting, validate the PRD has required elements:

- [ ] YAML frontmatter with `feature` field
- [ ] At least one user story with US-XXX ID
- [ ] Each story has acceptance criteria
- [ ] Stories are ordered by dependency (schema → backend → UI)
- [ ] `depends_on` PRDs are completed (if specified)

### Dependency check

If the PRD has `depends_on: [other-feature]`:

1. Check if `prd-other-feature.md` exists
2. Check if its status is `completed`
3. If not completed, warn:

> "This PRD depends on `prd-other-feature.md` which is not yet completed.
> Running Ralph on this PRD may fail due to missing prerequisites.
>
> Continue anyway? (y/N)"

**If validation fails**, report issues and ask user to fix the PRD first.

---

## Step 4: Generate prd.json

Convert the PRD to ralph's JSON format:

```json
{
  "project": "[Project name from SYNOPSIS.md or directory name]",
  "branchName": "ralph/[feature-name-from-frontmatter]",
  "description": "[From PRD Overview section]",
  "userStories": [
    {
      "id": "US-001",
      "title": "[Story title]",
      "description": "[Story description]",
      "acceptanceCriteria": [
        "[Criterion 1]",
        "[Criterion 2]",
        "Typecheck passes"
      ],
      "priority": 1,
      "passes": false,
      "notes": ""
    }
  ]
}
```

### Conversion rules:

1. **project**: Extract from `kit_tools/SYNOPSIS.md` title or use directory name
2. **branchName**: `ralph/` + feature name from frontmatter (kebab-case)
3. **description**: First paragraph of Overview section
4. **userStories**: Convert each `### US-XXX` section
5. **priority**: Sequential based on story order (first story = 1)
6. **passes**:
   - `true` if ALL acceptance criteria are checked (`[x]`)
   - `false` if ANY criterion is unchecked (`[ ]`)
7. **notes**: Empty string (ralph populates this during execution)

### Acceptance criteria handling:

- Extract each checkbox item under "Acceptance Criteria"
- Remove the `- [ ]` or `- [x]` prefix, keep just the text
- **Always ensure** "Typecheck passes" or "Typecheck/lint passes" is included
- For UI stories, ensure "Verify in browser" is included

---

## Step 5: Check for existing ralph files

Before writing:

1. **Check if `prd.json` exists**
   - If it exists with a DIFFERENT `branchName`, warn user:
     > "Existing prd.json found for feature '[branch]'. This will be overwritten. Continue?"
   - If same feature, this is an update — proceed

2. **Check if `progress.txt` exists**
   - If yes, leave it alone (ralph manages it)
   - If no, create a fresh one (see Step 6)

---

## Step 6: Write ralph files

### Write prd.json

Save to project root (same level as `kit_tools/`):

```
project/
├── prd.json          ← Write here
├── progress.txt      ← Create if needed
└── kit_tools/
    └── prd/
        └── prd-auth.md  ← Source
```

### Create progress.txt (if needed)

If `progress.txt` doesn't exist, create it:

```markdown
# Ralph Progress Log

Started: [current date/time]
Feature: [feature name]
Source PRD: kit_tools/prd/[filename]

---

## Codebase Patterns

<!-- Add reusable patterns discovered during implementation -->

---

```

---

## Step 7: Verify and summarize

After writing:

1. **Verify prd.json is valid JSON** (parse it)
2. **Count stories**: X total, Y already passing
3. **Report validation status**
4. **Remind about ralph usage**

### Success summary (no warnings):

```
✓ Export complete!

PRD: prd-auth-schema.md
Created: prd.json (3 user stories, 0 already passing)
Created: progress.txt (fresh log)

To run ralph:
  ./ralph.sh --tool claude

Or if using Amp:
  ./ralph.sh --tool amp

After ralph completes, run /kit-tools:import-learnings to
capture progress.txt learnings back into your PRD.
```

### Success summary (with warnings):

```
⚠️ Export complete (with warnings)

PRD: prd-payments.md
Created: prd.json (12 user stories, 0 already passing)

WARNING: This PRD exceeds recommended limits:
- 12 stories (recommended: ≤7)
- 48 acceptance criteria (recommended: ≤35)

Ralph may exhaust context before completing. Monitor closely.
Consider decomposing and re-exporting if Ralph fails.

To run ralph:
  ./ralph.sh --tool claude
```

---

## Story Ordering Reminder

Ralph executes stories in priority order. The PRD's story order should follow dependency order:

1. **Database/Schema changes** (migrations first)
2. **Backend/API** (server logic)
3. **Frontend/UI** (components that use the backend)

If the PRD's story order seems wrong, warn the user before export.

---

## Handling Partial Completion

If some stories are already marked complete in the PRD:

- Set `passes: true` for those stories in prd.json
- Ralph will skip completed stories and start with the first `passes: false`

This allows incremental work — you can do some stories manually, then let ralph handle the rest.

---

## Handling PRD Dependencies

If exporting a PRD that is part of an epic:

1. Check `depends_on` field in frontmatter
2. Verify dependent PRDs are completed
3. Suggest export order if multiple PRDs need to be run

```
This PRD is part of the OAuth epic:

Export/execution order:
1. ✓ prd-oauth-schema.md (completed)
2. → prd-oauth-provider.md (this export)
3.   prd-oauth-api.md (pending)
4.   prd-oauth-ui.md (pending)

Proceeding with export...
```

---

## Related Skills

| Skill | When to use |
|-------|-------------|
| `/kit-tools:plan-feature` | To create a PRD before export, or to decompose a large PRD |
| `/kit-tools:import-learnings` | After ralph completes, to capture learnings |
| `/kit-tools:complete-feature` | After all stories pass, to archive the PRD |
