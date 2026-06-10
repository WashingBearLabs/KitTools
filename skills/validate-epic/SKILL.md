---
name: validate-epic
description: Validate an epic's feature specs before execution — completeness, story quality, adversarial review, codebase fit, security review, and cross-model second opinion
---

# Validate Epic

Run six parallel pre-execution reviews on an epic's feature specs before handing off to `/kit-tools:execute-epic`. Catches missing stories, vague criteria, bad story IDs, implementation gaps, codebase mismatches, security risks, and architectural blind spots that would cause retries or failures during autonomous execution.

This skill is the quality gate between planning and execution.

## Dependencies

| Component | Location | Required |
|-----------|----------|---------|
| Completionist agent | `$CLAUDE_PLUGIN_ROOT/agents/spec-completionist-reviewer.md` | Yes |
| Story quality agent | `$CLAUDE_PLUGIN_ROOT/agents/story-quality-reviewer.md` | Yes |
| Salty engineer agent | `$CLAUDE_PLUGIN_ROOT/agents/salty-engineer-reviewer.md` | Yes |
| Codebase fit agent | `$CLAUDE_PLUGIN_ROOT/agents/codebase-fit-reviewer.md` | Yes |
| Security agent | `$CLAUDE_PLUGIN_ROOT/agents/spec-security-reviewer.md` | Yes |
| Second opinion agent | `$CLAUDE_PLUGIN_ROOT/agents/spec-second-opinion.md` | Yes |

**Reads:** `kit_tools/specs/epic-*.md`, `kit_tools/specs/feature-*.md`, `kit_tools/PRODUCT_VISION.md` (if exists)
**Creates (temporary):** `kit_tools/.validate_epic_1.json` through `kit_tools/.validate_epic_6.json`
**Cleans up:** Deletes temp result files on completion

## Arguments

| Argument | Description |
|----------|-------------|
| `[epic-name]` | Optional: specific epic to validate (e.g., `oauth`, `payments`) |

---

## Step 1: Identify the Epic

### If argument provided
Look for `kit_tools/specs/epic-[epic-name].md`. If not found, report and stop.

### If no argument
List all `epic-*.md` files in `kit_tools/specs/` (not in archive/). For each, show:
- Epic name
- Number of feature specs in the Decomposition table
- Number of those specs that are active vs. completed/archived

Ask the user which epic to validate.

### Vision context
Check if `kit_tools/PRODUCT_VISION.md` exists. Set `VISION_CONTEXT` for agent interpolation:
- If exists: `"Read kit_tools/PRODUCT_VISION.md for strategic context."`
- If not: `"No product vision document available."`

---

## Step 2: Identify Feature Specs

Read the selected `epic-*.md` file. Parse the Decomposition table to get the ordered list of feature specs.

For each spec in the table:
- Check if it exists in `kit_tools/specs/` (active) or `kit_tools/specs/archive/` (completed)
- Exclude already-archived/completed specs — they've already been executed

**If all specs are archived:** Report that the epic is complete and stop.

**Present the validation plan:**
```
Epic: [epic-name]
Validating [N] active feature spec(s):
  1. feature-foo-schema.md
  2. feature-foo-api.md
  3. feature-foo-ui.md

Running 6 reviews per spec (in parallel):
  1. Completionist — are we missing anything?
  2. Story Quality — are stories well-formed and right-sized?
  3. Salty Engineer — what will blow up in implementation?
  4. Codebase Fit — does the plan fit the existing code?
  5. Security — does this introduce security risks?
  6. Second Opinion (cross-model) — is there a better way to do this?
```

### Quick tier (optional, user's choice — never auto-selected)

The full 6-reviewer panel is the default. **If — and only if — the epic looks small and low-risk**, you may *suggest* the quick tier alongside it, but the **user decides; never silently run fewer reviewers on your own judgment.**

Suggest quick tier only when ALL of these hold for every active spec:
- ≤ 3 stories and `size:` frontmatter absent or S/M
- `session_ready` is not `false`
- No security-touching signals in the spec text (auth, login, session, token, secret, permission, payment, PII, upload, webhook, external API)

When suggesting, present both options with the trade-off:

