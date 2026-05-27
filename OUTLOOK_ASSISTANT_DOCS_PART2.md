# OUTLOOK ASSISTANT — Technical Documentation
## Part 2: Sections 11–22

---

# SECTION 11 — DATABASE DESIGN

## 11.1 Schema Overview

The persistence layer uses SQLite in Write-Ahead Log (WAL) mode. The schema is intentionally minimal — two tables support all session and conversation persistence requirements.

```
┌─────────────────────────────────────┐
│             sessions                 │
├──────────┬──────────────────────────┤
│ id       │ TEXT PRIMARY KEY (UUID)  │
│ title    │ TEXT NOT NULL            │
│ created_at│ TEXT (ISO 8601 UTC)     │
│ updated_at│ TEXT (ISO 8601 UTC)     │
└─────┬────┴──────────────────────────┘
      │ 1
      │
      │ ∞
┌─────▼────────────────────────────────────────┐
│                  messages                     │
├──────────┬───────────────────────────────────┤
│ id       │ TEXT PRIMARY KEY (UUID)            │
│ session_id│ TEXT → sessions.id (CASCADE DEL) │
│ role     │ TEXT ("user" | "assistant")        │
│ content  │ TEXT (message text)                │
│ tool_calls│ TEXT (JSON-encoded array | NULL)  │
│ created_at│ TEXT (ISO 8601 UTC)               │
└──────────┴───────────────────────────────────┘
```

## 11.2 Entity-Relationship Design

**Sessions** — each represents a named conversation thread. Sessions are sorted by `updated_at` descending so the most recently active conversation appears first in the sidebar.

**Messages** — each message belongs to exactly one session. The `role` field maps to the OpenAI message format (`user` or `assistant`), enabling direct use as LLM context. The `tool_calls` column stores a JSON array of tool execution records for later recovery (draft ID retrieval, observability).

**Cascade Delete** — when a session is deleted, all its messages are automatically removed by the database (ON DELETE CASCADE constraint), ensuring no orphaned records.

## 11.3 tool_calls Column Format

```json
[
  {
    "name": "outlook_find_messages",
    "args": "{\"query\": \"alice@company.com\"}",
    "result": {
      "success": true,
      "data": [
        {
          "id": "AAMkAGVm...",
          "subject": "Q4 Planning",
          "from": {"emailAddress": {"name": "Alice", "address": "alice@co.com"}},
          "receivedDateTime": "2026-05-26T14:30:00Z",
          "bodyPreview": "Hi, I wanted to follow up on..."
        }
      ]
    },
    "status": "done"
  }
]
```

## 11.4 WAL Mode Benefits

```sql
PRAGMA journal_mode=WAL;
```

| Mode | Behavior |
|------|----------|
| Default (rollback) | One writer at a time; readers block writers |
| WAL | Concurrent reads during writes; faster commits |

In Outlook Assistant, WAL mode is critical because:
- The SSE streaming loop saves messages while the agent is still running.
- The sidebar auto-refreshes sessions every 10 seconds (concurrent reads).
- Inbox polling reads from the DB while a chat is active (concurrent access).

## 11.5 Sample Queries

```python
# Get ordered session list (sidebar)
SELECT id, title, created_at, updated_at
FROM sessions ORDER BY updated_at DESC;

# Get full conversation history for LLM
SELECT role, content FROM messages
WHERE session_id = ? ORDER BY created_at ASC;

# Auto-title a session from first message
UPDATE sessions SET title = ?, updated_at = ? WHERE id = ?;

# Check for recent draft in last 20 messages (draft recovery)
SELECT tool_calls FROM messages
WHERE session_id = ? ORDER BY created_at DESC LIMIT 20;
```

---

# SECTION 12 — MICROSOFT GRAPH API INTEGRATION

## 12.1 What is Microsoft Graph?

Microsoft Graph is the unified REST API gateway for all Microsoft 365 data and services. It provides a single endpoint (`https://graph.microsoft.com/v1.0`) for accessing:

- **Outlook Mail**: Read, send, organize, search messages
- **Outlook Calendar**: Events, attendees, recurring meetings
- **OneDrive**: Files and folders
- **Teams**: Chats, channels, meetings
- **Azure AD**: Users, groups, organization

Outlook Assistant uses Microsoft Graph for **Mail** and **Calendar** operations.

## 12.2 Authentication Method: OAuth 2.0 Device Flow

The application uses the **Device Authorization Grant** (RFC 8628) instead of the more common Authorization Code Flow. This choice was deliberate:

| Flow | Requires | Best For |
|------|----------|---------|
| Authorization Code | Web redirect URI, browser redirect | Web apps with known callback URL |
| Device Flow | Any browser, no redirect | CLI tools, desktop apps, local dev |

The device flow is ideal for Outlook Assistant because:
- No redirect URI needs to be configured in Azure App Registration.
- Works even when running on localhost with no fixed port.
- Users can authenticate on a different device (e.g., phone) while the app runs on a server.

## 12.3 Device Flow Step-by-Step

```
Step 1: Application requests device flow
─────────────────────────────────────────
POST https://login.microsoftonline.com/common/oauth2/v2.0/devicecode
Body: {client_id, scope}

Response:
{
  "device_code": "DAQABAAEAAAAm...",  ← sent to server for polling
  "user_code": "ABCD-1234",          ← displayed to user
  "verification_uri": "https://microsoft.com/devicelogin",
  "expires_in": 900,
  "interval": 5
}

Step 2: User authenticates in browser
──────────────────────────────────────
User visits https://microsoft.com/devicelogin
User enters code: ABCD-1234
User signs in with Microsoft account
User grants permissions to the application

Step 3: Server polls for token
───────────────────────────────
POST https://login.microsoftonline.com/common/oauth2/v2.0/token
Body: {grant_type: device_code, client_id, device_code}

Response (when approved):
{
  "access_token": "eyJ0eXAi...",   ← Used for all API calls
  "refresh_token": "0.AXoA...",   ← Auto-refreshed by MSAL
  "expires_in": 3600,
  "scope": "Mail.Read Mail.Send User.Read Calendars.ReadWrite"
}
```

## 12.4 Required API Permissions (Scopes)

| Scope | Permission | Purpose |
|-------|-----------|---------|
| `Mail.Read` | Delegated | Read messages and mailbox settings |
| `Mail.Send` | Delegated | Send messages |
| `Mail.ReadWrite` | Delegated | Archive, move, delete messages |
| `User.Read` | Delegated | Read user profile (name, email) |
| `Calendars.ReadWrite` | Delegated | Read and create calendar events |

All scopes are **delegated** (acting on behalf of the signed-in user), not application permissions. This means the app can only access the data of the authenticated user, not all users in a tenant.

