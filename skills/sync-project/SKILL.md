---
name: sync-project
description: Detect and fix drift between kit_tools documentation and the actual codebase. Full mode rewrites stale docs; `--quick` runs a lightweight audit for monthly check-ins; `--resume` continues an interrupted sync. Invoke when docs feel outdated, after significant refactors, or when onboarding surfaces inaccurate docs.
---

# Sync Project Documentation

The codebase is the source of truth. This skill finds places where `kit_tools/` documentation has drifted from the code — stale file paths, removed features still documented, new modules not documented, API routes that have been renamed, env vars that have been added or deleted — and either fixes them (full mode) or reports them (quick mode).

## When to Use

- **Quick audit** (`--quick`, ~5 min): routine monthly check-in, or "is my docs rotten?" sanity check before onboarding someone.
- **Full sync** (default, multi-session): after a significant refactor, major feature landing, or any time `--quick` flags substantial drift.
- **Resume** (`--resume`): continue a full sync that was interrupted — picks up from manifest progress rather than re-exploring.

## Outcome

- Full mode: documentation is rewritten to match the current codebase state. `SESSION_LOG.md` records what was updated.
- Quick mode: a structured report of drift — which docs are current, stale, outdated, or have broken references — with a recommendation on whether a full sync is warranted. No files are modified.

## Dependencies

This skill requires the following project files:

| File | Required | Purpose |
|------|----------|---------|
| `kit_tools/` directory | Yes | Documentation to sync |
| `kit_tools/AGENT_README.md` | Yes | Patterns to verify against code |
| `kit_tools/SESSION_LOG.md` | Yes | To record sync session |
| All `kit_tools/**/*.md` | Yes | Documentation to compare against codebase |

**Creates:**
- `kit_tools/SYNC_MANIFEST.json` — Progress tracking (replaces SYNC_PROGRESS.md)
- `kit_tools/.sync_cache/` — Exploration cache for reuse

**Uses agents:**
- `generic-explorer.md` — Focused codebase exploration
- `drift-detector.md` — Doc-to-code comparison
- `template-validator.md` — Placeholder cleanup verification

**Prerequisite:**
- Project must have kit_tools initialized (`/kit-tools:init-project`)

## Modes

- **Quick mode** (`--quick`): Lightweight audit for monthly check-ins
- **Full mode** (default): Exhaustive multi-session sync
- **Resume mode** (`--resume`): Continue from manifest progress

Check `$ARGUMENTS` for flags to determine mode.

---

## Quick Mode (--quick)

A lightweight documentation audit to catch drift. Run monthly or when you suspect docs are stale.

### Step 1: Run Focused Exploration

Spawn `generic-explorer` for key areas to get current codebase state:

```
Focus areas: tech-stack, architecture
```

Cache results to `kit_tools/.sync_cache/` for reuse.

### Step 2: Drift Detection on Critical Docs

Run `drift-detector` on the most important docs:

1. `SYNOPSIS.md` — Project overview accurate?
2. `arch/CODE_ARCH.md` — Structure still valid?
3. `docs/LOCAL_DEV.md` — Setup instructions work?
4. `AGENT_README.md` — Patterns match reality?

### Step 3: Freshness Check

For each doc in `kit_tools/`:

- Extract "Last Updated" date
- Compare against git log for related code files
- Flag docs older than 30 days with related code changes

### Step 4: Report

Aggregate each document's `overall_verdict` from the drift-detector result files:

```
┌─────────────────────────────────────────────────────────────────┐
│                    QUICK SYNC AUDIT                              │
├─────────────────────────────────────────────────────────────────┤
│  Documents Checked: 19                                           │
│  Clean: 12    Warnings: 5    Issues: 2                           │
└─────────────────────────────────────────────────────────────────┘

ISSUES (critical drift — doc is actively misleading):
  ✗ arch/CODE_ARCH.md
    - References src/utils/ which no longer exists
    - Missing new src/services/ module

WARNINGS (stale but not wrong):
  ⚠ docs/API_GUIDE.md — Last updated 45 days ago, API routes changed
  ⚠ docs/ENV_REFERENCE.md — Missing 3 new env vars

RECOMMENDATION: Run full sync with `/kit-tools:sync-project`
```

