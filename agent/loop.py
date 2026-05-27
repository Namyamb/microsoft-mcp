"""
Agent loop: sends messages to LM Studio, executes tool calls, and yields
SSE-compatible event dicts for the FastAPI streaming endpoint.

Architecture
------------
Hybrid deterministic + agentic pipeline:

    User → Intent Router → Tool-First Decision → Pre-execute Tool(s)
         → Inject results as tool context → LLM generates final response

For mailbox-related intents (query/summary/action) the router runs a real
tool BEFORE the LLM speaks. The LLM never has to "remember" to fetch — the
data is already in its context. For general chat / drafting we stay
agentic (tool_choice="auto"). Behavior is controlled by env flags so the
old flow can be restored at any time.
"""
from __future__ import annotations

import json
import logging
import os
import time
import uuid
from typing import Any, Dict, Generator, List, Optional

from openai import OpenAI

from .router import (
    INTENT_DRAFTING,
    INTENT_GENERAL_CHAT,
    INTENT_MAILBOX_ACTION,
    MODE_TOOL_FIRST,
    RouteDecision,
    classify_intent,
)
from .schemas import TOOL_SCHEMAS

logger = logging.getLogger("outlook_agent")


def _env_flag(name: str, default: bool = True) -> bool:
    raw = (os.getenv(name) or "").strip().lower()
    if not raw:
        return default
    return raw not in ("0", "false", "no", "off")

