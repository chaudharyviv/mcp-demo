import sys
from pathlib import Path
import pytest
from agent.mcp_clients import MCPClientManager

def test_streamlit_config_exists():
    """Verifies .streamlit/config.toml exists and has wide layout."""
    config_path = Path(__file__).parent.parent / ".streamlit" / "config.toml"
    assert config_path.exists()
    content = config_path.read_text(encoding="utf-8")
    assert "wide = true" in content

def test_secrets_example_exists():
    """Verifies .streamlit/secrets.toml.example exists."""
    example_path = Path(__file__).parent.parent / ".streamlit" / "secrets.toml.example"
    assert example_path.exists()
    content = example_path.read_text(encoding="utf-8")
    assert "OPENAI_API_KEY" in content
    assert "GITHUB_PAT" in content

def test_gitignore_contains_secrets():
    """Verifies .gitignore ignores secrets.toml per AGENTS.md §3 rule 7."""
    gitignore_path = Path(__file__).parent.parent / ".gitignore"
    assert gitignore_path.exists()
    content = gitignore_path.read_text(encoding="utf-8")
    assert ".streamlit/secrets.toml" in content

def test_sys_executable_subprocess_command():
    """Verifies ONTAP server runs with sys.executable per AGENTS.md §4."""
    manager = MCPClientManager()
    ontap_cfg = manager.servers_config.get("ontap", {})
    assert ontap_cfg.get("type") == "stdio"
    assert ontap_cfg.get("command") == sys.executable