If issues are significant, recommend running a full sync.

---

## Full Mode (default)

Exhaustive codebase-to-documentation synchronization. The codebase is the source of truth — documentation must match it exactly.

### Phase 1: Initialize Manifest

1. **Check for existing manifest** at `kit_tools/SYNC_MANIFEST.json`
   - If exists and `--resume`: Load and continue from last progress
   - If exists and not `--resume`: Ask to reset or resume
   - If doesn't exist: Copy template from plugin and initialize

2. **Initialize manifest fields:**
   ```json
   {
     "created": "[current ISO timestamp]",
     "last_updated": "[current ISO timestamp]",
     "project_root": "[current directory]",
     "config": {
       "mode": "full",
       "stale_threshold_days": 30
     }
   }
   ```

3. **Create cache directory** at `kit_tools/.sync_cache/` if it doesn't exist

### Phase 2: Project Discovery (Using generic-explorer)

Instead of manual exploration, spawn focused explorers for each area:

#### Discovery Areas

| Area | Explorer Focus | What It Finds |
|------|---------------|---------------|
| Infrastructure | `infrastructure` | Docker, CI/CD, IaC, cloud configs |
| Code Structure | `architecture` | Directories, modules, entry points |
| APIs | `architecture`, `dependencies` | Endpoints, routes, interfaces |
| Data & Storage | `architecture`, `tech-stack` | Databases, caches, queues |
| Integrations | `dependencies` | Third-party services, SDKs |
| Background Jobs | `operations` | Cron, workers, queues |
| Testing | `testing` | Test frameworks, coverage |
| Tooling | `tech-stack` | Build tools, scripts |

For each area:

1. **Check cache** — If `.sync_cache/{focus}_summary.md` exists and is < 60 min old, reuse
2. **Run explorer** — Spawn `generic-explorer` with appropriate focus
3. **Cache results** — Save to `.sync_cache/`
4. **Update manifest** — Mark discovery area as complete

```
Discovery Progress: ████████░░░░ 6/8 areas

[✓] Infrastructure    [✓] Code Structure   [✓] APIs
[✓] Data & Storage    [✓] Integrations     [→] Background Jobs
[ ] Testing           [ ] Tooling
```

### Phase 3: Document Review (Using drift-detector)

For EACH document in `kit_tools/`:

1. **Load exploration context** for relevant focus areas

2. **Run drift-detector** with:
   - `{{DOCUMENT_CONTENT}}` — document content
   - `{{DOCUMENT_PATH}}`, `{{DOCUMENT_NAME}}` — document identifiers
   - `{{EXPLORATION_CONTEXT}}` — current codebase state from Phase 2
   - `{{LAST_UPDATED}}` — document's "Last updated" date
   - `{{STALE_THRESHOLD_DAYS}}` — `30`
   - `{{RESULT_FILE_PATH}}` — `kit_tools/.sync_drift_<doc-basename>.json` (per-document)

3. **Read the result file.** The agent writes JSON matching the unified Finding Schema (`$CLAUDE_PLUGIN_ROOT/agents/FINDING_SCHEMA.md`):

   ```json
   {
     "review_type": "drift",
     "target": "<document path>",
     "overall_verdict": "clean|warnings|issues",
     "findings": [
       {
         "severity": "critical|warning|info",
         "category": "missing-file|wrong-path|outdated-tech|stale-api|incorrect-claim|stale-content",
         "location": "<line or section>",
         "description": "...",
         "recommendation": "...",
         "confidence": "high|medium|low",
         "evidence": {"claim": "...", "reality": "..."}
       }
     ],
     "summary": "..."
   }
   ```

   A missing result file means the agent errored — treat as inconclusive, not clean.

4. **Update manifest** with per-document `overall_verdict` and finding count.

```
Document Review: ████████████░░░░ 14/19 docs

SYNOPSIS.md ................ clean
arch/CODE_ARCH.md .......... warnings (2 findings)
arch/SERVICE_MAP.md ........ clean
docs/LOCAL_DEV.md .......... clean
docs/API_GUIDE.md .......... issues (5 findings, 3 critical)  ← Current
```

