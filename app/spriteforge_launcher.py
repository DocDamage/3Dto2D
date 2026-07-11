import sys
import os
import subprocess
import json
from pathlib import Path
import datetime as dt
import urllib.request

from spriteforge_utils import ROOT


def dependency_requirements_file() -> Path:
    locked = ROOT.parent / "requirements-lock.txt"
    return locked if locked.exists() else ROOT / "requirements.txt"

def get_log_path() -> Path:
    logs_dir = ROOT / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    today = dt.date.today().strftime("%Y%m%d")
    return logs_dir / f"launcher_v12_{today}.log"

def log(msg: str):
    print(msg)
    try:
        log_path = get_log_path()
        with log_path.open("a", encoding="utf-8") as f:
            f.write(f"{dt.datetime.now().isoformat()} - {msg}\n")
    except Exception:
        pass

def get_venv_python() -> Path:
    bundled = str(os.environ.get("SPRITEFORGE_RUNTIME_PYTHON") or "").strip()
    if bundled and Path(bundled).is_file():
        return Path(bundled)
    if os.name == "nt":
        return ROOT / ".venv" / "Scripts" / "python.exe"
    else:
        return ROOT / ".venv" / "bin" / "python"

def _load_comfy_config() -> tuple[Path, str, int]:
    config_path = ROOT / "config" / "spriteforge_config.json"
    data = json.loads(config_path.read_text(encoding="utf-8"))
    comfy_override = str(os.environ.get("SPRITEFORGE_COMFYUI_DIR") or "").strip()
    comfy_dir = Path(comfy_override or str(data.get("paths", {}).get("comfyui_dir", "vendor/ComfyUI")))
    if not comfy_dir.is_absolute():
        comfy_dir = ROOT / comfy_dir
    comfy = data.get("comfy", {})
    host = str(comfy.get("host", "127.0.0.1"))
    port = int(comfy.get("port", 8188))
    return comfy_dir, host, port

def _comfy_is_running(host: str, port: int) -> bool:
    url = f"http://{host}:{port}/system_stats"
    try:
        with urllib.request.urlopen(url, timeout=0.8) as response:
            return 200 <= getattr(response, "status", 200) < 500
    except Exception:
        return False

def launch_comfy_for_default_start(venv_python: Path) -> bool:
    try:
        comfy_dir, host, port = _load_comfy_config()
    except Exception as exc:
        log(f"ComfyUI autostart skipped: could not read config ({exc}).")
        return False

    if _comfy_is_running(host, port):
        log(f"ComfyUI already running at http://{host}:{port}")
        return True
    if not comfy_dir.exists():
        log(f"ComfyUI autostart skipped: not installed at {comfy_dir}")
        return False

    cmd = [str(venv_python), "spriteforge_unified.py", "launch-comfy"]
    try:
        kwargs = {"cwd": str(ROOT)}
        if os.name == "nt":
            kwargs["creationflags"] = getattr(subprocess, "CREATE_NEW_CONSOLE", 0)
        subprocess.Popen(cmd, **kwargs)
        log(f"Started ComfyUI in the background: http://{host}:{port}")
        return True
    except Exception as exc:
        log(f"ComfyUI autostart failed: {exc}")
        return False

def main():
    log(f"==== SpriteForge Launcher starting with args: {sys.argv[1:]} ====")
    
    # 1. Setup Venv if needed
    venv_python = get_venv_python()
    if not venv_python.exists():
        log("First run: creating SpriteForge local Python environment...")
        log("This only affects this SpriteForge folder.")
        try:
            (ROOT / ".python_version").write_text("3.12", encoding="utf-8")
        except Exception:
            pass
        try:
            subprocess.run([sys.executable, "-m", "venv", str(ROOT / ".venv")], check=True)
            log("Venv created successfully.")
        except Exception as e:
            log(f"ERROR: Failed to create virtual environment: {e}")
            sys.exit(1)
            
    # 2. Check if pip and requirements are installed
    deps_flag = ROOT / ".deps_installed_v12"
    bundled_runtime = bool(str(os.environ.get("SPRITEFORGE_RUNTIME_PYTHON") or "").strip())
    if not deps_flag.exists() and not bundled_runtime:
        log("Installing/Upgrading requirements...")
        try:
            venv_python = get_venv_python()
            # Upgrade pip
            subprocess.run([str(venv_python), "-m", "pip", "install", "--upgrade", "pip"], check=True)
            # Install requirements
            subprocess.run([str(venv_python), "-m", "pip", "install", "-r", str(dependency_requirements_file())], check=True)
            deps_flag.write_text("ok", encoding="utf-8")
            log("Dependencies installed successfully.")
        except Exception as e:
            log(f"ERROR: Failed to install Python dependencies: {e}")
            sys.exit(1)
            
    # 3. Route arguments
    venv_python = get_venv_python()
    args = sys.argv[1:]
    mode = args[0] if args else ""
    
    cmd = []
    if mode == "--install":
        cmd = [str(venv_python), "spriteforge_unified.py", "install-all", "--model-tier", "safe"]
    elif mode == "--install-advanced":
        cmd = [str(venv_python), "spriteforge_unified.py", "install-all", "--model-tier", "advanced"]
    elif mode == "--download-wan22":
        cmd = [str(venv_python), "spriteforge_unified.py", "download-model-tier", "--tier", "wan22_only"]
    elif mode == "--classic":
        cmd = [str(venv_python), "spriteforge_easy.py"]
    elif mode == "--wizard":
        cmd = [str(venv_python), "spriteforge_first_run.py"]
    elif mode == "--demo":
        cmd = [str(venv_python), "spriteforge_demo.py"]
    elif mode == "--support":
        cmd = [str(venv_python), "spriteforge_support_bundle.py"]
    else:
        # Default: Web UI first, fallback to Classic
        cmd = [str(venv_python), "spriteforge_web.py"]
        launch_comfy_for_default_start(venv_python)
        log("Launching SpriteForge Studio Web UI...")
        try:
            res = subprocess.run(cmd, cwd=str(ROOT))
            if res.returncode != 0:
                log("Web UI failed or exited. Falling back to Classic Mode...")
                res2 = subprocess.run([str(venv_python), "spriteforge_easy.py"], cwd=str(ROOT))
                sys.exit(res2.returncode)
            sys.exit(res.returncode)
        except Exception as e:
            log(f"Failed to run Web UI ({e}). Falling back to Classic Mode...")
            res2 = subprocess.run([str(venv_python), "spriteforge_easy.py"], cwd=str(ROOT))
            sys.exit(res2.returncode)
            
    log(f"Running command: {cmd}")
    try:
        res = subprocess.run(cmd, cwd=str(ROOT))
        sys.exit(res.returncode)
    except Exception as e:
        log(f"ERROR executing command: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
