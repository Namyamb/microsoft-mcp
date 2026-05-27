# OUTLOOK ASSISTANT
## Enterprise AI Email & Calendar Agent
### Technical Documentation — v1.0

---

**Project Name:** Outlook Assistant  
**Version:** 1.0  
**Document Type:** Software Engineering Technical Documentation  
**Prepared By:** Namya Shah  
**Date:** May 27, 2026  
**Classification:** Portfolio / Academic Submission / Company Presentation  

---

---

# TABLE OF CONTENTS

| # | Section | Page |
|---|---------|------|
| 1 | Cover Page | 1 |
| 2 | Project Overview | 3 |
| 3 | Problem Statement | 4 |
| 4 | Objectives | 5 |
| 5 | Features | 6 |
| 6 | Technology Stack | 8 |
| 7 | System Architecture | 10 |
| 8 | Folder Structure | 13 |
| 9 | Backend Documentation | 15 |
| 10 | Frontend Documentation | 24 |
| 11 | Database Design | 31 |
| 12 | Microsoft Graph API Integration | 33 |
| 13 | LM Studio Integration | 38 |
| 14 | AI Agent Workflow | 41 |
| 15 | Tool Calling System | 44 |
| 16 | SSE Streaming Architecture | 48 |
| 17 | Authentication Flow | 51 |
| 18 | Installation Guide | 54 |
| 19 | Environment Variables Setup | 58 |
| 20 | Azure App Registration Setup | 60 |
| 21 | Running the Project | 63 |
| 22 | Docker Setup | 65 |
| 23 | API Endpoints Reference | 68 |
| 24 | Example User Flows | 72 |
| 25 | Security Considerations | 76 |
| 26 | Error Handling | 79 |
| 27 | Troubleshooting Guide | 82 |
| 28 | Future Improvements | 85 |
| 29 | Advantages of the Project | 87 |
| 30 | Conclusion | 89 |

---

---

# SECTION 2 — PROJECT OVERVIEW

## 2.1 Introduction

**Outlook Assistant** is a production-grade, AI-powered email and calendar management web application that integrates Microsoft Outlook (via Microsoft Graph API) with a locally-running large language model (LLM) through LM Studio. The application allows users to converse with their email inbox in natural language — asking questions, requesting summaries, drafting emails, and taking actions — all through a real-time streaming chat interface.

The system is designed to eliminate the friction of traditional email management by providing an intelligent conversational layer over Microsoft 365 mailbox data. Instead of navigating menus and folders, users simply describe what they want in plain English, and the AI agent orchestrates the appropriate API calls, executes them, and returns a grounded, contextually-aware response.

## 2.2 Core Concept

The application is built around a **hybrid agentic architecture**:

1. **Deterministic Intent Routing** — a rule-based router classifies the user's intent (mailbox query, summarization, action, drafting, or general chat) without relying on the LLM for classification, ensuring speed and predictability.

2. **Tool-First Execution** — for mailbox-related queries, the router pre-executes the most appropriate Microsoft Graph API tool *before* passing control to the LLM, ensuring that every AI response is grounded in real, live email data.

3. **Agentic LLM Loop** — for complex or multi-step requests (such as composing an email or answering a general question), the LLM autonomously decides which tools to invoke, collects results, and synthesizes a response.

4. **Real-Time Streaming** — all AI responses are streamed to the frontend via Server-Sent Events (SSE), providing a conversational, low-latency user experience with live tool status indicators.

## 2.3 Target Users

| User Type | Use Case |
|-----------|----------|
| Professionals | Quickly triage inbox, find emails, draft replies |
| Developers | AI/ML portfolio project, RAG + tool-calling showcase |
| Students | Major project submission demonstrating full-stack + AI integration |
| Teams | Internal AI email agent deployable on-premises |

---

# SECTION 3 — PROBLEM STATEMENT

## 3.1 The Email Overload Problem

Email remains the dominant communication channel in professional environments. The average knowledge worker receives over **120 emails per day** and spends approximately **2.5 hours per day** reading and responding to email (McKinsey Global Institute, 2012). This inefficiency is compounded by:

- **Information overload**: Critical emails buried under newsletters, promotions, and low-priority threads.
- **Context switching**: Users must leave their current task to navigate to a mail client, search, and read.
- **Repetitive actions**: Flagging, archiving, categorizing, and replying follow predictable patterns yet require manual effort.
- **Search limitations**: Traditional search requires exact keyword recall; natural language search is unavailable.

## 3.2 Gaps in Existing Solutions

Existing AI email tools (such as Microsoft Copilot, Google Gemini for Workspace) are:

- **Cloud-dependent**: All data is processed on remote servers, raising data privacy concerns.
- **Subscription-locked**: Expensive enterprise licenses required.
- **Black-box**: No transparency into what tools are called or what data is retrieved.
- **Not locally deployable**: Cannot be self-hosted or run in air-gapped environments.

## 3.3 The Solution

Outlook Assistant addresses these gaps by:

- Running the AI inference **locally** via LM Studio (no cloud API costs or data leakage).
- Providing **complete transparency** with tool call badges showing exactly which operations were performed.
- Being **fully self-hostable** via Docker.
- Using a **grounded architecture** that prevents AI hallucination by always fetching real data before generating a response.
- Offering a **modern, real-time chat interface** with session persistence and dark/light mode.

---

# SECTION 4 — OBJECTIVES

## 4.1 Primary Objectives

The core technical objectives of the Outlook Assistant project are:

1. **Authenticate securely** with Microsoft 365 using the OAuth 2.0 device flow via MSAL, without requiring a web redirect URI.

2. **Execute natural language email queries** — translate conversational requests ("show emails from Alice about the project") into precise Microsoft Graph API calls.

3. **Provide AI-generated email intelligence** — summaries, urgency detection, draft generation, task extraction — using a locally-hosted LLM.

4. **Enable email actions** — archive, delete, flag, mark read/unread — directly from the chat interface with confirmation safeguards.

5. **Stream responses in real-time** — use SSE so users see the AI thinking, tool execution, and response generation as it happens.

6. **Persist sessions** — store full conversation history in SQLite so users can return to previous chats with full context.

7. **Send and manage emails** — compose, draft, reply, forward, and send emails through natural language commands.

8. **Integrate calendar** — read upcoming events, today's schedule, and create new calendar events.

## 4.2 Secondary Objectives

- Deploy via Docker with a single `docker compose up` command.
- Support dark and light themes with preference persistence.
- Auto-title conversations based on the first user message.
- Notify users of new incoming emails via a real-time SSE notification banner.
- Implement a robust error handling and retry system for Graph API rate limits and transient failures.

---

# SECTION 5 — FEATURES

## 5.1 Authentication & Authorization

| Feature | Description |
|---------|-------------|
| Microsoft OAuth 2.0 Device Flow | Users authenticate by visiting a URL and entering a device code — no redirect URI needed |
| MSAL Token Caching | Access tokens are cached to disk; silent refresh happens automatically on subsequent runs |
| Session Persistence | Authentication state survives server restarts; users are not required to re-authenticate |
| Scope-Based Permissions | Only the minimum required Microsoft Graph scopes are requested |

## 5.2 Email Reading & Search

| Feature | Description |
|---------|-------------|
| Inbox Listing | Fetch latest N emails with sender, subject, preview, date, and flags |
| Unread Email Retrieval | Filter inbox to only unread messages |
| Flagged Email Retrieval | Scan inbox and return messages marked as flagged |
| Full-Text Search | KQL-based search across subject, body, sender |
| Sender-Based Filtering | "Show emails from alice@company.com" with heuristic domain/brand matching |
| Date-Range Filtering | Filter emails by a specified date range |
| Email Detail View | Fetch full email body, metadata, and attachment indicators |
| Natural Language Resolution | Convert "first email", "latest from Alice", "that email" into concrete email IDs |

