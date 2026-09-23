import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from agent.loop import AgentLoop, load_system_prompt, mcp_tools_to_openai_tools

def test_system_prompt_loading():
    """Verifies system prompt is loaded correctly."""
    prompt = load_system_prompt()
    assert "Microsoft Learn MCP" in prompt
    assert "Mock NetApp ONTAP MCP" in prompt
    assert "4 to 6 lines" in prompt
    assert "CHG" in prompt

def test_mcp_tools_to_openai_tools():
    """Verifies conversion of MCP tools to OpenAI format."""
    mcp_tools = [
        {
            "name": "ontap_cluster_health_summary",
            "description": "Returns health summary",
            "inputSchema": {"type": "object", "properties": {}}
        }
    ]
    openai_tools = mcp_tools_to_openai_tools(mcp_tools)
    assert len(openai_tools) == 1
    assert openai_tools[0]["type"] == "function"
    assert openai_tools[0]["function"]["name"] == "ontap_cluster_health_summary"

@pytest.mark.asyncio
async def test_agent_loop_with_mocked_openai():
    """Tests agent loop turn with mocked OpenAI response."""
    mock_mcp_manager = MagicMock()
    mock_mcp_manager.discover_all_tools = AsyncMock(return_value={
        "all_tools": [
            {
                "name": "ontap_cluster_health_summary",
                "description": "Health summary",
                "inputSchema": {"type": "object", "properties": {}},
                "server": "ontap"
            }
        ]
    })
    mock_mcp_manager.call_tool = AsyncMock(return_value={
        "content": [{"type": "text", "text": "Health OK"}],
        "isError": False
    })

    agent = AgentLoop(api_key="mock-key", mcp_manager=mock_mcp_manager)

    # Mock OpenAI completions response (1st call tool call, 2nd call text answer)
    mock_tool_call = MagicMock()
    mock_tool_call.id = "call_123"
    mock_tool_call.function.name = "ontap_cluster_health_summary"
    mock_tool_call.function.arguments = "{}"

    mock_msg_1 = MagicMock()
    mock_msg_1.tool_calls = [mock_tool_call]
    mock_msg_1.model_dump.return_value = {
        "role": "assistant",
        "tool_calls": [{
            "id": "call_123",
            "type": "function",
            "function": {"name": "ontap_cluster_health_summary", "arguments": "{}"}
        }]
    }

    mock_msg_2 = MagicMock()
    mock_msg_2.tool_calls = None
    mock_msg_2.content = "Storage status is healthy overall."

    mock_response_1 = MagicMock()
    mock_response_1.choices = [MagicMock(message=mock_msg_1)]

    mock_response_2 = MagicMock()
    mock_response_2.choices = [MagicMock(message=mock_msg_2)]

    agent.client = MagicMock()
    agent.client.chat.completions.create = AsyncMock(side_effect=[mock_response_1, mock_response_2])

    trace_events = []
    def trace_cb(evt):
        trace_events.append(evt)

    result = await agent.run_turn([{"role": "user", "content": "How healthy is storage?"}], trace_callback=trace_cb)

    assert result["role"] == "assistant"
    assert "healthy overall" in result["content"]
    assert result["iterations"] == 2
    assert len(trace_events) == 2
    assert trace_events[0]["event"] == "tool_started"
    assert trace_events[1]["event"] == "tool_finished"

@pytest.mark.asyncio
async def test_real_mcp_content_converts_to_text():
    """Real MCP results (TextContent objects) must serialise to the tool's JSON text (CODE_REVIEW H2)."""
    from agent.loop import content_to_text
    from agent.mcp_clients import MCPClientManager
    result = await MCPClientManager().call_tool("ontap", "ontap_cluster_health_summary", {})
    text = content_to_text(result["content"])
    assert json.loads(text)["synthetic"] is True

@pytest.mark.asyncio
async def test_namespaced_remote_tool_called_by_original_name():
    """Model sees learn_* names; the Learn server must receive its own tool name (CODE_REVIEW H4)."""
    mock_mcp_manager = MagicMock()
    mock_mcp_manager.discover_all_tools = AsyncMock(return_value={
        "all_tools": [{
            "name": "learn_microsoft_docs_search",
            "original_name": "microsoft_docs_search",
            "description": "Search docs",
            "inputSchema": {"type": "object", "properties": {}},
            "server": "learn"
        }]
    })
    mock_mcp_manager.call_tool = AsyncMock(return_value={"content": [], "isError": False})
    agent = AgentLoop(api_key="mock-key", mcp_manager=mock_mcp_manager)

    tool_call = MagicMock()
    tool_call.id = "call_1"
    tool_call.function.name = "learn_microsoft_docs_search"
    tool_call.function.arguments = '{"query": "storage"}'
    msg_1 = MagicMock(tool_calls=[tool_call])
    msg_1.model_dump.return_value = {"role": "assistant", "tool_calls": []}
    msg_2 = MagicMock(tool_calls=None, content="done")
    agent.client = MagicMock()
    agent.client.chat.completions.create = AsyncMock(side_effect=[
        MagicMock(choices=[MagicMock(message=msg_1)]),
        MagicMock(choices=[MagicMock(message=msg_2)]),
    ])

    await agent.run_turn([{"role": "user", "content": "q"}])
    mock_mcp_manager.call_tool.assert_awaited_once_with("learn", "microsoft_docs_search", {"query": "storage"})
