# Validate Implementation — Reference

Detailed formats, agent interpolation details, and edge cases for the validate-implementation workflow.

---

## Finding Format

All review steps output findings in this structured format:

```
FINDING:
  category: [quality|security|compliance|testing]
  severity: [critical|warning|info]
  file: [file path or "feature spec" or "test suite"]
  description: [What was found]
  recommendation: [What to do about it]
END_FINDING
```

If no issues found: `NO_FINDINGS: [category]`

---

## Agent Template Interpolation

### Code Quality Agent

Template: `$CLAUDE_PLUGIN_ROOT/agents/code-quality-validator.md`

| Token | Source |
|-------|--------|
| `{{GIT_DIFF}}` | Full branch diff from Step 2 |
| `{{CHANGED_FILES}}` | File list from Step 2 |
| `{{CONVENTIONS_PATH}}` | Path to CONVENTIONS.md (agent reads on-demand) |
| `{{GOTCHAS_PATH}}` | Path to GOTCHAS.md (agent reads on-demand) |
| `{{CODE_ARCH_PATH}}` | Path to CODE_ARCH.md (agent reads on-demand) |

### Security Agent

Template: `$CLAUDE_PLUGIN_ROOT/agents/security-reviewer.md`

| Token | Source |
|-------|--------|
| `{{GIT_DIFF}}` | Full branch diff from Step 2 |
| `{{CHANGED_FILES}}` | File list from Step 2 |
| `{{SECURITY_PATH}}` | Path to SECURITY.md (agent reads on-demand) |
| `{{CODE_ARCH_PATH}}` | Path to CODE_ARCH.md (agent reads on-demand) |

### Feature Spec Compliance Agent

Template: `$CLAUDE_PLUGIN_ROOT/agents/feature-compliance-reviewer.md`

| Token | Source |
|-------|--------|
| `{{SPEC_PATH}}` | Path to the feature spec file |
| `{{GIT_DIFF}}` | Full branch diff from Step 2 |
| `{{CHANGED_FILES}}` | File list from Step 2 |
| `{{CODE_ARCH_PATH}}` | Path to CODE_ARCH.md (agent reads on-demand) |

### Feature Fixer Agent

Template: `$CLAUDE_PLUGIN_ROOT/agents/feature-fixer.md`

| Token | Source |
|-------|--------|
| `{{FINDINGS}}` | Critical findings only |
| `{{GIT_DIFF}}` | Full branch diff |
| `{{CHANGED_FILES}}` | File list |
| `{{CONVENTIONS_PATH}}` | Path to CONVENTIONS.md (agent reads on-demand) |
| `{{CODE_ARCH_PATH}}` | Path to CODE_ARCH.md (agent reads on-demand) |
| `{{RESULT_FILE_PATH}}` | Path to write fix result JSON (`kit_tools/.fix-result.json`) |

---

## Large Diff Handling

When the branch diff exceeds ~60KB, it must be summarized before interpolating into agent prompts to avoid blowing context windows:

1. Split the diff by `diff --git` headers into per-file chunks
2. Allocate a character budget per file (~60KB / number of files)
3. Truncate each file's hunks at the budget limit
4. Append notice: "Full diff truncated. Read individual files for complete changes."

Always include the full `git diff --stat` output — it fits easily and gives agents a structural overview. The truncated-diff note in each agent template instructs them to use the Read tool for full file context.

---

## Feature Spec Compliance Review Details

### 5a: Acceptance Criteria Coverage

For each user story's acceptance criteria:
- Is the criterion addressed by changes in the diff?
- If not, is it pre-existing (already met before this branch)?
- Flag unaddressed criteria as findings

### 5b: Out of Scope Creep

Review the diff for changes that:
- Implement functionality explicitly listed as out of scope
- Add features or capabilities not described anywhere in the feature spec
- Flag scope creep as findings (severity: warning)

### 5c: Intent Alignment

Overall assessment:
- Do the changes accomplish what the feature spec describes?
- Are there significant gaps between the feature spec goals and the implementation?
- Are there TODO comments or placeholder implementations?

---

## AUDIT_FINDINGS.md Format

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

New date headings go at the top of the Active Findings section (newest first).

---

## Re-validation Loop

If fixes were applied in Step 6:

1. Re-capture the branch diff: `git diff main...HEAD`
2. Re-run Steps 3, 4, 4b, and 5 with the updated diff
3. Check if any critical findings remain

**Stop re-validating when:**
- No critical findings remain (warnings and info are acceptable)
- 3 validation loops have been completed (proceed with remaining findings)

If the loop cap is reached, note: "Validation loop cap reached. Remaining findings logged."

---

## Test Command Detection

Auto-detect in order:
1. `package.json` "test" script (skip npm default `echo "Error: no test specified"`)
2. `pyproject.toml` [tool.pytest] section
3. `pytest.ini`
4. `Makefile` "test" target
5. `kit_tools/testing/TESTING_GUIDE.md` Quick Start code block

Test execution timeout: 5 minutes.

### Output Control

Run the full suite with quiet flags to suppress per-test PASSED noise, but preserve full failure output:
- pytest: `-q --tb=short` (remove `-v` if present) — tracebacks for failures, no PASSED spam
- jest: default output (verbose on failure only)
- vitest: default reporter

Pipe through `| head -200` as a safety net for runaway output. Never truncate in a way that hides failure tracebacks or assertion diffs.

### Test Mapping (for story-level targeted tests)

Projects can declare test mappings in `kit_tools/testing/TESTING_GUIDE.md` under a YAML code block:

```yaml
test_mapping:
  "src/memory/**": "tests/test_memory*.py"
  "src/core/**": "tests/test_perception*.py tests/test_context*.py"
```

The orchestrator uses this (plus heuristic name matching) to run only related tests during story verification. The full suite runs only at the validate-implementation gate.

---

## Fix Mode Details

### Autonomous mode

1. Read `$CLAUDE_PLUGIN_ROOT/agents/feature-fixer.md`
2. Interpolate with critical findings, diff, context paths, and `{{RESULT_FILE_PATH}}` (`kit_tools/.fix-result.json`)
3. Spawn via Task tool
4. Read fix results from `kit_tools/.fix-result.json` (JSON with `findings_fixed`, `findings_unfixable`, `files_changed`)

### Supervised/Guarded mode

Fix critical findings inline in the current session:
1. Read the referenced file
2. Apply the recommended fix
3. Verify the fix doesn't introduce new issues
