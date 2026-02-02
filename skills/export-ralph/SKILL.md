---
name: export-ralph
description: Convert a KitTools PRD to ralph's prd.json format for autonomous execution
---

# Export to Ralph

Convert a KitTools PRD to ralph's `prd.json` format for use with the ralph autonomous agent system.

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

## Prerequisites

Before using this skill:

1. **Ralph must be installed** in your project or globally
2. **A KitTools PRD must exist** with `status: active` in frontmatter
3. **User stories must be properly formatted** with US-XXX IDs and acceptance criteria

## Step 1: Select the PRD to export

Check `kit_tools/prd/` for active PRDs:

- List all `prd-*.md` files (excluding `archive/`)
- Show their status from frontmatter
- Ask user which PRD to export (or confirm if only one is active)

```
Active PRDs found:
1. prd-auth.md (3/5 stories complete)
2. prd-payments.md (0/4 stories complete)

Which PRD would you like to export to ralph?
```

## Step 2: Validate PRD structure

Before converting, validate the PRD has required elements:

- [ ] YAML frontmatter with `feature` field
- [ ] At least one user story with US-XXX ID
- [ ] Each story has acceptance criteria
- [ ] Stories are ordered by dependency (schema → backend → UI)

**If validation fails**, report issues and ask user to fix the PRD first.

## Step 3: Generate prd.json

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

## Step 4: Check for existing ralph files

Before writing:

1. **Check if `prd.json` exists**
   - If it exists with a DIFFERENT `branchName`, warn user:
     > "Existing prd.json found for feature '[branch]'. This will be overwritten. Continue?"
   - If same feature, this is an update — proceed

2. **Check if `progress.txt` exists**
   - If yes, leave it alone (ralph manages it)
   - If no, create a fresh one (see Step 5)

## Step 5: Write ralph files

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

## Step 6: Verify and summarize

After writing:

1. **Verify prd.json is valid JSON** (parse it)
2. **Count stories**: X total, Y already passing
3. **Remind about ralph usage**:

```
Export complete!

Created: prd.json (X user stories, Y already passing)
Created: progress.txt (fresh log)

To run ralph:
  ./ralph.sh --tool claude

Or if using Amp:
  ./ralph.sh --tool amp

Note: After ralph completes, run /kit-tools:import-learnings to
capture progress.txt learnings back into your PRD.
```

## Story Ordering Reminder

Ralph executes stories in priority order. The PRD's story order should follow dependency order:

1. **Database/Schema changes** (migrations first)
2. **Backend/API** (server logic)
3. **Frontend/UI** (components that use the backend)

If the PRD's story order seems wrong, warn the user before export.

## Handling Partial Completion

If some stories are already marked complete in the PRD:

- Set `passes: true` for those stories in prd.json
- Ralph will skip completed stories and start with the first `passes: false`

This allows incremental work — you can do some stories manually, then let ralph handle the rest.

## Related Skills

| Skill | When to use |
|-------|-------------|
| `/kit-tools:plan-feature` | To create a PRD before export |
| `/kit-tools:import-learnings` | After ralph completes, to capture learnings |
| `/kit-tools:complete-feature` | After all stories pass, to archive the PRD |
