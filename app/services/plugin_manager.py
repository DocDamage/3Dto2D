import os
import sys
import importlib.util
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from spriteforge_utils import ROOT

PLUGINS_DIR = ROOT / "plugins"
PLUGIN_MANIFEST = "spriteforge_plugin.json"
PLUGIN_SDK_VERSION = "1.0"
logger = logging.getLogger(__name__)
KNOWN_HOOKS = {
    "on_qa_check",
    "on_sprite_processed",
    "on_generation_complete",
    "filter_prompt",
    "filter_quality_report",
}


def plugin_sdk_contract() -> Dict[str, Any]:
    return {
        "schema": "spriteforge.plugin_sdk_contract.v1",
        "sdk_version": PLUGIN_SDK_VERSION,
        "manifest_file": PLUGIN_MANIFEST,
        "known_hooks": sorted(KNOWN_HOOKS),
        "manifest_required_fields": ["id", "name", "version", "sdk_version", "entrypoint", "hooks"],
        "manifest_optional_fields": ["author", "description", "tags", "enabled"],
        "compatibility_rule": "Plugin SDK major version must match host and plugin version must be <= host SDK.",
    }


def plugin_scaffold(plugin_id: str = "my_plugin") -> Dict[str, Any]:
    clean_id = _text(plugin_id, "my_plugin").lower().replace(" ", "_")[:80]
    manifest = {
        "schema": "spriteforge_plugin.v1",
        "sdk_version": PLUGIN_SDK_VERSION,
        "id": clean_id,
        "name": clean_id.replace("_", " ").title(),
        "version": "0.1.0",
        "author": "Local plugin author",
        "description": "Describe what this plugin adds to SpriteForge.",
        "tags": ["local"],
        "entrypoint": f"{clean_id}.py",
        "hooks": ["filter_prompt"],
        "enabled": True,
    }
    python_template = f'''"""SpriteForge plugin scaffold: {clean_id}."""


def filter_prompt(prompt, **kwargs):
    """Return a modified prompt string before generation."""
    return prompt


def on_qa_check(sprite_dir=None, report=None, **kwargs):
    """Observe QA reports without mutating project files by default."""
    return None
'''
    return {
        "schema": "spriteforge.plugin_scaffold.v1",
        "contract": plugin_sdk_contract(),
        "manifest": manifest,
        "files": {
            PLUGIN_MANIFEST: json.dumps(manifest, indent=2),
            manifest["entrypoint"]: python_template,
        },
    }


def _text(value: Any, fallback: str = "") -> str:
    text = str(value or "").strip()
    return text or fallback


def _tags(value: Any) -> List[str]:
    if not isinstance(value, list):
        return []
    tags: List[str] = []
    for item in value:
        tag = _text(item)
        if tag and tag not in tags:
            tags.append(tag[:32])
    return tags[:8]


def _version_tuple(value: Any) -> tuple[int, int, int]:
    text = _text(value, "0.0.0")
    parts = []
    for part in text.split(".")[:3]:
        digits = "".join(ch for ch in part if ch.isdigit())
        parts.append(int(digits or 0))
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts)  # type: ignore[return-value]


def plugin_compatibility(sdk_version: Any, host_version: str = PLUGIN_SDK_VERSION) -> Dict[str, Any]:
    plugin_version = _text(sdk_version, host_version)
    plugin_tuple = _version_tuple(plugin_version)
    host_tuple = _version_tuple(host_version)
    compatible = plugin_tuple[0] == host_tuple[0] and plugin_tuple <= host_tuple
    if compatible:
        status = "compatible"
        reason = f"Plugin SDK {plugin_version} is compatible with host SDK {host_version}."
    elif plugin_tuple[0] != host_tuple[0]:
        status = "major_mismatch"
        reason = f"Plugin SDK major version {plugin_tuple[0]} does not match host major version {host_tuple[0]}."
    else:
        status = "requires_newer_host"
        reason = f"Plugin SDK {plugin_version} requires a newer host than SDK {host_version}."
    return {
        "compatible": compatible,
        "status": status,
        "reason": reason,
        "host_sdk_version": host_version,
        "plugin_sdk_version": plugin_version,
    }


