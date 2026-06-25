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

    @staticmethod
    def get_summary() -> Dict[str, Any]:
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

        return {
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

    @staticmethod
    def get_disk_summary() -> Dict[str, Any]:
        total, used, free = shutil.disk_usage(ROOT)
        free_gb = round(free / (1024**3), 1)
        return {
            "ok": free_gb >= 25.0,
            "free_gb": free_gb,
            "total_gb": round(total / (1024**3), 1),
            "used_gb": round(used / (1024**3), 1),
        }
