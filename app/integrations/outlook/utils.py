from __future__ import annotations

import json
import logging
import os
import re
import time
from dataclasses import dataclass, field
from functools import wraps
from threading import RLock
from typing import Any, Callable, Dict, Iterable, Optional, Tuple, TypeVar


EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
LOGGER = logging.getLogger("outlook_mcp")


# ==============================
# Errors
# ==============================


class OutlookError(RuntimeError):
    """Base error for the Outlook MCP integration."""


class EmailNotFoundError(OutlookError):
    pass


class EmailAmbiguityError(OutlookError):
    pass


class EmailPermissionError(OutlookError):
    pass


class EmailRateLimitError(OutlookError):
    pass


class EmailValidationError(OutlookError):
    pass


class EmailSafetyError(OutlookError):
    pass


# ==============================
# Tool response helpers
# ==============================


def ok(data: Any = None) -> Dict[str, Any]:
    return {"success": True, "data": data, "error": None}


def err(message: str, *, data: Any = None) -> Dict[str, Any]:
    return {"success": False, "data": data, "error": message}


T = TypeVar("T")


def tool_wrapper(fn: Callable[..., T]) -> Callable[..., Dict[str, Any]]:
    """
    Wrap tool functions to ensure the required output format:
    {"success": True/False, "data": ..., "error": ...}
    """

    @wraps(fn)
    def _wrapped(*args: Any, **kwargs: Any) -> Dict[str, Any]:
        try:
            return ok(fn(*args, **kwargs))
        except OutlookError as e:
            return err(str(e))
        except Exception as e:  # noqa: BLE001
            LOGGER.exception("Unhandled tool error in %s", getattr(fn, "__name__", "tool"))
            return err(f"Unhandled error: {e}")

    return _wrapped


# ==============================
# Safety
# ==============================


def validate_email_address(address: str) -> str:
    address = (address or "").strip()
    if not address or not EMAIL_RE.match(address):
        raise EmailValidationError(f"Invalid email address: {address!r}")
    return address


def check_send_safety(*, to: Iterable[str], subject: str, body: str) -> None:
    to_list = [validate_email_address(a) for a in to]
    if not to_list:
        raise EmailSafetyError("No recipients provided.")
    if not (subject or "").strip():
        raise EmailSafetyError("Empty subject is not allowed.")
    if not (body or "").strip():
        raise EmailSafetyError("Empty body is not allowed.")


def check_batch_safety(
    count: int,
    *,
    max_without_explicit_ok: int = 10,
    allow_bulk: bool = False,
) -> None:
    if count <= max_without_explicit_ok:
        return
    if allow_bulk:
        return
    raise EmailSafetyError(
        f"Refusing bulk operation on {count} items. "
        f"Pass allow_bulk=True to override (use with caution)."
    )


def chunked(items: Iterable[str], size: int) -> Iterable[list[str]]:
    batch: list[str] = []
    for item in items:
        batch.append(item)
        if len(batch) >= size:
            yield batch
            batch = []
    if batch:
        yield batch


# ==============================
# Env / misc
# ==============================


def env(name: str, default: Optional[str] = None) -> Optional[str]:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    return value.strip()


def now_ms() -> int:
    return int(time.time() * 1000)


def json_dumps_compact(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))


@dataclass(frozen=True)
class RetryConfig:
    max_attempts: int = 4
    base_sleep_s: float = 0.5
    max_sleep_s: float = 8.0


def backoff_sleep(attempt: int, cfg: RetryConfig) -> None:
    sleep_s = min(cfg.max_sleep_s, cfg.base_sleep_s * (2 ** (attempt - 1)))
    time.sleep(sleep_s)


def pick_first(d: Dict[str, Any], *keys: str) -> Optional[Any]:
    for k in keys:
        if k in d and d[k] is not None:
            return d[k]
    return None


def to_graph_query_params(params: Dict[str, Any]) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for k, v in params.items():
        if v is None:
            continue
        if isinstance(v, bool):
            out[k] = "true" if v else "false"
        else:
            out[k] = str(v)
    return out


