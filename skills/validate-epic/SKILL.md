---
name: validate-epic
description: Validate an epic's feature specs before execution — completeness, story quality, adversarial review, and cross-model second opinion
---

# Validate Epic

Run four sequential pre-execution reviews on an epic's feature specs before handing off to `/kit-tools:execute-epic`. Catches missing stories, vague criteria, bad story IDs, implementation gaps, and architectural blind spots that would cause retries or failures during autonomous execution.

This skill is the quality gate between planning and execution.

## Dependencies

| Component | Location | Required |
|-----------|----------|---------|
| Completionist agent | `$CLAUDE_PLUGIN_ROOT/agents/spec-completionist-reviewer.md` | Yes |
| Story quality agent | `$CLAUDE_PLUGIN_ROOT/agents/story-quality-reviewer.md` | Yes |
| Salty engineer agent | `$CLAUDE_PLUGIN_ROOT/agents/salty-engineer-reviewer.md` | Yes |
| Second opinion agent | `$CLAUDE_PLUGIN_ROOT/agents/spec-second-opinion.md` | Yes |

**Reads:** `kit_tools/specs/epic-*.md`, `kit_tools/specs/feature-*.md`, `kit_tools/PRODUCT_VISION.md` (if exists)
**Creates (temporary):** `kit_tools/.validate_epic_1.json`, `kit_tools/.validate_epic_2.json`, `kit_tools/.validate_epic_3.json`, `kit_tools/.validate_epic_4.json`
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

Running 4 reviews per spec:
  1. Completionist — are we missing anything?
  2. Story Quality — are stories well-formed and right-sized?
  3. Salty Engineer — what will blow up in implementation?
  4. Second Opinion (Sonnet) — is there a better way to do this?
