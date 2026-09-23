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
from typing import Dict, List, Any, Optional
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.client.sse import sse_client

class MCPClientManager:
    """Manages MCP connections and tool execution across servers."""

    def __init__(self, github_pat: Optional[str] = None, ontap_server_script: Optional[str] = None):
        if not github_pat:
            github_pat = os.environ.get("GITHUB_PAT")
            if not github_pat:
                try:
                    import streamlit as st
                    github_pat = st.secrets.get("GITHUB_PAT")
                except Exception:
                    github_pat = None
        self.github_pat = github_pat
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
                "type": "sse",
                "url": "https://learn.microsoft.com/api/mcp",
                "headers": {}
            },
            "github": {
                "type": "sse",
                "url": "https://api.githubcopilot.com/mcp/",
                "headers": {"Authorization": f"Bearer {self.github_pat}"} if self.github_pat else {}
            }
        }

    async def get_server_tools(self, server_name: str) -> Dict[str, Any]:
        """Discovers tools for a specific server. Returns dict with status and tools list."""
        if server_name not in self.servers_config:
            return {"status": "error", "error": f"Unknown server {server_name}", "tools": []}

        cfg = self.servers_config[server_name]
        tools = []
        try:
            if cfg["type"] == "stdio":
                server_params = StdioServerParameters(
                    command=cfg["command"],
                    args=cfg["args"],
                    env=dict(os.environ)
                )
                async with stdio_client(server_params) as (read, write):
                    async with ClientSession(read, write) as session:
                        await session.initialize()
                        res = await session.list_tools()
                        for tool in res.tools:
                            tool_dict = {
                                "name": tool.name,
                                "description": tool.description,
                                "inputSchema": tool.inputSchema,
                                "server": server_name
                            }
                            tools.append(tool_dict)
            elif cfg["type"] == "sse":
                # For remote SSE servers
                async with sse_client(cfg["url"], headers=cfg["headers"]) as (read, write):
                    async with ClientSession(read, write) as session:
                        await session.initialize()
                        res = await session.list_tools()
                        for tool in res.tools:
                            name = tool.name if tool.name.startswith(f"{server_name}_") else f"{server_name}_{tool.name}"
                            tool_dict = {
                                "name": name,
                                "original_name": tool.name,
                                "description": tool.description,
                                "inputSchema": tool.inputSchema,
                                "server": server_name
                            }
                            tools.append(tool_dict)

            return {"status": "online", "tools": tools, "error": None}
        except Exception as e:
            return {"status": "offline", "tools": [], "error": str(e)}

    async def discover_all_tools(self) -> Dict[str, Any]:
        """Discovers tools across all configured MCP servers resiliently."""
        results = {}
        all_tools = []
        for server_name in self.servers_config.keys():
            res = await self.get_server_tools(server_name)
            results[server_name] = res
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
                    res = await session.call_tool(tool_name, arguments)
                    return {"content": res.content, "isError": res.isError}
        elif cfg["type"] == "sse":
            async with sse_client(cfg["url"], headers=cfg["headers"]) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    res = await session.call_tool(tool_name, arguments)
                    return {"content": res.content, "isError": res.isError}
        else:
            raise NotImplementedError(f"Unsupported transport type '{cfg['type']}'")