## 12.5 Graph API Endpoints Used

### Mail Endpoints

| Operation | HTTP Method | Endpoint |
|-----------|-------------|---------|
| List inbox | GET | `/me/messages?$top=N&$orderby=receivedDateTime desc` |
| Get email | GET | `/me/messages/{id}` |
| Send email | POST | `/me/sendMail` |
| Create draft | POST | `/me/messages` |
| Update draft | PATCH | `/me/messages/{id}` |
| Send draft | POST | `/me/messages/{id}/send` |
| Reply | POST | `/me/messages/{id}/reply` |
| Reply All | POST | `/me/messages/{id}/replyAll` |
| Forward | POST | `/me/messages/{id}/forward` |
| Delete | DELETE | `/me/messages/{id}` |
| Move | POST | `/me/messages/{id}/move` |
| Update flags | PATCH | `/me/messages/{id}` |
| Full-text search | GET | `/me/messages?$search="keyword"` |
| List folders | GET | `/me/mailFolders` |
| Create folder | POST | `/me/mailFolders` |

### Calendar Endpoints

| Operation | HTTP Method | Endpoint |
|-----------|-------------|---------|
| List events | GET | `/me/events?$top=N&$orderby=start/dateTime` |
| Filter by date | GET | `/me/events?$filter=start/dateTime ge 'ISO_DATE'` |
| Create event | POST | `/me/events` |
| Search events | GET | `/me/events?$search="keyword"` |

## 12.6 OData Query Parameters

Microsoft Graph supports OData v4 query parameters for powerful filtering:

```python
# Fetch top 10 emails, only selected fields
GET /me/messages?$top=10
  &$select=id,subject,from,receivedDateTime,isRead,flag,bodyPreview
  &$orderby=receivedDateTime desc

# Full-text search
GET /me/messages?$search="project proposal"

# Filter by sender (exact email)
GET /me/messages?$filter=from/emailAddress/address eq 'alice@co.com'

# Date range filter
GET /me/messages?$filter=receivedDateTime ge 2026-05-01T00:00:00Z
  and receivedDateTime le 2026-05-31T23:59:59Z

# Paginate with skiptoken
GET /me/messages?$skiptoken=AAMkAGVm...
```

## 12.7 Flagged Email Limitation

The Microsoft Graph API does not reliably support `$filter` on `flag/flagStatus` for shared mailboxes or some account types. The application works around this:

```python
def outlook_get_flagged_emails(self, top=10) -> List[dict]:
    """
    Fetch flagged emails by scanning batches in memory.
    Graph $filter on flagStatus is unreliable across account types.
    """
    flagged = []
    batch_size = 50
    skip = 0

    while len(flagged) < top:
        # Fetch batch
        batch, _ = self._paged_messages(
            "/me/messages",
            params={
                "$select": "id,subject,from,receivedDateTime,isRead,flag,bodyPreview",
                "$top": batch_size,
                "$skip": skip,
            },
            top=batch_size,
        )
        if not batch:
            break

        # Filter in memory
        flagged.extend([
            m for m in batch
            if m.get("flag", {}).get("flagStatus") == "flagged"
        ])
        skip += batch_size

        # Stop scanning after 2000 messages
        if skip >= 2000:
            break

    return flagged[:top]
```

## 12.8 Error Classification

The integration layer defines typed exceptions for precise error handling:

```python
class EmailError(Exception):
    """Base class for all email operation errors."""

class AuthenticationError(EmailError):
    """Token acquisition failed or expired."""

class EmailNotFoundError(EmailError):
    """Requested email ID does not exist."""

class EmailPermissionError(EmailError):
    """Insufficient Microsoft Graph permissions (HTTP 403)."""

class EmailRateLimitError(EmailError):
    """Graph API rate limit hit (HTTP 429), retries exhausted."""

class EmailValidationError(EmailError):
    """Invalid email address, empty subject/body, etc."""

class EmailAmbiguityError(EmailError):
    """Natural language resolution matched multiple emails."""
```

---

# SECTION 13 — LM STUDIO INTEGRATION

## 13.1 What is LM Studio?

LM Studio is a desktop application that downloads and runs open-source large language models locally on consumer hardware. It exposes an OpenAI-compatible REST API at `http://127.0.0.1:1234/v1`, meaning any code written for the OpenAI API works with LM Studio with only a URL change.

**Supported Models (examples):**
- Google Gemma 3 (4B, 12B)
- Meta Llama 3.2 (1B, 3B, 8B, 70B)
- Mistral 7B Instruct
- Microsoft Phi-3 Mini
- Alibaba Qwen 2.5

**Hardware Requirements:**
- Minimum: 8 GB RAM for 4B models
- Recommended: 16 GB RAM for 8B models, GPU for faster inference

## 13.2 LMStudioClient Class

```python
class LMStudioClient:
    def __init__(self):
        base_url = os.getenv("LMSTUDIO_BASE_URL", "http://127.0.0.1:1234/v1")
        api_key  = os.getenv("LMSTUDIO_API_KEY", "lm-studio")
        self.model = os.getenv("LMSTUDIO_MODEL", "local-model")
        self.timeout = int(os.getenv("LMSTUDIO_TIMEOUT", "120"))

        # Use OpenAI SDK pointed at local LM Studio endpoint
        self.client = openai.OpenAI(
            base_url=base_url,
            api_key=api_key,  # Any non-empty string works; LM Studio ignores it
        )
```

## 13.3 AI Tool Functions

Each AI tool in `ai.py` follows the same pattern: construct a focused prompt, call LM Studio, extract the response text.

```python
def summarize_email(self, subject: str, sender: str, preview: str) -> str:
    prompt = f"""Summarize this email in 2-4 concise bullet points.

Subject: {subject}
From: {sender}
Body: {preview}

Bullet points:"""

    response = self.client.chat.completions.create(
        model=self.model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        max_tokens=200,
    )
    return response.choices[0].message.content.strip()
```

### 13.3.1 Complete AI Tool List

| Function | Input | Output | Use Case |
|----------|-------|--------|----------|
| `summarize_email` | subject, sender, preview | 2–4 bullet points | "Summarize this email" |
| `summarize_emails` | list of emails | Numbered summaries | "Brief me on my inbox" |
| `classify_email` | subject, preview | label string | Auto-categorization |
| `detect_urgency` | subject, preview | low/medium/high | Priority triage |
| `sentiment_analysis` | preview | negative/neutral/positive | Tone detection |
| `detect_action_required` | preview | yes/no | Follow-up needed? |
| `extract_tasks` | preview | checklist items | Get action items |
| `extract_dates` | preview | JSON date array | Meeting scheduling |
| `extract_contacts` | preview | JSON contact array | Contact extraction |
| `extract_links` | preview | JSON URL array | Link extraction |
| `draft_reply` | subject, sender, preview, tone | Reply email body | "Draft a reply" |
| `generate_followup` | subject, recipient, context | Follow-up body | "Write a follow-up" |
| `auto_reply` | subject, sender, preview | Auto-reply body | OOO / acknowledgment |
| `rewrite_email` | draft, style | Rewritten body | Style adjustment |
| `translate_email` | text, language | Translated text | Translation |
| `auto_categorize_emails` | list of emails | Label assignments | Bulk categorization |

