<!-- Template Version: 1.1.0 -->
---
feature: {{FEATURE_NAME}}
status: active
ralph_ready: true
depends_on: []
created: {{DATE}}
updated: {{DATE}}
---

<!--
Frontmatter fields:
- feature: Kebab-case feature name (e.g., "user-auth")
- status: active | on-hold | completed
- ralph_ready: true if ≤7 stories and well-scoped; false if needs decomposition
- depends_on: Array of feature names this PRD depends on (for epics)
- created/updated: Dates in YYYY-MM-DD format
-->

# PRD: {{FEATURE_TITLE}}

## Overview

{{Brief description of the feature and the problem it solves. What pain point does this address? Why are we building this now?}}

## Goals

- {{Specific, measurable objective 1}}
- {{Specific, measurable objective 2}}
- {{Specific, measurable objective 3}}

## User Stories

<!--
RALPH-READY GUIDELINES:
- Target 5-7 stories per PRD (max 7 for reliable Ralph execution)
- Each story should complete in one focused session
- 3-5 acceptance criteria per story (max 6)
- Total criteria across all stories: ≤35
- Order by dependency: schema → backend → UI

If this PRD exceeds these limits, set ralph_ready: false in frontmatter
and consider decomposing into multiple PRDs.
-->

### US-001: {{Story Title}}

**Description:** As a {{user type}}, I want {{feature/capability}} so that {{benefit/outcome}}.

**Acceptance Criteria:**
- [ ] {{Specific, verifiable criterion}}
- [ ] {{Another criterion}}
- [ ] Typecheck/lint passes
<!-- For UI stories, add: -->
<!-- - [ ] Verify in browser -->

### US-002: {{Story Title}}

**Description:** As a {{user type}}, I want {{feature/capability}} so that {{benefit/outcome}}.

**Acceptance Criteria:**
- [ ] {{Criterion}}
- [ ] Typecheck/lint passes

<!-- Add more user stories as needed -->

## Functional Requirements

<!--
Numbered list of specific functionalities.
Be explicit and unambiguous.
-->

- **FR-1:** {{The system must...}}
- **FR-2:** {{When a user does X, the system must...}}
- **FR-3:** {{...}}

## Non-Goals

<!--
What this feature will NOT include. Critical for managing scope.
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

## Success Metrics

<!--
How will we measure success? Be specific.
-->

- {{Metric 1: e.g., "Reduce time to X by 50%"}}
- {{Metric 2: e.g., "Zero critical bugs in first week"}}

## Implementation Notes

<!--
Populated during and after implementation.
Capture learnings, gotchas discovered, patterns that worked.
This section is valuable for future reference and archival.
-->

## Open Questions

<!--
Unresolved questions or areas needing clarification.
Remove this section when all questions are answered.
-->

- [ ] {{Question 1}}
- [ ] {{Question 2}}
