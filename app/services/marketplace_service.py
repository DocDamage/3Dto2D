import json
import hashlib
import logging
import re
import shutil
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from services.plugin_manager import PLUGIN_SDK_VERSION


MARKETPLACE_SCHEMA = "spriteforge_marketplace.v1"
MARKETPLACE_SHARE_SCHEMA = "spriteforge_marketplace_share.v1"
MARKETPLACE_SHARE_COMPAT_SCHEMA = "spriteforge.marketplace_share_compatibility.v1"
_URL_PREFIXES = ("http://", "https://", "/file/")
logger = logging.getLogger(__name__)


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


def _safe_import_name(value: Any) -> str:
    text = _as_text(value, "imported_bundle")
    text = re.sub(r"[^A-Za-z0-9_.-]+", "_", text).strip("._")
    return (text or "imported_bundle")[:80]


def _bundle_integrity(path: Path) -> Dict[str, Any]:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return {
        "sha256": digest.hexdigest(),
        "size_bytes": path.stat().st_size,
    }


def _share_compatibility() -> Dict[str, Any]:
    return {
        "schema": MARKETPLACE_SHARE_COMPAT_SCHEMA,
        "host": "SpriteForge Studio",
        "marketplace_schema": MARKETPLACE_SCHEMA,
        "share_schema": MARKETPLACE_SHARE_SCHEMA,
        "plugin_sdk_version": PLUGIN_SDK_VERSION,
        "import_policy": "local bundles are copied non-destructively; remote bundles require explicit download",
    }


def _local_entry(root: Path, bundle: Path) -> Dict[str, Any]:
    mtime = bundle.stat().st_mtime
    rel_path = bundle.resolve().relative_to(root.resolve()).as_posix()
    integrity = _bundle_integrity(bundle)
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
        "size_bytes": integrity["size_bytes"],
        "sha256": integrity["sha256"],
    }


def plan_marketplace_import(root: Path, entry: Dict[str, Any], imports_dir: Optional[Path] = None) -> Dict[str, Any]:
    """Return a non-destructive import plan for a marketplace bundle entry."""
    root = root.resolve()
    bundle_url = _as_text(entry.get("bundle_url"))
    if not bundle_url:
        return {"ok": False, "message": "bundle_url is required.", "importable": False}
    if bundle_url.startswith(("http://", "https://")):
        return {
            "ok": True,
            "importable": False,
            "mode": "remote",
            "message": "Remote marketplace entries must be downloaded explicitly before import.",
            "source_url": bundle_url,
        }
    if not bundle_url.startswith("/file/"):
        return {"ok": False, "message": "Unsupported bundle URL.", "importable": False}

    rel = bundle_url[len("/file/"):].replace("\\", "/").lstrip("/")
    source = (root / rel).resolve()
    try:
        source.relative_to(root)
    except ValueError:
        return {"ok": False, "message": "Bundle path is outside the workspace.", "importable": False}
    if not source.exists() or not source.is_file() or source.suffix.lower() != ".spriteforge":
        return {"ok": False, "message": "Bundle file was not found or is not a .spriteforge bundle.", "importable": False}

    target_root = (imports_dir or root / "projects" / "imports").resolve()
    try:
        target_root.relative_to(root)
    except ValueError:
        return {"ok": False, "message": "Import target is outside the workspace.", "importable": False}
    safe_name = _safe_import_name(entry.get("id") or source.stem)
    target = target_root / f"{safe_name}.spriteforge"
    integrity = _bundle_integrity(source)
    return {
        "ok": True,
        "importable": True,
        "mode": "local",
        "source_path": source.as_posix(),
        "target_path": target.as_posix(),
        "size_bytes": integrity["size_bytes"],
        "sha256": integrity["sha256"],
        "message": "Bundle is ready for local import.",
    }


