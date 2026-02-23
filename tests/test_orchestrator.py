"""Unit tests for execute_orchestrator.py pure functions."""

import json
import os
import tempfile

import pytest

# Add scripts/ to path so we can import the orchestrator
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from execute_orchestrator import (
    parse_prd_frontmatter,
    parse_stories_from_prd,
    strip_frontmatter,
    sanitize_failure_details,
    gather_prior_learnings,
    update_state_story,
    read_json_result,
    read_verification_result,
    extract_learnings_from_results,
    build_implementation_prompt,
    build_verification_prompt,
    detect_test_command,
    VERIFY_RESULT_FILE,
)


# --- Fixtures ---


BASIC_PRD = """\
---
feature: user-auth
status: active
session_ready: true
depends_on: []
epic:
epic_seq:
epic_final:
created: 2026-02-22
updated: 2026-02-22
---

# PRD: User Auth

## Overview

Implement user authentication.

## User Stories

### US-001: Add login endpoint

**Description:** As a user, I want to log in so that I can access my account.

**Acceptance Criteria:**
- [ ] POST /auth/login accepts email and password
- [ ] Returns JWT token on success
- [ ] Returns 401 on invalid credentials
- [ ] Typecheck/lint passes

### US-002: Add logout endpoint

**Description:** As a user, I want to log out so that my session is terminated.

**Acceptance Criteria:**
- [x] POST /auth/logout invalidates the session
- [x] Returns 200 on success
- [x] Typecheck/lint passes

## Functional Requirements

- **FR-1:** The system must support JWT authentication
"""


EPIC_PRD = """\
---
feature: oauth-schema
status: active
session_ready: true
depends_on: [user-auth, session-mgmt]
epic: oauth
epic_seq: 1
epic_final: false
created: 2026-02-22
updated: 2026-02-22
---

# PRD: OAuth Schema
"""


PRD_NO_FRONTMATTER = """\
# PRD: No Frontmatter

## Overview

This PRD has no YAML frontmatter.
"""


PRD_MALFORMED_FRONTMATTER = """\
---
this is not: valid: yaml: at: all
  broken indentation
---

# PRD: Malformed
"""


PRD_WITH_HINTS = """\
---
feature: hints-test
status: active
session_ready: true
depends_on: []
created: 2026-02-22
updated: 2026-02-22
---

# PRD: Hints Test

## User Stories

### US-001: Story with hints

**Description:** As a user, I want a feature.

**Implementation Hints:**
- Login page at src/pages/login.tsx
- Use existing SessionService.create()
- OAuth callback at /auth/callback

**Acceptance Criteria:**
- [ ] Feature works
- [ ] Typecheck/lint passes

### US-002: Story without hints

**Description:** As a user, I want another feature.

**Acceptance Criteria:**
- [ ] Other feature works
- [ ] Typecheck/lint passes
"""


# --- parse_prd_frontmatter ---


class TestParsePrdFrontmatter:

    def _write_and_parse(self, content: str) -> dict:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write(content)
            f.flush()
            result = parse_prd_frontmatter(f.name)
        os.unlink(f.name)
        return result

    def test_basic_fields(self):
        fm = self._write_and_parse(BASIC_PRD)
        assert fm["feature"] == "user-auth"
        assert fm["status"] == "active"
        assert fm["created"] == "2026-02-22"
        assert fm["updated"] == "2026-02-22"

    def test_boolean_fields(self):
        fm = self._write_and_parse(BASIC_PRD)
        assert fm["session_ready"] is True

    def test_epic_boolean_false(self):
        fm = self._write_and_parse(EPIC_PRD)
        assert fm["epic_final"] is False

    def test_list_field(self):
        fm = self._write_and_parse(EPIC_PRD)
        assert fm["depends_on"] == ["user-auth", "session-mgmt"]

    def test_empty_list(self):
        fm = self._write_and_parse(BASIC_PRD)
        assert fm["depends_on"] == []

    def test_integer_field(self):
        fm = self._write_and_parse(EPIC_PRD)
        assert fm["epic_seq"] == 1

    def test_empty_fields_excluded(self):
        """Empty YAML values (None) should be excluded from the result dict."""
        fm = self._write_and_parse(BASIC_PRD)
        # epic, epic_seq, epic_final are empty in BASIC_PRD
        assert "epic" not in fm
        assert "epic_seq" not in fm
        assert "epic_final" not in fm

    def test_no_frontmatter(self):
        fm = self._write_and_parse(PRD_NO_FRONTMATTER)
        assert fm == {}

    def test_malformed_frontmatter(self):
        fm = self._write_and_parse(PRD_MALFORMED_FRONTMATTER)
        # yaml.safe_load may parse this as a dict or raise — either way we get a dict back
        assert isinstance(fm, dict)

    def test_epic_fields(self):
        fm = self._write_and_parse(EPIC_PRD)
        assert fm["epic"] == "oauth"
        assert fm["epic_seq"] == 1
        assert fm["epic_final"] is False
        assert fm["depends_on"] == ["user-auth", "session-mgmt"]


