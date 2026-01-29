<!-- Template Version: 1.1.0 -->
# ERROR_HANDLING.md

> **TEMPLATE_INTENT:** Document error handling patterns and conventions.

> Last updated: YYYY-MM-DD
> Updated by: [Human/Claude]

## Overview

This document describes how errors are handled throughout the application.

---

## Error Categories

| Category | HTTP Status | User Message | Log Level |
|----------|-------------|--------------|-----------|
| Validation | 400 | Specific field errors | INFO |
| Authentication | 401 | "Please log in" | WARNING |
| Authorization | 403 | "Not permitted" | WARNING |
| Not Found | 404 | "Resource not found" | INFO |
| Server Error | 500 | "Something went wrong" | ERROR |

---

## Error Response Format

```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "Human readable message",
    "details": [],
    "correlation_id": "abc-123"
  }
}
```

---

## Implementation

[Document your specific error handling implementation here]
