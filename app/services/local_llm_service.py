"""Optional client for user-managed, loopback-only assistant model servers.

SpriteForge does not start a process, download a model, or contact a hosted model
from this module.  When explicitly enabled, it can send a bounded chat request to
an already-running Ollama or OpenAI-compatible endpoint on the loopback interface.
"""
from __future__ import annotations

from dataclasses import dataclass
import http.client
import ipaddress
import json
import math
import os
from typing import Any, Mapping, MutableMapping
from urllib.parse import urlsplit


MAX_RESPONSE_BYTES = 256_000
ALLOWED_PROVIDERS = {"ollama", "openai_compatible"}
PERSISTED_LLM_FIELDS = (
    "enabled",
    "provider",
    "endpoint",
    "model",
    "timeout_seconds",
    "max_context_chunks",
    "max_answer_chars",
)
MIN_TIMEOUT_SECONDS = 1.0
MAX_TIMEOUT_SECONDS = 30.0
MIN_CONTEXT_CHUNKS = 1
MAX_CONTEXT_CHUNKS = 8
MIN_ANSWER_CHARS = 500
MAX_ANSWER_CHARS = 8_000
MAX_ENDPOINT_CHARS = 2_048
MAX_MODEL_CHARS = 256


def _as_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _bounded_float(value: Any, default: float, minimum: float, maximum: float) -> float:
    try:
        return max(minimum, min(maximum, float(value)))
    except (TypeError, ValueError):
        return default


def _bounded_int(value: Any, default: int, minimum: int, maximum: int) -> int:
    try:
        return max(minimum, min(maximum, int(value)))
    except (TypeError, ValueError):
        return default


def _stored_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    normalized = str(value or "").strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError("Assistant enabled must be true or false.")


def _stored_float(value: Any, field: str, minimum: float, maximum: float) -> float:
    if isinstance(value, bool):
        raise ValueError(f"Assistant {field} must be a number.")
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Assistant {field} must be a number.") from exc
    if not math.isfinite(parsed) or not minimum <= parsed <= maximum:
        raise ValueError(f"Assistant {field} must be between {minimum:g} and {maximum:g}.")
    return parsed


def _stored_int(value: Any, field: str, minimum: int, maximum: int) -> int:
    if isinstance(value, bool):
        raise ValueError(f"Assistant {field} must be an integer.")
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Assistant {field} must be an integer.") from exc
    if isinstance(value, float) and not value.is_integer():
        raise ValueError(f"Assistant {field} must be an integer.")
    if isinstance(value, str) and str(parsed) != value.strip():
        raise ValueError(f"Assistant {field} must be an integer.")
    if not minimum <= parsed <= maximum:
        raise ValueError(f"Assistant {field} must be between {minimum} and {maximum}.")
    return parsed


