"""
Landing panel component displayed before first chat interaction.
"""
import streamlit as st

def render_landing_panel(on_start_click):
    st.markdown("""
    ## One AI assistant, plugged into three systems through one universal connector
    ### Our storage estate included — with guardrails.
    """)

    col1, col2, col3 = st.columns(3)

    with col1:
        st.info("""
        **1 · Microsoft Learn**
        - Transport: Streamable HTTP
        - Status: Public / No Auth
        - Capability: Documentation & Guides
        """)

    with col2:
        st.info("""
        **2 · GitHub**
        - Transport: Streamable HTTP
        - Status: Scoped PAT
        - Capability: Repositories & Issues
        """)

    with col3:
        st.success("""
        **3 · Mock ONTAP Storage**
        - Transport: FastMCP Stdio Subprocess
        - Status: Synthetic Data
        - Capability: Read-only & Guarded Dry-run
        """)

    st.write("")
    if st.button("🚀 Start Demo", type="primary", use_container_width=True):
        on_start_click()