def normalize_plugin_manifest(raw: Dict[str, Any], path: Path) -> Dict[str, Any]:
    plugin_id = _text(raw.get("id"), path.parent.name if path.name == PLUGIN_MANIFEST else path.stem)
    hooks = raw.get("hooks") or []
    if isinstance(hooks, dict):
        hooks = list(hooks.keys())
    if not isinstance(hooks, list):
        hooks = []
    clean_hooks = []
    for hook in hooks:
        name = _text(hook)
        if name and name not in clean_hooks:
            clean_hooks.append(name)
    entrypoint = _text(raw.get("entrypoint"), path.parent.name + ".py" if path.name == PLUGIN_MANIFEST else path.name)
    sdk_version = _text(raw.get("sdk_version"), PLUGIN_SDK_VERSION)
    compatibility = plugin_compatibility(sdk_version)
    return {
        "schema": "spriteforge_plugin.v1",
        "sdk_version": sdk_version,
        "id": plugin_id[:80],
        "name": _text(raw.get("name"), plugin_id.replace("_", " ").title())[:120],
        "version": _text(raw.get("version"), "0.1.0")[:40],
        "author": _text(raw.get("author"), "Local plugin")[:80],
        "description": _text(raw.get("description"))[:240],
        "tags": _tags(raw.get("tags")),
        "entrypoint": entrypoint,
        "hooks": clean_hooks[:24],
        "known_hooks": [hook for hook in clean_hooks if hook in KNOWN_HOOKS],
        "unknown_hooks": [hook for hook in clean_hooks if hook not in KNOWN_HOOKS],
        "enabled": bool(raw.get("enabled", True)),
        "compatible": compatibility["compatible"],
        "compatibility": compatibility,
        "path": str(path).replace("\\", "/"),
    }


def validate_plugin_manifest(raw: Dict[str, Any], path: Path) -> Dict[str, Any]:
    """Return an author-facing validation report without executing plugin code."""
    metadata = normalize_plugin_manifest(raw if isinstance(raw, dict) else {}, path)
    required = plugin_sdk_contract()["manifest_required_fields"]
    missing = [
        field
        for field in required
        if field not in raw or raw.get(field) in (None, "", [])
    ]
    entrypoint_path = path.parent / str(metadata.get("entrypoint") or "")
    issues: List[Dict[str, Any]] = []
    if missing:
        issues.append({
            "code": "missing_required_fields",
            "severity": "error",
            "fields": missing,
            "message": "Manifest is missing required SDK fields.",
        })
    if metadata["unknown_hooks"]:
        issues.append({
            "code": "unknown_hooks",
            "severity": "warning",
            "hooks": metadata["unknown_hooks"],
            "message": "Unknown hooks will be ignored by this SpriteForge SDK.",
        })
    if not metadata["compatible"]:
        issues.append({
            "code": "sdk_incompatible",
            "severity": "error",
            "message": metadata["compatibility"]["reason"],
        })
    if metadata["entrypoint"] and not entrypoint_path.exists():
        issues.append({
            "code": "missing_entrypoint",
            "severity": "error",
            "path": str(entrypoint_path).replace("\\", "/"),
            "message": "Entrypoint file does not exist next to the plugin manifest.",
        })
    if metadata["entrypoint"] and Path(str(metadata["entrypoint"])).suffix != ".py":
        issues.append({
            "code": "entrypoint_not_python",
            "severity": "error",
            "entrypoint": metadata["entrypoint"],
            "message": "Plugin entrypoint must be a Python file.",
        })
    return {
        "schema": "spriteforge.plugin_manifest_validation.v1",
        "ok": not any(issue["severity"] == "error" for issue in issues),
        "metadata": metadata,
        "issues": issues,
        "known_hooks": sorted(KNOWN_HOOKS),
        "required_fields": required,
    }


