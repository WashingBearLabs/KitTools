---
name: plan-feature
description: Brainstorm and plan a new feature, creating a Product Requirements Document (PRD)
---

# Plan Feature

Let's brainstorm and plan a new feature together. This is an interactive process — I'll ask clarifying questions to help refine the idea before generating the PRD.

## Dependencies

This skill requires the following project files:

| File | Required | Purpose |
|------|----------|---------|
| `kit_tools/prd/` directory | Yes | Location for new PRD |
| `kit_tools/roadmap/BACKLOG.md` | Yes | To add feature reference |
| `$CLAUDE_PLUGIN_ROOT/templates/prd/PRODUCT_REQ_DOC.md` | Yes | Template for new PRD |

**Creates:**
- `kit_tools/prd/prd-[feature-name].md` — Product Requirements Document

**Updates:**
- `kit_tools/roadmap/BACKLOG.md` — Adds reference to new PRD
- `kit_tools/roadmap/MVP_TODO.md` — Optionally links PRD to milestone

## Step 1: Capture the spark

First, tell me about the feature idea:

- **What's the feature?** (Name and brief description)
- **What problem does it solve?** (The "why" — what pain point does this address?)
- **What triggered this idea?** (User feedback? Hit a limitation? Competitive pressure?)

## Step 2: Clarifying questions

I'll ask 3-5 essential questions to refine the scope. Format questions with lettered options for quick responses:

```
1. What is the primary goal of this feature?
   A. [Option based on context]
   B. [Option based on context]
   C. [Option based on context]
   D. Other: [please specify]

2. Who is the target user?
   A. New users only
   B. Existing users only
   C. All users
   D. Admin/internal users only

3. What is the initial scope?
   A. Minimal viable version
   B. Full-featured implementation
   C. Backend/API only
   D. UI only
```

This lets users respond with "1A, 2C, 3B" for quick iteration.

Focus questions on:
- **Problem/Goal:** What specific problem does this solve?
- **Core Functionality:** What are the key user actions?
- **Scope/Boundaries:** What should it NOT do?
- **Success Criteria:** How do we know it's done?

## Step 3: Define the scope

Now let's set clear boundaries:

### Goals
What are the specific, measurable objectives? (Bullet list)

### Non-Goals
What is explicitly **not** part of this feature? This is critical for managing scope creep.

### Success Criteria
How will we measure success?
- "User can complete X in under Y clicks"
- "API response time < 200ms"
- "Zero critical bugs in first week"

## Step 4: Break into user stories

Structure the implementation as user stories. Each story should be:
- **Small enough** to complete in one focused session (one context window)
- **Independent** where possible
- **Ordered by dependency** (schema → backend → UI)

For each story, define:

1. **ID:** Sequential (US-001, US-002, etc.)
2. **Title:** Short descriptive name
3. **Description:** "As a [user], I want [feature] so that [benefit]"
4. **Acceptance Criteria:** Verifiable checklist of what "done" means

### Story sizing guidance

**Right-sized stories:**
- Add a database column and migration
- Create a single UI component
- Add one API endpoint
- Implement one validation rule

**Too big (split these):**
- "Build the entire dashboard" → Split into schema, queries, components, filters
- "Add authentication" → Split into schema, middleware, login UI, session handling

**Rule of thumb:** If you can't describe the change in 2-3 sentences, it's too big.

### Acceptance criteria guidance

Each criterion must be **verifiable**, not vague:

**Good:** "Login form shows error message for invalid credentials"
**Bad:** "Works correctly"

**Good:** "API returns 401 for unauthenticated requests"
**Bad:** "Handles auth properly"

**Always include:**
- "Typecheck/lint passes" for every story
- "Verify in browser" for UI stories

## Step 5: Functional requirements

Extract numbered functional requirements from the stories:

- **FR-1:** The system must allow users to...
- **FR-2:** When a user clicks X, the system must...
- **FR-3:** The API must return...

Be explicit and unambiguous. These are the "contract" for what the feature does.

## Step 6: Technical considerations

Identify:

- **Dependencies:** What existing code/systems does this touch?
- **Constraints:** Performance requirements, compatibility needs
- **Architecture notes:** Relevant patterns from CODE_ARCH.md
- **Known gotchas:** Relevant items from GOTCHAS.md

Link to existing documentation where helpful.

## Step 7: Surface open questions

What decisions still need to be made? What assumptions should be validated?

Document these as checkboxes so they can be resolved and checked off.

## Step 8: Generate the PRD

Create `kit_tools/prd/prd-[feature-name].md` with:

```yaml
---
feature: [feature-name]
status: active
created: [YYYY-MM-DD]
updated: [YYYY-MM-DD]
---
```

Followed by:
- Overview (problem statement, why now)
- Goals (bullet list)
- User Stories (US-XXX format with acceptance criteria)
- Functional Requirements (FR-X format)
- Non-Goals (explicit scope boundaries)
- Technical Considerations
- Related Documentation (links to CODE_ARCH, GOTCHAS, etc.)
- Implementation Notes (empty — populated during development)
- Open Questions

Use the template at `$CLAUDE_PLUGIN_ROOT/templates/prd/PRODUCT_REQ_DOC.md` as reference.

## Step 9: Update tracking files

### Add to BACKLOG.md

Add a reference to the new PRD in `kit_tools/roadmap/BACKLOG.md`:

```markdown
## Planned Features
- [Feature Name](../prd/prd-feature-name.md) — Brief description
```

### Optionally link to MVP_TODO.md

If this feature is part of a milestone, add a link:

```markdown
## [Milestone Name]
- [ ] Feature Name ([PRD](../prd/prd-feature-name.md))
```

## Step 10: Summary

Report to the user:

- The feature we planned
- Where the PRD was created (`kit_tools/prd/prd-[name].md`)
- Number of user stories defined
- Key decisions made during brainstorming
- Open questions that need resolution
- Recommended next steps

---

## PRD Lifecycle

After creation, a PRD goes through these stages:

| Status | Meaning |
|--------|---------|
| `active` | Currently being implemented |
| `on-hold` | Paused, not currently prioritized |
| `completed` | All stories done, moved to `prd/archive/` |

Use `/kit-tools:complete-feature` to mark a PRD as completed and archive it.

---

## Related Skills

| Skill | When to use |
|-------|-------------|
| `/kit-tools:export-ralph` | To convert PRD to ralph's prd.json format for autonomous execution |
| `/kit-tools:complete-feature` | To mark PRD completed and archive it |
| `/kit-tools:start-session` | To orient on active PRDs at session start |

---

**Note:** This skill creates the PRD but does NOT change your Active Feature in the scratchpad. You can brainstorm a new feature while working on something else.
