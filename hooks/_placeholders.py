"""Shared placeholder detection for kit_tools hooks.

Used by:
- validate_seeded_template.py (PostToolUse hook — per-file check on edits)
- validate_setup.py (called by /kit-tools:init-project — full kit_tools scan)

Centralises regex patterns and exclusion rules so both hooks see the same
drift coverage instead of diverging over time (prior state: each hook had
its own pattern list).
"""
import re
from pathlib import Path


# Placeholder patterns that indicate unfilled template content.
# Each entry: (compiled_pattern, human-readable type label).
# Ordered broad → narrow for clarity; a line may match multiple patterns.
PLACEHOLDER_PATTERNS = [
    # FILL-style placeholders: [FILL: description], [TODO: description], etc.
    (re.compile(r'\[(FILL|TODO|REPLACE|INSERT|ADD|DESCRIBE|LIST|SPECIFY)[:\s][^\]]*\]'), 'fill placeholder'),
    # ALL-CAPS bracket placeholders (3+ chars): [PROJECT_NAME], [API_URL], etc.
    # Excludes common legitimate markdown like [NOTE], [TIP], [OK] by requiring 3+ chars.
    (re.compile(r'\[([A-Z][A-Z_]{2,})\]'), 'bracket placeholder'),
    # Title-case literals common in older templates: [Feature Name], [Project Name], [Your Name]
    (re.compile(r'\[(Feature Name|Project Name|Your Name)\]'), 'title-case placeholder'),
    # Numbered feature list placeholders: [Feature 1], [Feature 2 — description]
    (re.compile(r'\[Feature \d+'), 'list item placeholder'),
    # Date placeholders (but not in Template Version comments)
    (re.compile(r'(?<!Version: \d\.\d\.)YYYY-MM-DD'), 'date placeholder'),
    # Path placeholders with explicit "path" keyword: [path to config]
    (re.compile(r'\[path[^\]]*\]'), 'path placeholder'),
    # Choice placeholders: [type:X|Y|Z]
    (re.compile(r'\[type:[^\]]+\]'), 'choice placeholder'),
    # URL placeholders with explicit "URL" keyword: [GitHub URL], [URL of docs]
    (re.compile(r'\[[^\]]*URL[^\]]*\]'), 'URL placeholder'),
]


# Path patterns that should be skipped during validation.
# Files matching any of these are expected to contain placeholder-like content
# or be transient, and should not trigger placeholder warnings.
EXCLUDE_PATTERNS = [
    re.compile(r'SEED_MANIFEST\.json$'),     # Manifest tracks templates, expected placeholders
    re.compile(r'SYNC_MANIFEST\.json$'),     # Same for sync tracking
    re.compile(r'\.seed_cache/'),            # Exploration cache
    re.compile(r'\.sync_cache/'),            # Drift-detection cache
    re.compile(r'SESSION_SCRATCH\.md$'),     # Temporary scratchpad
    re.compile(r'SESSION_LOG\.md$'),         # Has its own format
    re.compile(r'PROGRESS'),                 # Any progress-tracking file
    re.compile(r'SCRATCH'),                  # Any scratch file
]


def should_validate_path(file_path: str) -> bool:
    """Return True if this file path should be checked for placeholders.

    Only checks `.md` files within `kit_tools/`, excluding manifest, cache,
    session, scratch, and progress files.
    """
    if 'kit_tools/' not in file_path:
        return False
    if not file_path.endswith('.md'):
        return False
    for pattern in EXCLUDE_PATTERNS:
        if pattern.search(file_path):
            return False
    return True


def find_placeholders(content: str) -> list[dict]:
    """Scan content for unfilled placeholders.

    Returns a list of issue dicts with keys: `line`, `type`, `match`.
    Returns an empty list if no placeholders are found.

    Lines starting with `<!--` (HTML comments, including version tags and
    FILL instruction comments) are skipped, since these are either
    intentional metadata or instructions meant for the seeder.
    """
    issues: list[dict] = []
    for line_num, line in enumerate(content.split('\n'), 1):
        stripped = line.strip()

        # Skip HTML comments (version tags, FILL instructions, etc.)
        if stripped.startswith('<!--'):
            continue
        # Skip TEMPLATE_INTENT lines (intentional long-lived metadata)
        if 'TEMPLATE_INTENT:' in line:
            continue

        for pattern, issue_type in PLACEHOLDER_PATTERNS:
            matches = pattern.findall(line)
            if not matches:
                continue
            for match in matches:
                # Extra guard: date placeholder on a Template Version line is metadata.
                if 'Template Version:' in line and issue_type == 'date placeholder':
                    continue
                issues.append({
                    'line': line_num,
                    'type': issue_type,
                    'match': match if isinstance(match, str) else str(match),
                })
    return issues


def file_has_placeholders(file_path) -> bool:
    """Convenience: does this file contain any placeholders?

    Accepts a string path or pathlib.Path. Returns False on IO errors
    rather than raising, since callers typically want to skip unreadable
    files rather than crash validation.
    """
    try:
        content = Path(file_path).read_text(encoding='utf-8')
    except (OSError, UnicodeDecodeError):
        return False
    return bool(find_placeholders(content))