def load_plugin_manifest(path: Path) -> Optional[Dict[str, Any]]:
    try:
        if path.name == PLUGIN_MANIFEST:
            raw = json.loads(path.read_text(encoding="utf-8"))
            return normalize_plugin_manifest(raw if isinstance(raw, dict) else {}, path)
        return normalize_plugin_manifest({}, path)
    except Exception as exc:
        logger.warning("Could not load plugin manifest %s: %s", path, exc)
        return None

class PluginManager:
    _plugins: List[Any] = []
    _loaded: bool = False

    @staticmethod
    def load_plugins() -> None:
        """Discover and load all Python plugins in the plugins/ directory."""
        if PluginManager._loaded:
            return
            
        PLUGINS_DIR.mkdir(parents=True, exist_ok=True)
        PluginManager._plugins = []
        
        # Look for any .py file directly in plugins/ plus manifest-backed plugin folders.
        candidates = list(PLUGINS_DIR.glob("*.py"))
        for manifest in PLUGINS_DIR.glob("*/" + PLUGIN_MANIFEST):
            metadata = load_plugin_manifest(manifest)
            if not metadata or not metadata.get("enabled", True) or not metadata.get("compatible", False):
                continue
            entrypoint = manifest.parent / str(metadata.get("entrypoint") or "")
            if entrypoint.exists() and entrypoint.suffix == ".py":
                candidates.append(entrypoint)
        seen = set()
        for p in candidates:
            if p.resolve() in seen:
                continue
            seen.add(p.resolve())
            try:
                module_name = f"plugins.{p.parent.name}.{p.stem}" if p.parent != PLUGINS_DIR else f"plugins.{p.stem}"
                spec = importlib.util.spec_from_file_location(module_name, str(p))
                if spec and spec.loader:
                    module = importlib.util.module_from_spec(spec)
                    sys.modules[module_name] = module
                    spec.loader.exec_module(module)
                    PluginManager._plugins.append(module)
                    print(f"Loaded plugin: {p.name}")
            except Exception as e:
                print(f"Error loading plugin {p.name}: {e}", file=sys.stderr)
                
        PluginManager._loaded = True

    @staticmethod
    def discover_plugins() -> List[Dict[str, Any]]:
        """Return plugin SDK manifests for local plugins without executing them."""
        PLUGINS_DIR.mkdir(parents=True, exist_ok=True)
        entries: List[Dict[str, Any]] = []
        seen_ids = set()
        for manifest in sorted(PLUGINS_DIR.glob("*/" + PLUGIN_MANIFEST)):
            metadata = load_plugin_manifest(manifest)
            if metadata:
                entries.append(metadata)
                seen_ids.add(metadata["id"])
        for py_file in sorted(PLUGINS_DIR.glob("*.py")):
            metadata = load_plugin_manifest(py_file)
            if metadata and metadata["id"] not in seen_ids:
                entries.append(metadata)
                seen_ids.add(metadata["id"])
        return entries

    @staticmethod
    def trigger_hook(hook_name: str, *args, **kwargs) -> None:
        """Trigger a specific hook on all loaded plugins."""
        PluginManager.load_plugins()
        for plugin in PluginManager._plugins:
            if hasattr(plugin, hook_name):
                try:
                    hook_fn = getattr(plugin, hook_name)
                    if callable(hook_fn):
                        hook_fn(*args, **kwargs)
                except Exception as e:
                    print(f"Error executing hook '{hook_name}' in plugin '{plugin.__name__}': {e}", file=sys.stderr)

    @staticmethod
    def filter_hook(hook_name: str, value: Any, *args, **kwargs) -> Any:
        """Trigger a filtering hook that takes a value and returns a modified value."""
        PluginManager.load_plugins()
        current_value = value
        for plugin in PluginManager._plugins:
            if hasattr(plugin, hook_name):
                try:
                    hook_fn = getattr(plugin, hook_name)
                    if callable(hook_fn):
                        current_value = hook_fn(current_value, *args, **kwargs)
                except Exception as e:
                    print(f"Error executing filter hook '{hook_name}' in plugin '{plugin.__name__}': {e}", file=sys.stderr)
        return current_value
