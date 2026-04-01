<!-- Template Version: 2.0.0 -->
<!-- Seeding:
  explorer_focus: none
  required_sections: []
  skip_if: always
  note: Created via plan-epic, not auto-seeded
-->
---
epic: {{EPIC_NAME}}
status: active
vision_ref:
created: {{DATE}}
updated: {{DATE}}
---

<!--
Frontmatter fields:
- epic: Kebab-case epic name (e.g., "user-management")
- status: active | on-hold | completed
- vision_ref: Product Vision reference (optional, section in PRODUCT_VISION.md — e.g., "Feature Area 2: User Management")
- created/updated: Dates in YYYY-MM-DD format
-->

# Epic: {{EPIC_TITLE}}

## Goal

{{One paragraph describing what this epic achieves and why it matters. What capability does completing all child feature specs unlock?}}

## Decomposition

<!--
Ordered list of feature specs that compose this epic.
Sequence determines execution order. Dependencies are tracked in individual feature specs.
-->

| Seq | Feature Spec | Status | Dependencies |
|-----|-------------|--------|--------------|
| 1 | [feature-*.md] | Planned / Active / Completed | None |
| 2 | [feature-*.md] | Planned | feature-*.md |

## Completion Criteria

<!--
How do we know the epic is done? These are higher-level than individual feature spec acceptance criteria.
-->

- [ ] {{All feature specs completed and archived}}
- [ ] {{Integration between features verified}}
- [ ] {{End-to-end user flow validated}}

## Notes

<!--
Running notes, decisions, and context for the epic as a whole.
-->
