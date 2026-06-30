#!/usr/bin/env python3
"""
SpriteForge Unified v12: local orchestrator for ComfyUI + WAN + sprite conversion.

This package delegates its command logic to spriteforge_commands.py, keeping this
orchestrator file under 500 lines of code. It remains fully compatible with CLI commands
and the integration test suite.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Optional, Sequence

# Expose globals and imports for tests (monkeypatch compatibility)
from spriteforge_commands import (
    ROOT,
    run,
    Config,
    load_config,
    cmd_status,
    cmd_doctor,
    cmd_install_spriteforge,
    cmd_install_all,
    cmd_install_comfy,
    cmd_install_nodes,
    cmd_install_manager,
    cmd_launch_comfy,
    cmd_open_comfy,
    cmd_submit_wan,
    cmd_generate_sprite,
    cmd_watch_output,
    cmd_convert_video,
    cmd_download_wan_native,
    cmd_model_report,
    cmd_model_tiers,
    cmd_download_model_tier,
    cmd_qa_report,
    cmd_open_model_pages,
    cmd_validate_workflow,
    cmd_queue_status,
    cmd_history
)

PRODUCTION_PASSTHROUGH = {
    "project-init", "batch-plan", "run-batch", "qa", "atlas", "export-atlas-engine", "lock-env"
}

FINAL_PASSTHROUGH = {
    "next-step": "next",
    "preflight": "preflight",
    "asset-dashboard": "dashboard",
    "release-package": "release",
    "open-latest": "latest",
}

QUEUE_PASSTHROUGH = {
    "queue-create": "create",
    "queue-run": "run",
    "queue-status": "status",
    "queue-reset": "reset",
}


from spriteforge_unified_parser import build_parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    argv = list(argv if argv is not None else sys.argv[1:])
    # Route rich subtools before argparse consumes their --flags.
    if argv and argv[0] in FINAL_PASSTHROUGH:
        mapped = FINAL_PASSTHROUGH[argv[0]]
        try:
            return run([sys.executable, str(ROOT / "spriteforge_final.py"), mapped] + argv[1:]).returncode
        except KeyboardInterrupt:
            print("Stopped.", file=sys.stderr)
            return 130
        except Exception as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 1
    if argv and argv[0] in QUEUE_PASSTHROUGH:
        mapped = QUEUE_PASSTHROUGH[argv[0]]
        try:
            return run([sys.executable, str(ROOT / "spriteforge_queue.py"), mapped] + argv[1:]).returncode
        except KeyboardInterrupt:
            print("Stopped.", file=sys.stderr)
            return 130
        except Exception as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 1
    if argv and argv[0] in PRODUCTION_PASSTHROUGH:
        try:
            return run([sys.executable, str(ROOT / "spriteforge_production.py")] + argv).returncode
        except KeyboardInterrupt:
            print("Stopped.", file=sys.stderr)
            return 130
        except Exception as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 1

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
