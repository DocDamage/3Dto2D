#!/usr/bin/env python3
"""Cloud job packager/runner scaffolding for SpriteForge Studio.

This does not store API keys and does not assume one cloud vendor. It creates a
portable job bundle that can be pushed to a GPU pod by SSH/SCP, or used as the
payload for a vendor-specific automation you add later.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
import zipfile
from pathlib import Path
from typing import Dict, List, Optional

ROOT = Path(__file__).resolve().parent


def copy_if(path: Optional[str], dest: Path) -> Optional[str]:
    if not path:
        return None
    p = Path(path).resolve()
    if not p.exists():
        raise FileNotFoundError(p)
    dest.mkdir(parents=True, exist_ok=True)
    if p.is_dir():
        out = dest / p.name
        if out.exists():
            shutil.rmtree(out)
        shutil.copytree(p, out)
    else:
        out = dest / p.name
        shutil.copy2(p, out)
    return str(out.name)


def zip_dir(src: Path, out_zip: Path) -> Path:
    out_zip.parent.mkdir(parents=True, exist_ok=True)
    if out_zip.exists():
        out_zip.unlink()
    with zipfile.ZipFile(out_zip, "w", zipfile.ZIP_DEFLATED) as z:
        for p in src.rglob("*"):
            z.write(p, p.relative_to(src.parent))
    return out_zip


def cloud_runner_script() -> str:
    return r'''#!/usr/bin/env python3
"""Run this inside a GPU cloud machine after installing ComfyUI/SpriteForge."""
from __future__ import annotations
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
JOB = json.loads((ROOT / "job_manifest.json").read_text(encoding="utf-8"))

# Edit this if your cloud layout is different.
SPRITEFORGE = Path(JOB.get("spriteforge_dir", "SpriteForge"))
if not SPRITEFORGE.exists():
    print("SpriteForge directory not found. Set spriteforge_dir in job_manifest.json or clone/upload SpriteForge Studio next to this job.")
    sys.exit(2)

cmd = [sys.executable, str(SPRITEFORGE / "spriteforge_unified.py"), "generate-sprite", "--start-comfy"]
cmd += ["--mode", JOB.get("mode", "t2v")]
cmd += ["--profile", JOB.get("profile", "quality_local")]
cmd += ["--prompt", JOB.get("prompt", "single full body character idle cycle, locked camera, green background")]
if JOB.get("negative"):
    cmd += ["--negative", JOB["negative"]]
if JOB.get("reference_image"):
    cmd += ["--reference-image", str(ROOT / "inputs" / JOB["reference_image"])]
if JOB.get("posepack"):
    cmd += ["--posepack", str(ROOT / "inputs" / JOB["posepack"])]
for key in ["width", "height", "frames", "steps", "cfg", "seed"]:
    if JOB.get(key) is not None:
        cmd += ["--" + key.replace("_", "-"), str(JOB[key])]
print("$", " ".join(cmd))
raise SystemExit(subprocess.call(cmd, cwd=str(SPRITEFORGE)))
'''


def cmd_package(args: argparse.Namespace) -> None:
    job_id = args.job_id or time.strftime("cloud_job_%Y%m%d_%H%M%S")
    job_dir = Path(args.output or (ROOT / "output" / "cloud_jobs" / job_id)).resolve()
    if job_dir.exists() and args.force:
        shutil.rmtree(job_dir)
    job_dir.mkdir(parents=True, exist_ok=True)
    inputs = job_dir / "inputs"
    ref = copy_if(args.reference_image, inputs)
    pose = copy_if(args.posepack, inputs)
    workflow = copy_if(args.workflow, inputs)

    manifest = {
        "job_id": job_id,
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "mode": args.mode,
        "profile": args.profile,
        "prompt": args.prompt,
        "negative": args.negative,
        "reference_image": ref,
        "posepack": pose,
        "workflow": workflow,
        "width": args.width,
        "height": args.height,
        "frames": args.frames,
        "steps": args.steps,
        "cfg": args.cfg,
        "seed": args.seed,
        "spriteforge_dir": args.spriteforge_dir,
        "notes": "Upload this job folder next to SpriteForge Studio on a GPU machine, then run python run_cloud_job.py.",
    }
    (job_dir / "job_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (job_dir / "run_cloud_job.py").write_text(cloud_runner_script(), encoding="utf-8")
    (job_dir / "README_CLOUD_JOB.md").write_text(f"""# SpriteForge cloud job

Run this on a GPU cloud machine that has Python, Git, ComfyUI, WAN models, and SpriteForge Studio installed.