### Phase 4: Conflict Resolution

When drift-detector finds issues, categorize them:

#### Auto-Fixable
- File paths that can be updated
- Version numbers from package files
- Missing sections that can be added from exploration

#### Needs Human Input
Present conflicts clearly:

```
## Conflict Found

**Document:** docs/API_GUIDE.md — Line 45

**Documentation says:**
> POST /api/users/create — Creates a new user

**Code actually shows:**
> POST /api/v2/users — Route was renamed in refactor

**Options:**
1. Update doc to match code (recommended)
2. Keep as-is (explain why)
3. Need more investigation
```

Log all conflicts in manifest under `conflicts` array.

### Phase 5: Documentation Updates

For each document needing updates:

1. **Apply fixes** based on drift-detector findings
2. **Remove stale sections** that reference deleted features
3. **Add missing documentation** from exploration context
4. **Update "Last Updated"** timestamp

### Phase 6: Validation (Using template-validator)

After updates, run `template-validator` on each modified document:

- Verify no placeholders remain
- Check all required sections have content
- Ensure file references are valid

```
Validation: ████████████████ 19/19 docs

Passed: 17    Warnings: 2    Failed: 0

Warnings:
  ⚠ docs/MONITORING.md — "Alerts" section has minimal content
  ⚠ arch/patterns/AUTH.md — Optional "OAuth" section empty
```

### Phase 7: Final Report

```
┌─────────────────────────────────────────────────────────────────┐
│                    SYNC COMPLETE                                 │
├─────────────────────────────────────────────────────────────────┤
│  Documents Reviewed: 19                                          │
│  Updated: 7    Current: 10    Skipped: 2                        │
│  Validation: 17 passed, 2 warnings, 0 failed                    │
└─────────────────────────────────────────────────────────────────┘

DOCUMENTS UPDATED:
  • arch/CODE_ARCH.md — Added new services/ module docs
  • docs/API_GUIDE.md — Updated 5 endpoint paths
  • docs/ENV_REFERENCE.md — Added 3 new variables
  • ...

CONFLICTS RESOLVED:
  • API endpoint rename: /api/users/create → /api/v2/users
  • ...

SKIPPED (not applicable):
  • docs/UI_STYLE_GUIDE.md — No frontend in project
  • arch/DATA_MODEL.md — No database in project

REMAINING ITEMS:
  • docs/MONITORING.md needs more detail on alerting
```

### Phase 8: Cleanup

After human confirms sync is complete:

1. Update SESSION_LOG.md with sync summary
2. Optionally delete manifest (or keep for next sync baseline)

---

## Resume Behavior (--resume)

When `--resume` is used:

1. Load existing `kit_tools/SYNC_MANIFEST.json`
2. Skip completed discovery areas
3. Skip documents with status "reviewed" or "updated"
4. Continue from first "pending" item
5. Maintain progress display

---

## Progress Display

Throughout sync, maintain a progress display:

```
┌─────────────────────────────────────────────────────────────────┐
│                    SYNC PROJECT PROGRESS                         │
├─────────────────────────────────────────────────────────────────┤
│  Phase: Document Review (3/7)                                    │
│                                                                  │
│  Discovery:  [████████] 8/8 complete                            │
│  Documents:  [██████░░░░░░░░░░░░░] 6/19                         │
│  Validation: [░░░░░░░░░░░░░░░░░░░] 0/19                         │
│                                                                  │
│  Current: Running drift-detector on docs/API_GUIDE.md...        │
│  Cache: 6/6 exploration areas cached                             │
└─────────────────────────────────────────────────────────────────┘
```

---

## Agent Usage Summary

| Phase | Agent | Purpose |
|-------|-------|---------|
| Discovery | `generic-explorer` | Build current codebase map |
| Review | `drift-detector` | Compare docs to code |
| Validation | `template-validator` | Verify cleanup complete |

---

## Quick Reference

```bash
# Quick audit (monthly check-in)
/kit-tools:sync-project --quick

# Full sync (exhaustive)
/kit-tools:sync-project

# Resume interrupted sync
/kit-tools:sync-project --resume
```
