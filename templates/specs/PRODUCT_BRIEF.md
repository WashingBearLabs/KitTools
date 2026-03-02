<!-- Template Version: 2.0.0 -->
<!-- Seeding:
  explorer_focus: none
  required_sections: []
  skip_if: always
  note: Created via plan-feature, not auto-seeded
-->
---
brief: {{BRIEF_NAME}}
status: draft
created: {{DATE}}
updated: {{DATE}}
---

<!--
Frontmatter fields:
- brief: Kebab-case brief name (e.g., "user-management")
- status: draft | active | completed
- created/updated: Dates in YYYY-MM-DD format
-->

# Product Brief: {{BRIEF_TITLE}}

## Problem Statement

<!--
What problem are we solving? Who has this problem? What's the cost of not solving it?
-->

{{Describe the problem clearly and concisely}}

## Target Users

<!--
Who will use this? Be specific about user segments.
-->

- {{User segment 1 — role and context}}
- {{User segment 2 — role and context}}

## Strategic Context

<!--
Why now? How does this fit into the product roadmap? What decisions led here?
-->

{{Explain the strategic reasoning and timing}}

## Success Metrics

<!--
How will we measure success at the product level? Be specific and measurable.
-->

- {{Metric 1: e.g., "Reduce time to X by 50%"}}
- {{Metric 2: e.g., "Zero critical bugs in first week"}}
- {{Metric 3: e.g., "80% adoption within target users"}}

## Scope Boundaries

<!--
High-level boundaries for the entire product area. Individual feature specs define granular scope.
-->

### In Scope
- {{What this product area covers}}

### Out of Scope
- {{What this product area explicitly does not cover}}

## Key Risks

<!--
What could go wrong? What assumptions are we making?
-->

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| {{Risk 1}} | Low/Med/High | Low/Med/High | {{How to mitigate}} |

## Feature Decomposition

<!--
Break this product area into individual feature specs. Each row links to a feature-*.md file.
-->

| Seq | Feature Spec | Status | Description |
|-----|-------------|--------|-------------|
| 1 | [feature-*.md] | Planned | {{Brief description}} |

## Open Questions

<!--
Unresolved questions at the product level.
Remove this section when all questions are answered.
-->

- [ ] {{Question 1}}
- [ ] {{Question 2}}
