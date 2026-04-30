from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional
from urllib.parse import urlparse, parse_qs

import requests
from msal import PublicClientApplication, SerializableTokenCache

from .utils import (
    EmailPermissionError,
    EmailRateLimitError,
    EmailSafetyError,
    EmailValidationError,
    OutlookError,
    RetryConfig,
    backoff_sleep,
    check_batch_safety,
    check_send_safety,
    to_graph_query_params,
    validate_email_address,
    GLOBAL_CONTEXT,
)


GRAPH_BASE = "https://graph.microsoft.com/v1.0"
DEFAULT_AUTHORITY = "https://login.microsoftonline.com/common"
DEFAULT_SCOPES = ["Mail.Read", "Mail.Send", "User.Read"]


@dataclass
class OutlookAuthConfig:
    client_id: str
    authority: str = DEFAULT_AUTHORITY
    scopes: List[str] = None  # type: ignore[assignment]
    token_cache_path: str = ".outlook_msal_token_cache.bin"
    sender_email: Optional[str] = None

    def __post_init__(self) -> None:
        if self.scopes is None:
            self.scopes = list(DEFAULT_SCOPES)


class OutlookGraphClient:
    def __init__(
        self,
        auth: OutlookAuthConfig,
        *,
        session: Optional[requests.Session] = None,
        retry: RetryConfig = RetryConfig(),
        user_agent: str = "outlook-mcp/1.0",
    ) -> None:
        self._auth = auth
        self._retry = retry
        self._session = session or requests.Session()
        self._session.headers.update({"User-Agent": user_agent})

        self._cache = SerializableTokenCache()
        if os.path.exists(auth.token_cache_path):
            self._cache.deserialize(open(auth.token_cache_path, "r", encoding="utf-8").read())

        self._app = PublicClientApplication(
            auth.client_id,
            authority=auth.authority,
            token_cache=self._cache,
        )

    def _save_cache(self) -> None:
        if self._cache.has_state_changed:
            with open(self._auth.token_cache_path, "w", encoding="utf-8") as f:
                f.write(self._cache.serialize())

    def acquire_token(self) -> str:
        accounts = self._app.get_accounts()
        result: Dict[str, Any] | None = None
        if accounts:
            result = self._app.acquire_token_silent(self._auth.scopes, account=accounts[0])
        if not result:
            # Device code flow is more production-friendly than interactive browser popups.
            flow = self._app.initiate_device_flow(scopes=self._auth.scopes)
            if "user_code" not in flow:
                raise OutlookError(f"Failed to initiate device flow: {flow}")
            print(flow["message"])  # user-facing device code instructions
            result = self._app.acquire_token_by_device_flow(flow)

        if not result or "access_token" not in result:
            raise OutlookError(f"Token acquisition failed: {result}")

        self._save_cache()
        return str(result["access_token"])

    # Compatibility with prompt naming
    def get_access_token(self) -> str:
        return self.acquire_token()

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        url = f"{GRAPH_BASE}{path}"
        token = self.acquire_token()
        merged_headers = {"Authorization": f"Bearer {token}"}
        if headers:
            merged_headers.update(headers)
        q = to_graph_query_params(params or {})

        last_error: Optional[str] = None
        for attempt in range(1, self._retry.max_attempts + 1):
            resp = self._session.request(method, url, params=q, json=json, headers=merged_headers, timeout=30)
            if resp.status_code == 401 or resp.status_code == 403:
                raise EmailPermissionError(resp.text)
            if resp.status_code in (429, 500, 502, 503, 504):
                last_error = resp.text
                if resp.status_code == 429:
                    # Surface as a typed error if we ultimately fail.
                    last_error = resp.text
                backoff_sleep(attempt, self._retry)
                continue
            if resp.status_code >= 400:
                raise OutlookError(f"Graph error {resp.status_code}: {resp.text}")
            if resp.status_code == 204:
                return {}
            if resp.text.strip() == "":
                return {}
            return resp.json()

        raise OutlookError(f"Graph request failed after retries: {last_error}")

    def _request_abs(
        self,
        method: str,
        abs_url: str,
        *,
        json: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        token = self.acquire_token()
        merged_headers = {"Authorization": f"Bearer {token}"}
        if headers:
            merged_headers.update(headers)
        last_error: Optional[str] = None
        for attempt in range(1, self._retry.max_attempts + 1):
            resp = self._session.request(method, abs_url, json=json, headers=merged_headers, timeout=30)
            if resp.status_code == 401 or resp.status_code == 403:
                raise EmailPermissionError(resp.text)
            if resp.status_code in (429, 500, 502, 503, 504):
                last_error = resp.text
                backoff_sleep(attempt, self._retry)
                continue
            if resp.status_code >= 400:
                raise OutlookError(f"Graph error {resp.status_code}: {resp.text}")
            if resp.status_code == 204 or resp.text.strip() == "":
                return {}
            return resp.json()
        if last_error and "429" in last_error:
            raise EmailRateLimitError(last_error)
        raise OutlookError(f"Graph request failed after retries: {last_error}")

    def _next_token_from_nextlink(self, next_link: Optional[str]) -> Optional[str]:
        if not next_link:
            return None
        try:
            parsed = urlparse(next_link)
            qs = parse_qs(parsed.query)
            # Prefer $skiptoken; fall back to $skip.
            if "$skiptoken" in qs and qs["$skiptoken"]:
                return qs["$skiptoken"][0]
            if "$skip" in qs and qs["$skip"]:
                return qs["$skip"][0]
        except Exception:
            return next_link
        return next_link

    def _paged_messages(
        self,
        *,
        page_size: int,
        next_token: Optional[str],
        select: str,
        orderby: str,
        filter_expr: Optional[str] = None,
    ) -> Dict[str, Any]:
        params: Dict[str, Any] = {"$top": page_size, "$select": select, "$orderby": orderby}
        if filter_expr:
            params["$filter"] = filter_expr
        if next_token:
            # If next_token is an absolute nextLink, just request it directly.
            if next_token.startswith("https://"):
                data = self._request_abs("GET", next_token)
            else:
                # Graph uses $skiptoken in nextLink; accept raw token or skip.
                params["$skiptoken"] = next_token
                data = self._request("GET", "/me/messages", params=params)
        else:
            data = self._request("GET", "/me/messages", params=params)

        emails = list(data.get("value", []))
        GLOBAL_CONTEXT.set_last_email_list(emails)
        next_link = data.get("@odata.nextLink")
        return {"emails": emails, "next_token": self._next_token_from_nextlink(next_link), "next_link": next_link}

    # ==============================
    # Read
    # ==============================
    def outlook_get_emails(
        self,
        *,
        page_size: int = 20,
        next_token: Optional[str] = None,
        select: str = "id,subject,from,receivedDateTime,isRead,hasAttachments,importance,bodyPreview",
        orderby: str = "receivedDateTime desc",
    ) -> Dict[str, Any]:
        return self._paged_messages(page_size=page_size, next_token=next_token, select=select, orderby=orderby)

    def outlook_get_email_by_id(
        self,
        email_id: str,
        *,
        select: str = "id,subject,from,toRecipients,ccRecipients,bccRecipients,receivedDateTime,isRead,hasAttachments,importance,body,bodyPreview",
    ) -> Dict[str, Any]:
        email = self._request("GET", f"/me/messages/{email_id}", params={"$select": select})
        if "id" in email:
            GLOBAL_CONTEXT.push_viewed_id(str(email["id"]))
        return email

    def outlook_get_unread_emails(self, *, page_size: int = 20, next_token: Optional[str] = None) -> Dict[str, Any]:
        return self._paged_messages(
            page_size=page_size,
            next_token=next_token,
            select="id,subject,from,receivedDateTime,isRead,hasAttachments,importance,bodyPreview",
            orderby="receivedDateTime desc",
            filter_expr="isRead eq false",
        )

    def outlook_get_flagged_emails(self, *, page_size: int = 20, next_token: Optional[str] = None) -> Dict[str, Any]:
        return self._paged_messages(
            page_size=page_size,
            next_token=next_token,
            select="id,subject,from,receivedDateTime,isRead,hasAttachments,importance,bodyPreview",
            orderby="receivedDateTime desc",
            filter_expr="flag/flagStatus eq 'flagged'",
        )

    def outlook_search_emails(
        self,
        query: str,
        *,
        top: int = 10,
        select: str = "id,subject,from,receivedDateTime,isRead,hasAttachments,importance,bodyPreview",
    ) -> List[Dict[str, Any]]:
        # Graph supports $search with special header.
        data = self._request(
            "GET",
            "/me/messages",
            params={"$search": f"\"{query}\"", "$top": top, "$select": select},
            headers={"ConsistencyLevel": "eventual"},
        )
        return list(data.get("value", []))

    def outlook_filter_emails_by_sender(self, sender: str, *, page_size: int = 20, next_token: Optional[str] = None) -> Dict[str, Any]:
        sender = validate_email_address(sender)
        # from/emailAddress/address isn't filterable in all tenants; use substring match on from.
        # Keep conservative: use contains() on from/emailAddress/address when supported.
        filter_expr = f"from/emailAddress/address eq '{sender}'"
        return self._paged_messages(
            page_size=page_size,
            next_token=next_token,
            select="id,subject,from,receivedDateTime,isRead,hasAttachments,importance,bodyPreview",
            orderby="receivedDateTime desc",
            filter_expr=filter_expr,
        )

    def outlook_filter_emails_by_date(
        self,
        start: str,
        end: str,
        *,
        page_size: int = 20,
        next_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        # Expect ISO-8601 strings, e.g. 2026-04-29T00:00:00Z
        filter_expr = f"receivedDateTime ge {start} and receivedDateTime le {end}"
        return self._paged_messages(
            page_size=page_size,
            next_token=next_token,
            select="id,subject,from,receivedDateTime,isRead,hasAttachments,importance,bodyPreview",
            orderby="receivedDateTime desc",
            filter_expr=filter_expr,
        )

    # ==============================
    # Send / Draft
    # ==============================
    def outlook_send_email(
        self,
        *,
        to: List[str],
        subject: str,
        body: str,
        cc: Optional[List[str]] = None,
        bcc: Optional[List[str]] = None,
        content_type: str = "Text",
    ) -> None:
        check_send_safety(to=to, subject=subject, body=body)
        to_recipients = [{"emailAddress": {"address": validate_email_address(a)}} for a in to]
        cc_recipients = [{"emailAddress": {"address": validate_email_address(a)}} for a in (cc or [])]
        bcc_recipients = [{"emailAddress": {"address": validate_email_address(a)}} for a in (bcc or [])]
        msg: Dict[str, Any] = {
            "subject": subject,
            "body": {"contentType": content_type, "content": body},
            "toRecipients": to_recipients,
        }
        if self._auth.sender_email:
            msg["from"] = {"emailAddress": {"address": self._auth.sender_email}}
        if cc_recipients:
            msg["ccRecipients"] = cc_recipients
        if bcc_recipients:
            msg["bccRecipients"] = bcc_recipients

        self._request("POST", "/me/sendMail", json={"message": msg, "saveToSentItems": True})

    def outlook_create_draft(
        self,
        *,
        to: List[str],
        subject: str,
        body: str,
        content_type: str = "Text",
    ) -> Dict[str, Any]:
        check_send_safety(to=to, subject=subject, body=body)
        to_recipients = [{"emailAddress": {"address": validate_email_address(a)}} for a in to]
        draft_body: Dict[str, Any] = {
            "subject": subject,
            "body": {"contentType": content_type, "content": body},
            "toRecipients": to_recipients,
        }
        if self._auth.sender_email:
            draft_body["from"] = {"emailAddress": {"address": self._auth.sender_email}}
        draft = self._request(
            "POST",
            "/me/messages",
            json=draft_body,
        )
        return draft

    def outlook_send_draft(self, draft_id: str) -> None:
        self._request("POST", f"/me/messages/{draft_id}/send")

    def outlook_update_draft(self, draft_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        # Expect Graph message patch payload; caller provides safe subset.
        return self._request("PATCH", f"/me/messages/{draft_id}", json=updates)

    def outlook_delete_draft(self, draft_id: str) -> None:
        self.outlook_delete_email(draft_id)

    # ==============================
    # Reply / Forward
    # ==============================
    def outlook_reply_email(self, email_id: str, *, comment: str) -> None:
        self._request("POST", f"/me/messages/{email_id}/reply", json={"comment": comment})

    def outlook_reply_all(self, email_id: str, *, comment: str) -> None:
        self._request("POST", f"/me/messages/{email_id}/replyAll", json={"comment": comment})

    def outlook_forward_email(self, email_id: str, *, to: List[str], comment: str = "") -> None:
        to_recipients = [{"emailAddress": {"address": validate_email_address(a)}} for a in to]
        self._request(
            "POST",
            f"/me/messages/{email_id}/forward",
            json={"comment": comment, "toRecipients": to_recipients},
        )

    # ==============================
    # Organization
    # ==============================
    def outlook_delete_email(self, email_id: str) -> None:
        self._request("DELETE", f"/me/messages/{email_id}")

    def outlook_archive_email(self, email_id: str, *, archive_folder_id: Optional[str] = None) -> Dict[str, Any]:
        # Default Outlook archive folder is typically named "Archive".
        if not archive_folder_id:
            folders = self.outlook_list_folders()
            archive = next((f for f in folders if (f.get("displayName") or "").lower() == "archive"), None)
            if not archive or "id" not in archive:
                raise OutlookError("Archive folder not found. Provide archive_folder_id.")
            archive_folder_id = str(archive["id"])
        return self.outlook_move_to_folder(email_id, folder_id=archive_folder_id)

    def outlook_move_to_folder(self, email_id: str, *, folder_id: str) -> Dict[str, Any]:
        return self._request("POST", f"/me/messages/{email_id}/move", json={"destinationId": folder_id})

    def outlook_move_to_folder_name(self, email_id: str, *, folder_name: str) -> Dict[str, Any]:
        folder_id = self._resolve_folder_id_by_name(folder_name)
        return self.outlook_move_to_folder(email_id, folder_id=folder_id)

    def outlook_restore_email(self, email_id: str) -> Dict[str, Any]:
        # Best-effort restore: move from Deleted Items to Inbox.
        inbox_id = self._resolve_folder_id_by_name("Inbox")
        return self.outlook_move_to_folder(email_id, folder_id=inbox_id)

    # ==============================
    # State / Flags
    # ==============================
    def outlook_mark_as_read(self, email_id: str) -> Dict[str, Any]:
        return self._request("PATCH", f"/me/messages/{email_id}", json={"isRead": True})

    def outlook_mark_as_unread(self, email_id: str) -> Dict[str, Any]:
        return self._request("PATCH", f"/me/messages/{email_id}", json={"isRead": False})

    def outlook_flag_email(self, email_id: str) -> Dict[str, Any]:
        # Minimal followUpFlag structure
        return self._request("PATCH", f"/me/messages/{email_id}", json={"flag": {"flagStatus": "flagged"}})

    def outlook_unflag_email(self, email_id: str) -> Dict[str, Any]:
        return self._request("PATCH", f"/me/messages/{email_id}", json={"flag": {"flagStatus": "notFlagged"}})

    # ==============================
    # Folders
    # ==============================
    def outlook_list_folders(self, *, top: int = 200) -> List[Dict[str, Any]]:
        data = self._request("GET", "/me/mailFolders", params={"$top": top, "$select": "id,displayName,parentFolderId"})
        return list(data.get("value", []))

    def outlook_create_folder(self, *, display_name: str, parent_folder_id: Optional[str] = None) -> Dict[str, Any]:
        path = f"/me/mailFolders/{parent_folder_id}/childFolders" if parent_folder_id else "/me/mailFolders"
        return self._request("POST", path, json={"displayName": display_name})

    def outlook_delete_folder(self, name: str) -> None:
        folder_id = self._resolve_folder_id_by_name(name)
        self._request("DELETE", f"/me/mailFolders/{folder_id}")

    def outlook_move_email_to_folder(self, email_id: str, folder: str) -> Dict[str, Any]:
        return self.outlook_move_to_folder_name(email_id, folder_name=folder)

    def _resolve_folder_id_by_name(self, folder_name: str) -> str:
        target = (folder_name or "").strip().lower()
        folders = self.outlook_list_folders(top=200)
        match = next((f for f in folders if (f.get("displayName") or "").strip().lower() == target), None)
        if not match or "id" not in match:
            raise OutlookError(f"Folder not found: {folder_name!r}")
        return str(match["id"])

    # ==============================
    # Categories
    # ==============================
    def outlook_list_categories(self) -> List[Dict[str, Any]]:
        data = self._request("GET", "/me/outlook/masterCategories")
        return list(data.get("value", []))

    def outlook_add_category(self, email_id: str, category: str) -> Dict[str, Any]:
        msg = self.outlook_get_email_by_id(email_id, select="id,categories")
        categories = list(msg.get("categories") or [])
        if category not in categories:
            categories.append(category)
        return self._request("PATCH", f"/me/messages/{email_id}", json={"categories": categories})

    def outlook_remove_category(self, email_id: str, category: str) -> Dict[str, Any]:
        msg = self.outlook_get_email_by_id(email_id, select="id,categories")
        categories = [c for c in (msg.get("categories") or []) if c != category]
        return self._request("PATCH", f"/me/messages/{email_id}", json={"categories": categories})

    # ==============================
    # Attachments
    # ==============================
    def outlook_get_attachments(self, email_id: str) -> List[Dict[str, Any]]:
        data = self._request("GET", f"/me/messages/{email_id}/attachments")
        return list(data.get("value", []))

    def outlook_download_attachment(self, email_id: str, attachment_id: str) -> Dict[str, Any]:
        # For simple attachments, Graph returns base64 contentBytes.
        return self._request("GET", f"/me/messages/{email_id}/attachments/{attachment_id}")

    def outlook_save_attachment_to_disk(self, email_id: str, attachment_id: str, path: str) -> Dict[str, Any]:
        import base64

        att = self.outlook_download_attachment(email_id, attachment_id)
        content_b64 = att.get("contentBytes")
        if not content_b64:
            raise OutlookError("Attachment contentBytes not present (may be item attachment).")
        data = base64.b64decode(content_b64)
        with open(path, "wb") as f:
            f.write(data)
        return {"path": path, "bytes": len(data), "name": att.get("name")}

    # ==============================
    # Batch helpers (Graph $batch is an option; keep it simple with small batches)
    # ==============================
    def outlook_delete_emails(self, email_ids: Iterable[str], *, allow_bulk: bool = False) -> Dict[str, Any]:
        ids = list(email_ids)
        check_batch_safety(len(ids), allow_bulk=allow_bulk)
        results: Dict[str, Any] = {"deleted": [], "failed": []}
        for email_id in ids:
            try:
                self.outlook_delete_email(email_id)
                results["deleted"].append(email_id)
            except Exception as e:  # noqa: BLE001
                results["failed"].append({"id": email_id, "error": str(e)})
        return results

    def outlook_archive_emails(
        self, email_ids: Iterable[str], *, archive_folder_id: Optional[str] = None, allow_bulk: bool = False
    ) -> Dict[str, Any]:
        ids = list(email_ids)
        check_batch_safety(len(ids), allow_bulk=allow_bulk)
        results: Dict[str, Any] = {"archived": [], "failed": []}
        for email_id in ids:
            try:
                moved = self.outlook_archive_email(email_id, archive_folder_id=archive_folder_id)
                results["archived"].append({"id": email_id, "movedId": moved.get("id")})
            except Exception as e:  # noqa: BLE001
                results["failed"].append({"id": email_id, "error": str(e)})
        return results

    def outlook_mark_emails_read(self, email_ids: Iterable[str], *, allow_bulk: bool = False) -> Dict[str, Any]:
        ids = list(email_ids)
        check_batch_safety(len(ids), allow_bulk=allow_bulk)
        results: Dict[str, Any] = {"marked_read": [], "failed": []}
        for email_id in ids:
            try:
                self.outlook_mark_as_read(email_id)
                results["marked_read"].append(email_id)
            except Exception as e:  # noqa: BLE001
                results["failed"].append({"id": email_id, "error": str(e)})
        return results

    def outlook_flag_emails(self, email_ids: Iterable[str], *, allow_bulk: bool = False) -> Dict[str, Any]:
        ids = list(email_ids)
        check_batch_safety(len(ids), allow_bulk=allow_bulk)
        results: Dict[str, Any] = {"flagged": [], "failed": []}
        for email_id in ids:
            try:
                self.outlook_flag_email(email_id)
                results["flagged"].append(email_id)
            except Exception as e:  # noqa: BLE001
                results["failed"].append({"id": email_id, "error": str(e)})
        return results

    # ==============================
    # Calendar
    # ==============================
    def calendar_get_upcoming_events(self, *, top: int = 10, days_ahead: int = 7) -> List[Dict[str, Any]]:
        from datetime import datetime, timezone, timedelta
        now = datetime.now(timezone.utc)
        end = now + timedelta(days=days_ahead)
        data = self._request(
            "GET",
            "/me/calendarView",
            params={
                "$top": top,
                "$select": "id,subject,start,end,organizer,attendees,isAllDay,location,bodyPreview,importance",
                "$orderby": "start/dateTime",
                "startDateTime": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "endDateTime": end.strftime("%Y-%m-%dT%H:%M:%SZ"),
            },
        )
        return list(data.get("value", []))

    def calendar_get_today_events(self) -> List[Dict[str, Any]]:
        from datetime import datetime, timezone, timedelta
        now = datetime.now(timezone.utc)
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=1)
        data = self._request(
            "GET",
            "/me/calendarView",
            params={
                "$top": 20,
                "$select": "id,subject,start,end,organizer,attendees,isAllDay,location,bodyPreview",
                "$orderby": "start/dateTime",
                "startDateTime": start.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "endDateTime": end.strftime("%Y-%m-%dT%H:%M:%SZ"),
            },
        )
        return list(data.get("value", []))

    def calendar_create_event(
        self,
        *,
        subject: str,
        start_datetime: str,
        end_datetime: str,
        attendees: Optional[List[str]] = None,
        body: Optional[str] = None,
        location: Optional[str] = None,
        is_all_day: bool = False,
        timezone_str: str = "UTC",
    ) -> Dict[str, Any]:
        event: Dict[str, Any] = {
            "subject": subject,
            "start": {"dateTime": start_datetime, "timeZone": timezone_str},
            "end": {"dateTime": end_datetime, "timeZone": timezone_str},
            "isAllDay": is_all_day,
        }
        if attendees:
            event["attendees"] = [
                {"emailAddress": {"address": a}, "type": "required"} for a in attendees
            ]
        if body:
            event["body"] = {"contentType": "Text", "content": body}
        if location:
            event["location"] = {"displayName": location}
        return self._request("POST", "/me/events", json=event)

    def calendar_search_events(self, query: str, *, top: int = 10) -> List[Dict[str, Any]]:
        data = self._request(
            "GET",
            "/me/events",
            params={
                "$search": f'"{query}"',
                "$top": top,
                "$select": "id,subject,start,end,organizer,attendees,isAllDay,location,bodyPreview",
            },
            headers={"ConsistencyLevel": "eventual"},
        )
        return list(data.get("value", []))

    def outlook_move_emails(
        self, email_ids: Iterable[str], *, folder_name: str, allow_bulk: bool = False
    ) -> Dict[str, Any]:
        ids = list(email_ids)
        check_batch_safety(len(ids), allow_bulk=allow_bulk)
        folder_id = self._resolve_folder_id_by_name(folder_name)
        results: Dict[str, Any] = {"moved": [], "failed": []}
        for email_id in ids:
            try:
                moved = self.outlook_move_to_folder(email_id, folder_id=folder_id)
                results["moved"].append({"id": email_id, "movedId": moved.get("id")})
            except Exception as e:  # noqa: BLE001
                results["failed"].append({"id": email_id, "error": str(e)})
        return results
