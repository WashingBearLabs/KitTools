#!/usr/bin/env python3
"""
detect_phase_completion.py - Detects checkbox completions in PRDs and roadmap files.

Trigger: PostToolUse (Edit|Write)

When a checkbox is marked complete (- [ ] → - [x]) in:
- kit_tools/prd/*.md (PRD acceptance criteria)
- kit_tools/roadmap/*_TODO.md (milestone tasks)

Outputs an advisory message suggesting to run /kit-tools:validate-phase.
"""
import json
import re
import sys


def main():
    # Read hook input from stdin
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        return

    tool_name = data.get("tool_name", "")
    tool_input = data.get("tool_input", {})

    # Only process Edit tool calls (Write doesn't have old_string/new_string)
    if tool_name != "Edit":
        return

    file_path = tool_input.get("file_path", "")
    if not file_path:
        return

    # Determine file type
    is_prd = "kit_tools/prd/" in file_path and file_path.endswith(".md") and "/archive/" not in file_path
    is_roadmap = "kit_tools/roadmap/" in file_path and (
        file_path.endswith("_TODO.md") or file_path.endswith("BACKLOG.md")
    )

    if not is_prd and not is_roadmap:
        return

    old_string = tool_input.get("old_string", "")
    new_string = tool_input.get("new_string", "")

    if not old_string or not new_string:
        return

    # Count unchecked boxes in old vs new to detect completions
    old_unchecked = len(re.findall(r"- \[ \]", old_string))
    new_unchecked = len(re.findall(r"- \[ \]", new_string))
    new_checked = len(re.findall(r"- \[x\]", new_string, re.IGNORECASE))

    # Only fire when checkboxes are being marked complete
    # (old has unchecked boxes, new has fewer unchecked or more checked)
    if old_unchecked > 0 and (new_unchecked < old_unchecked or new_checked > 0):
        # Extract filename for the message
        filename = file_path.split("/")[-1]
        completed_count = old_unchecked - new_unchecked

        if is_prd:
            # PRD acceptance criteria completed
            message = f"Acceptance criteria completed in {filename}."
            if completed_count > 0:
                message = f"{completed_count} acceptance criteria completed in {filename}."
            message += " Consider running `/kit-tools:validate-phase` to review changes."
        else:
            # Roadmap TODO task completed
            message = f"Task(s) completed in {filename}."
            if completed_count > 0:
                message = f"{completed_count} task(s) completed in {filename}."
            message += " Consider running `/kit-tools:validate-phase` to review changes."

        print(json.dumps({"message": message}))


if __name__ == "__main__":
    main()
