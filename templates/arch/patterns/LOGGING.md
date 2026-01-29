<!-- Template Version: 1.2.0 -->
<!-- Seeding:
  explorer_focus: operations, architecture
  required_sections:
    - "Overview"
  skip_if: never
-->
# LOGGING.md

> **TEMPLATE_INTENT:** Document logging patterns, levels, and conventions.

> Last updated: YYYY-MM-DD
> Updated by: [Human/Claude]

## Overview

This document describes the logging patterns used in this project.

---

## Log Levels

| Level | When to Use |
|-------|-------------|
| `DEBUG` | Detailed diagnostic info (dev only) |
| `INFO` | Normal operations worth recording |
| `WARNING` | Something unexpected but handled |
| `ERROR` | Something failed but app continues |
| `CRITICAL` | App cannot continue |

---

## What to Log

### Always Log
- Authentication events (login, logout, failed attempts)
- Authorization failures
- Data modifications (create, update, delete)
- External API calls (with duration)
- Errors and exceptions

### Never Log
- Passwords or secrets
- Full credit card numbers
- Personal health information
- Session tokens or API keys

---

## Implementation

[Document your specific logging implementation here]
