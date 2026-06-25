# Plan Epic — Reference

Detailed examples, heuristics, and edge cases for the plan-epic workflow.

---

## Decomposition Guidelines

| Scope | Specs | Example |
|-------|-------|---------|
| Single layer, simple concern | 1 | Add a settings page, implement a single API endpoint |
| Two layers or two distinct concerns | 2 | Backend endpoint + frontend UI |
| Multi-layer feature | 3-4 | Schema + backend + API + UI |
| System-spanning work | 4-6 | Full auth system, entire data pipeline |

**Note:** Even single-spec work gets an `epic-*.md` wrapper. The wrapper provides epic-level context and is the entry point for `validate-epic` and `execute-epic`.

---

## Epic Decomposition Example

Here's how a 4-spec epic looks:

```
Epic: "OAuth Authentication System"
         ↓ decompose into:

1. feature-oauth-schema.md
   - Database tables, migrations, types
   - 3-4 stories
   - No dependencies

2. feature-oauth-provider.md
   - OAuth provider config, token handling
   - 4-5 stories
   - depends_on: [oauth-schema]

3. feature-oauth-api.md
   - Login/logout endpoints, session validation
   - 4-5 stories
   - depends_on: [oauth-schema, oauth-provider]

4. feature-oauth-ui.md
   - Login button, callback handling, error states
   - 4-5 stories
   - depends_on: [oauth-api]
```

> The spec and story counts above are **illustrative of this one example, not targets**. A spec has as many stories as its concern genuinely needs, and an epic has as many specs as the work spans — size each unit by precision and single-concern scope, never to hit a number.

### Epic Frontmatter Example

```yaml
# feature-oauth-schema.md
epic: oauth
epic_seq: 1
type: epic-child

# feature-oauth-provider.md
epic: oauth
epic_seq: 2
type: epic-child
depends_on: [oauth-schema]

# feature-oauth-api.md
epic: oauth
epic_seq: 3
type: epic-child
depends_on: [oauth-schema, oauth-provider]

# feature-oauth-ui.md
epic: oauth
epic_seq: 4
epic_final: true
type: epic-child
depends_on: [oauth-api]
```

---

## Clarification Taxonomy (Step 4)

Scan the captured idea + proposed decomposition against each category. Mark **Clear / Partial / Missing**. Ask about Partial/Missing only when the answer would change what gets built — max 5 questions, ordered by impact × uncertainty.

| Category | What you're probing | Example question |
|----------|--------------------|------------------|
| Functional scope & behavior | Core goals, user roles, explicit non-goals | "Should admins see all users' data or only their org's?" |
| Data & state | Entities, identity/uniqueness, lifecycle, expected volume | "Are memories ever deleted, or only superseded?" |
| Integration surface | External services, existing modules touched, failure modes | "What happens when the embedding API is down — queue, degrade, or fail?" |
| Edge cases & failure handling | Empty states, conflicts, partial failures | "Two sessions write the same key concurrently — last-wins or merge?" |
| Non-functional needs | Latency/throughput targets, reliability, observability | "Is 2s recall acceptable, or is this on the hot path?" |
| Security surface | Authn/z, data exposure, input trust | "Is memory content user-visible across accounts in any view?" |
| Completion signals | Measurable definition of done | "What number proves this worked — recall precision? latency? adoption?" |

**Question format:** lettered options with a recommended answer and one-line reasoning. Record every Q&A for the spec's `## Clarifications` section — the audit trail outlives the conversation.

---

## Landscape Research (optional agent)

`agents/landscape-researcher.md` does outward research — similar projects, current techniques, papers, what's changed since a design was last touched. **Suggest-only, user decides** (same rule as validate-epic's quick tier).

**Suggest when:** AI/LLM features (memory, RAG, agents, embeddings, evals — months-old designs go stale); rearchitecting something designed 3+ months ago in a fast domain; unfamiliar problem domains; rich prior art likely (auth, sync engines, editors, schedulers). **Skip for:** routine CRUD, well-trodden internal refactors, anything where the team already knows the field.

