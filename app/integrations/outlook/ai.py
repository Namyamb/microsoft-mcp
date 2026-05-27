from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import requests

from .utils import OutlookError, env


@dataclass
class LMStudioConfig:
    base_url: str = "http://localhost:1234/v1"
    api_key: str = "lm-studio"  # LM Studio ignores it by default, but keep OpenAI-compatible shape.
    model: str = "local-model"
    timeout_s: int = 60


class LMStudioClient:
    """
    Minimal OpenAI-compatible chat client for LM Studio.
    """

    def __init__(self, cfg: Optional[LMStudioConfig] = None, *, session: Optional[requests.Session] = None) -> None:
        self.cfg = cfg or LMStudioConfig(
            base_url=env("LMSTUDIO_BASE_URL", "http://localhost:1234/v1") or "http://localhost:1234/v1",
            api_key=env("LMSTUDIO_API_KEY", "lm-studio") or "lm-studio",
            model=env("LMSTUDIO_MODEL", "local-model") or "local-model",
        )
        self._session = session or requests.Session()

    def chat(self, messages: List[Dict[str, str]], *, temperature: float = 0.2) -> str:
        url = f"{self.cfg.base_url}/chat/completions"
        headers = {"Authorization": f"Bearer {self.cfg.api_key}", "Content-Type": "application/json"}
        payload: Dict[str, Any] = {
            "model": self.cfg.model,
            "messages": messages,
            "temperature": temperature,
        }
        resp = self._session.post(url, headers=headers, json=payload, timeout=self.cfg.timeout_s)
        if resp.status_code >= 400:
            raise OutlookError(f"LM Studio error {resp.status_code}: {resp.text}")
        data = resp.json()
        try:
            return str(data["choices"][0]["message"]["content"])
        except Exception as e:  # noqa: BLE001
            raise OutlookError(f"Unexpected LM Studio response: {data}") from e


def summarize_email(llm: LMStudioClient, *, subject: str, sender: str, preview: str) -> str:
    return llm.chat(
        [
            {"role": "system", "content": "Summarize the email succinctly in 2-4 bullet points."},
            {"role": "user", "content": f"From: {sender}\nSubject: {subject}\nPreview: {preview}"},
        ]
    )


def classify_email(llm: LMStudioClient, *, subject: str, preview: str) -> str:
    return llm.chat(
        [
            {"role": "system", "content": "Classify the email into one label: work, personal, finance, promo, spam, other."},
            {"role": "user", "content": f"Subject: {subject}\nPreview: {preview}"},
        ]
    )


def detect_urgency(llm: LMStudioClient, *, subject: str, preview: str) -> str:
    return llm.chat(
        [
            {"role": "system", "content": "Return urgency as one of: low, medium, high. Output only the label."},
            {"role": "user", "content": f"Subject: {subject}\nPreview: {preview}"},
        ]
    )


def detect_action_required(llm: LMStudioClient, *, preview: str) -> str:
    return llm.chat(
        [
            {"role": "system", "content": "Answer with yes or no: does this email require action from the recipient? Output only yes/no."},
            {"role": "user", "content": preview},
        ]
    )


def sentiment_analysis(llm: LMStudioClient, *, preview: str) -> str:
    return llm.chat(
        [
            {"role": "system", "content": "Return sentiment as one of: negative, neutral, positive. Output only the label."},
            {"role": "user", "content": preview},
        ]
    )


def extract_tasks(llm: LMStudioClient, *, preview: str) -> str:
    return llm.chat(
        [
            {"role": "system", "content": "Extract action items as a short checklist. If none, say 'No action items'."},
            {"role": "user", "content": preview},
        ]
    )


def extract_dates(llm: LMStudioClient, *, preview: str) -> str:
    return llm.chat(
        [
            {"role": "system", "content": "Extract all mentioned dates/times as a JSON array of strings. If none, return [] only."},
            {"role": "user", "content": preview},
        ]
    )


def extract_contacts(llm: LMStudioClient, *, preview: str) -> str:
    return llm.chat(
        [
            {"role": "system", "content": "Extract people/contacts mentioned as a JSON array of strings. If none, return [] only."},
            {"role": "user", "content": preview},
        ]
    )


def extract_links(llm: LMStudioClient, *, preview: str) -> str:
    return llm.chat(
        [
            {"role": "system", "content": "Extract URLs as a JSON array of strings. If none, return [] only."},
            {"role": "user", "content": preview},
        ]
    )


