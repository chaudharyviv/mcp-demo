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
from contextlib import AsyncExitStack, asynccontextmanager
from contextvars import ContextVar
from typing import Any, AsyncIterator, Dict, Iterable, List, Optional
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.client.streamable_http import streamablehttp_client
from agent.settings import get_secret

MCP_TIMEOUT_SECONDS = 30.0


class TurnSessions:
    """MCP sessions for one user turn: one per server, opened on first need, reused by every call
    in the turn, closed when the turn ends (AGENTS.md §4: sessions per turn, not across reruns)."""

    def __init__(self, manager: "MCPClientManager"):
        self.manager = manager
        self.stack = AsyncExitStack()
        self.sessions: Dict[str, Any] = {}
        self.errors: Dict[str, str] = {}

    async def open(self, server_names: Iterable[str]) -> None:
        """Opens sessions for these servers. Call from the turn's own task, not from parallel call
        tasks: the MCP transports use cancel scopes that must be closed by the task that opened them."""
        for name in server_names:
            if name in self.sessions or name in self.errors or name not in self.manager.servers_config:
                continue
            try:
                async with asyncio.timeout(self.manager.timeout):
                    self.sessions[name] = await self.stack.enter_async_context(self.manager._open_session(name))
            except TimeoutError:
                self.errors[name] = f"Timed out after {self.manager.timeout:.0f}s connecting to {name}"
            except Exception as e:
                self.errors[name] = f"Could not connect to {name}: {e}"


# The current turn's sessions; parallel call tasks inherit it, other Streamlit sessions don't see it
_current_turn: ContextVar[Optional[TurnSessions]] = ContextVar("mcp_current_turn", default=None)

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
                # Read-only endpoint: write tools don't exist here, so the guardrail is server-side.
                # The full catalog is fetched only to show blocked tools in the sidebar.
                "url": "https://api.githubcopilot.com/mcp/readonly",
                "catalog_url": "https://api.githubcopilot.com/mcp/",
                "headers": {"Authorization": f"Bearer {self.github_pat}"} if self.github_pat else {}
            }
        }

    @asynccontextmanager
    async def _open_session(self, server_name: str, url: Optional[str] = None) -> AsyncIterator[ClientSession]:
        """Opens an initialised MCP session for one server (optionally at another URL); closed when the block exits."""
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
            async with streamablehttp_client(url or cfg["url"], headers=cfg["headers"]) as (read, write, _):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    yield session
        else:
            raise NotImplementedError(f"Unsupported transport type '{cfg['type']}'")

    async def _list_tools(self, server_name: str, url: Optional[str] = None) -> List[Any]:
        """Raw MCP tool list for one server, with the per-operation timeout."""
        async def _list():
            async with self._open_session(server_name, url) as session:
                return (await session.list_tools()).tools
        return await asyncio.wait_for(_list(), self.timeout)

    def _namespaced(self, server_name: str, tool_name: str) -> str:
        return tool_name if tool_name.startswith(f"{server_name}_") else f"{server_name}_{tool_name}"

    async def get_server_tools(self, server_name: str, include_catalog: bool = False) -> Dict[str, Any]:
        """Discovers tools for a specific server. Returns dict with status and tools list.

        include_catalog: for servers with a catalog_url, also return "catalog" (every tool the server
        has, each marked enabled or not) for display. Only "tools" is ever offered to the model.
        """
        if server_name not in self.servers_config:
            return {"status": "error", "error": f"Unknown server {server_name}", "tools": []}

        cfg = self.servers_config[server_name]
        is_remote = cfg["type"] == "http"
        tools = []
        try:
            for tool in await self._list_tools(server_name):
                tool_dict = {
                    "name": tool.name,
                    "description": tool.description,
                    "inputSchema": tool.inputSchema,
                    "server": server_name
                }
                if is_remote:
                    # Namespace remote tools for the model/trace; keep the server's own name for calls
                    tool_dict["name"] = self._namespaced(server_name, tool.name)
                    tool_dict["original_name"] = tool.name
                tools.append(tool_dict)
            result = {"status": "online", "tools": tools, "error": None}
            if include_catalog and cfg.get("catalog_url"):
                result["catalog"] = await self._get_catalog(server_name, {t["name"] for t in tools})
            return result
        except asyncio.TimeoutError:
            return {"status": "offline", "tools": [], "error": f"Timed out after {self.timeout:.0f}s"}
        except Exception as e:
            return {"status": "offline", "tools": [], "error": str(e)}

    async def _get_catalog(self, server_name: str, enabled_names: set) -> Optional[List[Dict[str, Any]]]:
        """Full tool list from catalog_url, each marked enabled if the model gets it. None if unavailable."""
        try:
            full = await self._list_tools(server_name, self.servers_config[server_name]["catalog_url"])
        except Exception:
            return None  # display-only; the sidebar falls back to the enabled list
        return [
            {
                "name": self._namespaced(server_name, tool.name),
                "description": tool.description,
                "enabled": self._namespaced(server_name, tool.name) in enabled_names
            }
            for tool in full
        ]

    async def discover_all_tools(self, include_catalog: bool = False) -> Dict[str, Any]:
        """Discovers tools across all configured MCP servers concurrently and resiliently."""
        names = list(self.servers_config.keys())
        # get_server_tools never raises, so one slow or failed server can't block the others
        responses = await asyncio.gather(*(self.get_server_tools(name, include_catalog) for name in names))
        results = dict(zip(names, responses))
        all_tools = []
        for res in responses:
            if res["status"] == "online":
                all_tools.extend(res["tools"])
        return {
            "servers": results,
            "all_tools": all_tools
        }

    @asynccontextmanager
    async def turn(self) -> AsyncIterator[TurnSessions]:
        """Scope for one user turn; call_tool inside it reuses the turn's sessions."""
        sessions = TurnSessions(self)
        token = _current_turn.set(sessions)
        try:
            async with sessions.stack:
                yield sessions
        finally:
            _current_turn.reset(token)

    async def call_tool(self, server_name: str, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Invokes a tool: on the current turn's session if one is open, else on a one-off session."""
        if server_name not in self.servers_config:
            raise ValueError(f"Unknown server '{server_name}'")

        turn = _current_turn.get()
        if turn is not None and server_name in turn.errors:
            raise ConnectionError(turn.errors[server_name])
        if turn is not None and server_name in turn.sessions:
            try:
                res = await asyncio.wait_for(turn.sessions[server_name].call_tool(tool_name, arguments), self.timeout)
            except asyncio.TimeoutError:
                raise TimeoutError(f"{server_name} tool '{tool_name}' timed out after {self.timeout:.0f}s") from None
            return {"content": res.content, "isError": res.isError}

        async def _call():
            async with self._open_session(server_name) as session:
                return await session.call_tool(tool_name, arguments)

        try:
            res = await asyncio.wait_for(_call(), self.timeout)
        except asyncio.TimeoutError:
            raise TimeoutError(f"{server_name} tool '{tool_name}' timed out after {self.timeout:.0f}s") from None
        return {"content": res.content, "isError": res.isError}