# --- parse_stories_from_prd ---


class TestParseStoriesFromPrd:

    def _write_and_parse(self, content: str) -> list:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write(content)
            f.flush()
            result = parse_stories_from_prd(f.name)
        os.unlink(f.name)
        return result

    def test_parses_two_stories(self):
        stories = self._write_and_parse(BASIC_PRD)
        assert len(stories) == 2

    def test_story_ids(self):
        stories = self._write_and_parse(BASIC_PRD)
        assert stories[0]["id"] == "US-001"
        assert stories[1]["id"] == "US-002"

    def test_story_titles(self):
        stories = self._write_and_parse(BASIC_PRD)
        assert stories[0]["title"] == "Add login endpoint"
        assert stories[1]["title"] == "Add logout endpoint"

    def test_uncompleted_story(self):
        stories = self._write_and_parse(BASIC_PRD)
        assert stories[0]["completed"] is False

    def test_completed_story(self):
        stories = self._write_and_parse(BASIC_PRD)
        assert stories[1]["completed"] is True

    def test_criteria_extracted(self):
        stories = self._write_and_parse(BASIC_PRD)
        assert len(stories[0]["criteria"]) == 4
        assert "POST /auth/login accepts email and password" in stories[0]["criteria"][0]

    def test_criteria_text_format(self):
        stories = self._write_and_parse(BASIC_PRD)
        # criteria_text should be all unchecked format
        assert stories[0]["criteria_text"].startswith("- [ ] ")

    def test_no_stories(self):
        stories = self._write_and_parse(PRD_NO_FRONTMATTER)
        assert stories == []

    def test_story_with_hints(self):
        stories = self._write_and_parse(PRD_WITH_HINTS)
        assert len(stories) == 2
        # Stories should still parse correctly even with hints section
        assert stories[0]["id"] == "US-001"
        assert len(stories[0]["criteria"]) == 2
        # Hints should be extracted
        assert "Login page at src/pages/login.tsx" in stories[0]["hints"]
        assert "Use existing SessionService.create()" in stories[0]["hints"]
        assert "OAuth callback at /auth/callback" in stories[0]["hints"]

    def test_story_without_hints(self):
        stories = self._write_and_parse(PRD_WITH_HINTS)
        # US-002 has no hints section
        assert stories[1]["hints"] == ""

    def test_hints_empty_in_basic_prd(self):
        stories = self._write_and_parse(BASIC_PRD)
        # BASIC_PRD has no hints sections
        assert stories[0]["hints"] == ""
        assert stories[1]["hints"] == ""

    def test_description_extracted(self):
        stories = self._write_and_parse(BASIC_PRD)
        assert "log in" in stories[0]["description"]


# --- strip_frontmatter ---


class TestStripFrontmatter:

    def test_strips_frontmatter(self):
        text = "---\nname: test\n---\n\n# Content"
        assert strip_frontmatter(text) == "# Content"

    def test_no_frontmatter(self):
        text = "# No frontmatter here"
        assert strip_frontmatter(text) == "# No frontmatter here"

    def test_empty_string(self):
        assert strip_frontmatter("") == ""

    def test_whitespace_before_frontmatter(self):
        text = "  \n---\nname: test\n---\n\nContent"
        assert strip_frontmatter(text) == "Content"

    def test_frontmatter_only(self):
        text = "---\nname: test\n---"
        result = strip_frontmatter(text)
        assert result == ""


# --- sanitize_failure_details ---


class TestSanitizeFailureDetails:

    def test_strips_session_error_prefix(self):
        result = sanitize_failure_details("SESSION_ERROR: Something went wrong")
        assert result == "Something went wrong"

    def test_truncates_long_string(self):
        long_msg = "A" * 300
        result = sanitize_failure_details(long_msg)
        assert len(result) <= 153  # 150 + "..."

    def test_truncates_template_content(self):
        result = sanitize_failure_details("---\nname: template\ndescription: stuff")
        assert result.endswith("...")

    def test_takes_first_line_only(self):
        result = sanitize_failure_details("First line\nSecond line\nThird line")
        assert result == "First line"

    def test_normal_message(self):
        result = sanitize_failure_details("Verification failed: criterion 3 not met")
        assert result == "Verification failed: criterion 3 not met"


