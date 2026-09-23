import asyncio
import pytest
from unittest.mock import patch
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
    # Mock invalid URL for learn server to simulate network / unreachable failure
    manager.servers_config["learn"]["url"] = "https://invalid.unreachable.endpoint/mcp"

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
