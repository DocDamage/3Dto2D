import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


MARKETPLACE_SCHEMA = "spriteforge_marketplace.v1"
_URL_PREFIXES = ("http://", "https://", "/file/")


def _as_text(value: Any, fallback: str = "") -> str:
    text = str(value or "").strip()
    return text or fallback


def _as_tags(value: Any) -> List[str]:
    if not isinstance(value, list):
        return []
    tags: List[str] = []
    for item in value:
        tag = _as_text(item)
        if tag and tag not in tags:
            tags.append(tag[:32])
    return tags[:8]


def _file_url(root: Path, path: Path) -> str:
    return "/file/" + path.resolve().relative_to(root.resolve()).as_posix()


def _safe_url(value: Any) -> str:
    url = _as_text(value)
    return url if url.startswith(_URL_PREFIXES) else ""


def _bundle_title(path: Path) -> str:
    return path.stem.replace("_", " ").replace("-", " ").title()


def _local_entry(root: Path, bundle: Path) -> Dict[str, Any]:
    mtime = bundle.stat().st_mtime
    rel_path = bundle.resolve().relative_to(root.resolve()).as_posix()
    preview = next(
        (
            candidate
            for candidate in (
                bundle.with_suffix(".gif"),
                bundle.with_suffix(".png"),
                bundle.parent / "preview.gif",
                bundle.parent / "preview.png",
            )
            if candidate.exists() and candidate.is_file()
        ),
        None,
    )
    return {
        "id": "local-" + rel_path.lower().replace("/", "-").replace(".", "-"),
        "title": _bundle_title(bundle),
        "author": "Local workspace",
        "description": "Exported SpriteForge project bundle ready to import or share.",
        "tags": ["local", "spriteforge"],
        "license": "",
        "updated_at": "",
        "source": "local",
        "bundle_url": _file_url(root, bundle),
        "preview_url": _file_url(root, preview) if preview else "",
        "bundle_path": rel_path,
        "modified": mtime,
        "size_bytes": bundle.stat().st_size,
    }


def discover_local_bundles(root: Path, limit: int = 40) -> List[Dict[str, Any]]:
    root = root.resolve()
    search_roots = [root / "output" / "releases", root / "releases", root / "projects"]
    seen: set[Path] = set()
    entries: List[Dict[str, Any]] = []
    for search_root in search_roots:
        if not search_root.exists():
            continue
        for bundle in search_root.rglob("*.spriteforge"):
            resolved = bundle.resolve()
            if resolved in seen or not resolved.is_file():
                continue
            seen.add(resolved)
            entries.append(_local_entry(root, resolved))
    entries.sort(key=lambda item: item["modified"], reverse=True)
    return entries[:limit]


def _normalize_index_entry(raw: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    bundle_url = _safe_url(raw.get("bundle_url"))
    if not bundle_url:
        return None
    title = _as_text(raw.get("title"))
    if not title:
        return None
    entry_id = _as_text(raw.get("id"), title.lower().replace(" ", "-"))
    return {
        "id": entry_id[:80],
        "title": title[:120],
        "author": _as_text(raw.get("author"), "Community")[:80],
        "description": _as_text(raw.get("description"))[:240],
        "tags": _as_tags(raw.get("tags")),
        "license": _as_text(raw.get("license"))[:80],
        "updated_at": _as_text(raw.get("updated_at"))[:40],
        "source": _as_text(raw.get("source"), "index")[:40],
        "bundle_url": bundle_url,
        "preview_url": _safe_url(raw.get("preview_url")),
        "bundle_path": "",
        "modified": 0,
        "size_bytes": 0,
    }


def load_index_entries(index_path: Path) -> List[Dict[str, Any]]:
    if not index_path.exists() or not index_path.is_file():
        return []
    try:
        data = json.loads(index_path.read_text(encoding="utf-8"))
    except Exception:
        return []
    rows: Iterable[Any] = data.get("entries", []) if isinstance(data, dict) else []
    entries: List[Dict[str, Any]] = []
    for row in rows:
        if isinstance(row, dict):
            entry = _normalize_index_entry(row)
            if entry:
                entries.append(entry)
    return entries


def marketplace_gallery(root: Path, index_path: Optional[Path] = None, limit: int = 60) -> Dict[str, Any]:
    index = index_path or root / "config" / "marketplace_index.json"
    local_entries = discover_local_bundles(root, limit=limit)
    indexed_entries = load_index_entries(index)
    seen = {item["bundle_url"] for item in local_entries}
    entries = list(local_entries)
    for item in indexed_entries:
        if item["bundle_url"] in seen:
            continue
        seen.add(item["bundle_url"])
        entries.append(item)
    return {
        "schema": MARKETPLACE_SCHEMA,
        "entries": entries[:limit],
        "local_count": len(local_entries),
        "index_path": index.as_posix(),
    }
