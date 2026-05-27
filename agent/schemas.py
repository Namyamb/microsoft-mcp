"""
OpenAI-compatible tool schemas for the Outlook MCP tools.
These are sent to LM Studio so the agent knows what tools are available.
"""
from __future__ import annotations

TOOL_SCHEMAS = [
    # ── Read ─────────────────────────────────────────────────────────────────
    {
        "type": "function",
        "function": {
            "name": "outlook_get_emails",
            "description": "Fetch a list of recent emails from the inbox, ordered newest first.",
            "parameters": {
                "type": "object",
                "properties": {
                    "page_size": {
                        "type": "integer",
                        "description": "Number of emails to return (default 10, max 50).",
                    }
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "outlook_get_unread_emails",
            "description": "Fetch only unread emails from the inbox.",
            "parameters": {
                "type": "object",
                "properties": {
                    "page_size": {
                        "type": "integer",
                        "description": "Number of emails to return (default 10).",
                    }
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "outlook_get_flagged_emails",
            "description": "Fetch emails that are flagged / starred.",
            "parameters": {
                "type": "object",
                "properties": {
                    "page_size": {
                        "type": "integer",
                        "description": "Number of emails to return (default 10).",
                    }
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "outlook_get_email_by_id",
            "description": "Get the full details and body of a specific email by its ID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "email_id": {
                        "type": "string",
                        "description": "The message ID of the email.",
                    }
                },
                "required": ["email_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "outlook_find_messages",
            "description": (
                "Primary tool whenever the user wants to find, search, or check whether mail exists — "
                "by sender (any phrasing like mail/email/messages from a person, company, domain, or address), "
                "by topic or keywords in subject/body, or casual questions in full sentences. "
                "Pass the user's wording or the distilled search phrase; do not split into a separate "
                "sender tool vs keyword tool — this one routes appropriately."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": (
                            "Natural question or search text, e.g. full sentence asking if mail exists from someone, "
                            "or keywords like project name, invoice, flight confirmation."
                        ),
                    },
                    "page_size": {
                        "type": "integer",
                        "description": "Max messages to return (default 15, cap 50).",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "outlook_filter_emails_by_date",
            "description": "Get emails received within a date range.",
            "parameters": {
                "type": "object",
                "properties": {
                    "start": {
                        "type": "string",
                        "description": "Start datetime in ISO-8601 format, e.g. 2026-04-01T00:00:00Z",
                    },
                    "end": {
                        "type": "string",
                        "description": "End datetime in ISO-8601 format, e.g. 2026-04-30T23:59:59Z",
                    },
                    "page_size": {
                        "type": "integer",
                        "description": "Number of emails to return (default 10).",
                    },
                },
                "required": ["start", "end"],
            },
        },
    },
    # ── Send / Draft ──────────────────────────────────────────────────────────
    {
        "type": "function",
        "function": {
            "name": "outlook_send_email",
            "description": "Send a new email immediately and permanently. WARNING: ONLY call this tool when the user uses the word 'send'. If the user says 'draft', 'create a draft', or anything other than 'send', you MUST use outlook_create_draft instead. Do NOT call this tool for drafts.",
            "parameters": {
                "type": "object",
                "properties": {
                    "to": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of recipient email addresses.",
                    },
                    "subject": {"type": "string", "description": "Email subject line."},
                    "body": {"type": "string", "description": "Email body (plain text)."},
                    "cc": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional CC recipients.",
                    },
                    "bcc": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional BCC recipients.",
                    },
                },
                "required": ["to", "subject", "body"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "outlook_create_draft",
            "description": (
                "Create a draft email and save it to the Drafts folder WITHOUT sending it. "
                "Always use this tool when the user says 'draft', 'create a draft', 'save as draft', "
                "or does not explicitly say 'send'. "
                "Returns {\"success\": true, \"data\": {\"draft_id\": \"...\", \"subject\": \"...\", \"status\": \"saved_to_drafts\"}}. "
                "CRITICAL: remember the value of data.draft_id — pass it exactly to outlook_send_draft when the user asks to send."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "to": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of recipient email addresses.",
                    },
                    "subject": {"type": "string", "description": "Email subject line."},
                    "body": {"type": "string", "description": "Email body (plain text)."},
                },
                "required": ["to", "subject", "body"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "outlook_send_draft",
            "description": (
                "Send an already-saved draft by its id. "
                "Use this — NOT outlook_send_email — whenever the user says 'send it', 'send the draft', "
                "'go ahead and send', or any similar phrasing AFTER a draft has already been created. "
                "The draft_id comes from the 'id' field returned by outlook_create_draft."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "draft_id": {
                        "type": "string",
                        "description": "The draft_id from data.draft_id returned by outlook_create_draft. Pass it exactly as-is.",
                    },
                },
                "required": ["draft_id"],
            },
        },
    },
    # ── Reply / Forward ───────────────────────────────────────────────────────
    {
        "type": "function",
        "function": {
            "name": "outlook_reply_email",
            "description": "Reply to an email by its ID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "email_id": {"type": "string", "description": "ID of the email to reply to."},
                    "comment": {"type": "string", "description": "The reply text."},
                },
                "required": ["email_id", "comment"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "outlook_reply_all",
            "description": "Reply-all to an email by its ID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "email_id": {"type": "string", "description": "ID of the email."},
                    "comment": {"type": "string", "description": "The reply text."},
                },
                "required": ["email_id", "comment"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "outlook_forward_email",
            "description": "Forward an email to one or more recipients.",
            "parameters": {
                "type": "object",
                "properties": {
                    "email_id": {"type": "string", "description": "ID of the email to forward."},
                    "to": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Recipient email addresses.",
                    },
                    "comment": {"type": "string", "description": "Optional message to prepend."},
                },
                "required": ["email_id", "to"],
            },
        },
    },
    # ── Organization ──────────────────────────────────────────────────────────
    {
        "type": "function",
        "function": {
            "name": "outlook_delete_email",
            "description": "Permanently delete a single email by ID. Confirm with user first.",
            "parameters": {
                "type": "object",
                "properties": {
                    "email_id": {"type": "string", "description": "ID of the email to delete."},
                },
                "required": ["email_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "outlook_archive_email",
            "description": "Archive a single email (moves it to the Archive folder).",
            "parameters": {
                "type": "object",
                "properties": {
                    "email_id": {"type": "string", "description": "ID of the email to archive."},
                },
                "required": ["email_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "outlook_move_to_folder_name",
            "description": "Move an email to a named folder (e.g. 'Inbox', 'Junk', 'Archive', or a custom folder).",
            "parameters": {
                "type": "object",
                "properties": {
                    "email_id": {"type": "string", "description": "ID of the email to move."},
                    "folder_name": {"type": "string", "description": "Display name of the target folder."},
                },
                "required": ["email_id", "folder_name"],
            },
        },
    },
    # ── State / Flags ─────────────────────────────────────────────────────────
    {
        "type": "function",
        "function": {
            "name": "outlook_mark_as_read",
            "description": "Mark an email as read.",
            "parameters": {
                "type": "object",
                "properties": {
                    "email_id": {"type": "string", "description": "ID of the email."},
                },
                "required": ["email_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "outlook_mark_as_unread",
            "description": "Mark an email as unread.",
            "parameters": {
                "type": "object",
                "properties": {
                    "email_id": {"type": "string", "description": "ID of the email."},
                },
                "required": ["email_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "outlook_flag_email",
            "description": "Flag (star) an email for follow-up.",
            "parameters": {
                "type": "object",
                "properties": {
                    "email_id": {"type": "string", "description": "ID of the email."},
                },
                "required": ["email_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "outlook_unflag_email",
            "description": "Remove the flag from an email.",
            "parameters": {
                "type": "object",
                "properties": {
                    "email_id": {"type": "string", "description": "ID of the email."},
                },
                "required": ["email_id"],
            },
        },
    },
    # ── Folders ───────────────────────────────────────────────────────────────
    {
        "type": "function",
        "function": {
            "name": "outlook_list_folders",
            "description": "List all mail folders in the mailbox.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "outlook_create_folder",
            "description": "Create a new mail folder.",
            "parameters": {
                "type": "object",
                "properties": {
                    "display_name": {"type": "string", "description": "Name of the new folder."},
                },
                "required": ["display_name"],
            },
        },
    },
    # ── Categories ────────────────────────────────────────────────────────────
    {
        "type": "function",
        "function": {
            "name": "outlook_list_categories",
            "description": "List all Outlook categories available in the mailbox.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    # ── AI helpers ────────────────────────────────────────────────────────────
    {
        "type": "function",
        "function": {
            "name": "summarize_mailbox",
            "description": (
                "Use AI to answer any natural-language request about summarizing or briefing on mail: "
                "recent inbox, unread, flagged, mail from a person or company, topics or keywords, "
                "or a single message if you have its id. Pass the user's request as-is; this tool fetches "
                "the right messages and summarizes — you do not need subject/sender/preview fields."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": (
                            "What the user wants, in their own words (e.g. summarize unread, "
                            "what's important today, recap mail from finance, overview of last week)."
                        ),
                    },
                    "max_emails": {
                        "type": "integer",
                        "description": "How many messages to load at most (default 15, max 25).",
                    },
                    "email_id": {
                        "type": "string",
                        "description": "Optional. If set, summarize only this message id (Graph id).",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "draft_reply",
            "description": "Use AI to draft a reply to an email.",
            "parameters": {
                "type": "object",
                "properties": {
                    "subject": {"type": "string", "description": "Email subject."},
                    "sender": {"type": "string", "description": "Sender name or address."},
                    "preview": {"type": "string", "description": "Email body or preview."},
                    "tone": {
                        "type": "string",
                        "description": "Tone for the reply (e.g. professional, friendly, brief).",
                    },
                },
                "required": ["subject", "sender", "preview"],
            },
        },
    },
    # ── Calendar ──────────────────────────────────────────────────────────────
    {
        "type": "function",
        "function": {
            "name": "calendar_get_upcoming_events",
            "description": "Get upcoming calendar events for the next N days.",
            "parameters": {
                "type": "object",
                "properties": {
                    "top": {"type": "integer", "description": "Max number of events to return (default 10)."},
                    "days_ahead": {"type": "integer", "description": "How many days ahead to look (default 7)."},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "calendar_get_today_events",
            "description": "Get all calendar events scheduled for today.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "calendar_create_event",
            "description": "Create a new calendar event / meeting.",
            "parameters": {
                "type": "object",
                "properties": {
                    "subject": {"type": "string", "description": "Event title."},
                    "start_datetime": {"type": "string", "description": "Start time in ISO-8601 UTC, e.g. 2026-05-01T10:00:00."},
                    "end_datetime": {"type": "string", "description": "End time in ISO-8601 UTC, e.g. 2026-05-01T11:00:00."},
                    "attendees": {"type": "array", "items": {"type": "string"}, "description": "Optional list of attendee email addresses."},
                    "body": {"type": "string", "description": "Optional event description."},
                    "location": {"type": "string", "description": "Optional location or meeting link."},
                    "is_all_day": {"type": "boolean", "description": "True if this is an all-day event."},
                    "timezone_str": {"type": "string", "description": "Timezone name, e.g. 'Asia/Kolkata' or 'UTC' (default UTC)."},
                },
                "required": ["subject", "start_datetime", "end_datetime"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "calendar_search_events",
            "description": "Search calendar events by keyword in the subject or body.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search keyword."},
                    "top": {"type": "integer", "description": "Max results (default 10)."},
                },
                "required": ["query"],
            },
        },
    },
    # ── V2 (ID-free / NL helpers) ─────────────────────────────────────────────
    {
        "type": "function",
        "function": {
            "name": "resolve_email_id",
            "description": (
                "Resolve a natural-language email reference (e.g. 'latest email', 'first email', "
                "'second email', 'email from john@example.com') to an actual email ID. "
                "Use this when the user refers to an email without giving an explicit ID."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "reference": {
                        "type": "string",
                        "description": "Natural language reference, e.g. 'latest', 'first', 'second', 'email from alice@co.com'.",
                    }
                },
                "required": ["reference"],
            },
        },
    },
]
