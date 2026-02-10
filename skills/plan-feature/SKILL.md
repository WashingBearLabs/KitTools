---
name: plan-feature
description: Brainstorm and plan a new feature, creating a Product Requirements Document (PRD)
---

# Plan Feature

Let's brainstorm and plan a new feature together. This is an interactive process — I'll ask clarifying questions to help refine the idea before generating the PRD.

## Your Role as Senior Dev

**You are the senior developer on this project.** Your job is to ensure PRDs are properly scoped, implementable, and set up for success. This means:

- **Push back on scope creep** — If a feature is too large, say so directly
- **Enforce atomic stories** — Each story must be completable in one focused session
- **Detect epics early** — Large features should be decomposed into multiple PRDs
- **Validate before generating** — Don't create PRDs that will fail during implementation

When you identify issues, be direct:
> "I need to push back on this scope. What you're describing is an epic, not a single feature. Let me break this down into manageable PRDs."

Your goal is high-quality PRDs that can be implemented successfully, either manually or via autonomous execution.

---

## Dependencies

This skill requires the following project files:

| File | Required | Purpose |
|------|----------|---------|
| `kit_tools/prd/` directory | Yes | Location for new PRD |
| `kit_tools/roadmap/BACKLOG.md` | Yes | To add feature reference |
| `$CLAUDE_PLUGIN_ROOT/templates/prd/PRODUCT_REQ_DOC.md` | Yes | Template for new PRD |

**Creates:**
- `kit_tools/prd/prd-[feature-name].md` — Product Requirements Document (one or more)

**Updates:**
- `kit_tools/roadmap/BACKLOG.md` — Adds reference to new PRD(s)
- `kit_tools/roadmap/MVP_TODO.md` — Optionally links PRD to milestone

---

## Step 1: Capture the spark

First, tell me about the feature idea:

- **What's the feature?** (Name and brief description)
- **What problem does it solve?** (The "why" — what pain point does this address?)
- **What triggered this idea?** (User feedback? Hit a limitation? Competitive pressure?)

---

## Step 2: Epic detection (CRITICAL)

**Before proceeding, evaluate whether this is a single feature or an epic.**

### Epic warning signs

Flag as an epic if ANY of these apply:

| Signal | Example | Why it's a problem |
|--------|---------|-------------------|
| **Multiple subsystems** | "Auth with OAuth, session management, and user profiles" | Touches too many areas |
| **Scope keywords** | "entire", "full", "complete", "from scratch", "system" | Indicates large scope |
| **Layer spanning** | "Database + API + UI for payments" | Should be separate PRDs per layer |
| **Multiple user types** | "Admin dashboard AND user dashboard" | Should be separate features |
| **Vague boundaries** | "Make it production-ready" | Scope is undefined |

**Note:** Epic = multi-subsystem feature, not just "many stories". A PRD with 15 well-refined, session-fit stories is fine. A PRD spanning 3 subsystems with 5 stories is an epic.

### If epic detected

**Stop and address this directly:**

> "What you're describing sounds like an **epic** — a collection of related features that's too large for a single PRD.
>
> Large PRDs cause problems:
> - They overwhelm autonomous execution (agents will exhaust context)
> - They're harder to track and complete
> - They delay the satisfaction of shipping
>
> Let me propose breaking this into focused PRDs that can each be completed in a single session."

Then proceed to **Step 2b: Epic Decomposition**.

### If NOT an epic

Proceed to Step 3.

---

## Step 2b: Epic decomposition

When you've identified an epic, decompose it into multiple PRDs.

### Decomposition strategy

Break down by **layer and concern**:

```
Epic: "OAuth Authentication System"
         ↓ decompose into:

1. prd-oauth-schema.md
   - Database tables, migrations, types
   - 3-4 stories
   - No dependencies

2. prd-oauth-provider.md
   - OAuth provider config, token handling
   - 4-5 stories
   - depends_on: [oauth-schema]

3. prd-oauth-api.md
   - Login/logout endpoints, session validation
   - 4-5 stories
   - depends_on: [oauth-schema, oauth-provider]

4. prd-oauth-ui.md
   - Login button, callback handling, error states
   - 4-5 stories
   - depends_on: [oauth-api]
```

### Present the decomposition

Show the user your proposed breakdown:

