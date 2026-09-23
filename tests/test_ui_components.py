import pytest
from ui.landing import render_landing_panel
from ui.sidebar import render_sidebar
from ui.closing_card import render_closing_card
from ui.trace import render_trace_log

def test_ui_imports_and_structure():
    """Verifies that all UI modules are importable and callables exist."""
    assert callable(render_landing_panel)
    assert callable(render_sidebar)
    assert callable(render_closing_card)
    assert callable(render_trace_log)

def test_prompt_chips_spec_mapping():
    """Verifies prompt text matches spec.md §5."""
    prompts = {
        "1": "How do I restrict public network access to an Azure Storage account? Give me the key steps and the official doc link.",
        "2": "Summarise the open issues in our demo repo and tell me which one looks most urgent.",
        "3a": "How healthy is our storage estate? Anything I should worry about?",
        "3b": "Grow the payments database volume by 200 GB.",
        "3c": "Change number is CHG0012345."
    }
    assert "Azure Storage" in prompts["1"]
    assert "open issues" in prompts["2"]
    assert "storage estate" in prompts["3a"]
    assert "payments database" in prompts["3b"]
    assert "CHG0012345" in prompts["3c"]
