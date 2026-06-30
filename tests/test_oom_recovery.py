import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "app"
sys.path.insert(0, str(APP))


def test_oom_recovery_uses_progressive_fallback_chain():
    from services.oom_recovery_service import progressive_vram_fallback

    cmd = [
        "python",
        "spriteforge_unified.py",
        "generate-sprite",
        "--tier",
        "wan22_5b",
        "--profile",
        "wan22_5b_3060_best",
        "--cell-size",
        "512x512",
        "--resolutions",
        "832x480,640x384",
    ]

    first = progressive_vram_fallback(cmd, attempt=1)
    second = progressive_vram_fallback(first.command, attempt=2)
    third = progressive_vram_fallback(second.command, attempt=3)
    fourth = progressive_vram_fallback(third.command, attempt=4)

    assert first.label == "fp8_quantization"
    assert first.command[first.command.index("--tier") + 1] == "wan21_safe"
    assert first.command[first.command.index("--profile") + 1] == "wan22_5b_debug"
    assert "--vram-fallback" in first.command

    assert second.label == "reduced_batch"
    assert second.command[second.command.index("--batch-size") + 1] == "1"

    assert third.label == "reduced_resolution"
    assert third.command[third.command.index("--cell-size") + 1] == "256x256"
    assert third.command[third.command.index("--resolutions") + 1] == "416x240,320x192"

    assert fourth.label == "cpu_offload"
    assert fourth.command[fourth.command.index("--cpu-offload") + 1] == "true"


def test_job_service_compat_wrapper_uses_first_progressive_step():
    from services.job_service import JobService

    cmd = ["python", "spriteforge_unified.py", "generate-sprite", "--tier", "wan22_5b", "--profile", "wan22_5b_local"]

    adjusted = JobService.adjust_cmd_for_vram_fallback(cmd)

    assert adjusted[adjusted.index("--tier") + 1] == "wan21_safe"
    assert adjusted[adjusted.index("--profile") + 1] == "wan22_5b_debug"
    assert adjusted[adjusted.index("--vram-fallback") + 1] == "fp8"


def test_generate_sprite_accepts_vram_fallback_flags():
    from spriteforge_unified import build_parser

    args = build_parser().parse_args([
        "generate-sprite",
        "--vram-fallback",
        "batch",
        "--batch-size",
        "1",
        "--cpu-offload",
        "true",
    ])

    assert args.vram_fallback == "batch"
    assert args.batch_size == 1
    assert args.cpu_offload == "true"
