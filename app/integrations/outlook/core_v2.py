from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional
import re

from .core import OutlookGraphClient
from .utils import EmailAmbiguityError, EmailNotFoundError, OutlookError, pick_first, GLOBAL_CONTEXT, validate_email_address


@dataclass
class ResolveHints:
    subject: Optional[str] = None
    from_address: Optional[str] = None
    received_after_iso: Optional[str] = None
    received_before_iso: Optional[str] = None


class OutlookGraphClientV2:
    """
    "V2" helper methods that make tools usable without requiring explicit IDs.
    """

    def __init__(self, core: OutlookGraphClient) -> None:
        self.core = core

    def resolve_email_id(
        self,
        reference: str,
        *,
        top: int = 5,
        prefer_unread: bool = True,
    ) -> Dict[str, Any]:
        """
        Returns {"id": "...", "candidates": [...]}.
        """
        ref = (reference or "").strip().lower()
        ctx = GLOBAL_CONTEXT.get()

        # Check context-pointer phrases BEFORE any stripping
        if ref in ("this", "that", "it", "this email", "that email", "this one",
                   "that one", "current email", "current", "the email"):
            if ctx.last_viewed_ids:
                return {"id": ctx.last_viewed_ids[0], "chosen": {"id": ctx.last_viewed_ids[0]}, "candidates": []}
            raise EmailNotFoundError("No current email in context. View an email first.")

        # Strip filler words so "the first email", "first one", "#1" etc. all resolve correctly
        ref = re.sub(r"\b(the|an?|that|this)\b", "", ref).strip()
        ref = re.sub(r"\b(email|message|mail|one|item)\b", "", ref).strip()
        ref = re.sub(r"\s+", " ", ref).strip()

        # numeric shorthand: "1", "2", "#1", "number 1"
        num_match = re.fullmatch(r"#?(\d+)", ref) or re.fullmatch(r"number\s*(\d+)", ref)
        if num_match:
            idx = int(num_match.group(1)) - 1
            if 0 <= idx < len(ctx.last_email_list):
                chosen = ctx.last_email_list[idx]
                return {"id": str(chosen["id"]), "chosen": chosen, "candidates": ctx.last_email_list}
            raise EmailNotFoundError(f"No email at position {idx + 1} in the last list.")

        # ordinal references based on last list
        ord_map = {
            "first": 1, "1st": 1,
            "second": 2, "2nd": 2,
            "third": 3, "3rd": 3,
            "fourth": 4, "4th": 4,
            "fifth": 5, "5th": 5,
            "sixth": 6, "6th": 6,
        }
        if ref in ord_map:
            idx = ord_map[ref] - 1
            if 0 <= idx < len(ctx.last_email_list):
                chosen = ctx.last_email_list[idx]
                return {"id": str(chosen["id"]), "chosen": chosen, "candidates": ctx.last_email_list}
            raise EmailNotFoundError(f"No {ref} email in the last list.")

        if ref in ("latest", "last"):
            emails = self.core.outlook_get_emails(page_size=top).get("emails", [])
            if not emails:
                raise EmailNotFoundError("No emails found.")
            chosen = emails[0]
            return {"id": str(chosen["id"]), "chosen": chosen, "candidates": emails}

        if "latest unread" in ref or ref == "unread" or "unread email" in ref:
            emails = self.core.outlook_get_unread_emails(page_size=top).get("emails", [])
            if not emails:
                raise EmailNotFoundError("No unread emails found.")
            chosen = emails[0]
            return {"id": str(chosen["id"]), "chosen": chosen, "candidates": emails}

        m = re.search(r"email from\s+(.+)$", ref)
        if m:
            sender = validate_email_address(m.group(1).strip())
            emails = self.core.outlook_filter_emails_by_sender(sender, page_size=top).get("emails", [])
            if not emails:
                raise EmailNotFoundError(f"No emails found from {sender}.")
            return {"id": str(emails[0]["id"]), "chosen": emails[0], "candidates": emails}

        # subject-based / general search
        candidates = self.core.outlook_search_emails(reference, top=top)
        if not candidates:
            raise EmailNotFoundError(f"No emails found for reference: {reference!r}")

        chosen = candidates[0]
        if prefer_unread:
            unread = next((c for c in candidates if not c.get("isRead", False)), None)
            if unread:
                chosen = unread
        # If many candidates and none is a clear "best", surface ambiguity for orchestrator.
        if len(candidates) >= 3 and (candidates[0].get("subject") != chosen.get("subject")):
            raise EmailAmbiguityError(f"Ambiguous reference {reference!r}. Please be more specific.")
        return {"id": str(chosen["id"]), "chosen": chosen, "candidates": candidates}

    def outlook_email_action(
        self,
        *,
        action: str,
        query: Optional[str] = None,
        email_id: Optional[str] = None,
        comment: str = "",
        to: Optional[List[str]] = None,
        archive_folder_id: Optional[str] = None,
        allow_bulk: bool = False,
    ) -> Dict[str, Any]:
        """
        Generic action wrapper for NL usage.
        Supported actions: reply, forward, delete, archive
        """
        if not email_id:
            if not query:
                raise OutlookError("Provide email_id or query.")
            email_id = self.resolve_email_id(query)["id"]

        action_l = action.strip().lower()
        if action_l == "read":
            email = self.core.outlook_get_email_by_id(email_id)
            return {"ok": True, "action": "read", "id": email_id, "email": email}
        if action_l == "reply":
            self.core.outlook_reply_email(email_id, comment=comment)
            return {"ok": True, "action": "reply", "id": email_id}
        if action_l == "forward":
            self.core.outlook_forward_email(email_id, to=to or [], comment=comment)
            return {"ok": True, "action": "forward", "id": email_id}
        if action_l == "delete":
            # prevent accidental multi-delete by only allowing one id here.
            self.core.outlook_delete_emails([email_id], allow_bulk=allow_bulk)
            return {"ok": True, "action": "delete", "id": email_id}
        if action_l == "archive":
            moved = self.core.outlook_archive_email(email_id, archive_folder_id=archive_folder_id)
            return {"ok": True, "action": "archive", "id": email_id, "moved": moved}
        if action_l == "mark_read":
            updated = self.core.outlook_mark_as_read(email_id)
            return {"ok": True, "action": "mark_read", "id": email_id, "result": updated}
        if action_l == "mark_unread":
            updated = self.core.outlook_mark_as_unread(email_id)
            return {"ok": True, "action": "mark_unread", "id": email_id, "result": updated}
        if action_l == "flag":
            updated = self.core.outlook_flag_email(email_id)
            return {"ok": True, "action": "flag", "id": email_id, "result": updated}
        if action_l == "unflag":
            updated = self.core.outlook_unflag_email(email_id)
            return {"ok": True, "action": "unflag", "id": email_id, "result": updated}
        raise OutlookError(f"Unknown action: {action!r}")

    def outlook_email_modify(
        self,
        *,
        modify: str,
        query: Optional[str] = None,
        email_id: Optional[str] = None,
        folder_name: Optional[str] = None,
        add_category: Optional[str] = None,
        remove_category: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Supported modifies: mark_read, mark_unread, flag, unflag, move, add_category, remove_category
        """
        if not email_id:
            if not query:
                raise OutlookError("Provide email_id or query.")
            email_id = self.resolve_email_id(query)["id"]

        m = modify.strip().lower()
        if m in ("mark_read", "read"):
            updated = self.core.outlook_mark_as_read(email_id)
            return {"ok": True, "modify": "mark_read", "id": email_id, "result": updated}
        if m in ("mark_unread", "unread"):
            updated = self.core.outlook_mark_as_unread(email_id)
            return {"ok": True, "modify": "mark_unread", "id": email_id, "result": updated}
        if m == "flag":
            updated = self.core.outlook_flag_email(email_id)
            return {"ok": True, "modify": "flag", "id": email_id, "result": updated}
        if m == "unflag":
            updated = self.core.outlook_unflag_email(email_id)
            return {"ok": True, "modify": "unflag", "id": email_id, "result": updated}
        if m == "move":
            if not folder_name:
                raise OutlookError("folder_name is required for modify=move")
            moved = self.core.outlook_move_to_folder_name(email_id, folder_name=folder_name)
            return {"ok": True, "modify": "move", "id": email_id, "moved": moved}
        if m == "add_category":
            if not add_category:
                raise OutlookError("add_category is required for modify=add_category")
            updated = self.core.outlook_add_category(email_id, add_category)
            return {"ok": True, "modify": "add_category", "id": email_id, "result": updated}
        if m == "remove_category":
            if not remove_category:
                raise OutlookError("remove_category is required for modify=remove_category")
            updated = self.core.outlook_remove_category(email_id, remove_category)
            return {"ok": True, "modify": "remove_category", "id": email_id, "result": updated}
        raise OutlookError(f"Unknown modify: {modify!r}")

    def outlook_email_generate(self, *, prompt: str) -> Dict[str, Any]:
        # Simple placeholder to be powered by ai.py; keep in v2 for a unified surface.
        return {"prompt": prompt}

    def outlook_email_analyze(self, *, email: Dict[str, Any]) -> Dict[str, Any]:
        # Light, deterministic analysis without an LLM dependency.
        subject = (email.get("subject") or "").strip()
        sender = pick_first(email.get("from", {}).get("emailAddress", {}), "address")
        importance = email.get("importance")
        has_attachments = bool(email.get("hasAttachments"))
        return {
            "subject": subject,
            "from": sender,
            "importance": importance,
            "hasAttachments": has_attachments,
            "isRead": email.get("isRead"),
        }