## 5.3 AI Intelligence Features

| Feature | Description |
|---------|-------------|
| Email Summarization | 2–4 bullet-point summary of a single email |
| Inbox Summary | High-level briefing across multiple unread/flagged emails |
| Draft Generation | Compose a new email from a natural language description |
| Reply Drafting | Generate a contextual reply to any fetched email |
| Email Classification | Label emails as work, personal, finance, promo, spam |
| Urgency Detection | Rate emails as low / medium / high urgency |
| Sentiment Analysis | Classify email tone as negative / neutral / positive |
| Task Extraction | Extract action items from an email as a checklist |
| Date & Contact Extraction | Extract meeting dates and contact references |
| Email Rewriting | Rewrite draft in formal, casual, or concise styles |
| Follow-up Generation | Auto-generate follow-up emails from context |

## 5.4 Email Actions

| Feature | Description |
|---------|-------------|
| Send Email | Send a new message immediately |
| Create Draft | Save email to Drafts folder, retrieve draft ID |
| Send Saved Draft | Send a previously created draft by draft ID |
| Reply / Reply All | Reply to a message with AI or user-provided content |
| Forward Email | Forward message to another recipient |
| Archive | Move message to Archive folder |
| Delete | Delete message (with confirmation safeguard) |
| Mark Read / Unread | Toggle read status |
| Flag / Unflag | Toggle flag status |
| Move to Folder | Move message to a named folder |
| List Folders | Enumerate mailbox folders |
| Create Folder | Create a new mailbox folder |

## 5.5 Calendar Features

| Feature | Description |
|---------|-------------|
| Today's Events | List all calendar events for today |
| Upcoming Events | List events for the next N days |
| Search Events | Search calendar by keyword |
| Create Event | Add a new calendar event |

## 5.6 Chat Interface Features

| Feature | Description |
|---------|-------------|
| Real-Time Streaming | AI responses stream token-by-token via SSE |
| Tool Call Badges | Visual indicators showing which tools are running / completed |
| Email Cards | Rich email previews with inline action buttons inside chat |
| Session Management | Create, rename, delete, and switch between conversation sessions |
| Markdown Rendering | AI responses rendered with headers, bold, code blocks, and lists |
| Dark / Light Mode | User-toggled theme with localStorage persistence |
| Inbox Notifications | Live banner when new emails arrive (SSE-based) |
| Conversation Auto-Titling | Sessions automatically titled from the first user message |
| Stop Generation | Abort an in-progress AI response mid-stream |
| Typing Indicator | Animated dots while AI is thinking before text appears |
| Quick Suggestions | Clickable starter prompts on empty chat screen |

---

# SECTION 6 — TECHNOLOGY STACK

## 6.1 Overview Table

| Layer | Technology | Version | Purpose |
|-------|-----------|---------|---------|
| Frontend Framework | React | 18.3.x | Component-based UI |
| Frontend Build | Vite | 5.3.x | Fast bundler and dev server |
| Backend Framework | FastAPI | 0.111.x | Async Python API server |
| ASGI Server | Uvicorn | Latest | Production Python runtime |
| Authentication | MSAL (Python) | 1.28.x | Microsoft OAuth 2.0 |
| Graph API | Microsoft Graph REST | v1.0 | Email, calendar operations |
| AI Inference | LM Studio | Latest | Local LLM serving |
| LLM Client | OpenAI Python SDK | 1.30.x | OpenAI-compatible calls to LM Studio |
| Database | SQLite | 3.x (WAL) | Session and message persistence |
| Containerization | Docker + Compose | Latest | Single-command deployment |
| HTTP Client | Requests | 2.31.x | Graph API calls |
| Data Validation | Pydantic | 2.7.x | Request/response schemas |
| Environment Config | python-dotenv | 1.0.x | `.env` file loading |

## 6.2 Frontend Stack Detail

```
React 18
├── Vite (bundler, HMR, dev server)
├── JSX (component templating)
├── CSS Modules / Global CSS (index.css)
├── Fetch API (HTTP + SSE consumer)
└── localStorage (theme + session preference)
```

React 18 introduces **concurrent features** and improved streaming support. The application uses functional components exclusively with React Hooks (`useState`, `useEffect`, `useRef`, `useCallback`). Vite replaces Create React App for dramatically faster cold starts and hot module replacement.

## 6.3 Backend Stack Detail

```
FastAPI
├── Uvicorn (ASGI runtime)
├── Pydantic (request body validation)
├── StreamingResponse (SSE delivery)
├── Background threads (auth polling, inbox polling)
├── SQLite via sqlite3 (WAL mode)
└── python-dotenv (.env config)

Agent Layer
├── agent/loop.py (LLM orchestration)
├── agent/router.py (deterministic intent classification)
└── agent/schemas.py (OpenAI-compatible tool schemas)

Outlook Integration
├── app/integrations/outlook/core.py (Graph API client)
├── app/integrations/outlook/core_v2.py (NL resolution)
├── app/integrations/outlook/ai.py (LM Studio AI tools)
└── app/integrations/outlook/registry.py (tool factory)
```

## 6.4 Why These Technologies?

| Technology | Rationale |
|-----------|-----------|
| FastAPI | Async-native, auto-generates OpenAPI docs, type-safe with Pydantic, excellent streaming support via `StreamingResponse` |
| React 18 | Industry-standard UI library, component reusability, large ecosystem, excellent for real-time UIs |
| LM Studio | Run any open-source LLM locally with zero cloud cost; exposes an OpenAI-compatible `/v1` endpoint |
| SQLite | Zero-config, serverless, file-based — perfect for single-user and portfolio deployments with no DevOps overhead |
| MSAL | Official Microsoft authentication library; handles token refresh, caching, and device flow |
| SSE over WebSocket | SSE is simpler (HTTP/1.1 compatible, no handshake), one-directional, and natively supported by `EventSource` and `fetch` |
| Docker | Reproducible builds, one-command deployment, solves "works on my machine" problems |

---

# SECTION 7 — SYSTEM ARCHITECTURE

## 7.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         USER BROWSER                                 │
│                                                                       │
│  ┌─────────────┐   ┌──────────────┐   ┌────────────────────────┐   │
│  │  Sidebar     │   │  ChatView     │   │  AuthFlow              │   │
│  │  (Sessions)  │   │  (Messages)   │   │  (Device Code UI)      │   │
│  └──────┬───────┘   └──────┬───────┘   └───────────┬────────────┘   │
│         │                  │                        │                 │
└─────────┼──────────────────┼────────────────────────┼────────────────┘
          │ REST API          │ SSE Stream             │ REST API
          ▼                  ▼                        ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      FASTAPI BACKEND (server.py)                      │