# --- gather_prior_learnings ---


class TestGatherPriorLearnings:

    def test_empty_state(self):
        state = {"stories": {}}
        result = gather_prior_learnings(state, "US-001")
        assert result == []

    def test_single_prd_mode(self):
        state = {
            "stories": {
                "US-001": {"learnings": ["Found pattern X"]},
                "US-002": {"learnings": ["Use service Y"]},
            }
        }
        result = gather_prior_learnings(state, "US-003")
        assert "Found pattern X" in result
        assert "Use service Y" in result

    def test_excludes_current_story(self):
        state = {
            "stories": {
                "US-001": {"learnings": ["Should include"]},
                "US-002": {"learnings": ["Should exclude"]},
            }
        }
        result = gather_prior_learnings(state, "US-002")
        assert "Should include" in result
        assert "Should exclude" not in result

    def test_epic_mode(self):
        state = {
            "prds": {
                "prd-a.md": {
                    "stories": {
                        "US-001": {"learnings": ["From PRD A"]},
                    }
                },
                "prd-b.md": {
                    "stories": {
                        "US-001": {"learnings": ["From PRD B"]},
                    }
                },
            }
        }
        result = gather_prior_learnings(state, "US-002", prd_key="prd-b.md")
        assert "From PRD A" in result
        assert "From PRD B" in result

    def test_prunes_at_15(self):
        state = {
            "stories": {
                f"US-{i:03d}": {"learnings": [f"Learning {i}"]}
                for i in range(20)
            }
        }
        result = gather_prior_learnings(state, "US-999")
        assert len(result) == 15

    def test_epic_excludes_current_story_in_current_prd(self):
        state = {
            "prds": {
                "prd-a.md": {
                    "stories": {
                        "US-001": {"learnings": ["Should exclude"]},
                        "US-002": {"learnings": ["Should include"]},
                    }
                },
            }
        }
        result = gather_prior_learnings(state, "US-001", prd_key="prd-a.md")
        assert "Should include" in result
        assert "Should exclude" not in result


# --- update_state_story ---


class TestUpdateStateStory:

    def test_single_prd_mode(self):
        state = {"stories": {}}
        update_state_story(state, "US-001", "in_progress", 1)
        assert state["stories"]["US-001"]["status"] == "in_progress"
        assert state["stories"]["US-001"]["attempts"] == 1

    def test_completed_with_learnings(self):
        state = {"stories": {}}
        update_state_story(state, "US-001", "completed", 2, learnings=["Found X"])
        assert state["stories"]["US-001"]["status"] == "completed"
        assert "completed_at" in state["stories"]["US-001"]
        assert "Found X" in state["stories"]["US-001"]["learnings"]

    def test_failed_with_failure(self):
        state = {"stories": {}}
        update_state_story(state, "US-001", "failed", 3, failure="Timed out")
        assert state["stories"]["US-001"]["last_failure"] == "Timed out"

    def test_epic_mode(self):
        state = {"prds": {"prd-a.md": {"stories": {}}}}
        update_state_story(state, "US-001", "in_progress", 1, prd_key="prd-a.md")
        assert state["prds"]["prd-a.md"]["stories"]["US-001"]["status"] == "in_progress"

    def test_learnings_accumulate(self):
        state = {"stories": {}}
        update_state_story(state, "US-001", "retrying", 1, learnings=["First"])
        update_state_story(state, "US-001", "retrying", 2, learnings=["Second"])
        assert state["stories"]["US-001"]["learnings"] == ["First", "Second"]


# --- read_json_result ---


