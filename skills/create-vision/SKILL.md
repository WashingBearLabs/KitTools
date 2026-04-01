---
name: create-vision
description: Define the product vision through an interactive, iterative process
---

# Create Product Vision

Define your product's vision through a guided, iterative process with AI-assisted review.

## Dependencies

| Component | Location | Purpose |
|-----------|----------|---------|
| **Vision template** | `$CLAUDE_PLUGIN_ROOT/templates/PRODUCT_VISION.md` | Template for vision document |
| **Vision reviewer agent** | `$CLAUDE_PLUGIN_ROOT/agents/vision-reviewer.md` | Reviews vision for completeness, feasibility, and spec-readiness |

**Creates in project:**
- `kit_tools/PRODUCT_VISION.md` — the singular product vision document

---

## Step 1: Check for Existing Vision

Check if `kit_tools/PRODUCT_VISION.md` already exists.

### If it exists and is populated (not just the template)
Ask: **"You already have a Product Vision document. Would you like to:"**
1. **Revise** — Update the existing vision (keep structure, refine content)
2. **Start fresh** — Replace with a new vision document
3. **Cancel** — Keep the existing vision as-is

### If it doesn't exist
Proceed to Step 2.

---

## Step 2: Gather Initial Input

Ask the user about their product vision. Use a conversational approach — don't dump all questions at once.

**Start with:**
> "Let's define your product vision. Tell me: **What are you building, and what problem does it solve?**"

**Follow up with** (as needed, based on the initial answer):
- "**Who is this for?** Describe your target users — their roles, context, and what frustrates them today."
- "**What does success look like?** How would you measure whether this product is working?"
- "**What are the main feature areas you envision?** Think high-level capabilities, not individual features."
- "**Any constraints I should know about?** Technical limits, timeline, team size, etc."

Don't require complete answers — the review step will catch gaps.

---

## Step 3: Draft the Vision Document

1. Read the template from `$CLAUDE_PLUGIN_ROOT/templates/PRODUCT_VISION.md`
2. Write `kit_tools/PRODUCT_VISION.md` populated with the user's input
3. Replace all `{{placeholder}}` tokens with real content or remove sections that don't apply yet
4. Use tier-prefixed IDs for feature areas (T1.1, T1.2, T2.1, etc.) — group features into tiers based on user input about priority
5. Leave the Build Order and Walking Skeleton sections with placeholder content for now — these are filled in Steps 7-8
6. Set the "Last updated" date to today
7. Tell the user: "I've drafted your vision document. Let me run it through a review to identify any gaps."

---

## Step 4: Agent Review — Completeness

Spawn the `vision-reviewer` agent in `completeness` mode:

1. Read the agent template from `$CLAUDE_PLUGIN_ROOT/agents/vision-reviewer.md`
2. Interpolate tokens:
   - `{{VISION_CONTENT}}` — the content of `kit_tools/PRODUCT_VISION.md`
   - `{{REVIEW_MODE}}` — `completeness`
   - `{{PROJECT_CONTEXT}}` — project summary from any existing `kit_tools/SYNOPSIS.md` or CLAUDE.md, or "No project context available"
   - `{{RESULT_FILE_PATH}}` — `kit_tools/.vision_review_1.json`
3. Run via Task tool
4. Read the result file

---

## Step 5: Surface Gaps to User

Present the reviewer's findings conversationally:

**Format:**
> "The review scored your vision **X/5 overall**. Here's what stood out:"
>
> **Strong areas:**
> - [Dimensions scoring 4-5 with brief finding]
>
> **Areas to strengthen:**
> - [Dimensions scoring 1-3 with finding and suggestion]
>
> **Potential gotchas:**
> - [List from reviewer]

Ask: **"Would you like to address any of these gaps? You can also mark some as intentional — not every vision doc needs a perfect score."**

---

## Step 6: Revise the Document

Incorporate the user's responses:
- Update sections they want to strengthen
- Add notes for intentional omissions (e.g., "Constraints are minimal for this personal project")
- Don't change sections the user is happy with

---

## Step 7: Build Order

