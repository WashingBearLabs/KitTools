<!-- Template Version: 1.1.0 -->
# DATA_MODEL.md

> **TEMPLATE_INTENT:** Document database schema and data relationships. The source of truth for data structure.

> Last updated: YYYY-MM-DD
> Updated by: [Human/Claude]

<!--
NOTE: This file documents the data model / database schema.
Delete this file entirely if the project has no database.
-->

---

## Overview

<!-- FILL: What database technology is used? -->

Database: **[PostgreSQL / MySQL / SQLite / MongoDB / etc.]**
ORM/Query Builder: **[SQLAlchemy / Prisma / Drizzle / Mongoose / None]**
Hosted on: **[Supabase / Cloud SQL / RDS / Local / etc.]**

---

## Entity Relationship Diagram

<!-- FILL: Draw the actual relationships between tables/collections -->

```
[Draw your ER diagram here]

Example format:
┌──────────────┐       ┌──────────────┐
│  [table_a]   │       │  [table_b]   │
├──────────────┤       ├──────────────┤
│ id (PK)      │──────▶│ id (PK)      │
│ [column]     │       │ table_a_id   │
└──────────────┘       └──────────────┘
```

---

## Tables / Collections

<!-- FILL: Document each table. Copy this section for each table -->

### `[table_name]`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `[column]` | [TYPE] | [PK/FK/UNIQUE/etc.] | [Description] |

**Indexes:**
- [Index name] on ([columns])

**Relationships:**
- [Description of foreign key relationships]

---

## Migrations

<!-- FILL: How are schema changes managed? -->

Location: `[path to migrations]`

```bash
# Generate new migration
[command]

# Apply migrations
[command]

# Rollback
[command]
```