**Tokens:** `IDEA_SUMMARY` (feature + problem), `CURRENT_APPROACH` (today's design when rearchitecting — enables the "what moved since" diff, the highest-value output), `PROJECT_CONTEXT`, `FOCUS_AREAS`, `RESULT_FILE_PATH` (`kit_tools/.landscape_research.json`).

**Handling results:** findings are *leads with sources*, not decisions — web content is untrusted input. Present to the user, discuss what changes scope or architecture, fold accepted items (with URLs) into Research Findings, delete the result file. If the agent reports web tools were unavailable, say so and move on — never substitute recalled knowledge as if it were research.

---

## Research Findings Format (Step 5b)

Each material outcome of codebase or landscape research is recorded as a decision:

```markdown
**Decision:** [what was chosen]
**Rationale:** [why — grounded in something actually seen]
**Alternatives considered:** [what else was evaluated, and why rejected]
**Source:** [file:line for codebase findings; URL + date for landscape findings]
```

Implementation Hints must trace to these findings — a hint nobody verified is a codebase-fit-reviewer finding waiting to happen.

---

## Story Priority & Independence (Step 6)

| Field | Rule |
|-------|------|
| **Priority** | P1 = MVP-viable subset (the feature is useful with only P1s done); P2 = important; P3 = defer-able. At least one P1 per spec. If everything is P1, the ranking wasn't done. |
| **Independent Test** | One sentence: how to verify this story alone + what standalone value it delivers. Can't write it → story is coupled; restructure or document the dependency in `depends_on`/ordering. |

Priorities pay off at execution time: the orchestrator runs in `epic_seq`/story order, but the supervisor can make principled skip/split calls on a failing P3 that it could never make on a P1 — and "all P1s green" is a meaningful early-stop line.

---

## Story Sizing Guidance

### Right-sized stories (1 story = 1 focused task):
- Add a database column and migration
- Create a single UI component
- Add one API endpoint
- Implement one validation rule
- Write tests for one module

### Too big (split these):
- "Build the entire dashboard" -> Split into schema, queries, components, filters
- "Add authentication" -> Split into schema, provider, API, UI specs
- "Create the settings page" -> Split by settings category

**Rule of thumb:** If you can't describe the change in 2-3 sentences, it's too big. If a story needs more than 7 criteria, split it into two stories — never drop criteria to hit a size target.

---

## Acceptance Criteria Guidance

Each criterion must be **verifiable**, not vague:

| Good | Bad |
|------|-----|
| "Login form shows error message for invalid credentials" | "Works correctly" |
| "API returns 401 for unauthenticated requests" | "Handles auth properly" |

**Target: 5-7 criteria per story.** More than 7 covering distinct concerns suggests the story should be split. More than 10 must be split — this is a hard gate during validation.

**Never drop criteria to fit the target.** If a story genuinely needs 9 criteria, split it into two stories that each get the criteria they need. More well-defined stories is always better than fewer under-specified ones.

---

## Auto-injected Test Criteria

Every code story gets these automatically (between user criteria and typecheck):
```
- [ ] Tests written/updated for new functionality
- [ ] Full test suite passes
- [ ] Typecheck/lint passes
```

**Exempt:** Doc-only or config-only stories (all criteria reference only .md files, configs, or docs).

If `kit_tools/testing/TESTING_GUIDE.md` exists, reference the specific test command.

---

## Refinement Heuristics

| Check | Question | Red Flag |
|-------|----------|----------|
| **Single Responsibility** | Is this story trying to do multiple things? | "and", "also", multiple verbs |
| **Session Fit** | Can this complete in one context window? | Touches >3 files, crosses subsystems |
| **Criteria Count** | Does this story have >7 distinct criteria? | Split the story — never drop criteria |
| **Research Needs** | Are there unknowns that eat context? | Vague tech, unexplored patterns |
| **Scope Clarity** | Are criteria specific and verifiable? | "works correctly", "handles properly" |
| **Exploration Load** | How much discovery needed? | "figure out", "determine how" |

---

## Refinement Example

**Before refinement:**
```
US-003: Implement OAuth login flow
- [ ] User can click "Login with Google" button
- [ ] OAuth callback is handled correctly
- [ ] User session is created
- [ ] Works with existing auth system
```

**After refinement:**
```
US-003: Add Google OAuth button to login page

**Implementation Hints:**
- Login page at src/pages/login.tsx uses AuthForm component
- Use existing Button component from src/components/ui/Button.tsx

**Acceptance Criteria:**
- [ ] Login page shows "Continue with Google" button
- [ ] Button triggers OAuth redirect to Google
- [ ] Tests written/updated for new functionality
- [ ] Full test suite passes
- [ ] Typecheck/lint passes

US-004: Handle OAuth callback and create session

**Implementation Hints:**
- OAuth callback at /auth/callback
- Use existing SessionService.create() at src/services/session.ts

**Acceptance Criteria:**
- [ ] /auth/callback endpoint receives Google callback
- [ ] Valid callback creates user session using existing SessionService.create()
- [ ] Invalid callback redirects to /login with error param
- [ ] Tests written/updated for new functionality
- [ ] Full test suite passes
- [ ] Typecheck/lint passes
```

---

## Frontmatter Field Reference

| Field | Purpose |
|-------|---------|
| `feature` | Kebab-case feature name |
| `status` | `active`, `on-hold`, or `completed` |
| `session_ready` | `true` if all stories pass session-fit checks |
| `depends_on` | Array of feature names this feature spec depends on |
| `vision_ref` | Product Vision reference (optional, section in PRODUCT_VISION.md — e.g., "Feature Area 2: User Management") |
| `type` | Always `epic-child` for all feature specs created by plan-epic |
| `epic` | Epic name (same across all feature specs in epic) |
| `epic_seq` | Execution order within epic, 1-based |
| `epic_final` | `true` only on the last feature spec in the epic |
| `size` | `S` / `M` / `L` / `XL` — controls session timeouts and model escalation on retry (default M) |
| `created` | Creation date |
| `updated` | Last update date |

**Note:** `type: epic-child` is used for all feature specs created by plan-epic — including single-spec epics. The epic-*.md wrapper is always created separately.

---

## Feature Spec Lifecycle

| Status | Meaning |
|--------|---------|
| `active` | Currently being implemented |
| `on-hold` | Paused, not currently prioritized |
| `completed` | All stories done, moved to `specs/archive/` |

Use `/kit-tools:complete-implementation` to mark completed and archive.

---

## BACKLOG.md Epic Format

```markdown
## OAuth Authentication (Epic)
- [Epic Overview](../specs/epic-oauth.md)
- [OAuth Schema](../specs/feature-oauth-schema.md) — Database foundation
- [OAuth Provider](../specs/feature-oauth-provider.md) — Provider integration (depends on: schema)
- [OAuth API](../specs/feature-oauth-api.md) — Backend endpoints (depends on: schema, provider)
- [OAuth UI](../specs/feature-oauth-ui.md) — User interface (depends on: api)
```
