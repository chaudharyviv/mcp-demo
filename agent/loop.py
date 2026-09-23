"""
Agent Loop for GPT-4o mini with tool-calling capabilities over MCP tools.
Emits trace events for UI streaming.
"""
import asyncio
import json
import os
import time
from pathlib import Path
from typing import Dict, List, Any, Optional, Callable
from openai import AsyncOpenAI
from agent.mcp_clients import MCPClientManager

SYSTEM_PROMPT_PATH = Path(__file__).parent / "system_prompt.md"

def load_system_prompt() -> str:
    with open(SYSTEM_PROMPT_PATH, "r", encoding="utf-8") as f:
        return f.read()

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

class AgentLoop:
    def __init__(self, api_key: Optional[str] = None, mcp_manager: Optional[MCPClientManager] = None):
        if not api_key:
            api_key = os.environ.get("OPENAI_API_KEY")
            if not api_key:
                try:
                    import streamlit as st
                    api_key = st.secrets.get("OPENAI_API_KEY")
                except Exception:
                    api_key = None
        self.api_key = api_key
        self.client = AsyncOpenAI(api_key=self.api_key) if self.api_key else None
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
                return {
                    "role": "assistant",
                    "content": f"Error calling language model: {str(e)}",
                    "iterations": iterations
                }

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
                server_name = "ontap"
                for tool in tools_list:
                    if tool["name"] == func_name:
                        server_name = tool.get("server", "ontap")
                        break

                if trace_callback:
                    trace_callback({
                        "event": "tool_started",
                        "tool": func_name,
                        "server": server_name,
                        "args": func_args
                    })

                tool_start = time.time()
                try:
                    tool_result = await self.mcp_manager.call_tool(server_name, func_name, func_args)
                    duration = time.time() - tool_start

                    content_output = tool_result.get("content", "")
                    content_str = json.dumps(content_output) if isinstance(content_output, (dict, list)) else str(content_output)

                    if trace_callback:
                        trace_callback({
                            "event": "tool_finished",
                            "tool": func_name,
                            "server": server_name,
                            "duration": round(duration, 2),
                            "status": "success",
                            "result": content_str[:200]
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

        return {
            "role": "assistant",
            "content": final_text or conversation[-1].get("content", ""),
            "iterations": iterations,
            "messages": conversation
        }

    async def _call_openai_with_retry(self, conversation: List[Dict[str, Any]], tools: Optional[List[Dict[str, Any]]]):
        """Calls OpenAI with 30s timeout and single retry on 5xx or 429."""
        params = {
            "model": self.model,
            "messages": conversation,
            "temperature": self.temperature
        }
        if tools:
            params["tools"] = tools

        for attempt in range(2):
            try:
                return await asyncio.wait_for(
                    self.client.chat.completions.create(**params),
                    timeout=30.0
                )
            except Exception as e:
                # Retry once if 1st attempt fails
                if attempt == 0:
                    await asyncio.sleep(1.0)
                    continue
                raise e
