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
