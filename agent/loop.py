"""
Agent Loop for GPT-4o mini with tool-calling capabilities over MCP tools.
Emits trace events for UI streaming.
"""
import asyncio
import json
import time
from pathlib import Path
from typing import Dict, List, Any, Optional, Callable
from openai import AsyncOpenAI, APIStatusError, APITimeoutError
from agent.mcp_clients import MCPClientManager
from agent.settings import get_secret

SYSTEM_PROMPT_PATH = Path(__file__).parent / "system_prompt.md"

def load_system_prompt() -> str:
    with open(SYSTEM_PROMPT_PATH, "r", encoding="utf-8") as f:
        prompt = f.read()
    # Fill in the demo repo so "our demo repo" (chip 2) resolves to a concrete repository
    return prompt.replace("{GITHUB_DEMO_REPO}", get_secret("GITHUB_DEMO_REPO") or "(not configured)")

def mcp_tools_to_openai_tools(mcp_tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Converts MCP tool schemas to OpenAI format."""
    openai_tools = []
    for tool in mcp_tools:
        openai_tools.append({
            "type": "function",
            "function": {
                "name": tool["name"],
                "description": tool.get("description", ""),
                "parameters": tool.get("inputSchema", {"type": "object", "properties": {}})
            }
        })
    return openai_tools

def content_to_text(content: Any) -> str:
    """Flattens MCP tool result content (list of TextContent etc.) into a string."""
    if isinstance(content, list):
        parts = []
        for item in content:
            text = item.get("text") if isinstance(item, dict) else getattr(item, "text", None)
            parts.append(text if text is not None else str(item))
        return "\n".join(parts)
    if isinstance(content, dict):
        return json.dumps(content)
    return str(content)

class AgentLoop:
    def __init__(self, api_key: Optional[str] = None, mcp_manager: Optional[MCPClientManager] = None):
        self.api_key = api_key or get_secret("OPENAI_API_KEY")
        # 30 s per request; SDK retries off so the single retry below is the only one (spec LLM-4)
        self.client = AsyncOpenAI(api_key=self.api_key, timeout=30.0, max_retries=0) if self.api_key else None
        self.mcp_manager = mcp_manager or MCPClientManager()
        self.model = "gpt-4o-mini"
        self.temperature = 0.2
        self.max_iterations = 6

    async def run_turn(
        self,
        messages: List[Dict[str, Any]],
        trace_callback: Optional[Callable[[Dict[str, Any]], None]] = None
    ) -> Dict[str, Any]:
        """Executes a single user turn with up to max_iterations tool calls."""
        if not self.client:
            raise ValueError("OPENAI_API_KEY is not configured.")

        system_prompt = load_system_prompt()
        conversation = [{"role": "system", "content": system_prompt}] + messages

        # Discover tools
        discovery = await self.mcp_manager.discover_all_tools()
        tools_list = discovery.get("all_tools", [])
        openai_tools = mcp_tools_to_openai_tools(tools_list) if tools_list else None

        iterations = 0
        final_text = ""

        while iterations < self.max_iterations:
            iterations += 1
            start_time = time.time()

            try:
                # Call OpenAI with 30s timeout and automatic retry logic on 5xx/429
                response = await self._call_openai_with_retry(conversation, openai_tools)
            except Exception as e:
                if trace_callback:
                    trace_callback({
                        "event": "llm_error",
                        "error": str(e)
                    })
                # Propagate so the UI can show a friendly error and offer the replay fallback
                raise

            choice = response.choices[0]
            message = choice.message

            # If no tool calls requested, we are done
            if not message.tool_calls:
                final_text = message.content or ""
                conversation.append({"role": "assistant", "content": final_text})
                break

            # Handle tool calls
            conversation.append(message.model_dump())

            for tool_call in message.tool_calls:
                func_name = tool_call.function.name
                func_args_str = tool_call.function.arguments
                try:
                    func_args = json.loads(func_args_str)
                except Exception:
                    func_args = {}

                # Determine server
                tool_info = next((t for t in tools_list if t["name"] == func_name), None)
                if tool_info is None:
                    # Model asked for a tool no server offers; tell it rather than guessing a server
                    error = f"Unknown tool '{func_name}'. Use only the tools provided."
                    if trace_callback:
                        trace_callback({
                            "event": "tool_failed",
                            "tool": func_name,
                            "server": "unknown",
                            "duration": 0.0,
                            "status": "error",
                            "error": error
                        })
                    conversation.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "name": func_name,
                        "content": json.dumps({"error": error})
                    })
                    continue
                server_name = tool_info.get("server", "ontap")
                # Remote tools are namespaced for the model; the server expects its own name
                server_tool_name = tool_info.get("original_name", func_name)

                if trace_callback:
                    trace_callback({
                        "event": "tool_started",
                        "tool": func_name,
                        "server": server_name,
                        "args": func_args
                    })

                tool_start = time.time()
                try:
                    tool_result = await self.mcp_manager.call_tool(server_name, server_tool_name, func_args)
                    duration = time.time() - tool_start

                    content_str = content_to_text(tool_result.get("content", ""))
                    # The server can report failure in-band (e.g. input validation); trace it as ✗
                    failed = bool(tool_result.get("isError"))

                    if trace_callback:
                        trace_callback({
                            "event": "tool_failed" if failed else "tool_finished",
                            "tool": func_name,
                            "server": server_name,
                            "duration": round(duration, 2),
                            "status": "error" if failed else "success",
                            "error" if failed else "result": content_str[:200]
                        })

                    conversation.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "name": func_name,
                        "content": content_str
                    })
                except Exception as e:
                    duration = time.time() - tool_start
                    if trace_callback:
                        trace_callback({
                            "event": "tool_failed",
                            "tool": func_name,
                            "server": server_name,
                            "duration": round(duration, 2),
                            "status": "error",
                            "error": str(e)
                        })
                    conversation.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "name": func_name,
                        "content": json.dumps({"error": str(e)})
                    })

        if not final_text:
            # Iteration cap hit while the model still wanted tools: answer with what's known (spec LLM-3)
            try:
                response = await self._call_openai_with_retry(conversation, openai_tools, tool_choice="none")
            except Exception as e:
                if trace_callback:
                    trace_callback({"event": "llm_error", "error": str(e)})
                raise
            final_text = response.choices[0].message.content or ""
            conversation.append({"role": "assistant", "content": final_text})

        return {
            "role": "assistant",
            "content": final_text,
            "iterations": iterations,
            "messages": conversation
        }

    async def _call_openai_with_retry(
        self,
        conversation: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]],
        tool_choice: Optional[str] = None
    ):
        """Calls OpenAI with 30s timeout and single retry on 5xx or 429."""
        params = {
            "model": self.model,
            "messages": conversation,
            "temperature": self.temperature
        }
        if tools:
            params["tools"] = tools
            if tool_choice:
                params["tool_choice"] = tool_choice

        for attempt in range(2):
            try:
                return await self.client.chat.completions.create(**params)
            except (APIStatusError, APITimeoutError) as e:
                # Retry once, only on timeout, 429 or 5xx; anything else (e.g. 401, 400) fails fast
                status = getattr(e, "status_code", None)
                retryable = isinstance(e, APITimeoutError) or status == 429 or (status or 0) >= 500
                if attempt == 0 and retryable:
                    await asyncio.sleep(1.0)
                    continue
                raise
