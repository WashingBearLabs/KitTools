<!-- Template Version: 2.2.0 -->
---
feature: {{FEATURE_NAME}}
status: active
session_ready: true
depends_on: []
vision_ref:
type: feature
size:
epic:
epic_seq:
epic_final:
created: {{DATE}}
updated: {{DATE}}
---

<!--
Frontmatter fields — see `specs/SCHEMA.md` for full reference, validation rules, and examples.

Quick summary:
- feature: kebab-case name (used as feature branch suffix)
- status: active | on-hold | completed
- session_ready: true once story-quality checks pass; false blocks execution
- depends_on: [feature-names] — hard gate, empty list OK
- vision_ref: free-form reference into PRODUCT_VISION.md (optional)
- size: S | M | L | XL — controls session timeouts and model escalation (default M if omitted)
- type: feature | epic-child
- epic / epic_seq / epic_final: only populated for epic-child specs
- created / updated: YYYY-MM-DD
-->

# Feature Spec: {{FEATURE_TITLE}}

## Overview

{{Brief description of the feature and the problem it solves. What pain point does this address? Why are we building this now?}}

## Goals

- {{Specific, measurable objective 1}}
- {{Specific, measurable objective 2}}
- {{Specific, measurable objective 3}}

## User Stories

<!--
SESSION-FIT GUIDELINES:
- Each story should complete in one focused session (single context window)
- 5-7 acceptance criteria per story (clear, verifiable)
- Order by dependency: schema → backend → UI
- Stories are refined during planning to ensure session-fit
- Implementation Hints give the implementing agent a head start (key files, patterns, gotchas)
- More stories with fewer criteria > fewer stories with many criteria

Story count is not a target — what matters is that each story:
- Has single responsibility (one concern)
- Is session-fit (completable in one context window)
- Has clear, verifiable acceptance criteria
- Has implementation hints (3-5 bullet points of guidance)

Never compress scope by dropping criteria to fit a story size target.
If a story needs more criteria, split the story instead.
-->

### US-001: {{Story Title}}

**Description:** As a {{user type}}, I want {{feature/capability}} so that {{benefit/outcome}}.

**Implementation Hints:**
- {{Key file path or module to modify}}
- {{Existing pattern or function to follow/use}}
- {{Relevant gotcha or constraint}}

**Acceptance Criteria:**
- [ ] {{Specific, verifiable criterion}}
- [ ] {{Another criterion}}
- [ ] Tests written/updated for new functionality
- [ ] Full test suite passes
- [ ] Typecheck/lint passes
<!-- For UI stories, add: -->
<!-- - [ ] Verify in browser -->
<!-- For doc/config-only stories, remove the test criteria above -->

### US-002: {{Story Title}}

**Description:** As a {{user type}}, I want {{feature/capability}} so that {{benefit/outcome}}.

**Implementation Hints:**
- {{Key file path or module to modify}}
- {{Existing pattern to follow}}

**Acceptance Criteria:**
- [ ] {{Criterion}}
- [ ] Tests written/updated for new functionality
- [ ] Full test suite passes
- [ ] Typecheck/lint passes

<!-- Add more user stories as needed -->

## Out of Scope

<!--
What this feature will NOT include. Critical for managing scope and preventing creep.
-->

- {{Explicitly out of scope item 1}}
- {{Explicitly out of scope item 2}}

## Technical Considerations

<!--
Architecture notes, constraints, dependencies.
Link to relevant CODE_ARCH.md sections.
-->

- {{Known constraint or dependency}}
- {{Integration point with existing system}}
- {{Performance requirement}}

## Design Considerations

<!--
Optional. UI/UX requirements, mockups, existing components to reuse.
-->

- {{UI/UX requirement}}
- {{Link to mockup if available}}

## Related Documentation

<!--
KitTools extension: Link to relevant project docs.
Remove any that don't apply.
-->

- Architecture: [CODE_ARCH.md](../arch/CODE_ARCH.md)
- Known Issues: [GOTCHAS.md](../docs/GOTCHAS.md)
- Conventions: [CONVENTIONS.md](../docs/CONVENTIONS.md)

## Implementation Notes

<!--
Populated during and after implementation.
Capture learnings, gotchas discovered, patterns that worked.
This section is valuable for future reference and archival.
-->

## Refinement Notes

<!--
Populated during planning refinement. Documents research conducted and decisions made.
-->

### Research Conducted
<!-- What was explored during refinement and key findings -->

### Scope Adjustments
<!-- Stories that were split, combined, or modified during refinement -->

### Decisions Made
<!-- Key decisions and their rationale -->

## Open Questions

<!--
Unresolved questions or areas needing clarification.
Remove this section when all questions are answered.
-->

- [ ] {{Question 1}}
- [ ] {{Question 2}}