│                                                                       │
│  ┌──────────────┐  ┌───────────────┐  ┌──────────────────────────┐  │
│  │  Auth Routes  │  │  Chat Routes   │  │  Session / Email Routes  │  │
│  │  /auth/start  │  │  POST /chat    │  │  /sessions, /email/action│  │
│  │  /auth/poll   │  │  GET /notifs   │  │  CRUD operations         │  │
│  └──────┬───────┘  └──────┬────────┘  └──────────────────────────┘  │
│         │                 │                                           │
│         ▼                 ▼                                           │
│  ┌──────────────┐  ┌───────────────────────────────────────────────┐ │
│  │  MSAL Auth   │  │             AGENT LAYER                        │ │
│  │  Device Flow  │  │                                               │ │
│  │  Token Cache  │  │  ┌───────────┐   ┌──────────────────────────┐│ │
│  └──────────────┘  │  │  router.py │   │      loop.py             ││ │
│                    │  │  (Intent   │──▶│  (Orchestration + SSE    ││ │
│                    │  │   Classify)│   │   Streaming + Tool Exec) ││ │
│                    │  └───────────┘   └──────────┬───────────────┘│ │
│                    └──────────────────────────────┼────────────────┘ │
│                                                   │                   │
│  ┌────────────────────────────────────────────────┼──────────────┐   │
│  │                TOOL REGISTRY (registry.py)      │              │   │
│  │                                                 ▼              │   │
│  │  ┌────────────────────┐  ┌──────────────────────────────────┐ │   │
│  │  │  core.py           │  │  ai.py                           │ │   │
│  │  │  Graph API Client  │  │  LM Studio AI Functions          │ │   │
│  │  │  60+ operations    │  │  (summarize, draft, classify)    │ │   │
│  │  └─────────┬──────────┘  └──────────────┬───────────────────┘ │   │
│  └────────────┼──────────────────────────────┼────────────────────┘   │
│               │                              │                         │
└───────────────┼──────────────────────────────┼─────────────────────────┘
                │                              │
                ▼                              ▼
┌──────────────────────────┐    ┌──────────────────────────────────┐
│  MICROSOFT GRAPH API      │    │  LM STUDIO (Local LLM)           │
│  graph.microsoft.com/v1.0 │    │  http://127.0.0.1:1234/v1        │
│  Email / Calendar / User  │    │  OpenAI-compatible endpoint      │
└──────────────────────────┘    └──────────────────────────────────┘
                                              │
                                              ▼
                                 ┌────────────────────────┐
                                 │  Any Open-Source LLM   │
                                 │  (Gemma, Llama, Mistral│
                                 │   Qwen, Phi, etc.)     │
                                 └────────────────────────┘
```

## 7.2 Agent Pipeline Architecture

The core intelligence of the system is the **hybrid agent pipeline**. This is the most architecturally significant part of the project:

```
User Message
     │
     ▼
┌────────────────────────────────────────┐
│  router.py — Deterministic Classifier   │
│                                          │
│  Input:  Raw user message (string)       │
│  Logic:  Keyword + pattern matching      │
│  Output: RouteDecision {                 │
│    intent,        # MAILBOX_QUERY etc.   │
│    mode,          # TOOL_FIRST / AGENTIC │
│    requires_tools,# bool                 │
│    recommended_tool, # e.g. outlook_get_unread_emails
│    tool_args,     # pre-built args dict  │
│    reason         # human-readable note  │
│  }                                       │
└────────────────┬───────────────────────┘
                 │
        ┌────────┴──────────┐
        │                   │
        ▼ TOOL_FIRST         ▼ AGENTIC
┌──────────────┐      ┌──────────────────────────────┐
│ Pre-execute   │      │ Pass full context to LLM      │
│ recommended   │      │ LLM selects tools autonomously│
│ tool BEFORE   │      │ (temperature=0.4, max 8 iter) │
│ calling LLM   │      └──────────────┬───────────────┘
└──────┬───────┘                      │
       │                              │
       ▼                              ▼
┌──────────────────────────────────────────────────────┐
│             LM STUDIO LLM LOOP (loop.py)              │
│                                                        │
│  1. Assemble messages (system + history + context)    │
│  2. POST /v1/chat/completions (stream=True)           │
│  3. Buffer streaming deltas                           │
│  4. On finish_reason=tool_calls: execute tools        │
│  5. Append tool results to message list               │
│  6. Repeat until finish_reason=stop or max_iterations │
│  7. Yield SSE events for each phase                   │
└──────────────────────────────────────────────────────┘
                         │
                         ▼ SSE Events
              text_delta / tool_start /
              tool_end / error / done
                         │
                         ▼
               React ChatView
               (live streaming UI)
```

## 7.3 Data Flow Architecture

```
POST /api/chat
{session_id, message}
        │
        ▼
server.py saves user message to SQLite
        │
        ▼
Load conversation history from SQLite
        │
        ▼
Spawn worker thread → run_agent_stream()
        │
        ├──► router.py classifies intent
        │
        ├──► [TOOL_FIRST] Execute recommended tool immediately
        │         └──► Yield: tool_start, tool_end events
        │
        ├──► Build LLM messages array
        │         ├── system prompt
        │         ├── conversation history
        │         └── [if tool_first] injected tool result
        │
        ├──► POST to LM Studio /v1/chat/completions (stream)
        │         └──► Yield: text_delta events
        │
        ├──► If LLM requests tool calls:
        │         ├──► Execute each tool via registry
        │         ├──► Yield: tool_start, tool_end events
        │         └──► Re-enter LLM with tool results
        │
        ├──► Collect final content + tool_calls
        │
        ├──► Save assistant message to SQLite
        │
        └──► Yield: done event
```

## 7.4 Thread Model

FastAPI is async (via Uvicorn/asyncio). However, MSAL and some Graph API calls are synchronous. The application uses Python threading to bridge this:

| Thread | Purpose |
|--------|---------|
| Main asyncio event loop | FastAPI request handling, SSE delivery |
| Auth polling thread | Background `acquire_token_by_device_flow()` |
| Agent worker thread | `run_agent_stream()` (sync LLM + tool calls) |
| Inbox poller thread | Every 30s, check for new emails |
| SSE queue per client | `queue.Queue` per `/notifications/stream` subscriber |

---

# SECTION 8 — FOLDER STRUCTURE

## 8.1 Complete File Tree

```
outlook mcp/
│
├── server.py                          # FastAPI entry point, all routes
├── db.py                              # SQLite session + message persistence
├── requirements.txt                   # Python package dependencies
├── Dockerfile                         # Multi-stage Docker build
├── docker-compose.yml                 # Service orchestration
├── .env                               # Environment configuration (not in git)
├── .env.example                       # Template for environment variables
├── chat.db                            # SQLite database (WAL journal mode)
├── .outlook_msal_token_cache.bin      # MSAL token cache (auto-generated)
│
├── agent/
│   ├── __init__.py
│   ├── loop.py                        # Agent orchestration and LLM streaming
│   ├── router.py                      # Deterministic intent classification
│   └── schemas.py                     # OpenAI-compatible tool schema definitions
│
├── app/
│   └── integrations/
│       └── outlook/
│           ├── __init__.py
│           ├── core.py                # Microsoft Graph API client (~800 lines)
│           ├── core_v2.py             # Natural language email ID resolution
│           ├── ai.py                  # LM Studio AI tools (summarize, draft, etc.)
│           ├── registry.py            # Tool registry factory (60+ tools)
│           └── utils.py               # Error classes, safety helpers
│
└── web/
    ├── package.json                   # npm dependencies
    ├── vite.config.js                 # Vite build configuration
    ├── index.html                     # HTML entry point
    ├── dist/                          # Built static files (served by FastAPI)
    └── src/
        ├── main.jsx                   # React entry point
        ├── App.jsx                    # Root component (auth gate + layout)
        ├── index.css                  # Global styles + CSS variables
        └── components/
            ├── AuthFlow.jsx           # Microsoft device code authentication UI
            ├── ChatView.jsx           # Main chat interface + SSE consumer
            ├── Sidebar.jsx            # Session list, create/rename/delete
            ├── MessageBubble.jsx      # Message rendering + markdown
            ├── EmailCard.jsx          # Email preview with inline actions
            ├── ToolCallBadge.jsx      # Tool execution status indicators
            └── NotificationBanner.jsx # New email notification banner