## 13.4 LM Studio vs Cloud APIs

| Factor | LM Studio (Local) | OpenAI / Azure OpenAI |
|--------|------------------|----------------------|
| Cost | Free (electricity only) | Per-token billing |
| Privacy | All data stays on-device | Data sent to cloud |
| Latency | Depends on hardware | Typically lower (GPU cloud) |
| Model choice | Any GGUF/GGML model | Specific models only |
| Setup | Install app, download model | API key only |
| Uptime | Requires local machine on | Always available |
| Context window | Model-dependent | Predictable (gpt-4: 128k) |

## 13.5 Tool-Calling with LM Studio

LM Studio supports the OpenAI function-calling protocol when using compatible models. The agent passes tool schemas and the model returns structured `tool_calls` in its completion:

```python
# Request with tools
completion = lm_client.chat.completions.create(
    model="gemma-4-e2b-it",
    messages=messages,
    tools=TOOL_SCHEMAS,         # List of function schemas
    tool_choice="auto",         # Model decides when to call
    temperature=0.4,
    stream=True,
)

# Response when model calls a tool:
# chunk.choices[0].delta.tool_calls = [
#   ToolCall(
#     index=0,
#     id="call_abc123",
#     type="function",
#     function=Function(
#       name="outlook_get_unread_emails",
#       arguments='{"top": 5}'
#     )
#   )
# ]
```

**Important**: Not all models in LM Studio support function calling reliably. Recommended models:
- **Gemma 3 IT variants** (recommended — strong tool-calling)
- **Llama 3.1 Instruct** (good tool-calling support)
- **Qwen 2.5 Instruct** (excellent function-calling)
- Avoid: Base models, non-instruct variants, models below 4B parameters

---

# SECTION 14 — AI AGENT WORKFLOW

## 14.1 Conceptual Overview

An **AI agent** is a system where an LLM is given tools and asked to solve a task by choosing which tools to call, in what order, and how to synthesize their results. The Outlook Assistant implements a **hybrid agent**: part deterministic (router-driven), part fully autonomous (LLM-driven).

## 14.2 Full Conversation Lifecycle

```
┌─────────────────────────────────────────────────────────┐
│  User: "Show me emails from marketing@company.com"       │
└──────────────────────┬──────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────┐
│  STEP 1: router.py classifies intent                     │
│                                                          │
│  Input:  "Show me emails from marketing@company.com"     │
│  Detects: email address pattern                          │
│  Intent: MAILBOX_QUERY                                   │
│  Mode:   TOOL_FIRST                                      │
│  Tool:   outlook_find_messages                           │
│  Args:   {"query": "marketing@company.com"}              │
└──────────────────────┬──────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────┐
│  STEP 2: Pre-execute tool (TOOL_FIRST mode)              │
│                                                          │
│  Call: outlook_find_messages(query="marketing@company.com")
│                                                          │
│  Graph API: GET /me/messages?$search="marketing@company.com"
│                                                          │
│  Result: {success: true, data: [                         │
│    {id: "AAMk...", subject: "Q4 Campaign", ...},         │
│    {id: "BBMk...", subject: "Newsletter Stats", ...}     │
│  ]}                                                      │
│                                                          │
│  → Yield SSE: tool_start, tool_end                       │
└──────────────────────┬──────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────┐
│  STEP 3: Build LLM message context                       │
│                                                          │
│  messages = [                                            │
│    {role: "system", content: SYSTEM_PROMPT},             │
│    ...conversation_history,                              │
│    {role: "user", content: "Show emails from..."},       │
│    {role: "assistant", content: "[Router called outlook_find_messages]"},
│    {role: "tool", content: JSON.stringify(tool_result),  │
│     tool_call_id: "pre_exec_1"},                         │
│    {role: "system", content:                             │
│     "[ROUTER PRE-EXECUTION] Tool: outlook_find_messages, │
│      Intent: mailbox_query, Success: true.               │
│      Ground your answer in this data."}                  │
│  ]                                                       │
└──────────────────────┬──────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────┐
│  STEP 4: LLM generates grounded response                 │
│                                                          │
│  LM Studio streams:                                      │
│  "Here are the emails from marketing@company.com:        │
│                                                          │
│   **Q4 Campaign** (May 25, 2026)                         │
│   From: marketing@company.com                            │
│   Preview: Excited to share our Q4 results...            │
│                                                          │
│   **Newsletter Stats** (May 20, 2026)                    │
│   From: marketing@company.com                            │
│   Preview: Weekly newsletter performance report..."      │
│                                                          │
│  → Yield SSE: text_delta (token by token)                │
└──────────────────────┬──────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────┐
│  STEP 5: Save to DB + yield done event                   │
│                                                          │
│  add_message(session_id, "assistant", content, tool_calls)
│  → Yield SSE: done                                       │
└─────────────────────────────────────────────────────────┘
```

## 14.3 Multi-Step Agentic Example

For a more complex request like *"Draft a polite follow-up email to the sender of the latest unread email"*, the agent runs multiple tool iterations autonomously:

```
Iteration 1:
  LLM decides to call: outlook_get_unread_emails(top=1)
  Result: [{subject: "Partnership Proposal", from: "bob@partner.com"}]

Iteration 2:
  LLM decides to call: outlook_get_email_by_id(id="AAMk...")
  Result: {body: "Hi, I wanted to discuss...", subject: "Partnership Proposal"}

Iteration 3:
  LLM decides to call: draft_reply(subject=..., sender=..., tone="polite")
  Result: "Dear Bob, Thank you for reaching out regarding..."

LLM synthesizes:
  "I've drafted a follow-up email:

   **To**: bob@partner.com
   **Subject**: Re: Partnership Proposal

   Dear Bob,
   Thank you for reaching out regarding the partnership proposal.
   I wanted to follow up and ask if you're available for a call
   this week to discuss further details..."
```

## 14.4 Iteration Safety

The loop is capped at 8 iterations to prevent infinite tool-call cycles:

