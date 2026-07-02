import shutil
from pathlib import Path
from typing import Dict, Any, List
from services.config_service import ConfigService, load_json

ROOT = Path(__file__).resolve().parent.parent

class ModelService:
    @staticmethod
    def get_manifest_status(manifest_rel: str) -> Dict[str, Any]:
        p = Path(manifest_rel)
        if not p.is_absolute():
            p = ROOT / p
        manifest = load_json(p, {}) or {}
        comfy_dir = ConfigService.get_path("paths.comfyui_dir")
        files = []
        for item in manifest.get("files", []):
            dest = comfy_dir / "models" / str(item.get("dest_subdir", "")) / str(item.get("filename", ""))
            # Validate that file exists and is not a corrupted small stub (must be > 10 MB)
            exists = dest.exists() and dest.stat().st_size > 10 * 1024 * 1024
            files.append({
                "filename": item.get("filename"),
                "exists": exists,
                "size_bytes": dest.stat().st_size if dest.exists() else 0,
                "expected_size": item.get("approx_size", "unknown"),
                "dest_subdir": item.get("dest_subdir", "")
            })
        present = sum(1 for f in files if f["exists"])
        total = len(files)
        missing_files = [f["filename"] for f in files if not f["exists"]]
        return {
            "manifest": str(p.relative_to(ROOT)) if p.is_relative_to(ROOT) else str(p),
            "label": manifest.get("label", p.stem),
            "present": present,
            "total": total,
            "ok": total > 0 and present == total,
            "files": files,
            "missing_files": missing_files
        }

    @staticmethod
    def get_tiers_status() -> Dict[str, Any]:
        cfg = ConfigService.get_config()
        rows = {}
        for key, tier in cfg.get("model_tiers", {}).items():
            mf = tier.get("manifest")
            if mf:
                st = ModelService.get_manifest_status(str(mf))
                st["short_label"] = tier.get("short_label") or tier.get("label") or key
                st["local_ok"] = bool(tier.get("local_ok", True))
                st["cloud_only"] = False
                rows[key] = st
            else:
                rows[key] = {
                    "short_label": tier.get("short_label") or tier.get("label") or key,
                    "present": 0,
                    "total": 0,
                    "ok": False,
                    "cloud_only": True,
                    "local_ok": False,
                    "files": []
                }
        return rows

    _summary_cache = None
    _summary_cache_time = 0.0
    _disk_cache = None
    _disk_cache_time = 0.0

    @staticmethod
    def get_summary() -> Dict[str, Any]:
        import sys
        import time
        is_testing = "pytest" in sys.modules or "unittest" in sys.modules
        now = time.time()
        if not is_testing and ModelService._summary_cache is not None and now - ModelService._summary_cache_time < 10.0:
            return ModelService._summary_cache

        cfg = ConfigService.get_config()
        tiers = ModelService.get_tiers_status()
        safe_key = str(cfg.get("default_model_tier") or "wan21_safe")
        safe = tiers.get(safe_key) or tiers.get("wan21_safe") or {}

        advanced_rows = [
            row for key, row in tiers.items()
            if not row.get("cloud_only") and ("wan22" in key or "advanced" in key)
        ]
        advanced_present = sum(int(row.get("present", 0)) for row in advanced_rows)
        advanced_total = sum(int(row.get("total", 0)) for row in advanced_rows)

        res = {
            "ok": bool(safe.get("ok")),
            "present": int(safe.get("present", 0)),
            "total": int(safe.get("total", 0)),
            "label": safe.get("label", safe_key),
            "safe_key": safe_key,
            "advanced_present": advanced_present,
            "advanced_total": advanced_total,
            "advanced_ok": advanced_total > 0 and advanced_present == advanced_total,
            "tiers": tiers,
        }
        ModelService._summary_cache = res
        ModelService._summary_cache_time = now
        return res

    @staticmethod
    def get_disk_summary() -> Dict[str, Any]:
        import sys
        import time
        is_testing = "pytest" in sys.modules or "unittest" in sys.modules
        now = time.time()
        if not is_testing and ModelService._disk_cache is not None and now - ModelService._disk_cache_time < 15.0:
            return ModelService._disk_cache

        total, used, free = shutil.disk_usage(ROOT)
        free_gb = round(free / (1024**3), 1)
        res = {
            "ok": free_gb >= 25.0,
            "free_gb": free_gb,
            "total_gb": round(total / (1024**3), 1),
            "used_gb": round(used / (1024**3), 1),
        }
        ModelService._disk_cache = res
        ModelService._disk_cache_time = now
        return res

    @staticmethod
    def get_addons_status() -> Dict[str, Any]:
        registry_path = ROOT / "config" / "model_addons.json"
        registry = load_json(registry_path, {"schema": "spriteforge_model_addons_v1", "addons": []}) or {}
        comfy_dir = ConfigService.get_path("paths.comfyui_dir")
        models_root = comfy_dir / "models"
        workflows_root = ROOT / "workflows"
        addons = []

        def check_dest(dest_subdir: str, filename: str) -> Path:
            if dest_subdir == "workflows":
                return workflows_root / filename
            return models_root / dest_subdir / filename

        for raw_addon in registry.get("addons", []):
            addon = dict(raw_addon)
            checks = []
            found_files = []
            required_total = 0
            required_present = 0

            for file_item in addon.get("files", []):
                filename = str(file_item.get("filename", "")).strip()
                if not filename:
                    continue
                dest_subdir = str(file_item.get("dest_subdir") or addon.get("dest_subdir") or "loras")
                dest = check_dest(dest_subdir, filename)
                is_optional = bool(file_item.get("optional"))
                min_size = 1024 if dest.suffix.lower() == ".json" else 10 * 1024 * 1024
                exists = dest.exists() and dest.is_file() and dest.stat().st_size >= min_size
                if not is_optional:
                    required_total += 1
                    required_present += 1 if exists else 0
                if exists:
                    found_files.append(str(dest))
                checks.append({
                    "filename": filename,
                    "dest_subdir": dest_subdir,
                    "path": str(dest),
                    "exists": exists,
                    "optional": is_optional,
                    "size_bytes": dest.stat().st_size if dest.exists() else 0,
                    "expected_size": file_item.get("approx_size", "unknown"),
                })

            for pattern in addon.get("file_patterns", []):
                dest_subdir = str(addon.get("dest_subdir") or "loras")
                search_dir = models_root / dest_subdir
                matches = []
                if search_dir.exists():
                    matches = [
                        match for match in search_dir.glob(str(pattern))
                        if match.is_file() and match.stat().st_size >= 10 * 1024 * 1024
                    ]
                exists = bool(matches)
                required_total += 1
                required_present += 1 if exists else 0
                found_files.extend(str(match) for match in matches[:4])
                checks.append({
                    "pattern": str(pattern),
                    "dest_subdir": dest_subdir,
                    "path": str(search_dir / str(pattern)),
                    "exists": exists,
                    "optional": False,
                    "matches": [str(match) for match in matches[:8]],
                })

            addon["present"] = required_present
            addon["total"] = required_total
            addon["installed"] = required_total > 0 and required_present == required_total
            addon["partial"] = required_present > 0 and required_present < required_total
            addon["checks"] = checks
            addon["found_files"] = found_files
            addons.append(addon)

        return {
            "ok": True,
            "schema": registry.get("schema", "spriteforge_model_addons_v1"),
            "addons": addons,
            "comfy_models_dir": str(models_root),
        }
