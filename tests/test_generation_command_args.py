import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "app"
sys.path.insert(0, str(APP))


def test_shared_sprite_polish_args_register_modern_engines():
    from services.generation_commands import add_sprite_polish_args, _sprite_extra_from_generate_args

    parser = argparse.ArgumentParser()
    add_sprite_polish_args(parser, defaults=False)
    args = parser.parse_args([
        "--matting-engine",
        "depth-anything",
        "--interpolation-engine",
        "rife",
        "--pixel-cleanup",
        "--pixel-cleanup-palette",
        "#112233,#445566",
        "--generate-normal-maps",
        "--normal-map-engine",
        "native-depth",
    ])

    extra = _sprite_extra_from_generate_args(args)
    assert "--matting-engine" in extra
    assert "depth-anything" in extra
    assert "--interpolation-engine" in extra
    assert "rife" in extra
    assert "--pixel-cleanup" in extra
    assert "--generate-normal-maps" in extra


def test_unified_generate_sprite_uses_shared_polish_args():
    from spriteforge_unified import build_parser

    args = build_parser().parse_args([
        "generate-sprite",
        "--matting-engine",
        "depth-anything",
        "--interpolation-engine",
        "rife",
        "--pixel-cleanup-dither-mode",
        "bayer",
    ])

    assert args.matting_engine == "depth-anything"
    assert args.interpolation_engine == "rife"
    assert args.pixel_cleanup_dither_mode == "bayer"
    assert args.pack_mode == "grid"