```

## 8.2 Module Responsibilities

| File | Responsibility | Lines |
|------|---------------|-------|
| `server.py` | All HTTP routes, SSE delivery, auth state, inbox polling | ~450 |
| `db.py` | SQLite operations: sessions, messages, CRUD | ~148 |
| `agent/loop.py` | LLM loop, tool execution, event streaming | ~393 |
| `agent/router.py` | Intent classification without LLM | ~350 |
| `agent/schemas.py` | 25+ tool definitions in OpenAI JSON schema | ~531 |
| `outlook/core.py` | All Microsoft Graph API operations | ~800 |
| `outlook/core_v2.py` | NL → email ID resolution wrapper | ~200 |
| `outlook/ai.py` | LM Studio client + 15 AI tool functions | ~200 |
| `outlook/registry.py` | Assembles all tools into callable dict | ~159 |
| `web/src/App.jsx` | Auth gating, layout, theme, session state | ~113 |
| `web/src/components/ChatView.jsx` | SSE streaming, message state, UI | ~268 |
| `web/src/components/Sidebar.jsx` | Session CRUD and navigation | ~129 |
| `web/src/components/MessageBubble.jsx` | Markdown + email card extraction | ~164 |
| `web/src/components/EmailCard.jsx` | Email display with inline actions | ~161 |
| `web/src/components/ToolCallBadge.jsx` | Tool status visual indicators | ~80 |

---

# SECTION 9 — BACKEND DOCUMENTATION

## 9.1 server.py — Main FastAPI Application

### 9.1.1 Application Setup

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import StreamingResponse
import threading, queue, sqlite3, json, time, os

app = FastAPI(title="Outlook Assistant API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],           # Restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup():
    init_db()                      # Create SQLite tables if not exist
```

FastAPI is initialized with CORS middleware allowing all origins (intended for local development; production deployments should restrict this to the frontend domain). On startup, `init_db()` creates the SQLite schema.

### 9.1.2 Authentication State Management

Authentication state is managed in-memory using a thread-safe dictionary:

```python
_auth_state = {
    "status": "unauthenticated",   # or "pending", "authenticated"
    "user_code": None,             # Device code shown to user
    "verification_uri": None,      # Microsoft login URL
    "expires_at": None,            # Code expiry timestamp
    "error": None,                 # Error message if any
}
_auth_lock = threading.Lock()      # Thread safety for state mutations
```

**Auth Endpoint Flow:**

```
POST /api/auth/start
    └──► Calls graph_client.initiate_device_flow()
    └──► Stores user_code + verification_uri in _auth_state
    └──► Spawns background thread to poll acquire_token_by_device_flow()
    └──► Returns {user_code, verification_uri, expires_at} to frontend

GET /api/auth/poll
    └──► Returns current _auth_state (status, user_code, error)

GET /api/auth/status
    └──► Checks if graph_client._is_authenticated()
    └──► Returns {authenticated: bool, email: str}
```

### 9.1.3 Chat Streaming Endpoint

The `/api/chat` endpoint is the most critical route in the application. It accepts a user message and streams an AI response using Server-Sent Events:

```python
@app.post("/api/chat")
async def chat(request: ChatRequest):
    # 1. Save user message to SQLite
    add_message(request.session_id, "user", request.message)

    # 2. Load prior conversation history
    history = get_agent_history(request.session_id)

    # 3. Create an asyncio queue for cross-thread communication
    result_queue = asyncio.Queue()

    # 4. Spawn worker thread (sync operations: LLM calls, Graph API)
    def worker():
        asyncio.run(run_agent_stream(
            history, request.message, request.session_id, result_queue
        ))
    thread = threading.Thread(target=worker, daemon=True)
    thread.start()

    # 5. SSE generator — reads queue, formats events
    async def event_generator():
        final_content = []
        final_tool_calls = []
        while True:
            event = await result_queue.get()
            if event["type"] == "done":
                # Save complete assistant message to DB
                add_message(
                    request.session_id, "assistant",
                    "".join(final_content),
                    json.dumps(final_tool_calls)
                )
                yield f"data: {json.dumps(event)}\n\n"
                break
            elif event["type"] == "text_delta":
                final_content.append(event["content"])
                yield f"data: {json.dumps(event)}\n\n"
            elif event["type"] in ("tool_start", "tool_end"):
                if event["type"] == "tool_end":
                    final_tool_calls.append(event)
                yield f"data: {json.dumps(event)}\n\n"
            else:
                yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
```

### 9.1.4 Email Action Endpoint

Direct email actions (archive, flag, delete, etc.) can be triggered without going through the chat AI:

```python
@app.post("/api/email/action")
async def email_action(request: EmailActionRequest):
    """
    Executes email actions directly via tool registry.
    Bypasses LLM entirely for deterministic operations.
    """
    action_to_tool = {
        "archive":      "outlook_archive_email",
        "delete":       "outlook_delete_email",
        "flag":         "outlook_flag_email",
        "unflag":       "outlook_unflag_email",
        "mark_read":    "outlook_mark_as_read",
        "mark_unread":  "outlook_mark_as_unread",
    }
    tool_name = action_to_tool[request.action]
    tools = _get_tools()
    result = tools[tool_name](email_id=request.email_id)
    return {"success": result.get("success", False), "data": result}
```

### 9.1.5 Inbox Notification System

A background thread continuously polls for new emails every 30 seconds and broadcasts to all SSE subscribers:

```python
_notification_subscribers: List[asyncio.Queue] = []

def _inbox_poller():
    """Background thread: polls for new emails every 30 seconds."""
    last_check = datetime.utcnow()
    while True:
        time.sleep(30)
        if not graph_client._is_authenticated():
            continue
        try:
            new_emails = graph_client.get_new_emails_since(last_check)
            if new_emails:
                _broadcast({"type": "new_emails", "count": len(new_emails),
                            "emails": new_emails[:3]})  # Preview first 3
            last_check = datetime.utcnow()
        except Exception:
            pass

def _broadcast(event: dict):
    for q in _notification_subscribers:
        try:
            q.put_nowait(event)
        except asyncio.QueueFull:
            pass

@app.get("/api/notifications/stream")
async def notification_stream():
    """SSE endpoint for inbox notifications."""
    q = asyncio.Queue(maxsize=20)
    _notification_subscribers.append(q)
    async def generator():
        try:
            while True:
                event = await q.get()
                yield f"data: {json.dumps(event)}\n\n"
        finally:
            _notification_subscribers.remove(q)
    return StreamingResponse(generator(), media_type="text/event-stream")
```

### 9.1.6 Static File Serving

After building the React frontend, FastAPI serves it directly:

```python
# Mount React build at root if dist folder exists
dist_path = os.path.join(os.path.dirname(__file__), "web", "dist")
if os.path.exists(dist_path):
    app.mount("/", StaticFiles(directory=dist_path, html=True), name="static")
```

This allows the application to be deployed as a single server — no separate Nginx or CDN required.

---

## 9.2 agent/loop.py — AI Orchestration Engine

### 9.2.1 System Prompt

The system prompt is carefully engineered to produce grounded, accurate responses:

