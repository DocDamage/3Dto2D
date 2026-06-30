#!/usr/bin/env python3
"""
SpriteForge Studio v12: Local Flask-based Web UI Server.
Modularized to split endpoints into clean routes under web_routes/.
"""
from __future__ import annotations

import argparse
import os
import socket
import sys
import threading
import webbrowser
from pathlib import Path
from typing import Optional, Sequence

from flask import Flask

from services.job_service import JobService
from web_helpers import ROOT, WEB, LOGS, OUTPUT, INPUT
from web_routes import routes_jobs, routes_projects, routes_sprites, routes_misc, routes_static

app = Flask(__name__)

# Register Blueprints
app.register_blueprint(routes_jobs)
app.register_blueprint(routes_projects)
app.register_blueprint(routes_sprites)
app.register_blueprint(routes_misc)
app.register_blueprint(routes_static)

def find_free_port(preferred: int) -> int:
    for port in [preferred, 8766, 8767, 8877, 8899, 0]:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            try:
                sock.bind(("127.0.0.1", port))
                return int(sock.getsockname()[1])
            except OSError:
                continue
    return preferred

def run_server(port: int, no_browser: bool = False) -> int:
    for folder in [LOGS, OUTPUT, INPUT, WEB]:
        folder.mkdir(parents=True, exist_ok=True)
    port = find_free_port(port)
    url = f"http://127.0.0.1:{port}/"
    print("SpriteForge Studio v12 Final Polish Edition (Flask Core)")
    print(f"Local UI: {url}")
    print("Close this window to stop the local UI server.")
    JobService.recover_interrupted_jobs()
    print("Startup: interrupted job recovery complete.")
    if not no_browser:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        # Disable Flask default CLI banner and run
        import logging
        log = logging.getLogger('werkzeug')
        log.setLevel(logging.ERROR)
        app.run(host="127.0.0.1", port=port, debug=False, threaded=True)
    except KeyboardInterrupt:
        print("\nStopping SpriteForge web UI.")
    return 0

def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="SpriteForge Studio v12 local web UI")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args(argv)
    if args.smoke:
        expected_files = [
            "index.html",
            "styles.css",
            "js/globals.js",
            "js/project.js",
            "js/gallery.js",
            "js/editor.js",
            "js/experiments.js",
            "js/qa.js",
            "js/app_status.js",
            "js/app_jobs.js",
            "js/app_main.js",
        ]
        missing = [str(WEB / name) for name in expected_files if not (WEB / name).exists()]
        if missing:
            print("Missing web assets:", missing)
            return 1
        print("SpriteForge v12 web UI smoke test passed.")
        return 0
    return run_server(args.port, args.no_browser)

if __name__ == "__main__":
    raise SystemExit(main())
