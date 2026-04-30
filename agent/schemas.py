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
            "name": "outlook_search_emails",
            "description": "Search emails by keyword. Searches subject, body, and sender.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search keyword or phrase.",
                    },
                    "top": {
                        "type": "integer",
                        "description": "Max number of results (default 10).",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "outlook_filter_emails_by_sender",
            "description": "Get emails from a specific sender email address.",
            "parameters": {
                "type": "object",
                "properties": {
                    "sender": {
                        "type": "string",
                        "description": "The sender's email address.",
                    },
                    "page_size": {
                        "type": "integer",
                        "description": "Number of emails to return (default 10).",
                    },
                },
                "required": ["sender"],
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
            "description": "Send a new email. Always confirm with the user before calling this.",
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
            "description": "Create a draft email without sending it.",
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
            "name": "summarize_email",
            "description": "Use AI to summarize an email into 2-4 bullet points.",
            "parameters": {
                "type": "object",
                "properties": {
                    "subject": {"type": "string", "description": "Email subject."},
                    "sender": {"type": "string", "description": "Sender name or address."},
                    "preview": {"type": "string", "description": "Email body preview or full text."},
                },
                "required": ["subject", "sender", "preview"],
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
