import os
import logging
import shutil
import subprocess
import sys
import urllib.request
import urllib.parse
from pathlib import Path
from typing import Dict, Any, List
from services.config_service import ConfigService
from spriteforge_utils import ROOT

logger = logging.getLogger(__name__)

class ComfyService:
    _running_cache = None
    _running_cache_time = 0.0
    _running_cache_ttl = 5.0

    @staticmethod
    def get_url() -> str:
        cfg = ConfigService.get_config()
        host = cfg.get("comfy", {}).get("host", "127.0.0.1")
        port = cfg.get("comfy", {}).get("port", 8188)
        return f"http://{host}:{port}"

    @staticmethod
    def is_running(timeout: float = 0.8, force_refresh: bool = False) -> bool:
        import time
        now = time.time()
        if (
            not force_refresh
            and ComfyService._running_cache is not None
            and now - ComfyService._running_cache_time < ComfyService._running_cache_ttl
        ):
            return bool(ComfyService._running_cache)

        url = ComfyService.get_url()
        try:
            with urllib.request.urlopen(url.rstrip("/") + "/system_stats", timeout=timeout) as r:
                res = 200 <= getattr(r, "status", 200) < 500
        except Exception as exc:
            logger.debug("ComfyUI health check failed for %s: %s", url, exc)
            res = False
        ComfyService._running_cache = res
        ComfyService._running_cache_time = now
        return res

    _gpu_info_cache = None
    _gpu_info_cache_time = 0.0
    _gpu_info_cache_ttl = 60.0

    @staticmethod
    def _cache_meta(cached_at: float, ttl: float, from_cache: bool) -> Dict[str, Any]:
        import time
        age = max(0.0, time.time() - float(cached_at or 0.0)) if cached_at else 0.0
        return {"from_cache": from_cache, "age_seconds": round(age, 3), "ttl_seconds": ttl}

    @staticmethod
    def get_gpu_info(force_refresh: bool = False) -> Dict[str, Any]:
        import time
        now = time.time()
        if not force_refresh and ComfyService._gpu_info_cache is not None and now - ComfyService._gpu_info_cache_time < ComfyService._gpu_info_cache_ttl:
            return {**ComfyService._gpu_info_cache, "_cache": ComfyService._cache_meta(ComfyService._gpu_info_cache_time, ComfyService._gpu_info_cache_ttl, True)}

        exe = shutil.which("nvidia-smi")
        if not exe:
            res = {"ok": False, "label": "GPU unknown", "detail": "nvidia-smi not found", "vram_gb": None}
            ComfyService._gpu_info_cache = res
            ComfyService._gpu_info_cache_time = now
            return {**res, "_cache": ComfyService._cache_meta(now, ComfyService._gpu_info_cache_ttl, False)}
        try:
            p = subprocess.run([exe, "--query-gpu=name,memory.total,memory.free,driver_version", "--format=csv,noheader"], capture_output=True, text=True, timeout=10)
            if p.returncode != 0:
                res = {"ok": False, "label": "GPU check failed", "detail": p.stderr.strip(), "vram_gb": None}
                ComfyService._gpu_info_cache = res
                ComfyService._gpu_info_cache_time = now
                return {**res, "_cache": ComfyService._cache_meta(now, ComfyService._gpu_info_cache_ttl, False)}
            line = p.stdout.strip().splitlines()[0] if p.stdout.strip() else ""
            parts = [p.strip() for p in line.split(",")]
            total_mb = None
            if len(parts) >= 2:
                digits = "".join(ch for ch in parts[1] if ch.isdigit())
                if digits:
                    total_mb = int(digits)
            res = {
                "ok": True,
                "label": parts[0] if parts else "NVIDIA GPU",
                "memory_total": parts[1] if len(parts) > 1 else "",
                "memory_free": parts[2] if len(parts) > 2 else "",
                "driver": parts[3] if len(parts) > 3 else "",
                "vram_gb": round(total_mb / 1024, 1) if total_mb else None,
                "detail": line,
            }
            ComfyService._gpu_info_cache = res
            ComfyService._gpu_info_cache_time = now
            return {**res, "_cache": ComfyService._cache_meta(now, ComfyService._gpu_info_cache_ttl, False)}
        except Exception as exc:
            res = {"ok": False, "label": "GPU check failed", "detail": str(exc), "vram_gb": None}
            ComfyService._gpu_info_cache = res
            ComfyService._gpu_info_cache_time = now
            return {**res, "_cache": ComfyService._cache_meta(now, ComfyService._gpu_info_cache_ttl, False)}

    @staticmethod
    def reset_caches() -> None:
        ComfyService._running_cache = None
        ComfyService._running_cache_time = 0.0
        ComfyService._gpu_info_cache = None
        ComfyService._gpu_info_cache_time = 0.0

    @staticmethod
    def launch() -> bool:
        # Resolve python executable inside venv if possible
        if os.name == "nt":
            py = ROOT / ".venv" / "Scripts" / "python.exe"
        else:
            py = ROOT / ".venv" / "bin" / "python"
        py_exe = str(py if py.exists() else Path(sys.executable))
        
        cmd = [py_exe, "spriteforge_unified.py", "launch-comfy"]
        try:
            kwargs: Dict[str, Any] = {"cwd": str(ROOT)}
            if os.name == "nt":
                kwargs["creationflags"] = getattr(subprocess, "CREATE_NEW_CONSOLE", 0)
            subprocess.Popen(cmd, **kwargs)
            return True
        except Exception as exc:
            logger.warning("Could not launch ComfyUI via %s: %s", cmd, exc)
            return False

    @staticmethod
    def watch_websocket(job: Dict[str, Any], lock: Any) -> None:
        """Bridge ComfyUI websocket progress into the active job when available."""
        import json
        import time
        import uuid
        prompt_id = str((job.get("metadata") or {}).get("comfy_prompt_id") or "")
        if not prompt_id:
            return
        try:
            import websocket  # type: ignore
            from services.generation_intelligence import apply_comfy_ws_message
        except Exception as exc:
            logger.debug("ComfyUI websocket bridge import failed: %s", exc)
            with lock:
                job.setdefault("logs", []).append(f"[{time.strftime('%H:%M:%S')}] ComfyUI websocket bridge unavailable; install websocket-client for exact WAN progress.")
            return

        url = ComfyService.get_url()
        parsed = urllib.parse.urlparse(url)
        scheme = "wss" if parsed.scheme == "https" else "ws"
        client_id = str(job.get("id") or uuid.uuid4())
        ws_url = f"{scheme}://{parsed.netloc}/ws?clientId={urllib.parse.quote(client_id)}"
        try:
            ws = websocket.create_connection(ws_url, timeout=3)
            with lock:
                job["progress_mode"] = "comfy_ws"
                job.setdefault("metadata", {})["comfy_ws_bridge"] = "connected"
            while True:
                with lock:
                    if job.get("phase") != "running":
                        break
                raw = ws.recv()
                try:
                    message = json.loads(raw)
                except Exception as exc:
                    logger.debug("Ignoring malformed ComfyUI websocket message: %s", exc)
                    continue
                with lock:
                    apply_comfy_ws_message(job, message)
                    done = job.get("stage") in {"complete", "failed", "cancelled"}
                if done:
                    break
        except Exception as exc:
            with lock:
                job.setdefault("metadata", {})["comfy_ws_bridge"] = "error"
                job.setdefault("logs", []).append(f"[{time.strftime('%H:%M:%S')}] ComfyUI websocket bridge stopped: {exc}")
        finally:
            try:
                ws.close()  # type: ignore[name-defined]
            except Exception as exc:
                logger.debug("Could not close ComfyUI websocket connection: %s", exc)