```
You are Outlook Assistant, an AI agent with access to the user's
Microsoft Outlook account via Microsoft Graph API.

You have the following tools available:
[complete tool list injected at runtime]

CRITICAL RULES:
1. GROUND YOUR ANSWER IN TOOL RESULTS. If the router pre-executed a
   tool and injected the results, your answer MUST be based on that data.
2. DO NOT fabricate emails, senders, subjects, or dates.
3. For sending email: first use outlook_create_draft (returns draft_id),
   then outlook_send_draft(draft_id) when the user confirms.
4. When the user says "send it" or "send the draft", recover the
   draft_id from conversation history and call outlook_send_draft.
5. Be concise and helpful. Format email lists with sender, subject, date.
```

### 9.2.2 Intent-Driven Execution

```python
async def run_agent_stream(history, message, session_id, queue):
    # Step 1: Classify intent deterministically
    decision = classify_intent(message)
    await queue.put({"type": "route", "decision": decision.dict()})

    # Step 2: Tool-First pre-execution (if applicable)
    injected_tool_context = None
    if decision.mode == MODE_TOOL_FIRST and decision.recommended_tool:
        tool_result = await _pre_execute_routed_tool(decision, queue)
        if tool_result:
            injected_tool_context = tool_result

    # Step 3: Build LLM messages
    messages = _build_messages(history, message, injected_tool_context)

    # Step 4: Enter LLM loop
    await _llm_loop(messages, session_id, queue)
```

### 9.2.3 LLM Streaming Loop

```python
async def _llm_loop(messages, session_id, queue):
    tools = _get_tools()
    tool_schemas = TOOL_SCHEMAS  # from agent/schemas.py

    for iteration in range(MAX_ITERATIONS):  # MAX = 8
        # Stream from LM Studio
        stream = lm_client.chat.completions.create(
            model=LM_MODEL,
            messages=messages,
            tools=tool_schemas,
            tool_choice="auto",
            temperature=0.4,
            stream=True,
        )

        content_buffer = ""
        tool_call_buffer = {}  # index → {id, name, args}

        for chunk in stream:
            delta = chunk.choices[0].delta

            if delta.content:
                content_buffer += delta.content
                await queue.put({"type": "text_delta", "content": delta.content})

            if delta.tool_calls:
                for tc in delta.tool_calls:
                    idx = tc.index
                    if idx not in tool_call_buffer:
                        tool_call_buffer[idx] = {"id": tc.id, "name": "", "args": ""}
                    if tc.function.name:
                        tool_call_buffer[idx]["name"] += tc.function.name
                    if tc.function.arguments:
                        tool_call_buffer[idx]["args"] += tc.function.arguments

            if chunk.choices[0].finish_reason == "stop":
                await queue.put({"type": "done"})
                return

            if chunk.choices[0].finish_reason == "tool_calls":
                break  # Execute tools then re-enter loop

        # Execute all tool calls
        for tc in tool_call_buffer.values():
            await queue.put({"type": "tool_start", "name": tc["name"],
                             "args": tc["args"], "status": "running"})
            result = tools[tc["name"]](**json.loads(tc["args"]))
            await queue.put({"type": "tool_end", "name": tc["name"],
                             "result": result, "status": "done"})
            # Append tool result to messages for next iteration
            messages.append({"role": "tool", "content": json.dumps(result),
                              "tool_call_id": tc["id"]})

    # Exceeded max iterations
    await queue.put({"type": "text_delta",
                     "content": "\n\n_(Reached maximum iterations.)_"})
    await queue.put({"type": "done"})
```

### 9.2.4 Draft ID Recovery

A key safety feature: when the user says "send it" or "send the draft", the agent must send the *correct* draft without relying on the LLM's memory:

```python
def _extract_recent_draft_id(session_id: str) -> Optional[str]:
    """
    Scans the last 20 messages in the session for a successful
    outlook_create_draft tool call. Returns the draft_id if found.
    """
    messages = get_messages(session_id)[-20:]
    for msg in reversed(messages):
        if msg.get("tool_calls"):
            for tc in json.loads(msg["tool_calls"]):
                if (tc.get("name") == "outlook_create_draft" and
                        tc.get("result", {}).get("success")):
                    return tc["result"]["data"].get("draft_id")
    return None
```

---

## 9.3 agent/router.py — Deterministic Intent Router

### 9.3.1 Design Philosophy

The router avoids all LLM calls for classification. Instead, it uses fast string operations to categorize the user's intent. This has three benefits:

1. **Speed**: Classification completes in microseconds, not seconds.
2. **Reliability**: No model variance — the same input always produces the same output.
3. **Debuggability**: The `reason` field explains exactly why a decision was made.

### 9.3.2 Intent Types

```python
INTENT_MAILBOX_QUERY   = "mailbox_query"    # "show emails from alice"
INTENT_MAILBOX_SUMMARY = "mailbox_summary"  # "brief me on my inbox"
INTENT_MAILBOX_ACTION  = "mailbox_action"   # "delete first email"
INTENT_DRAFTING        = "drafting"         # "draft email to john"
INTENT_GENERAL_CHAT    = "general_chat"     # "who are you?"
```

### 9.3.3 Classification Logic

```python
def classify_intent(message: str) -> RouteDecision:
    msg = message.lower().strip()

    # Check for summary intent
    if any(k in msg for k in ["summarize", "brief me", "what's important",
                               "what is important", "overview"]):
        if _is_mail_context(msg):
            return RouteDecision(
                intent=INTENT_MAILBOX_SUMMARY,
                mode=MODE_TOOL_FIRST,
                recommended_tool="summarize_mailbox",
                reason="Summary keyword with mail context"
            )

    # Check for unread emails
    if "unread" in msg and _is_mail_context(msg):
        return RouteDecision(
            intent=INTENT_MAILBOX_QUERY,
            mode=MODE_TOOL_FIRST,
            recommended_tool="outlook_get_unread_emails",
            tool_args={},
            reason="Unread mail query"
        )

    # Check for sender query
    sender = _extract_sender(msg)
    if sender:
        return RouteDecision(
            intent=INTENT_MAILBOX_QUERY,
            mode=MODE_TOOL_FIRST,
            recommended_tool="outlook_find_messages",
            tool_args={"query": sender},
            reason=f"Sender query: {sender}"
        )

    # Check for action on ordinal reference
    ordinal = _extract_ordinal(msg)
    if ordinal and _has_action_verb(msg):
        return RouteDecision(
            intent=INTENT_MAILBOX_ACTION,
            mode=MODE_TOOL_FIRST,
            recommended_tool="resolve_email_id",
            tool_args={"reference": ordinal},
            reason=f"Action on ordinal position: {ordinal}"
        )

    # Check for drafting
    if any(k in msg for k in ["draft", "compose", "write an email",
                               "send an email to"]):
        return RouteDecision(
            intent=INTENT_DRAFTING,
            mode=MODE_AGENTIC,
            reason="Drafting intent detected"
        )

    # Default: general chat
    return RouteDecision(
        intent=INTENT_GENERAL_CHAT,
        mode=MODE_AGENTIC,
        reason="No specific mail intent detected"
    )
```

---

## 9.4 agent/schemas.py — Tool Schema Definitions

Tool schemas follow the OpenAI function-calling JSON schema format. Each tool definition includes name, description, and parameter specifications:

```python
# Example: outlook_find_messages schema
{
    "type": "function",
    "function": {
        "name": "outlook_find_messages",
        "description": (
            "Search Outlook messages by sender email/name or keyword. "
            "Use for queries like 'emails from alice' or 'find emails about project'."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search term: sender name, email address, or keyword"
                },
                "top": {
                    "type": "integer",
                    "description": "Maximum number of results (default 10)",
                    "default": 10
                }
            },
            "required": ["query"]
        }
    }
}
```

### 9.4.1 Complete Tool Catalogue

