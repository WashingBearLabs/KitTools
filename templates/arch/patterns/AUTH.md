<!-- Template Version: 1.1.0 -->
# AUTH.md

> **TEMPLATE_INTENT:** Document authentication patterns and implementation details.

> Last updated: YYYY-MM-DD
> Updated by: [Human/Claude]

## Overview

This document describes the authentication and authorization patterns.

**Auth Provider:** [Supabase Auth / Auth0 / Custom / etc.]

---

## Authentication Flow

```
[Client] → [Login] → [Auth Provider] → [Token] → [API with Bearer Token]
```

---

## Token Management

| Token | Purpose | Storage | Expiration |
|-------|---------|---------|------------|
| Access Token | API authentication | Memory / Cookie | 15 min - 1 hour |
| Refresh Token | Get new access token | HttpOnly Cookie | 7 - 30 days |

---

## Implementation

[Document your specific auth implementation here]
