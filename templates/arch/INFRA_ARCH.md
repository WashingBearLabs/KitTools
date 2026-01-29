<!-- Template Version: 1.2.0 -->
<!-- Seeding:
  explorer_focus: infrastructure
  required_sections:
    - "Overview"
  skip_if: no-infrastructure
-->
# INFRA_ARCH.md

> **TEMPLATE_INTENT:** Document cloud resources, networking, and infrastructure. The map of deployed systems.

> Last updated: YYYY-MM-DD
> Updated by: [Human/Claude]

<!--
NOTE: This file documents infrastructure and deployment.
Delete sections that don't apply to your project.
For libraries, CLI tools, or projects without cloud infrastructure,
this file may only need the "Local Development" section.
-->

---

## Overview

<!-- FILL: Where is this project hosted? How is infrastructure managed? -->

This project is hosted on **[Cloud provider / self-hosted / N/A]**.

Infrastructure is managed via: **[Terraform / Pulumi / CloudFormation / Console / N/A]**

| Environment | Purpose | URL |
|-------------|---------|-----|
| **Production** | [Purpose] | `[URL or N/A]` |
| **Staging** | [Purpose] | `[URL or N/A]` |
| **Development** | Local development | `http://localhost:[port]` |

<!-- Delete environments that don't exist -->

---

## Architecture Diagram

<!-- FILL: Draw your actual architecture. Delete if not applicable -->

```
[Draw your architecture here, or delete this section]
```

---

## Cloud Resources

<!-- FILL: List actual cloud resources. Delete entire section if no cloud infra -->

### Compute

| Resource | Service | Purpose | Config |
|----------|---------|---------|--------|
| [Name] | [Service] | [Purpose] | [Config notes] |

### Database

<!-- Delete if no database -->

| Resource | Service | Purpose | Config |
|----------|---------|---------|--------|
| [Name] | [Service] | [Purpose] | [Config notes] |

### Storage

<!-- Delete if no storage -->

| Resource | Service | Purpose |
|----------|---------|---------|
| [Name] | [Service] | [Purpose] |

### Caching

<!-- Delete if no caching -->

| Resource | Service | Purpose |
|----------|---------|---------|
| [Name] | [Redis / Memcached / etc.] | [Purpose] |

### Message Queues

<!-- Delete if no queues -->

| Resource | Service | Purpose |
|----------|---------|---------|
| [Name] | [SQS / RabbitMQ / etc.] | [Purpose] |

---

## Networking

<!-- FILL: Network topology. Delete if simple setup or N/A -->

### Network Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                         Internet                             │
└─────────────────────────────┬───────────────────────────────┘
                              │
                       ┌──────▼──────┐
                       │  [LB/CDN]   │
                       └──────┬──────┘
                              │
┌─────────────────────────────▼───────────────────────────────┐
│                    VPC: [CIDR range]                         │
│  ┌────────────────────────────────────────────────────────┐ │
│  │              Public Subnet: [CIDR]                      │ │
│  │  ┌─────────────┐                                       │ │
│  │  │ [Service]   │                                       │ │
│  │  └─────────────┘                                       │ │
│  └────────────────────────────────────────────────────────┘ │
│  ┌────────────────────────────────────────────────────────┐ │
│  │             Private Subnet: [CIDR]                      │ │
│  │  ┌─────────────┐  ┌─────────────┐                      │ │
│  │  │ [Service]   │  │    [DB]     │                      │ │
│  │  └─────────────┘  └─────────────┘                      │ │
│  └────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

### DNS

| Domain | Points To | Managed By |
|--------|-----------|------------|
| `[domain]` | [Service/IP] | [DNS provider] |

### Firewall Rules

| Rule | Source | Destination | Ports | Purpose |
|------|--------|-------------|-------|---------|
| [Name] | [Source] | [Dest] | [Ports] | [Why] |

### Load Balancing

| Load Balancer | Type | Backend Services |
|---------------|------|------------------|
| [Name] | [ALB / NLB / etc.] | [What it routes to] |

---

## IAM / Permissions

<!-- FILL: Service accounts and permissions. Delete if N/A -->

### Service Accounts

| Account | Services Using It | Permissions |
|---------|-------------------|-------------|
| [Account name] | [Services] | [Permission set] |

### IAM Roles

| Role | Purpose | Attached To |
|------|---------|-------------|
| [Role name] | [What it allows] | [Users/services] |

### Access Patterns

- **Developer access:** [How devs access cloud resources]
- **CI/CD access:** [How pipelines authenticate]
- **Service-to-service:** [How services authenticate to each other]

---

## Infrastructure as Code

<!-- FILL: Document IaC structure. Delete if no IaC -->

```
[path to infra code]/
├── [file]    # [Purpose]
└── [file]    # [Purpose]
```

### Applying Changes

```bash
# Plan changes
[command]

# Apply changes
[command]

# Destroy (careful!)
[command]
```

### State Management

**State storage:** [S3 / GCS / Terraform Cloud / etc.]
**State locking:** [DynamoDB / etc.]

---

## Cost Management

<!-- FILL: Cost information. Delete if not relevant -->

### Estimated Monthly Cost

| Resource | Estimated Cost | Notes |
|----------|----------------|-------|
| [Resource] | $[amount] | [Usage assumptions] |
| **Total** | $[amount] | |

### Cost Optimization Notes

- [Optimization opportunity 1]
- [Optimization opportunity 2]

### Billing Alerts

| Alert | Threshold | Notification |
|-------|-----------|--------------|
| [Alert name] | $[amount] | [Where notified] |

---

## Service Limits / Quotas

<!-- FILL: Known limits to be aware of. Delete if N/A -->

| Service | Limit | Current Usage | Notes |
|---------|-------|---------------|-------|
| [Service] | [Limit] | [Usage] | [How to increase] |

---

## Disaster Recovery

<!-- FILL: DR procedures. Delete if N/A -->

### Backups

| Resource | Backup Frequency | Retention | Location |
|----------|------------------|-----------|----------|
| [DB] | [Frequency] | [Days] | [Where] |

### Recovery Procedures

**RTO (Recovery Time Objective):** [Target time]
**RPO (Recovery Point Objective):** [Target data loss]

```bash
# Restore database from backup
[command]

# Restore to different region
[command]
```

---

## Deployment

<!-- FILL: How is the project deployed? -->

See `docs/DEPLOYMENT.md` for detailed deployment procedures.

---

## Security Considerations

<!-- FILL: Security checklist relevant to your infrastructure -->

See `arch/SECURITY.md` for detailed security documentation.

- [ ] All traffic over HTTPS
- [ ] Secrets in Secret Manager, not env vars
- [ ] Service accounts follow least-privilege
- [ ] Database not publicly accessible
- [ ] Firewall rules are restrictive
- [ ] Audit logging enabled
