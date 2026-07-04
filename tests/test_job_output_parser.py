import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "app"
sys.path.insert(0, str(APP))


def test_job_output_parser_extracts_progress_formats():
    from services.job_output_parser import parse_job_output_line

    assert parse_job_output_line("progress: 50%").progress_percent == 50.0
    assert parse_job_output_line("42%|████").progress_percent == 42.0
    assert parse_job_output_line("step 5/10").progress_percent == 50.0


def test_job_output_parser_extracts_stage_and_artifacts():
    from services.job_output_parser import parse_job_output_line

    queued = parse_job_output_line("Queued ComfyUI prompt id: abc-123")
    assert queued.stage == "queued_comfy"
    assert queued.prompt_id == "abc-123"

    source = parse_job_output_line("Source video: output/render.webm")
    assert source.source_video == "output/render.webm"

    sprite = parse_job_output_line("Sprite output: output/hero_walk")
    assert sprite.stage == "pack_sprite"
    assert sprite.sprite_output == "output/hero_walk"

    oom = parse_job_output_line("CUDA out of memory while allocating")
    assert oom.oom_detected is True