> "Here's how I'd break this epic into session-sized PRDs:
>
> | PRD | Stories | Depends On | Purpose |
> |-----|---------|------------|---------|
> | `prd-oauth-schema` | ~3 | — | Database foundation |
> | `prd-oauth-provider` | ~4 | schema | OAuth integration |
> | `prd-oauth-api` | ~4 | schema, provider | Backend endpoints |
> | `prd-oauth-ui` | ~4 | api | User interface |
>
> Each PRD can be completed in one session and executed autonomously.
>
> Should I proceed with this breakdown, or would you like to adjust it?"

### User options

- **Proceed** — Create all PRDs with the proposed structure
- **Adjust** — Modify the breakdown (combine, split differently, change order)
- **Single PRD anyway** — User insists (warn but comply, mark `session_ready: false`)

### Creating multiple PRDs

If proceeding with decomposition:

1. Walk through each PRD using Steps 3-8
2. Or offer: "Would you like me to generate all PRDs with sensible defaults, then you can refine them?"
3. Set `depends_on` fields correctly in each PRD's frontmatter
4. **Set epic chaining fields** in each PRD's frontmatter:
   - `epic`: The epic name (same across all PRDs in the epic, kebab-case)
   - `epic_seq`: Execution order (1-based, sequential)
   - `epic_final`: `true` only on the **last** PRD in the epic
5. Link all PRDs in BACKLOG.md as a grouped epic

**Example epic frontmatter:**

```yaml
# prd-oauth-schema.md
epic: oauth
epic_seq: 1

# prd-oauth-provider.md
epic: oauth
epic_seq: 2
depends_on: [oauth-schema]

# prd-oauth-api.md
epic: oauth
epic_seq: 3
depends_on: [oauth-schema, oauth-provider]

# prd-oauth-ui.md
epic: oauth
epic_seq: 4
epic_final: true
depends_on: [oauth-api]
```

The `epic` fields enable the execute-feature orchestrator to chain PRD execution automatically on a shared `epic/[name]` branch.

---

## Step 3: Clarifying questions

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

---

## Step 4: Define the scope

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

---

## Step 5: Break into user stories

Structure the implementation as user stories. Each story should be:
- **Small enough** to complete in one focused session (one context window)
- **Independent** where possible
- **Ordered by dependency** (schema → backend → UI)

For each story, define:

1. **ID:** Sequential (US-001, US-002, etc.)
2. **Title:** Short descriptive name
3. **Description:** "As a [user], I want [feature] so that [benefit]"
4. **Acceptance Criteria:** Verifiable checklist of what "done" means

### Session-fit focus

**Focus on session-fit per story, not story count.** The goal is right-sized stories that can each be completed in a single Claude session. If 20 well-refined stories are needed, that's fine — what matters is that each story is atomic and achievable.

Stories will be evaluated during the refinement step (Step 11) for:
- Single responsibility (one concern per story)
- Session fit (completable in one context window)
- Clear acceptance criteria

### Story sizing guidance

**Right-sized stories (1 story = 1 focused task):**
- Add a database column and migration
- Create a single UI component
- Add one API endpoint
- Implement one validation rule
- Write tests for one module

**Too big (split these):**
- "Build the entire dashboard" → Split into schema, queries, components, filters
- "Add authentication" → This is an epic, not a story
- "Create the settings page" → Split by settings category

**Rule of thumb:** If you can't describe the change in 2-3 sentences, it's too big.

### Acceptance criteria guidance

Each criterion must be **verifiable**, not vague:

**Good:** "Login form shows error message for invalid credentials"
**Bad:** "Works correctly"

**Good:** "API returns 401 for unauthenticated requests"
**Bad:** "Handles auth properly"

**Target: 3-5 acceptance criteria per story.** More than 6 suggests the story is too big.

**Always include:**
- "Typecheck/lint passes" for every story
- "Verify in browser" for UI stories

---

## Step 6: Functional requirements

Extract numbered functional requirements from the stories:

- **FR-1:** The system must allow users to...
- **FR-2:** When a user clicks X, the system must...
- **FR-3:** The API must return...

Be explicit and unambiguous. These are the "contract" for what the feature does.

---

## Step 7: Technical considerations

Identify:

- **Dependencies:** What existing code/systems does this touch?
- **Constraints:** Performance requirements, compatibility needs
- **Architecture notes:** Relevant patterns from CODE_ARCH.md
- **Known gotchas:** Relevant items from GOTCHAS.md

Link to existing documentation where helpful.

---

## Step 8: Surface open questions

What decisions still need to be made? What assumptions should be validated?

Document these as checkboxes so they can be resolved and checked off.

---

## Step 9: Final scope check

**Before generating, verify the PRD meets these criteria:**

| Check | Target | Status |
|-------|--------|--------|
| Acceptance criteria | 3-5 per story | ✓ or ✗ |
| Layer focus | Single layer or tightly coupled | ✓ or ✗ |
| Dependencies clear | All blockers identified | ✓ or ✗ |
| Stories well-defined | Clear scope per story | ✓ or ✗ |

**Note:** Story count is not a target — session-fit per story matters more. Stories will be refined in Step 11.

**If any check fails, address it before proceeding.**

---

## Step 10: Generate the PRD

Create `kit_tools/prd/prd-[feature-name].md` with:

```yaml
---
feature: [feature-name]
status: active
session_ready: true
depends_on: []
epic:                              # Epic name (empty for standalone PRDs)
epic_seq:                          # Execution order within epic (1-based)
epic_final:                        # true only on last PRD in epic
created: [YYYY-MM-DD]
updated: [YYYY-MM-DD]
---
```

### Frontmatter fields

| Field | Purpose |
|-------|---------|
| `feature` | Kebab-case feature name |
| `status` | `active`, `on-hold`, or `completed` |
| `session_ready` | `true` if all stories pass session-fit checks; `false` if user skipped refinement or stories have unresolved issues |
| `depends_on` | Array of feature names this PRD depends on (for epics) |
| `epic` | Epic name — same across all PRDs in the epic (empty for standalone) |
| `epic_seq` | Execution order within the epic, 1-based (empty for standalone) |
| `epic_final` | `true` only on the last PRD in the epic (empty for standalone) |
| `created` | Creation date |
| `updated` | Last update date |

### PRD content

Followed by:
- Overview (problem statement, why now)
- Goals (bullet list)
- User Stories (US-XXX format with acceptance criteria)
- Functional Requirements (FR-X format)
- Non-Goals (explicit scope boundaries)
- Technical Considerations
- Related Documentation (links to CODE_ARCH, GOTCHAS, etc.)
- Implementation Notes (empty — populated during development)
- Refinement Notes (populated during Step 11 refinement)
- Open Questions

Use the template at `$CLAUDE_PLUGIN_ROOT/templates/prd/PRODUCT_REQ_DOC.md` as reference.

---

## Step 11: Story Refinement

**Iterative per-story review to ensure each story is session-fit.**

PRD creation should represent the bulk of pre-coding work. This refinement step is investment, not overhead — catching over-scoped stories now prevents wasted context during implementation.

### Refinement heuristics

Evaluate each story against these checks:

| Check | Question | Red Flag |
|-------|----------|----------|
| **Single Responsibility** | Is this story trying to do multiple things? | "and", "also", multiple verbs |
| **Session Fit** | Can this realistically complete in one context window? | Touches >3 files, crosses subsystems |
| **Research Needs** | Are there unknowns that would eat context during implementation? | Vague tech, unexplored patterns |
| **Scope Clarity** | Are acceptance criteria specific and verifiable? | "works correctly", "handles properly" |
| **Exploration Load** | How much discovery is needed vs. straightforward implementation? | "figure out", "determine how" |

### Refinement loop

For each user story:

1. **Present** the story with current acceptance criteria
2. **Evaluate** against the heuristics above
3. **If issues found:**
   - **Multi-concern:** Propose split into separate stories
   - **Over-scoped:** Propose narrowing or splitting
   - **Research needs:**
     a. Explain what research is needed and why
     b. Conduct the research (using exploration patterns)
     c. Document findings in Refinement Notes
     d. Apply findings to refine the story
   - **Vague criteria:** Propose specific, verifiable criteria
4. **Ask:** "Ready to move to next story, or refine further?"
5. **Apply** changes and continue

### Populate Refinement Notes

As you refine, update the PRD's Refinement Notes section:

- **Research Conducted:** What was explored and key findings
- **Scope Adjustments:** Stories that were split, combined, or modified
- **Decisions Made:** Key decisions and their rationale

### After all stories reviewed

> "All stories reviewed — any you want to revisit before finalizing?"

### Example refinement

**Before refinement:**
```
US-003: Implement OAuth login flow
- [ ] User can click "Login with Google" button
- [ ] OAuth callback is handled correctly
- [ ] User session is created
- [ ] Works with existing auth system
```

**Refinement catches:**
- "Works with existing auth system" is vague
- This touches UI, API, and session management (multiple areas)
- Need to research: How does existing auth work?

**After refinement:**
```
US-003: Add Google OAuth button to login page
- [ ] Login page shows "Continue with Google" button
- [ ] Button triggers OAuth redirect to Google
- [ ] Typecheck/lint passes

US-004: Handle OAuth callback and create session
- [ ] /auth/callback endpoint receives Google callback
- [ ] Valid callback creates user session using existing SessionService.create()
- [ ] Invalid callback redirects to /login with error param
- [ ] Typecheck/lint passes
```

**Refinement Notes populated:**
```
### Research Conducted
- Existing auth uses SessionService at src/services/session.ts
- Session creation: SessionService.create(userId, metadata)
- Login page at src/pages/login.tsx uses AuthForm component

### Scope Adjustments
- US-003 split into US-003 (UI) and US-004 (callback handling)
- Original US-003 was crossing UI and API layers

### Decisions Made
- Reuse existing SessionService rather than creating OAuth-specific session handling
- Place OAuth callback at /auth/callback to match existing /auth/* routes
```

---

## Step 12: Update tracking files

### Add to BACKLOG.md

Add a reference to the new PRD in `kit_tools/roadmap/BACKLOG.md`:

```markdown
## Planned Features
- [Feature Name](../prd/prd-feature-name.md) — Brief description
```

**For epics (multiple related PRDs):**

```markdown
## OAuth Authentication (Epic)
- [OAuth Schema](../prd/prd-oauth-schema.md) — Database foundation
- [OAuth Provider](../prd/prd-oauth-provider.md) — Provider integration (depends on: schema)
- [OAuth API](../prd/prd-oauth-api.md) — Backend endpoints (depends on: schema, provider)
- [OAuth UI](../prd/prd-oauth-ui.md) — User interface (depends on: api)
```

### Optionally link to MVP_TODO.md

If this feature is part of a milestone, add a link:

```markdown
## [Milestone Name]
- [ ] Feature Name ([PRD](../prd/prd-feature-name.md))
```

---

## Step 13: Summary

Report to the user:

- The feature(s) we planned
- Whether this was decomposed from an epic
- Where the PRD(s) were created
- Number of user stories per PRD
- Refinement status (all stories refined, or skipped)
- Session-readiness status
- Dependencies between PRDs (if applicable)
- Key decisions made during brainstorming and refinement
- Open questions that need resolution
- Recommended next steps

**Example summary:**

> **Feature Planning Complete**
>
> Created 4 PRDs for the OAuth Authentication epic:
>
> | PRD | Stories | Refined | Session Ready | Depends On |
> |-----|---------|---------|--------------|------------|
> | `prd-oauth-schema.md` | 3 | ✓ | ✓ | — |
> | `prd-oauth-provider.md` | 5 | ✓ | ✓ | schema |
> | `prd-oauth-api.md` | 6 | ✓ | ✓ | schema, provider |
> | `prd-oauth-ui.md` | 4 | ✓ | ✓ | api |
>
> **Refinement notes:** 2 stories split during refinement, research conducted on existing SessionService
>
> **Recommended order:** schema → provider → api → ui
>
> **Next steps:**
> 1. Resolve open questions in each PRD
> 2. Run `/kit-tools:execute-feature` on `prd-oauth-schema` to start
> 3. Complete PRDs in dependency order

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
| `/kit-tools:execute-feature` | To execute PRD stories autonomously or with supervision |
| `/kit-tools:complete-feature` | To mark PRD completed and archive it |
| `/kit-tools:start-session` | To orient on active PRDs at session start |

---

**Note:** This skill creates the PRD but does NOT change your Active Feature in the scratchpad. You can brainstorm a new feature while working on something else.