```bash
python run_cloud_job.py
```

This package intentionally contains no API keys.

Job mode: `{args.mode}`  
Profile: `{args.profile}`
""", encoding="utf-8")

    out_zip = Path(args.zip or (job_dir.with_suffix(".zip"))).resolve()
    zip_dir(job_dir, out_zip)
    print(f"Cloud job folder: {job_dir}")
    print(f"Cloud job zip: {out_zip}")


def run_cmd(cmd: List[str]) -> int:
    print("$ " + " ".join(cmd))
    return subprocess.call(cmd)


def cmd_ssh_run(args: argparse.Namespace) -> None:
    job_zip = Path(args.job_zip).resolve()
    if not job_zip.exists():
        raise FileNotFoundError(job_zip)
    target = f"{args.user + '@' if args.user else ''}{args.host}"
    remote_dir = args.remote_dir.rstrip("/")
    key_args = ["-i", args.key] if args.key else []

    run_cmd(["ssh"] + key_args + [target, f"mkdir -p {remote_dir}"])
    run_cmd(["scp"] + key_args + [str(job_zip), f"{target}:{remote_dir}/job.zip"])
    remote_cmd = f"cd {remote_dir} && unzip -o job.zip && python */run_cloud_job.py"
    rc = run_cmd(["ssh"] + key_args + [target, remote_cmd])
    raise SystemExit(rc)


def cmd_plan_runpod(args: argparse.Namespace) -> None:
    out = Path(args.output or (ROOT / "output" / "cloud_jobs" / "RUNPOD_PLAN.md"))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(f"""# RunPod-style SpriteForge plan

This is a safe plan file, not an API-keyed deploy.

Recommended cloud shape for heavy WAN jobs:

- GPU: RTX 4090, L40S, A40, A100, H100, or equivalent
- VRAM: 24 GB minimum for bigger WAN paths; more is better
- Disk: 80-150 GB depending on model set
- Container/image: Python + CUDA + Git + ComfyUI/SpriteForge installed

Workflow:

1. Start a GPU pod.
2. Upload/extract `spriteforge_studio_v5.zip`.
3. Run `setup_windows.bat` on Windows or manually create a venv on Linux.
4. Install ComfyUI/WAN models from the SpriteForge setup commands.
5. Create a cloud job package:

```bash
python spriteforge_cloud.py package --mode i2v --profile quality_local --prompt "your prompt" --reference-image input/reference.png
```

6. Upload the generated `cloud_job_*.zip` to the pod.
7. Run:

```bash
python run_cloud_job.py
```

No API key is written here. Put vendor credentials only in your cloud dashboard or environment variables, never in a project zip.
""", encoding="utf-8")
    print(f"Wrote: {out}")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="SpriteForge cloud GPU job packager")
    sub = p.add_subparsers(dest="command", required=True)

    s = sub.add_parser("package")
    s.add_argument("--job-id", default=None)
    s.add_argument("--output", default=None)
    s.add_argument("--zip", default=None)
    s.add_argument("--force", action="store_true")
    s.add_argument("--mode", default="t2v", choices=["t2v", "i2v", "vace", "custom"])
    s.add_argument("--profile", default="quality_local")
    s.add_argument("--prompt", required=True)
    s.add_argument("--negative", default=None)
    s.add_argument("--reference-image", default=None)
    s.add_argument("--posepack", default=None)
    s.add_argument("--workflow", default=None)
    s.add_argument("--width", type=int, default=None)
    s.add_argument("--height", type=int, default=None)
    s.add_argument("--frames", type=int, default=None)
    s.add_argument("--steps", type=int, default=None)
    s.add_argument("--cfg", type=float, default=None)
    s.add_argument("--seed", type=int, default=-1)
    s.add_argument("--spriteforge-dir", default="SpriteForge")
    s.set_defaults(func=cmd_package)

    s = sub.add_parser("ssh-run", help="Upload a cloud job zip over SSH and run it")
    s.add_argument("--host", required=True)
    s.add_argument("--user", default=None)
    s.add_argument("--key", default=None)
    s.add_argument("--remote-dir", default="~/spriteforge_job")
    s.add_argument("--job-zip", required=True)
    s.set_defaults(func=cmd_ssh_run)

    s = sub.add_parser("runpod-plan", help="Write a RunPod-style setup plan without storing API keys")
    s.add_argument("--output", default=None)
    s.set_defaults(func=cmd_plan_runpod)
    return p


def main() -> int:
    p = build_parser()
    args = p.parse_args()
    args.func(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
