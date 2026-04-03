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

**Rule of thumb:** If you can't describe the change in 2-3 sentences, it's too big.

---

## Acceptance Criteria Guidance

Each criterion must be **verifiable**, not vague:

| Good | Bad |
|------|-----|
| "Login form shows error message for invalid credentials" | "Works correctly" |
| "API returns 401 for unauthenticated requests" | "Handles auth properly" |

**Target: 3-5 criteria per story.** More than 6 suggests the story is too big.

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