**Email Read Tools (6):**

| Tool Name | Description |
|-----------|-------------|
| `outlook_get_emails` | Fetch latest N inbox messages |
| `outlook_get_unread_emails` | Fetch only unread messages |
| `outlook_get_flagged_emails` | Fetch flagged messages (memory scan) |
| `outlook_get_email_by_id` | Fetch full email by ID |
| `outlook_find_messages` | KQL search by sender/keyword |
| `outlook_filter_emails_by_date` | Filter by date range |

**Email Send/Draft Tools (3):**

| Tool Name | Description |
|-----------|-------------|
| `outlook_send_email` | Send new email immediately |
| `outlook_create_draft` | Save to Drafts folder, return draft_id |
| `outlook_send_draft` | Send saved draft by draft_id |

**Reply/Forward Tools (3):**

| Tool Name | Description |
|-----------|-------------|
| `outlook_reply_email` | Reply to a message |
| `outlook_reply_all` | Reply-all to a message |
| `outlook_forward_email` | Forward to another recipient |

**Organization Tools (7):**

| Tool Name | Description |
|-----------|-------------|
| `outlook_delete_email` | Permanently delete |
| `outlook_archive_email` | Move to Archive |
| `outlook_move_to_folder_name` | Move to named folder |
| `outlook_mark_as_read` | Set read flag |
| `outlook_mark_as_unread` | Clear read flag |
| `outlook_flag_email` | Set follow-up flag |
| `outlook_unflag_email` | Clear follow-up flag |
| `outlook_list_folders` | List all mailbox folders |
| `outlook_create_folder` | Create new folder |

**AI Helper Tools (2):**

| Tool Name | Description |
|-----------|-------------|
| `summarize_mailbox` | AI summary of multiple emails |
| `draft_reply` | AI-generated reply to an email |

**Calendar Tools (4):**

| Tool Name | Description |
|-----------|-------------|
| `calendar_get_upcoming_events` | Next N days of events |
| `calendar_get_today_events` | Today's schedule |
| `calendar_create_event` | Create new event |
| `calendar_search_events` | Search events by keyword |

**Natural Language Resolution (1):**

| Tool Name | Description |
|-----------|-------------|
| `resolve_email_id` | Convert "first email", "that email" → email_id |

---

## 9.5 outlook/core.py — Microsoft Graph API Client

### 9.5.1 Client Initialization

```python
class OutlookGraphClient:
    def __init__(self):
        self.client_id = os.getenv("OUTLOOK_CLIENT_ID")
        self.authority = os.getenv("OUTLOOK_AUTHORITY",
                                    "https://login.microsoftonline.com/common")
        self.scopes = os.getenv("OUTLOOK_SCOPES",
                                 "Mail.Read Mail.Send User.Read").split()
        self.graph_base = "https://graph.microsoft.com/v1.0"

        # Load persistent token cache from disk
        self._cache = msal.SerializableTokenCache()
        cache_path = os.getenv("OUTLOOK_TOKEN_CACHE", ".outlook_msal_token_cache.bin")
        if os.path.exists(cache_path):
            self._cache.deserialize(open(cache_path, "r").read())

        self._app = msal.PublicClientApplication(
            client_id=self.client_id,
            authority=self.authority,
            token_cache=self._cache,
        )
```

### 9.5.2 Token Acquisition

```python
def acquire_token(self) -> str:
    """Get access token: silent (cache) or device flow."""
    accounts = self._app.get_accounts()
    if accounts:
        result = self._app.acquire_token_silent(self.scopes, account=accounts[0])
        if result and "access_token" in result:
            self._save_cache()
            return result["access_token"]

    # Fall back to device flow
    flow = self._app.initiate_device_flow(scopes=self.scopes)
    print(f"Visit {flow['verification_uri']} and enter code: {flow['user_code']}")
    result = self._app.acquire_token_by_device_flow(flow)
    if "access_token" not in result:
        raise AuthenticationError(result.get("error_description"))
    self._save_cache()
    return result["access_token"]
```

### 9.5.3 Request Retry Logic

All Graph API calls go through `_request()` which implements exponential backoff:

```python
def _request(self, method, path, **kwargs):
    url = f"{self.graph_base}{path}"
    token = self.acquire_token()
    headers = {"Authorization": f"Bearer {token}",
               "Content-Type": "application/json"}

    for attempt in range(self.max_retries):
        resp = requests.request(method, url, headers=headers, **kwargs)

        if resp.status_code == 429:
            retry_after = int(resp.headers.get("Retry-After", 2 ** attempt))
            time.sleep(retry_after)
            continue

        if resp.status_code in (500, 502, 503, 504):
            time.sleep(2 ** attempt)
            continue

        if resp.status_code == 403:
            raise EmailPermissionError("Insufficient permissions")

        resp.raise_for_status()
        return resp.json() if resp.content else {}

    raise EmailRateLimitError("Max retries exceeded")
```

### 9.5.4 Pagination Support

```python
def _paged_messages(self, path, params=None, top=10):
    """
    Fetch emails with pagination support.
    Returns (emails, next_token, total_fetched)
    """
    all_messages = []
    url = f"{self.graph_base}{path}"
    params = params or {}
    params["$top"] = min(top, 50)  # Graph max per page = 50

    while url and len(all_messages) < top:
        resp = self._request("GET", url, params=params)
        messages = resp.get("value", [])
        all_messages.extend(messages)
        url = resp.get("@odata.nextLink")  # Next page URL
        params = {}  # nextLink already has params encoded

    next_token = None
    if url:
        # Extract $skiptoken from nextLink for cursor-based pagination
        from urllib.parse import urlparse, parse_qs
        qs = parse_qs(urlparse(url).query)
        next_token = qs.get("$skiptoken", [None])[0]

    return all_messages[:top], next_token
```

---

## 9.6 db.py — SQLite Persistence Layer

### 9.6.1 Schema

```sql
-- Sessions table: one row per conversation
CREATE TABLE IF NOT EXISTS sessions (
    id         TEXT PRIMARY KEY,           -- UUID v4
    title      TEXT NOT NULL,              -- "New Chat" or auto-titled
    created_at TEXT NOT NULL,              -- ISO 8601 UTC
    updated_at TEXT NOT NULL               -- Updated on each new message
);

-- Messages table: one row per message (user or assistant)
CREATE TABLE IF NOT EXISTS messages (
    id         TEXT PRIMARY KEY,           -- UUID v4
    session_id TEXT NOT NULL,              -- FK → sessions.id
    role       TEXT NOT NULL,              -- "user" | "assistant"
    content    TEXT NOT NULL,              -- Message text
    tool_calls TEXT,                       -- JSON array of tool call records
    created_at TEXT NOT NULL,              -- ISO 8601 UTC
    FOREIGN KEY (session_id)
        REFERENCES sessions(id)
        ON DELETE CASCADE                  -- Auto-delete messages with session
);
```

### 9.6.2 Key Functions

```python
def init_db():
    """Initialize SQLite with WAL mode for concurrent read/write."""
    conn = get_conn()
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(SCHEMA_SQL)
    conn.commit()

def add_message(session_id, role, content, tool_calls=None):
    """Insert message and update session's updated_at timestamp."""
    conn = get_conn()
    msg_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()
    conn.execute(
        "INSERT INTO messages (id, session_id, role, content, tool_calls, created_at)"
        " VALUES (?, ?, ?, ?, ?, ?)",
        (msg_id, session_id, role, content, tool_calls, now)
    )
    conn.execute(
        "UPDATE sessions SET updated_at = ? WHERE id = ?",
        (now, session_id)
    )
    conn.commit()

def get_agent_history(session_id) -> List[dict]:
    """
    Return text-only history for LLM context.
    Excludes tool_calls column (not sent to LLM; used for recovery only).
    """
    rows = get_conn().execute(
        "SELECT role, content FROM messages WHERE session_id = ?"
        " ORDER BY created_at ASC",
        (session_id,)
    ).fetchall()
    return [{"role": row[0], "content": row[1]} for row in rows]
```

