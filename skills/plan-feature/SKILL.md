---
name: plan-feature
description: Brainstorm and plan a new feature, creating a Product Requirements Document (PRD)
---

# Plan Feature

Let's brainstorm and plan a new feature together. This is an interactive process.

Read `REFERENCE.md` in this skill directory for detailed examples, heuristics, and edge cases.

## Your Role as Senior Dev

**You are the senior developer.** Push back on scope creep, enforce atomic stories, detect epics early, validate before generating. Your goal is high-quality PRDs that can be implemented successfully.

---

## Dependencies

| File | Required | Purpose |
|------|----------|---------|
| `kit_tools/prd/` directory | Yes | Location for new PRD |
| `kit_tools/roadmap/BACKLOG.md` | Yes | To add feature reference |
| `$CLAUDE_PLUGIN_ROOT/templates/prd/PRODUCT_REQ_DOC.md` | Yes | Template for new PRD |

---

## Step 1: Capture the spark

Ask: **What's the feature?** **What problem does it solve?** **What triggered this idea?**

---

## Step 2: Epic detection (CRITICAL)

Flag as epic if ANY apply: multiple subsystems, scope keywords ("entire", "full", "system"), layer spanning, multiple user types, vague boundaries.

### If epic detected

Stop and tell the user directly. Propose decomposition into session-sized PRDs.

### If NOT an epic

Proceed to Step 3.

---

## Step 2b: Epic decomposition

Break down by **layer and concern**. Present a table with PRD names, story counts, dependencies. Set `epic`, `epic_seq`, `epic_final` frontmatter correctly.

See REFERENCE.md for decomposition examples and epic frontmatter format.

---

## Step 3: Clarifying questions

Ask 3-5 essential questions with lettered options for quick responses. Focus on: problem/goal, core functionality, scope/boundaries, success criteria.

---

## Step 4: Define the scope

Set: **Goals** (measurable), **Non-Goals** (explicit boundaries), **Success Criteria**.

---

## Step 5: Break into user stories

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

## Step 6: Functional requirements

Extract numbered FRs: explicit, unambiguous contracts for what the feature does.

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

## Step 10: Generate the PRD

Create `kit_tools/prd/prd-[feature-name].md` using the template. Set frontmatter fields. See REFERENCE.md for field reference.

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

Update the PRD's Refinement Notes: research conducted, scope adjustments, decisions made.

---

## Step 12: Update tracking files

Add PRD reference to `kit_tools/roadmap/BACKLOG.md`. For epics, group as a section.

---

## Step 13: Summary

Report: feature(s) planned, epic decomposition (if any), PRD location(s), story counts, refinement status, session readiness, dependencies, key decisions, open questions, next steps.

---

## Related Skills

| Skill | When to use |
|-------|-------------|
| `/kit-tools:execute-feature` | To execute PRD stories |
| `/kit-tools:complete-feature` | To mark PRD completed and archive it |

---

**Note:** This skill creates the PRD but does NOT change your Active Feature in the scratchpad.
