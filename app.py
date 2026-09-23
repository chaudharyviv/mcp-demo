"""
Main Streamlit Entry Point for MCP Live Demo.
"""
import asyncio
import os
import time
import streamlit as st
from agent.mcp_clients import MCPClientManager
from agent.loop import AgentLoop
from replay.manager import ReplayManager
from ui.landing import render_landing_panel
from ui.sidebar import render_sidebar
from ui.closing_card import render_closing_card
from ui.trace import LiveTraceWriter, render_trace_log

st.set_page_config(
    page_title="MCP Live Demo",
    page_icon="🔌",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Larger base font for screen share (spec UI-1); Streamlit sizes text in rem, so this scales it all
st.markdown("<style>html { font-size: 18px; }</style>", unsafe_allow_html=True)

# Replay pacing (spec UI-9): short "thinking" pause, then each step for its recorded duration, capped
REPLAY_THINK_SECONDS = 0.8
REPLAY_MAX_STEP_SECONDS = 1.5

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
    # Re-check server connectivity so a server that was down at cold start can turn green
    get_cached_mcp_manager.clear()
    st.rerun()

# Helper: Replay fallback after an LLM failure (button callback)
def append_recorded_answer(replay_data):
    st.session_state.messages.append({
        "role": "assistant",
        "content": replay_data["content"],
        "trace": replay_data["trace"]
    })

# Cache Tool Discovery for Sidebar
# ttl: a server that was down at startup is retried after 5 minutes rather than staying red all demo
@st.cache_resource(show_spinner="Connecting to MCP Servers...", ttl=300)
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

            # Check Replay Mode
            replay_data = None
            if settings["replay_mode"]:
                replay_data = ReplayManager.get_replay_by_prompt(active_prompt)

            if replay_data:
                answer_content = replay_data["content"]
                current_trace = replay_data["trace"]
                status = st.status("Working via MCP…", expanded=True)
                live_writer = LiveTraceWriter(status)
                time.sleep(REPLAY_THINK_SECONDS)
                for evt in current_trace:
                    if evt.get("event") in ("tool_finished", "tool_failed"):
                        # Hold the "running" line for the recorded call duration
                        time.sleep(min(evt.get("duration", 0.5), REPLAY_MAX_STEP_SECONDS))
                    live_writer(evt)
                status.update(label="Done", state="complete", expanded=False)
                st.markdown(answer_content)
                render_trace_log(current_trace, presenter_mode=settings["presenter_mode"])

                st.session_state.messages.append({
                    "role": "assistant",
                    "content": answer_content,
                    "trace": current_trace
                })
            else:
                # Steps stream into the status box as each tool call starts and finishes (spec UI-5)
                status = st.status("Working via MCP…", expanded=True)
                live_writer = LiveTraceWriter(status)
                def trace_cb(evt):
                    current_trace.append(evt)
                    live_writer(evt)

                try:
                    agent = AgentLoop(mcp_manager=mcp_manager)
                    agent_messages = [
                        {"role": m["role"], "content": m["content"]}
                        for m in st.session_state.messages
                        if m.get("role") in ("user", "assistant")
                    ]
                    result = asyncio.run(agent.run_turn(agent_messages, trace_callback=trace_cb))
                    answer_content = result.get("content", "")
                    status.update(label="Done", state="complete", expanded=False)

                    st.markdown(answer_content)
                    render_trace_log(current_trace, presenter_mode=settings["presenter_mode"])

                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": answer_content,
                        "trace": current_trace
                    })
                except Exception as e:
                    status.update(label="Failed", state="error", expanded=False)
                    st.error("The AI service didn't respond in time. You can show the recorded answer instead.")
                    st.caption(f"Details: {e}")
                    # Offer Replay Fallback Button. on_click runs on the next rerun even though
                    # this except branch won't execute again, so the answer lands in chat history.
                    fallback_replay = ReplayManager.get_replay_by_prompt(active_prompt)
                    if fallback_replay:
                        st.button(
                            "▶️ Show Recorded Answer (Replay Fallback)",
                            on_click=append_recorded_answer,
                            args=(fallback_replay,)
                        )
