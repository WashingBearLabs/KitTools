---
name: validate-implementation
description: Validate a feature branch against its feature spec with code quality, security, and compliance checks
---

# Validate Implementation

Run a comprehensive validation of a feature branch against its feature spec. Reviews the entire branch diff for code quality, security, testing, and feature spec compliance.

Read `REFERENCE.md` in this skill directory for detailed finding formats, agent interpolation, and edge cases.

## Dependencies

| Component | Location | Required |
|-----------|----------|----------|
| Quality agent | `$CLAUDE_PLUGIN_ROOT/agents/code-quality-validator.md` | Yes |
| Security agent | `$CLAUDE_PLUGIN_ROOT/agents/security-reviewer.md` | Yes |
| Compliance agent | `$CLAUDE_PLUGIN_ROOT/agents/feature-compliance-reviewer.md` | Yes |
| Fixer agent | `$CLAUDE_PLUGIN_ROOT/agents/feature-fixer.md` | For autonomous |
| Findings template | `$CLAUDE_PLUGIN_ROOT/templates/AUDIT_FINDINGS.md` | Yes |

**Creates/Updates:** `kit_tools/AUDIT_FINDINGS.md`

## Arguments

| Argument | Description |
|----------|-------------|
| `[feature-name]` | Optional: specific feature spec to validate against |

---

## Step 0: Resolve the working directory

Autonomous/guarded executions run in an isolated worktree. Determine where to validate:

```bash
python3 "$CLAUDE_PLUGIN_ROOT/scripts/orchestrator/registry.py" census
```

- **Orchestrator-invoked** (the common case): you are already running with the worktree as your cwd — set `EXEC_DIR` = `.` (the current directory) and proceed. `git diff main...HEAD` is correct here because HEAD is the feature branch in this worktree.
- **Manual invocation from the main checkout, and a census record matches this feature:** the branch's work lives in that record's `worktree`, not your cwd (`main...HEAD` would be empty). Set `EXEC_DIR` = the record's `worktree` and run all git/diff/agent steps **there** (or diff `main...<record.branch>`).
- **No record (supervised/manual in-dir):** set `EXEC_DIR` = current project root and proceed as before.

Every `kit_tools/...` path and git command below runs relative to `EXEC_DIR`. Resolve it once and substitute the **literal absolute path** into each command — it isn't a shell variable that persists between separate command invocations.

---

## Step 1: Identify Feature

Determine feature spec from argument, `$EXEC_DIR/kit_tools/specs/.execution-state.json`, or by listing active feature specs.
Read full feature spec: overview, stories, criteria, out of scope, tech considerations.

### Epic-wide validation

