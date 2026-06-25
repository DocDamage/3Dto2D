import sys
import os
import subprocess
from pathlib import Path
import datetime as dt

ROOT = Path(__file__).resolve().parent

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
    if os.name == "nt":
        return ROOT / ".venv" / "Scripts" / "python.exe"
    else:
        return ROOT / ".venv" / "bin" / "python"

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
    if not deps_flag.exists():
        log("Installing/Upgrading requirements...")
        try:
            venv_python = get_venv_python()
            # Upgrade pip
            subprocess.run([str(venv_python), "-m", "pip", "install", "--upgrade", "pip"], check=True)
            # Install requirements
            subprocess.run([str(venv_python), "-m", "pip", "install", "-r", str(ROOT / "requirements.txt")], check=True)
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
