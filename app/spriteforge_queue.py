#!/usr/bin/env python3
"""Persistent SpriteForge job queue.

This is for production batches where users need to generate many actions/directions
without babysitting the command line. It writes a queue JSON, records status after
each command, and can resume after failure/interruption.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

ROOT = Path(__file__).resolve().parent
JOBS = ROOT / "output" / "jobs"


from spriteforge_utils import load_json, save_json, app_python

write_json = save_json


def split_csv(value: str) -> List[str]:
    return [x.strip() for x in (value or "").split(",") if x.strip()]


def shell_join(cmd: Sequence[str]) -> str:
    return subprocess.list2cmdline(list(map(str, cmd))) if os.name == "nt" else " ".join([f"'{x}'" if " " in str(x) else str(x) for x in cmd])


def project_root(path: Path) -> Path:
    return path if path.is_dir() else path.parent


def load_project(path: Path) -> Dict[str, Any]:
    if path.is_dir():
        path = path / "spriteforge_project.json"
    return json.loads(path.read_text(encoding="utf-8"))


def queue_path_for(name: str) -> Path:
    JOBS.mkdir(parents=True, exist_ok=True)
    return JOBS / f"{name}_{time.strftime('%Y%m%d_%H%M%S')}_queue.json"


def build_generate_command(project: Dict[str, Any], action: str, direction: str, args: argparse.Namespace) -> List[str]:
    frames = int(project.get("frames_by_action", {}).get(action, args.frames or 24))
    cmd = [
        app_python(), "spriteforge_unified.py", "generate-sprite",
        "--start-comfy",
        "--tier", args.tier,
        "--profile", args.profile,
        "--action", action,
        "--direction", direction,
        "--character", str(project.get("character") or project.get("description") or args.character),
        "--style", str(project.get("style") or args.style),
        "--background", str(project.get("background") or args.background),
        "--frames", str(frames),
        "--video-fps", str(project.get("fps", args.fps)),
        "--quality-check",
    ]
    if args.seed is not None:
        cmd += ["--seed", str(args.seed)]
    return cmd


def cmd_create(args: argparse.Namespace) -> None:
    if args.project:
        p = Path(args.project)
        if not p.is_absolute():
            p = ROOT / p
        project = load_project(p)
        name = str(project.get("name") or p.stem)
        actions = split_csv(args.actions) if args.actions else list(project.get("actions", []))
        directions = split_csv(args.directions) if args.directions else list(project.get("directions", []))
    else:
        name = args.name
        project = {"name": name, "character": args.character, "style": args.style, "background": args.background, "fps": args.fps, "frames_by_action": {}}
        actions = split_csv(args.actions)
        directions = split_csv(args.directions)
    if not actions or not directions:
        raise SystemExit("No actions/directions provided.")
    jobs = []
    idx = 1
    for action in actions:
        for direction in directions:
            jobs.append({
                "id": f"{idx:03d}_{action}_{direction}",
                "action": action,
                "direction": direction,
                "status": "pending",
                "created_at": dt.datetime.now().isoformat(timespec="seconds"),
                "started_at": None,
                "finished_at": None,
                "exit_code": None,
                "command": build_generate_command(project, action, direction, args),
                "log": None,
            })
            idx += 1
    queue = {"schema": "spriteforge_queue_v12", "name": name, "created_at": dt.datetime.now().isoformat(timespec="seconds"), "jobs": jobs}
    out = Path(args.output) if args.output else queue_path_for(name)
    if not out.is_absolute():
        out = ROOT / out
    write_json(out, queue)
    bat = out.with_suffix(".bat")
    lines = ["@echo off", "cd /d \"%~dp0\\..\\..\"", f"\"{app_python()}\" spriteforge_queue.py run --queue \"{out}\"", "pause", ""]
    bat.write_text("\n".join(lines), encoding="utf-8")
    print(f"Queue: {out}")
    print(f"Runner: {bat}")


def load_queue(path: Path) -> Dict[str, Any]:
    data = load_json(path, None)
    if not data or "jobs" not in data:
        raise SystemExit(f"Invalid queue: {path}")
    return data


def save_queue(path: Path, data: Dict[str, Any]) -> None:
    write_json(path, data)


def cmd_status(args: argparse.Namespace) -> None:
    q = Path(args.queue)
    if not q.is_absolute():
        q = ROOT / q
    data = load_queue(q)
    counts: Dict[str, int] = {}
    for job in data["jobs"]:
        counts[job.get("status", "unknown")] = counts.get(job.get("status", "unknown"), 0) + 1
    print(f"Queue: {q}")
    print("Status:", ", ".join(f"{k}={v}" for k, v in sorted(counts.items())))
    for job in data["jobs"]:
        print(f"{job['id']}: {job.get('status')} exit={job.get('exit_code')}")


def cmd_run(args: argparse.Namespace) -> None:
    qpath = Path(args.queue)
    if not qpath.is_absolute():
        qpath = ROOT / qpath
    data = load_queue(qpath)
    logs = qpath.parent / (qpath.stem + "_logs")
    logs.mkdir(parents=True, exist_ok=True)
    for job in data["jobs"]:
        if job.get("status") == "done" and not args.rerun_done:
            continue
        if job.get("status") == "failed" and not args.retry_failed:
            continue
        log = logs / f"{job['id']}.log"
        job["status"] = "running"
        job["started_at"] = dt.datetime.now().isoformat(timespec="seconds")
        job["log"] = str(log)
        save_queue(qpath, data)
        print(f"\n=== Running {job['id']} ===")
        print(shell_join(job["command"]))
        code = 1
        try:
            with log.open("w", encoding="utf-8", errors="replace") as fp:
                proc = subprocess.Popen(list(map(str, job["command"])), cwd=str(ROOT), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors="replace")
                assert proc.stdout is not None
                for line in proc.stdout:
                    print(line, end="")
                    fp.write(line)
                    fp.flush()
                code = proc.wait()
        except KeyboardInterrupt:
            job["status"] = "interrupted"
            job["finished_at"] = dt.datetime.now().isoformat(timespec="seconds")
            job["exit_code"] = None
            save_queue(qpath, data)
            raise
        except Exception as exc:
            with log.open("a", encoding="utf-8", errors="replace") as fp:
                fp.write("ERROR: " + str(exc) + "\n")
            code = 1
        job["finished_at"] = dt.datetime.now().isoformat(timespec="seconds")
        job["exit_code"] = code
        job["status"] = "done" if code == 0 else "failed"
        save_queue(qpath, data)
        if code != 0 and not args.continue_on_error:
            print(f"Job failed: {job['id']}")
            break
    cmd_status(argparse.Namespace(queue=str(qpath)))


def cmd_reset(args: argparse.Namespace) -> None:
    q = Path(args.queue)
    if not q.is_absolute():
        q = ROOT / q
    data = load_queue(q)
    for job in data["jobs"]:
        if args.only_failed and job.get("status") != "failed":
            continue
        job["status"] = "pending"
        job["started_at"] = None
        job["finished_at"] = None
        job["exit_code"] = None
    save_queue(q, data)
    print(f"Reset queue: {q}")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="SpriteForge persistent production queue")
    sub = p.add_subparsers(dest="command", required=True)
    s = sub.add_parser("create")
    s.add_argument("--project", default=None)
    s.add_argument("--name", default="character")
    s.add_argument("--character", default="single full body original game character, clean silhouette")
    s.add_argument("--style", default="clean 2D game sprite, crisp edges")
    s.add_argument("--background", default="plain bright green background")
    s.add_argument("--actions", default="idle,walk,run,attack_light,hurt")
    s.add_argument("--directions", default="right")
    s.add_argument("--tier", default="wan21_safe")
    s.add_argument("--profile", default="auto")
    s.add_argument("--fps", type=int, default=12)
    s.add_argument("--frames", type=int, default=None)
    s.add_argument("--seed", type=int, default=None)
    s.add_argument("--output", default=None)
    s.set_defaults(func=cmd_create)
    s = sub.add_parser("run")
    s.add_argument("--queue", required=True)
    s.add_argument("--retry-failed", action="store_true", default=True)
    s.add_argument("--rerun-done", action="store_true")
    s.add_argument("--continue-on-error", action="store_true")
    s.set_defaults(func=cmd_run)
    s = sub.add_parser("status")
    s.add_argument("--queue", required=True)
    s.set_defaults(func=cmd_status)
    s = sub.add_parser("reset")
    s.add_argument("--queue", required=True)
    s.add_argument("--only-failed", action="store_true")
    s.set_defaults(func=cmd_reset)
    return p


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        args.func(args)
        return 0
    except KeyboardInterrupt:
        print("Stopped.", file=sys.stderr)
        return 130
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
