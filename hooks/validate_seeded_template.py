#!/usr/bin/env python3
"""
validate_seeded_template.py - Quick placeholder check after template edits.

Trigger: PostToolUse (Edit|Write)

When a template file in kit_tools/ is edited, performs a quick check for
common unfilled placeholder patterns and warns immediately if any remain.
This provides fast feedback during seeding without running the full validator.
"""
import json
import os
import re
import sys


# Placeholder patterns that indicate unfilled template content
PLACEHOLDER_PATTERNS = [
    # Square bracket placeholders
    (r'\[([A-Z][A-Z_]+|[a-z][a-z_ ]+)\]', 'bracket placeholder'),
    # Date placeholders in content (not in version comments)
    (r'(?<!Version: \d\.\d\.)YYYY-MM-DD', 'date placeholder'),
    # Mustache placeholders (but not in agent/skill templates)
    (r'\{\{[^}]+\}\}', 'mustache placeholder'),
    # Path placeholders
    (r'\[path[^\]]*\]', 'path placeholder'),
    # Choice placeholders
    (r'\[type:[^\]]+\]', 'choice placeholder'),
    # URL placeholders
    (r'\[[^\]]*URL[^\]]*\]', 'URL placeholder'),
    # Feature list placeholders
    (r'- \[Feature \d', 'list item placeholder'),
]

# Files/patterns to exclude from validation
EXCLUDE_PATTERNS = [
    r'SEED_MANIFEST\.json$',  # Manifest has template placeholders
    r'\.seed_cache/',  # Cache files
    r'SESSION_SCRATCH\.md$',  # Scratchpad is temporary
    r'SESSION_LOG\.md$',  # Session log has its own format
]


def should_validate(file_path: str) -> bool:
    """Check if this file should be validated."""
    # Must be in kit_tools directory
    if 'kit_tools/' not in file_path:
        return False

    # Must be a markdown file
    if not file_path.endswith('.md'):
        return False

    # Check exclusions
    for pattern in EXCLUDE_PATTERNS:
        if re.search(pattern, file_path):
            return False

    return True


def check_for_placeholders(content: str) -> list:
    """Check content for unfilled placeholders."""
    issues = []
    lines = content.split('\n')

    for line_num, line in enumerate(lines, 1):
        # Skip HTML comments (instructions, version tags)
        if line.strip().startswith('<!--'):
            continue

        # Skip TEMPLATE_INTENT lines (these are meant to stay)
        if 'TEMPLATE_INTENT:' in line:
            continue

        for pattern, issue_type in PLACEHOLDER_PATTERNS:
            matches = re.findall(pattern, line)
            if matches:
                for match in matches:
                    # Skip if it's part of a version comment on same line
                    if 'Template Version:' in line and issue_type == 'date placeholder':
                        continue
                    # Skip common false positives
                    if match in ['x', 'X', ' ', '']:
                        continue
                    issues.append({
                        'line': line_num,
                        'type': issue_type,
                        'match': match if isinstance(match, str) else str(match),
                    })

    return issues


def main():
    # Read hook input from stdin
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        return

    tool_name = data.get("tool_name", "")
    tool_input = data.get("tool_input", {})

    # Process both Edit and Write tools
    if tool_name not in ("Edit", "Write"):
        return

    file_path = tool_input.get("file_path", "")
    if not file_path or not should_validate(file_path):
        return

    # Get the content to check
    content = None

    if tool_name == "Write":
        content = tool_input.get("content", "")
    elif tool_name == "Edit":
        # For Edit, we need to read the file to get current content
        # Since we're a post-hook, the edit has already been applied
        project_dir = os.environ.get("CLAUDE_PROJECT_DIR", "")
        if project_dir and not os.path.isabs(file_path):
            full_path = os.path.join(project_dir, file_path)
        else:
            full_path = file_path

        try:
            with open(full_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except (IOError, OSError):
            return

    if not content:
        return

    # Check for placeholders
    issues = check_for_placeholders(content)

    if issues:
        # Limit to first 5 issues to avoid overwhelming output
        shown_issues = issues[:5]
        remaining = len(issues) - 5

        filename = os.path.basename(file_path)

        # Build message
        msg_parts = [f"Placeholder check: {len(issues)} unfilled placeholder(s) in {filename}:"]

        for issue in shown_issues:
            msg_parts.append(f"  Line {issue['line']}: {issue['type']}")

        if remaining > 0:
            msg_parts.append(f"  ... and {remaining} more")

        msg_parts.append("")
        msg_parts.append("Run `/kit-tools:validate-seeding` for full validation.")

        print(json.dumps({"message": "\n".join(msg_parts)}))


if __name__ == "__main__":
    main()
