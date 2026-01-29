<!-- Template Version: 1.2.0 -->
<!-- Seeding:
  explorer_focus: security, architecture
  required_sections:
    - "Security Overview"
  skip_if: no-auth
-->
# SECURITY.md

> **TEMPLATE_INTENT:** Document authentication, authorization, and secrets management. Security architecture reference.

> Last updated: YYYY-MM-DD
> Updated by: [Human/Claude]

---

## Security Overview

<!-- FILL: High-level security posture -->

**Auth Provider:** [Auth0 / Supabase / Firebase / Custom / etc.]
**Secrets Management:** [AWS Secrets Manager / GCP Secret Manager / Vault / etc.]
**Encryption:** [At rest and in transit details]

---

## Authentication Flow

<!-- FILL: How users authenticate. Delete if no auth -->

### Login Flow

```
┌─────────┐     ┌─────────┐     ┌─────────┐     ┌─────────┐
│  User   │────▶│ Client  │────▶│  Auth   │────▶│   API   │
│         │     │  App    │     │ Provider│     │         │
└─────────┘     └─────────┘     └─────────┘     └─────────┘
     │               │               │               │
     │  1. Login     │               │               │
     │──────────────▶│               │               │
     │               │ 2. Auth Req   │               │
     │               │──────────────▶│               │
     │               │               │ 3. Verify     │
     │               │               │──────────────▶│
     │               │ 4. Token      │               │
     │               │◀──────────────│               │
     │  5. Session   │               │               │
     │◀──────────────│               │               │
```

### Token Types

| Token | Purpose | Storage | Lifetime |
|-------|---------|---------|----------|
| [Access token] | [API authentication] | [Where stored] | [Duration] |
| [Refresh token] | [Token renewal] | [Where stored] | [Duration] |
| [Session] | [State management] | [Where stored] | [Duration] |

### Token Validation

[Describe how tokens are validated - JWT verification, session lookup, etc.]

```
# Where token validation happens
[file path or service]
```

---

## Authorization Model

<!-- FILL: How permissions work -->

### Role-Based Access Control (RBAC)

| Role | Permissions | Description |
|------|-------------|-------------|
| [role] | [what they can do] | [who has this role] |

### Permission Checks

```
# Where authorization is enforced
[file path or middleware location]

# Example permission check
[code example or pattern]
```

### Resource-Level Permissions

<!-- FILL: If users can only access their own resources -->

[Describe how resource ownership is enforced]

---

## Secrets Management

<!-- FILL: Where secrets live and how to manage them -->

### Secrets Storage

| Environment | Storage | Access Method |
|-------------|---------|---------------|
| Local | `.env` file | Environment variables |
| Staging | [Service name] | [How accessed] |
| Production | [Service name] | [How accessed] |

### Secrets Inventory

| Secret | Purpose | Rotation Schedule | Stored In |
|--------|---------|-------------------|-----------|
| `[SECRET_NAME]` | [What it's for] | [How often rotated] | [Location] |

### Rotating Secrets

```bash
# How to rotate [secret type]
[commands or process]
```

### Adding New Secrets

1. [Step 1]
2. [Step 2]
3. [Step 3]

---

## API Security

<!-- FILL: How APIs are secured -->

### Authentication

```
# Required header
Authorization: Bearer <token>
```

### Rate Limiting

| Endpoint | Limit | Window |
|----------|-------|--------|
| [endpoint pattern] | [requests] | [time period] |

### Input Validation

[Describe validation approach - schema validation, sanitization, etc.]

```
# Where validation is defined
[file path or pattern]
```

### CORS Configuration

```
# Allowed origins
[list or pattern]
```

---

## Infrastructure Security

<!-- FILL: Cloud/infra security measures -->

### IAM / Service Accounts

| Service/Role | Permissions | Purpose |
|--------------|-------------|---------|
| [service account] | [permission set] | [why it needs these] |

### Network Security

- [ ] VPC/network isolation configured
- [ ] Database not publicly accessible
- [ ] Firewall rules restrict access
- [ ] TLS everywhere

### Encryption

| Data | At Rest | In Transit |
|------|---------|------------|
| Database | [Encryption method] | [TLS version] |
| File storage | [Encryption method] | [TLS version] |
| Backups | [Encryption method] | N/A |

---

## Security Headers

<!-- FILL: HTTP security headers configured -->

| Header | Value | Purpose |
|--------|-------|---------|
| `Strict-Transport-Security` | [value] | Force HTTPS |
| `Content-Security-Policy` | [value] | Prevent XSS |
| `X-Frame-Options` | [value] | Prevent clickjacking |

---

## Audit Logging

<!-- FILL: What security events are logged -->

### Logged Events

- [ ] Authentication attempts (success/failure)
- [ ] Authorization failures
- [ ] Sensitive data access
- [ ] Admin actions
- [ ] Configuration changes

### Log Location

[Where audit logs are stored and how to access them]

---

## Known Security Considerations

<!-- FILL: Security items to be aware of -->

### Accepted Risks

| Risk | Mitigation | Reason Accepted |
|------|------------|-----------------|
| [risk] | [mitigation in place] | [why accepted] |

### Security TODOs

- [ ] [Security improvement needed]
- [ ] [Security improvement needed]

---

## Incident Response

### If You Suspect a Breach

1. [Immediate step]
2. [Containment step]
3. [Who to contact]

### Key Contacts

| Role | Contact |
|------|---------|
| Security lead | [contact] |
| On-call | [contact] |

---

## Security Review Checklist

For PRs that touch auth, permissions, or sensitive data:

- [ ] No secrets in code
- [ ] Input validation in place
- [ ] Authorization checks present
- [ ] Audit logging added
- [ ] Security headers maintained
- [ ] Dependencies checked for vulnerabilities