@dataclass(frozen=True)
class LocalLlmSettings:
    enabled: bool = False
    provider: str = "ollama"
    endpoint: str = "http://127.0.0.1:11434"
    model: str = ""
    api_key: str = ""
    timeout_seconds: float = 12.0
    max_context_chunks: int = 5
    max_answer_chars: int = 4_000

    @property
    def configured(self) -> bool:
        if not (
            self.enabled
            and self.provider in ALLOWED_PROVIDERS
            and self.endpoint.strip()
            and self.model.strip()
        ):
            return False
        try:
            self.validate_for_storage()
            return True
        except ValueError:
            return False

    def validate_for_storage(self) -> None:
        """Validate the non-secret settings that may be persisted in app config."""
        if self.provider not in ALLOWED_PROVIDERS:
            raise ValueError("Assistant provider must be ollama or openai_compatible.")
        if not self.endpoint or len(self.endpoint) > MAX_ENDPOINT_CHARS:
            raise ValueError(f"Assistant endpoint must be 1-{MAX_ENDPOINT_CHARS} characters.")
        parsed = urlsplit(self.endpoint)
        if parsed.scheme not in {"http", "https"}:
            raise ValueError("Assistant model endpoint must use http or https.")
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError("Assistant model endpoint cannot contain credentials, a query, or a fragment.")
        _loopback_host(parsed.hostname)
        try:
            port = parsed.port
        except ValueError as exc:
            raise ValueError("Assistant model endpoint has an invalid port.") from exc
        if port is not None and not 1 <= port <= 65_535:
            raise ValueError("Assistant model endpoint port must be between 1 and 65535.")
        if len(self.model) > MAX_MODEL_CHARS:
            raise ValueError(f"Assistant model must be {MAX_MODEL_CHARS} characters or fewer.")
        if self.enabled and not self.model:
            raise ValueError("Choose a local assistant model before enabling the LLM.")
        if not MIN_TIMEOUT_SECONDS <= self.timeout_seconds <= MAX_TIMEOUT_SECONDS:
            raise ValueError(
                f"Assistant timeout must be between {MIN_TIMEOUT_SECONDS:g} and {MAX_TIMEOUT_SECONDS:g} seconds."
            )
        if not MIN_CONTEXT_CHUNKS <= self.max_context_chunks <= MAX_CONTEXT_CHUNKS:
            raise ValueError(
                f"Assistant context chunks must be between {MIN_CONTEXT_CHUNKS} and {MAX_CONTEXT_CHUNKS}."
            )
        if not MIN_ANSWER_CHARS <= self.max_answer_chars <= MAX_ANSWER_CHARS:
            raise ValueError(
                f"Assistant answer cap must be between {MIN_ANSWER_CHARS} and {MAX_ANSWER_CHARS} characters."
            )

    def to_persisted_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "provider": self.provider,
            "endpoint": self.endpoint,
            "model": self.model,
            "timeout_seconds": self.timeout_seconds,
            "max_context_chunks": self.max_context_chunks,
            "max_answer_chars": self.max_answer_chars,
        }

    @classmethod
    def from_mapping(
        cls,
        data: Mapping[str, Any] | None = None,
        *,
        environ: Mapping[str, str] | None = None,
    ) -> "LocalLlmSettings":
        raw = data if isinstance(data, Mapping) else {}
        env = os.environ if environ is None else environ

        def value(key: str, env_key: str, default: Any) -> Any:
            return env[env_key] if env_key in env else raw.get(key, default)

        provider = str(value("provider", "SPRITEFORGE_ASSISTANT_PROVIDER", cls.provider) or "").strip().lower()
        if provider == "openai":
            provider = "openai_compatible"
        return cls(
            enabled=_as_bool(value("enabled", "SPRITEFORGE_ASSISTANT_LLM_ENABLED", cls.enabled)),
            provider=provider,
            endpoint=str(value("endpoint", "SPRITEFORGE_ASSISTANT_ENDPOINT", cls.endpoint) or "").strip(),
            model=str(value("model", "SPRITEFORGE_ASSISTANT_MODEL", cls.model) or "").strip(),
            # Keep credentials out of spriteforge_config.json because that file
            # is returned by the local config status endpoint.
            api_key=str(env.get("SPRITEFORGE_ASSISTANT_API_KEY", "") or "").strip(),
            timeout_seconds=_bounded_float(
                value("timeout_seconds", "SPRITEFORGE_ASSISTANT_TIMEOUT_SECONDS", cls.timeout_seconds),
                cls.timeout_seconds,
                MIN_TIMEOUT_SECONDS,
                MAX_TIMEOUT_SECONDS,
            ),
            max_context_chunks=_bounded_int(
                value("max_context_chunks", "SPRITEFORGE_ASSISTANT_MAX_CONTEXT_CHUNKS", cls.max_context_chunks),
                cls.max_context_chunks,
                MIN_CONTEXT_CHUNKS,
                MAX_CONTEXT_CHUNKS,
            ),
            max_answer_chars=_bounded_int(
                value("max_answer_chars", "SPRITEFORGE_ASSISTANT_MAX_ANSWER_CHARS", cls.max_answer_chars),
                cls.max_answer_chars,
                MIN_ANSWER_CHARS,
                MAX_ANSWER_CHARS,
            ),
        )

    def public_status(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "configured": self.configured,
            "provider": self.provider if self.provider in ALLOWED_PROVIDERS else "invalid",
            "endpoint": self.endpoint,
            "model": self.model,
            "timeout_seconds": self.timeout_seconds,
            "max_context_chunks": self.max_context_chunks,
            "max_answer_chars": self.max_answer_chars,
            "local_only": True,
        }


def normalize_persisted_llm_settings(
    current: Mapping[str, Any] | None,
    update: Mapping[str, Any],
) -> dict[str, Any]:
    """Merge and strictly validate a partial, non-secret settings update."""
    supplied = {key: update[key] for key in PERSISTED_LLM_FIELDS if key in update}
    if not supplied:
        raise ValueError("At least one assistant LLM setting is required.")
    baseline = LocalLlmSettings.from_mapping(current, environ={}).to_persisted_dict()
    if "enabled" in supplied:
        baseline["enabled"] = _stored_bool(supplied["enabled"])
    for field in ("provider", "endpoint", "model"):
        if field not in supplied:
            continue
        if not isinstance(supplied[field], str):
            raise ValueError(f"Assistant {field} must be text.")
        value = supplied[field].strip()
        if any(ord(char) < 32 or ord(char) == 127 for char in value):
            raise ValueError(f"Assistant {field} contains invalid control characters.")
        baseline[field] = value
    if "timeout_seconds" in supplied:
        baseline["timeout_seconds"] = _stored_float(
            supplied["timeout_seconds"],
            "timeout",
            MIN_TIMEOUT_SECONDS,
            MAX_TIMEOUT_SECONDS,
        )
    if "max_context_chunks" in supplied:
        baseline["max_context_chunks"] = _stored_int(
            supplied["max_context_chunks"],
            "context chunks",
            MIN_CONTEXT_CHUNKS,
            MAX_CONTEXT_CHUNKS,
        )
    if "max_answer_chars" in supplied:
        baseline["max_answer_chars"] = _stored_int(
            supplied["max_answer_chars"],
            "answer cap",
            MIN_ANSWER_CHARS,
            MAX_ANSWER_CHARS,
        )
    settings = LocalLlmSettings.from_mapping(baseline, environ={})
    settings.validate_for_storage()
    return settings.to_persisted_dict()


