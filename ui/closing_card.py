"""
Closing takeaways card rendered for the 'Wrap up' chip.
Talking points are verbatim from docs/plan.md §5 ("Closing card talking points").
"""
import streamlit as st

TAKEAWAYS = [
    "The ONTAP tools mirror the public ONTAP REST API structure, so connecting a real cluster is an implementation step, not a redesign.",
    "Read-only by default; any change is gated by a change number and shown as a plan first.",
    "Every tool call is visible and logged.",
    "The agent layer is model-agnostic; the same MCP server works in any MCP client.",
    "No production system or data was needed to build or demo this.",
]

def render_closing_card():
    st.markdown("### 🎯 Takeaways\n\n" + "\n".join(f"- {point}" for point in TAKEAWAYS))
