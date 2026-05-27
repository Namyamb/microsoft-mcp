"""
Deterministic intent router for the Outlook MCP agent.

Purpose
-------
Decide BEFORE calling the LLM whether the user's message refers to mailbox state
(and therefore requires a real tool call) or is a free-form chat / drafting
request. This makes mailbox answers tool-grounded by construction, instead of
relying on the LLM to remember to call tools.

The classifier uses only plain string operations (lowercase substring checks,
startswith, token scans). No regex.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger("outlook_router")


INTENT_MAILBOX_QUERY = "MAILBOX_QUERY"
INTENT_MAILBOX_SUMMARY = "MAILBOX_SUMMARY"
INTENT_MAILBOX_ACTION = "MAILBOX_ACTION"
INTENT_DRAFTING = "DRAFTING"
INTENT_GENERAL_CHAT = "GENERAL_CHAT"


MODE_TOOL_FIRST = "tool_first"
MODE_AGENTIC = "agentic"


@dataclass
class RouteDecision:
    """Result of intent classification — fed to the agent loop."""

    intent: str
    requires_tools: bool
    recommended_tool: Optional[str]
    recommended_args: Dict[str, Any] = field(default_factory=dict)
    mode: str = MODE_AGENTIC
    reason: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "intent": self.intent,
            "requires_tools": self.requires_tools,
            "recommended_tool": self.recommended_tool,
            "recommended_args": self.recommended_args,
            "mode": self.mode,
            "reason": self.reason,
        }


_MAIL_NOUNS = (
    "email", "emails", "mail", "mails", "message", "messages", "inbox",
)

_SUMMARY_KEYS = (
    "summari",          # summarize / summary / summarise
    "recap",
    "brief me",
    "give me a brief",
    "tldr",
    "tl;dr",
    "catch me up",
    "overview of my",
    "what's new in my inbox",
    "whats new in my inbox",
    "what's important",
    "whats important",
)

_QUERY_VERBS = (
    "show", "list", "find", "search", "fetch", "get", "look up", "lookup",
    "any mail", "any email", "any emails", "any messages",
    "is there any mail", "is there any email", "is there any emails",
    "do i have any", "did i get any", "did i receive any", "got any",
    "anything from",
)

_SENDER_MARKERS = (
    "mail from", "email from", "emails from", "messages from",
    "message from", "anything from",
)

_TIME_KEYS = (
    "today", "yesterday", "this week", "last week", "this month",
    "last month", "past week", "past month",
)

_MAIL_ONLY_ACTION_VERBS = (
    "archive",
    "unflag", "unstar",
    "mark as read", "mark as unread", "mark read", "mark unread",
    "reply to", "reply-all", "reply all", "reply with",
    "send the draft", "send draft", "send it", "send this", "send this draft",
    "snooze",
)

_AMBIGUOUS_ACTION_VERBS = (
    "delete", "trash", "remove this", "remove that",
    "flag this", "flag that", "star this", "star that",
    "move to", "move it to",
    "forward this", "forward that", "forward it",
)

_DRAFTING_VERBS = (
    "draft", "compose", "write an email", "write a mail", "write me an email",
    "write me a mail", "create a draft", "save as draft",
)

_SEND_DRAFT_PHRASES = (
    "send it",
    "send the draft",
    "send draft",
    "send this draft",
    "send this email",
    "send this",
    "go ahead and send",
    "yes send",
    "yes, send",
)


def _has_send_draft_intent(low: str) -> bool:
    """True for any phrasing that means 'send the previously-created draft'."""
    if _contains_any(low, _SEND_DRAFT_PHRASES):
        return True
    if "send" in low and "draft" in low:
        return True
    return False

_ORDINAL_MAPPING: Tuple[Tuple[str, str], ...] = (
    ("most recent", "latest"),
    ("this email", "this"),
    ("that email", "this"),
    ("this message", "this"),
    ("that message", "this"),
    ("this one", "this"),
    ("that one", "this"),
    ("latest", "latest"),
    ("newest", "latest"),
    ("first", "first"),
    ("1st", "first"),
    ("second", "second"),
    ("2nd", "second"),
    ("third", "third"),
    ("3rd", "third"),
    ("fourth", "fourth"),
    ("4th", "fourth"),
    ("fifth", "fifth"),
    ("5th", "fifth"),
    ("last", "latest"),
)


def _contains_any(low: str, needles: Tuple[str, ...]) -> bool:
    return any(n in low for n in needles)


def _has_mail_context(low: str) -> bool:
    if _contains_any(low, _MAIL_NOUNS):
        return True
    if "drafts" in low or "sent items" in low:
        return True
    if _contains_any(low, _SENDER_MARKERS):
        return True
    return False


def _extract_ordinal(low: str) -> Optional[str]:
    for needle, ref in _ORDINAL_MAPPING:
        if needle in low:
            return ref
    return None


def _is_summary(low: str) -> bool:
    if _contains_any(low, _SUMMARY_KEYS):
        if _has_mail_context(low):
            return True
        if "unread" in low or "flagged" in low or "starred" in low:
            return True
        if " my " in f" {low} " or low.startswith("my "):
            return True
    return False


def _is_query(low: str) -> bool:
    if _contains_any(low, _SENDER_MARKERS):
        return True
    if "unread" in low and _has_mail_context(low):
        return True
    if ("flagged" in low or "starred" in low) and _has_mail_context(low):
        return True
    if not _has_mail_context(low):
        return False
    if _contains_any(low, _QUERY_VERBS):
        return True
    if _contains_any(low, _TIME_KEYS):
        return True
    if low.startswith("what emails") or low.startswith("which emails") or low.startswith("what mail"):
        return True
    return False


def _is_action(low: str) -> bool:
    if _has_send_draft_intent(low):
        return True
    if _contains_any(low, _MAIL_ONLY_ACTION_VERBS):
        return True
    if not _contains_any(low, _AMBIGUOUS_ACTION_VERBS):
        return False
    return _has_mail_context(low) or _extract_ordinal(low) is not None or "draft" in low


def _is_drafting(low: str) -> bool:
    if "drafts folder" in low or "show drafts" in low or "show me drafts" in low:
        return False
    if "list drafts" in low or "find drafts" in low or "search drafts" in low:
        return False
    return _contains_any(low, _DRAFTING_VERBS)


def _pick_query_tool(low: str, raw: str, *, semantic: bool) -> Tuple[str, Dict[str, Any]]:
    if "unread" in low:
        return "outlook_get_unread_emails", {"page_size": 20}
    if "flag" in low or "starred" in low:
        return "outlook_get_flagged_emails", {"page_size": 20}

    sender_signal = _contains_any(low, _SENDER_MARKERS) or low.startswith("from ")
    if sender_signal and semantic:
        return "outlook_find_messages", {"query": raw, "page_size": 15}

    if (
        "my inbox" in low
        or low.startswith("show inbox")
        or low.startswith("show my inbox")
        or low.startswith("list emails")
        or low.startswith("show emails")
        or low.startswith("show me emails")
    ):
        return "outlook_get_emails", {"page_size": 15}

    if _contains_any(low, _TIME_KEYS):
        return "outlook_get_emails", {"page_size": 25}

    if semantic:
        return "outlook_find_messages", {"query": raw, "page_size": 15}
    return "outlook_get_emails", {"page_size": 15}


def _env_flag(name: str, default: bool = True) -> bool:
    raw = (os.getenv(name) or "").strip().lower()
    if not raw:
        return default
    return raw not in ("0", "false", "no", "off")


def classify_intent(message: str) -> RouteDecision:
    """Deterministic classifier — used by the agent loop to decide tool-first vs agentic mode."""
    raw = (message or "").strip()
    low = raw.lower()

    semantic_tools = _env_flag("ENABLE_SEMANTIC_TOOLS", True)

    if not low:
        return RouteDecision(
            intent=INTENT_GENERAL_CHAT,
            requires_tools=False,
            recommended_tool=None,
            mode=MODE_AGENTIC,
            reason="empty message",
        )

    if _is_summary(low):
        tool = "summarize_mailbox" if semantic_tools else "outlook_get_emails"
        args: Dict[str, Any] = (
            {"query": raw, "max_emails": 15}
            if tool == "summarize_mailbox"
            else {"page_size": 20}
        )
        return RouteDecision(
            intent=INTENT_MAILBOX_SUMMARY,
            requires_tools=True,
            recommended_tool=tool,
            recommended_args=args,
            mode=MODE_TOOL_FIRST,
            reason="summary keyword + mailbox context",
        )

    if _is_action(low):
        if _has_send_draft_intent(low):
            return RouteDecision(
                intent=INTENT_MAILBOX_ACTION,
                requires_tools=True,
                recommended_tool=None,
                mode=MODE_TOOL_FIRST,
                reason="send-draft phrase — recover draft_id from session history, deterministic send",
            )
        ord_ref = _extract_ordinal(low)
        if ord_ref:
            return RouteDecision(
                intent=INTENT_MAILBOX_ACTION,
                requires_tools=True,
                recommended_tool="resolve_email_id",
                recommended_args={"reference": ord_ref},
                mode=MODE_TOOL_FIRST,
                reason=f"action verb with ordinal reference '{ord_ref}'",
            )
        return RouteDecision(
            intent=INTENT_MAILBOX_ACTION,
            requires_tools=True,
            recommended_tool="outlook_get_emails",
            recommended_args={"page_size": 25},
            mode=MODE_TOOL_FIRST,
            reason="action verb without specific reference — fetching recent inbox for grounding",
        )

    if _is_query(low):
        tool, args = _pick_query_tool(low, raw, semantic=semantic_tools)
        return RouteDecision(
            intent=INTENT_MAILBOX_QUERY,
            requires_tools=True,
            recommended_tool=tool,
            recommended_args=args,
            mode=MODE_TOOL_FIRST,
            reason="mailbox query keyword + mail context",
        )

    if _is_drafting(low):
        return RouteDecision(
            intent=INTENT_DRAFTING,
            requires_tools=False,
            recommended_tool=None,
            mode=MODE_AGENTIC,
            reason="drafting verb — free LLM generation, tools optional",
        )

    return RouteDecision(
        intent=INTENT_GENERAL_CHAT,
        requires_tools=False,
        recommended_tool=None,
        mode=MODE_AGENTIC,
        reason="no mailbox intent detected",
    )
