# Complete Implementation — Reference

Detailed formats, epic handling, and edge cases for the complete-implementation workflow.

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

**Worktree-isolated execution (autonomous/guarded — has a `.kit/` registry record):**
The `.execution-*` state files live inside the worktree, so worktree teardown
(see Branch Options below) removes them. From inside the worktree, only
`set-status <key> completed`; defer removal to the main checkout.

**Legacy / in-dir execution (no registry record):**
- Delete `kit_tools/specs/.execution-state.json`
- Delete `kit_tools/specs/.execution-config.json`
- Delete `kit_tools/.pause_execution`

**Mid-epic feature spec:** Do NOT clean up — still needed for subsequent feature specs.

---

## Worktree Teardown (registry-backed executions)

Run **only from the main checkout**, for standalone/final-epic completion:

```bash
python3 "$CLAUDE_PLUGIN_ROOT/scripts/orchestrator/registry.py" teardown "<key>"
```

The teardown sequence is `worktree remove` → `branch -d` → `worktree prune` →
deregister, and it leans on git's own guards:

| git guard | Effect |
|-----------|--------|
| `git worktree remove` (no `--force`) | Refuses a dirty/untracked worktree → kept + flagged |
| `git branch -d` (lowercase) | Refuses an unmerged branch → kept + flagged (worktree may still be removed if its tree was clean) |

Exit codes: `0` = cleaned; `3` = kept/flagged (surface `messages` to the user, never force); `1` = not a git repo. Force (`--force` / `git branch -D`) only on explicit human instruction.

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

> **Worktree branches:** push/PR from the worktree path, never `git checkout main`
> in the worktree. After the branch decision, run worktree teardown (above).
