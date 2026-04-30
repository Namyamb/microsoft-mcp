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
