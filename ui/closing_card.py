"""
Closing takeaways card rendered for the 'Wrap up' chip.
"""
import streamlit as st

def render_closing_card():
    st.markdown("""
    ### 🎯 Demo Takeaways & Key Highlights

    - **Standardized Connectivity**: One universal protocol (MCP) connecting public APIs, dev tools, and enterprise storage.
    - **API Parallelism**: ONTAP MCP tools mirror NetApp's public REST API structure; swapping to a live cluster requires zero agent prompt redesign.
    - **In-Tool Governance**: Safety guardrails (such as mandatory Change Request numbers and dry-run execution enforcement) live **inside the tool**, not just in system prompts.
    - **Total Observability**: Full trace transparency over tool selection, arguments, status, and sub-second execution duration.
    - **100% Synthetic Data**: Enterprise storage operations demonstrated safely without touching production environments.
    """)
