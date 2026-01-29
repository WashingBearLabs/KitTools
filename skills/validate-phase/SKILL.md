---
name: validate-phase
description: Run code quality, security, and intent alignment validation on recent changes
---

# Validate Phase

Run an automated code quality review on recent changes. Findings are advisory — they inform but never block other workflows.

## Step 1: Determine scope

- Read `kit_tools/SESSION_SCRATCH.md` to identify the active feature and TODO file
- If `$ARGUMENTS` specifies a TODO file (e.g., `FEATURE_TODO_auth.md`), use that instead
- If `$ARGUMENTS` contains `--phase N`, focus validation on that specific phase's intent
- If no scratchpad or arguments are available, validate all uncommitted changes

## Step 2: Gather context

Collect the following inputs for the validator:

### 2a: Git diff

Run `git diff` to capture current uncommitted changes. If there are no uncommitted changes, use `git diff HEAD~1` to capture the last commit's changes. Store the diff output.

### 2b: Phase intent

- Read the identified TODO file from `kit_tools/roadmap/`
- Extract the current phase's **Intent** statement (the line starting with `> **Intent:**` under the active phase heading)
- If `--phase N` was specified, use that phase's intent
- If no phase intent is found, use "General development — no specific phase intent documented"

### 2c: Project rulebook docs

Read each of the following files if they exist. If a file is missing, note "Not available — validation limited to general best practices" for that input:

- `kit_tools/docs/CONVENTIONS.md`
- `kit_tools/docs/GOTCHAS.md`
- `kit_tools/arch/CODE_ARCH.md`
- `kit_tools/arch/SECURITY.md`

### 2d: Changed files list

Run `git diff --name-only` (or `git diff HEAD~1 --name-only` if no uncommitted changes) to get the list of changed files.

## Step 3: Spawn validator subagent

1. Read the agent prompt template from `$CLAUDE_PLUGIN_ROOT/agents/code-quality-validator.md`
2. Replace the placeholder tokens in the template with the gathered context:
   - `{{PHASE_INTENT}}` → Phase intent from Step 2b
   - `{{GIT_DIFF}}` → Git diff output from Step 2a
   - `{{CHANGED_FILES}}` → File list from Step 2d
   - `{{CONVENTIONS}}` → Contents of CONVENTIONS.md (or "Not available" note)
   - `{{GOTCHAS}}` → Contents of GOTCHAS.md (or "Not available" note)
   - `{{CODE_ARCH}}` → Contents of CODE_ARCH.md (or "Not available" note)
   - `{{SECURITY}}` → Contents of SECURITY.md (or "Not available" note)
3. Use the Task tool with `subagent_type: "general-purpose"` to run the interpolated prompt
4. The subagent will return findings in the structured format defined in the template

## Step 4: Process findings

Parse the subagent's response for findings in the structured format:

```
FINDING:
  category: [quality|security|intent]
  severity: [critical|warning|info]
  file: [file path]
  description: [description]
  recommendation: [recommendation]
END_FINDING
```

For each finding:
1. Assign an ID in the format `YYYY-MM-DD-NNN` (today's date + sequential number starting at 001)
2. Set status to `open`
3. Check for `NO_FINDINGS: [pass name]` entries — these indicate clean passes

If the subagent returns no parseable findings at all, note "Validation completed with no findings."

## Step 5: Write to AUDIT_FINDINGS.md

### 5a: Check for existing file

- Look for `kit_tools/AUDIT_FINDINGS.md` in the project
- If it doesn't exist, copy the template from `$CLAUDE_PLUGIN_ROOT/templates/AUDIT_FINDINGS.md` to `kit_tools/AUDIT_FINDINGS.md`

### 5b: Determine next finding ID

- Read the Active Findings section
- Find the highest existing ID for today's date (if any)
- Start numbering from the next sequential number (e.g., if `2025-01-28-003` exists, start at `004`)

### 5c: Append findings

Under the **Active Findings** section, add a new date heading (if one doesn't exist for today) and append each finding:

```markdown
### YYYY-MM-DD

| ID | Category | Severity | File | Status |
|----|----------|----------|------|--------|
| YYYY-MM-DD-001 | quality | warning | `src/auth.py` | open |
| YYYY-MM-DD-002 | security | critical | `src/api/routes.py` | open |

**YYYY-MM-DD-001** — [Description of finding]
> Recommendation: [What to do about it]

**YYYY-MM-DD-002** — [Description of finding]
> Recommendation: [What to do about it]
```

Place new date headings at the top of the Active Findings section (newest first).

### 5d: Update timestamp

Update the "Last Updated" line in AUDIT_FINDINGS.md to today's date.

## Step 6: Report

Provide a summary to the user:

### Summary format

```
Validation complete:
- Critical: N finding(s)
- Warning: N finding(s)
- Info: N finding(s)

[If critical findings exist:]
⚠ Critical findings require attention:
  - [ID]: [brief description]

All findings written to kit_tools/AUDIT_FINDINGS.md
Note: All findings are advisory.
```

If no findings were generated:

```
Validation complete — no findings. Clean pass across all review categories.
```

## Notes

- **All findings are advisory.** They should inform decisions but never block checkpoint or close-session from completing.
- **Git diff scope:** The validator reviews actual code changes, not the entire codebase. This keeps reviews focused and actionable.
- **Missing rulebook docs:** If CONVENTIONS.md, GOTCHAS.md, CODE_ARCH.md, or SECURITY.md don't exist, the validator notes this and limits checks to general best practices.
- **Manual invocation:** This skill can be run at any time with `/kit-tools:validate-phase`. It is also invoked automatically by checkpoint and close-session for code changes.
