---
description: Sync documentation with codebase (use --quick for lightweight audit)
---

# Sync Project Documentation

Synchronize documentation with the actual codebase. This skill has two modes:

- **Quick mode** (`--quick`): Lightweight audit for monthly check-ins
- **Full mode** (default): Exhaustive multi-session sync

Check `$ARGUMENTS` for `--quick` flag to determine mode.

---

## Quick Mode (--quick)

A lightweight documentation audit to catch drift. Run monthly or when you suspect docs are stale.

### Step 1: Freshness Check

Review all files in `kit_tools/` and flag any that:

- Have "Last updated" older than 30 days AND related code has changed
- Reference files, functions, or patterns that no longer exist
- Contradict what you see in the actual codebase

### Step 2: Completeness Check

For each major feature/module in the codebase, verify:

- Is there documentation in `kit_tools/arch/CODE_ARCH.md`?
- If it has an API, is it in `kit_tools/docs/API_GUIDE.md`?
- If it has env vars, are they in `kit_tools/docs/ENV_REFERENCE.md`?
- If it's a significant feature, is there a feature guide?

### Step 3: Consistency Check

Spot-check for conflicts between:

- `kit_tools/AGENT_README.md` patterns vs. actual code
- `kit_tools/docs/API_GUIDE.md` vs. actual endpoints
- `kit_tools/arch/DATA_MODEL.md` vs. actual schema

### Step 4: Report

Provide a summary:

- **Stale docs** — Files needing updates (with specific issues)
- **Missing docs** — Undocumented features or modules
- **Inconsistencies** — Conflicts between docs and code
- **Recommended actions** — Prioritized by impact

If issues are significant, recommend running a full sync.

---

## Full Mode (default)

Exhaustive codebase-to-documentation synchronization. The codebase is the source of truth — documentation must match it exactly.

This may take multiple sessions for complex projects. That's expected.

### Before You Begin

1. **Check for existing progress**: Look for `kit_tools/SYNC_PROGRESS.md`
   - If it exists, a sync is already in progress — resume from where it left off
   - If it doesn't exist, this is a fresh sync — create the progress file

2. **Create/Update SYNC_PROGRESS.md** with this structure:

```markdown
# Sync Progress

**Started:** [DATE]
**Last Updated:** [DATE]
**Status:** In Progress

## Areas Reviewed
- [ ] Area 1
- [ ] Area 2

## Findings Log
### [Area Name]
- Finding 1
- Finding 2

## Pending Human Review
- [ ] Conflict/question 1

## Documentation Created
- file1.md - reason
```

3. **Ask any clarifying questions** about the project before starting.

### Phase 1: Project Discovery

Build a complete mental map of the project:

#### 1.1 Infrastructure & Environment
- [ ] Docker/container configurations
- [ ] Terraform/CloudFormation/Pulumi (IaC)
- [ ] Kubernetes manifests
- [ ] CI/CD pipelines
- [ ] Environment files
- [ ] Build scripts and tooling

#### 1.2 Code Structure
- [ ] Every top-level directory and its purpose
- [ ] Entry points
- [ ] All modules/packages and their responsibilities
- [ ] Internal libraries or shared utilities

#### 1.3 APIs & Interfaces
- [ ] REST/GraphQL/gRPC endpoints
- [ ] CLI commands and flags
- [ ] Library exports and public APIs
- [ ] Webhooks and WebSocket handlers

#### 1.4 Data & Storage
- [ ] Database schemas and migrations
- [ ] Cache layers
- [ ] File storage
- [ ] Message queues

#### 1.5 External Integrations
- [ ] Third-party API clients
- [ ] SDK usage
- [ ] OAuth/SSO providers

#### 1.6 Background Processing
- [ ] Cron jobs and scheduled tasks
- [ ] Queue workers and consumers

#### 1.7 Testing & Quality
- [ ] Test suites and frameworks
- [ ] Linting and formatting configs

#### 1.8 Scripts & Tooling
- [ ] One-off scripts
- [ ] Migration scripts
- [ ] Development utilities

Update SYNC_PROGRESS.md as you complete each area.

### Phase 2: Documentation Review

For EACH documentation file in kit_tools, systematically compare against what was discovered:

#### Review Process (for each doc)
1. Read the documentation file completely
2. Compare every statement against the actual codebase
3. For each discrepancy, determine if it's:
   - **Outdated**: Code changed, docs didn't update
   - **Incomplete**: Code exists that isn't documented
   - **Incorrect**: Documentation states something false
   - **Missing context**: Documentation lacks important details

#### Files to Review
- [ ] SYNOPSIS.md
- [ ] AGENT_README.md
- [ ] arch/CODE_ARCH.md
- [ ] arch/SERVICE_MAP.md
- [ ] arch/INFRA_ARCH.md
- [ ] arch/DATA_MODEL.md
- [ ] arch/SECURITY.md
- [ ] arch/DECISIONS.md
- [ ] arch/patterns/*.md
- [ ] docs/LOCAL_DEV.md
- [ ] docs/API_GUIDE.md
- [ ] docs/ENV_REFERENCE.md
- [ ] docs/CONVENTIONS.md
- [ ] docs/CI_CD.md
- [ ] docs/DEPLOYMENT.md
- [ ] docs/MONITORING.md
- [ ] docs/TROUBLESHOOTING.md
- [ ] docs/GOTCHAS.md
- [ ] docs/feature_guides/*.md
- [ ] testing/TESTING_GUIDE.md
- [ ] roadmap/*.md

### Phase 3: Conflict Resolution

When finding a conflict between code and documentation, STOP and ask for human input:

```
## Conflict Found

**Location:** [doc file] — [section/line]

**Documentation says:**
> [quote from docs]

**Code actually does:**
> [what you found in the code]

**My recommendation:**
[Suggested update to the documentation]

Please advise:
1. Update documentation as recommended
2. Different update (please specify)
3. This is intentional, leave as-is
4. Need to investigate further
```

Log all conflicts in SYNC_PROGRESS.md under "Pending Human Review".

### Phase 4: New Documentation

When discovering undocumented features, systems, or patterns:

1. Note it in SYNC_PROGRESS.md under "Documentation Created"
2. Create documentation in the appropriate location
3. Flag for human review

### Phase 5: Template Cleanup

- Remove HTML comments with template guidance
- Replace all `[PLACEHOLDER]` text with actual values
- Replace `YYYY-MM-DD` with actual dates
- Delete sections that don't apply

### Multi-Session Handling

For complex projects spanning multiple sessions:

1. Always update SYNC_PROGRESS.md before ending a session
2. Natural breakpoints: after completing major areas, after presenting conflicts
3. Resuming: Read SYNC_PROGRESS.md first, pick up where previous session left off

### Final Report

When fully complete, provide:

1. **Summary**: What was reviewed, how many sessions it took
2. **Documentation Updated**: List of files modified
3. **Documentation Created**: New files created and why
4. **Conflicts Resolved**: Summary of conflicts and resolutions
5. **Remaining Gaps**: Anything that couldn't be documented
6. **Recommendations**: Suggested follow-up actions

### Cleanup

After the human confirms the sync is complete:

1. Delete SYNC_PROGRESS.md
2. Update SESSION_LOG.md with a summary of the sync
