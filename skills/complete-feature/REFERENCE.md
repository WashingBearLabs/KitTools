# Complete Feature — Reference

Detailed formats, epic handling, and edge cases for the complete-feature workflow.

---

## Epic Handling

### Mid-epic PRD (not `epic_final`)

The orchestrator handles mid-epic completion automatically (tag + archive). If manually invoked:

- Tag checkpoint: `git tag [epic-name]/[feature-name]-complete`
- Archive PRD (update frontmatter, move to archive/)
- **Do NOT** create a PR or merge
- **Do NOT** clean up execution artifacts (other PRDs may need them)

### Final PRD (`epic_final: true`)

- Tag checkpoint
- Archive PRD
- Offer PR for the entire `epic/[name]` branch
- Clean up all execution artifacts

### Standalone PRD (no `epic` field)

Standard behavior — archive, clean up, offer PR/merge.

---

## PR Format — Epic

```
PR title: feat([epic-name]): complete epic

PR body:
## Summary
- prd-[name-1]: [N stories]
- prd-[name-2]: [N stories]
- prd-[name-3]: [N stories]

## Checkpoints
- [epic-name]/[feature-1]-complete
- [epic-name]/[feature-2]-complete
- [epic-name]/[feature-3]-complete
```

Scan `kit_tools/prd/archive/` for all PRDs with the same `epic` field, and `git tag -l` for checkpoint tags.

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

### MVP_TODO.md
- Find line referencing this PRD
- Mark complete: `- [x] Feature Name ([PRD](../prd/archive/prd-auth.md))`
- Update link to archive location

### BACKLOG.md
- Remove from "Planned Features"
- Optionally add to "Completed Features" section

---

## Archive Handling

Move PRD to `kit_tools/prd/archive/`. Create directory if needed.

If file already exists in archive (shouldn't happen):
- Rename existing to `prd-auth-[date].md`
- Then move current PRD

### Why archive instead of delete?
- Preserves Implementation Notes for future reference
- Maintains history of completed features
- Useful for similar future features
- Audit trail

---

## Cleanup Artifacts

**Standalone PRD or final epic PRD:**
- Delete `kit_tools/prd/.execution-state.json`
- Delete `kit_tools/prd/.execution-config.json`
- Delete `kit_tools/.pause_execution`

**Mid-epic PRD:** Do NOT clean up — still needed for subsequent PRDs.

---

## Branch Options

### Standalone PRD
```
Feature branch: feature/auth

1. Create a PR (recommended)
2. Merge to main now
3. Leave it — I'll handle it myself
```

### Epic (final PRD)
```
Epic branch: epic/arxiv

1. Create a PR for the epic (recommended)
2. Merge to main now
3. Leave it — I'll handle it myself
```

- **Autonomous mode** (auto-invoked): Note branch, user merges/PRs after review
- **Supervised/manual mode**: Ask user