### 9.6.3 Write-Ahead Logging (WAL)

SQLite's default journal mode is "rollback", which serializes all operations. The application enables WAL mode which allows:

- Multiple concurrent readers while a write is in progress.
- Much faster write throughput (important for streaming, where messages are saved mid-stream).
- Atomic commits even during server crashes.

---

# SECTION 10 — FRONTEND DOCUMENTATION

## 10.1 React Application Architecture

The frontend is a single-page application (SPA) built with React 18 and Vite. It communicates with the FastAPI backend via standard REST for CRUD operations and via the Fetch API's streaming interface for SSE events.

```
App.jsx (root, state owner)
├── AuthFlow.jsx          (if not authenticated)
└── [Authenticated Layout]
    ├── NotificationBanner.jsx   (SSE inbox alerts)
    ├── Sidebar.jsx              (session list + CRUD)
    └── ChatView.jsx             (main chat area)
        ├── MessageBubble.jsx[]  (one per message)
        │   ├── ToolCallBadge.jsx[] (tool status)
        │   └── EmailCard.jsx[]     (email previews)
        └── Input + Send Button
```

## 10.2 App.jsx — Root Component

The root component is responsible for:
- **Authentication gating**: Shows `AuthFlow` until the user is authenticated.
- **Session management**: Creates or restores the active session.
- **Layout rendering**: Renders sidebar + chat view once authenticated.
- **Theme management**: Reads/writes theme preference to `localStorage`.

```jsx
function App() {
  const [authStatus, setAuthStatus] = useState("checking"); // checking|unauth|auth
  const [activeSessionId, setActiveSessionId] = useState(null);
  const [theme, setTheme] = useState(
    () => localStorage.getItem("theme") || "dark"
  );

  // Auth check on mount
  useEffect(() => {
    fetch("/api/auth/status")
      .then(r => r.json())
      .then(data => {
        setAuthStatus(data.authenticated ? "authenticated" : "unauthenticated");
        if (data.authenticated) ensureSession();
      });
  }, []);

  // Persist theme
  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    localStorage.setItem("theme", theme);
  }, [theme]);

  if (authStatus === "checking") return <LoadingScreen />;
  if (authStatus === "unauthenticated") return <AuthFlow onAuth={checkAuth} />;

  return (
    <div className={`app-layout theme-${theme}`}>
      <NotificationBanner />
      <Sidebar
        activeId={activeSessionId}
        onSelect={setActiveSessionId}
        onNew={handleNewChat}
      />
      <ChatView sessionId={activeSessionId} />
    </div>
  );
}
```

## 10.3 AuthFlow.jsx — Device Code Authentication UI

The authentication component handles the Microsoft device flow. Instead of a redirect-based OAuth flow (which requires a web server on a specific port), device flow lets users authenticate on any device by visiting a URL and entering a short code.

```
User loads app
      │
      ▼
POST /api/auth/start
      │
      ▼
Display to user:
  ┌─────────────────────────────────────────────────────────┐
  │  To sign in, visit:  https://microsoft.com/devicelogin  │
  │  Enter code:  ABCD-1234                                  │
  │                                                          │
  │  This code expires in 15 minutes.                        │
  │  [Copy Code]                                             │
  └─────────────────────────────────────────────────────────┘
      │
      ▼ (Poll GET /api/auth/poll every 3 seconds)
      │
      ▼ (When backend signals "authenticated")
App re-renders with ChatView
```

```jsx
function AuthFlow({ onAuth }) {
  const [deviceCode, setDeviceCode] = useState(null);
  const [verificationUri, setVerificationUri] = useState(null);
  const [status, setStatus] = useState("idle"); // idle|starting|waiting|error

  async function startAuth() {
    setStatus("starting");
    const resp = await fetch("/api/auth/start", { method: "POST" });
    const data = await resp.json();
    setDeviceCode(data.user_code);
    setVerificationUri(data.verification_uri);
    setStatus("waiting");
    pollStatus();
  }

  function pollStatus() {
    const interval = setInterval(async () => {
      const resp = await fetch("/api/auth/poll");
      const data = await resp.json();
      if (data.status === "authenticated") {
        clearInterval(interval);
        onAuth();
      } else if (data.status === "error") {
        clearInterval(interval);
        setStatus("error");
      }
    }, 3000);
  }

  return (
    <div className="auth-container">
      <h1>Outlook Assistant</h1>
      {status === "idle" && (
        <button onClick={startAuth}>Connect Microsoft Account</button>
      )}
      {status === "waiting" && (
        <div className="device-code-box">
          <p>Visit: <strong>{verificationUri}</strong></p>
          <p>Enter code: <strong className="code">{deviceCode}</strong></p>
          <Spinner /> Waiting for authentication...
        </div>
      )}
    </div>
  );
}
```

## 10.4 ChatView.jsx — Main Chat Interface

`ChatView` is the most complex frontend component, managing the SSE streaming connection, local message state, and all user interactions.

### 10.4.1 State Structure

```jsx
const [messages, setMessages] = useState([]);
// Each message:
// {
//   id: uuid,
//   role: "user" | "assistant",
//   content: string,
//   toolCalls: [{id, name, args, result, status}],
//   streaming: boolean,    // Is this message still receiving tokens?
//   stopped: boolean,      // Did the user abort this message?
// }

const [input, setInput] = useState("");
const [isStreaming, setIsStreaming] = useState(false);
const abortControllerRef = useRef(null);
const messagesEndRef = useRef(null);  // For auto-scroll
```

### 10.4.2 Sending a Message and Consuming SSE

```jsx
async function sendMessage() {
  if (!input.trim() || isStreaming) return;

  const userMsg = { id: uuidv4(), role: "user", content: input };
  const assistantMsg = {
    id: uuidv4(), role: "assistant", content: "",
    toolCalls: [], streaming: true, stopped: false
  };

  setMessages(prev => [...prev, userMsg, assistantMsg]);
  setInput("");
  setIsStreaming(true);

  const controller = new AbortController();
  abortControllerRef.current = controller;

  const response = await fetch("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId, message: input }),
    signal: controller.signal,
  });

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let finalContent = "";
  let finalToolCalls = [];

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    const text = decoder.decode(value);
    const lines = text.split("\n").filter(l => l.startsWith("data: "));

    for (const line of lines) {
      const event = JSON.parse(line.slice(6));  // strip "data: "

      if (event.type === "text_delta") {
        finalContent += event.content;
        // Update message content in place
        setMessages(prev => prev.map(m =>
          m.id === assistantMsg.id
            ? { ...m, content: finalContent }
            : m
        ));
      }

      if (event.type === "tool_start") {
        finalToolCalls.push({
          id: event.id, name: event.name,
          args: event.args, status: "running"
        });
        setMessages(prev => prev.map(m =>
          m.id === assistantMsg.id
            ? { ...m, toolCalls: [...finalToolCalls] }
            : m
        ));
      }

      if (event.type === "tool_end") {
        finalToolCalls = finalToolCalls.map(tc =>
          tc.name === event.name
            ? { ...tc, result: event.result, status: "done" }
            : tc
        );
        setMessages(prev => prev.map(m =>
          m.id === assistantMsg.id
            ? { ...m, toolCalls: [...finalToolCalls] }
            : m
        ));
      }

      if (event.type === "done") {
        setMessages(prev => prev.map(m =>
          m.id === assistantMsg.id
            ? { ...m, streaming: false }
            : m
        ));
        setIsStreaming(false);
      }
    }
  }
}
```

