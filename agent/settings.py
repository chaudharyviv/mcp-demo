"""
Secret/config lookup: environment variables first, then Streamlit secrets (AGENTS.md §3.7).
"""
import os
from typing import Optional


def get_secret(name: str) -> Optional[str]:
    value = os.environ.get(name)
    if value:
        return value
    try:
        import streamlit as st
        return st.secrets.get(name)
    except Exception:
        return None