def draft_reply(llm: LMStudioClient, *, subject: str, sender: str, preview: str, tone: str = "professional") -> str:
    return llm.chat(
        [
            {"role": "system", "content": f"Draft a {tone} reply email. Keep it concise and specific."},
            {"role": "user", "content": f"From: {sender}\nSubject: {subject}\nEmail: {preview}"},
        ],
        temperature=0.4,
    )


def generate_followup(llm: LMStudioClient, *, subject: str, recipient: str, context: str) -> str:
    return llm.chat(
        [
            {"role": "system", "content": "Draft a concise follow-up email. Be polite and specific."},
            {"role": "user", "content": f"To: {recipient}\nSubject: {subject}\nContext: {context}"},
        ],
        temperature=0.4,
    )


def auto_reply(llm: LMStudioClient, *, subject: str, sender: str, preview: str) -> str:
    return llm.chat(
        [
            {"role": "system", "content": "Draft a short automatic reply acknowledging receipt and next steps if possible."},
            {"role": "user", "content": f"From: {sender}\nSubject: {subject}\nEmail: {preview}"},
        ],
        temperature=0.4,
    )


def rewrite_email(llm: LMStudioClient, *, draft: str, style: str = "clear and professional") -> str:
    return llm.chat(
        [
            {"role": "system", "content": f"Rewrite the email in a {style} style. Preserve meaning."},
            {"role": "user", "content": draft},
        ],
        temperature=0.3,
    )


def translate_email(llm: LMStudioClient, *, text: str, language: str) -> str:
    return llm.chat(
        [
            {"role": "system", "content": f"Translate the email to {language}. Keep formatting simple."},
            {"role": "user", "content": text},
        ],
        temperature=0.2,
    )


# ==============================
# Bulk AI helpers (orchestrator-friendly)
# ==============================


def summarize_emails(llm: LMStudioClient, *, emails: List[Dict[str, str]]) -> str:
    # emails: [{"subject":..., "sender":..., "preview":...}, ...]
    content = "\n\n".join(
        [f"[{i+1}] From: {e.get('sender')}\nSubject: {e.get('subject')}\nPreview: {e.get('preview')}" for i, e in enumerate(emails)]
    )
    return llm.chat(
        [
            {"role": "system", "content": "Summarize each email in 1 bullet. Output a numbered list."},
            {"role": "user", "content": content},
        ]
    )


def _graph_message_to_snippet(m: Dict[str, Any]) -> Dict[str, str]:
    """Turn a Graph message dict into a small text bundle for the LLM."""
    from_addr = (m.get("from") or {}).get("emailAddress") or {}
    name = (from_addr.get("name") or "").strip()
    addr = (from_addr.get("address") or "").strip()
    if name and addr:
        sender = f"{name} <{addr}>"
    else:
        sender = addr or name or "?"
    prev = (m.get("bodyPreview") or "").strip()
    if not prev:
        body = m.get("body")
        if isinstance(body, dict):
            prev = (body.get("content") or "").strip()[:8000]
    return {
        "subject": (m.get("subject") or "(no subject)").strip(),
        "sender": sender,
        "preview": prev[:8000],
        "id": str(m.get("id") or ""),
    }


def _emails_from_tool_result(obj: Any) -> List[Dict[str, Any]]:
    if isinstance(obj, list):
        return list(obj)
    if isinstance(obj, dict):
        return list(obj.get("emails") or [])
    return []


def _collect_messages_for_summarize(core: Any, user_query: str, max_emails: int) -> List[Dict[str, Any]]:
    """
    Pick a sensible slice of the mailbox for summarization from free-text intent.
    Uses simple substring checks only (no regex).
    """
    low = user_query.lower()

    if "unread" in low:
        r = core.outlook_get_unread_emails(page_size=max_emails)
        got = _emails_from_tool_result(r)
        if got:
            return got[:max_emails]

    if "flag" in low or "starred" in low:
        r = core.outlook_get_flagged_emails(page_size=max_emails)
        got = _emails_from_tool_result(r)
        if got:
            return got[:max_emails]

    broad_phrases = (
        "summarize my inbox",
        "summary of my inbox",
        "my inbox",
        "entire inbox",
        "whole inbox",
        "all my email",
        "all my emails",
        "all my mail",
        "catch me up",
        "summarize everything",
        "email overview",
        "mail overview",
        "what's new",
        "whats new",
        "recent mail",
        "recent emails",
        "latest mail",
        "latest emails",
    )
    if any(p in low for p in broad_phrases):
        r = core.outlook_get_emails(page_size=max_emails)
        got = _emails_from_tool_result(r)
        if got:
            return got[:max_emails]

    r = core.outlook_find_messages(user_query, page_size=max_emails)
    got = _emails_from_tool_result(r)
    if got:
        return got[:max_emails]
    r2 = core.outlook_get_emails(page_size=max_emails)
    return _emails_from_tool_result(r2)[:max_emails]


