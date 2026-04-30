# Outlook MCP (Microsoft Graph + LM Studio)

Production-grade Outlook tool layer designed to be plugged into an MCP server (or any agent/tool runner).

## What you get

- Microsoft Graph API client with MSAL auth (`authority=https://login.microsoftonline.com/common`)
- Tool registry with the requested core + V2 + AI tools
- Safety controls for email validation and bulk destructive actions
- LM Studio integration via OpenAI-compatible `chat/completions`

## Folder layout

- `app/integrations/outlook/core.py` Graph client + core tools
- `app/integrations/outlook/core_v2.py` ID-free (natural language) helpers
- `app/integrations/outlook/ai.py` LM Studio client + AI tools
- `app/integrations/outlook/utils.py` safety + small utilities
- `app/integrations/outlook/registry.py` tool registry

## Setup

### 1) Install dependencies

```powershell
pip install msal requests
```

### 2) Azure App Registration

Create an app registration in Azure AD / Entra ID and configure it as a **public client** (desktop/mobile) with redirect URI enabled for native flows.

Required delegated permissions (scopes):

- `Mail.Read`
- `Mail.Send`
- `User.Read`

### 3) Environment variables

At minimum:

- `OUTLOOK_CLIENT_ID` = your app registration client id

Optional:

- `OUTLOOK_AUTHORITY` (default `https://login.microsoftonline.com/common`)
- `OUTLOOK_SCOPES` (default `Mail.Read Mail.Send User.Read`)
- `OUTLOOK_TOKEN_CACHE` (default `.outlook_msal_token_cache.bin`)

For LM Studio:

- `LMSTUDIO_BASE_URL` (default `http://localhost:1234/v1`)
- `LMSTUDIO_MODEL` (default `local-model`)
- `LMSTUDIO_API_KEY` (default `lm-studio`)

## Tool list

### Core tools (Graph)

Read:
- `outlook_get_emails`
- `outlook_get_email_by_id`
- `outlook_search_emails`

Send/Draft:
- `outlook_send_email`
- `outlook_create_draft`

Reply/Forward:
- `outlook_reply_email`
- `outlook_forward_email`

Organization:
- `outlook_delete_email`
- `outlook_archive_email`
- `outlook_move_to_folder`

State:
- `outlook_mark_as_read`
- `outlook_mark_as_unread`

Flag:
- `outlook_flag_email`
- `outlook_unflag_email`

Folders:
- `outlook_list_folders`
- `outlook_create_folder`

Attachments:
- `outlook_get_attachments`
- `outlook_download_attachment`

Batch:
- `outlook_delete_emails`
- `outlook_archive_emails`

### V2 tools (ID-free)

- `resolve_email_id`
- `outlook_email_action`
- `outlook_email_modify`
- `outlook_email_generate`
- `outlook_email_analyze`

### AI tools (LM Studio)

- `summarize_email`
- `classify_email`
- `detect_urgency`
- `sentiment_analysis`
- `extract_tasks`
- `draft_reply`

## Safety

- Email addresses are validated before sending/forwarding (`utils.validate_email_address`)
- Bulk destructive actions are blocked by default (>10 items) unless `allow_bulk=True`

## Using the registry

```python
from app.integrations.outlook import get_outlook_tools

tools = get_outlook_tools()
emails = tools["outlook_get_emails"](top=5)
```

## Notes

- Auth uses MSAL device-code flow by default (suitable for headless/CLI usage).
- Endpoints used:
  - `GET /me/messages`
  - `POST /me/sendMail`
  - `PATCH /me/messages/{id}`
  - `DELETE /me/messages/{id}`