```

Confirm before proceeding.

---

## Step 3: Per-Spec Review Loop

For each active feature spec (in epic order), run all four reviews:

### 3a: Completionist Review

1. Read `$CLAUDE_PLUGIN_ROOT/agents/spec-completionist-reviewer.md`
2. Interpolate tokens:
   - `{{SPEC_PATH}}` — path to the feature spec file
   - `{{SPEC_NAME}}` — the feature name from the spec's `feature:` frontmatter
   - `{{VISION_CONTEXT}}` — from Step 1
   - `{{RESULT_FILE_PATH}}` — `kit_tools/.validate_epic_1.json`
3. Spawn via Task tool
4. Read `kit_tools/.validate_epic_1.json`

**Present findings:**
> **Review 1/3 — Completionist: [spec-name]**
>
> Verdict: [ready / needs-work / not-ready]
>
> **Findings:**
> - 🔴 [critical findings]
> - ⚠️  [warning findings]
> - ℹ️  [info findings]
>
> _(If no findings: "No gaps found — all goals have implementing stories.")_

**If critical or warning findings:**
Ask: "Would you like to update the spec now, or continue to the next review?"
- If user updates the spec, offer to re-run this review before continuing
- If user continues, note that findings are outstanding and include them in the final summary

### 3b: Story Quality Review

1. Read `$CLAUDE_PLUGIN_ROOT/agents/story-quality-reviewer.md`
2. Interpolate tokens:
   - `{{SPEC_PATH}}` — path to the feature spec file
   - `{{SPEC_NAME}}` — feature name
   - `{{RESULT_FILE_PATH}}` — `kit_tools/.validate_epic_2.json`
3. Spawn via Task tool
4. Read `kit_tools/.validate_epic_2.json`

**Present findings:**
> **Review 2/3 — Story Quality: [spec-name]**
>
> Verdict: [ready / needs-work / not-ready]
>
> Per-story status:
> | Story | Verdict | Issues |
> |-------|---------|--------|
> | US-001 | ready | — |
> | US-002 | needs-work | Story too big, vague criterion 3 |
>
> **Findings:**
> - 🔴 [critical — bad IDs, massively oversized stories]
> - ⚠️  [warnings — split suggestions, vague criteria, underscoped integrations]
> - ℹ️  [info — hint quality]

**If critical or warning findings:**
Ask: "Update the spec now, or continue to the salty engineer review?"
- Offer re-run if user updates

### 3c: Salty Engineer Review

1. Read `$CLAUDE_PLUGIN_ROOT/agents/salty-engineer-reviewer.md`
2. Interpolate tokens:
   - `{{SPEC_PATH}}` — path to the feature spec file
   - `{{SPEC_NAME}}` — feature name
   - `{{VISION_CONTEXT}}` — from Step 1
   - `{{RESULT_FILE_PATH}}` — `kit_tools/.validate_epic_3.json`
3. Spawn via Task tool
4. Read `kit_tools/.validate_epic_3.json`

**Present findings in the engineer's voice — don't sanitize them:**
> **Review 3/3 — Salty Engineer: [spec-name]**
>
> Verdict: [ready / needs-work / not-ready]
>
> **Findings:**
> - 🔴 [critical — things that will definitely blow up]
> - ⚠️  [warnings — things that will cause significant rework]
> - ℹ️  [info — things worth knowing]
>
> _(Preserve the engineer's direct voice when presenting critique fields)_

**If critical or warning findings:**
Ask: "Address these before proceeding, or note them as known risks and continue?"
- If user updates spec, offer to re-run the salty engineer review
- If user accepts risk, log them as acknowledged in the final summary

### 3d: Second Opinion Review (cross-model)

This review deliberately uses a **different model** than the other three reviews. The value of a second opinion comes from different training surfacing different blind spots — so pick a model that contrasts with the model you're using for the primary reviews.

**Model choice:**
- If the rest of the session is running on Opus, use `model: "sonnet"` here.
- If the rest is running on Sonnet (or you've configured `model_config.reviewer_primary: sonnet` in your orchestrator config), use `model: "opus"` here.
- If the user has specified a secondary model (e.g., via `model_config.reviewer_second_opinion` in their execution config), honor that.

The goal is *different model from the other reviewers*, not a specific model pin — that way the pattern keeps working as new models ship.

1. Read `$CLAUDE_PLUGIN_ROOT/agents/spec-second-opinion.md`
2. Interpolate tokens:
   - `{{SPEC_PATH}}` — path to the feature spec file
   - `{{SPEC_NAME}}` — feature name
   - `{{VISION_CONTEXT}}` — from Step 1
   - `{{RESULT_FILE_PATH}}` — `kit_tools/.validate_epic_4.json`
3. Spawn via Task tool with an explicit `model:` parameter chosen per the guidance above
4. Read `kit_tools/.validate_epic_4.json`

**Present findings:**
> **Review 4/4 — Second Opinion (Sonnet): [spec-name]**
>
> Verdict: [ready / needs-work / not-ready]
>
> **Findings:**
> - 🔴 [critical findings]
> - ⚠️  [warning findings — architecture, feasibility, alternatives with trade-offs]
> - ℹ️  [info findings]
>
> _(For alternative-approach and over-engineering findings, always include the trade-offs in the presentation)_

**If critical or warning findings:**
Ask: "Consider these suggestions, or continue with the current approach?"
- If user wants to incorporate suggestions, update the spec and offer to re-run
- If user prefers the current approach, acknowledge and continue

---

## Step 4: Next Spec

After all 4 reviews complete for a spec (with or without revisions), move to the next spec in the epic and repeat Step 3.

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

| Feature Spec | Completionist | Story Quality | Salty Engineer | Second Opinion | Ready? |
|-------------|---------------|---------------|----------------|----------------|--------|
| feature-foo-schema.md | ✅ ready | ✅ ready | ⚠️ needs-work | ✅ ready | ⚠️ |
| feature-foo-api.md | ✅ ready | ✅ ready | ✅ ready | ✅ ready | ✅ |
| feature-foo-ui.md | ⚠️ needs-work | ⚠️ needs-work | 🔴 not-ready | ⚠️ needs-work | 🔴 |

Outstanding findings (unaddressed):
  - feature-foo-schema.md: [N warnings acknowledged as known risks]
  - feature-foo-ui.md: [N critical, N warnings]

Overall readiness: [ready / needs-work / not-ready]
```

**Overall readiness logic:**
- **ready** — All specs are ready across all four reviews (or only info findings remain)
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

**Clean up:** Delete `kit_tools/.validate_epic_1.json`, `kit_tools/.validate_epic_2.json`, `kit_tools/.validate_epic_3.json`, `kit_tools/.validate_epic_4.json`.

---

## Related Skills

| Skill | When to use |
|-------|-------------|
| `/kit-tools:plan-epic` | To create or refine the epic and feature specs |
| `/kit-tools:execute-epic` | After validation — to execute the epic |
| `/kit-tools:validate-implementation` | After execution — to validate code quality on the completed branch |
