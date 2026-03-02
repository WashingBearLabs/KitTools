---
name: plan-feature
description: Brainstorm and plan a new feature, creating a Feature Spec
---

# Plan Feature

Let's brainstorm and plan a new feature together. This is an interactive process.

Read `REFERENCE.md` in this skill directory for detailed examples, heuristics, and edge cases.

## Your Role as Senior Dev

**You are the senior developer.** Push back on scope creep, enforce atomic stories, detect epics early, validate before generating. Your goal is high-quality feature specs that can be implemented successfully.

---

## Dependencies

| File | Required | Purpose |
|------|----------|---------|
| `kit_tools/specs/` directory | Yes | Location for new feature spec |
| `kit_tools/roadmap/BACKLOG.md` | Yes | To add feature reference |
| `$CLAUDE_PLUGIN_ROOT/templates/specs/FEATURE_SPEC.md` | Yes | Template for new feature spec |
| `$CLAUDE_PLUGIN_ROOT/templates/specs/PRODUCT_BRIEF.md` | Optional | Template for Product Brief |
| `$CLAUDE_PLUGIN_ROOT/templates/specs/EPIC.md` | Optional | Template for epic decomposition |

---

## Step 1: Product Brief Check

Check for existing Product Briefs in `kit_tools/specs/brief-*.md`.

Ask: **"Does this feature belong to an existing Product Brief, or should we create one? (Recommended for new product areas, optional for incremental features)"**

### If creating a new brief
- Use `PRODUCT_BRIEF.md` template
- Save as `kit_tools/specs/brief-[name].md`
- Fill in Problem Statement, Target Users, Strategic Context, Success Metrics
- Continue to Step 2

### If linking to an existing brief
- Note the brief name for the feature spec's `brief:` frontmatter field
- Continue to Step 2

### If skipping
- Proceed directly to Step 2

---

## Step 2: Capture the spark

Ask: **What's the feature?** **What problem does it solve?** **What triggered this idea?**

---

## Step 3: Epic detection (CRITICAL)

Flag as epic if ANY apply: multiple subsystems, scope keywords ("entire", "full", "system"), layer spanning, multiple user types, vague boundaries.

### If epic detected

Stop and tell the user directly. Propose decomposition into session-sized feature specs.

### If NOT an epic

Proceed to Step 4.

---

## Step 3b: Epic decomposition

Break down by **layer and concern**. Present a table with feature spec names, story counts, dependencies. Set `epic`, `epic_seq`, `epic_final` frontmatter correctly. Generate an explicit `kit_tools/specs/epic-[name].md` using the EPIC.md template.

See REFERENCE.md for decomposition examples and epic frontmatter format.

---

## Step 4: Clarifying questions

Ask 3-5 essential questions with lettered options for quick responses. Focus on: problem/goal, core functionality, scope/boundaries, success criteria.

---

## Step 5: Define the scope

Set: **Goals** (measurable), **Out of Scope** (explicit boundaries), **Success Criteria**.

---

## Step 6: Break into user stories

Each story needs: ID, Title, Description, Implementation Hints (populated in Step 11), Acceptance Criteria.

### Session-fit focus

Focus on right-sized stories completable in one Claude session, not story count.

### Auto-injected test criteria

Every code story automatically includes:
```
- [ ] Tests written/updated for new functionality
- [ ] Full test suite passes
- [ ] Typecheck/lint passes
```

Doc/config-only stories are exempt. Test criteria go after user-defined criteria, before typecheck.

---

## Step 7: Technical considerations

Identify dependencies, constraints, architecture notes, known gotchas.

---

## Step 8: Surface open questions

Document unresolved decisions as checkboxes.

---

## Step 9: Final scope check

Verify: 3-5 criteria per story, single layer focus, dependencies clear, stories well-defined.

---

## Step 10: Generate the Feature Spec

Create `kit_tools/specs/feature-[feature-name].md` using the FEATURE_SPEC.md template. Set frontmatter fields including `brief:` (if applicable) and `type:`. See REFERENCE.md for field reference.

---

## Step 11: Story Refinement

**Iterative per-story review to ensure each story is session-fit.**

### Refinement loop

For each user story:

1. **Present** the story with current acceptance criteria
2. **Evaluate** against refinement heuristics (see REFERENCE.md)
3. **If issues found:** Split, narrow, research, or clarify
4. **Generate Implementation Hints** (3-5 bullet points per story):
   - Key file paths the implementer will need
   - Existing patterns or functions to follow/reuse
   - Specific modules or imports needed
   - Relevant gotchas that apply
   - Constraints discovered during research
5. **Ask:** "Ready to move to next story, or refine further?"
6. **Apply** changes and continue

### Implementation Hints format

Add `**Implementation Hints:**` between Description and Acceptance Criteria:

```markdown
**Implementation Hints:**
- Login page at src/pages/login.tsx uses AuthForm component
- Use existing Button component from src/components/ui/Button.tsx
- See GOTCHAS.md: "OAuth redirects must use absolute URLs"
```

### Populate Refinement Notes

Update the feature spec's Refinement Notes: research conducted, scope adjustments, decisions made.

---

## Step 12: Update tracking files

Add feature spec reference to `kit_tools/roadmap/BACKLOG.md`. For epics, group as a section.

---

## Step 13: Summary

Report: feature(s) planned, epic decomposition (if any), feature spec location(s), story counts, refinement status, session readiness, dependencies, key decisions, open questions, next steps.

---

## Related Skills

| Skill | When to use |
|-------|-------------|
| `/kit-tools:execute-feature` | To execute feature spec stories |
| `/kit-tools:complete-feature` | To mark feature spec completed and archive it |

---

**Note:** This skill creates the feature spec but does NOT change your Active Feature in the scratchpad.
