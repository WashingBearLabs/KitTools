<!-- Template Version: 2.0.0 -->
<!-- Seeding:
  explorer_focus: tech-stack, architecture
  required_sections:
    - "Version Source"
  skip_if: never
-->
# BUMP_VERSION.md

> **TEMPLATE_INTENT:** Project-specific version bumping runbook. Read by `/kit-tools:bump-version` every time it runs. Tells the skill where the version lives and what extra steps are needed beyond the standard bump.

> Last updated: YYYY-MM-DD
> Updated by: [Human/Claude]

---

## Version Source

<!-- FILL: Where does this project's canonical version live? The skill reads and updates this file. -->

| Field | Value |
|-------|-------|
| **File** | `[path to version file, e.g., package.json, pyproject.toml, Cargo.toml]` |
| **Format** | `[json / toml / yaml / plain]` |
| **Field path** | `[e.g., version, tool.poetry.version, package.version]` |

<!-- If the version appears in multiple files that must stay in sync, list them all: -->
<!--
| File | Field path | Notes |
|------|------------|-------|
| `package.json` | `version` | Canonical source |
| `package-lock.json` | `version` | Auto-updated by npm |
-->

---

## Versioning Strategy

<!-- FILL: Describe when to bump major, minor, or patch for THIS project. Delete the defaults below and write project-specific guidance if needed. -->

This project follows [Semantic Versioning](https://semver.org/):

- **Major** (X.0.0) — Breaking changes to public API, incompatible behavior changes
- **Minor** (0.X.0) — New features, non-breaking additions
- **Patch** (0.0.X) — Bug fixes, documentation, internal cleanup

---

## Changelog

<!-- FILL: Does this project maintain a changelog? If so, where? -->

| Field | Value |
|-------|-------|
| **File** | `[CHANGELOG.md / HISTORY.md / none]` |
| **Format** | `[Keep a Changelog / custom / none]` |

<!-- If no changelog is maintained, delete this section. -->

---

## Pre-Bump Steps

<!-- FILL: Steps that must happen BEFORE the version is updated. Delete this section if none. -->

<!-- Examples:
- Run the test suite: `npm test`
- Verify the build compiles: `npm run build`
- Check for uncommitted changes
-->

None.

---

## Additional Version Locations

<!-- FILL: Other files or repos that must be updated when the version changes. Delete this section if the version only lives in one place. -->

<!-- Examples:

### Other files in this repo
| File | What to update |
|------|----------------|
| `README.md` | Version badge or reference |
| `docs/conf.py` | `release` variable |

### External repos
| Repo | Path | What to update | Notes |
|------|------|----------------|-------|
| `/path/to/marketplace-repo` | `marketplace.json` | Version field | Push after this repo |
| `/path/to/docs-site` | `src/content/docs/release-notes.md` | Add release entry | Build triggers on push |
-->

None.

---

## Post-Bump Steps

<!-- FILL: Steps that must happen AFTER all versions are updated but BEFORE committing. Delete this section if none. -->

<!-- Examples:
- Regenerate lock file: `npm install`
- Update generated docs: `npm run docs`
- Run smoke test: `npm run test:smoke`
-->

None.

---

## Commit Convention

<!-- FILL: How should the version bump commit be formatted? -->

| Field | Value |
|-------|-------|
| **Message format** | `[e.g., "release: vX.Y.Z", "chore: bump version to X.Y.Z"]` |
| **Tag** | `[e.g., "vX.Y.Z", none]` |
| **Branch** | `[commit directly to main / create release branch]` |

---

> **Note:** This runbook is read by `/kit-tools:bump-version` each time the skill runs. Keep it current — stale instructions here mean missed steps on every release.
