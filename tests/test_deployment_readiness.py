import sys
from pathlib import Path
from agent.mcp_clients import MCPClientManager

def test_streamlit_config_exists():
    """Verifies .streamlit/config.toml exists and uses only valid Streamlit options."""
    config_path = Path(__file__).parent.parent / ".streamlit" / "config.toml"
    assert config_path.exists()
    content = config_path.read_text(encoding="utf-8")
    assert "[layout]" not in content  # not a Streamlit option (CODE_REVIEW M11)

def test_app_uses_wide_layout_and_larger_font():
    """Wide layout is set in app.py (spec UI-1); CODE_REVIEW L3."""
    app_source = (Path(__file__).parent.parent / "app.py").read_text(encoding="utf-8")
    assert 'layout="wide"' in app_source
    assert "font-size" in app_source

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
