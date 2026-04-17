#!/usr/bin/env python3
"""
KitTools Execute Orchestrator — backward-compat shim.

The orchestrator logic was split from this monolithic file into the
`orchestrator/` package during the 2.4.0 refactor. This module remains as
the CLI entry point and re-exports the public API so that tests, skills,
and anyone who imports from `execute_orchestrator` keeps working.

Usage:
    python3 execute_orchestrator.py --config kit_tools/specs/.execution-config.json
"""

import os
import sys

# Make the orchestrator package importable regardless of how this script is
# launched. When run as `python3 /path/to/scripts/execute_orchestrator.py`,
# Python already adds the script's directory to sys.path. Guard just in case
# the shim is loaded via `importlib` from a test harness where that isn't true.
_SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

# Re-export everything from the orchestrator package.
from orchestrator import *  # noqa: F401,F403,E402
from orchestrator import (  # noqa: F401,E402
    # Private names that `from X import *` skips — tests and internals
    # rely on these, so re-export explicitly.
    _assert_prompt_fully_substituted,
    _atomic_json_write,
    _build_test_command,
    _count_completed_stories,
    _count_total_stories,
    _extract_json_from_text,
    _filter_source_files,
    _get_child_pids,
    _get_memory_usage_mb,
    _get_persistent_learnings_path,
    _GIT_STUCK_STATE_MARKERS,
    _handle_split_story,
    _is_permanent_error,
    _kill_process_group,
    _read_persistent_learnings,
    _read_state_file,
    _REQUIRED_STATE_FIELDS_COMMON,
    _REQUIRED_STATE_FIELDS_EPIC,
    _REQUIRED_STATE_FIELDS_SINGLE,
    _resolve_git_dir,
    _resolve_test_files,
    _store_attempt_diff,
    _TEMPLATE_TOKEN_PATTERN,
    _trim_section,
    _validate_state,
)

# Main entry point is also re-exported. When run as a script,
# dispatch to it.
from orchestrator.entry import main  # noqa: E402


if __name__ == "__main__":
    main()
