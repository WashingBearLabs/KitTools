<!-- Template Version: 1.0.0 -->
<!-- Seeding:
  explorer_focus: none
  required_sections: []
  skip_if: never
  note: Schema reference, not instantiated per feature
-->
# Feature Spec & Epic Frontmatter Schema

Canonical reference for YAML frontmatter on `feature-*.md` and `epic-*.md` files. The orchestrator, validators, and `plan-epic` / `execute-epic` skills all depend on this schema — deviations silently break routing, dependency gates, and execution flow. This file ships with the plugin; read it before authoring specs by hand.

---

## Feature Spec Fields (`feature-*.md`)

```yaml
---
feature: user-auth              # required
status: active                  # required
session_ready: true             # required
depends_on: []                  # required (empty array for no deps)
vision_ref: "Feature Area 2"    # optional
type: feature                   # required
epic: user-auth-epic            # optional (empty for standalone)
epic_seq: 1                     # optional (empty for standalone)
epic_final: false               # optional (empty for standalone)
created: 2026-04-16             # required
updated: 2026-04-16             # required
---
```

| Field | Type | Required | Values | Notes |
|-------|------|----------|--------|-------|
| `feature` | string | yes | kebab-case (`user-auth`, `payment-flow`) | Used as feature branch suffix (`feature/user-auth`) and in orchestrator state keys. |
| `status` | enum | yes | `active` \| `on-hold` \| `completed` | `completed` moves the spec to `specs/archive/` via `/kit-tools:complete-implementation`. |
| `session_ready` | bool | yes | `true` \| `false` | `false` blocks execution. Set by `/kit-tools:plan-epic` / `/kit-tools:validate-epic` when story-quality checks fail. Manually set `true` only if you've resolved flagged issues. |
| `depends_on` | list[string] | yes | List of feature names | Hard gate: a feature spec is not picked up by `execute-epic` until all entries have archived specs. Use the feature name only (no `feature-` prefix). Empty list is valid. |
| `vision_ref` | string | optional | Free-form reference into `PRODUCT_VISION.md` | Used by spec reviewers for vision-alignment checks. If absent, vision dimension is skipped (not flagged). |
| `type` | enum | yes | `feature` \| `epic-child` | Always `feature` for standalone; `epic-child` for specs decomposed from an epic. |
| `epic` | string | optional | Kebab-case epic name | Links this spec to a parent epic. Must match a sibling `epic-*.md` file's `epic` field. Empty for standalone. |
| `epic_seq` | int | optional | 1-based integer | Execution order within the epic. Must be unique and contiguous within the epic. Empty for standalone. |
| `epic_final` | bool | optional | `true` only on last epic child | Triggers epic-completion handling in `execute-epic`. Empty/false on all other children. Exactly one child must set `true`. |
| `created` | date | yes | `YYYY-MM-DD` | Authored date. Never updated. |
| `updated` | date | yes | `YYYY-MM-DD` | Bumped on every edit (hooks handle this automatically). |

## Epic Fields (`epic-*.md`)

```yaml
---
epic: user-auth-epic            # required
status: active                  # required
vision_ref: "Feature Area 2"    # optional
created: 2026-04-16             # required
updated: 2026-04-16             # required
---
```

| Field | Type | Required | Values | Notes |
|-------|------|----------|--------|-------|
| `epic` | string | yes | Kebab-case (`user-auth-epic`) | Must match the `epic` field on all child `feature-*.md` files. |
| `status` | enum | yes | `active` \| `on-hold` \| `completed` | `completed` when all child specs are archived and completion criteria met. |
| `vision_ref` | string | optional | Free-form reference into `PRODUCT_VISION.md` | Same semantics as feature specs. |
| `created` | date | yes | `YYYY-MM-DD` | Authored date. |
| `updated` | date | yes | `YYYY-MM-DD` | Bumped on edits. |

---

## Common Patterns

### Standalone feature (no epic)

```yaml
---
feature: payment-refunds
status: active
session_ready: true
depends_on: []
type: feature
created: 2026-04-16
updated: 2026-04-16
---
```

### Feature that depends on another feature

```yaml
---
feature: payment-invoicing
status: active
session_ready: true
depends_on: [payment-core, user-auth]
type: feature
created: 2026-04-16
updated: 2026-04-16
---
```

### Epic child (second of four specs)

```yaml
---
feature: user-auth-provider
status: active
session_ready: true
depends_on: [user-auth-schema]
type: epic-child
epic: user-auth-epic
epic_seq: 2
epic_final: false
created: 2026-04-16
updated: 2026-04-16
---
```

### Epic child (last spec in the epic)

```yaml
---
feature: user-auth-ui
status: active
session_ready: true
depends_on: [user-auth-api]
type: epic-child
epic: user-auth-epic
epic_seq: 4
epic_final: true
created: 2026-04-16
updated: 2026-04-16
---
```

---

## Gotchas

- **`depends_on` uses feature names, not file paths.** `depends_on: [user-auth]`, not `depends_on: [feature-user-auth.md]`.
- **`epic_final` is exclusive.** Exactly one child in an epic sets it. `execute-epic` uses this to trigger epic-level completion after the final child archives.
- **`session_ready: false` blocks execution.** If `plan-epic` flags story-quality issues, this gets set to `false`. Fix the flagged issues, then set back to `true`.
- **Dates must be `YYYY-MM-DD`.** The `update_doc_timestamps` hook writes this format and readers parse it strictly.
- **Don't edit frontmatter during execution.** The orchestrator reads the spec file per-story; mutating frontmatter mid-run can invalidate dependency chains.
- **Empty epic/epic_seq/epic_final fields** on standalone features should be literally empty (`epic:` with nothing after), not `null` or `""`.

---

## Validation

`/kit-tools:validate-epic` checks this schema via the `story-quality-reviewer` and `spec-completionist-reviewer` agents. Invalid frontmatter surfaces as critical findings before execution starts.