def import_marketplace_bundle(root: Path, entry: Dict[str, Any], imports_dir: Optional[Path] = None) -> Dict[str, Any]:
    """Copy a verified local marketplace bundle into the imports folder."""
    plan = plan_marketplace_import(root, entry, imports_dir=imports_dir)
    if not plan.get("ok") or not plan.get("importable"):
        return {"ok": False, "imported": False, "plan": plan, "message": plan.get("message", "Bundle is not importable.")}
    source = Path(str(plan["source_path"])).resolve()
    target = Path(str(plan["target_path"])).resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and source.read_bytes() == target.read_bytes():
        return {
            "ok": True,
            "imported": True,
            "already_present": True,
            "plan": plan,
            "target_path": target.as_posix(),
            "message": "Bundle is already present in local imports.",
        }
    if target.exists():
        stem = target.stem
        suffix = target.suffix
        counter = 2
        while target.exists():
            target = target.with_name(f"{stem}_{counter}{suffix}")
            counter += 1
    shutil.copy2(source, target)
    updated_plan = dict(plan)
    updated_plan["target_path"] = target.as_posix()
    return {
        "ok": True,
        "imported": True,
        "already_present": False,
        "plan": updated_plan,
        "target_path": target.as_posix(),
        "message": "Bundle imported into projects/imports.",
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
    except Exception as exc:
        logger.warning("Could not load marketplace index %s: %s", index_path, exc)
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
    for item in entries:
        item["import_plan"] = plan_marketplace_import(root, item)
    return {
        "schema": MARKETPLACE_SCHEMA,
        "entries": entries[:limit],
        "local_count": len(local_entries),
        "index_path": index.as_posix(),
    }


def build_marketplace_share_manifest(
    root: Path,
    bundle_paths: Optional[List[str]] = None,
    author: str = "Local workspace",
    license_name: str = "",
) -> Dict[str, Any]:
    """Build a safe community-sharing manifest for selected local bundles."""
    root = root.resolve()
    selected: List[Path] = []
    if bundle_paths:
        for value in bundle_paths:
            path = Path(value)
            if not path.is_absolute():
                path = root / path
            resolved = path.resolve()
            try:
                resolved.relative_to(root)
            except ValueError:
                continue
            if resolved.exists() and resolved.is_file() and resolved.suffix.lower() == ".spriteforge":
                selected.append(resolved)
    else:
        selected = [
            (root / entry["bundle_path"]).resolve()
            for entry in discover_local_bundles(root)
            if entry.get("bundle_path")
        ]
    entries = []
    seen: set[Path] = set()
    for bundle in selected:
        if bundle in seen:
            continue
        seen.add(bundle)
        entry = _local_entry(root, bundle)
        import_plan = plan_marketplace_import(root, entry)
        share_checks = {
            "workspace_safe": entry["bundle_url"].startswith("/file/") and ".." not in entry["bundle_url"],
            "bundle_exists": bundle.exists() and bundle.is_file(),
            "size_bytes": entry["size_bytes"],
            "sha256_present": bool(entry.get("sha256")),
            "compatibility_declared": True,
            "has_preview": bool(entry["preview_url"]),
            "license_declared": bool(license_name),
            "local_import_plan_ok": bool(import_plan.get("ok")),
            "local_importable": bool(import_plan.get("importable")),
        }
        entries.append({
            "id": entry["id"],
            "title": entry["title"],
            "author": author or entry["author"],
            "description": entry["description"],
            "tags": entry["tags"],
            "license": license_name,
            "bundle_url": entry["bundle_url"],
            "preview_url": entry["preview_url"],
            "size_bytes": entry["size_bytes"],
            "sha256": entry.get("sha256", ""),
            "compatibility": _share_compatibility(),
            "share_ready": True,
            "share_checks": share_checks,
            "import_plan": import_plan,
            "notes": "Review asset and plugin licenses before publishing this manifest.",
        })
    return {
        "schema": MARKETPLACE_SHARE_SCHEMA,
        "compatibility": _share_compatibility(),
        "entry_count": len(entries),
        "entries": entries,
        "non_destructive": True,
        "upload_performed": False,
    }
