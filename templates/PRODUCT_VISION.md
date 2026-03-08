<!-- Template Version: 2.0.0 -->
<!-- Seeding:
  explorer_focus: none
  required_sections: []
  skip_if: always
  note: Created interactively by create-vision skill, not auto-seeded
-->
# PRODUCT_VISION.md

> **TEMPLATE_INTENT:** Singular strategic document capturing the product's why, who, and what. Guides feature planning and prioritization. One per project.

> Last updated: YYYY-MM-DD
> Updated by: [Human/Claude]

---

## Product Vision Statement

<!--
One paragraph describing the product's purpose and aspiration. What does this product exist to do? What future does it create?
-->

{{A concise, inspiring statement of what this product is and why it matters}}

---

## Target Users & Personas

<!--
Who is this product for? Be specific about user segments, their roles, and their context.
-->

| Persona | Role / Context | Primary Need | Pain Point |
|---------|---------------|--------------|------------|
| {{Persona 1}} | {{Role and context}} | {{What they need}} | {{What frustrates them today}} |
| {{Persona 2}} | {{Role and context}} | {{What they need}} | {{What frustrates them today}} |

---

## Value Proposition

<!--
What unique value does this product provide? Why would target users choose this over alternatives?
-->

**For** {{target users}}
**Who** {{have this need/problem}}
**This product** {{provides this capability}}
**Unlike** {{alternatives or current approach}}
**Our approach** {{key differentiator}}

---

## Success Criteria

<!--
How will we measure whether this product is succeeding? Be specific and measurable.
-->

| Criterion | Metric | Target |
|-----------|--------|--------|
| {{Criterion 1}} | {{How to measure}} | {{Target value or threshold}} |
| {{Criterion 2}} | {{How to measure}} | {{Target value or threshold}} |
| {{Criterion 3}} | {{How to measure}} | {{Target value or threshold}} |

---

## Feature Areas

<!--
Major capability areas organized by tier. Each feature area may become one or more feature specs.
Use tier-prefixed IDs (T1.1, T1.2, T2.1) to avoid cascading renumber pain when adding features.
Link to feature specs as they are created via /kit-tools:plan-feature.
-->

### Tier 1 — Core (MVP)

#### T1.1 — {{Feature Area Name}}
- **Description:** {{What this area covers and why it matters}}
- **Feature Spec(s):** —
- **Status:** Planned

#### T1.2 — {{Feature Area Name}}
- **Description:** {{What this area covers and why it matters}}
- **Feature Spec(s):** —
- **Status:** Planned

### Tier 2 — Extended

#### T2.1 — {{Feature Area Name}}
- **Description:** {{What this area covers and why it matters}}
- **Feature Spec(s):** —
- **Status:** Planned

### Tier 3 — Future

#### T3.1 — {{Feature Area Name}}
- **Description:** {{What this area covers and why it matters}}
- **Feature Spec(s):** —
- **Status:** Planned

---

## Build Order

<!--
How do the feature areas depend on each other? What gets built first?
This section answers "what do I build first?" — the dependency graph between feature areas.
-->

### Dependency Graph
<!-- List feature areas and what they depend on. Use tier-prefixed IDs. -->

| Feature | Depends On | Notes |
|---------|-----------|-------|
| {{T1.1}} | — | {{Foundation, no dependencies}} |
| {{T1.2}} | T1.1 | {{Why this dependency exists}} |
| {{T2.1}} | T1.1, T1.2 | {{Why these dependencies exist}} |

### Suggested Build Sequence
<!-- Ordered list of implementation phases based on the dependency graph. -->

1. **Phase 1:** {{T1.1 — Rationale for why this is first}}
2. **Phase 2:** {{T1.2 — What it unblocks}}
3. **Phase 3:** {{T2.1 — Why it follows}}

---

## Walking Skeleton

<!--
The thinnest possible end-to-end slice that proves the architecture works.
This is NOT the MVP — it's the minimal vertical slice that touches every layer
(UI → logic → data → integration) to validate the approach before building out.
-->

**Slice:** {{One sentence describing the thinnest end-to-end path through the system}}

**Layers touched:**
- {{UI/Frontend}}: {{What the user sees/does}}
- {{Logic/Backend}}: {{What processing happens}}
- {{Data/Storage}}: {{What gets persisted}}
- {{Integration}}: {{What external systems are involved, if any}}

**Proves:** {{What architectural assumption this validates}}

---

## Constraints & Assumptions

<!--
What are we assuming to be true? What constraints shape the product?
-->

### Constraints
- {{Technical, business, or resource constraint}}

### Assumptions
- {{Assumption we're making that could change}}

---

## Open Questions

<!--
Unresolved strategic questions. Remove this section when all questions are answered.
-->

- [ ] {{Question 1}}
- [ ] {{Question 2}}
