#!/usr/bin/env python3
"""Small in-process rate limiting helpers for local web routes."""
from __future__ import annotations

import logging
import threading
import time
from collections import defaultdict, deque
from functools import wraps
from typing import Callable, Deque, Dict, Tuple

from flask import jsonify, request

RATE_LIMIT_BUCKETS: Dict[Tuple[str, str], Deque[float]] = defaultdict(deque)
RATE_LIMIT_LOCK = threading.RLock()
logger = logging.getLogger(__name__)


def rate_limit_key(scope: str) -> Tuple[str, str]:
    identity = request.headers.get("X-Forwarded-For", request.remote_addr or "local").split(",")[0].strip()
    return scope, identity or "local"


def check_rate_limit(scope: str, *, limit: int = 30, window_seconds: float = 60.0) -> Tuple[bool, int, float]:
    now = time.monotonic()
    key = rate_limit_key(scope)
    with RATE_LIMIT_LOCK:
        bucket = RATE_LIMIT_BUCKETS[key]
        while bucket and now - bucket[0] > window_seconds:
            bucket.popleft()
        remaining = max(0, limit - len(bucket))
        if remaining <= 0:
            retry_after = max(0.0, window_seconds - (now - bucket[0])) if bucket else window_seconds
            return False, 0, retry_after
        bucket.append(now)
        return True, remaining - 1, 0.0


def reset_rate_limits() -> None:
    with RATE_LIMIT_LOCK:
        RATE_LIMIT_BUCKETS.clear()


def route_rate_limited(scope: str, *, limit: int = 30, window_seconds: float = 60.0) -> Callable:
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            if request.method in {"GET", "HEAD", "OPTIONS"}:
                return func(*args, **kwargs)
            ok, remaining, retry_after = check_rate_limit(scope, limit=limit, window_seconds=window_seconds)
            if not ok:
                response = jsonify({
                    "ok": False,
                    "message": "Too many requests. Please wait before trying again.",
                    "retry_after_seconds": round(retry_after, 2),
                })
                response.status_code = 429
                response.headers["Retry-After"] = str(max(1, int(round(retry_after))))
                return response
            response = func(*args, **kwargs)
            try:
                flask_response = response[0] if isinstance(response, tuple) else response
                flask_response.headers["X-RateLimit-Remaining"] = str(remaining)
            except Exception as exc:
                logger.debug("Could not attach rate limit header for scope %s: %s", scope, exc)
            return response
        return wrapper
    return decorator
