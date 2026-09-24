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

def test_chip_prompts_match_spec():
    """Every chip prompt used by app.py appears verbatim in docs/spec.md §5, in order (CODE_REVIEW L1)."""
    from pathlib import Path
    from ui.chips import DEMO_CHIPS
    spec = (Path(__file__).parent.parent / "docs" / "spec.md").read_text(encoding="utf-8")
    positions = [spec.index(f"| `{label}` | \"{prompt}\"") for _, label, prompt in DEMO_CHIPS]
    assert positions == sorted(positions)

def test_chip_prompts_map_to_their_replays():
    from ui.chips import DEMO_CHIPS
    from replay.manager import ReplayManager
    for chip_id, _, prompt in DEMO_CHIPS:
        assert ReplayManager.get_replay_by_prompt(prompt)["chip_id"] == chip_id

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
    assert lines == ["✓ :green[**Mock ONTAP**] → `ontap_aggr_show` · 0.3 s"]

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
    assert at.expander[0].label == "🔍 Tool Call Trace · 1 step (Microsoft Learn)"
    assert not any("running" in m.value for m in at.markdown)

def test_reset_demo_rechecks_server_connectivity(monkeypatch):
    """Reset clears the cached discovery so servers are re-checked (CODE_REVIEW M8)."""
    import streamlit as st
    from streamlit.testing.v1 import AppTest
    from agent.mcp_clients import MCPClientManager
    calls = []
    async def fake_discovery(self, include_catalog=False):
        calls.append(1)
        return {"servers": {}, "all_tools": []}
    monkeypatch.setattr(MCPClientManager, "discover_all_tools", fake_discovery)
    st.cache_resource.clear()
    at = AppTest.from_file("app.py", default_timeout=60).run()
    assert len(calls) == 1
    at.button[[b.label for b in at.button].index("🔄 Reset Demo")].click().run()
    assert len(calls) == 2
    st.cache_resource.clear()

def test_closing_card_matches_plan_talking_points():
    """Closing card shows exactly the plan.md §5 talking points (CODE_REVIEW L8)."""
    from pathlib import Path
    from ui.closing_card import TAKEAWAYS
    plan = (Path(__file__).parent.parent / "docs" / "plan.md").read_text(encoding="utf-8")
    section = plan.split("### Closing card talking points", 1)[1].split("\n## ", 1)[0]
    plan_points = [line[2:].strip() for line in section.splitlines() if line.startswith("- ")]
    assert TAKEAWAYS == plan_points

def test_sidebar_lists_tools_per_server():
    """Sidebar shows each server's discovered tools in a collapsed expander; offline shows none."""
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_string(
        "from ui.sidebar import render_sidebar\n"
        "render_sidebar({\n"
        "  'learn': {'status': 'online', 'tools': [{'name': 'learn_microsoft_docs_search', 'description': 'Search docs.\\nMore detail.'}]},\n"
        "  'ontap': {'status': 'online', 'tools': [{'name': 'ontap_vol_resize', 'description': 'Plans a volume resize (dry run only).'}]},\n"
        "  'github': {'status': 'offline', 'tools': []},\n"
        "}, on_reset_click=lambda: None)\n"
    ).run()
    labels = [e.label for e in at.expander]
    assert "🟢 :blue[**Microsoft Learn**] · 1 tool" in labels
    assert "🔴 :blue[**GitHub**] · 0 tools" in labels
    markdown = [m.value for m in at.sidebar.markdown]
    assert "`learn_microsoft_docs_search`" in markdown and "`ontap_vol_resize`" in markdown
    captions = [c.value for c in at.caption]
    assert "Search docs." in captions and "Not connected — no tools available." in captions

def test_sidebar_shows_blocked_catalog_tools():
    """With a catalog, the sidebar shows enabled vs total and lists blocked (write) tools."""
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_string(
        "from ui.sidebar import render_sidebar\n"
        "render_sidebar({'github': {'status': 'online',\n"
        "  'tools': [{'name': 'github_list_issues', 'description': 'List issues'}],\n"
        "  'catalog': [{'name': 'github_list_issues', 'description': 'List issues', 'enabled': True},\n"
        "              {'name': 'github_merge_pull_request', 'description': 'Merge', 'enabled': False}]}},\n"
        "  on_reset_click=lambda: None)\n"
    ).run()
    assert "🟢 :blue[**GitHub**] · 1 of 2 tools enabled (read-only)" in [e.label for e in at.expander]
    assert "**🔒 Blocked (1): not offered to the model**" in [m.value for m in at.markdown]
    assert "~~github_merge_pull_request~~" in [c.value for c in at.caption]

def test_chip_tooltips_show_full_prompt():
    """Hovering a chip shows the exact prompt it sends (owner request)."""
    from streamlit.testing.v1 import AppTest
    from ui.chips import DEMO_CHIPS
    at = AppTest.from_file("app.py", default_timeout=90).run()
    at.button[[b.label for b in at.button].index("🚀 Start Demo")].click().run()
    help_by_label = {b.label: b.help for b in at.button}
    for _, label, prompt in DEMO_CHIPS:
        assert help_by_label[label] == prompt
    assert "no AI call" in help_by_label["Wrap up"]

def test_trace_title_names_servers_in_order():
    """Collapsed trace title lists the systems used, once each, in order of use."""
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_string(
        "from ui.trace import render_trace_log\n"
        "render_trace_log([\n"
        "  {'event': 'tool_finished', 'server': 'ontap', 'tool': 'ontap_cluster_health_summary', 'duration': 0.2},\n"
        "  {'event': 'tool_finished', 'server': 'github', 'tool': 'github_list_issues', 'duration': 0.4},\n"
        "  {'event': 'tool_failed', 'server': 'ontap', 'tool': 'ontap_vol_show', 'duration': 0.1},\n"
        "])\n"
    ).run()
    assert at.expander[0].label == "🔍 Tool Call Trace · 3 steps (Mock ONTAP, GitHub)"

def test_status_header_names_current_step():
    """While a tool runs, the status header says which server/tool; afterwards it reverts."""
    from streamlit.testing.v1 import AppTest
    script = (
        "import streamlit as st\n"
        "from ui.trace import WORKING_LABEL, LiveTraceWriter\n"
        "status = st.status(WORKING_LABEL, expanded=True)\n"
        "w = LiveTraceWriter(status, status=status)\n"
        "w({'event': 'tool_started', 'server': 'ontap', 'tool': 'ontap_vol_resize', 'args': {}})\n"
    )
    at = AppTest.from_string(script).run()
    assert at.status[0].label == "Calling Mock ONTAP → `ontap_vol_resize`…"
    at = AppTest.from_string(script + "w({'event': 'tool_finished', 'server': 'ontap', 'tool': 'ontap_vol_resize', 'duration': 0.3})\n").run()
    assert at.status[0].label == "Working via MCP…"

def test_server_colours_match_landing_cards():
    """Public servers share one colour, ONTAP gets the accent (design.md §4.2)."""
    from ui.trace import SERVER_COLORS
    assert SERVER_COLORS["learn"] == SERVER_COLORS["github"] != SERVER_COLORS["ontap"]
