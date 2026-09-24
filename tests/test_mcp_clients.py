import pytest
from agent.mcp_clients import MCPClientManager

@pytest.mark.asyncio
async def test_ontap_stdio_discovery():
    """Tests tool discovery against local stdio ONTAP server."""
    manager = MCPClientManager()
    res = await manager.get_server_tools("ontap")
    assert res["status"] == "online"
    tool_names = [t["name"] for t in res["tools"]]
    assert "ontap_cluster_health_summary" in tool_names
    assert "ontap_aggr_show" in tool_names
    assert "ontap_vol_show" in tool_names
    assert "ontap_vol_resize" in tool_names

@pytest.mark.asyncio
async def test_ontap_tool_invocation_via_client():
    """Tests calling an ONTAP tool through MCPClientManager."""
    manager = MCPClientManager()
    result = await manager.call_tool("ontap", "ontap_cluster_health_summary", {})
    assert result["isError"] is False or result["isError"] is None
    content = result["content"]
    assert len(content) > 0

@pytest.mark.asyncio
async def test_unreachable_server_resilience():
    """Verifies that an unreachable server returns status offline without failing discover_all_tools."""
    manager = MCPClientManager()
    # Closed local port: fails fast and deterministically, no DNS or internet needed (CODE_REVIEW M17)
    manager.servers_config["learn"]["url"] = "http://127.0.0.1:9/mcp"

    discovery = await manager.discover_all_tools()
    assert discovery["servers"]["ontap"]["status"] == "online"
    assert discovery["servers"]["learn"]["status"] == "offline"
    assert len(discovery["all_tools"]) > 0

@pytest.mark.asyncio
async def test_learn_discovery_over_streamable_http():
    """Learn MCP is reachable over Streamable HTTP (spec.md §2.3, CODE_REVIEW H3). Requires network."""
    res = await MCPClientManager().get_server_tools("learn")
    assert res["status"] == "online", res["error"]
    assert any(t["original_name"] == "microsoft_docs_search" for t in res["tools"])

def _hanging_manager() -> MCPClientManager:
    """ONTAP entry pointed at a process that never speaks MCP, with a short timeout."""
    manager = MCPClientManager()
    manager.servers_config["ontap"]["args"] = ["-c", "import time; time.sleep(60)"]
    manager.timeout = 2.0
    return manager

@pytest.mark.asyncio
async def test_hung_server_discovery_times_out_as_offline():
    """A hung server is reported offline within the timeout (CODE_REVIEW M2)."""
    import time
    start = time.monotonic()
    res = await _hanging_manager().get_server_tools("ontap")
    assert res["status"] == "offline" and "Timed out" in res["error"]
    assert time.monotonic() - start < 15

@pytest.mark.asyncio
async def test_hung_server_tool_call_times_out():
    """A hung tool call raises TimeoutError instead of blocking the turn (CODE_REVIEW M2)."""
    with pytest.raises(TimeoutError):
        await _hanging_manager().call_tool("ontap", "ontap_cluster_health_summary", {})

@pytest.mark.asyncio
async def test_discovery_runs_servers_concurrently():
    """Two hung servers cost one timeout, not two (CODE_REVIEW M3)."""
    import sys
    import time
    manager = _hanging_manager()
    manager.servers_config["learn"] = {"type": "stdio", "command": sys.executable, "args": ["-c", "import time; time.sleep(60)"]}
    manager.servers_config["github"] = {"type": "stdio", "command": sys.executable, "args": ["-c", "import time; time.sleep(60)"]}
    start = time.monotonic()
    discovery = await manager.discover_all_tools()
    elapsed = time.monotonic() - start
    assert all(s["status"] == "offline" for s in discovery["servers"].values())
    assert elapsed < 2 * manager.timeout + 1, f"discovery looks serial ({elapsed:.1f}s)"

class _FakeTool:
    def __init__(self, name):
        self.name, self.description, self.inputSchema = name, f"{name} tool", {"type": "object", "properties": {}}

@pytest.mark.asyncio
async def test_github_model_gets_readonly_tools_catalog_marks_blocked(monkeypatch):
    """Model tools come from the read-only endpoint; catalog marks the rest blocked by set difference."""
    manager = MCPClientManager()
    cfg = manager.servers_config["github"]
    assert cfg["url"].endswith("/mcp/readonly") and cfg["catalog_url"].endswith("/mcp/")

    async def fake_list(self, server_name, url=None):
        full = ["list_issues", "get_me", "merge_pull_request", "delete_file"]
        return [_FakeTool(n) for n in (full if url == cfg["catalog_url"] else full[:2])]
    monkeypatch.setattr(MCPClientManager, "_list_tools", fake_list)

    res = await manager.get_server_tools("github", include_catalog=True)
    assert [t["name"] for t in res["tools"]] == ["github_list_issues", "github_get_me"]
    assert {t["name"]: t["enabled"] for t in res["catalog"]} == {
        "github_list_issues": True, "github_get_me": True,
        "github_merge_pull_request": False, "github_delete_file": False,
    }
    # Per-turn discovery (what the model sees) never fetches the catalog
    assert "catalog" not in await manager.get_server_tools("github")

@pytest.mark.asyncio
async def test_turn_reuses_one_session_per_server():
    """Inside a turn, calls reuse the server's session instead of opening one per call (AGENTS §4)."""
    import asyncio
    manager = MCPClientManager()
    opened = []
    real_open = manager._open_session
    def counting_open(name, url=None):
        opened.append(name)
        return real_open(name, url)
    manager._open_session = counting_open
    async with manager.turn() as turn:
        await turn.open({"ontap"})
        results = await asyncio.gather(*(manager.call_tool("ontap", "ontap_aggr_show", {}) for _ in range(3)))
    assert opened == ["ontap"]
    assert all(not r["isError"] for r in results)
    # Outside a turn, a call still works on a one-off session
    assert not (await manager.call_tool("ontap", "ontap_aggr_show", {}))["isError"]

@pytest.mark.asyncio
async def test_turn_hung_server_fails_its_calls_only():
    """A server that can't be opened within the timeout fails its own calls; the turn still closes cleanly."""
    manager = _hanging_manager()
    async with manager.turn() as turn:
        await turn.open({"ontap"})
        assert "Timed out" in turn.errors["ontap"]
        with pytest.raises(ConnectionError):
            await manager.call_tool("ontap", "ontap_aggr_show", {})
