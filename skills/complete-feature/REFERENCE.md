# Complete Feature — Reference

Detailed formats, epic handling, and edge cases for the complete-feature workflow.

---

## Epic Handling

### Mid-epic feature spec (not `epic_final`)

The orchestrator handles mid-epic completion automatically (tag + archive). If manually invoked:

- Tag checkpoint: `git tag [epic-name]/[feature-name]-complete`
- Archive feature spec (update frontmatter, move to archive/)
- **Do NOT** create a PR or merge
- **Do NOT** clean up execution artifacts (other feature specs may need them)

### Final feature spec (`epic_final: true`)

- Tag checkpoint
- Archive feature spec
- Offer PR for the entire `epic/[name]` branch
- Clean up all execution artifacts

### Standalone feature spec (no `epic` field)

Standard behavior — archive, clean up, offer PR/merge.

---

## PR Format — Epic

```
PR title: feat([epic-name]): complete epic

PR body:
## Summary
- feature-[name-1]: [N stories]
- feature-[name-2]: [N stories]
- feature-[name-3]: [N stories]

## Checkpoints
- [epic-name]/[feature-1]-complete
- [epic-name]/[feature-2]-complete
- [epic-name]/[feature-3]-complete
```

Scan `kit_tools/specs/archive/` for all feature specs with the same `epic` field, and `git tag -l` for checkpoint tags.

---

## Frontmatter Update

```yaml
---
feature: auth
status: completed      # Changed from 'active'
created: 2025-01-15
updated: 2025-02-01    # Today's date
completed: 2025-02-01  # Add completion date
---
```

---

## Tracking File Updates

### MILESTONES.md
- Find line referencing this feature spec
- Mark complete: `- [x] Feature Name ([Feature Spec](../specs/archive/feature-auth.md))`
- Update link to archive location

### BACKLOG.md
- Remove from "Planned Features"
- Optionally add to "Completed Features" section

---

## Archive Handling

Move feature spec to `kit_tools/specs/archive/`. Create directory if needed.

If file already exists in archive (shouldn't happen):
- Rename existing to `feature-auth-[date].md`
- Then move current feature spec

### Why archive instead of delete?
- Preserves Implementation Notes for future reference
- Maintains history of completed features
- Useful for similar future features
- Audit trail

---

## Cleanup Artifacts

**Standalone feature spec or final epic feature spec:**
- Delete `kit_tools/specs/.execution-state.json`
- Delete `kit_tools/specs/.execution-config.json`
- Delete `kit_tools/.pause_execution`

**Mid-epic feature spec:** Do NOT clean up — still needed for subsequent feature specs.

---

## Branch Options

### Standalone feature spec
```
Feature branch: feature/auth

1. Create a PR (recommended)
2. Merge to main now
3. Leave it — I'll handle it myself
```

### Epic (final feature spec)
```
Epic branch: epic/arxiv

1. Create a PR for the epic (recommended)
2. Merge to main now
3. Leave it — I'll handle it myself
```

- **Autonomous mode** (auto-invoked): Note branch, user merges/PRs after review
- **Supervised/manual mode**: Ask user