### 10.4.3 Stop Generation

```jsx
function stopGeneration() {
  if (abortControllerRef.current) {
    abortControllerRef.current.abort();
    setIsStreaming(false);
    setMessages(prev => prev.map((m, idx) =>
      idx === prev.length - 1 && m.role === "assistant"
        ? { ...m, streaming: false, stopped: true }
        : m
    ));
  }
}
```

## 10.5 MessageBubble.jsx — Message Rendering

### 10.5.1 Markdown Parser

The assistant messages are rendered with a custom lightweight Markdown parser (no external library, keeping bundle size small):

```jsx
function renderMarkdown(text) {
  return text
    // Code blocks
    .replace(/```(\w+)?\n([\s\S]*?)```/g,
      '<pre><code class="language-$1">$2</code></pre>')
    // Inline code
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    // Bold
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    // Italic
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    // Headers
    .replace(/^### (.+)$/gm, '<h3>$1</h3>')
    .replace(/^## (.+)$/gm,  '<h2>$1</h2>')
    .replace(/^# (.+)$/gm,   '<h1>$1</h1>')
    // Unordered lists
    .replace(/^- (.+)$/gm, '<li>$1</li>')
    // Paragraph breaks
    .replace(/\n\n/g, '</p><p>')
    .replace(/^(.+)/, '<p>$1')
    .replace(/(.+)$/, '$1</p>');
}
```

### 10.5.2 Email Card Extraction

Before rendering markdown, `MessageBubble` scans tool call results for email objects and renders them as `EmailCard` components:

```jsx
function extractEmailsFromToolCalls(toolCalls) {
  const emails = [];
  for (const tc of toolCalls || []) {
    const result = tc.result;
    if (!result?.success) continue;
    const data = result.data;

    if (Array.isArray(data)) {
      // Array of emails
      emails.push(...data.filter(isEmailObject));
    } else if (data?.emails) {
      // {emails: [...]}
      emails.push(...data.emails.filter(isEmailObject));
    } else if (isEmailObject(data)) {
      // Single email
      emails.push(data);
    }
  }
  return emails;
}

function isEmailObject(obj) {
  return obj && typeof obj === "object" && obj.subject && obj.id;
}
```

## 10.6 Sidebar.jsx — Session Management

```jsx
function Sidebar({ activeId, onSelect, onNew }) {
  const [sessions, setSessions] = useState([]);
  const [editId, setEditId] = useState(null);
  const [editTitle, setEditTitle] = useState("");

  // Load and auto-refresh sessions
  useEffect(() => {
    loadSessions();
    const timer = setInterval(loadSessions, 10_000);
    return () => clearInterval(timer);
  }, []);

  async function loadSessions() {
    const resp = await fetch("/api/sessions");
    setSessions(await resp.json());
  }

  async function renameSession(id, title) {
    await fetch(`/api/sessions/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title }),
    });
    setEditId(null);
    loadSessions();
  }

  async function deleteSession(id) {
    await fetch(`/api/sessions/${id}`, { method: "DELETE" });
    if (id === activeId) onNew();
    loadSessions();
  }

  return (
    <aside className={`sidebar ${collapsed ? "collapsed" : ""}`}>
      <button onClick={onNew} className="new-chat-btn">+ New Chat</button>
      {sessions.map(session => (
        <div key={session.id}
          className={`session-item ${session.id === activeId ? "active" : ""}`}
          onClick={() => onSelect(session.id)}>
          {editId === session.id
            ? <input value={editTitle}
                onChange={e => setEditTitle(e.target.value)}
                onBlur={() => renameSession(session.id, editTitle)} />
            : <span>{session.title}</span>
          }
          <div className="session-actions">
            <button onClick={() => { setEditId(session.id); setEditTitle(session.title); }}>
              ✏️
            </button>
            <button onClick={() => deleteSession(session.id)}>🗑️</button>
          </div>
        </div>
      ))}
    </aside>
  );
}
```

## 10.7 EmailCard.jsx — Inline Email Actions

`EmailCard` renders a rich email preview with action buttons, enabling users to perform email operations without leaving the chat interface:

```jsx
function EmailCard({ email }) {
  const [isRead, setIsRead] = useState(email.isRead ?? true);
  const [isFlagged, setIsFlagged] = useState(
    email.flag?.flagStatus === "flagged"
  );
  const [busy, setBusy] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);

  async function doAction(action) {
    setBusy(true);
    try {
      await fetch("/api/email/action", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email_id: email.id, action }),
      });
      // Update local state optimistically
      if (action === "mark_read") setIsRead(true);
      if (action === "mark_unread") setIsRead(false);
      if (action === "flag") setIsFlagged(true);
      if (action === "unflag") setIsFlagged(false);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className={`email-card ${!isRead ? "unread" : ""}`}>
      <div className="email-header">
        <span className="sender">{email.from?.emailAddress?.name}</span>
        <span className="date">{formatDate(email.receivedDateTime)}</span>
      </div>
      <div className="email-subject">{email.subject}</div>
      <div className="email-preview">{email.bodyPreview?.slice(0, 160)}</div>
      <div className="email-actions">
        <button onClick={() => doAction(isRead ? "mark_unread" : "mark_read")}
                title={isRead ? "Mark Unread" : "Mark Read"}>
          {isRead ? "📭" : "📬"}
        </button>
        <button onClick={() => doAction(isFlagged ? "unflag" : "flag")}
                title={isFlagged ? "Unflag" : "Flag"}>
          {isFlagged ? "🚩" : "⬜"}
        </button>
        <button onClick={() => doAction("archive")} title="Archive">📦</button>
        <button onClick={() => confirmDelete
          ? doAction("delete")
          : setConfirmDelete(true)}
          title={confirmDelete ? "Confirm Delete" : "Delete"}>
          {confirmDelete ? "⚠️ Confirm" : "🗑️"}
        </button>
      </div>
    </div>
  );
}
```

## 10.8 ToolCallBadge.jsx — Tool Status Indicators

```jsx
const TOOL_ICONS = {
  outlook_get_emails:         "📬",
  outlook_get_unread_emails:  "📩",
  outlook_find_messages:      "🔍",
  outlook_send_email:         "📤",
  outlook_create_draft:       "📝",
  outlook_reply_email:        "↩️",
  outlook_archive_email:      "📦",
  outlook_delete_email:       "🗑️",
  outlook_flag_email:         "🚩",
  summarize_mailbox:          "✨",
  draft_reply:                "✍️",
  calendar_get_today_events:  "📅",
  resolve_email_id:           "🔎",
};

function ToolCallBadge({ tool }) {
  const icon = TOOL_ICONS[tool.name] || "⚙️";
  const label = tool.name.replace(/_/g, " ").replace("outlook ", "");

  return (
    <div className={`tool-badge status-${tool.status}`}>
      <span className="tool-icon">{icon}</span>
      <span className="tool-label">{label}</span>
      {tool.status === "running" && <span className="spinner" />}
      {tool.status === "done" && !tool.result?.error && <span>✓</span>}
      {tool.status === "done" && tool.result?.error  && <span>✗</span>}
    </div>
  );
}
```

---

*End of Part 1 — Sections 1–10*
