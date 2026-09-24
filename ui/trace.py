"""
Trace rendering component for tool execution logs.
"""
import streamlit as st
from typing import Dict, Any, List, Optional

SERVER_DISPLAY_NAMES = {
    "ontap": "Mock ONTAP",
    "learn": "Microsoft Learn",
    "github": "GitHub"
}

# design.md §4.2: public servers in one colour, the ONTAP server in an accent colour
# (matches the landing cards: st.info is blue, st.success is green)
SERVER_COLORS = {
    "ontap": "green",
    "learn": "blue",
    "github": "blue"
}

STEP_EVENTS = ("tool_finished", "tool_failed")

def server_label(server_key: str) -> str:
    """Server name in its colour, as Streamlit Markdown, e.g. ":green[**Mock ONTAP**]"."""
    name = SERVER_DISPLAY_NAMES.get(server_key, server_key)
    color = SERVER_COLORS.get(server_key)
    return f":{color}[**{name}**]" if color else f"**{name}**"

def format_step(evt: Dict[str, Any]) -> str:
    """One trace line, e.g. "✓ :green[**Mock ONTAP**] → `ontap_aggr_show` · 0.3 s" (design.md §4.3)."""
    server = server_label(evt.get("server", "ontap"))
    tool_name = evt.get("tool", "tool")
    if evt.get("event") == "tool_started":
        return f"⏱️ {server} → `{tool_name}` … running"
    mark = "✓" if evt.get("event") == "tool_finished" else "✗"
    return f"{mark} {server} → `{tool_name}` · {evt.get('duration', 0.0)} s"

WORKING_LABEL = "Working via MCP…"

class LiveTraceWriter:
    """Trace callback that streams steps into a container: a "running" line, replaced when the call ends.

    If a status box is given, its header names the step in progress so a slow call reads as deliberate.
    """

    def __init__(self, container, status: Optional[Any] = None):
        self.container = container
        self.status = status
        self._pending: Optional[Any] = None

    def __call__(self, evt: Dict[str, Any]) -> None:
        event_type = evt.get("event")
        if event_type == "tool_started":
            self._pending = self.container.empty()
            self._pending.markdown(format_step(evt))
            if self.status is not None:
                name = SERVER_DISPLAY_NAMES.get(evt.get("server", ""), evt.get("server", ""))
                self.status.update(label=f"Calling {name} → `{evt.get('tool', 'tool')}`…")
        elif event_type in STEP_EVENTS:
            slot = self._pending or self.container.empty()
            slot.markdown(format_step(evt))
            self._pending = None
            if self.status is not None:
                self.status.update(label=WORKING_LABEL)

def render_trace_log(trace_events: List[Dict[str, Any]], presenter_mode: bool = True):
    if not trace_events:
        return

    # Label ONTAP-backed answers deterministically rather than relying on the model to say it
    if any(evt.get("server") == "ontap" for evt in trace_events):
        st.caption("🧪 Storage data above is synthetic demo data — no real systems.")

    # One line per completed call; arguments come from the preceding tool_started event
    steps = []
    last_args = None
    for evt in trace_events:
        if evt.get("event") == "tool_started":
            last_args = evt.get("args")
        elif evt.get("event") in STEP_EVENTS:
            steps.append((evt, evt.get("args", last_args)))
            last_args = None
    if not steps:
        return

    # Title names the systems used, so the collapsed trace still tells the "three systems" story
    servers = list(dict.fromkeys(SERVER_DISPLAY_NAMES.get(evt.get("server", ""), evt.get("server", "")) for evt, _ in steps))
    title = f"🔍 Tool Call Trace · {len(steps)} step{'s' if len(steps) != 1 else ''} ({', '.join(servers)})"
    with st.expander(title, expanded=True):
        for evt, args in steps:
            st.write(format_step(evt))
            if not presenter_mode and args is not None:
                st.caption(f"Arguments: `{args}`")
            if not presenter_mode and ("result" in evt or "error" in evt):
                st.code(evt.get("result") or evt.get("error"), language="json")
