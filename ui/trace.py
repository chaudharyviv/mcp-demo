"""
Trace rendering component for tool execution logs.
"""
import streamlit as st
from typing import Dict, Any, List

SERVER_DISPLAY_NAMES = {
    "ontap": "Mock ONTAP",
    "learn": "Microsoft Learn",
    "github": "GitHub"
}

def render_trace_log(trace_events: List[Dict[str, Any]], presenter_mode: bool = True):
    if not trace_events:
        return

    with st.expander(f"🔍 Tool Call Trace ({len(trace_events)} step{'s' if len(trace_events)>1 else ''})", expanded=True):
        for evt in trace_events:
            event_type = evt.get("event")
            if event_type in ("tool_started", "tool_finished", "tool_failed"):
                server_key = evt.get("server", "ontap")
                server_name = SERVER_DISPLAY_NAMES.get(server_key, server_key)
                tool_name = evt.get("tool", "tool")

                if event_type == "tool_started":
                    st.write(f"⏱️ `{server_name}` → `{tool_name}` ... running")
                elif event_type == "tool_finished":
                    duration = evt.get("duration", 0.0)
                    st.write(f"✓ `{server_name}` → `{tool_name}` · {duration}s")
                elif event_type == "tool_failed":
                    duration = evt.get("duration", 0.0)
                    st.write(f"✗ `{server_name}` → `{tool_name}` · {duration}s (Error)")

                if not presenter_mode and "args" in evt:
                    st.caption(f"Arguments: `{evt['args']}`")
                if not presenter_mode and "result" in evt:
                    st.code(evt["result"], language="json")
