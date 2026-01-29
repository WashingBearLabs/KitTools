<!-- Template Version: 1.1.0 -->
<!-- Seeding:
  explorer_focus: operations, tech-stack
  required_sections:
    - "Debugging Tools"
  skip_if: never
-->
# TROUBLESHOOTING.md

> **TEMPLATE_INTENT:** Document debugging procedures and common fixes. How to diagnose problems.

> Last updated: YYYY-MM-DD
> Updated by: [Human/Claude]

---

## Quick Diagnostics

<!-- FILL: First steps when something breaks -->

When investigating an issue:

1. **Check service health:** `[command or URL to health check]`
2. **Check recent deploys:** `[command or URL to deployment history]`
3. **Check logs:** `[command or URL to logs]`
4. **Check alerts:** `[URL to alerting dashboard]`

---

## How to Access Logs

<!-- FILL: Where are logs and how to access them? -->

### Application Logs

| Environment | Location | How to Access |
|-------------|----------|---------------|
| Local | `[path or command]` | `[command]` |
| Staging | `[service/location]` | `[command or URL]` |
| Production | `[service/location]` | `[command or URL]` |

### Useful Log Queries

```
# Find errors in the last hour
[query]

# Find logs for specific user/request
[query]

# Find slow requests
[query]
```

---

## How to Trace a Request

<!-- FILL: How to follow a request through the system -->

### Request ID / Correlation ID

[Explain how requests are tagged and how to trace them across services]

```
# Find all logs for a specific request
[query or command]
```

### Tracing Flow

```
[Request] → [Service A] → [Service B] → [Database] → [Response]
     │           │             │             │
     └─ Log: X   └─ Log: Y     └─ Log: Z     └─ Log: W
```

---

## Common Issues & Solutions

<!-- FILL: Document recurring problems and their fixes -->

### [Issue Title]

**Symptoms:**
- [What the user/system sees]

**Cause:**
[Why this happens]

**Solution:**
```bash
[Commands or steps to fix]
```

**Prevention:**
[How to prevent this in the future]

---

### [Issue Title]

**Symptoms:**
- [What the user/system sees]

**Cause:**
[Why this happens]

**Solution:**
```bash
[Commands or steps to fix]
```

---

## Service-Specific Debugging

<!-- FILL: Debugging tips for each major service/component -->

### [Service/Component Name]

**Health check:** `[command]`

**Restart:** `[command]`

**Common issues:**
- [Issue 1]: [Quick fix]
- [Issue 2]: [Quick fix]

**Useful commands:**
```bash
[debugging commands specific to this service]
```

---

## Database Issues

<!-- FILL: Database-specific troubleshooting. Delete if no database -->

### Connection Issues

```bash
# Test database connectivity
[command]

# Check connection pool status
[command]
```

### Slow Queries

```bash
# Find slow queries
[command or query]

# Check query plan
[command]
```

### Data Issues

```bash
# Useful diagnostic queries
[query]
```

---

## External Service Failures

<!-- FILL: What to do when third-party services are down -->

| Service | Status Page | Fallback Behavior |
|---------|-------------|-------------------|
| [Service] | [URL] | [What happens when it's down] |

---

## Escalation Path

<!-- FILL: Who to contact when you can't resolve an issue -->

| Severity | Response Time | Contact |
|----------|---------------|---------|
| P1 - System down | Immediate | [Contact method] |
| P2 - Major feature broken | [Timeframe] | [Contact method] |
| P3 - Minor issue | [Timeframe] | [Contact method] |

---

## Post-Incident

After resolving an issue:

- [ ] Document what happened in [incident log location]
- [ ] Update this file if it's a new common issue
- [ ] Update `GOTCHAS.md` if relevant
- [ ] Consider preventive measures