Now that features are defined and reviewed, prompt the user to think about dependencies and sequencing.

Ask: **"Let's figure out what gets built first. Looking at your feature areas:"**

Present the feature areas by tier, then ask:
> "**Which of these depend on each other?** For example, does T1.2 need T1.1 to exist first? Are there features that are foundational — everything else builds on them?"

Based on the user's answers:
1. Fill in the **Dependency Graph** table in the vision doc
2. Propose a **Build Sequence** — ordered phases based on the dependency graph
3. Ask the user to confirm or adjust the sequence

If the user isn't sure about dependencies, help them think through it:
> "Think about it this way: if you could only ship one feature area, which one? That's Phase 1. Now what does the next one need from Phase 1 to work?"

---

## Step 8: Walking Skeleton

Prompt the user to define the thinnest vertical slice.

Ask: **"What's the thinnest end-to-end path through your system that would prove the architecture works?"**

Clarify if needed:
> "This isn't the MVP — it's smaller. It's the simplest thing that touches every layer: a user does X, the system processes Y, data Z gets stored. What would that look like for your product?"

Based on the user's answer:
1. Fill in the **Walking Skeleton** section with the slice description and layers touched
2. Note what architectural assumption it validates

---

## Step 9: Agent Review — Feasibility

Spawn the `vision-reviewer` agent in `feasibility` mode:

1. Interpolate tokens:
   - `{{VISION_CONTENT}}` — the updated content of `kit_tools/PRODUCT_VISION.md`
   - `{{REVIEW_MODE}}` — `feasibility`
   - `{{PROJECT_CONTEXT}}` — same as Step 4
   - `{{RESULT_FILE_PATH}}` — `kit_tools/.vision_review_2.json`
2. Run via Task tool
3. Read the result file

Present feasibility findings:

> "The feasibility review flagged a few things to consider:"
>
> - [Gotchas and open questions from the review]
>
> "These aren't blockers — they're things to keep in mind as you plan features. Want to address any of these now, or note them as open questions in the vision doc?"

Apply any updates the user requests.

---

## Step 10: Agent Review — Spec-Readiness

Spawn the `vision-reviewer` agent in `spec-readiness` mode:

1. Interpolate tokens:
   - `{{VISION_CONTENT}}` — the updated content of `kit_tools/PRODUCT_VISION.md`
   - `{{REVIEW_MODE}}` — `spec-readiness`
   - `{{PROJECT_CONTEXT}}` — same as Step 4
   - `{{RESULT_FILE_PATH}}` — `kit_tools/.vision_review_3.json`
2. Run via Task tool
3. Read the result file

Present spec-readiness findings:

> "Final check — can a spec writer use this vision to create feature specs?"
>
> **Ready for specs:**
> - [Feature areas that passed]
>
> **Needs work before speccing:**
> - [Feature areas with issues and what's missing]
>
> **Structural issues:**
> - [Any build order gaps, boundary confusion, etc.]

Ask: **"Want to address any of these, or are you comfortable moving to feature planning with these noted as open items?"**

Apply any final updates.

---

## Step 11: Finalize

1. Write the final version of `kit_tools/PRODUCT_VISION.md`
2. Clean up temporary review files (`kit_tools/.vision_review_1.json`, `kit_tools/.vision_review_2.json`, `kit_tools/.vision_review_3.json`)
3. Report summary:

```
Product Vision: Defined

Document: kit_tools/PRODUCT_VISION.md
Overall Score: X/5 (from completeness review)
Feature Areas: N defined (T1: X, T2: Y, T3: Z)
Build Phases: N phases defined
Walking Skeleton: Defined / Not defined
Open Questions: N remaining

Suggested next steps:
  - /kit-tools:seed-project — if you haven't seeded yet
  - /kit-tools:plan-epic — to create feature specs for your vision's feature areas
```

---

## Related Skills

| Skill | When to use |
|-------|-------------|
| `/kit-tools:init-project` | Before this, to set up the kit_tools framework |
| `/kit-tools:seed-project` | After this, to populate other templates |
| `/kit-tools:plan-epic` | After this, to create feature specs for vision areas |