class TestReadJsonResult:

    def test_valid_json(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"verdict": "pass", "story_id": "US-001"}, f)
            f.flush()
            result, error = read_json_result(f.name)
        os.unlink(f.name)
        assert result is not None
        assert result["verdict"] == "pass"
        assert error == ""

    def test_missing_file(self):
        result, error = read_json_result("/nonexistent/path/result.json")
        assert result is None
        assert "not found" in error

    def test_invalid_json(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write("this is not json {{{")
            f.flush()
            result, error = read_json_result(f.name)
        os.unlink(f.name)
        assert result is None
        assert "Invalid JSON" in error

    def test_non_dict_json(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(["a", "list"], f)
            f.flush()
            result, error = read_json_result(f.name)
        os.unlink(f.name)
        assert result is None
        assert "not a JSON object" in error

    def test_empty_dict(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({}, f)
            f.flush()
            result, error = read_json_result(f.name)
        os.unlink(f.name)
        assert result == {}
        assert error == ""


# --- read_verification_result ---


class TestReadVerificationResult:

    def test_normalizes_verdict_to_lowercase(self, tmp_path):
        """read_verification_result uses VERIFY_RESULT_FILE relative to project_dir."""
        result_path = tmp_path / VERIFY_RESULT_FILE
        result_path.parent.mkdir(parents=True, exist_ok=True)
        result_path.write_text(json.dumps({"verdict": "PASS", "story_id": "US-001"}))
        result, error = read_verification_result(str(tmp_path))
        assert error == ""
        assert result is not None
        assert result["verdict"] == "pass"

    def test_missing_verdict_field(self, tmp_path):
        """read_verification_result returns error when verdict field is missing."""
        result_path = tmp_path / VERIFY_RESULT_FILE
        result_path.parent.mkdir(parents=True, exist_ok=True)
        result_path.write_text(json.dumps({"story_id": "US-001"}))
        result, error = read_verification_result(str(tmp_path))
        assert result is None
        assert "verdict" in error

    def test_file_not_found(self, tmp_path):
        result, error = read_verification_result(str(tmp_path))
        assert result is None
        assert "not found" in error


# --- extract_learnings_from_results ---


class TestExtractLearningsFromResults:

    def test_both_results(self):
        impl = {
            "learnings": ["Found pattern X", "Use service Y"],
            "issues": ["Minor issue Z"],
        }
        verify = {
            "recommendations": "Consider error handling",
            "overall_notes": "Good implementation overall",
        }
        learnings = extract_learnings_from_results(impl, verify)
        assert "Found pattern X" in learnings
        assert "Use service Y" in learnings
        assert "Issue: Minor issue Z" in learnings
        assert "Verifier: Consider error handling" in learnings
        assert "Verifier note: Good implementation overall" in learnings

    def test_impl_only(self):
        impl = {"learnings": ["Found X"], "issues": []}
        learnings = extract_learnings_from_results(impl, None)
        assert "Found X" in learnings
        assert len(learnings) == 1

    def test_verify_only(self):
        verify = {"recommendations": "Fix Y", "overall_notes": ""}
        learnings = extract_learnings_from_results(None, verify)
        assert "Verifier: Fix Y" in learnings

    def test_both_none(self):
        learnings = extract_learnings_from_results(None, None)
        assert learnings == []

    def test_empty_learnings_filtered(self):
        impl = {"learnings": ["", "Real learning", ""], "issues": [""]}
        learnings = extract_learnings_from_results(impl, None)
        assert learnings == ["Real learning"]


# --- build_implementation_prompt ---


class TestBuildImplementationPrompt:

    def _make_config(self, template: str = "# Implementer\n{{IMPLEMENTATION_HINTS}}\n{{ACCEPTANCE_CRITERIA}}\n{{STORY_ID}}") -> dict:
        return {
            "implementer_template": template,
            "project_context": {
                "prd_overview": "Test overview",
                "synopsis": "kit_tools/SYNOPSIS.md",
                "code_arch": "kit_tools/arch/CODE_ARCH.md",
                "conventions": "kit_tools/docs/CONVENTIONS.md",
                "gotchas": "kit_tools/docs/GOTCHAS.md",
            },
            "feature_name": "test-feature",
            "prd_path": "/tmp/test-prd.md",
            "project_dir": "/tmp/test-project",
        }

    def _make_story(self, hints: str = "") -> dict:
        return {
            "id": "US-001",
            "title": "Test story",
            "description": "A test story",
            "hints": hints,
            "criteria": ["Criterion 1", "Criterion 2"],
            "criteria_text": "- [ ] Criterion 1\n- [ ] Criterion 2",
        }

    def test_hints_interpolated(self):
        story = self._make_story(hints="- Use existing SessionService\n- File at src/auth.ts")
        config = self._make_config()
        state = {"stories": {}}
        prompt = build_implementation_prompt(story, config, state, attempt=1)
        assert "Use existing SessionService" in prompt
        assert "File at src/auth.ts" in prompt

    def test_empty_hints_fallback(self):
        story = self._make_story(hints="")
        config = self._make_config()
        state = {"stories": {}}
        prompt = build_implementation_prompt(story, config, state, attempt=1)
        assert "No hints provided" in prompt

    def test_reference_paths_in_prompt(self):
        story = self._make_story()
        config = self._make_config(
            "{{SYNOPSIS_PATH}} {{CODE_ARCH_PATH}} {{CONVENTIONS_PATH}} {{GOTCHAS_PATH}}"
        )
        state = {"stories": {}}
        prompt = build_implementation_prompt(story, config, state, attempt=1)
        assert "kit_tools/SYNOPSIS.md" in prompt
        assert "kit_tools/arch/CODE_ARCH.md" in prompt
        assert "kit_tools/docs/CONVENTIONS.md" in prompt
        assert "kit_tools/docs/GOTCHAS.md" in prompt


# --- build_verification_prompt ---


class TestBuildVerificationPrompt:

    def _make_config(self, template: str = "# Verifier\n{{FILES_CHANGED}}\n{{CONVENTIONS_PATH}}") -> dict:
        return {
            "verifier_template": template,
            "project_context": {
                "conventions": "kit_tools/docs/CONVENTIONS.md",
            },
            "project_dir": "/tmp/test-project",
        }

    def _make_story(self) -> dict:
        return {
            "id": "US-001",
            "title": "Test story",
            "criteria_text": "- [ ] Criterion 1",
        }

    def test_git_files_interpolated(self):
        config = self._make_config()
        story = self._make_story()
        prompt = build_verification_prompt(story, config, "src/auth.ts\nsrc/api.ts")
        assert "src/auth.ts" in prompt
        assert "src/api.ts" in prompt

    def test_no_impl_output_in_prompt(self):
        """Verifier prompt should NOT contain implementer output/evidence."""
        config = self._make_config("{{STORY_ID}} {{FILES_CHANGED}} {{CONVENTIONS_PATH}} {{ACCEPTANCE_CRITERIA}}")
        story = self._make_story()
        prompt = build_verification_prompt(story, config, "src/file.ts")
        # There should be no implementation evidence placeholder
        assert "IMPLEMENTATION_EVIDENCE" not in prompt
        assert "Evidence from Implementer" not in prompt

    def test_reference_path_in_prompt(self):
        config = self._make_config()
        story = self._make_story()
        prompt = build_verification_prompt(story, config, "src/file.ts")
        assert "kit_tools/docs/CONVENTIONS.md" in prompt


# --- detect_test_command ---


class TestDetectTestCommand:

    def test_package_json_npm_test(self, tmp_path):
        pkg = {"scripts": {"test": "jest --coverage"}}
        (tmp_path / "package.json").write_text(json.dumps(pkg))
        assert detect_test_command(str(tmp_path)) == "npm test"

    def test_package_json_default_skipped(self, tmp_path):
        pkg = {"scripts": {"test": 'echo "Error: no test specified" && exit 1'}}
        (tmp_path / "package.json").write_text(json.dumps(pkg))
        assert detect_test_command(str(tmp_path)) is None

    def test_package_json_no_test_script(self, tmp_path):
        pkg = {"scripts": {"start": "node index.js"}}
        (tmp_path / "package.json").write_text(json.dumps(pkg))
        assert detect_test_command(str(tmp_path)) is None

    def test_pyproject_toml_pytest(self, tmp_path):
        (tmp_path / "pyproject.toml").write_text("[tool.pytest.ini_options]\ntestpaths = ['tests']")
        assert detect_test_command(str(tmp_path)) == "python3 -m pytest"

    def test_pytest_ini(self, tmp_path):
        (tmp_path / "pytest.ini").write_text("[pytest]\ntestpaths = tests")
        assert detect_test_command(str(tmp_path)) == "python3 -m pytest"

    def test_makefile_test_target(self, tmp_path):
        (tmp_path / "Makefile").write_text("build:\n\tgo build\n\ntest:\n\tgo test ./...")
        assert detect_test_command(str(tmp_path)) == "make test"

    def test_makefile_no_test_target(self, tmp_path):
        (tmp_path / "Makefile").write_text("build:\n\tgo build\n\nclean:\n\trm -rf build/")
        assert detect_test_command(str(tmp_path)) is None

    def test_testing_guide_quickstart(self, tmp_path):
        guide_dir = tmp_path / "kit_tools" / "testing"
        guide_dir.mkdir(parents=True)
        (guide_dir / "TESTING_GUIDE.md").write_text(
            "# Testing\n\n## Quick Start\n\n```bash\npython3 -m pytest tests/ -v\n```\n"
        )
        assert detect_test_command(str(tmp_path)) == "python3 -m pytest tests/ -v"

    def test_nothing_detected(self, tmp_path):
        assert detect_test_command(str(tmp_path)) is None

    def test_priority_order_package_json_wins(self, tmp_path):
        """package.json should be checked before pyproject.toml."""
        pkg = {"scripts": {"test": "jest"}}
        (tmp_path / "package.json").write_text(json.dumps(pkg))
        (tmp_path / "pyproject.toml").write_text("[tool.pytest.ini_options]\n")
        assert detect_test_command(str(tmp_path)) == "npm test"
