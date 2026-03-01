---
name: validate-feature
description: Validate a feature branch against its PRD with code quality, security, and compliance checks
---

# Validate Feature

Run a comprehensive validation of a feature branch against its PRD. Reviews the entire branch diff for code quality, security, testing, and PRD compliance.

Read `REFERENCE.md` in this skill directory for detailed finding formats, agent interpolation, and edge cases.

## Dependencies

| Component | Location | Required |
|-----------|----------|----------|
| Quality agent | `$CLAUDE_PLUGIN_ROOT/agents/code-quality-validator.md` | Yes |
| Security agent | `$CLAUDE_PLUGIN_ROOT/agents/security-reviewer.md` | Yes |
| Compliance agent | `$CLAUDE_PLUGIN_ROOT/agents/prd-compliance-reviewer.md` | Yes |
| Fixer agent | `$CLAUDE_PLUGIN_ROOT/agents/feature-fixer.md` | For autonomous |
| Findings template | `$CLAUDE_PLUGIN_ROOT/templates/AUDIT_FINDINGS.md` | Yes |

**Creates/Updates:** `kit_tools/AUDIT_FINDINGS.md`

## Arguments

| Argument | Description |
|----------|-------------|
| `[prd-name]` | Optional: specific PRD to validate against |

---

## Step 1: Identify Feature

Determine PRD from argument, `.execution-state.json`, or by listing active PRDs.
Read full PRD: overview, stories, criteria, FRs, non-goals, tech considerations.

---

## Step 2: Get Branch Diff

```bash
git diff main...HEAD           # Full diff
git diff main...HEAD --name-only  # File list
```

If diff is empty, report and stop.

### Large Diff Handling

If the full diff exceeds ~60KB, summarize before interpolating into agent prompts:
- Include the full `--stat` output (always fits)
- Include the first ~500 characters of each file's diff
- Append a truncation notice: "Full diff truncated. Read individual files for complete changes."
- Agents will use the Read tool to examine full files as needed

---

## Step 3: Code Quality Review

Interpolate `code-quality-validator.md` with diff, file list, and project context.
Spawn via Task tool. Parse `FINDING:` / `END_FINDING` blocks.

---

## Step 4: Security Review

Interpolate `security-reviewer.md` with diff, file list, and security context.
Spawn via Task tool. Parse findings.

---

## Step 4b: Test Execution

1. **Detect test command** — Check: `package.json`, `pyproject.toml`, `pytest.ini`, `Makefile`, `TESTING_GUIDE.md`
2. **Run tests** — Execute with 5-minute timeout
3. **Report findings:**
   - Pass: info finding with test count
   - Fail: critical finding with failure summary
   - No test command: info finding suggesting tests be added

---

## Step 5: PRD Compliance Review

Interpolate `prd-compliance-reviewer.md` with PRD path, diff, file list, and architecture context.
Spawn via Task tool. Parse `FINDING:` / `END_FINDING` blocks.

Reviews:
- **5a: Acceptance criteria** — Is each criterion addressed?
- **5b: Functional requirements** — Is each FR-X implemented?
- **5c: Scope creep** — Changes outside PRD scope? (warning)
- **5d: Intent alignment** — Do changes match PRD goals?

**Steps 3, 4, and 5 can all run in parallel.**

---

## Step 6: Process & Fix

### Aggregate findings from Steps 3, 4, 4b, 5. Assign IDs: `YYYY-MM-DD-NNN`.

### Determine mode from `.execution-state.json` (default: supervised).

### Fix critical findings:
- **Autonomous:** Spawn fixer agent
- **Supervised/Guarded:** Fix inline in current session
- **No criticals:** Skip to Step 8

---

## Step 7: Re-validate (max 3 loops)

If fixes applied: re-capture diff, re-run Steps 3-5. Stop when no criticals or 3 loops done.

---

## Step 8: Log to AUDIT_FINDINGS.md

- Create from template if missing
- Assign sequential IDs for today's date
- Append remaining findings under Active Findings section

---

## Step 9: Report & Next Step

Report: branch, files changed, validation loops, finding counts by severity.

### Pause on critical findings (autonomous mode only)

If autonomous mode AND critical findings remain:
1. Create `kit_tools/.pause_execution` referencing finding count
2. Orchestrator waits until file removed

**No pause for:** supervised/guarded mode, manual invocation, warning/info-only findings.

### Next step

- **Autonomous (no criticals):** Auto-invoke `/kit-tools:complete-feature`
- **Autonomous (criticals):** Pause until `.pause_execution` removed
- **Other modes:** Suggest `/kit-tools:complete-feature`

---

## Notes

- Warning/info findings are advisory. Critical findings pause autonomous execution.
- Step 4b auto-detects and runs the project's test suite. Test failures are critical.
- Missing context docs (CONVENTIONS, GOTCHAS, etc.) — validators use general best practices.
- Can be run manually at any time, or automatically by the orchestrator.
