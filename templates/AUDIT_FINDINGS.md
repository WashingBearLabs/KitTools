<!-- Template Version: 1.2.2 -->
<!-- Seeding:
  explorer_focus: none
  required_sections: []
  skip_if: always
  note: AUDIT_FINDINGS is populated by validate-phase skill, not during seeding
-->
# AUDIT_FINDINGS.md

> **TEMPLATE_INTENT:** Persistent record of code quality, security, and intent alignment findings from automated validation. Tracks findings across sessions with status tracking and archival.

> Last Updated: YYYY-MM-DD
> Updated by: Claude

---

## Status Key

| Status | Meaning |
|--------|---------|
| `open` | Finding has not been addressed |
| `resolved` | Finding has been fixed or addressed |
| `dismissed` | Finding reviewed and intentionally not addressed (with reason) |

## Severity Key

| Severity | Meaning |
|----------|---------|
| `critical` | Must address before shipping — security vulnerabilities, data loss risks, broken functionality |
| `warning` | Should address — convention violations, potential bugs, incomplete error handling |
| `info` | Worth noting — minor style issues, suggestions, observations |

---

## Active Findings

<!-- Newest findings at top. Each entry has a unique ID: YYYY-MM-DD-NNN -->
<!-- Findings are added by /kit-tools:validate-phase -->

*No active findings.*

---

## Archived Findings

<!-- Resolved or dismissed findings are moved here with their resolution note -->

*No archived findings.*