If the invocation names an **epic** rather than a single feature spec ("for epic \<name\>" — the orchestrator's final pass after all specs complete, or a manual whole-epic audit), the subject is the **entire assembled branch against ALL of the epic's feature specs together**:

- Gather every feature spec belonging to the epic. After an epic run they live in `$EXEC_DIR/kit_tools/specs/archive/` (the orchestrator archives each as it completes; its prompt lists the exact paths). For a manual audit, match active + archived specs by their `epic:` frontmatter field.
- Read **all** of them. Every later step that interpolates "the feature spec" gets the **full spec list** — most importantly Step 5: a compliance review fed only one spec audits that spec's criteria and silently ignores the rest of the epic.
- Tell the compliance reviewer this is a cross-spec pass: acceptance criteria from one spec may have production call sites introduced by a different spec, and criteria checked off spec-by-spec can still be unmet on the assembled branch (e.g. a protection verified against a helper in isolation but never applied at the call site a later story wired). That integration seam is exactly what the per-spec validations could not see.

---

## Step 2: Get Branch Diff

Run from `EXEC_DIR` (in the worktree, HEAD is the feature branch):

```bash
git -C "$EXEC_DIR" diff main...HEAD              # Full diff
git -C "$EXEC_DIR" diff main...HEAD --name-only  # File list
```

If diff is empty, report and stop.

### Large Diff Handling

If the full diff exceeds ~60KB, summarize before interpolating into agent prompts:
- Include the full `--stat` output (always fits)
- Include the first ~500 characters of each file's diff
- Append a truncation notice: "Full diff truncated. Read individual files for complete changes."
- Agents will use the Read tool to examine full files as needed

---

> **Run the three reviews in parallel.** Steps 3, 4, and 5 spawn independent, read-only reviewer agents that write to separate result files — **spawn all three via the Task tool in a single message** so they run concurrently, then collect all three result files. Do not run them one after another. (Step 4b, test execution, is deterministic and runs alongside them.)

> **Model selection (read once).** Resolve the `reviewer` role from `kit_tools/model_preferences.json` and apply it to all three reviewer Task calls below — pass it as each call's `model` parameter, or omit `model` when the role is unset (the agent runs on the session model). If the file doesn't exist, present the canonical Selection menu **once**, write the file, then proceed; don't prompt on later runs. See `$CLAUDE_PLUGIN_ROOT/skills/configure-models/REFERENCE.md` → "Lazy first-run contract". Users change choices via `/kit-tools:configure-models`.

## Step 3: Code Quality Review

Interpolate `code-quality-validator.md` with diff, file list, and project context (include `{{RESULT_FILE_PATH}} = kit_tools/.validate_impl_quality.json`).
Spawn via Task tool. The agent writes findings to the result file using the unified Finding Schema (see `$CLAUDE_PLUGIN_ROOT/agents/FINDING_SCHEMA.md`); read that file and parse the `findings[]` array.

---

## Step 4: Security Review

Interpolate `security-reviewer.md` with diff, file list, and security context (include `{{RESULT_FILE_PATH}} = kit_tools/.validate_impl_security.json`).
Spawn via Task tool. Read the result file, parse `findings[]` using the unified Finding Schema.

---

## Step 4b: Test Execution

1. **Detect test command** — Check in this order, **first hit wins** (this matches the orchestrator's `detect_test_command`, so manual and autonomous validation behave identically): `package.json` test script → `pyproject.toml` → `pytest.ini` → `Makefile` test target → `kit_tools/testing/TESTING_GUIDE.md` Quick Start command. TESTING_GUIDE.md is the *fallback*, not an override — if its command disagrees with the manifest's, surface that as a docs-drift info finding.
2. **Run tests with minimal output** — Execute with 5-minute timeout. Use quiet flags to suppress per-test PASSED lines:
   - pytest: add `-q --tb=short` (and remove `-v` if present) — suppresses passing tests, preserves failure tracebacks
   - jest: default output is fine (only verbose on failure)
   - vitest: default reporter is fine
   - Pipe through `| head -200` as a safety net for runaway output, but let failure details (tracebacks, assertion diffs) flow in full
3. **Report findings:**
   - Pass: info finding with test count
   - Fail: critical finding with failure summary including traceback details
   - No test command: info finding suggesting tests be added
4. **Account for a pre-existing (baseline) failure set (issue #6).** A full-suite run cannot by itself tell an epic-introduced regression from a test that was *already red at the merge base*. Before treating any failure as blocking:
   - **Autonomous runs** — the orchestrator injects a `BASELINE:` section into this validation's prompt listing the tests that already failed before the epic began. Treat any failure in that list as **pre-existing/informational**, never blocking. Only failures **not** in the baseline list may raise a critical finding. If the baseline says the suite was red but could not enumerate node ids (non-pytest runner), do not treat a red full-suite result as a regression without confirming the specific failures are new — focus the gate on the epic's diff and acceptance criteria.
   - **Manual runs** — if no baseline was provided, and a failure looks unrelated to the diff (touches files/areas the change did not modify), run that same test against the merge base (`git stash` or a scratch checkout of `main`) to check whether it was already failing. Report confirmed pre-existing failures as informational docs/health findings, not blocking regressions.
   - A gate that says "3 new failures, 7 pre-existing" is actionable; a bare `passed=false` on a red baseline is not.

---

## Step 5: Feature Spec Compliance Review

Interpolate `feature-compliance-reviewer.md` with feature spec path, diff, file list, and architecture context (include `{{RESULT_FILE_PATH}} = kit_tools/.validate_impl_compliance.json`).
Spawn via Task tool. Read the result file, parse `findings[]` using the unified Finding Schema.

**Epic-wide validation:** interpolate `{{SPEC_PATH}}` with the full list of the epic's spec paths (newline-separated) and instruct the reviewer to check every spec's acceptance criteria against the assembled branch, flagging cross-spec integration gaps explicitly (see Step 1).

Reviews:
- **5a: Acceptance criteria** — Is each criterion addressed?
- **5b: Scope creep** — Changes outside feature spec scope? (warning)
- **5c: Intent alignment** — Do changes match feature spec goals?

**Steps 3, 4, and 5 are spawned together in one message (see the note above Step 3) — collect all three result files before moving on.**

---

## Step 6: Process & Fix

### Aggregate findings from Steps 3, 4, 4b, 5.

All findings arrive in the same shape (unified Finding Schema), so merging them is straightforward: concatenate each review's `findings[]` array, tagging each entry with its `review_type` so later presentation can group by source. Assign IDs: `YYYY-MM-DD-NNN`. Each result file also carries `canonical_verdict` (`ready|needs-work|not-ready`) alongside the native `overall_verdict` — prefer it when summarizing per-reviewer verdicts; fall back to the native field for results from pre-2.7.0 agents.

### Determine mode from `$EXEC_DIR/kit_tools/specs/.execution-state.json` (default: supervised).

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
1. Create `$EXEC_DIR/kit_tools/.pause_execution` referencing finding count (the orchestrator watches the worktree's copy)
2. Orchestrator waits until file removed

**No pause for:** supervised/guarded mode, manual invocation, warning/info-only findings.

### Next step

- **Autonomous (no criticals):** Auto-invoke `/kit-tools:complete-implementation`
- **Autonomous (criticals):** Pause until `.pause_execution` removed
- **Other modes:** Suggest `/kit-tools:complete-implementation`

---

## Notes

- Warning/info findings are advisory. Critical findings pause autonomous execution.
- Step 4b auto-detects and runs the project's test suite. Test failures are critical.
- Missing context docs (CONVENTIONS, GOTCHAS, etc.) — validators use general best practices.
- Can be run manually at any time, or automatically by the orchestrator.
