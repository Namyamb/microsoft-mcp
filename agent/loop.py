"""
Agent loop: sends messages to LM Studio, executes tool calls, and yields
SSE-compatible event dicts for the FastAPI streaming endpoint.
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, Generator, List

from openai import OpenAI

from .schemas import TOOL_SCHEMAS

logger = logging.getLogger("outlook_agent")

SYSTEM_PROMPT = """You are Outlook Assistant, an AI email agent with direct access to the user's Microsoft Outlook account via Microsoft Graph API.

You have tools to:
- Read, list, search, and filter emails
- Send, reply, reply-all, forward, and draft emails
- Organize emails: move, archive, delete, flag/unflag, mark read/unread
- Manage folders and categories
- AI helpers: summarize emails, draft replies
- Resolve natural-language references (e.g. "the latest email", "first email") to IDs using resolve_email_id

Rules:
- When the user asks about their emails, ALWAYS call the appropriate tool to fetch real data — never make up email content.
- Use resolve_email_id whenever the user refers to an email without an explicit ID (e.g. "that email", "the first one", "latest email").
- For destructive actions (delete, send), confirm the action in your final response.
- Be concise. When listing emails, show subject, sender, date, and read status.
- If a tool returns success=false, explain the error and suggest what to do.
- Today is Thursday, April 30, 2026.
"""

_tools_cache: Dict[str, Any] | None = None


def _get_tools() -> Dict[str, Any]:
    global _tools_cache
    if _tools_cache is None:
        from app.integrations.outlook import get_outlook_tools
        _tools_cache = get_outlook_tools()
    return _tools_cache


def _execute_tool(name: str, args: Dict[str, Any]) -> str:
    tools = _get_tools()
    fn = tools.get(name)
    if fn is None:
        return json.dumps({"success": False, "error": f"Unknown tool: '{name}'"})
    try:
        result = fn(**args)
        return json.dumps(result, default=str, ensure_ascii=False)
    except TypeError as e:
        return json.dumps({"success": False, "error": f"Bad arguments for {name}: {e}"})
    except Exception as e:  # noqa: BLE001
        logger.exception("Tool %s raised an exception", name)
        return json.dumps({"success": False, "error": str(e)})


def run_agent_stream(
    history: List[Dict[str, str]],
    user_message: str,
) -> Generator[Dict[str, Any], None, None]:
    """
    Synchronous generator. Yields dicts:
      {"type": "text_delta", "content": "..."}
      {"type": "tool_start", "name": "...", "args": {...}, "id": "..."}
      {"type": "tool_end",   "name": "...", "result": {...}, "id": "..."}
      {"type": "error",      "message": "..."}
    The caller (server.py) appends the final "done" event.
    """
    base_url = os.getenv("LMSTUDIO_BASE_URL", "http://127.0.0.1:1234/v1")
    api_key = os.getenv("LMSTUDIO_API_KEY", "lm-studio")
    model = os.getenv("LMSTUDIO_MODEL", "gemma-4-e2b-it")

    client = OpenAI(base_url=base_url, api_key=api_key, timeout=120.0)

    messages: List[Dict[str, Any]] = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages.extend(history)
    messages.append({"role": "user", "content": user_message})

    max_iterations = 8

    for iteration in range(max_iterations):
        tool_calls_buf: Dict[int, Dict[str, Any]] = {}
        current_content = ""
        finish_reason = None

        try:
            stream = client.chat.completions.create(
                model=model,
                messages=messages,
                tools=TOOL_SCHEMAS,
                tool_choice="auto",
                stream=True,
                temperature=0.4,
            )

            for chunk in stream:
                if not chunk.choices:
                    continue
                choice = chunk.choices[0]
                finish_reason = choice.finish_reason
                delta = choice.delta

                if delta.content:
                    current_content += delta.content
                    yield {"type": "text_delta", "content": delta.content}

                if delta.tool_calls:
                    for tc_delta in delta.tool_calls:
                        idx = tc_delta.index
                        if idx not in tool_calls_buf:
                            tool_calls_buf[idx] = {"id": "", "name": "", "args": ""}
                        if tc_delta.id:
                            tool_calls_buf[idx]["id"] = tc_delta.id
                        if tc_delta.function:
                            if tc_delta.function.name:
                                tool_calls_buf[idx]["name"] = tc_delta.function.name
                            if tc_delta.function.arguments:
                                tool_calls_buf[idx]["args"] += tc_delta.function.arguments

        except Exception as e:  # noqa: BLE001
            msg = str(e)
            if "connection" in msg.lower() or "refused" in msg.lower():
                yield {
                    "type": "error",
                    "message": (
                        "Cannot reach LM Studio. Make sure LM Studio is running at "
                        f"{base_url} with a model loaded."
                    ),
                }
            else:
                yield {"type": "error", "message": f"LM Studio error: {msg}"}
            return

        if not tool_calls_buf:
            # No tool calls → conversation turn is complete.
            break

        # Build OpenAI-format tool_calls for the history message
        sorted_calls = [tool_calls_buf[i] for i in sorted(tool_calls_buf)]
        openai_tool_calls = [
            {
                "id": tc["id"],
                "type": "function",
                "function": {"name": tc["name"], "arguments": tc["args"]},
            }
            for tc in sorted_calls
        ]

        messages.append(
            {
                "role": "assistant",
                "content": current_content or None,
                "tool_calls": openai_tool_calls,
            }
        )

        # Execute each tool and stream events
        for tc in sorted_calls:
            try:
                args = json.loads(tc["args"] or "{}")
            except json.JSONDecodeError:
                args = {}

            yield {"type": "tool_start", "name": tc["name"], "args": args, "id": tc["id"]}

            raw_result = _execute_tool(tc["name"], args)
            try:
                result_data = json.loads(raw_result)
            except Exception:  # noqa: BLE001
                result_data = {"raw": raw_result}

            yield {"type": "tool_end", "name": tc["name"], "result": result_data, "id": tc["id"]}

            messages.append(
                {"role": "tool", "tool_call_id": tc["id"], "content": raw_result}
            )

    else:
        # Max iterations reached — yield a warning so the user sees something
        yield {
            "type": "text_delta",
            "content": "\n\n_(Reached maximum tool-call iterations. The above may be incomplete.)_",
        }
