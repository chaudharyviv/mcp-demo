"""
Demo chip prompts (docs/spec.md §5), in presentation order. Single source for app.py and tests.
"""
from typing import List, Tuple

# (chip_id, button label, prompt sent to the agent)
DEMO_CHIPS: List[Tuple[str, str, str]] = [
    ("1", "1 · Docs", "How do I restrict public network access to an Azure Storage account? Give me the key steps and the official doc link."),
    ("2", "2 · GitHub", "What's been happening in our demo repo? Summarise the last 3 commits and tell me if there are any open issues or pull requests."),
    ("3a", "3a · Health", "How healthy is our storage estate? Anything I should worry about?"),
    ("3b", "3b · Resize", "Grow the payments database volume by 200 GB."),
    ("3c", "3c · Approve", "Change number is CHG0012345."),
]
