import argparse
import sys
from spriteforge_commands import (
    ROOT,
    run,
    cmd_download_wan_native,
    cmd_model_report,
    cmd_model_tiers,
    cmd_download_model_tier,
    cmd_download_model_addon,
    cmd_open_model_pages,
    cmd_validate_workflow,
    cmd_queue_status,
    cmd_history,
)


def add_parsers(sub: argparse._SubParsersAction) -> None:
    s = sub.add_parser("download-wan-native", help="Download model files from a selected manifest")
    s.add_argument("--manifest", default="model_manifests/wan21_t2v_1_3b_native.json")
    s.add_argument("--force", action="store_true")
    s.add_argument("--dry-run", action="store_true")
    s.add_argument("--allow-heavy", action="store_true")
    s.set_defaults(func=cmd_download_wan_native)

    s = sub.add_parser("download-model-tier", help="Download a named model tier: safe, advanced, wan22_only, cloud")
    s.add_argument("--tier", default="safe")
    s.add_argument("--force", action="store_true")
    s.add_argument("--dry-run", action="store_true")
    s.add_argument("--allow-heavy", action="store_true")
    s.set_defaults(func=cmd_download_model_tier)

    s = sub.add_parser("download-model-addon", help="Download a recommended LoRA/model add-on from the add-on registry")
    s.add_argument("--addon", required=True)
    s.add_argument("--force", action="store_true")
    s.set_defaults(func=cmd_download_model_addon)

    s = sub.add_parser("model-tiers", help="List available model tiers and local file status")
    s.set_defaults(func=cmd_model_tiers)

    s = sub.add_parser("model-report", help="Check required model files")
    s.add_argument("--manifest", default="model_manifests/wan21_t2v_1_3b_native.json")
    s.add_argument("--json", action="store_true")
    s.set_defaults(func=cmd_model_report)

    s = sub.add_parser("open-model-pages")
    s.set_defaults(func=cmd_open_model_pages)

    s = sub.add_parser("validate-workflow", help="Validate API workflow JSON links and optionally node classes against running ComfyUI")
    s.add_argument("--workflow", default=None)
    s.add_argument("--profile", default="auto")
    s.add_argument("--tier", default="wan21_safe")
    s.add_argument("--check-nodes", action="store_true")
    s.set_defaults(func=cmd_validate_workflow)

    s = sub.add_parser("queue-status", help="Print ComfyUI queue/history summary")
    s.add_argument("--max-chars", type=int, default=8000)
    s.set_defaults(func=cmd_queue_status)

    s = sub.add_parser("history", help="Print one ComfyUI prompt history entry and resolved output files")
    s.add_argument("prompt_id")
    s.add_argument("--max-chars", type=int, default=12000)
    s.set_defaults(func=cmd_history)

    s = sub.add_parser("hardware-advisor", help="Read nvidia-smi and recommend local/cloud WAN and sprite defaults")
    s.add_argument("--apply", action="store_true", help="Back up config and apply recommended sprite defaults")
    s.add_argument("--output", default=None)
    s.set_defaults(func=lambda a: run([sys.executable, str(ROOT / "spriteforge_hardware.py"), "apply"] if a.apply else [sys.executable, str(ROOT / "spriteforge_hardware.py"), "report"] + (["--output", a.output] if a.output else [])))
