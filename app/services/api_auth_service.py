from __future__ import annotations
import secrets

__all__ = ["get_session_token", "validate_token"]

_session_token: str = secrets.token_hex(24)

def get_session_token() -> str:
    global _session_token
    return _session_token

def validate_token(token: str | None) -> bool:
    if not token:
        return False
    global _session_token
    return secrets.compare_digest(token, _session_token)
