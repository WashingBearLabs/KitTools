<!-- Template Version: 1.1.0 -->
<!-- Seeding:
  explorer_focus: tech-stack, architecture
  required_sections:
    - "Code Style"
  skip_if: never
-->
# CONVENTIONS.md

> **TEMPLATE_INTENT:** Document coding standards and style guidelines. What 'good' looks like here.

> Last updated: YYYY-MM-DD
> Updated by: [Human/Claude]

## Code Style

### Python
- **Formatter:** Black
- **Linter:** Ruff
- **Line length:** 88

### TypeScript
- **Formatter:** Prettier
- **Linter:** ESLint

---

## Naming Conventions

| Type | Convention | Example |
|------|------------|---------|
| Files (Python) | snake_case | `user_service.py` |
| Files (TS) | camelCase | `userService.ts` |
| Classes | PascalCase | `UserService` |
| Functions | camelCase/snake_case | `getUser`/`get_user` |
| Constants | SCREAMING_SNAKE | `MAX_RETRIES` |
| Env vars | SCREAMING_SNAKE | `DATABASE_URL` |

---

## Git Conventions

### Branch Naming
```
feature/short-description
bugfix/issue-123-description
hotfix/critical-fix
```

### Commit Messages (Conventional Commits)
```
feat: add user profile page
fix: correct login redirect
docs: update API documentation
```
