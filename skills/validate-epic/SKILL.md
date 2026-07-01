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
**Creates (temporary):** `kit_tools/.validate_epic_<spec-slug>_1.json` … `_6.json` — one set of per-reviewer files per spec, so all specs can be reviewed in parallel without collision
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

Running the 6-reviewer panel across ALL [N] specs at once (every reviewer for every spec, in parallel):
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

If the user picks quick tier, run reviewers 1, 3, and 5 only for every spec (same per-spec result files, same parallel flow); note in the epic-level summary that the quick tier was used. If any quick-tier reviewer returns a critical finding, recommend escalating that spec to the full panel.

Confirm before proceeding.

---

## Step 3: Fan Out All Reviews (parallel — the whole epic at once)

**Do not review one spec at a time.** Spawn **every reviewer for every active spec in a single message** so the entire epic's review runs concurrently. For an epic with N active specs on the full panel that's N × 6 Task calls in one message; the harness runs as many as it can concurrently and queues the rest — you collect a complete set of findings once, not spec-by-spec.

Give each reviewer a **per-spec result file** so parallel specs never collide: `kit_tools/.validate_epic_<slug>_<n>.json`, where `<slug>` is the spec's filename without `.md` (e.g. `feature-foo-schema`) and `<n>` is the reviewer number below. Read the six agent templates from `$CLAUDE_PLUGIN_ROOT/agents/` once, then interpolate the tokens per spec.

| # | Agent | Template | Result file (per spec; `<slug>` = spec basename) | Tokens |
|---|-------|----------|--------------------------------------------------|--------|
| 1 | Completionist | `spec-completionist-reviewer.md` | `kit_tools/.validate_epic_<slug>_1.json` | `SPEC_PATH`, `SPEC_NAME`, `VISION_CONTEXT`, `RESULT_FILE_PATH` |
| 2 | Story Quality | `story-quality-reviewer.md` | `kit_tools/.validate_epic_<slug>_2.json` | `SPEC_PATH`, `SPEC_NAME`, `RESULT_FILE_PATH` |
| 3 | Salty Engineer | `salty-engineer-reviewer.md` | `kit_tools/.validate_epic_<slug>_3.json` | `SPEC_PATH`, `SPEC_NAME`, `VISION_CONTEXT`, `RESULT_FILE_PATH` |
| 4 | Codebase Fit | `codebase-fit-reviewer.md` | `kit_tools/.validate_epic_<slug>_4.json` | `SPEC_PATH`, `SPEC_NAME`, `RESULT_FILE_PATH` |
| 5 | Security | `spec-security-reviewer.md` | `kit_tools/.validate_epic_<slug>_5.json` | `SPEC_PATH`, `SPEC_NAME`, `VISION_CONTEXT`, `RESULT_FILE_PATH` |
| 6 | Second Opinion | `spec-second-opinion.md` | `kit_tools/.validate_epic_<slug>_6.json` | `SPEC_PATH`, `SPEC_NAME`, `VISION_CONTEXT`, `RESULT_FILE_PATH` |

Quick tier (if the user chose it): spawn reviewers **1, 3, 5 only** for every spec — same per-spec file names.

**Second Opinion model choice:** This review deliberately uses a **different model** than the other five. The value comes from different training surfacing different blind spots.
- If the session is running on Opus, use `model: "sonnet"` for this agent.
- If the session is running on Sonnet, use `model: "opus"`.
- If the user has specified a model via `model_config.reviewer_second_opinion`, honor that.

**How to detect the session model:** you know your own model from your system prompt (the environment section names it). If it names Opus or Sonnet, apply the rules above. If it names anything else (Haiku, a newer family, unknown), default to `model: "opus"` for this agent — the goal is simply a *different* training than the one reviewing everything else.

**Resilience:** collect every result file once the agents finish. If one is missing or malformed (an agent crashed), mark that reviewer `error` for that spec and continue — a single failed agent must never block the consolidated report or the rest of the epic.

---

## Step 4: Present Consolidated Findings (the whole epic)

Once all agents complete, read **every** result file and present ONE consolidated view for the entire epic — not spec-by-spec. Every result carries a native verdict and `canonical_verdict` (`ready|needs-work|not-ready`, see FINDING_SCHEMA.md) — prefer `canonical_verdict` when aggregating; fall back to the native field for pre-2.7.0 results.

Each reviewer also emits a `readiness_score` (1–10, anchored to its verdict — see FINDING_SCHEMA.md). **Report the per-reviewer vector; never average it.** The spread is signal: a high salty score against a low security score is worth digging into (*how* did a spec a senior engineer would ship still carry a security gap?). The gate reads the **worst** reviewer, not a mean — preserving every reviewer's score keeps that telemetry intact. For pre-2.7.0 results the score may be absent; show `—`.

Sanity-check each score against its band before presenting: `not-ready` → 1–4, `needs-work` → 5–7, `ready` → 8–10. A score outside the band implied by that reviewer's `canonical_verdict` is a bug (like a `clean` verdict carrying a critical finding) — flag it and trust the verdict/findings over the number.

First, the **epic-level readiness matrix** — every spec × every reviewer, each cell a verdict icon + readiness score:

