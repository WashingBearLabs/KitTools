<!-- Template Version: 1.2.2 -->
<!-- Seeding:
  explorer_focus: architecture, dependencies
  required_sections:
    - "Endpoints" or "Commands" or "Interface"
  skip_if: no-api
-->
# API_GUIDE.md

> **TEMPLATE_INTENT:** Document API endpoints, CLI commands, or library interface. The external contract.

> Last updated: YYYY-MM-DD
> Updated by: [Human/Claude]

<!--
NOTE: This file documents APIs.
- For REST APIs: Document HTTP endpoints
- For libraries: Document public functions/classes
- For CLIs: Document commands and flags
- Delete this file if not applicable
-->

---

## Overview

<!-- FILL: Describe the API and how to access it -->

Base URL: `[production URL]` (production) | `[local URL]` (development)

[Describe the API format: REST, GraphQL, gRPC, library exports, CLI commands, etc.]

---

## Authentication

<!-- FILL: How is the API authenticated? Delete if no auth -->

```
[Authentication method and example]
```

---

## Common Response Codes

<!-- FILL: For HTTP APIs. Delete for libraries/CLIs -->

| Code | Meaning |
|------|---------|
| [code] | [meaning] |

---

## Endpoints / Commands / Functions

<!-- FILL: Document the actual API surface -->

### [Endpoint/Command/Function Name]

```
[Method] [Path/Signature]
```

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| [name] | [type] | [yes/no] | [description] |

**Response/Returns:**
```
[Example response or return value]
```

---

<!-- Copy the section above for each endpoint/command/function -->
