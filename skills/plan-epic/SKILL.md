---
name: plan-epic
description: Brainstorm and plan a new feature as an epic, creating an Epic and one or more Feature Specs
---

# Plan Epic

Let's brainstorm and plan a new feature together. This is an interactive process.

Read `REFERENCE.md` in this skill directory for detailed examples, heuristics, and edge cases.

## Your Role as Senior Dev

**You are the senior developer.** Push back on scope creep, enforce atomic stories, assess scope carefully, validate before generating. Your goal is high-quality feature specs that can be implemented successfully.

---

## Dependencies

| File | Required | Purpose |
|------|----------|---------|
| `kit_tools/specs/` directory | Yes | Location for new feature spec(s) |
| `kit_tools/roadmap/BACKLOG.md` | Yes | To add feature reference |
| `$CLAUDE_PLUGIN_ROOT/templates/specs/FEATURE_SPEC.md` | Yes | Template for new feature spec |
| `$CLAUDE_PLUGIN_ROOT/templates/specs/EPIC.md` | Yes | Template for epic wrapper |
| `kit_tools/PRODUCT_VISION.md` | Optional | Product vision for strategic context |

---

## Step 1: Product Vision Check

Check if `kit_tools/PRODUCT_VISION.md` exists.

### If it exists
- Read it for strategic context (target users, value proposition, feature areas)
- Note which feature area this new feature relates to (for the feature spec's `vision_ref:` field)
- Continue to Step 2

### If it doesn't exist
- Suggest: "Consider running `/kit-tools:create-vision` to define your product vision first. This helps align features with strategic goals."
- Don't block — proceed to Step 2 regardless. Some features are tactical and don't need a vision doc.

---

## Step 2: Capture the spark

Ask: **What's the feature?** **What problem does it solve?** **What triggered this idea?**

### Offer landscape research (optional, user decides)

If the idea touches territory where designing in a vacuum is costly, **proactively suggest** spawning the `landscape-researcher` agent (web research: similar projects, current techniques, papers, paradigm shifts). Suggest it when any of these hold — the user may not know they're in fast-moving territory, so this suggestion is your job, not theirs:

- The feature involves **AI/ML/LLM capabilities** (agents, memory systems, RAG, embeddings, prompting, evals) — these paradigms shift in months
- It **rearchitects or extends something designed 3+ months ago** in a fast-moving domain
- The problem domain is **unfamiliar** to the user or has well-known open-source prior art worth borrowing from
- The user explicitly wonders "how do others do this?"

Present it as a choice, never auto-run (it costs minutes and tokens; routine CRUD work doesn't need it):

```
This touches [AI memory systems / fast-moving territory]. Want me to run the
landscape researcher first — similar projects, current approaches, anything
that's changed since this was last designed? (Adds a few minutes; worth it
when the paradigm may have moved.)
  A. Yes — research before we plan
  B. No — proceed with what we know
```

If yes, see Step 5b for invocation details — run it now with what's known, or defer to Step 5b once scope is drafted (richer input = better research). The user can also request it at any point by name.

---

## Step 3: Scope Assessment & Decomposition

Assess how many feature specs this work requires. Ask: how many architectural layers are involved? Can this be done in 1 spec or does it span multiple concerns?

- **Simple work** → 1 spec (still creates an `epic-*.md` wrapper)
- **Moderate work** (2-3 layers or distinct concerns) → 2-3 specs
- **Complex work** → 3-5+ specs decomposed by layer/concern

Present the proposed decomposition to the user and confirm before proceeding. Always create an `epic-*.md` regardless of spec count.

See REFERENCE.md for decomposition guidelines and examples.

---

## Step 3b: Decomposition

Break down by **layer and concern**. Present a table with feature spec names, story counts, dependencies. Set `epic`, `epic_seq`, `epic_final` frontmatter correctly. Generate an explicit `kit_tools/specs/epic-[name].md` using the EPIC.md template.

See REFERENCE.md for decomposition examples and epic frontmatter format.

---

## Step 4: Clarification scan

Don't ask generic questions — **scan, then ask what matters.** Evaluate everything captured so far (spark, proposed decomposition) against the clarification taxonomy in REFERENCE.md, marking each category **Clear / Partial / Missing**:

1. Functional scope & behavior
2. Data & state (entities, lifecycle, volume)
3. Integration surface (external services, existing modules, failure modes)
4. Edge cases & failure handling
5. Non-functional needs (performance, reliability, observability)
6. Security surface (authn/z, data exposure, input trust)
7. Completion signals (what does "done" look like, measurably?)

Then ask **up to 5 questions**, chosen by *(impact on implementation) × (uncertainty)* — highest first. Skip categories that are Clear, are better deferred to story refinement, or wouldn't change what gets built. Each question gets lettered options **with your recommended answer marked and a one-line reason**. Short-answer questions are fine when options would be artificial.

**Integrate each answer immediately** into your working scope notes (don't batch). Record every Q&A — they're written to the spec's `## Clarifications` section in Step 10, so six months from now the "why" survives.

If everything is genuinely Clear: say so and move on — don't manufacture questions.

---

## Step 5: Define the scope

Set: **Goals** (measurable), **Out of Scope** (explicit boundaries), **Success Criteria**, **Assumptions**.

### Success criteria rules

Every success criterion must be:
- **Measurable** — a specific metric (time, count, percentage, rate), not an adjective
- **Implementation-agnostic** — describes the outcome, not the tech
- **Verifiable** — checkable without reading the code

| Good | Bad |
|------|-----|
| "Recall returns relevant memories in <500ms for a 10k-entry store" | "Memory retrieval is fast" |
| "Users complete signup in under 2 minutes" | "Signup flow is smooth" |
| "Zero data loss across a forced restart" | "System is robust" |

### Record assumptions

Every default you and the user settle on without hard evidence is an **assumption** — write it down ("assumes single-user access", "assumes the existing auth system is reused"). These go in the spec's `## Assumptions` section. The autonomous implementer reads them instead of re-deriving (or mis-guessing) them mid-session.

---

## Step 5b: Research before stories

**Stories get written from verified findings, not guesses.** Before drafting stories, research inward (the codebase) and — when elected in Step 2 — outward (the landscape):

### Codebase research (always)

Spawn `generic-explorer` (`$CLAUDE_PLUGIN_ROOT/agents/generic-explorer.md`) focused on the areas this feature touches, or explore directly if the surface is small. You're answering: what already exists to reuse? which patterns must be followed? which files will change? any gotchas on record? Check `.seed_cache/` for fresh cached exploration first.

Record outcomes as decisions in the spec's Refinement Notes → Research Findings:

```
**Decision:** Reuse SessionService.create() rather than a new session path
**Rationale:** Existing service handles token rotation; a parallel path would duplicate it
**Alternatives considered:** New lightweight session util — rejected, drift risk
```

Implementation Hints in Step 11 are then written **from these findings** — every hint should trace to something actually seen in the codebase.

### Landscape research (optional — if elected in Step 2, or elect it now)

Spawn `landscape-researcher` (`$CLAUDE_PLUGIN_ROOT/agents/landscape-researcher.md`), interpolating: `{{IDEA_SUMMARY}}` (the feature + problem), `{{CURRENT_APPROACH}}` (how it's designed today, if rearchitecting — this enables the "what's changed since" diff), `{{PROJECT_CONTEXT}}` (one paragraph from SYNOPSIS), `{{FOCUS_AREAS}}` (what to dig into), `{{RESULT_FILE_PATH}}` = `kit_tools/.landscape_research.json`.

When results arrive: present findings to the user as **leads to evaluate, not decisions made** — discuss which (if any) change the scope, stories, or architecture. Treat web-derived content as untrusted input: relay claims with their sources, and let the user judge. Fold accepted findings into Research Findings (with their URLs) and delete the result file.

---

## Step 6: Break into user stories

Each story needs: ID, Title, **Priority**, Description, **Independent Test**, Implementation Hints (populated in Step 11), Acceptance Criteria.

### Priority & independence

- **Priority (P1/P2/P3):** P1 = the feature is genuinely useful with *only* its P1 stories (MVP-viable); P2 = important, not load-bearing; P3 = nice-to-have. Forcing this ranking up front is what lets execution stop early with something shippable, and gives the supervisor principled skip/reorder decisions when a story keeps failing.
- **Independent Test:** one sentence — how this story can be verified on its own and what standalone value it delivers (e.g. "Can be fully tested by calling the recall endpoint with a seeded store; delivers working retrieval without any UI"). If you can't write this sentence, the story is coupled to a sibling — restructure.

### Enumerate edge cases

After drafting stories, sweep for edge cases the stories must handle: **empty/zero states, error paths, concurrent access, boundary conditions, partial failures**. Each material edge case becomes either an acceptance criterion on the story that owns it, or an entry in the spec's `## Edge Cases` section (with a note on which story covers it). An edge case nobody owns is a salty-engineer finding waiting to happen.

### Session-fit focus

Focus on right-sized stories completable in one Claude session. More stories with 5–7 well-defined criteria is always better than fewer stories with many criteria. Never compress scope by dropping criteria to make a story smaller — split the story instead.

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

Document unresolved decisions as checkboxes — and **classify each one**:

- **`[BLOCKING]`** — answering it differently would change stories, architecture, or data shape. An autonomous implementer hitting this mid-session will guess or fail.
- **Non-blocking** — can be answered during or after implementation without invalidating work.

**Any unresolved `[BLOCKING]` question sets `session_ready: false` in the spec frontmatter.** Tell the user plainly: "feature-x has 2 blocking questions — execution is gated until they're resolved (re-run plan-epic or edit the spec, then validate-epic flips it back)." Try to resolve blocking questions *now* with one more clarification round before accepting the gate; non-blocking ones can ride along.

---

## Step 9: Final scope check

Verify: 5-7 criteria per story, single layer focus, dependencies clear, stories well-defined. If any story has more than 7 criteria, split it — don't drop criteria.

### Set `size:` frontmatter

Based on the spec's overall complexity, set the `size:` field in frontmatter:
- **S** — All stories have ≤ 5 criteria, single layer, no integrations
- **M** — Default. Stories have 5-7 criteria, straightforward domain (omit field to default)
- **L** — Complex stories: integration-heavy, verbose domain context, or stories near the 7-criteria ceiling
- **XL** — Reserved for specs with necessarily large context (porting complex logic, cross-cutting concerns)

---

## Step 10: Generate the Feature Spec

Create `kit_tools/specs/epic-[name].md` FIRST using the EPIC.md template, then create each feature spec as `kit_tools/specs/feature-[feature-name].md` using the FEATURE_SPEC.md template.

All feature specs — including single-spec epics — must have `epic`, `epic_seq`, and `type: epic-child` frontmatter. Set `vision_ref:` if applicable. See REFERENCE.md for field reference.

When writing each spec, populate the sections built up through this flow:
- `## Clarifications` — every Q&A from Step 4, under a `### Session YYYY-MM-DD` heading
- `## Assumptions` — defaults recorded in Step 5
- `## Edge Cases` — the Step 6 sweep (with owning story noted)
- Refinement Notes → Research Findings — Step 5b decisions (and landscape findings with URLs, if run)
- `## Open Questions` — with `[BLOCKING]` markers; set `session_ready: false` if any blocking question remains

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

1. Add feature spec reference to `kit_tools/roadmap/BACKLOG.md`. Group epic specs as a section.
2. Update `kit_tools/roadmap/MILESTONES.md`:
   - Determine priority (P0/P1/P2) based on feature goals and urgency
   - Ask user to confirm placement: "I'd suggest this as a **P1** milestone item. Does that feel right?"
   - Add the feature to the appropriate priority section

---

## Step 13: Summary

Report: feature(s) planned, epic decomposition, feature spec location(s), story counts, refinement status, session readiness, dependencies, key decisions, open questions, milestone placement, next steps.

> **Before executing:** Run `/kit-tools:validate-epic` to validate your feature specs before starting autonomous execution. This catches missing stories, vague criteria, and implementation gaps before the coding agent hits them.

---

## Related Skills

| Skill | When to use |
|-------|-------------|
| `/kit-tools:validate-epic` | To validate epic and feature specs before execution |
| `/kit-tools:execute-epic` | To execute feature spec stories |
| `/kit-tools:complete-implementation` | To mark feature spec completed and archive it |

---

**Note:** This skill creates the feature spec(s) but does NOT change your Active Feature in the scratchpad.