```
This epic is small ([N] stories, no security surface). Choose validation depth:
  A. Full panel — all 6 reviewers (recommended default)
  B. Quick tier — Completionist + Salty Engineer + Security (3 reviewers; skips
     Story Quality, Codebase Fit, and the cross-model Second Opinion)
```

If the user picks quick tier, run reviewers 1, 3, and 5 only (same result files, same flow); note in the epic-level summary that the quick tier was used. If any quick-tier reviewer returns a critical finding, recommend escalating that spec to the full panel.

Confirm before proceeding.

---

## Step 3: Per-Spec Review Loop

For each active feature spec (in epic order), spawn all six reviewers in parallel, collect results, then present consolidated findings.

### 3a: Spawn All Reviewers (parallel)

Read all six agent templates from `$CLAUDE_PLUGIN_ROOT/agents/`, interpolate their tokens, and spawn all six via the Task tool **in a single message** so they run concurrently.

| # | Agent | Template | Result File | Tokens | Notes |
|---|-------|----------|-------------|--------|-------|
| 1 | Completionist | `spec-completionist-reviewer.md` | `kit_tools/.validate_epic_1.json` | `SPEC_PATH`, `SPEC_NAME`, `VISION_CONTEXT`, `RESULT_FILE_PATH` | |
| 2 | Story Quality | `story-quality-reviewer.md` | `kit_tools/.validate_epic_2.json` | `SPEC_PATH`, `SPEC_NAME`, `RESULT_FILE_PATH` | |
| 3 | Salty Engineer | `salty-engineer-reviewer.md` | `kit_tools/.validate_epic_3.json` | `SPEC_PATH`, `SPEC_NAME`, `VISION_CONTEXT`, `RESULT_FILE_PATH` | |
| 4 | Codebase Fit | `codebase-fit-reviewer.md` | `kit_tools/.validate_epic_4.json` | `SPEC_PATH`, `SPEC_NAME`, `RESULT_FILE_PATH` | Explores actual source code |
| 5 | Security | `spec-security-reviewer.md` | `kit_tools/.validate_epic_5.json` | `SPEC_PATH`, `SPEC_NAME`, `VISION_CONTEXT`, `RESULT_FILE_PATH` | Adversarial security review |
| 6 | Second Opinion | `spec-second-opinion.md` | `kit_tools/.validate_epic_6.json` | `SPEC_PATH`, `SPEC_NAME`, `VISION_CONTEXT`, `RESULT_FILE_PATH` | Cross-model (see below) |

**Second Opinion model choice:** This review deliberately uses a **different model** than the other five. The value comes from different training surfacing different blind spots.
- If the session is running on Opus, use `model: "sonnet"` for this agent.
- If the session is running on Sonnet, use `model: "opus"`.
- If the user has specified a model via `model_config.reviewer_second_opinion`, honor that.

**How to detect the session model:** you know your own model from your system prompt (the environment section names it). If it names Opus or Sonnet, apply the rules above. If it names anything else (Haiku, a newer family, unknown), default to `model: "opus"` for this agent — the goal is simply a *different* training than the one reviewing everything else.

### 3b: Present Consolidated Findings

Once all six agents complete, read all result files and present findings grouped by reviewer. Every result file carries both a native verdict and `canonical_verdict` (`ready|needs-work|not-ready`, see FINDING_SCHEMA.md) — prefer `canonical_verdict` when aggregating; fall back to the native field for results from pre-2.7.0 agents.

```
Review Results — [spec-name]
═══════════════════════════════════════

| Reviewer | Verdict | Critical | Warnings | Info |
|----------|---------|----------|----------|------|
| Completionist | ready | 0 | 0 | 1 |
| Story Quality | needs-work | 0 | 3 | 2 |
| Salty Engineer | needs-work | 1 | 2 | 0 |
| Codebase Fit | needs-work | 0 | 4 | 1 |
| Security | needs-work | 0 | 2 | 1 |
| Second Opinion | ready | 0 | 1 | 0 |
```

Then present findings by severity across all reviewers — critical first, then warnings, then info. For each finding, prefix with the reviewer name so the user knows the source.

