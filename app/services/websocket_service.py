"""In-process progress event hub for WebSocket/SSE transports."""
from __future__ import annotations

import queue
import logging
import threading
import time
from collections import deque
from typing import Any, Deque, Dict, List


MAX_EVENT_HISTORY = 200
logger = logging.getLogger(__name__)


class ProgressEventHub:
    _lock = threading.RLock()
    _events: Deque[Dict[str, Any]] = deque(maxlen=MAX_EVENT_HISTORY)
    _subscribers: List[queue.Queue] = []
    _sequence = 0

    @classmethod
    def publish(cls, event_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        with cls._lock:
            cls._sequence += 1
            event = {
                "seq": cls._sequence,
                "type": str(event_type),
                "time": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "payload": dict(payload),
            }
            cls._events.append(event)
            subscribers = list(cls._subscribers)
        for subscriber in subscribers:
            try:
                subscriber.put_nowait(event)
            except Exception as exc:
                logger.debug("Dropping progress event for unavailable subscriber: %s", exc)
        return event

    @classmethod
    def recent(cls, after: int = 0, limit: int = 50) -> List[Dict[str, Any]]:
        with cls._lock:
            rows = [event for event in cls._events if int(event.get("seq", 0)) > int(after)]
        return rows[-max(1, min(200, int(limit))):]

    @classmethod
    def subscribe(cls) -> queue.Queue:
        q: queue.Queue = queue.Queue(maxsize=100)
        with cls._lock:
            cls._subscribers.append(q)
        return q

    @classmethod
    def unsubscribe(cls, q: queue.Queue) -> None:
        with cls._lock:
            if q in cls._subscribers:
                cls._subscribers.remove(q)

    @classmethod
    def reset(cls) -> None:
        with cls._lock:
            cls._events.clear()
            cls._subscribers.clear()
            cls._sequence = 0


def job_event_payload(job: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": job.get("id"),
        "title": job.get("title"),
        "phase": job.get("phase"),
        "stage": job.get("stage"),
        "stage_label": job.get("stage_label"),
        "stage_detail": job.get("stage_detail"),
        "progress": job.get("progress"),
        "progress_mode": job.get("progress_mode"),
        "exit_code": job.get("exit_code"),
        "started_at": job.get("started_at"),
        "finished_at": job.get("finished_at"),
    }


def progress_transport_status() -> Dict[str, Any]:
    return {
        "schema": "spriteforge.progress_transport.v1",
        "browser_transport": "sse",
        "stream_endpoint": "/api/progress/stream",
        "events_endpoint": "/api/progress/events",
        "fallback": "polling",
        "upstream_transports": {
            "comfyui": "websocket",
        },
        "notes": "SpriteForge uses Server-Sent Events for browser progress push and bridges ComfyUI websocket events into the shared progress hub when available.",
    }