# ==============================
# TTL cache + stats
# ==============================


@dataclass
class CacheEntry:
    value: Any
    expires_at_ms: int


class TTLCache:
    def __init__(self, *, default_ttl_s: int = 60) -> None:
        self._default_ttl_s = int(default_ttl_s)
        self._data: Dict[str, CacheEntry] = {}
        self._lock = RLock()

    def get(self, key: str) -> Optional[Any]:
        with self._lock:
            entry = self._data.get(key)
            if not entry:
                return None
            if entry.expires_at_ms <= now_ms():
                self._data.pop(key, None)
                return None
            return entry.value

    def set(self, key: str, value: Any, *, ttl_s: Optional[int] = None) -> None:
        ttl = self._default_ttl_s if ttl_s is None else int(ttl_s)
        with self._lock:
            self._data[key] = CacheEntry(value=value, expires_at_ms=now_ms() + ttl * 1000)

    def clear(self) -> None:
        with self._lock:
            self._data.clear()


@dataclass
class ToolStats:
    calls: int = 0
    errors: int = 0
    last_error: Optional[str] = None
    last_call_ms: Optional[int] = None


class StatsTracker:
    def __init__(self) -> None:
        self._lock = RLock()
        self._stats: Dict[str, ToolStats] = {}

    def record(self, name: str, *, ok_call: bool, error: Optional[str] = None) -> None:
        with self._lock:
            s = self._stats.setdefault(name, ToolStats())
            s.calls += 1
            s.last_call_ms = now_ms()
            if not ok_call:
                s.errors += 1
                s.last_error = error

    def snapshot(self) -> Dict[str, Dict[str, Any]]:
        with self._lock:
            return {k: vars(v).copy() for k, v in self._stats.items()}


GLOBAL_STATS = StatsTracker()


def log_tool_call(name: str) -> Callable[[Callable[..., T]], Callable[..., T]]:
    def _decorator(fn: Callable[..., T]) -> Callable[..., T]:
        @wraps(fn)
        def _wrapped(*args: Any, **kwargs: Any) -> T:
            start = now_ms()
            try:
                out = fn(*args, **kwargs)
                dur = now_ms() - start
                LOGGER.info("tool=%s ok duration_ms=%s", name, dur)
                GLOBAL_STATS.record(name, ok_call=True)
                return out
            except Exception as e:  # noqa: BLE001
                dur = now_ms() - start
                LOGGER.warning("tool=%s err duration_ms=%s error=%s", name, dur, e)
                GLOBAL_STATS.record(name, ok_call=False, error=str(e))
                raise

        return _wrapped

    return _decorator


# ==============================
# Context store (for NL references)
# ==============================


@dataclass
class OutlookContext:
    last_email_list: list[Dict[str, Any]] = field(default_factory=list)
    last_viewed_ids: list[str] = field(default_factory=list)
    recent_entities: Dict[str, Any] = field(default_factory=dict)


class ContextStore:
    def __init__(self) -> None:
        self._lock = RLock()
        self._ctx = OutlookContext()

    def get(self) -> OutlookContext:
        with self._lock:
            return OutlookContext(
                last_email_list=list(self._ctx.last_email_list),
                last_viewed_ids=list(self._ctx.last_viewed_ids),
                recent_entities=dict(self._ctx.recent_entities),
            )

    def set_last_email_list(self, emails: list[Dict[str, Any]]) -> None:
        with self._lock:
            self._ctx.last_email_list = list(emails)

    def push_viewed_id(self, email_id: str) -> None:
        with self._lock:
            self._ctx.last_viewed_ids = ([email_id] + [i for i in self._ctx.last_viewed_ids if i != email_id])[:50]

    def set_entity(self, key: str, value: Any) -> None:
        with self._lock:
            self._ctx.recent_entities[key] = value


GLOBAL_CONTEXT = ContextStore()
