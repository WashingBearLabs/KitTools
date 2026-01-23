<!-- Template Version: 1.0.0 -->
# ENV_REFERENCE.md

> **TEMPLATE_INTENT:** Document environment variables and secrets. What config exists and where to find it.

> Last updated: YYYY-MM-DD
> Updated by: [Human/Claude]

## Overview

This document lists all environment variables used by the application, where they're stored, and how to manage them.

---

## Quick Reference

| Variable | Required | Description |
|----------|----------|-------------|
| `[VAR_NAME]` | Yes/No | [Brief description] |

---

## Required Variables

<!-- FILL: Variables that must be set for the app to run -->

| Variable | Description | Example | Where Stored |
|----------|-------------|---------|--------------|
| `[VAR_NAME]` | [What it's for] | `[example value]` | [.env / Secret Manager / etc.] |

---

## Optional Variables

<!-- FILL: Variables with sensible defaults -->

| Variable | Description | Default | Where Stored |
|----------|-------------|---------|--------------|
| `[VAR_NAME]` | [What it's for] | `[default]` | [.env / etc.] |

---

## Secrets

<!-- FILL: Sensitive values that require special handling -->

| Secret | Purpose | Rotation | Storage Location |
|--------|---------|----------|------------------|
| `[SECRET_NAME]` | [What it's for] | [Frequency] | [Where it lives per environment] |

### Secret Storage by Environment

| Environment | Storage Method | Access Method |
|-------------|----------------|---------------|
| Local | `.env` file (gitignored) | Direct env var |
| Staging | [Secret Manager / Vault / etc.] | [How accessed] |
| Production | [Secret Manager / Vault / etc.] | [How accessed] |

### Getting Secrets for Local Development

```bash
# How to obtain secrets for local development
[commands or instructions]
```

### Rotating Secrets

```bash
# How to rotate [secret type]
[commands or process]
```

---

## Feature Flags

<!-- FILL: Environment-based feature toggles. Delete if none -->

| Variable | Description | Values |
|----------|-------------|--------|
| `[FLAG_NAME]` | [What it toggles] | `true` / `false` |

---

## Service-Specific Variables

<!-- FILL: Group variables by service if you have multiple services -->

### [Service Name]

| Variable | Description | Required |
|----------|-------------|----------|
| `[VAR_NAME]` | [Description] | Yes/No |

---

## Third-Party Service Credentials

<!-- FILL: API keys and credentials for external services -->

| Service | Variable(s) | How to Obtain | Storage |
|---------|-------------|---------------|---------|
| [Service] | `[VAR_NAME]` | [Instructions or link] | [Where stored] |

---

## Environment-Specific Values

<!-- FILL: Values that differ by environment -->

| Variable | Local | Staging | Production |
|----------|-------|---------|------------|
| `[VAR_NAME]` | `[value]` | `[value]` | `[value]` |

---

## Example `.env` Files

### Local Development (`.env`)

```bash
# =============================================================================
# Local Development Environment
# =============================================================================
# Copy this to .env and fill in the values

# Required
[VAR_NAME]=[example or placeholder]

# Optional (defaults shown)
[VAR_NAME]=[default value]

# Feature Flags
[FLAG_NAME]=false
```

### Testing (`.env.test`)

```bash
# =============================================================================
# Test Environment
# =============================================================================

[VAR_NAME]=[test value]
```

---

## Adding New Environment Variables

When adding a new environment variable:

1. Add it to this documentation with description
2. Add to `.env.example` with placeholder/example value
3. Add to CI/CD secrets if needed (see `docs/CI_CD.md`)
4. Add to infrastructure secrets if needed (see `arch/SECURITY.md`)
5. Update deployment configs if needed

---

## Validation

<!-- FILL: How env vars are validated at startup -->

[Describe validation approach: startup checks, schema validation, etc.]

```
# Where validation happens
[file path]
```

---

## Troubleshooting

### Missing Environment Variable Error

```
[Example error message]
```

**Fix:** [How to resolve]

### Invalid Value Error

```
[Example error message]
```

**Fix:** [How to resolve]