SYSTEM_PROMPT = """You are Outlook Assistant, an AI email agent with direct access to the user's Microsoft Outlook account via Microsoft Graph API.

You have tools to:
- Read, list, and filter emails; use outlook_find_messages for any find/search/exists question about mail (sender or topic)
- Send, reply, reply-all, forward, and draft emails
- Organize emails: move, archive, delete, flag/unflag, mark read/unread
- Manage folders and categories
- AI helpers: summarize_mailbox (any summarization / inbox briefing question), draft replies
- Resolve natural-language references (e.g. "the latest email", "first email") to IDs using resolve_email_id

ROUTER NOTICE:
- For mailbox-related questions, an upstream router may already have executed a tool and injected its result as a tool message above. When that happens, GROUND YOUR ANSWER IN THAT TOOL RESULT. Do not invent emails, senders, or content beyond what the tool returned.
- If the injected tool result indicates failure or returned no messages, say so honestly. Do not fabricate mailbox data to fill the gap.
- You may still call additional tools to refine, follow up, or perform actions (e.g. resolve_email_id then a destructive action). Always confirm destructive actions in your final reply.

Rules:
- When the user asks about their emails, ALWAYS call the appropriate tool to fetch real data — never make up email content.
- For questions like whether mail exists, mail from someone, searching by company/domain/name, or by topic/keywords, call outlook_find_messages with the user's question or the key phrase (one call; it handles sender vs keyword routing internally).
- For any request to summarize, recap, brief, or explain mail (inbox, unread, flagged, from someone, about a topic, or a specific message id), call summarize_mailbox with the user's wording; do not ask them to paste subject, sender, and preview manually.
- CRITICAL — draft vs send:
    * If the user says "draft", "create a draft", or "save as draft" → call outlook_create_draft. NEVER call outlook_send_email.
    * outlook_create_draft returns {"success": true, "data": {"draft_id": "...", ...}} — extract data.draft_id and remember it.
    * If the user later says "send it", "send the draft", "go ahead", "yes send", or similar AFTER a draft was created → call outlook_send_draft(draft_id=<value of data.draft_id>) — NEVER call outlook_send_email in this case.
    * Only call outlook_send_email when the user asks to send a brand-new email with no prior draft in context.
    * When in doubt, ALWAYS default to outlook_create_draft, not outlook_send_email.
- Use resolve_email_id whenever the user refers to an email without an explicit ID.
  Pass ONLY the ordinal/position word as the reference — examples:
    "delete the first email"  → resolve_email_id(reference="first")
    "reply to the second one" → resolve_email_id(reference="second")
    "archive that email"      → resolve_email_id(reference="this")
    "show email from alice"   → resolve_email_id(reference="email from alice@example.com")
  Never pass phrases like "first email" or "the first email" — just "first".
- If you just called outlook_get_emails and the list is fresh, do NOT call it again before resolving.
- For destructive actions (delete, send), confirm the action in your final response.
- Be concise. When listing emails, show subject, sender, date, and read status.
- If a tool returns success=false, explain the error and suggest what to do.
- Today is Monday, May 11, 2026.
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


def _extract_recent_draft_id(session_id: Optional[str]) -> Optional[str]:
    """
    Scan the session's stored tool-call history for the most recent successful
    outlook_create_draft call and return its draft_id. This is what makes the
    create-draft → send-draft flow deterministic across chat turns: the LLM
    never has to remember the id; the router pulls it from persisted state.
    """
    if not session_id:
        return None
    try:
        import db as _db  # local import — avoids hard coupling at module load
        msgs = _db.get_messages(session_id)
    except Exception:  # noqa: BLE001
        return None
    for m in reversed(msgs):
        tool_events = m.get("tool_calls") or []
        if not isinstance(tool_events, list):
            continue
        for event in reversed(tool_events):
            if not isinstance(event, dict):
                continue
            if event.get("type") != "tool_end":
                continue
            if event.get("name") != "outlook_create_draft":
                continue
            result = event.get("result") or {}
            if not isinstance(result, dict):
                continue
            data = result.get("data") or {}
            if isinstance(data, dict):
                did = data.get("draft_id")
                if did:
                    return str(did)
    return None


def _pre_execute_routed_tool(
    decision: RouteDecision,
    messages: List[Dict[str, Any]],
) -> Generator[Dict[str, Any], None, None]:
    """
    Run the router-recommended tool deterministically and append its result to
    the LLM message history as a synthetic tool-call exchange. Yields SSE
    events so the UI can show the same tool badge it would for a normal call.
    """
    tool_name = decision.recommended_tool
    if not tool_name:
        return
    args = dict(decision.recommended_args or {})
    call_id = f"router_{uuid.uuid4().hex[:12]}"

    yield {"type": "tool_start", "name": tool_name, "args": args, "id": call_id}

    t0 = time.time()
    raw_result = _execute_tool(tool_name, args)
    elapsed_ms = int((time.time() - t0) * 1000)

    try:
        result_data = json.loads(raw_result)
    except Exception:  # noqa: BLE001
        result_data = {"raw": raw_result}

    success = bool(result_data.get("success", True)) if isinstance(result_data, dict) else True
    logger.info(
        "router pre_exec tool=%s success=%s duration_ms=%s intent=%s reason=%s",
        tool_name, success, elapsed_ms, decision.intent, decision.reason,
    )

    yield {"type": "tool_end", "name": tool_name, "result": result_data, "id": call_id}

    messages.append(
        {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": call_id,
                    "type": "function",
                    "function": {"name": tool_name, "arguments": json.dumps(args)},
                }
            ],
        }
    )
    messages.append({"role": "tool", "tool_call_id": call_id, "content": raw_result})

    grounding_note = (
        "[ROUTER PRE-EXECUTION]\n"
        f"Tool: {tool_name}\n"
        f"Intent: {decision.intent}\n"
        f"Reason: {decision.reason}\n"
        f"Success: {success}\n"
        "The tool above was executed deterministically by the router BEFORE you were called. "
        "Use its result to answer the user. Ground every mailbox claim in this data. "
        "If the tool failed or returned no messages, say so honestly — do not fabricate mailbox content. "
        "You may call additional tools to refine, follow up, or perform actions."
    )
    messages.append({"role": "system", "content": grounding_note})


def run_agent_stream(
    history: List[Dict[str, str]],
    user_message: str,
    *,
    session_id: Optional[str] = None,
) -> Generator[Dict[str, Any], None, None]:
    """
    Synchronous generator. Yields dicts:
      {"type": "route",      "decision": {...}}              (router observability)
      {"type": "text_delta", "content": "..."}
      {"type": "tool_start", "name": "...", "args": {...}, "id": "..."}
      {"type": "tool_end",   "name": "...", "result": {...}, "id": "..."}
      {"type": "error",      "message": "..."}
    The caller (server.py) appends the final "done" event.
    """
    base_url = os.getenv("LMSTUDIO_BASE_URL", "http://127.0.0.1:1234/v1")
    api_key = os.getenv("LMSTUDIO_API_KEY", "lm-studio")
    model = os.getenv("LMSTUDIO_MODEL", "gemma-4-e2b-it")

    tool_first_enabled = _env_flag("ENABLE_TOOL_FIRST_ROUTING", True)

    client = OpenAI(base_url=base_url, api_key=api_key, timeout=120.0)

    messages: List[Dict[str, Any]] = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages.extend(history)
    messages.append({"role": "user", "content": user_message})

    decision = classify_intent(user_message)

    if (
        decision.intent == INTENT_MAILBOX_ACTION
        and decision.recommended_tool is None
        and "send-draft" in (decision.reason or "")
    ):
        draft_id = _extract_recent_draft_id(session_id)
        if draft_id:
            short = draft_id[:24] + "…" if len(draft_id) > 24 else draft_id
            decision = RouteDecision(
                intent=INTENT_MAILBOX_ACTION,
                requires_tools=True,
                recommended_tool="outlook_send_draft",
                recommended_args={"draft_id": draft_id},
                mode=MODE_TOOL_FIRST,
                reason=f"send-draft phrase — recovered draft_id={short} from session history",
            )

    logger.info(
        "router decision intent=%s mode=%s requires_tools=%s tool=%s reason=%s",
        decision.intent, decision.mode, decision.requires_tools,
        decision.recommended_tool, decision.reason,
    )
    yield {"type": "route", "decision": decision.to_dict()}

    if (
        tool_first_enabled
        and decision.mode == MODE_TOOL_FIRST
        and decision.requires_tools
        and decision.recommended_tool
    ):
        try:
            for event in _pre_execute_routed_tool(decision, messages):
                yield event
        except Exception as e:  # noqa: BLE001
            logger.exception("Router pre-execution failed: %s", e)
            messages.append(
                {
                    "role": "system",
                    "content": (
                        "[ROUTER PRE-EXECUTION FAILED]\n"
                        f"Tool: {decision.recommended_tool}\n"
                        f"Error: {e}\n"
                        "Acknowledge the failure to the user; do not invent mailbox data."
                    ),
                }
            )

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
