"""Read-only lexical retrieval for SpriteForge's approved local knowledge.

The assistant deliberately uses a small, explicit allowlist instead of crawling the
workspace.  This keeps API keys, logs, generated assets, and model/vendor payloads
out of assistant context while still making the shipped guides and presets useful
without an LLM or an embedding dependency.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
import re
from typing import Any, Mapping, Sequence


MAX_SOURCE_BYTES = 512_000
MAX_CHUNK_CHARS = 1_200
MAX_PROJECT_BYTES = 256_000


@dataclass(frozen=True)
class KnowledgeSpec:
    path: str
    title: str
    kind: str = "documentation"
    safe_config: bool = False


@dataclass(frozen=True)
class KnowledgeChunk:
    chunk_id: str
    title: str
    path: str
    kind: str
    section: str
    text: str


@dataclass(frozen=True)
class RetrievedChunk:
    chunk: KnowledgeChunk
    score: float


# Every non-project file the retriever may read is named here.  In particular,
# this excludes .env files, logs, output, vendor, uploaded media, and model files.
APPROVED_KNOWLEDGE_FILES: tuple[KnowledgeSpec, ...] = (
    KnowledgeSpec("docs/END_USER_GUIDE.md", "SpriteForge End User Guide"),
    KnowledgeSpec("docs/ONE_PAGE_CHEAT_SHEET.md", "SpriteForge One-Page Cheat Sheet"),
    KnowledgeSpec("docs/FIRST_RUN_CHECKLIST_v8.md", "First Run Checklist"),
    KnowledgeSpec("docs/TROUBLESHOOTING_v8.md", "Troubleshooting Guide"),
    KnowledgeSpec("docs/WAN_MODEL_TIERS_v11.md", "WAN Model Tiers"),
    KnowledgeSpec("docs/LOCAL_FORGE_GUIDE.md", "Local Forge Guide"),
    KnowledgeSpec("docs/AUTO_WAN_INSTALL_v10.md", "Local WAN Setup Guide"),
    KnowledgeSpec("docs/api.md", "SpriteForge API Guide"),
    KnowledgeSpec("END_USER_README.md", "SpriteForge Read Me"),
    KnowledgeSpec("config/easy_presets.json", "Sprite and Animation Presets", "preset"),
    KnowledgeSpec("config/character_archetypes.json", "Character Archetypes", "preset"),
    KnowledgeSpec("config/pixel_prompt_templates.json", "Pixel Prompt Templates", "preset"),
    KnowledgeSpec("config/pixel_asset_modes.json", "Pixel Asset Modes", "preset"),
    KnowledgeSpec("config/user_presets.json", "User Presets", "preset"),
    KnowledgeSpec(
        "config/spriteforge_config.json",
        "Safe SpriteForge Configuration Summary",
        "configuration",
        safe_config=True,
    ),
)


_WORD_RE = re.compile(r"[a-z0-9]+", re.IGNORECASE)
_HEADING_RE = re.compile(r"^#{1,6}\s+(.+?)\s*$")
_SPACE_RE = re.compile(r"\s+")
_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_SECRET_ASSIGNMENT_RE = re.compile(
    r"\b(?:api[_-]?key|access[_-]?token|refresh[_-]?token|id[_-]?token|hf[_-]?token|"
    r"auth(?:orization)?|password|passwd|secret|session[_-]?token|credential)\b"
    r"(\s*[:=]\s*)[^\r\n]*",
    re.IGNORECASE,
)
_SECRET_VALUE_PATTERNS = (
    re.compile(r"\bsk-[A-Za-z0-9_-]{12,}\b"),
    re.compile(r"\bAIza[A-Za-z0-9_-]{20,}\b"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b", re.IGNORECASE),
    re.compile(r"\bBearer\s+[A-Za-z0-9._~+/-]{12,}", re.IGNORECASE),
)
_SENSITIVE_KEY_RE = re.compile(
    r"(?:api[_-]?key|access[_-]?token|refresh[_-]?token|id[_-]?token|hf[_-]?token|"
    r"auth(?:orization)?|password|passwd|secret|session[_-]?token|credential|"
    r"(?:^|[_-])token(?:$|[_-]))",
    re.IGNORECASE,
)
_COMMAND_LINE_RE = re.compile(
    r"^(?:python(?:3)?|py|powershell|pwsh|cmd|bash|sh|git|curl|wget|blender)(?:\.exe)?\s+",
    re.IGNORECASE,
)
_STOP_WORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "can", "do", "for",
    "from", "how", "i", "in", "is", "it", "me", "my", "of", "on", "or",
    "help", "please", "should", "that", "the", "this", "to", "what", "when", "where",
    "which", "with", "would", "you", "your",
}


_QUERY_ALIASES: Mapping[str, tuple[str, ...]] = {
    "create": ("generate", "generation", "sprite", "sprite-lab", "prompt"),
    "make": ("create", "generate", "sprite", "prompt"),
    "review": ("quality", "qa", "inspect", "flicker", "seam"),
    "polish": ("quality", "qa", "cleanup", "repair"),
    "export": ("release", "package", "godot", "unity", "unreal", "atlas"),
    "play": ("preview", "animation", "player"),
    "edit": ("editor", "frame", "pixel", "inpaint"),
    "problem": ("troubleshooting", "quality", "failure", "repair"),
    "broken": ("troubleshooting", "failure", "repair", "diagnostic"),
    "start": ("first-run", "setup", "guide", "debug"),
    "model": ("wan", "profile", "comfyui", "setup"),
    "character": ("archetype", "sprite", "style", "actions"),
    "project": ("manifest", "palette", "style", "actions", "directions"),
}


_SAFE_CONFIG_TOP_LEVEL = {
    "comfy",
    "sprite_defaults",
    "wan_defaults",
    "profiles",
    "wan_modes",
}
_SAFE_PROJECT_FIELDS = (
    "schema",
    "schema_version",
    "project_id",
    "name",
    "character",
    "style",
    "background",
    "profile",
    "mode",
    "actions",
    "directions",
    "fps",
    "cell_size",
    "frames_by_action",
    "quality_gates",
    "palette_lock",
    "feature_flags",
)


def _redact_text(value: Any) -> str:
    text = _CONTROL_RE.sub("", "" if value is None else str(value))
    for pattern in _SECRET_VALUE_PATTERNS:
        text = pattern.sub("[credential removed]", text)
    text = _SECRET_ASSIGNMENT_RE.sub(lambda match: f"[credential removed]{match.group(1)}[credential removed]", text)
    return text


def _clean_text(value: Any, *, limit: int | None = None) -> str:
    text = _redact_text(value)
    text = _SPACE_RE.sub(" ", text).strip()
    return text[:limit].rstrip() if limit is not None else text


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except (OSError, ValueError):
        return False


def _safe_value(value: Any, *, depth: int = 0) -> Any:
    """Copy JSON-like data while removing secret-looking keys and huge values."""
    if depth > 6:
        return "[nested data omitted]"
    if isinstance(value, Mapping):
        result: dict[str, Any] = {}
        for raw_key, item in value.items():
            key = _clean_text(raw_key, limit=100)
            if not key or _SENSITIVE_KEY_RE.search(key):
                continue
            result[key] = _safe_value(item, depth=depth + 1)
        return result
    if isinstance(value, (list, tuple)):
        return [_safe_value(item, depth=depth + 1) for item in list(value)[:100]]
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return _clean_text(value, limit=2_000)


def _safe_config_payload(data: Any) -> dict[str, Any]:
    if not isinstance(data, Mapping):
        return {}
    return {
        key: _safe_value(data[key])
        for key in _SAFE_CONFIG_TOP_LEVEL
        if key in data and not _SENSITIVE_KEY_RE.search(key)
    }


def _flatten_json(value: Any, prefix: str = "", *, depth: int = 0) -> list[str]:
    if depth > 7:
        return []
    if isinstance(value, Mapping):
        lines: list[str] = []
        for key, item in value.items():
            clean_key = _clean_text(key, limit=100)
            if not clean_key or _SENSITIVE_KEY_RE.search(clean_key):
                continue
            child = f"{prefix}.{clean_key}" if prefix else clean_key
            lines.extend(_flatten_json(item, child, depth=depth + 1))
        return lines
    if isinstance(value, (list, tuple)):
        if all(not isinstance(item, (Mapping, list, tuple)) for item in value):
            rendered = ", ".join(_clean_text(item, limit=300) for item in value[:100])
            return [f"{prefix}: {rendered}" if prefix else rendered]
        lines = []
        for index, item in enumerate(value[:100]):
            lines.extend(_flatten_json(item, f"{prefix}[{index}]", depth=depth + 1))
        return lines
    rendered = _clean_text(value, limit=2_000)
    return [f"{prefix}: {rendered}" if prefix else rendered] if rendered else []


def _windows(text: str, *, size: int = MAX_CHUNK_CHARS) -> list[str]:
    text = text.strip()
    if not text:
        return []
    if len(text) <= size:
        return [text]
    rows: list[str] = []
    cursor = 0
    while cursor < len(text):
        end = min(len(text), cursor + size)
        if end < len(text):
            boundary = max(text.rfind("\n", cursor, end), text.rfind(". ", cursor, end))
            if boundary > cursor + (size // 2):
                end = boundary + 1
        part = text[cursor:end].strip()
        if part:
            rows.append(part)
        cursor = max(end, cursor + 1)
    return rows


def _markdown_sections(text: str, default_title: str) -> list[tuple[str, str]]:
    sections: list[tuple[str, str]] = []
    heading = default_title
    lines: list[str] = []
    in_fence = False
    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        if line.strip().startswith("```"):
            in_fence = not in_fence
            continue
        match = _HEADING_RE.match(line) if not in_fence else None
        if match:
            body = "\n".join(lines).strip()
            if body:
                sections.append((heading, body))
            heading = _clean_text(match.group(1), limit=160) or default_title
            lines = []
            continue
        lines.append(line)
    body = "\n".join(lines).strip()
    if body:
        sections.append((heading, body))
    return sections


def _chunk_id(path: str, section: str, index: int, text: str) -> str:
    digest = hashlib.sha256(f"{path}|{section}|{index}|{text}".encode("utf-8")).hexdigest()
    return digest[:20]


def _stem(token: str) -> str:
    if len(token) > 5 and token.endswith("ing"):
        token = token[:-3]
        if len(token) > 3 and token[-1] == token[-2]:
            token = token[:-1]
    elif len(token) > 4 and token.endswith("ied"):
        token = f"{token[:-3]}y"
    elif len(token) > 4 and token.endswith("ed"):
        token = token[:-2]
    elif len(token) > 4 and token.endswith("ies"):
        token = f"{token[:-3]}y"
    elif len(token) > 4 and token.endswith("s") and not token.endswith("ss"):
        token = token[:-1]
    return token


def _tokens(text: str) -> list[str]:
    tokens: list[str] = []
    for raw in _WORD_RE.findall(text):
        token = _stem(raw.lower())
        if len(token) > 1 and token not in _STOP_WORDS:
            tokens.append(token)
    return tokens


def _query_terms(text: str) -> tuple[set[str], set[str]]:
    direct = set(_tokens(text))
    expanded = set(direct)
    for token in tuple(direct):
        expanded.update(_QUERY_ALIASES.get(token, ()))
    return direct, expanded


class AssistantKnowledgeService:
    """Build a bounded in-memory index from approved local text sources."""

    def __init__(
        self,
        root: Path,
        *,
        approved_files: Sequence[KnowledgeSpec] = APPROVED_KNOWLEDGE_FILES,
    ) -> None:
        self.root = Path(root).resolve()
        self.approved_files = tuple(approved_files)

    def _read_spec(self, spec: KnowledgeSpec) -> str | None:
        path = (self.root / spec.path).resolve()
        if not _is_within(path, self.root) or not path.is_file():
            return None
        try:
            if path.stat().st_size > MAX_SOURCE_BYTES:
                return None
            raw = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return None
        if path.suffix.lower() != ".json":
            return _redact_text(raw)
        try:
            data = json.loads(raw)
        except (TypeError, ValueError):
            return None
        safe = _safe_config_payload(data) if spec.safe_config else _safe_value(data)
        return "\n".join(_flatten_json(safe))

    def _chunks_for_spec(self, spec: KnowledgeSpec) -> list[KnowledgeChunk]:
        text = self._read_spec(spec)
        if not text:
            return []
        if spec.path.lower().endswith(".md") or spec.path.lower().endswith(".txt"):
            sections = _markdown_sections(text, spec.title)
        else:
            sections = [(spec.title, text)]
        chunks: list[KnowledgeChunk] = []
        for section, body in sections:
            for index, part in enumerate(_windows(body)):
                chunks.append(KnowledgeChunk(
                    chunk_id=_chunk_id(spec.path, section, index, part),
                    title=spec.title,
                    path=spec.path.replace("\\", "/"),
                    kind=spec.kind,
                    section=section,
                    text=part,
                ))
        return chunks

    def _project_manifest_path(self, project: Any) -> Path | None:
        if project in (None, False, ""):
            return None
        candidate: Any = project
        if project is True or str(project).strip().lower() == "active":
            state_path = self.root / "output" / "projects" / "project_state.json"
            try:
                state = json.loads(state_path.read_text(encoding="utf-8"))
                candidate = state.get("active_project") if isinstance(state, Mapping) else None
            except (OSError, TypeError, ValueError):
                return None
        elif isinstance(project, Mapping):
            candidate = project.get("path") or project.get("project_path") or project.get("root")
        if not isinstance(candidate, (str, Path)) or not str(candidate).strip():
            return None
        raw = Path(str(candidate).strip())
        if raw.is_absolute():
            path = raw.resolve()
        else:
            path = (self.root / raw).resolve()
            if not path.exists() and len(raw.parts) == 1:
                path = (self.root / "projects" / raw).resolve()
        if path.is_dir():
            path = path / "spriteforge_project.json"
        projects_root = (self.root / "projects").resolve()
        if not _is_within(path, projects_root):
            raise ValueError("Project context must be a SpriteForge project under the local projects folder.")
        if path.name != "spriteforge_project.json" or not path.is_file():
            raise ValueError("Project context was not found.")
        return path

    def _project_chunk(self, project: Any) -> KnowledgeChunk | None:
        path = self._project_manifest_path(project)
        if path is None:
            return None
        try:
            if path.stat().st_size > MAX_PROJECT_BYTES:
                raise ValueError("Project context is too large for the assistant.")
            data = json.loads(path.read_text(encoding="utf-8"))
        except OSError as exc:
            raise ValueError("Project context could not be read.") from exc
        except (TypeError, json.JSONDecodeError) as exc:
            raise ValueError("Project context is not valid JSON.") from exc
        if not isinstance(data, Mapping):
            raise ValueError("Project context is not a JSON object.")
        filtered = {
            key: _safe_value(data[key])
            for key in _SAFE_PROJECT_FIELDS
            if key in data and not _SENSITIVE_KEY_RE.search(key)
        }
        text = "\n".join(_flatten_json(filtered))
        if not text:
            return None
        relative = str(path.relative_to(self.root)).replace("\\", "/")
        name = _clean_text(filtered.get("name") or path.parent.name, limit=120)
        title = f"Current project: {name}"
        return KnowledgeChunk(
            chunk_id=_chunk_id(relative, title, 0, text),
            title=title,
            path=relative,
            kind="project",
            section="Approved project settings",
            text=text,
        )

    def build_chunks(self, *, project: Any = None) -> list[KnowledgeChunk]:
        chunks: list[KnowledgeChunk] = []
        for spec in self.approved_files:
            chunks.extend(self._chunks_for_spec(spec))
        project_chunk = self._project_chunk(project)
        if project_chunk is not None:
            chunks.append(project_chunk)
        return chunks

    def retrieve(
        self,
        query: str,
        *,
        project: Any = None,
        context_text: str = "",
        limit: int = 5,
    ) -> list[RetrievedChunk]:
        chunks = self.build_chunks(project=project)
        if not chunks:
            return []
        direct, terms = _query_terms(query)
        _, context_terms = _query_terms(context_text)
        terms.update(context_terms)
        if not terms:
            return []
        token_counts = [Counter(_tokens(f"{chunk.title} {chunk.section} {chunk.text}")) for chunk in chunks]
        document_frequency = Counter(
            term
            for counts in token_counts
            for term in counts.keys()
        )
        count = len(chunks)
        scored: list[RetrievedChunk] = []
        normalized_query = _clean_text(query).lower()
        for chunk, counts in zip(chunks, token_counts):
            score = 0.0
            title_tokens = set(_tokens(f"{chunk.title} {chunk.section} {chunk.path}"))
            direct_matches = sum(1 for term in direct if counts.get(term))
            minimum_direct_matches = 2 if len(direct) >= 3 else (1 if direct else 0)
            if direct_matches < minimum_direct_matches:
                continue
            for term in terms:
                frequency = counts.get(term, 0)
                if not frequency:
                    continue
                inverse_frequency = math.log((count + 1) / (document_frequency[term] + 1)) + 1.0
                weight = 2.0 if term in direct else 0.65
                if term in title_tokens:
                    weight += 0.75
                score += weight * (1.0 + math.log(frequency)) * inverse_frequency
            if normalized_query and len(normalized_query) >= 5 and normalized_query in chunk.text.lower():
                score += 5.0
            if chunk.kind == "project" and direct.intersection({"project", "current", "character", "style", "palette"}):
                score += 2.0
            if score > 0:
                scored.append(RetrievedChunk(chunk=chunk, score=round(score, 4)))
        scored.sort(key=lambda item: (-item.score, item.chunk.path, item.chunk.section, item.chunk.chunk_id))

        # Prefer citations from different files before returning a second chunk
        # from a long guide.  This makes the source list both useful and compact.
        selected: list[RetrievedChunk] = []
        deferred: list[RetrievedChunk] = []
        seen_paths: set[str] = set()
        for item in scored:
            if item.chunk.path in seen_paths:
                deferred.append(item)
                continue
            selected.append(item)
            seen_paths.add(item.chunk.path)
            if len(selected) >= max(1, min(8, int(limit))):
                return selected
        for item in deferred:
            selected.append(item)
            if len(selected) >= max(1, min(8, int(limit))):
                break
        return selected


def context_to_text(context: Any, *, limit: int = 2_000) -> str:
    """Create bounded retrieval context while dropping secret-looking fields."""
    if context in (None, "", {}, []):
        return ""
    safe = _safe_value(context)
    if isinstance(safe, str):
        return _clean_text(safe, limit=limit)
    return _clean_text("; ".join(_flatten_json(safe)), limit=limit)


def source_snippet(text: str, query: str, *, limit: int = 360) -> str:
    """Choose a stable, query-relevant plain-text excerpt for a citation."""
    direct, expanded = _query_terms(query)
    terms = direct or expanded
    candidates = []
    for raw in re.split(r"(?:\n+|(?<=[.!?])\s+)", text):
        clean = _clean_text(raw.lstrip("-*#> "))
        clean = re.sub(r"`([^`]*)`", r"\1", clean).replace("**", "")
        if len(clean) < 12:
            continue
        if clean.endswith(":"):
            continue
        tokens = Counter(_tokens(clean))
        score = sum(2 if term in direct else 1 for term in terms if tokens.get(term))
        if _COMMAND_LINE_RE.match(clean):
            continue
        candidates.append((score, clean))
    if not candidates:
        return "See the cited SpriteForge section for details."
    candidates.sort(key=lambda item: (-item[0], -min(len(item[1]), limit), item[1].lower()))
    chosen = [candidates[0][1]]
    for score, candidate in candidates[1:]:
        if score <= 0 or candidate in chosen:
            continue
        separator = " " if chosen[-1].endswith((".", "!", "?")) else ". "
        combined = separator.join(chosen + [candidate])
        if len(combined) <= limit:
            chosen.append(candidate)
        break
    if len(chosen) == 1:
        best = chosen[0]
    else:
        separator = " " if chosen[0].endswith((".", "!", "?")) else ". "
        best = separator.join(chosen)
    if len(best) <= limit:
        return best
    cut = best[:limit].rsplit(" ", 1)[0].rstrip(" ,;:")
    return f"{cut}…"


__all__ = [
    "APPROVED_KNOWLEDGE_FILES",
    "AssistantKnowledgeService",
    "KnowledgeChunk",
    "KnowledgeSpec",
    "RetrievedChunk",
    "context_to_text",
    "source_snippet",
]
