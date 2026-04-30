from __future__ import annotations

from typing import Any, Callable, Dict, Optional

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from .ai import (
    LMStudioClient,
    classify_email,
    detect_urgency,
    detect_action_required,
    draft_reply,
    generate_followup,
    auto_reply,
    rewrite_email,
    translate_email,
    extract_tasks,
    extract_dates,
    extract_contacts,
    extract_links,
    sentiment_analysis,
    summarize_email,
    summarize_emails,
    auto_categorize_emails,
    auto_archive_promotions,
    auto_reply_rules,
)
from .core import OutlookAuthConfig, OutlookGraphClient
from .core_v2 import OutlookGraphClientV2
from .utils import env, tool_wrapper, log_tool_call, ok, err, GLOBAL_STATS


ToolFn = Callable[..., Any]


def build_default_clients() -> tuple[OutlookGraphClient, OutlookGraphClientV2, LMStudioClient]:
    client_id = env("OUTLOOK_CLIENT_ID")
    if not client_id:
        raise RuntimeError("Missing OUTLOOK_CLIENT_ID env var.")
    auth = OutlookAuthConfig(
        client_id=client_id,
        authority=env("OUTLOOK_AUTHORITY", "https://login.microsoftonline.com/common")
        or "https://login.microsoftonline.com/common",
        scopes=(env("OUTLOOK_SCOPES") or "").split() or ["Mail.Read", "Mail.Send", "User.Read"],
        token_cache_path=env("OUTLOOK_TOKEN_CACHE", ".outlook_msal_token_cache.bin") or ".outlook_msal_token_cache.bin",
        sender_email=env("OUTLOOK_SENDER_EMAIL") or None,
    )
    core = OutlookGraphClient(auth)
    v2 = OutlookGraphClientV2(core)
    llm = LMStudioClient()
    return core, v2, llm


def get_outlook_tools(
    core: Optional[OutlookGraphClient] = None,
    v2: Optional[OutlookGraphClientV2] = None,
    llm: Optional[LMStudioClient] = None,
) -> Dict[str, ToolFn]:
    if core is None or v2 is None or llm is None:
        core, v2, llm = build_default_clients()

    tools: Dict[str, ToolFn] = {
        # Core
        "outlook_get_emails": core.outlook_get_emails,
        "outlook_get_email_by_id": core.outlook_get_email_by_id,
        "outlook_get_unread_emails": core.outlook_get_unread_emails,
        "outlook_get_flagged_emails": core.outlook_get_flagged_emails,
        "outlook_search_emails": core.outlook_search_emails,
        "outlook_filter_emails_by_sender": core.outlook_filter_emails_by_sender,
        "outlook_filter_emails_by_date": core.outlook_filter_emails_by_date,
        "outlook_send_email": core.outlook_send_email,
        "outlook_create_draft": core.outlook_create_draft,
        "outlook_send_draft": core.outlook_send_draft,
        "outlook_update_draft": core.outlook_update_draft,
        "outlook_delete_draft": core.outlook_delete_draft,
        "outlook_reply_email": core.outlook_reply_email,
        "outlook_reply_all": core.outlook_reply_all,
        "outlook_forward_email": core.outlook_forward_email,
        "outlook_delete_email": core.outlook_delete_email,
        "outlook_archive_email": core.outlook_archive_email,
        "outlook_move_to_folder": core.outlook_move_to_folder,
        "outlook_move_to_folder_name": core.outlook_move_to_folder_name,
        "outlook_restore_email": core.outlook_restore_email,
        "outlook_mark_as_read": core.outlook_mark_as_read,
        "outlook_mark_as_unread": core.outlook_mark_as_unread,
        "outlook_flag_email": core.outlook_flag_email,
        "outlook_unflag_email": core.outlook_unflag_email,
        "outlook_list_folders": core.outlook_list_folders,
        "outlook_create_folder": core.outlook_create_folder,
        "outlook_delete_folder": core.outlook_delete_folder,
        "outlook_move_email_to_folder": core.outlook_move_email_to_folder,
        "outlook_list_categories": core.outlook_list_categories,
        "outlook_add_category": core.outlook_add_category,
        "outlook_remove_category": core.outlook_remove_category,
        "outlook_get_attachments": core.outlook_get_attachments,
        "outlook_download_attachment": core.outlook_download_attachment,
        "outlook_save_attachment_to_disk": core.outlook_save_attachment_to_disk,
        "outlook_delete_emails": core.outlook_delete_emails,
        "outlook_archive_emails": core.outlook_archive_emails,
        "outlook_mark_emails_read": core.outlook_mark_emails_read,
        "outlook_flag_emails": core.outlook_flag_emails,
        "outlook_move_emails": core.outlook_move_emails,
        # V2
        "resolve_email_id": v2.resolve_email_id,
        "outlook_email_action": v2.outlook_email_action,
        "outlook_email_modify": v2.outlook_email_modify,
        "outlook_email_generate": v2.outlook_email_generate,
        "outlook_email_analyze": v2.outlook_email_analyze,
        # AI tools
        "summarize_email": lambda *, subject, sender, preview: summarize_email(
            llm, subject=subject, sender=sender, preview=preview
        ),
        "classify_email": lambda *, subject, preview: classify_email(llm, subject=subject, preview=preview),
        "detect_urgency": lambda *, subject, preview: detect_urgency(llm, subject=subject, preview=preview),
        "detect_action_required": lambda *, preview: detect_action_required(llm, preview=preview),
        "sentiment_analysis": lambda *, preview: sentiment_analysis(llm, preview=preview),
        "extract_tasks": lambda *, preview: extract_tasks(llm, preview=preview),
        "extract_dates": lambda *, preview: extract_dates(llm, preview=preview),
        "extract_contacts": lambda *, preview: extract_contacts(llm, preview=preview),
        "extract_links": lambda *, preview: extract_links(llm, preview=preview),
        "draft_reply": lambda *, subject, sender, preview, tone="professional": draft_reply(
            llm, subject=subject, sender=sender, preview=preview, tone=tone
        ),
        "generate_followup": lambda *, subject, recipient, context: generate_followup(
            llm, subject=subject, recipient=recipient, context=context
        ),
        "auto_reply": lambda *, subject, sender, preview: auto_reply(llm, subject=subject, sender=sender, preview=preview),
        "rewrite_email": lambda *, draft, style="clear and professional": rewrite_email(llm, draft=draft, style=style),
        "translate_email": lambda *, text, language: translate_email(llm, text=text, language=language),
        "summarize_emails": lambda *, emails: summarize_emails(llm, emails=emails),
        "auto_categorize_emails": lambda *, emails: auto_categorize_emails(llm, emails=emails),
        "auto_archive_promotions": lambda *, emails: auto_archive_promotions(llm, emails=emails),
        "auto_reply_rules": lambda *, emails, rule: auto_reply_rules(llm, emails=emails, rule=rule),
        "outlook_tool_stats": lambda: GLOBAL_STATS.snapshot(),
        # Calendar tools
        "calendar_get_upcoming_events": core.calendar_get_upcoming_events,
        "calendar_get_today_events": core.calendar_get_today_events,
        "calendar_create_event": core.calendar_create_event,
        "calendar_search_events": core.calendar_search_events,
    }

    # Standardize outputs + add logging/stats
    wrapped: Dict[str, ToolFn] = {}
    for name, fn in tools.items():
        wrapped[name] = tool_wrapper(log_tool_call(name)(fn))
    return wrapped


TOOL_REGISTRY = get_outlook_tools
