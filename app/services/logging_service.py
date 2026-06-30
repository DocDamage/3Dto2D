from __future__ import annotations

import json
import logging
import sys
import time
from typing import Any, Dict


RESERVED = set(logging.LogRecord("", 0, "", 0, "", (), None).__dict__.keys())


class JsonLogFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        data: Dict[str, Any] = {
            "time": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(record.created)),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            data["exception"] = self.formatException(record.exc_info)
        for key, value in record.__dict__.items():
            if key not in RESERVED and not key.startswith("_"):
                data[key] = value
        return json.dumps(data, ensure_ascii=False, default=str)


def _level(value: Any) -> int:
    if isinstance(value, int):
        return value
    return getattr(logging, str(value or "INFO").upper(), logging.INFO)


def configure_logging(config: Dict[str, Any] | None = None) -> logging.Logger:
    settings = (config or {}).get("logging", {}) if isinstance(config, dict) else {}
    logger = logging.getLogger("spriteforge")
    logger.handlers = []
    logger.setLevel(_level(settings.get("level", "INFO")))
    logger.propagate = False
    handler = logging.StreamHandler(sys.stderr)
    if settings.get("json", False):
        handler.setFormatter(JsonLogFormatter())
    else:
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    logger.addHandler(handler)
    return logger


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(f"spriteforge.{name.strip('.')}")
