import os
import shutil
import subprocess
import sys
import urllib.request
import urllib.parse
from pathlib import Path
from typing import Dict, Any, List
from services.config_service import ConfigService

ROOT = Path(__file__).resolve().parent.parent

class ComfyService:
    @staticmethod
    def get_url() -> str:
        cfg = ConfigService.get_config()
        host = cfg.get("comfy", {}).get("host", "127.0.0.1")
        port = cfg.get("comfy", {}).get("port", 8188)
        return f"http://{host}:{port}"

    @staticmethod
    def is_running(timeout: float = 0.8) -> bool:
        url = ComfyService.get_url()
        try:
            with urllib.request.urlopen(url.rstrip("/") + "/system_stats", timeout=timeout) as r:
                return 200 <= getattr(r, "status", 200) < 500
        except Exception:
            return False

    _gpu_info_cache = None
    _gpu_info_cache_time = 0.0

    @staticmethod
    def get_gpu_info() -> Dict[str, Any]:
        import sys
        import time
        is_testing = "pytest" in sys.modules or "unittest" in sys.modules
        now = time.time()
        if not is_testing and ComfyService._gpu_info_cache is not None and now - ComfyService._gpu_info_cache_time < 60.0:
            return ComfyService._gpu_info_cache

        exe = shutil.which("nvidia-smi")
        if not exe:
            res = {"ok": False, "label": "GPU unknown", "detail": "nvidia-smi not found", "vram_gb": None}
            ComfyService._gpu_info_cache = res
            ComfyService._gpu_info_cache_time = now
            return res
        try:
            p = subprocess.run([exe, "--query-gpu=name,memory.total,memory.free,driver_version", "--format=csv,noheader"], capture_output=True, text=True, timeout=10)
            if p.returncode != 0:
                res = {"ok": False, "label": "GPU check failed", "detail": p.stderr.strip(), "vram_gb": None}
                ComfyService._gpu_info_cache = res
                ComfyService._gpu_info_cache_time = now
                return res
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
            return res
        except Exception as exc:
            res = {"ok": False, "label": "GPU check failed", "detail": str(exc), "vram_gb": None}
            ComfyService._gpu_info_cache = res
            ComfyService._gpu_info_cache_time = now
            return res

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
        except Exception:
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
        except Exception:
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
                except Exception:
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
            except Exception:
                pass

