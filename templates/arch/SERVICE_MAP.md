<!-- Template Version: 1.1.0 -->
<!-- Seeding:
  explorer_focus: architecture, dependencies
  required_sections:
    - "Service Topology"
  skip_if: never
-->
# SERVICE_MAP.md

> **TEMPLATE_INTENT:** Document dependencies and integrations. Shows what talks to what and failure impacts.

> Last updated: YYYY-MM-DD
> Updated by: [Human/Claude]

---

## System Overview

<!-- FILL: High-level view of all services and their relationships -->

```
┌─────────────────────────────────────────────────────────────────┐
│                         [System Name]                            │
│                                                                  │
│   [Draw your service topology here]                              │
│                                                                  │
│   Example:                                                       │
│   ┌─────────┐     ┌─────────┐     ┌─────────┐                  │
│   │ Client  │────▶│   API   │────▶│   DB    │                  │
│   └─────────┘     └────┬────┘     └─────────┘                  │
│                        │                                         │
│                        ▼                                         │
│                   ┌─────────┐     ┌─────────┐                  │
│                   │  Queue  │────▶│ Worker  │                  │
│                   └─────────┘     └─────────┘                  │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Internal Services

<!-- FILL: Document each internal service -->

### [Service Name]

| Attribute | Value |
|-----------|-------|
| **Purpose** | [What it does] |
| **Repository** | [Repo location if separate] |
| **Runtime** | [Language/framework] |
| **Port** | [Default port] |
| **Health Check** | `[endpoint or command]` |

**Depends on:**
- [Service/resource it needs]
- [Service/resource it needs]

**Depended on by:**
- [Services that call this one]

**Failure impact:**
[What breaks if this service goes down]

---

## External Integrations

<!-- FILL: Third-party services and APIs -->

### [Integration Name]

| Attribute | Value |
|-----------|-------|
| **Purpose** | [What we use it for] |
| **Documentation** | [Link to their docs] |
| **Status Page** | [Link to status page] |
| **Dashboard** | [Link to our dashboard/console for this service] |

**Used by:**
- [Which internal services use this]

**Failure behavior:**
[What happens when this external service is unavailable]

**Fallback:**
[Any graceful degradation or fallback behavior]

**Rate limits:**
[Known rate limits to be aware of]

---

## Data Stores

<!-- FILL: Databases, caches, file storage -->

### [Data Store Name]

| Attribute | Value |
|-----------|-------|
| **Type** | [PostgreSQL / Redis / S3 / etc.] |
| **Purpose** | [What data it holds] |
| **Location** | [Cloud service or self-hosted] |
| **Connection** | [How services connect - env var name] |

**Accessed by:**
- [Services that read/write to this]

**Backup schedule:**
[How often backed up, where backups go]

**Failure impact:**
[What breaks if this is unavailable]

---

## Message Queues / Event Buses

<!-- FILL: Async communication. Delete if not applicable -->

### [Queue/Topic Name]

| Attribute | Value |
|-----------|-------|
| **Type** | [SQS / RabbitMQ / Kafka / Redis / etc.] |
| **Purpose** | [What messages flow through it] |

**Producers:**
- [Services that publish to this]

**Consumers:**
- [Services that consume from this]

**Message format:**
```json
{
  "example": "message structure"
}
```

**Failure behavior:**
[What happens if queue backs up or is unavailable]

---

## Background Jobs / Scheduled Tasks

<!-- FILL: Cron jobs, workers, scheduled tasks. Delete if none -->

| Job Name | Schedule | Purpose | Runs On |
|----------|----------|---------|---------|
| [name] | [cron expression or frequency] | [what it does] | [where it runs] |

### [Job Name] Details

**Trigger:** [Cron schedule or event trigger]

**Duration:** [Typical runtime]

**Failure handling:** [What happens if it fails, retry behavior]

**Manual trigger:**
```bash
[command to manually run this job]
```

---

## Dependency Matrix

<!-- FILL: Quick reference for what depends on what -->

| Service | Depends On | Impact if Down |
|---------|------------|----------------|
| [Service A] | [DB, Cache, Service B] | [What breaks] |
| [Service B] | [DB, External API] | [What breaks] |

---

## Startup Order

<!-- FILL: If services must start in a specific order -->

For local development or disaster recovery, start services in this order:

1. [Database / data stores]
2. [Cache]
3. [Core services]
4. [Dependent services]
5. [Workers / background jobs]

---

## Network Boundaries

<!-- FILL: What can talk to what. Delete if simple setup -->

```
┌──────────────────────────────────────────────────────────┐
│                      Public Internet                      │
└──────────────────────────┬───────────────────────────────┘
                           │
                    ┌──────▼──────┐
                    │   [LB/CDN]  │
                    └──────┬──────┘
                           │
┌──────────────────────────▼───────────────────────────────┐
│                    [Public Subnet]                        │
│  ┌─────────────┐                                         │
│  │ [Frontend]  │                                         │
│  └─────────────┘                                         │
└──────────────────────────┬───────────────────────────────┘
                           │
┌──────────────────────────▼───────────────────────────────┐
│                   [Private Subnet]                        │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐      │
│  │   [API]     │  │  [Worker]   │  │    [DB]     │      │
│  └─────────────┘  └─────────────┘  └─────────────┘      │
└──────────────────────────────────────────────────────────┘
```
