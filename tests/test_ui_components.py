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

def test_start_demo_single_click_shows_chips():
    """One click on Start Demo must show the chip row immediately (CODE_REVIEW H5)."""
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file("app.py", default_timeout=90).run()
    assert not at.exception
    at.button[[b.label for b in at.button].index("🚀 Start Demo")].click().run()
    labels = [b.label for b in at.button]
    assert "3a · Health" in labels and "🚀 Start Demo" not in labels

def test_ontap_answer_shows_synthetic_caption():
    """Answers that used ONTAP tools are labelled synthetic in the UI (CODE_REVIEW N2)."""
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_string(
        "from ui.trace import render_trace_log\n"
        "render_trace_log([{'event': 'tool_finished', 'server': 'ontap', 'tool': 'ontap_aggr_show', 'duration': 0.1}])\n"
        "render_trace_log([{'event': 'tool_finished', 'server': 'learn', 'tool': 'learn_x', 'duration': 0.1}])\n"
    ).run()
    captions = [c.value for c in at.caption if "synthetic demo data" in c.value]
    assert len(captions) == 1

def test_live_trace_writer_replaces_running_line():
    """Streaming trace shows 'running' then replaces it with the ✓ line (spec UI-5, CODE_REVIEW M6)."""
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_string(
        "import streamlit as st\n"
        "from ui.trace import LiveTraceWriter\n"
        "w = LiveTraceWriter(st.container())\n"
        "w({'event': 'tool_started', 'server': 'ontap', 'tool': 'ontap_aggr_show', 'args': {}})\n"
        "w({'event': 'tool_finished', 'server': 'ontap', 'tool': 'ontap_aggr_show', 'duration': 0.3})\n"
    ).run()
    lines = [m.value for m in at.markdown]
    assert lines == ["✓ `Mock ONTAP` → `ontap_aggr_show` · 0.3 s"]

def test_trace_log_counts_calls_not_events():
    """Started+finished pair renders as one step, not two (CODE_REVIEW M6)."""
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_string(
        "from ui.trace import render_trace_log\n"
        "render_trace_log([\n"
        "  {'event': 'tool_started', 'server': 'learn', 'tool': 'learn_x', 'args': {'q': 1}},\n"
        "  {'event': 'tool_finished', 'server': 'learn', 'tool': 'learn_x', 'duration': 0.2},\n"
        "])\n"
    ).run()
    assert at.expander[0].label == "🔍 Tool Call Trace (1 step)"
    assert not any("running" in m.value for m in at.markdown)

def test_reset_demo_rechecks_server_connectivity(monkeypatch):
    """Reset clears the cached discovery so servers are re-checked (CODE_REVIEW M8)."""
    import streamlit as st
    from streamlit.testing.v1 import AppTest
    from agent.mcp_clients import MCPClientManager
    calls = []
    async def fake_discovery(self):
        calls.append(1)
        return {"servers": {}, "all_tools": []}
    monkeypatch.setattr(MCPClientManager, "discover_all_tools", fake_discovery)
    st.cache_resource.clear()
    at = AppTest.from_file("app.py", default_timeout=60).run()
    assert len(calls) == 1
    at.button[[b.label for b in at.button].index("🔄 Reset Demo")].click().run()
    assert len(calls) == 2
    st.cache_resource.clear()
