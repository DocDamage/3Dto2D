import argparse
import sys
from spriteforge_commands import (
    ROOT,
    run,
    cmd_status,
    cmd_doctor,
    cmd_install_spriteforge,
    cmd_install_all,
    cmd_install_comfy,
    cmd_install_nodes,
    cmd_install_manager,
    cmd_launch_comfy,
    cmd_open_comfy,
)


def add_parsers(sub: argparse._SubParsersAction) -> None:
    s = sub.add_parser("status")
    s.set_defaults(func=cmd_status)

    s = sub.add_parser("doctor", help="Run system, ComfyUI, model, node, and workflow diagnostics")
    s.add_argument("--manifest", default="model_manifests/wan21_t2v_1_3b_native.json")
    s.add_argument("--workflow", default=None)
    s.add_argument("--profile", default="auto")
    s.add_argument("--tier", default="wan21_safe")
    s.set_defaults(func=cmd_doctor)

    s = sub.add_parser("install-spriteforge", help="Install SpriteForge local Python dependencies")
    s.add_argument("--python", default="3.12")
    s.set_defaults(func=cmd_install_spriteforge)

    s = sub.add_parser("install-all", help="Install/update SpriteForge, ComfyUI, WAN nodes, Manager, and selected WAN model tier")
    s.add_argument("--python", default="3.12")
    s.add_argument("--torch-index", default="cu126", choices=["cu130", "cu126", "cu121"])
    s.add_argument("--skip-torch", action="store_true")
    s.add_argument("--model-tier", default="safe", help="safe/recommended=Wan2.1 1.3B, advanced=Wan2.1+Wan2.2 5B, wan22_only=only Wan2.2 5B, cloud=no local model download")
    s.add_argument("--manifest", default=None, help="Legacy/manual manifest override. Usually leave empty and use --model-tier.")
    s.add_argument("--force-models", action="store_true")
    s.add_argument("--allow-heavy-models", action="store_true", help="Allow cloud/heavy manifests if explicitly requested")
    s.add_argument("--skip-models", action="store_true", help="Install ComfyUI/nodes but do not download WAN weights")
    s.add_argument("--skip-doctor", action="store_true")
    s.add_argument("--skip-hardware-apply", action="store_true")
    s.add_argument("--snapshot", action="store_true", help="Create a rollback snapshot before updating ComfyUI/custom nodes")
    s.set_defaults(func=cmd_install_all)

    s = sub.add_parser("install-comfy", help="Install/update ComfyUI and optionally WAN/video nodes")
    s.add_argument("--python", default="3.12")
    s.add_argument("--torch-index", default="cu130", choices=["cu130", "cu126", "cu121"])
    s.add_argument("--skip-torch", action="store_true")
    s.add_argument("--nodes", action="store_true", help="Also install WanVideoWrapper and VideoHelperSuite")
    s.add_argument("--manager", action="store_true", help="Also install ComfyUI Manager into custom_nodes/comfyui-manager")
    s.set_defaults(func=cmd_install_comfy)

    s = sub.add_parser("install-nodes", help="Install/update WAN and video helper ComfyUI custom nodes")
    s.add_argument("--manager", action="store_true")
    s.set_defaults(func=cmd_install_nodes)

    s = sub.add_parser("install-manager", help="Install/update ComfyUI Manager")
    s.set_defaults(func=cmd_install_manager)

    s = sub.add_parser("launch-comfy", help="Launch ComfyUI")
    s.add_argument("extra", nargs=argparse.REMAINDER, help="Extra args passed to ComfyUI main.py")
    s.set_defaults(func=cmd_launch_comfy)

    s = sub.add_parser("open-comfy")
    s.set_defaults(func=cmd_open_comfy)

    s = sub.add_parser("snapshot", help="Snapshot ComfyUI/custom-node git revisions before updates")
    s.add_argument("--name", default=None)
    s.set_defaults(func=lambda a: run([sys.executable, str(ROOT / "spriteforge_maintenance.py"), "snapshot"] + (["--name", a.name] if a.name else [])))

    s = sub.add_parser("safe-update", help="Snapshot first, then git-pull ComfyUI and optionally custom nodes")
    s.add_argument("--custom-nodes", action="store_true")
    s.set_defaults(func=lambda a: run([sys.executable, str(ROOT / "spriteforge_maintenance.py"), "safe-update"] + (["--custom-nodes"] if a.custom_nodes else [])))

    s = sub.add_parser("rollback", help="Rollback ComfyUI/custom-node git repos to a saved snapshot")
    s.add_argument("--snapshot", required=True)
    s.add_argument("--dry-run", action="store_true")
    s.set_defaults(func=lambda a: run([sys.executable, str(ROOT / "spriteforge_maintenance.py"), "rollback", "--snapshot", a.snapshot] + (["--dry-run"] if a.dry_run else [])))
