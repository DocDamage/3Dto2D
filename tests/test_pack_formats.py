import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "app"
sys.path.insert(0, str(APP))

from spriteforge_pack_formats import aseprite_json, build_parser, cmd_export, xml_atlas
from spriteforge_unified import build_parser as build_unified_parser


def sample_meta():
    return {
        "animation": "hero_walk",
        "frame_count": 2,
        "fps": 12,
        "frame_width": 16,
        "frame_height": 24,
        "columns": 2,
        "rows": 1,
        "frames": [
            {"x": 0, "y": 0, "w": 16, "h": 24},
            {"x": 16, "y": 0, "w": 16, "h": 24},
        ],
    }


def test_xml_atlas_export_shape():
    root = ET.fromstring(xml_atlas(sample_meta(), "hero.png"))

    assert root.tag == "TextureAtlas"
    assert root.attrib["imagePath"] == "hero.png"
    assert root.attrib["width"] == "32"
    frames = root.findall("SubTexture")
    assert [frame.attrib["name"] for frame in frames] == ["hero_walk_0000.png", "hero_walk_0001.png"]
    assert frames[1].attrib["x"] == "16"


def test_aseprite_json_export_shape():
    data = aseprite_json(sample_meta(), "hero.png")

    assert data["meta"]["image"] == "hero.png"
    assert data["frames"][0]["filename"] == "hero_walk_0000.png"
    assert data["frames"][1]["frame"] == {"x": 16, "y": 0, "w": 16, "h": 24}
    assert data["meta"]["frameTags"] == [{"name": "hero_walk", "from": 0, "to": 1, "direction": "forward"}]


def test_xml_atlas_cli_writes_file(tmp_path):
    sprite_dir = tmp_path / "sprite"
    sprite_dir.mkdir()
    (sprite_dir / "sheet.json").write_text(json.dumps({**sample_meta(), "image": "sheet.png"}), encoding="utf-8")
    (sprite_dir / "sheet.png").write_bytes(b"fake")

    args = build_parser().parse_args(["export", "--sprite-dir", str(sprite_dir), "--format", "xml"])
    cmd_export(args)

    atlas = sprite_dir / "atlas_exports" / "atlas.xml"
    assert atlas.exists()
    assert ET.parse(atlas).getroot().findall("SubTexture")


def test_unified_export_atlas_accepts_xml():
    args = build_unified_parser().parse_args(["export-atlas", "--sprite-dir", "output/demo", "--format", "xml"])

    assert args.format == "xml"


def test_unified_export_atlas_accepts_aseprite():
    args = build_unified_parser().parse_args(["export-atlas", "--sprite-dir", "output/demo", "--format", "aseprite"])

    assert args.format == "aseprite"


def test_export_apng(tmp_path):
    from PIL import Image
    from services.sprite_sheet_service import export_apng
    from services.sprite_video_loader import FrameItem
    img1 = Image.new("RGBA", (32, 32), (255, 0, 0, 255))
    img2 = Image.new("RGBA", (32, 32), (0, 255, 0, 255))
    frames = [
        FrameItem(image=img1, name="f1", source_index=0),
        FrameItem(image=img2, name="f2", source_index=1)
    ]
    out_file = tmp_path / "anim.png"
    export_apng(frames, out_file, fps=12)
    assert out_file.exists()

    with Image.open(out_file) as img:
        assert img.format == "PNG"
        assert img.size == (32, 32)


def test_export_webp_anim(tmp_path):
    from PIL import Image
    from services.sprite_sheet_service import export_webp_anim
    from services.sprite_video_loader import FrameItem
    img1 = Image.new("RGBA", (32, 32), (255, 0, 0, 255))
    img2 = Image.new("RGBA", (32, 32), (0, 255, 0, 255))
    frames = [
        FrameItem(image=img1, name="f1", source_index=0),
        FrameItem(image=img2, name="f2", source_index=1)
    ]
    out_file = tmp_path / "anim.webp"
    export_webp_anim(frames, out_file, fps=12)
    assert out_file.exists()

    with Image.open(out_file) as img:
        assert img.format == "WEBP"
        assert img.size == (32, 32)