```
Validate Epic: [epic-name]  —  [N] specs × [6|3] reviewers, reviewed in parallel
═══════════════════════════════════════
| Feature Spec | Completionist | Story Quality | Salty | Codebase Fit | Security | 2nd Opinion | Worst |
|-------------|---------------|---------------|-------|--------------|----------|-------------|-------|
| feature-foo-schema.md | ✅ 8 | ✅ 8 | ⚠️ 6 | ✅ 8 | ⚠️ 5 | ✅ 8 | ⚠️ 5 |
| feature-foo-api.md    | ✅ 8 | ✅ 8 | ✅ 8 | ⚠️ 6 | ⚠️ 6 | ✅ 8 | ⚠️ 6 |
| feature-foo-ui.md     | ⚠️ 6 | ⚠️ 6 | 🔴 3 | ⚠️ 6 | ⚠️ 5 | ⚠️ 6 | 🔴 3 |

Each spec's worst reviewer drives its gate — never a row or table average.
```

Then present findings **grouped by spec, critical first across the whole epic**, then warnings, then info. Prefix every finding with `spec-name · reviewer` so the source is unambiguous.

**Presentation notes per reviewer:**
- **Salty Engineer**: Preserve the engineer's direct voice — don't sanitize critique fields
- **Codebase Fit**: Always include the `evidence` block (existing code reference + what the spec proposes) — this is what makes the finding actionable
- **Security**: Lead with the biggest risk. Group findings by lens (attack surface, auth, data exposure, input trust, omissions) when there are many. Omission findings are often the most important — highlight them.
- **Second Opinion**: Include trade-offs for alternative-approach and over-engineering findings
- **Story Quality**: Include the per-story status table if present

## Step 5: Fix and Re-run

After the consolidated findings, ask the user (epic-wide):

> **[N] findings across [M] specs (worst readiness: [score] — [spec] / [reviewer]). Would you like to:**
> - **A.** Update one or more specs and re-run the affected reviewers
> - **B.** Note findings as known risks and proceed to execution
> - **C.** Stop and address findings before continuing

Graduated guidance (advice, not a hard gate — the user always chooses): any critical finding → recommend **A**; otherwise worst score 1–4 → **A**; 5–7 → **B** is reasonable if the user accepts the named risks; 8–10 → clean enough to proceed.

If the user picks **A**: after they update the spec(s), re-run **only the affected (spec, reviewer) pairs** — again **in a single parallel message** — collect, and re-present the updated consolidated matrix (unchanged results carry forward). Repeat until the user proceeds or stops. If **B**, record unresolved findings for the summary.

---

## Step 6: Finalize

**Overall readiness:**
- **ready** — every spec ready across all reviewers (or only info findings remain)
- **needs-work** — warnings remain somewhere; all criticals resolved
- **not-ready** — any unresolved critical finding in any spec

**Next steps:**

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
  "reviewer_scores": {
    "feature-foo-schema.md": {
      "completionist": 8,
      "story-quality": 8,
      "salty-engineer": 6,
      "codebase-fit": 8,
      "security": 5,
      "second-opinion": 8
    }
  },
  "finding_counts": {"critical": 1, "warning": 4, "info": 3},
  "per_spec_finding_counts": {
    "feature-foo-schema.md": {"critical": 1, "warning": 2, "info": 1}
  }
}
```

`reviewer_scores` mirrors `reviewer_verdicts`' shape (per spec, per reviewer) and is added **alongside** it, not merged into it — existing consumers that read `reviewer_verdicts` keep working unchanged. Record the raw per-reviewer scores; do **not** write an averaged or rolled-up score anywhere. Omit a reviewer's entry if it produced no score (a pre-2.7.0 result).

`per_spec_finding_counts` is optional but recommended: the top-level `finding_counts` is the epic total, so a per-spec breakdown (keyed by spec name) is what lets the trace correlate a spec's finding load to its execution outcome. Include it if you have per-spec counts from the review; omit it if you only tracked epic totals.

**Emit trace events:** After writing the summary, append per-reviewer spec-quality events to the run trace so the benchmark/retrospective pipeline can join pre-execution spec quality to downstream outcomes:

```bash
python3 "$CLAUDE_PLUGIN_ROOT/scripts/emit_validate_events.py"
```

This reads the summary you just wrote and appends one `spec.validate.scored` event (reviewer, `canonical_verdict`, `readiness_score`, `finding_counts`) per reviewer to `kit_tools/.execution-events.jsonl` — the same stream the executor and `harvest_signals` reducer use. It is best-effort and deterministic (no model in the loop); if it prints a skip note, continue normally.

**Clean up:** Delete the per-spec result files (`kit_tools/.validate_epic_<slug>_<n>.json` for every spec and reviewer). **Leave `.validate_epic_summary.json`** — the Stop hook reads it (its name has no `_<n>` suffix, so it isn't one of the files you delete).

---

## Related Skills

| Skill | When to use |
|-------|-------------|
| `/kit-tools:plan-epic` | To create or refine the epic and feature specs |
| `/kit-tools:execute-epic` | After validation — to execute the epic |
| `/kit-tools:validate-implementation` | After execution — to validate code quality on the completed branch |
