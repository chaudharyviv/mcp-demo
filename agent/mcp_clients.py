"""
MCP Client Manager supporting multi-server tool discovery and invocation.
Connects to:
1. Microsoft Learn (Streamable HTTP)
2. GitHub (Streamable HTTP with Bearer PAT)
3. Mock NetApp ONTAP (stdio subprocess via sys.executable)
"""
import asyncio
import os
import sys
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Dict, Optional
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.client.streamable_http import streamablehttp_client
from agent.settings import get_secret

MCP_TIMEOUT_SECONDS = 30.0

class MCPClientManager:
    """Manages MCP connections and tool execution across servers."""

    def __init__(self, github_pat: Optional[str] = None, ontap_server_script: Optional[str] = None):
        self.github_pat = github_pat or get_secret("GITHUB_PAT")
        self.timeout = MCP_TIMEOUT_SECONDS
        self.ontap_server_script = ontap_server_script or os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "ontap_mock",
            "server.py"
        )
        self.servers_config = {
            "ontap": {
                "type": "stdio",
                "command": sys.executable,
                "args": [self.ontap_server_script]
            },
            "learn": {
                "type": "http",
                "url": "https://learn.microsoft.com/api/mcp",
                "headers": {}
            },
            "github": {
                "type": "http",
                "url": "https://api.githubcopilot.com/mcp/",
                "headers": {"Authorization": f"Bearer {self.github_pat}"} if self.github_pat else {}
            }
        }

    @asynccontextmanager
    async def _open_session(self, server_name: str) -> AsyncIterator[ClientSession]:
        """Opens an initialised MCP session for one server; closed when the block exits."""
        cfg = self.servers_config[server_name]
        if cfg["type"] == "stdio":
            server_params = StdioServerParameters(
                command=cfg["command"],
                args=cfg["args"],
                env=dict(os.environ)
            )
            async with stdio_client(server_params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    yield session
        elif cfg["type"] == "http":
            # Remote servers over Streamable HTTP (spec.md §2.3)
            async with streamablehttp_client(cfg["url"], headers=cfg["headers"]) as (read, write, _):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    yield session
        else:
            raise NotImplementedError(f"Unsupported transport type '{cfg['type']}'")

    async def get_server_tools(self, server_name: str) -> Dict[str, Any]:
        """Discovers tools for a specific server. Returns dict with status and tools list."""
        if server_name not in self.servers_config:
            return {"status": "error", "error": f"Unknown server {server_name}", "tools": []}

        is_remote = self.servers_config[server_name]["type"] == "http"
        tools = []
        async def _list_tools():
            async with self._open_session(server_name) as session:
                return await session.list_tools()

        try:
            res = await asyncio.wait_for(_list_tools(), self.timeout)
            for tool in res.tools:
                tool_dict = {
                    "name": tool.name,
                    "description": tool.description,
                    "inputSchema": tool.inputSchema,
                    "server": server_name
                }
                if is_remote:
                    # Namespace remote tools for the model/trace; keep the server's own name for calls
                    if not tool.name.startswith(f"{server_name}_"):
                        tool_dict["name"] = f"{server_name}_{tool.name}"
                    tool_dict["original_name"] = tool.name
                tools.append(tool_dict)
            return {"status": "online", "tools": tools, "error": None}
        except asyncio.TimeoutError:
            return {"status": "offline", "tools": [], "error": f"Timed out after {self.timeout:.0f}s"}
        except Exception as e:
            return {"status": "offline", "tools": [], "error": str(e)}

    async def discover_all_tools(self) -> Dict[str, Any]:
        """Discovers tools across all configured MCP servers concurrently and resiliently."""
        names = list(self.servers_config.keys())
        # get_server_tools never raises, so one slow or failed server can't block the others
        responses = await asyncio.gather(*(self.get_server_tools(name) for name in names))
        results = dict(zip(names, responses))
        all_tools = []
        for res in responses:
            if res["status"] == "online":
                all_tools.extend(res["tools"])
        return {
            "servers": results,
            "all_tools": all_tools
        }

    async def call_tool(self, server_name: str, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Invokes a tool on a specified server session per turn."""
        if server_name not in self.servers_config:
            raise ValueError(f"Unknown server '{server_name}'")

        async def _call():
            async with self._open_session(server_name) as session:
                return await session.call_tool(tool_name, arguments)

        try:
            res = await asyncio.wait_for(_call(), self.timeout)
        except asyncio.TimeoutError:
            raise TimeoutError(f"{server_name} tool '{tool_name}' timed out after {self.timeout:.0f}s") from None
        return {"content": res.content, "isError": res.isError}
