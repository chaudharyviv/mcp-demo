"""
Sidebar UI component displaying connected systems status, active model, data badge, and presenter tools.
"""
import streamlit as st
from typing import Dict, Any

def render_sidebar(servers_status: Dict[str, Any], on_reset_click) -> Dict[str, Any]:
    with st.sidebar:
        st.title("MCP Demo Control")
        st.caption("Model Context Protocol Live Demo")

        st.subheader("Connected Systems")
        for server_name, display_title in [("learn", "Microsoft Learn"), ("github", "GitHub"), ("ontap", "Mock ONTAP Storage")]:
            status_info = servers_status.get(server_name, {"status": "offline", "tools": []})
            is_online = status_info.get("status") == "online"
            tool_count = len(status_info.get("tools", []))
            dot = "🟢" if is_online else "🔴"
            st.markdown(f"{dot} **{display_title}** `{tool_count} tools`")

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
