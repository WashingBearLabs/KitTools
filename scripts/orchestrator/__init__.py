"""Orchestrator package — split from the monolithic execute_orchestrator.py
during the 2.4.0 refactor. This __init__ re-exports the public API so that
`from orchestrator import X` and the legacy `execute_orchestrator.X` shim
both keep working.
"""

from .utils import *  # noqa: F401,F403
from .events import *  # noqa: F401,F403
from .config import *  # noqa: F401,F403
from .state import *  # noqa: F401,F403
from .specs import *  # noqa: F401,F403
from .prompts import *  # noqa: F401,F403
from .sessions import *  # noqa: F401,F403
from .tests_metrics import *  # noqa: F401,F403
from .git_ops import *  # noqa: F401,F403
from .supervisor import *  # noqa: F401,F403
from .execution_log import *  # noqa: F401,F403
from .executor import *  # noqa: F401,F403
from .entry import *  # noqa: F401,F403

# Explicit re-exports for private names (skipped by * imports)
from .utils import _TEMPLATE_TOKEN_PATTERN  # noqa: F401
from .utils import _assert_prompt_fully_substituted  # noqa: F401
from .utils import _atomic_json_write  # noqa: F401
from .state import _validate_state  # noqa: F401
from .state import _read_state_file  # noqa: F401
from .state import _REQUIRED_STATE_FIELDS_COMMON  # noqa: F401
from .state import _REQUIRED_STATE_FIELDS_SINGLE  # noqa: F401
from .state import _REQUIRED_STATE_FIELDS_EPIC  # noqa: F401
from .state import _store_attempt_diff  # noqa: F401
from .git_ops import _resolve_git_dir  # noqa: F401
from .git_ops import _GIT_STUCK_STATE_MARKERS  # noqa: F401
from .sessions import _kill_process_group  # noqa: F401
from .sessions import _is_permanent_error  # noqa: F401
from .sessions import _extract_json_from_text  # noqa: F401
from .supervisor import _get_memory_usage_mb  # noqa: F401
from .supervisor import _get_child_pids  # noqa: F401
from .supervisor import _count_completed_stories  # noqa: F401
from .supervisor import _count_total_stories  # noqa: F401
from .supervisor import _handle_split_story  # noqa: F401
from .prompts import _trim_section  # noqa: F401
from .prompts import _get_persistent_learnings_path  # noqa: F401
from .prompts import _read_persistent_learnings  # noqa: F401
from .tests_metrics import _filter_source_files  # noqa: F401
from .tests_metrics import _resolve_test_files  # noqa: F401
from .tests_metrics import _build_test_command  # noqa: F401
