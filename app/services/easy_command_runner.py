#!/usr/bin/env python3
"""CommandRunner for Easy Mode — subprocess pipeline execution with progress."""
from __future__ import annotations

import subprocess
import threading
from pathlib import Path
from typing import Callable, List, Optional, Sequence, Tuple

ROOT = Path(__file__).resolve().parent.parent


class CommandRunner:
    def __init__(self, app):
        self.app = app
        self.current_proc: Optional[subprocess.Popen] = None
        self.lock = threading.Lock()

    def busy(self) -> bool:
        with self.lock:
            return self.current_proc is not None

    def run(self, title: str, cmd: Sequence[str], on_done: Optional[Callable[[int], None]] = None) -> None:
        self.run_sequence(title, [(title, list(cmd), True)], on_done=on_done)

    def run_sequence(self, title: str, steps: Sequence[Tuple[str, Sequence[str], bool]],
                     on_done: Optional[Callable[[int], None]] = None) -> None:
        if self.busy():
            from tkinter import messagebox
            ans = messagebox.askyesno("SpriteForge is busy", f"A task is already running.\n\nWould you like to queue '{title}' to run later?")
            if ans:
                for step_title, cmd, _ in steps:
                    action = "custom"; direction = "none"
                    for i, arg in enumerate(cmd):
                        if arg == "--action" and i + 1 < len(cmd): action = cmd[i + 1]
                        elif arg == "--direction" and i + 1 < len(cmd): direction = cmd[i + 1]
                    self.app.enqueue_job(step_title, list(cmd), action=action, direction=direction)
            return

        self.app.progress_bar["value"] = 0
        self.app.progress_bar["maximum"] = 100

        def worker():
            final_code = 0
            self.app.log(f"\n=== {title} ===\n")
            for step_title, cmd, stop_on_fail in steps:
                self.app.set_busy(True, step_title)
                self.app.log(f"\n--- {step_title} ---\n")
                self.app.log("Command: " + subprocess.list2cmdline(list(cmd)) + "\n")

                missing_arg = False
                for arg in cmd:
                    if "01_DROP_VIDEOS_HERE" in str(arg):
                        if not Path(arg).exists():
                            missing_arg = True; self.app.log(f"ERROR: Dropped video file not found: {Path(arg)}\n"); rc = 1; break
                if missing_arg:
                    final_code = rc; self.app.log(f"Step failed (missing file): {step_title}\n")
                    if stop_on_fail: break
                    continue

                try:
                    proc = subprocess.Popen(list(cmd), cwd=str(ROOT), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                            text=True, encoding="utf-8", errors="replace", bufsize=1)
                    with self.lock: self.current_proc = proc
                    assert proc.stdout is not None
                    for line in proc.stdout: self.app.log(line)
                    rc = proc.wait()
                except Exception as exc:
                    rc = 1; self.app.log(f"ERROR: {exc}\n")
                finally:
                    with self.lock: self.current_proc = None
                final_code = rc
                if rc != 0:
                    self.app.log(f"Step failed with exit code {rc}: {step_title}\n")
                    if stop_on_fail: break
                else:
                    self.app.log(f"Finished: {step_title}\n")

            self.app.after(0, lambda: self.app.set_busy(False, "Ready"))
            if on_done: self.app.after(0, lambda: on_done(final_code))
            self.app.after(0, self.app.refresh_status)
            self.app.after(0, self.app.refresh_outputs)

        threading.Thread(target=worker, daemon=True).start()

    def terminate(self) -> None:
        with self.lock:
            proc = self.current_proc
        if proc is None: return
        try:
            proc.terminate()
            self.app.log("\nStop requested. The current process was asked to terminate.\n")
        except Exception as exc:
            self.app.log(f"\nCould not terminate process: {exc}\n")