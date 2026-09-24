"""
Sidebar UI component displaying connected systems status, active model, data badge, and presenter tools.
"""
import streamlit as st
from typing import Dict, Any

def short_description(text: str, limit: int = 90) -> str:
    """First line of a tool description, trimmed so remote servers' long descriptions fit the sidebar."""
    first = text.strip().splitlines()[0] if text.strip() else ""
    return first if len(first) <= limit else first[:limit - 1].rstrip() + "…"

def render_sidebar(servers_status: Dict[str, Any], on_reset_click) -> Dict[str, Any]:
    with st.sidebar:
        st.title("MCP Demo Control")
        st.caption("Model Context Protocol Live Demo")

        st.subheader("Connected Systems")
        for server_name, display_title in [("learn", "Microsoft Learn"), ("github", "GitHub"), ("ontap", "Mock ONTAP Storage")]:
            status_info = servers_status.get(server_name, {"status": "offline", "tools": []})
            is_online = status_info.get("status") == "online"
            tools = status_info.get("tools", [])
            dot = "🟢" if is_online else "🔴"
            # Collapsed by default so the audience sees status first; expand to show the discovered tools
            tool_label = f"{len(tools)} tool{'s' if len(tools) != 1 else ''}"
            with st.expander(f"{dot} **{display_title}** · {tool_label}", expanded=False):
                if not tools:
                    st.caption("Not connected — no tools available.")
                for tool in tools:
                    st.markdown(f"`{tool['name']}`")
                    if tool.get("description"):
                        st.caption(short_description(tool["description"]))

        st.markdown("---")
        st.markdown("**Active Model:** `OpenAI GPT-4o mini`")
        st.markdown("🔒 **Governance:** Guarded Dry-Run Only")

        st.markdown("""
        <div style="background-color: #1E293B; border: 1px solid #334155; padding: 8px 12px; border-radius: 6px; text-align: center; margin-top: 10px;">
            <small style="color: #94A3B8;">⚠️ <b>Demo data</b> — no real systems</small>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("---")

        with st.expander("🛠️ Presenter Settings", expanded=False):
            replay_mode = st.checkbox("Enable Replay Mode", value=st.session_state.get("replay_mode", False))
            st.session_state["replay_mode"] = replay_mode

            presenter_mode = st.checkbox("Presenter Mode (Hide Raw JSON)", value=st.session_state.get("presenter_mode", True))
            st.session_state["presenter_mode"] = presenter_mode

            if st.button("🔄 Reset Demo", use_container_width=True):
                on_reset_click()

    return {
        "replay_mode": st.session_state.get("replay_mode", False),
        "presenter_mode": st.session_state.get("presenter_mode", True)
    }
