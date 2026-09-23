"""
Main Streamlit Entry Point for MCP Live Demo.
"""
import asyncio
import os
import streamlit as st
from agent.mcp_clients import MCPClientManager
from agent.loop import AgentLoop
from replay.manager import ReplayManager
from ui.landing import render_landing_panel
from ui.sidebar import render_sidebar
from ui.closing_card import render_closing_card
from ui.trace import render_trace_log

st.set_page_config(
    page_title="MCP Live Demo",
    page_icon="🔌",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize Session State
if "messages" not in st.session_state:
    st.session_state.messages = []
if "trace" not in st.session_state:
    st.session_state.trace = []
if "demo_started" not in st.session_state:
    st.session_state.demo_started = False
if "presenter_mode" not in st.session_state:
    st.session_state.presenter_mode = True
if "replay_mode" not in st.session_state:
    st.session_state.replay_mode = False

# Helper: Reset Handler
def reset_demo():
    st.session_state.messages = []
    st.session_state.trace = []
    st.session_state.demo_started = False
    st.rerun()

# Cache Tool Discovery for Sidebar
@st.cache_resource(show_spinner="Connecting to MCP Servers...")
def get_cached_mcp_manager():
    manager = MCPClientManager()
    discovery = asyncio.run(manager.discover_all_tools())
    return manager, discovery

mcp_manager, discovery_data = get_cached_mcp_manager()
servers_status = discovery_data.get("servers", {})

# Render Sidebar
settings = render_sidebar(servers_status, on_reset_click=reset_demo)

# Main Application Layout
st.title("🔌 MCP Live Demo")

if not st.session_state.demo_started:
    render_landing_panel(on_start_click=lambda: st.session_state.update(demo_started=True))
else:
    # Chips Row
    st.markdown("### Demo Prompts")
    col1, col2, col3, col4, col5, col6 = st.columns(6)

    selected_prompt = None
    chip_id = None
    is_wrap_up = False

    with col1:
        if st.button("1 · Docs", use_container_width=True):
            selected_prompt = "How do I restrict public network access to an Azure Storage account? Give me the key steps and the official doc link."
            chip_id = "1"
    with col2:
        if st.button("2 · GitHub", use_container_width=True):
            selected_prompt = "Summarise the open issues in our demo repo and tell me which one looks most urgent."
            chip_id = "2"
    with col3:
        if st.button("3a · Health", use_container_width=True):
            selected_prompt = "How healthy is our storage estate? Anything I should worry about?"
            chip_id = "3a"
    with col4:
        if st.button("3b · Resize", use_container_width=True):
            selected_prompt = "Grow the payments database volume by 200 GB."
            chip_id = "3b"
    with col5:
        if st.button("3c · Approve", use_container_width=True):
            selected_prompt = "Change number is CHG0012345."
            chip_id = "3c"
    with col6:
        if st.button("Wrap up", use_container_width=True):
            is_wrap_up = True

    # Render Chat History
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if msg.get("role") == "assistant" and "trace" in msg:
                render_trace_log(msg["trace"], presenter_mode=settings["presenter_mode"])

    # Render Wrap Up Card
    if is_wrap_up:
        render_closing_card()

    # Chat Input or Selected Prompt Handler
    user_input = st.chat_input("Type your message or click a prompt chip above...")
    active_prompt = selected_prompt or user_input

    if active_prompt:
        st.session_state.messages.append({"role": "user", "content": active_prompt})
        with st.chat_message("user"):
            st.markdown(active_prompt)

        with st.chat_message("assistant"):
            current_trace = []
            def trace_cb(evt):
                current_trace.append(evt)

            # Check Replay Mode
            replay_data = None
            if settings["replay_mode"]:
                replay_data = ReplayManager.get_replay_by_prompt(active_prompt)

            if replay_data:
                answer_content = replay_data["content"]
                current_trace = replay_data["trace"]
                st.markdown(answer_content)
                render_trace_log(current_trace, presenter_mode=settings["presenter_mode"])

                st.session_state.messages.append({
                    "role": "assistant",
                    "content": answer_content,
                    "trace": current_trace
                })
            else:
                with st.spinner("Executing agent turn via MCP..."):
                    try:
                        agent = AgentLoop(mcp_manager=mcp_manager)
                        agent_messages = [
                            {"role": m["role"], "content": m["content"]}
                            for m in st.session_state.messages
                            if m.get("role") in ("user", "assistant")
                        ]
                        result = asyncio.run(agent.run_turn(agent_messages, trace_callback=trace_cb))
                        answer_content = result.get("content", "")

                        st.markdown(answer_content)
                        render_trace_log(current_trace, presenter_mode=settings["presenter_mode"])

                        st.session_state.messages.append({
                            "role": "assistant",
                            "content": answer_content,
                            "trace": current_trace
                        })
                    except Exception as e:
                        st.error(f"Error executing agent turn: {str(e)}")
                        # Offer Replay Fallback Button
                        fallback_replay = ReplayManager.get_replay_by_prompt(active_prompt)
                        if fallback_replay and st.button("▶️ Show Recorded Answer (Replay Fallback)"):
                            st.markdown(fallback_replay["content"])
                            render_trace_log(fallback_replay["trace"], presenter_mode=settings["presenter_mode"])
                            st.session_state.messages.append({
                                "role": "assistant",
                                "content": fallback_replay["content"],
                                "trace": fallback_replay["trace"]
                            })