def summarize_mailbox(
    llm: LMStudioClient,
    core: Any,
    *,
    query: str,
    max_emails: int = 15,
    email_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    One-shot summarization from natural language: recent inbox, unread, flagged,
    sender/topic-focused (delegates to the same discovery path as mail search), or a single message by id.
    """
    cap = max(1, min(25, int(max_emails or 15)))
    q = (query or "").strip() or "Summarize my recent mailbox."
    eid = (email_id or "").strip()

    if eid:
        msg = core.outlook_get_email_by_id(eid)
        snippets = [_graph_message_to_snippet(msg)]
        n = 1
    else:
        raw = _collect_messages_for_summarize(core, q, cap)
        snippets = [_graph_message_to_snippet(m) for m in raw]
        n = len(snippets)

    if not snippets:
        return {"summary": "No messages were found to summarize.", "email_count": 0}

    blocks: List[str] = []
    for i, s in enumerate(snippets, start=1):
        sid = s.get("id") or ""
        short_id = (sid[:20] + "…") if len(sid) > 20 else sid
        blocks.append(
            f"--- Message {i} (id={short_id})\n"
            f"From: {s['sender']}\nSubject: {s['subject']}\nPreview:\n{s['preview']}\n"
        )
    body = "\n".join(blocks)
    max_ctx = 14000
    if len(body) > max_ctx:
        body = body[:max_ctx] + "\n… (content truncated for the model context limit)"

    user_block = f"The user asked:\n{q}\n\nHere are the messages:\n{body}"
    summary = llm.chat(
        [
            {
                "role": "system",
                "content": (
                    "You are an intelligent mailbox assistant (similar in spirit to inbox briefing tools). "
                    "The user described what they want in their own words — follow that intent: summarize, "
                    "prioritize, extract themes, compare threads, surface deadlines or action items, or give a "
                    "brief overview. Use only the excerpts provided; never invent messages or senders not shown. "
                    "If the excerpts do not match their request, say so briefly."
                ),
            },
            {"role": "user", "content": user_block},
        ],
        temperature=0.3,
    )
    return {"summary": summary, "email_count": n}


def auto_categorize_emails(llm: LMStudioClient, *, emails: List[Dict[str, str]]) -> str:
    content = "\n\n".join([f"[{i+1}] Subject: {e.get('subject')}\nPreview: {e.get('preview')}" for i, e in enumerate(emails)])
    return llm.chat(
        [
            {"role": "system", "content": "Assign a category for each email (work/personal/finance/promo/spam/other). Return JSON object mapping index->category."},
            {"role": "user", "content": content},
        ]
    )


def auto_archive_promotions(llm: LMStudioClient, *, emails: List[Dict[str, str]]) -> str:
    content = "\n\n".join([f"[{i+1}] Subject: {e.get('subject')}\nPreview: {e.get('preview')}" for i, e in enumerate(emails)])
    return llm.chat(
        [
            {"role": "system", "content": "Decide which emails are promotions and should be archived. Return JSON array of indexes to archive."},
            {"role": "user", "content": content},
        ]
    )


def auto_reply_rules(llm: LMStudioClient, *, emails: List[Dict[str, str]], rule: str) -> str:
    content = "\n\n".join(
        [f"[{i+1}] From: {e.get('sender')}\nSubject: {e.get('subject')}\nPreview: {e.get('preview')}" for i, e in enumerate(emails)]
    )
    return llm.chat(
        [
            {"role": "system", "content": f"Apply this auto-reply rule: {rule}. Return JSON object mapping index->draft_reply (or null if no reply)."},
            {"role": "user", "content": content},
        ],
        temperature=0.4,
    )
