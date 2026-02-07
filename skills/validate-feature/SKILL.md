---
name: validate-feature
description: Validate a feature branch against its PRD with code quality, security, and compliance checks
---

# Validate Feature

Run a comprehensive validation of a feature branch against its PRD. Reviews the entire branch diff (not just recent changes) for code quality, security vulnerabilities, and PRD compliance. Findings are advisory — they inform but never block other workflows.

## Dependencies

This skill requires the following components:

| Component | Location | Required | Purpose |
|-----------|----------|----------|---------|
| **Quality agent** | `$CLAUDE_PLUGIN_ROOT/agents/code-quality-validator.md` | Yes | Code quality review template |
| **Security agent** | `$CLAUDE_PLUGIN_ROOT/agents/security-reviewer.md` | Yes | Security review template |
| **Fixer agent** | `$CLAUDE_PLUGIN_ROOT/agents/feature-fixer.md` | For autonomous | Targeted fix agent template |
| **Findings template** | `$CLAUDE_PLUGIN_ROOT/templates/AUDIT_FINDINGS.md` | Yes | Template for findings file |
| `kit_tools/prd/*.md` | Yes | PRD with acceptance criteria and requirements |
| `kit_tools/prd/.execution-state.json` | Optional | Execution mode detection |
| `kit_tools/docs/CONVENTIONS.md` | Optional | Project conventions for validation |
| `kit_tools/docs/GOTCHAS.md` | Optional | Known issues to check against |
| `kit_tools/arch/CODE_ARCH.md` | Optional | Architecture patterns to validate |
| `kit_tools/arch/SECURITY.md` | Optional | Security patterns to validate |

**Creates/Updates:**
- `kit_tools/AUDIT_FINDINGS.md` — Findings log (created from template if missing)

**Related hooks:**
- `detect_phase_completion.py` (PostToolUse) — Suggests running this skill after PRD criteria or TODO completion

## Arguments

| Argument | Description |
|----------|-------------|
| `[prd-name]` | Optional: specific PRD to validate against (e.g., `prd-auth`) |

---

## Step 1: Identify Feature

### Determine the PRD

**If `$ARGUMENTS` specifies a PRD name:**
Look for `kit_tools/prd/prd-[argument].md` or `kit_tools/prd/[argument].md`

**If no argument provided:**
1. Check `kit_tools/prd/.execution-state.json` for the `prd` field
2. If no state file, list active PRDs from `kit_tools/prd/` (exclude `archive/`):

```
Active PRDs:

1. prd-auth.md (5/5 stories complete)
2. prd-payments.md (4/4 stories complete)

Which PRD should be validated?
```

### Read the PRD

Once identified, read the full PRD and extract:
- **Overview** — Feature description and goals
- **User Stories** — All stories with acceptance criteria
- **Functional Requirements** — FR-X entries
- **Non-Goals** — Explicit scope boundaries
- **Technical Considerations** — Architecture notes

Store these for PRD compliance review in Step 5.

---

## Step 2: Get Branch Diff

### Determine the branch

Read the PRD frontmatter `feature` field. The feature branch is `feature/[name]`.

Verify we're on the feature branch:
```bash
git branch --show-current
```

If not on the feature branch, warn the user and ask whether to continue validating from the current branch.

### Capture the full branch diff

```bash
git diff main...HEAD
```

This captures ALL changes from the entire feature, not just recent edits. This is the fundamental scope of validate-feature.

Also capture the file list:
```bash
git diff main...HEAD --name-only
```

If the diff is empty, report "No changes found on this branch relative to main" and stop.

---

## Step 3: Code Quality Review

1. Read the agent prompt template from `$CLAUDE_PLUGIN_ROOT/agents/code-quality-validator.md`
2. Read project context files (use "Not available" if missing):
   - `kit_tools/docs/CONVENTIONS.md`
   - `kit_tools/docs/GOTCHAS.md`
   - `kit_tools/arch/CODE_ARCH.md`
3. Replace placeholder tokens in the template:
   - `{{GIT_DIFF}}` → Full branch diff from Step 2
   - `{{CHANGED_FILES}}` → File list from Step 2
   - `{{CONVENTIONS}}` → Contents of CONVENTIONS.md
   - `{{GOTCHAS}}` → Contents of GOTCHAS.md
   - `{{CODE_ARCH}}` → Contents of CODE_ARCH.md
4. Use the Task tool with `subagent_type: "general-purpose"` to run the interpolated prompt
5. Parse `FINDING:` / `END_FINDING` blocks from the response

---

## Step 4: Security Review

1. Read the agent prompt template from `$CLAUDE_PLUGIN_ROOT/agents/security-reviewer.md`
2. Read security context (use "Not available" if missing):
   - `kit_tools/arch/SECURITY.md`
   - `kit_tools/arch/CODE_ARCH.md`
3. Replace placeholder tokens in the template:
   - `{{GIT_DIFF}}` → Full branch diff from Step 2
   - `{{CHANGED_FILES}}` → File list from Step 2
   - `{{SECURITY}}` → Contents of SECURITY.md
   - `{{CODE_ARCH}}` → Contents of CODE_ARCH.md
4. Use the Task tool with `subagent_type: "general-purpose"` to run the interpolated prompt
5. Parse `FINDING:` / `END_FINDING` blocks from the response

**Note:** Steps 3 and 4 can be run in parallel — spawn both subagents at the same time.

---

## Step 5: PRD Compliance Review

This step is performed directly by the skill (not a subagent), because it requires holistic reasoning about the full PRD.

