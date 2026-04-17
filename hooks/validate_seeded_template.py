#!/usr/bin/env python3
"""
validate_seeded_template.py - Quick placeholder check after template edits.

Trigger: PostToolUse (Edit|Write)

When a template file in kit_tools/ is edited, performs a quick check for
common unfilled placeholder patterns and warns immediately if any remain.
This provides fast feedback during seeding without running the full validator.

Placeholder detection logic is shared with validate_setup.py via _placeholders.py
so both hooks see the same coverage.
"""
import json
import os
import sys

from _placeholders import find_placeholders, should_validate_path


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
    if not file_path or not should_validate_path(file_path):
        return

    # Get the content to check
    content = None

    if tool_name == "Write":
        content = tool_input.get("content", "")
    elif tool_name == "Edit":
        # For Edit, we need to read the file to get current content.
        # Since we're a post-hook, the edit has already been applied.
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

    issues = find_placeholders(content)

    if issues:
        # Limit to first 5 issues to avoid overwhelming output
        shown_issues = issues[:5]
        remaining = len(issues) - 5

        filename = os.path.basename(file_path)

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