```python
MAX_ITERATIONS = 8

for i in range(MAX_ITERATIONS):
    # ... LLM call ...
    if finish_reason == "stop":
        return  # Natural completion
    if finish_reason == "tool_calls":
        # Execute tools, continue to next iteration
        continue

# If we reach here, max iterations exceeded
yield_event("text_delta", {
    "content": "\n\n_(Reached maximum tool-call iterations.)_"
})
yield_event("done", {})
```

---

# SECTION 15 — TOOL CALLING SYSTEM

## 15.1 Tool Registry Architecture

All tools are registered in a single dictionary returned by `get_outlook_tools()` in `registry.py`. This dictionary maps tool name strings to Python callables:

```python
def get_outlook_tools(
    core: OutlookGraphClient,
    v2: OutlookGraphClientV2,
    llm: LMStudioClient
) -> Dict[str, Callable]:
    return {
        # Core read tools
        "outlook_get_emails":           core.outlook_get_emails,
        "outlook_get_unread_emails":    core.outlook_get_unread_emails,
        "outlook_get_flagged_emails":   core.outlook_get_flagged_emails,
        "outlook_get_email_by_id":      core.outlook_get_email_by_id,
        "outlook_find_messages":        core.outlook_find_messages,
        "outlook_filter_emails_by_date":core.outlook_filter_emails_by_date,

        # Send tools
        "outlook_send_email":           core.outlook_send_email,
        "outlook_create_draft":         core.outlook_create_draft,
        "outlook_send_draft":           core.outlook_send_draft,

        # Reply/forward
        "outlook_reply_email":          core.outlook_reply_email,
        "outlook_reply_all":            core.outlook_reply_all,
        "outlook_forward_email":        core.outlook_forward_email,

        # Organization
        "outlook_delete_email":         core.outlook_delete_email,
        "outlook_archive_email":        core.outlook_archive_email,
        "outlook_move_to_folder_name":  core.outlook_move_to_folder_name,
        "outlook_mark_as_read":         core.outlook_mark_as_read,
        "outlook_mark_as_unread":       core.outlook_mark_as_unread,
        "outlook_flag_email":           core.outlook_flag_email,
        "outlook_unflag_email":         core.outlook_unflag_email,
        "outlook_list_folders":         core.outlook_list_folders,
        "outlook_create_folder":        core.outlook_create_folder,

        # AI helpers
        "summarize_mailbox":            _make_summarize_mailbox(core, llm),
        "draft_reply":                  _make_draft_reply(core, llm),

        # Calendar
        "calendar_get_upcoming_events": core.calendar_get_upcoming_events,
        "calendar_get_today_events":    core.calendar_get_today_events,
        "calendar_create_event":        core.calendar_create_event,
        "calendar_search_events":       core.calendar_search_events,

        # NL resolution
        "resolve_email_id":             v2.resolve_email_id,
    }
```

## 15.2 Tool Wrapper Pattern

Every tool is wrapped with a standardized output format and error handling:

```python
def tool_wrapper(func_name: str, func: Callable) -> Callable:
    """Wraps any tool function with:
    - Standard {success, data, error} output format
    - Exception catching and classification
    - Execution logging and stats
    """
    def wrapped(**kwargs):
        start = time.time()
        try:
            result = func(**kwargs)
            duration = time.time() - start
            GLOBAL_STATS[func_name]["calls"] += 1
            GLOBAL_STATS[func_name]["total_ms"] += duration * 1000
            return {"success": True, "data": result, "error": None}

        except EmailNotFoundError as e:
            return {"success": False, "data": None,
                    "error": f"Email not found: {e}"}

        except EmailPermissionError as e:
            return {"success": False, "data": None,
                    "error": f"Permission denied: {e}"}

        except EmailRateLimitError as e:
            return {"success": False, "data": None,
                    "error": f"Rate limit: {e}"}

        except EmailAmbiguityError as e:
            return {"success": False, "data": None,
                    "error": f"Ambiguous: {e}. Please be more specific."}

        except Exception as e:
            logger.exception(f"Tool {func_name} failed")
            return {"success": False, "data": None, "error": str(e)}

    wrapped.__name__ = func_name
    return wrapped
```

## 15.3 Tool Execution in the Agent Loop

When the LLM decides to call a tool, the agent loop:

1. Collects all tool call deltas from the streaming response (buffered by index).
2. Emits a `tool_start` SSE event (shows spinner badge in UI).
3. Looks up the tool in the registry by name.
4. Calls the tool with the parsed JSON arguments.
5. Emits a `tool_end` SSE event (shows result + ✓ or ✗ in UI).
6. Appends the tool result to the message list for the next LLM iteration.

```python
# Buffer tool call fragments from streaming
tool_call_buffer: Dict[int, dict] = {}

for chunk in stream:
    if chunk.choices[0].delta.tool_calls:
        for tc_delta in chunk.choices[0].delta.tool_calls:
            idx = tc_delta.index
            if idx not in tool_call_buffer:
                tool_call_buffer[idx] = {
                    "id":   tc_delta.id or "",
                    "name": "",
                    "args": ""
                }
            if tc_delta.function.name:
                tool_call_buffer[idx]["name"] += tc_delta.function.name
            if tc_delta.function.arguments:
                tool_call_buffer[idx]["args"] += tc_delta.function.arguments

# Execute collected tool calls
for tc in tool_call_buffer.values():
    tool_fn = tools.get(tc["name"])
    if not tool_fn:
        result = {"success": False, "error": f"Unknown tool: {tc['name']}"}
    else:
        args = json.loads(tc["args"] or "{}")
        result = tool_fn(**args)

    # Append to messages for next LLM iteration
    messages.append({
        "role": "tool",
        "tool_call_id": tc["id"],
        "content": json.dumps(result)
    })
```

## 15.4 Natural Language Email Resolution

`resolve_email_id` is a special tool that converts human references into concrete email IDs:

```python
def resolve_email_id(reference: str, top: int = 5) -> dict:
    """
    Resolve natural language email references to email IDs.

    Examples:
    - "first email"     → index 0 of GLOBAL_CONTEXT.last_email_list
    - "second email"    → index 1
    - "latest"          → fetch top 1 from inbox
    - "latest unread"   → fetch top 1 unread
    - "that email"      → GLOBAL_CONTEXT.last_viewed_id
    - "this"            → GLOBAL_CONTEXT.last_viewed_id
    - "email from alice@co.com" → filter by sender
    - "email about project"     → search by keyword
    """
    ref = reference.lower().strip()

    # Context pronouns
    if ref in ("this", "that", "it", "the email", "this email", "that email"):
        if GLOBAL_CONTEXT.last_viewed_id:
            return {"id": GLOBAL_CONTEXT.last_viewed_id,
                    "method": "context_pronoun"}
        raise EmailAmbiguityError("No recent email in context")

    # Ordinal references
    ordinal_map = {
        "first": 0, "second": 1, "third": 2, "fourth": 3, "fifth": 4,
        "1st": 0, "2nd": 1, "3rd": 2, "4th": 3, "5th": 4,
        "latest": 0, "last": 0, "most recent": 0, "newest": 0,
    }
    for word, idx in ordinal_map.items():
        if word in ref:
            if GLOBAL_CONTEXT.last_email_list and len(GLOBAL_CONTEXT.last_email_list) > idx:
                email = GLOBAL_CONTEXT.last_email_list[idx]
                return {"id": email["id"], "chosen": email, "method": f"ordinal_{word}"}
            # Fall back to fetching fresh
            emails = self.core.outlook_get_emails(top=idx + 1)
            if len(emails) > idx:
                return {"id": emails[idx]["id"], "chosen": emails[idx],
                        "method": f"ordinal_fetch_{word}"}

    # Sender extraction: "email from alice@co.com"
    if "from" in ref:
        sender = ref.split("from")[-1].strip()
        results = self.core.outlook_find_messages(query=sender, top=top)
        if results:
            if len(results) == 1:
                return {"id": results[0]["id"], "chosen": results[0],
                        "method": "sender_match"}
            # Multiple results — check for ambiguity
            subjects = {r["subject"] for r in results}
            if len(subjects) > 2:
                raise EmailAmbiguityError(
                    f"Found {len(results)} emails from '{sender}'. "
                    "Please specify the subject."
                )
            return {"id": results[0]["id"], "chosen": results[0],
                    "candidates": results, "method": "sender_top"}

    # Full-text fallback
    results = self.core.outlook_search_emails(reference, top=top)
    if results:
        return {"id": results[0]["id"], "chosen": results[0], "method": "search"}

    raise EmailNotFoundError(f"Could not resolve email reference: '{reference}'")
```

---

# SECTION 16 — SSE STREAMING ARCHITECTURE

## 16.1 What is Server-Sent Events (SSE)?

Server-Sent Events is an HTTP/1.1 standard (W3C EventSource spec) for **one-directional server-to-client streaming**. Unlike WebSocket (bidirectional), SSE uses a single long-lived HTTP connection over which the server can push text events.

**SSE Message Format:**
```
data: {"type": "text_delta", "content": "Here"}\n\n
data: {"type": "text_delta", "content": " are"}\n\n
data: {"type": "text_delta", "content": " your emails"}\n\n
data: {"type": "tool_start", "name": "outlook_get_emails", "status": "running"}\n\n
data: {"type": "tool_end", "name": "outlook_get_emails", "status": "done", "result": {...}}\n\n
data: {"type": "done"}\n\n
```

Each event is a `data: <json>\n\n` line. The double newline `\n\n` is the message delimiter.

## 16.2 Why SSE over WebSocket?

| Criterion | SSE | WebSocket |
|-----------|-----|-----------|
| Direction | Server → Client only | Bidirectional |
| Protocol | HTTP/1.1 | Upgraded TCP |
| Browser support | Native `EventSource` | `WebSocket` API |
| Auto-reconnect | Built-in | Manual |
| Load balancer friendly | Yes (standard HTTP) | Requires WS support |
| Complexity | Simple | More setup required |
| Suitable for | AI streaming, notifications | Chat, gaming, live collab |

For Outlook Assistant, SSE is the correct choice:
- The server streams tokens/tool events to the client.
- The client sends a single POST request and receives the streaming response.
- No need for bidirectional communication.

## 16.3 FastAPI SSE Implementation

```python
@app.post("/api/chat")
async def chat(request: ChatRequest):
    result_queue: asyncio.Queue = asyncio.Queue()

    # Worker thread runs synchronous operations (LM Studio, Graph API)
    def run_worker():
        # Create new event loop for thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(
                run_agent_stream(
                    history=get_agent_history(request.session_id),
                    message=request.message,
                    session_id=request.session_id,
                    queue=result_queue,
                )
            )
        finally:
            loop.close()

    thread = threading.Thread(target=run_worker, daemon=True)
    thread.start()

    async def event_generator():
        final_content = []
        final_tool_calls = []

        try:
            while True:
                # Wait for next event from worker thread
                event = await asyncio.wait_for(result_queue.get(), timeout=120.0)

                if event["type"] == "text_delta":
                    final_content.append(event.get("content", ""))

                elif event["type"] == "tool_end":
                    final_tool_calls.append(event)

                elif event["type"] == "done":
                    # Persist complete assistant message
                    full_content = "".join(final_content)
                    if full_content or final_tool_calls:
                        add_message(
                            request.session_id,
                            "assistant",
                            full_content,
                            json.dumps(final_tool_calls) if final_tool_calls else None
                        )
                    yield f"data: {json.dumps(event)}\n\n"
                    return

                yield f"data: {json.dumps(event)}\n\n"

        except asyncio.CancelledError:
            # Client disconnected — save partial response
            if final_content:
                add_message(request.session_id, "assistant",
                            "".join(final_content) + " _(interrupted)_", None)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",     # Disable Nginx buffering
            "Connection": "keep-alive",
        }
    )
```

## 16.4 React SSE Consumer

On the frontend, SSE is consumed using the `fetch` API's streaming body reader (more flexible than `EventSource`):

```javascript
async function consumeSSE(sessionId, message) {
    const response = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: sessionId, message }),
        signal: abortController.signal,
    });

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        // Decode chunk and add to buffer (handles partial lines)
        buffer += decoder.decode(value, { stream: true });

        // Process complete SSE messages
        const lines = buffer.split("\n");
        buffer = lines.pop();  // Keep incomplete last line in buffer

        for (const line of lines) {
            if (!line.startsWith("data: ")) continue;
            const eventData = JSON.parse(line.slice(6));
            handleSSEEvent(eventData);
        }
    }
}
```

## 16.5 SSE Event Types Reference

| Event Type | Payload Fields | UI Effect |
|------------|---------------|----------|
| `text_delta` | `content: string` | Appends text to assistant bubble |
| `tool_start` | `name`, `args`, `status: "running"` | Shows spinner badge |
| `tool_end` | `name`, `result`, `status: "done"` | Updates badge to ✓/✗, renders EmailCards |
| `route` | `intent`, `mode`, `reason` | Observability only (not shown to user) |
| `error` | `content: error string` | Appends error text to bubble |
| `done` | (empty) | Stops streaming, persists message |

## 16.6 Notification SSE Stream

A separate SSE endpoint handles inbox notifications:

```javascript
// React: Subscribe to inbox notifications
useEffect(() => {
    const controller = new AbortController();

    async function subscribeNotifications() {
        const resp = await fetch("/api/notifications/stream", {
            signal: controller.signal
        });
        const reader = resp.body.getReader();
        const decoder = new TextDecoder();

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            const text = decoder.decode(value);
            for (const line of text.split("\n")) {
                if (!line.startsWith("data: ")) continue;
                const event = JSON.parse(line.slice(6));
                if (event.type === "new_emails") {
                    showNotificationBanner(
                        `${event.count} new email${event.count > 1 ? "s" : ""}`
                    );
                }
            }
        }
    }

    subscribeNotifications();
    return () => controller.abort();
}, []);
```

---

# SECTION 17 — AUTHENTICATION FLOW

## 17.1 Complete Authentication Sequence

```
Browser (React)           FastAPI Server            Microsoft Azure AD
     │                         │                           │
     │─── GET /api/auth ──────▶│                           │
     │                         │◀── Check MSAL cache ──────│
     │◀── {authenticated:false}│                           │
     │                         │                           │
     │─── POST /api/auth/start▶│                           │
     │                         │─── POST /devicecode ─────▶│
     │                         │◀── {user_code, device_code│
     │◀── {user_code, uri, exp}│                           │
     │                         │                           │
     │  [User visits uri,      │                           │
     │   enters user_code]     │                           │
     │                         │                           │
     │─── GET /api/auth/poll ─▶│                           │
     │                         │─── POST /token ──────────▶│
     │                         │    (using device_code)    │
     │                         │◀── {authorization_pending}│
     │◀── {status: "pending"} │                           │
     │                         │    [User completes auth]  │
     │─── GET /api/auth/poll ─▶│                           │
     │                         │─── POST /token ──────────▶│
     │                         │◀── {access_token, refresh}│
     │                         │                           │
     │                         │  Save token to disk cache │
     │◀── {status:"auth'd"} ──│                           │
     │                         │                           │
     │  [Render ChatView]      │                           │
```

## 17.2 Token Caching and Refresh

MSAL handles token lifecycle automatically:

```python
# Token cache serialization (survives server restarts)
cache = msal.SerializableTokenCache()

# Load from disk on startup
if os.path.exists(CACHE_PATH):
    cache.deserialize(open(CACHE_PATH, "r").read())

# MSAL app uses cache
app = msal.PublicClientApplication(
    client_id=CLIENT_ID,
    authority=AUTHORITY,
    token_cache=cache,
)

# Acquire token silently (from cache or via refresh token)
result = app.acquire_token_silent(scopes=SCOPES, account=accounts[0])
if result:
    # Token was valid or was silently refreshed
    token = result["access_token"]

# Save updated cache after any token operation
if cache.has_state_changed:
    with open(CACHE_PATH, "w") as f:
        f.write(cache.serialize())
```

Token lifetime:
- **Access token**: 1 hour (auto-refreshed silently)
- **Refresh token**: 90 days (used by MSAL to get new access tokens)
- **Cache file**: Persists indefinitely until manually deleted

## 17.3 Multi-Tenant Configuration

The application defaults to `common` authority, which accepts:
- Personal Microsoft accounts (outlook.com, hotmail.com)
- Work/school accounts (any Azure AD tenant)

To restrict to a specific organization:
```bash
OUTLOOK_AUTHORITY=https://login.microsoftonline.com/YOUR_TENANT_ID
```

## 17.4 Security Considerations for Authentication

| Risk | Mitigation |
|------|-----------|
| Token cache file compromised | Store in secure directory; never commit to git |
| CORS allows all origins | Restrict to frontend domain in production |
| Device code exposed in UI | Code expires in 15 minutes; displayed only to authenticated session |
| Token scope creep | Only minimum required scopes are requested |
| Unauthorized API access | All endpoints check `_is_authenticated()` before executing |

---

# SECTION 18 — INSTALLATION GUIDE

## 18.1 Prerequisites

Before installing Outlook Assistant, ensure the following are available:

| Requirement | Version | Check Command |
|-------------|---------|---------------|
| Python | 3.10 or higher | `python --version` |
| Node.js | 18 or higher | `node --version` |
| npm | 9 or higher | `npm --version` |
| Git | Any | `git --version` |
| LM Studio | Latest | Download from lmstudio.ai |
| Azure Account | Active subscription or free tier | portal.azure.com |

## 18.2 Step 1: Clone the Repository

```bash
git clone https://github.com/your-username/outlook-assistant.git
cd outlook-assistant
```

Or, if starting from a local folder:
```bash
cd "c:\Users\Namya_Shah\Desktop\outlook mcp"
```

## 18.3 Step 2: Python Environment Setup

Create and activate a virtual environment (recommended):

```bash
# Create virtual environment
python -m venv venv

# Activate (Windows)
venv\Scripts\activate

# Activate (macOS / Linux)
source venv/bin/activate

# Verify activation
which python    # Should show venv path
```

Install Python dependencies:

```bash
pip install -r requirements.txt
```

**requirements.txt contents:**
```
msal>=1.28.0
requests>=2.31.0
python-dotenv>=1.0.0
fastapi>=0.111.0
uvicorn[standard]>=0.30.0
openai>=1.30.0
pydantic>=2.7.0
```

## 18.4 Step 3: Frontend Setup

```bash
# Navigate to web directory
cd web

# Install npm dependencies
npm install

# Build the React app (production bundle)
npm run build

# Go back to project root
cd ..
```

The `npm run build` command creates `web/dist/` which FastAPI serves as static files.

For active frontend development with hot reload:
```bash
cd web
npm run dev
# Frontend runs on http://localhost:5173
# Backend must run on http://localhost:8000 (Vite proxies API calls)
```

## 18.5 Step 4: LM Studio Setup

