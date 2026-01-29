<!-- Template Version: 1.1.0 -->
# CI_CD.md

> **TEMPLATE_INTENT:** Document build pipelines, deployment triggers, and automation. How code gets to production.

> Last updated: YYYY-MM-DD
> Updated by: [Human/Claude]

---

## Overview

**CI/CD Platform:** [GitHub Actions / GitLab CI / CircleCI / Jenkins / etc.]
**Pipeline Config:** `[path to config file]`
**Dashboard:** [URL to CI/CD dashboard]

---

## Pipeline Stages

<!-- FILL: What happens at each stage -->

```
┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐
│  Lint   │───▶│  Test   │───▶│  Build  │───▶│ Deploy  │
└─────────┘    └─────────┘    └─────────┘    └─────────┘
```

| Stage | Runs On | Duration | Blocking |
|-------|---------|----------|----------|
| Lint | Every push | ~[time] | Yes |
| Test | Every push | ~[time] | Yes |
| Build | PR + main | ~[time] | Yes |
| Deploy | main branch | ~[time] | N/A |

---

## Triggers

<!-- FILL: What triggers each pipeline -->

### On Pull Request

```yaml
# What runs:
- [step 1]
- [step 2]
```

### On Merge to Main

```yaml
# What runs:
- [step 1]
- [step 2]
- [deploy step]
```

### Manual Triggers

| Action | How to Trigger | Use Case |
|--------|----------------|----------|
| [action] | [command or UI path] | [when to use] |

---

## Pipeline Details

### Linting

**Config file:** `[path]`

```bash
# Run locally
[command]
```

**What it checks:**
- [Check 1]
- [Check 2]

### Tests

**Test runner:** [pytest / jest / etc.]

```bash
# Run locally (same as CI)
[command]
```

**Coverage requirements:** [X% minimum or none]

### Build

**Build tool:** [webpack / docker / etc.]

```bash
# Run locally (same as CI)
[command]
```

**Artifacts produced:**
- [Artifact 1]
- [Artifact 2]

### Deploy

**Deploy method:** [Kubernetes / Cloud Run / Vercel / etc.]

See `DEPLOYMENT.md` for detailed deployment procedures.

---

## Environment Variables in CI

<!-- FILL: What secrets/vars are configured in CI -->

| Variable | Where Set | Purpose |
|----------|-----------|---------|
| `[VAR_NAME]` | [CI secrets / repo settings] | [Purpose] |

### Adding New CI Variables

1. [Step 1]
2. [Step 2]
3. [Step 3]

---

## Checking Pipeline Status

### View Current Status

- **Dashboard:** [URL]
- **CLI:** `[command if available]`
- **Status badge:** [If there's a badge in README]

### View Logs

1. Go to [URL]
2. [Steps to find logs]

### Common Failure Points

| Failure | Likely Cause | Fix |
|---------|--------------|-----|
| Lint fails | [cause] | [fix] |
| Tests fail | [cause] | [fix] |
| Build fails | [cause] | [fix] |
| Deploy fails | [cause] | [fix] |

---

## Manual Deployments

<!-- FILL: How to deploy manually if needed -->

### Deploy to Staging

```bash
[command or process]
```

### Deploy to Production

```bash
[command or process]
```

### Skip CI

<!-- FILL: If there's a way to skip CI, document it -->

```
[How to skip CI if needed, e.g., commit message tag]
```

**Warning:** [When it's appropriate to skip CI]

---

## Rollback

### Automatic Rollback

[Is there automatic rollback on failure? Describe it]

### Manual Rollback

```bash
# Rollback to previous version
[command]

# Rollback to specific version
[command]
```

See `DEPLOYMENT.md` for detailed rollback procedures.

---

## Branch Protection

<!-- FILL: What branch protections are configured -->

### Main Branch

- [ ] Require PR reviews: [number]
- [ ] Require status checks: [which ones]
- [ ] Require up-to-date branch
- [ ] Restrict who can push

### Other Protected Branches

| Branch | Protection Rules |
|--------|------------------|
| [branch] | [rules] |

---

## Caching

<!-- FILL: What's cached to speed up CI -->

| Cache | Key | TTL |
|-------|-----|-----|
| Dependencies | `[key pattern]` | [duration] |
| Build artifacts | `[key pattern]` | [duration] |

### Invalidating Cache

```bash
[How to force cache invalidation]
```

---

## Notifications

<!-- FILL: Where CI notifications go -->

| Event | Notification Channel |
|-------|---------------------|
| Build failure | [Slack / email / etc.] |
| Deploy success | [Slack / email / etc.] |

---

## Troubleshooting CI

### "It works locally but fails in CI"

1. Check environment differences: [common differences]
2. Check CI logs for: [what to look for]
3. [Other debugging steps]

### Flaky Tests

[How to identify and handle flaky tests]

### CI is Slow

[Tips for speeding up CI]
