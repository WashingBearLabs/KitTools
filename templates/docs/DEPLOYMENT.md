<!-- Template Version: 1.2.0 -->
<!-- Seeding:
  explorer_focus: infrastructure, operations
  required_sections:
    - "Deployment Procedure"
  skip_if: no-infrastructure
-->
# DEPLOYMENT.md

> **TEMPLATE_INTENT:** Document deployment procedures and rollback processes. How to ship safely.

> Last updated: YYYY-MM-DD
> Updated by: [Human/Claude]

<!--
NOTE: This file documents deployment procedures.
Delete this file if the project is not deployed (e.g., local-only tools, libraries).
-->

---

## Environments

<!-- FILL: List actual deployment environments -->

| Environment | URL | Branch | Auto-Deploy |
|-------------|-----|--------|-------------|
| Production | `[URL]` | `[branch]` | [Yes/No] |
| Staging | `[URL]` | `[branch]` | [Yes/No] |

<!-- Delete rows that don't exist -->

---

## Prerequisites

<!-- FILL: What's needed to deploy? -->

- [Prerequisite 1: e.g., "Access to AWS console"]
- [Prerequisite 2: e.g., "GitHub Actions secrets configured"]

---

## Quick Deploy

<!-- FILL: Most common deployment method -->

```bash
# [Description of what this does]
[command]
```

---

## Manual Deploy

<!-- FILL: Step-by-step manual deployment if needed -->

```bash
# Step 1: [Description]
[command]

# Step 2: [Description]
[command]
```

---

## Rollback

<!-- FILL: How to rollback a bad deployment -->

```bash
# [Description of rollback procedure]
[command]
```

---

## Monitoring

<!-- FILL: Where to check deployment status and logs -->

- **Logs:** [Where to find logs]
- **Metrics:** [Where to find metrics]
- **Alerts:** [Where alerts are configured]