**Presentation notes per reviewer:**
- **Salty Engineer**: Preserve the engineer's direct voice — don't sanitize critique fields
- **Codebase Fit**: Always include the `evidence` block (existing code reference + what the spec proposes) — this is what makes the finding actionable
- **Security**: Lead with the biggest risk. Group findings by lens (attack surface, auth, data exposure, input trust, omissions) when there are many. Omission findings are often the most important — highlight them.
- **Second Opinion**: Include trade-offs for alternative-approach and over-engineering findings
- **Story Quality**: Include the per-story status table if present

### 3c: Fix and Re-run

After presenting all findings, ask the user:

> **[N] findings across [M] reviewers. Would you like to:**
> - **A.** Update the spec and re-run specific reviewers
> - **B.** Note findings as known risks and continue to the next spec
> - **C.** Stop and address findings before continuing

If the user picks **A**, ask which reviewers to re-run (only re-run the selected ones — no need to repeat reviewers that passed). Spawn the selected reviewers in parallel, collect results, and present the updated findings alongside the unchanged results from the other reviewers.

If the user picks **B**, record unresolved findings for the final summary.

---

## Step 4: Next Spec

After all 6 reviews complete for a spec (with or without revisions), move to the next spec in the epic and repeat Step 3.

Show progress:
```
[spec 1/3 complete] → [spec 2/3 complete] → [spec 3/3 complete]
```

---

## Step 5: Final Summary

After all specs are reviewed, present the epic-level summary:

```
Validate Epic: [epic-name]
═══════════════════════════════════════

Specs reviewed: N

| Feature Spec | Completionist | Story Quality | Salty Engineer | Codebase Fit | Security | Second Opinion | Ready? |
|-------------|---------------|---------------|----------------|--------------|----------|----------------|--------|
| feature-foo-schema.md | ✅ ready | ✅ ready | ⚠️ needs-work | ✅ ready | ✅ ready | ✅ ready | ⚠️ |
| feature-foo-api.md | ✅ ready | ✅ ready | ✅ ready | ⚠️ needs-work | ⚠️ needs-work | ✅ ready | ⚠️ |
| feature-foo-ui.md | ⚠️ needs-work | ⚠️ needs-work | 🔴 not-ready | ⚠️ needs-work | ⚠️ needs-work | ⚠️ needs-work | 🔴 |

Outstanding findings (unaddressed):
  - feature-foo-schema.md: [N warnings acknowledged as known risks]
  - feature-foo-ui.md: [N critical, N warnings]

Overall readiness: [ready / needs-work / not-ready]
```

**Overall readiness logic:**
- **ready** — All specs are ready across all six reviews (or only info findings remain)
- **needs-work** — Warning findings remain in one or more specs; critical findings are all resolved
- **not-ready** — Critical findings remain unresolved in any spec

---

## Step 6: Next Steps

**If ready or needs-work:**
> "Your epic looks ready to execute. Run `/kit-tools:execute-epic` to start."
>
> If needs-work: "Consider addressing the remaining warnings before execution — they'll reduce retry risk."

**If not-ready:**
> "There are critical findings that should be addressed before execution. Resolve them and re-run `/kit-tools:validate-epic [epic-name]` before proceeding."

**Write signal summary:** Before deleting result files, write `kit_tools/.validate_epic_summary.json` with the aggregated results so the `harvest_signals.py` Stop hook can capture them:

```json
{
  "epic_name": "[epic-name]",
  "specs_reviewed": 3,
  "overall_readiness": "ready|needs-work|not-ready",
  "reviewer_verdicts": {
    "feature-foo-schema.md": {
      "completionist": "ready",
      "story-quality": "ready",
      "salty-engineer": "needs-work",
      "codebase-fit": "ready",
      "security": "needs-work",
      "second-opinion": "ready"
    }
  },
  "finding_counts": {"critical": 1, "warning": 4, "info": 3}
}
```

**Clean up:** Delete `kit_tools/.validate_epic_1.json` through `kit_tools/.validate_epic_6.json`. Leave the summary file — the Stop hook reads and deletes it.

---

## Related Skills

| Skill | When to use |
|-------|-------------|
| `/kit-tools:plan-epic` | To create or refine the epic and feature specs |
| `/kit-tools:execute-epic` | After validation — to execute the epic |
| `/kit-tools:validate-implementation` | After execution — to validate code quality on the completed branch |
