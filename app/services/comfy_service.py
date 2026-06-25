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

    @staticmethod
    def get_gpu_info() -> Dict[str, Any]:
        exe = shutil.which("nvidia-smi")
        if not exe:
            return {"ok": False, "label": "GPU unknown", "detail": "nvidia-smi not found", "vram_gb": None}
        try:
            p = subprocess.run([exe, "--query-gpu=name,memory.total,memory.free,driver_version", "--format=csv,noheader"], capture_output=True, text=True, timeout=10)
            if p.returncode != 0:
                return {"ok": False, "label": "GPU check failed", "detail": p.stderr.strip(), "vram_gb": None}
            line = p.stdout.strip().splitlines()[0] if p.stdout.strip() else ""
            parts = [p.strip() for p in line.split(",")]
            total_mb = None
            if len(parts) >= 2:
                digits = "".join(ch for ch in parts[1] if ch.isdigit())
                if digits:
                    total_mb = int(digits)
            return {
                "ok": True,
                "label": parts[0] if parts else "NVIDIA GPU",
                "memory_total": parts[1] if len(parts) > 1 else "",
                "memory_free": parts[2] if len(parts) > 2 else "",
                "driver": parts[3] if len(parts) > 3 else "",
                "vram_gb": round(total_mb / 1024, 1) if total_mb else None,
                "detail": line,
            }
        except Exception as exc:
            return {"ok": False, "label": "GPU check failed", "detail": str(exc), "vram_gb": None}

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