1. Download LM Studio from [lmstudio.ai](https://lmstudio.ai)
2. Install and launch LM Studio.
3. In the **Discover** tab, search for and download a model:
   - Recommended: `google/gemma-3-4b-it-GGUF` (4B, balanced)
   - Alternative: `lmstudio-community/Meta-Llama-3.1-8B-Instruct-GGUF`
4. Load the model in LM Studio.
5. Enable the **Local Server** in the Developer tab.
6. Verify the server is running: `http://127.0.0.1:1234/v1/models`

## 18.6 Step 5: Azure App Registration

See Section 20 for complete Azure setup. Quick summary:
1. Go to [portal.azure.com](https://portal.azure.com) → Azure Active Directory → App Registrations
2. Create a new registration with supported account type: "Accounts in any organizational directory and personal Microsoft accounts"
3. Add delegated API permissions: `Mail.Read`, `Mail.Send`, `Mail.ReadWrite`, `User.Read`, `Calendars.ReadWrite`
4. Copy the Application (Client) ID

## 18.7 Step 6: Environment Configuration

```bash
# Copy the example environment file
cp .env.example .env

# Edit with your values
notepad .env    # Windows
nano .env       # Linux/macOS
```

Required `.env` values:
```bash
OUTLOOK_CLIENT_ID=your-azure-client-id-here
OUTLOOK_AUTHORITY=https://login.microsoftonline.com/common
OUTLOOK_SCOPES=Mail.Read Mail.Send Mail.ReadWrite User.Read Calendars.ReadWrite
LMSTUDIO_BASE_URL=http://127.0.0.1:1234/v1
LMSTUDIO_MODEL=gemma-3-4b-it
LMSTUDIO_API_KEY=lm-studio
```

## 18.8 Step 7: Launch the Application

```bash
# From project root (with venv activated)
uvicorn server:app --host 0.0.0.0 --port 8000 --reload
```

Open browser: `http://localhost:8000`

---

# SECTION 19 — ENVIRONMENT VARIABLES SETUP

## 19.1 Complete Environment Variables Reference

Create a `.env` file in the project root with the following variables:

```bash
# ─────────────────────────────────────────
# MICROSOFT GRAPH API AUTHENTICATION
# ─────────────────────────────────────────

# Required: Azure App Registration Client ID
OUTLOOK_CLIENT_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx

# OAuth authority (common = personal + work accounts)
OUTLOOK_AUTHORITY=https://login.microsoftonline.com/common

# Space-separated Microsoft Graph permission scopes
OUTLOOK_SCOPES=Mail.Read Mail.Send Mail.ReadWrite User.Read Calendars.ReadWrite

# Path to MSAL token cache file (auto-created on first auth)
OUTLOOK_TOKEN_CACHE=.outlook_msal_token_cache.bin

# Optional: Hardcode sender email (if different from authenticated account)
OUTLOOK_SENDER_EMAIL=

# ─────────────────────────────────────────
# LM STUDIO CONFIGURATION
# ─────────────────────────────────────────

# LM Studio API base URL (default for local installation)
LMSTUDIO_BASE_URL=http://127.0.0.1:1234/v1

# Model identifier as shown in LM Studio (use exact name)
LMSTUDIO_MODEL=gemma-3-4b-it

# API key (any non-empty string; LM Studio ignores it)
LMSTUDIO_API_KEY=lm-studio

# Request timeout in seconds
LMSTUDIO_TIMEOUT=120

# ─────────────────────────────────────────
# AGENT FEATURE FLAGS
# ─────────────────────────────────────────

# Enable tool-first routing (pre-execute tools before LLM call)
ENABLE_TOOL_FIRST_ROUTING=true

# Use AI summarization tools vs basic list tools
ENABLE_SEMANTIC_TOOLS=true

# ─────────────────────────────────────────
# SERVER CONFIGURATION
# ─────────────────────────────────────────

# SQLite database file path
DATABASE_PATH=chat.db

# Inbox polling interval in seconds
INBOX_POLL_INTERVAL=30
```

## 19.2 Variable Lookup Table

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `OUTLOOK_CLIENT_ID` | **Yes** | None | Azure App Registration Client ID |
| `OUTLOOK_AUTHORITY` | No | `common` | Microsoft login authority URL |
| `OUTLOOK_SCOPES` | No | See above | Space-separated Graph API scopes |
| `OUTLOOK_TOKEN_CACHE` | No | `.outlook_msal_token_cache.bin` | Token cache file path |
| `LMSTUDIO_BASE_URL` | No | `http://127.0.0.1:1234/v1` | LM Studio server URL |
| `LMSTUDIO_MODEL` | No | `local-model` | Model name in LM Studio |
| `LMSTUDIO_API_KEY` | No | `lm-studio` | Ignored by LM Studio |
| `LMSTUDIO_TIMEOUT` | No | `120` | Request timeout (seconds) |
| `ENABLE_TOOL_FIRST_ROUTING` | No | `true` | Enable pre-execution routing |
| `DATABASE_PATH` | No | `chat.db` | SQLite file path |

## 19.3 Docker Environment

When using Docker, environment variables are passed via the `env_file` directive in `docker-compose.yml`:

```yaml
services:
  app:
    env_file:
      - .env
    environment:
      # Override for Docker networking
      - LMSTUDIO_BASE_URL=http://host.docker.internal:1234/v1
```

`host.docker.internal` is a special Docker DNS name that resolves to the host machine's IP, allowing the container to reach LM Studio running on the host.

---

# SECTION 20 — AZURE APP REGISTRATION SETUP

## 20.1 Overview

To use Microsoft Graph API, the application must be registered in Azure Active Directory (Azure AD). This creates an **Application Identity** with specific permissions.

## 20.2 Step-by-Step Registration

### Step 1: Access Azure Portal

1. Go to [https://portal.azure.com](https://portal.azure.com)
2. Sign in with a Microsoft account (personal or work/school)
3. In the top search bar, search for **"App registrations"**
4. Click **"App registrations"** under Services

### Step 2: Create New Registration

1. Click **"+ New registration"**
2. Fill in the form:
   - **Name**: `Outlook Assistant` (or any name)
   - **Supported account types**: Select **"Accounts in any organizational directory (Any Azure AD directory - Multitenant) and personal Microsoft accounts (e.g. Skype, Xbox)"**
   - **Redirect URI**: Leave blank (device flow does not require a redirect URI)
3. Click **"Register"**

### Step 3: Note the Client ID

After registration, you'll see the **Overview** page. Copy the **Application (client) ID** — this is your `OUTLOOK_CLIENT_ID`:

```
Application (client) ID: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
```

### Step 4: Configure API Permissions

1. In the left sidebar, click **"API permissions"**
2. Click **"+ Add a permission"**
3. Select **"Microsoft Graph"**
4. Select **"Delegated permissions"**
5. Search for and add the following permissions:

| Permission | Type | Purpose |
|-----------|------|---------|
| `Mail.Read` | Delegated | Read emails |
| `Mail.Send` | Delegated | Send emails |
| `Mail.ReadWrite` | Delegated | Delete, move, archive |
| `User.Read` | Delegated | Read user profile |
| `Calendars.ReadWrite` | Delegated | Read and create events |

6. Click **"Add permissions"**
7. Click **"Grant admin consent"** (if you have admin rights) — otherwise each user grants consent during first authentication

### Step 5: Enable Public Client Flows

Device flow requires the app to be configured as a **public client** (no client secret):

1. In the left sidebar, click **"Authentication"**
2. Scroll down to **"Advanced settings"**
3. Set **"Allow public client flows"** to **"Yes"**
4. Click **"Save"**

### Step 6: Verify Configuration

Your final App Registration should look like:

```
App name:       Outlook Assistant
Client ID:      xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
Account types:  Multitenant + Personal
Redirect URIs:  None (device flow)
API permissions:
  ✓ Mail.Read (Delegated)
  ✓ Mail.Send (Delegated)
  ✓ Mail.ReadWrite (Delegated)
  ✓ User.Read (Delegated)
  ✓ Calendars.ReadWrite (Delegated)
Public client:  Yes
```

## 20.3 Common Registration Mistakes

| Mistake | Symptom | Fix |
|---------|---------|-----|
| Wrong account type selected | Work accounts can't sign in | Select "Multitenant + Personal" |
| Public client not enabled | `AADSTS7000218` error | Enable in Authentication settings |
| Missing Mail.ReadWrite | Archive/delete fails | Add Mail.ReadWrite scope |
| Admin consent not granted | Users see long consent screen | Grant admin consent in portal |
| Wrong Client ID in .env | `AADSTS700016` error | Copy exact ID from Overview page |

---

# SECTION 21 — RUNNING THE PROJECT

## 21.1 Development Mode

```bash
# Terminal 1: Start FastAPI backend
cd "c:\Users\Namya_Shah\Desktop\outlook mcp"
source venv/bin/activate    # or venv\Scripts\activate on Windows
uvicorn server:app --host 0.0.0.0 --port 8000 --reload

# Terminal 2: Start React frontend with hot reload
cd web
npm run dev
# Frontend: http://localhost:5173 (proxied to backend on :8000)

# Terminal 3: LM Studio
# Launch LM Studio desktop app
# Load your model
# Start local server (Developer tab)
```

## 21.2 Production Mode (Serve React from FastAPI)

```bash
# Build React app
cd web
npm run build
cd ..

# Run backend (serves both API and frontend)
uvicorn server:app --host 0.0.0.0 --port 8000

# Open: http://localhost:8000
```

## 21.3 First Run: Authentication

On first launch, you will see the authentication screen:

```
┌────────────────────────────────────────────────────────┐
│              OUTLOOK ASSISTANT                          │
│                                                         │
│  To connect your Microsoft account:                    │
│                                                         │
│  1. Click the button below                             │
│  2. Visit: https://microsoft.com/devicelogin           │
│  3. Enter the code shown                               │
│                                                         │
│         [Connect Microsoft Account]                    │
└────────────────────────────────────────────────────────┘
```

After clicking and completing authentication in the browser, the app automatically refreshes and shows the chat interface.

## 21.4 Verifying Everything Works

```bash
# Test backend health
curl http://localhost:8000/api/health
# Expected: {"status": "ok"}

# Test auth status
curl http://localhost:8000/api/auth/status
# Expected: {"authenticated": false} or {"authenticated": true, "email": "..."}

# Test LM Studio connection (from backend)
curl http://127.0.0.1:1234/v1/models
# Expected: {"object":"list","data":[{"id":"gemma-3-4b-it",...}]}
```

## 21.5 Startup Checklist

| Step | Command | Expected Result |
|------|---------|----------------|
| Python venv active | `which python` | Points to venv |
| Dependencies installed | `pip list | grep fastapi` | Shows fastapi version |
| `.env` configured | `cat .env` | Has OUTLOOK_CLIENT_ID |
| Frontend built | `ls web/dist` | Contains index.html |
| LM Studio running | curl LM Studio URL | Returns model list |
| Backend starts | `uvicorn server:app` | "Application startup complete" |
| Browser opens | `http://localhost:8000` | Shows app UI |

---

# SECTION 22 — DOCKER SETUP

## 22.1 Docker Architecture

The application uses a **multi-stage Docker build**:

```
Stage 1: Node Builder
  ├── FROM node:18-alpine
  ├── COPY web/package.json, web/src
  ├── RUN npm install
  └── RUN npm run build → /app/web/dist

Stage 2: Python Runtime
  ├── FROM python:3.11-slim
  ├── COPY requirements.txt
  ├── RUN pip install -r requirements.txt
  ├── COPY --from=builder /app/web/dist → /app/web/dist
  ├── COPY server.py, agent/, app/
  └── CMD uvicorn server:app --host 0.0.0.0 --port 8080
```

## 22.2 Dockerfile

```dockerfile
# Stage 1: Build React frontend
FROM node:18-alpine AS frontend-builder
WORKDIR /app/web
COPY web/package.json web/package-lock.json ./
RUN npm ci --production=false
COPY web/src ./src
COPY web/index.html web/vite.config.js ./
RUN npm run build

# Stage 2: Python backend
FROM python:3.11-slim
WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend source
COPY server.py db.py ./
COPY agent/ ./agent/
COPY app/ ./app/

# Copy built frontend from stage 1
COPY --from=frontend-builder /app/web/dist ./web/dist

# Expose port
EXPOSE 8080

# Run FastAPI
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8080"]
```

## 22.3 docker-compose.yml

```yaml
version: "3.9"

services:
  app:
    build: .
    ports:
      - "8080:8080"
    env_file:
      - .env
    environment:
      # Override LM Studio URL for Docker networking
      - LMSTUDIO_BASE_URL=http://host.docker.internal:1234/v1
    volumes:
      # Persist SQLite database
      - ./chat.db:/app/chat.db
      # Persist MSAL token cache
      - ./.outlook_msal_token_cache.bin:/app/.outlook_msal_token_cache.bin
    extra_hosts:
      # Allow container to reach host machine (for LM Studio)
      - "host.docker.internal:host-gateway"
    restart: unless-stopped
```

## 22.4 Docker Commands

```bash
# Build and start the application
docker compose up --build

# Run in background (detached mode)
docker compose up -d --build

# View logs
docker compose logs -f

# Stop the application
docker compose down

# Rebuild only (no start)
docker compose build

# Remove containers + volumes
docker compose down -v

# Shell into running container
docker compose exec app bash

# Check container status
docker compose ps
```

## 22.5 Docker Environment Notes

| Consideration | Detail |
|--------------|--------|
| LM Studio URL | Use `host.docker.internal:1234` instead of `127.0.0.1:1234` |
| Token cache | Mount `.outlook_msal_token_cache.bin` to avoid re-authentication |
| Database | Mount `chat.db` to persist conversations |
| Port | Container runs on 8080; map to any host port you prefer |
| Linux host | Add `extra_hosts: host.docker.internal:host-gateway` for host access |

## 22.6 Docker Build Time Optimization

The multi-stage build ensures the final image is lean:

```bash
# Check image size
docker images | grep outlook

# Expected: ~300MB (Python + deps, no Node.js in final image)

# Layer cache optimization:
# package.json is copied BEFORE src/ so npm install only re-runs
# when dependencies change, not when source code changes
```

---

*End of Part 2 — Sections 11–22*
