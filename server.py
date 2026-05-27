"""
FastAPI backend for Outlook MCP Chat — production edition.

Endpoints:
  GET  /api/health
  GET  /api/auth/status
  POST /api/auth/start
  GET  /api/auth/poll

  GET  /api/sessions              list sessions
  POST /api/sessions              create session
  GET  /api/sessions/{id}         get session + messages
  PATCH /api/sessions/{id}        rename session
  DELETE /api/sessions/{id}       delete session

  POST /api/chat                  SSE streaming agent chat
  POST /api/email/action          direct email action (archive/flag/etc.)
  GET  /api/notifications/stream  SSE new-email notifications
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import threading
import time
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import db
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("outlook_server")

app = FastAPI(title="Outlook MCP Chat", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

db.init_db()

# ── Graph client singleton ─────────────────────────────────────────────────────

_graph_client = None
_graph_lock = threading.Lock()


def _get_graph_client():
    global _graph_client
    with _graph_lock:
        if _graph_client is None:
            from app.integrations.outlook.core import OutlookAuthConfig, OutlookGraphClient
            client_id = os.getenv("OUTLOOK_CLIENT_ID", "").strip()
            if not client_id:
                raise RuntimeError("OUTLOOK_CLIENT_ID not set in .env")
            auth = OutlookAuthConfig(
                client_id=client_id,
                authority=os.getenv("OUTLOOK_AUTHORITY", "https://login.microsoftonline.com/common"),
                scopes=(os.getenv("OUTLOOK_SCOPES") or "Mail.Read Mail.Send User.Read Calendars.ReadWrite").split(),
                token_cache_path=os.getenv("OUTLOOK_TOKEN_CACHE", ".outlook_msal_token_cache.bin"),
                sender_email=os.getenv("OUTLOOK_SENDER_EMAIL") or None,
            )
            _graph_client = OutlookGraphClient(auth)
    return _graph_client


# ── Auth ───────────────────────────────────────────────────────────────────────

_auth_lock = threading.Lock()
_auth_state: Dict[str, Any] = {"status": "idle", "error": None}


def _is_authenticated() -> bool:
    try:
        client = _get_graph_client()
    except RuntimeError:
        return False
    accounts = client._app.get_accounts()
    if accounts:
        result = client._app.acquire_token_silent(client._auth.scopes, account=accounts[0])
        if result and "access_token" in result:
            return True
    with _auth_lock:
        return _auth_state["status"] == "completed"


def _clear_auth_state() -> None:
    global _graph_client
    # Reset MSAL cache (in-memory + file) and drop the singleton client so
    # the next request forces a fresh device-code flow.
    with _graph_lock:
        client = _graph_client
        _graph_client = None

    if client is not None:
        try:
            client._app.token_cache.clear()
        except Exception:
            pass
        try:
            client._save_cache()
        except Exception:
            pass

        try:
            cache_path = (client._auth.token_cache_path or "").strip()
            if cache_path:
                Path(cache_path).expanduser().unlink(missing_ok=True)
        except Exception:
            pass

    with _auth_lock:
        _auth_state["status"] = "idle"
        _auth_state["error"] = None


@app.get("/api/health")
def health():
    return {"status": "ok", "version": "2.0.0"}


@app.get("/api/auth/status")
def auth_status():
    authenticated = _is_authenticated()
    with _auth_lock:
        pending = _auth_state["status"] == "pending"
    return {"authenticated": authenticated, "pending": pending}


@app.post("/api/auth/start")
def auth_start():
    if _is_authenticated():
        return {"already_authenticated": True}
    try:
        client = _get_graph_client()
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))

    flow = client._app.initiate_device_flow(scopes=client._auth.scopes)
    if "user_code" not in flow:
        raise HTTPException(status_code=500, detail=f"Device flow failed: {flow}")

    with _auth_lock:
        _auth_state["status"] = "pending"
        _auth_state["error"] = None

    def _bg():
        try:
            result = client._app.acquire_token_by_device_flow(flow)
            if result and "access_token" in result:
                client._save_cache()
                with _auth_lock:
                    _auth_state["status"] = "completed"
            else:
                with _auth_lock:
                    _auth_state["status"] = "error"
                    _auth_state["error"] = str(result.get("error_description", result) if result else "Unknown")
        except Exception as e:
            with _auth_lock:
                _auth_state["status"] = "error"
                _auth_state["error"] = str(e)

    threading.Thread(target=_bg, daemon=True).start()
    return {
        "user_code": flow["user_code"],
        "verification_uri": flow.get("verification_uri", "https://microsoft.com/devicelogin"),
        "expires_in": flow.get("expires_in", 900),
        "message": flow.get("message", ""),
    }


@app.post("/api/auth/logout")
def auth_logout():
    _clear_auth_state()
    return {"ok": True}


@app.get("/api/auth/poll")
def auth_poll():
    with _auth_lock:
        return {"status": _auth_state["status"], "error": _auth_state.get("error")}


# ── Sessions ───────────────────────────────────────────────────────────────────

class CreateSessionBody(BaseModel):
    title: str = "New Chat"


class RenameSessionBody(BaseModel):
    title: str


@app.get("/api/sessions")
def list_sessions():
    return db.list_sessions()


@app.post("/api/sessions")
def create_session(body: CreateSessionBody = CreateSessionBody()):
    return db.create_session(body.title)


@app.get("/api/sessions/{sid}")
def get_session(sid: str):
    session = db.get_session(sid)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    messages = db.get_messages(sid)
    return {**session, "messages": messages}


@app.patch("/api/sessions/{sid}")
def rename_session(sid: str, body: RenameSessionBody):
    if not db.get_session(sid):
        raise HTTPException(status_code=404, detail="Session not found")
    db.update_session_title(sid, body.title)
    return {"ok": True}


@app.delete("/api/sessions/{sid}")
def delete_session(sid: str):
    db.delete_session(sid)
    return {"ok": True}


# ── Chat ───────────────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    session_id: str
    message: str


@app.post("/api/chat")
async def chat(request: ChatRequest, req: Request):
    if not _is_authenticated():
        async def _unauth():
            yield f"data: {json.dumps({'type': 'error', 'message': 'Not signed in.'})}\n\n"
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
        return StreamingResponse(_unauth(), media_type="text/event-stream")

    session = db.get_session(request.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Auto-title from first user message
    if session["title"] == "New Chat":
        title = request.message[:60].strip()
        db.update_session_title(request.session_id, title)

    # Save user message immediately
    db.add_message(request.session_id, "user", request.message)

    # Load history (exclude the message we just added)
    history = db.get_agent_history(request.session_id)
    if history and history[-1]["role"] == "user":
        history = history[:-1]

    async def _generate():
        from agent.loop import run_agent_stream

        q: asyncio.Queue = asyncio.Queue()
        loop = asyncio.get_event_loop()
        full_content: List[str] = []
        full_tool_calls: List[Any] = []
        assistant_saved = False

        def _worker():
            try:
                for event in run_agent_stream(history, request.message, session_id=request.session_id):
                    if event["type"] == "text_delta":
                        full_content.append(event["content"])
                    elif event["type"] in ("tool_start", "tool_end"):
                        full_tool_calls.append(event)
                    loop.call_soon_threadsafe(q.put_nowait, event)
                loop.call_soon_threadsafe(q.put_nowait, None)
            except Exception as e:
                loop.call_soon_threadsafe(q.put_nowait, {"type": "error", "message": str(e)})
                loop.call_soon_threadsafe(q.put_nowait, None)

        threading.Thread(target=_worker, daemon=True).start()

        poll_s = 0.25
        while True:
            try:
                event = await asyncio.wait_for(q.get(), timeout=poll_s)
            except asyncio.TimeoutError:
                if await req.is_disconnected():
                    content = "".join(full_content)
                    if (content.strip() or full_tool_calls) and not assistant_saved:
                        db.add_message(
                            request.session_id,
                            "assistant",
                            content,
                            tool_calls=full_tool_calls or None,
                        )
                        assistant_saved = True
                        logger.info(
                            "chat client disconnected mid-stream; saved partial assistant message session=%s",
                            request.session_id[:8],
                        )
                    return
                continue

            if event is None:
                if not assistant_saved:
                    content = "".join(full_content)
                    db.add_message(request.session_id, "assistant", content, tool_calls=full_tool_calls or None)
                    assistant_saved = True
                yield f"data: {json.dumps({'type': 'done'})}\n\n"
                break
            yield f"data: {json.dumps(event, default=str, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        _generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"},
    )


# ── Email direct actions ───────────────────────────────────────────────────────

class EmailActionRequest(BaseModel):
    email_id: str
    action: str          # archive | flag | unflag | mark_read | mark_unread | delete
    params: Dict[str, Any] = {}


@app.post("/api/email/action")
def email_action(body: EmailActionRequest):
    if not _is_authenticated():
        raise HTTPException(status_code=401, detail="Not authenticated")

    _ACTION_TOOL_MAP = {
        "archive":      "outlook_archive_email",
        "flag":         "outlook_flag_email",
        "unflag":       "outlook_unflag_email",
        "mark_read":    "outlook_mark_as_read",
        "mark_unread":  "outlook_mark_as_unread",
        "delete":       "outlook_delete_email",
    }

    if body.action not in _ACTION_TOOL_MAP:
        raise HTTPException(status_code=400, detail=f"Unknown action: {body.action!r}")

    try:
        from agent.loop import _get_tools
        tools = _get_tools()
        tool_name = _ACTION_TOOL_MAP[body.action]
        fn = tools.get(tool_name)
        if fn is None:
            raise HTTPException(status_code=500, detail=f"Tool {tool_name!r} not found in registry")
        result = fn(email_id=body.email_id)
        return {"success": True, "data": result}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("email_action failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


# ── Notifications (SSE) ────────────────────────────────────────────────────────

_notif_subscribers: List[asyncio.Queue] = []
_notif_lock = threading.Lock()
_main_loop: Optional[asyncio.AbstractEventLoop] = None


def _broadcast(event: Dict[str, Any]) -> None:
    if _main_loop is None:
        return
    with _notif_lock:
        subs = list(_notif_subscribers)
    for q in subs:
        try:
            _main_loop.call_soon_threadsafe(q.put_nowait, event)
        except Exception:
            pass


def _inbox_poller() -> None:
    last_check = datetime.now(timezone.utc) - timedelta(minutes=1)
    while True:
        time.sleep(30)
        try:
            if not _is_authenticated():
                continue
            client = _get_graph_client()
            filter_str = f"receivedDateTime gt {last_check.strftime('%Y-%m-%dT%H:%M:%SZ')}"
            data = client._request(
                "GET",
                "/me/messages",
                params={
                    "$top": 10,
                    "$select": "id,subject,from,receivedDateTime,isRead,importance",
                    "$filter": filter_str,
                    "$orderby": "receivedDateTime desc",
                },
            )
            emails = data.get("value", [])
            if emails:
                _broadcast({"type": "new_emails", "count": len(emails), "emails": emails})
            last_check = datetime.now(timezone.utc)
        except Exception as e:
            logger.debug("Inbox poller: %s", e)


@app.on_event("startup")
async def startup():
    global _main_loop
    _main_loop = asyncio.get_event_loop()
    threading.Thread(target=_inbox_poller, daemon=True, name="inbox-poller").start()
    logger.info("Inbox poller started.")


@app.get("/api/notifications/stream")
async def notifications_stream():
    q: asyncio.Queue = asyncio.Queue()
    with _notif_lock:
        _notif_subscribers.append(q)

    async def _gen():
        try:
            yield f"data: {json.dumps({'type': 'connected'})}\n\n"
            while True:
                try:
                    event = await asyncio.wait_for(q.get(), timeout=25.0)
                    yield f"data: {json.dumps(event, default=str)}\n\n"
                except asyncio.TimeoutError:
                    yield f"data: {json.dumps({'type': 'heartbeat'})}\n\n"
        finally:
            with _notif_lock:
                try:
                    _notif_subscribers.remove(q)
                except ValueError:
                    pass

    return StreamingResponse(
        _gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ── Serve built React app ──────────────────────────────────────────────────────

_dist = os.path.join(os.path.dirname(__file__), "web", "dist")
if os.path.isdir(_dist):
    app.mount("/", StaticFiles(directory=_dist, html=True), name="static")


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8080"))
    uvicorn.run("server:app", host="0.0.0.0", port=port, reload=True)
