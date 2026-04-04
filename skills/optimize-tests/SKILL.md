---
name: optimize-tests
description: Audit the project's test suite for mapping gaps, stale tests, overlap, performance issues, and KitTools alignment
---

# Optimize Tests

Run a full audit of the project's test suite. Produces a structured report with actionable findings across six dimensions: mapping completeness, stale test detection, coverage overlap, performance profiling, KitTools convention alignment, and suite verification.

This skill is for periodic test suite maintenance — run it after completing an epic, when tests feel slow or flaky, or as a monthly health check.

## Dependencies

| Component | Location | Required |
|-----------|----------|----------|
| Test optimizer agent | `$CLAUDE_PLUGIN_ROOT/agents/test-optimizer.md` | Yes |

**Reads:** `kit_tools/testing/TESTING_GUIDE.md`, test files, source files
**Creates:** `kit_tools/.test-optimizer-result.json` (temporary, cleaned up on completion)

## Arguments

None — always runs the full audit.

---

## Step 1: Gather Context

1. Check that `kit_tools/testing/TESTING_GUIDE.md` exists. If not, warn the user:
   > "No TESTING_GUIDE.md found. The audit will still run but mapping completeness checks will be limited. Consider running `/kit-tools:seed-template testing/TESTING_GUIDE` first."

2. Auto-detect the test command:
   - Check `package.json` for a `test` script
   - Check for `pyproject.toml` with `[tool.pytest]`
   - Check for `pytest.ini` or `setup.cfg` with pytest config
   - If none found, ask the user for the test command

3. Count test files and source files for the summary:
   - Test files: `**/test_*.py`, `**/*_test.py`, `**/*.test.{ts,tsx,js,jsx}`, `**/*.spec.{ts,tsx,js,jsx}`
   - Source files: all code files excluding test files, node_modules, .venv, __pycache__

4. Present the audit plan:
   ```
   Test Suite Audit
   ════════════════
   Project: {project directory name}
   Test command: {detected command}
   Test files: {count}
   Source files: {count}
   TESTING_GUIDE: {found/not found}

   Running 6 audit dimensions:
     1. Mapping completeness
     2. Stale test detection
     3. Coverage overlap analysis
     4. Performance profiling
     5. KitTools convention alignment
     6. Full suite verification

   This may take a few minutes for large test suites.
   ```

   Proceed without asking for confirmation — the audit is read-only.

---

## Step 2: Run the Audit

1. Read `$CLAUDE_PLUGIN_ROOT/agents/test-optimizer.md`
2. Interpolate tokens:
   - `{{TESTING_GUIDE_PATH}}` — path to `kit_tools/testing/TESTING_GUIDE.md` (or "Not found" if absent)
   - `{{PROJECT_DIR}}` — absolute path to the project directory
   - `{{TEST_COMMAND}}` — detected test command (or "Not detected — skip suite verification")
   - `{{RESULT_FILE_PATH}}` — `kit_tools/.test-optimizer-result.json`
3. Spawn via Task tool
4. Read `kit_tools/.test-optimizer-result.json`

---

## Step 3: Present Results

Parse the result JSON and present a human-readable report:

```
Test Suite Audit Report
═══════════════════════

Suite Health: {critical/warning/healthy}

Quick Stats:
  Test files: {count}
  Source files: {total} ({mapped} mapped, {unmapped} unmapped)
  Suite result: {passed/failed} ({tests_passed} passed, {tests_failed} failed, {tests_skipped} skipped)
  Suite runtime: {runtime}s

Findings: {critical_count} critical, {warning_count} warnings, {info_count} info

Critical:
  🔴 {finding description} — {file path}
     → {suggestion}

Warnings:
  ⚠️  {finding description} — {file path}
     → {suggestion}

Info:
  ℹ️  {finding description} — {file path}
     → {suggestion}

Top 5 Recommended Actions:
  1. {most impactful finding + fix}
  2. ...
```

Group findings by category for readability. For large result sets (>20 findings), show the top 10 by severity and note "... and {N} more. See full results in kit_tools/.test-optimizer-result.json".

---

## Step 4: Clean Up

Delete `kit_tools/.test-optimizer-result.json`.

If the user wants to keep the raw results, they can re-run the skill — the results are ephemeral by design.

---

## Step 5: Next Steps

Based on the findings, suggest appropriate follow-up:

**If critical findings exist:**
> "Fix the critical issues first — failing tests and broken imports should be resolved before other improvements."

**If mapping gaps are significant (>10 unmapped files):**
> "Consider adding test_mapping entries to TESTING_GUIDE.md for the flagged files. This will improve orchestrator test targeting and prevent heuristic over-matching."

**If the suite is healthy:**
> "Test suite looks good! Consider running this audit again after your next epic completion."

---

## Related Skills

| Skill | When to use |
|-------|-------------|
| `/kit-tools:seed-template testing/TESTING_GUIDE` | To create a TESTING_GUIDE.md if one doesn't exist |
| `/kit-tools:execute-epic` | After fixing test issues — the orchestrator will benefit from improved mappings |
| `/kit-tools:validate-implementation` | Uses test results as part of feature validation |