Compare the branch diff from Step 2 against the PRD content from Step 1:

### 5a: Acceptance Criteria Coverage

For each user story's acceptance criteria:
- Is the criterion addressed by changes in the diff?
- If not, is it pre-existing (already met before this branch)?
- Flag unaddressed criteria as findings

### 5b: Functional Requirements Coverage

For each FR-X requirement:
- Is there code in the diff that implements this requirement?
- Flag unaddressed requirements as findings

### 5c: Non-Goal Scope Creep

Review the diff for changes that:
- Implement functionality explicitly listed as a non-goal
- Add features or capabilities not described anywhere in the PRD
- Flag scope creep as findings (severity: warning)

### 5d: Intent Alignment

Overall assessment:
- Do the changes accomplish what the PRD describes?
- Are there significant gaps between the PRD goals and the implementation?
- Are there TODO comments or placeholder implementations?

### Output compliance findings

Use the same structured format:

```
FINDING:
  category: compliance
  severity: [critical|warning|info]
  file: [file path or "PRD"]
  description: [What was found]
  recommendation: [What to do about it]
END_FINDING
```

If no compliance issues exist, note `NO_FINDINGS: compliance`.

---

## Step 6: Process & Fix

### 6a: Aggregate findings

Collect all findings from Steps 3, 4, and 5. Assign each a unique ID in the format `YYYY-MM-DD-NNN` (today's date + sequential number starting at 001).

### 6b: Determine mode

Check `kit_tools/prd/.execution-state.json` for the `mode` field:
- If file exists and `mode` is set → use that mode
- If no file exists → default to `supervised`

### 6c: Apply fixes (critical findings only)

**If no critical findings:** Skip to Step 8.

**If critical findings exist:**

- **Autonomous mode:**
  1. Read `$CLAUDE_PLUGIN_ROOT/agents/feature-fixer.md`
  2. Interpolate with: `{{FINDINGS}}` (critical findings only), `{{GIT_DIFF}}`, `{{CHANGED_FILES}}`, `{{CONVENTIONS}}`, `{{CODE_ARCH}}`
  3. Spawn via Task tool with `subagent_type: "general-purpose"`
  4. Parse `FIX_RESULT:` / `END_FIX_RESULT` from response

- **Supervised/Guarded mode:**
  Fix critical findings inline in the current session. For each critical finding:
  1. Read the referenced file
  2. Apply the recommended fix
  3. Verify the fix doesn't introduce new issues

---

## Step 7: Re-validate (max 3 loops)

If fixes were applied in Step 6:

1. Re-capture the branch diff: `git diff main...HEAD`
2. Re-run Steps 3, 4, and 5 with the updated diff
3. Check if any critical findings remain

**Stop re-validating when:**
- No critical findings remain (warnings and info are acceptable)
- 3 validation loops have been completed (proceed with remaining findings)

If the loop cap is reached, note in the report: "Validation loop cap reached. Remaining findings logged to AUDIT_FINDINGS.md."

---

## Step 8: Log to AUDIT_FINDINGS.md

### 8a: Check for existing file

- Look for `kit_tools/AUDIT_FINDINGS.md` in the project
- If it doesn't exist, copy the template from `$CLAUDE_PLUGIN_ROOT/templates/AUDIT_FINDINGS.md` to `kit_tools/AUDIT_FINDINGS.md`

### 8b: Determine next finding ID

- Read the Active Findings section
- Find the highest existing ID for today's date (if any)
- Re-number findings from the next sequential number

### 8c: Append remaining findings

Under the **Active Findings** section, add a new date heading (if one doesn't exist for today) and append each remaining finding (warnings and info that were not fixed):

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

### 8d: Update timestamp

Update the "Last Updated" line in AUDIT_FINDINGS.md to today's date.

---

## Step 9: Report & Next Step

### Summary format

```
Feature validation complete for [prd-name]:

Branch: feature/[name]
Diff scope: [N] files changed (full branch vs main)
Validation loops: [N]

Findings:
- Critical: [N] ([N] fixed, [N] remaining)
- Warning: [N]
- Info: [N]
- Compliance: [N]

[If critical findings were fixed:]
Fixes applied and committed.

[If unfixable findings remain:]
Unfixable findings logged to kit_tools/AUDIT_FINDINGS.md

All findings written to kit_tools/AUDIT_FINDINGS.md
Note: All findings are advisory.
```

### Next step

- **Autonomous mode:** Auto-invoke `/kit-tools:complete-feature`
- **Other modes:** Suggest running `/kit-tools:complete-feature`

---

## Related Skills

| Skill | When to use |
|-------|-------------|
| `/kit-tools:execute-feature` | To execute PRD stories before validating |
| `/kit-tools:complete-feature` | To archive PRD after validation passes |
| `/kit-tools:plan-feature` | To create a PRD before execution |
| `/kit-tools:start-session` | To orient on active PRDs at session start |

---

## Notes

- **All findings are advisory.** They should inform decisions but never block complete-feature from running.
- **Branch-level scope:** Unlike validate-phase (which reviewed working-tree changes), this skill reviews the entire branch diff against main. This ensures nothing is missed across the full feature implementation.
- **Missing rulebook docs:** If CONVENTIONS.md, GOTCHAS.md, CODE_ARCH.md, or SECURITY.md don't exist, the validators note this and limit checks to general best practices.
- **Manual invocation:** This skill can be run at any time with `/kit-tools:validate-feature`. It is also invoked automatically by the execute orchestrator after all stories complete.
