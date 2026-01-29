<!-- Template Version: 1.2.1 -->
<!-- Seeding:
  explorer_focus: testing, tech-stack
  required_sections:
    - "Quick Start"
    - "Test Structure"
  skip_if: no-tests
-->
# TESTING_GUIDE.md

> **TEMPLATE_INTENT:** Document test structure, running tests, and writing new tests. Quality assurance reference.

> Last updated: YYYY-MM-DD
> Updated by: [Human/Claude]

## Quick Start

<!-- FILL: Add commands to run tests in this project -->

```bash
# Run all tests
[command to run all tests]

# Run specific test suite (if applicable)
[command]
```

---

## Testing Strategy

<!-- FILL: Document what types of tests exist and their coverage -->

| Type | Coverage | Tools |
|------|----------|-------|
| Unit | [What's covered] | [Testing framework] |
| Integration | [What's covered] | [Testing framework] |
| E2E | [What's covered] | [Testing framework] |

<!-- Delete rows that don't apply to this project -->

---

## Test Structure

<!-- FILL: Where do tests live? How are they organized? -->

```
[tests location]/
├── [subdirectory]/  # [What these tests cover]
└── [subdirectory]/  # [What these tests cover]
```

---

## Writing Tests

<!-- FILL: Add examples of how to write tests in this project's style -->

### Example Test

```[language]
[Example test in the project's testing style]
```

---

## Running Tests in CI

<!-- FILL: How are tests run in CI? Delete if no CI -->

[Describe CI test configuration, or delete this section]

---

## Test Data / Fixtures

<!-- FILL: How is test data managed? Delete if not applicable -->

[Describe fixtures, factories, seed data, etc.]
