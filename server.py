"""
FastAPI backend for the Outlook MCP Chat web app.

Endpoints:
  GET  /api/health          health check
  GET  /api/auth/status     check if authenticated
  POST /api/auth/start      begin MSAL device-code flow
  GET  /api/auth/poll       poll for auth completion
  POST /api/chat            SSE streaming chat with the agent
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import threading
from typing import Any, Dict, List, Optional

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("outlook_server")

app = FastAPI(title="Outlook MCP Chat", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Outlook Graph client (singleton) ─────────────────────────────────────────

_graph_client = None
_graph_lock = threading.Lock()


def _get_graph_client():
    global _graph_client
    with _graph_lock:
        if _graph_client is None:
            from app.integrations.outlook.core import OutlookAuthConfig, OutlookGraphClient
            client_id = os.getenv("OUTLOOK_CLIENT_ID", "").strip()
            if not client_id:
                raise RuntimeError("OUTLOOK_CLIENT_ID is not set. Check your .env file.")
            auth = OutlookAuthConfig(
                client_id=client_id,
                authority=os.getenv("OUTLOOK_AUTHORITY", "https://login.microsoftonline.com/common"),
                scopes=(os.getenv("OUTLOOK_SCOPES") or "Mail.Read Mail.Send User.Read").split(),
                token_cache_path=os.getenv("OUTLOOK_TOKEN_CACHE", ".outlook_msal_token_cache.bin"),
                sender_email=os.getenv("OUTLOOK_SENDER_EMAIL") or None,
            )
            _graph_client = OutlookGraphClient(auth)
    return _graph_client


# ── Auth state ────────────────────────────────────────────────────────────────

_auth_lock = threading.Lock()
_auth_state: Dict[str, Any] = {
    "status": "idle",   # idle | pending | completed | error
    "error": None,
}


def _is_authenticated() -> bool:
    """Return True if a cached token is available."""
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


# ── Routes: health & auth ─────────────────────────────────────────────────────

@app.get("/api/health")
def health():
    return {"status": "ok"}


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
        raise HTTPException(status_code=500, detail=f"Failed to start device flow: {flow}")

    with _auth_lock:
        _auth_state["status"] = "pending"
        _auth_state["error"] = None

    def _bg_poll() -> None:
        try:
            result = client._app.acquire_token_by_device_flow(flow)
            if result and "access_token" in result:
                client._save_cache()
                with _auth_lock:
                    _auth_state["status"] = "completed"
            else:
                with _auth_lock:
                    _auth_state["status"] = "error"
                    _auth_state["error"] = str(
                        result.get("error_description", result) if result else "Unknown error"
                    )
        except Exception as e:  # noqa: BLE001
            with _auth_lock:
                _auth_state["status"] = "error"
                _auth_state["error"] = str(e)

    threading.Thread(target=_bg_poll, daemon=True).start()

    return {
        "user_code": flow["user_code"],
        "verification_uri": flow.get("verification_uri", "https://microsoft.com/devicelogin"),
        "expires_in": flow.get("expires_in", 900),
        "message": flow.get("message", ""),
    }


@app.get("/api/auth/poll")
def auth_poll():
    with _auth_lock:
        return {
            "status": _auth_state["status"],
            "error": _auth_state.get("error"),
        }


# ── Route: chat (SSE streaming) ───────────────────────────────────────────────

class HistoryMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    history: List[HistoryMessage] = []
    message: str


@app.post("/api/chat")
async def chat(request: ChatRequest):
    if not _is_authenticated():
        async def _not_auth():
            yield f"data: {json.dumps({'type': 'error', 'message': 'Not signed in. Please authenticate first.'})}\n\n"
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
        return StreamingResponse(_not_auth(), media_type="text/event-stream")

    history = [{"role": m.role, "content": m.content} for m in request.history]

    async def _generate():
        from agent.loop import run_agent_stream

        q: asyncio.Queue = asyncio.Queue()
        loop = asyncio.get_event_loop()

        def _worker():
            try:
                for event in run_agent_stream(history, request.message):
                    loop.call_soon_threadsafe(q.put_nowait, event)
                loop.call_soon_threadsafe(q.put_nowait, None)  # sentinel
            except Exception as e:  # noqa: BLE001
                loop.call_soon_threadsafe(q.put_nowait, {"type": "error", "message": str(e)})
                loop.call_soon_threadsafe(q.put_nowait, None)

        threading.Thread(target=_worker, daemon=True).start()

        while True:
            event = await q.get()
            if event is None:
                yield f"data: {json.dumps({'type': 'done'})}\n\n"
                break
            yield f"data: {json.dumps(event, default=str, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        _generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


# ── Serve built React app ─────────────────────────────────────────────────────

_dist = os.path.join(os.path.dirname(__file__), "web", "dist")
if os.path.isdir(_dist):
    app.mount("/", StaticFiles(directory=_dist, html=True), name="static")


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)
