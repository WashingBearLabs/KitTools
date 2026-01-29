<!-- Template Version: 1.2.0 -->
<!-- Seeding:
  explorer_focus: operations, infrastructure
  required_sections:
    - "Logging"
  skip_if: no-infrastructure
-->
# MONITORING.md

> **TEMPLATE_INTENT:** Document logs, metrics, alerts, and dashboards. How to observe the system.

> Last updated: YYYY-MM-DD
> Updated by: [Human/Claude]

---

## Quick Links

<!-- FILL: Fast access to monitoring resources -->

| Resource | URL |
|----------|-----|
| **Logs** | [URL] |
| **Metrics Dashboard** | [URL] |
| **Alerts** | [URL] |
| **Traces** | [URL] |
| **Status Page** | [URL] |

---

## Logging

### Log Aggregation

**Platform:** [CloudWatch / Datadog / Papertrail / ELK / etc.]
**Dashboard:** [URL]

### Log Locations by Service

| Service | Log Location | How to Access |
|---------|--------------|---------------|
| [Service] | [Location] | [Command or URL] |

### Log Levels

| Level | When Used | Example |
|-------|-----------|---------|
| ERROR | Unhandled exceptions, failures | [example] |
| WARN | Recoverable issues, deprecations | [example] |
| INFO | Normal operations, milestones | [example] |
| DEBUG | Detailed diagnostic info | [example] |

### Searching Logs

```
# Find errors in the last hour
[query]

# Find logs for specific user
[query]

# Find logs for specific request ID
[query]

# Find slow operations
[query]
```

### Log Retention

| Environment | Retention Period |
|-------------|------------------|
| Production | [duration] |
| Staging | [duration] |

---

## Metrics

### Metrics Platform

**Platform:** [Prometheus / CloudWatch / Datadog / etc.]
**Dashboard:** [URL]

### Key Metrics to Monitor

#### Application Metrics

| Metric | Description | Alert Threshold |
|--------|-------------|-----------------|
| `[metric_name]` | [What it measures] | [When to alert] |
| Request rate | Requests per second | [threshold] |
| Error rate | Errors per second | [threshold] |
| Response time (p50) | Median latency | [threshold] |
| Response time (p99) | 99th percentile latency | [threshold] |

#### Infrastructure Metrics

| Metric | Description | Alert Threshold |
|--------|-------------|-----------------|
| CPU usage | Compute utilization | [threshold] |
| Memory usage | RAM utilization | [threshold] |
| Disk usage | Storage utilization | [threshold] |
| Database connections | Active DB connections | [threshold] |

### Custom Metrics

<!-- FILL: Application-specific metrics -->

| Metric | Description | Where Emitted |
|--------|-------------|---------------|
| `[custom_metric]` | [What it measures] | [Code location] |

### Viewing Metrics

```bash
# CLI access (if available)
[command]
```

---

## Distributed Tracing

<!-- FILL: Request tracing. Delete if not implemented -->

### Tracing Platform

**Platform:** [Jaeger / Zipkin / X-Ray / Datadog APM / etc.]
**Dashboard:** [URL]

### Trace Propagation

**Header name:** `[X-Request-ID / X-Trace-ID / etc.]`

```
# How traces are propagated
[Description of trace context propagation]
```

### Finding Traces

1. Get the trace/request ID from logs
2. Search in [tracing platform]
3. [Additional steps]

---

## Alerting

### Alert Platform

**Platform:** [PagerDuty / Opsgenie / CloudWatch Alarms / etc.]
**Dashboard:** [URL]

### Active Alerts

| Alert Name | Condition | Severity | Notification |
|------------|-----------|----------|--------------|
| [Alert] | [When it triggers] | [P1/P2/P3] | [Where notified] |

### Responding to Alerts

#### [Alert Name]

**Meaning:** [What this alert indicates]

**Immediate actions:**
1. [Step 1]
2. [Step 2]

**Escalation:** [When/how to escalate]

### Silencing Alerts

```bash
# How to silence during maintenance
[command or UI steps]
```

**Important:** Always document why alerts are silenced in [location]

---

## Health Checks

### Endpoints

| Service | Health Endpoint | Expected Response |
|---------|-----------------|-------------------|
| [Service] | `[URL]` | `[expected response]` |

### Automated Health Checks

| Check | Frequency | Timeout | Alert On Failure |
|-------|-----------|---------|------------------|
| [Check] | [interval] | [timeout] | [Yes/No] |

---

## Uptime Monitoring

<!-- FILL: External uptime monitoring. Delete if not applicable -->

**Platform:** [Pingdom / UptimeRobot / StatusCake / etc.]
**Dashboard:** [URL]

### Monitored Endpoints

| Endpoint | Check Frequency | Alert After |
|----------|-----------------|-------------|
| [URL] | [frequency] | [duration] |

---

## Status Page

<!-- FILL: Public or internal status page. Delete if none -->

**URL:** [URL]
**Management:** [How to update status]

### Updating Status

```bash
# How to post an incident
[command or steps]

# How to update status
[command or steps]
```

---

## Dashboards

### Pre-built Dashboards

| Dashboard | Purpose | URL |
|-----------|---------|-----|
| [Name] | [What it shows] | [URL] |

### Key Dashboard Views

#### System Overview

[Screenshot or description of what to look for]

#### Per-Service Health

[Screenshot or description of what to look for]

---

## On-Call

<!-- FILL: On-call rotation info. Delete if not applicable -->

### Current On-Call

**Schedule:** [URL to schedule]
**Contact method:** [How to reach on-call]

### Escalation Path

| Level | Response Time | Contact |
|-------|---------------|---------|
| L1 | [time] | [who] |
| L2 | [time] | [who] |
| L3 | [time] | [who] |

---

## Adding New Monitoring

### Adding a New Metric

1. [Step 1]
2. [Step 2]
3. [Step 3]

### Adding a New Alert

1. [Step 1]
2. [Step 2]
3. [Step 3]

### Adding to Dashboard

1. [Step 1]
2. [Step 2]