def _loopback_host(hostname: str | None) -> str:
    host = str(hostname or "").strip().lower()
    if host == "localhost":
        # Connect to the literal loopback address so a modified hosts file cannot
        # redirect this optional client to another machine.
        return "127.0.0.1"
    try:
        address = ipaddress.ip_address(host)
    except ValueError as exc:
        raise ValueError("Assistant model endpoint must use localhost or a loopback IP address.") from exc
    if not address.is_loopback:
        raise ValueError("Assistant model endpoint must stay on the loopback interface.")
    return str(address)


def _request_path(provider: str, configured_path: str) -> str:
    path = configured_path.rstrip("/")
    if provider == "ollama":
        if not path:
            return "/api/chat"
        if path.endswith("/api"):
            return f"{path}/chat"
        return path if path.endswith("/api/chat") else path
    if not path:
        return "/v1/chat/completions"
    if path.endswith("/v1"):
        return f"{path}/chat/completions"
    return path if path.endswith("/chat/completions") else path


def _message_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        parts: list[str] = []
        for item in value:
            if isinstance(item, Mapping) and isinstance(item.get("text"), str):
                parts.append(item["text"])
        return "\n".join(parts)
    return ""


class LocalLlmClient:
    def __init__(self, settings: LocalLlmSettings) -> None:
        self.settings = settings

    def _post_json(self, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        parsed = urlsplit(self.settings.endpoint)
        if parsed.scheme not in {"http", "https"}:
            raise ValueError("Assistant model endpoint must use http or https.")
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError("Assistant model endpoint cannot contain credentials, a query, or a fragment.")
        connect_host = _loopback_host(parsed.hostname)
        try:
            port = parsed.port or (443 if parsed.scheme == "https" else 80)
        except ValueError as exc:
            raise ValueError("Assistant model endpoint has an invalid port.") from exc
        path = _request_path(self.settings.provider, parsed.path)
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers: MutableMapping[str, str] = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Host": parsed.netloc,
        }
        if self.settings.api_key:
            headers["Authorization"] = f"Bearer {self.settings.api_key}"
        connection_type = http.client.HTTPSConnection if parsed.scheme == "https" else http.client.HTTPConnection
        connection = connection_type(connect_host, port, timeout=self.settings.timeout_seconds)
        try:
            connection.request("POST", path, body=body, headers=dict(headers))
            response = connection.getresponse()
            raw = response.read(MAX_RESPONSE_BYTES + 1)
            if len(raw) > MAX_RESPONSE_BYTES:
                raise RuntimeError("Local model response exceeded the assistant size limit.")
            if response.status < 200 or response.status >= 300:
                raise RuntimeError(f"Local model returned HTTP {response.status}.")
        finally:
            connection.close()
        try:
            decoded = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise RuntimeError("Local model returned an invalid JSON response.") from exc
        if not isinstance(decoded, Mapping):
            raise RuntimeError("Local model returned an unexpected response.")
        return decoded

    def generate(self, *, system_prompt: str, user_prompt: str) -> str:
        if not (
            self.settings.enabled
            and self.settings.provider in ALLOWED_PROVIDERS
            and self.settings.endpoint.strip()
            and self.settings.model.strip()
        ):
            raise RuntimeError("Local assistant model is disabled or not fully configured.")
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        if self.settings.provider == "ollama":
            payload: Mapping[str, Any] = {
                "model": self.settings.model,
                "messages": messages,
                "stream": False,
                "options": {"temperature": 0.1},
            }
            decoded = self._post_json(payload)
            message = decoded.get("message")
            content = message.get("content") if isinstance(message, Mapping) else decoded.get("response")
        elif self.settings.provider == "openai_compatible":
            payload = {
                "model": self.settings.model,
                "messages": messages,
                "temperature": 0.1,
                "max_tokens": 700,
                "stream": False,
            }
            decoded = self._post_json(payload)
            choices = decoded.get("choices")
            first = choices[0] if isinstance(choices, list) and choices else None
            message = first.get("message") if isinstance(first, Mapping) else None
            content = message.get("content") if isinstance(message, Mapping) else ""
        else:
            raise ValueError("Unsupported local assistant provider.")
        answer = _message_text(content).strip()
        if not answer:
            raise RuntimeError("Local model returned an empty answer.")
        return answer[: self.settings.max_answer_chars].rstrip()


__all__ = [
    "ALLOWED_PROVIDERS",
    "MAX_ANSWER_CHARS",
    "MAX_CONTEXT_CHUNKS",
    "MAX_ENDPOINT_CHARS",
    "MAX_MODEL_CHARS",
    "MAX_TIMEOUT_SECONDS",
    "MIN_ANSWER_CHARS",
    "MIN_CONTEXT_CHUNKS",
    "MIN_TIMEOUT_SECONDS",
    "PERSISTED_LLM_FIELDS",
    "LocalLlmClient",
    "LocalLlmSettings",
    "normalize_persisted_llm_settings",
]
