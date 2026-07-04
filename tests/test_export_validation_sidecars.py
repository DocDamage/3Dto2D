import json
import sys
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "app"
sys.path.insert(0, str(APP))


def _make_sprite_dir(tmp_path: Path) -> Path:
    sprite_dir = tmp_path / "sprite"
    sprite_dir.mkdir()
    Image.new("RGBA", (16, 8), (40, 90, 160, 255)).save(sprite_dir / "sheet.png")
    (sprite_dir / "sheet.json").write_text(
        json.dumps(
            {
                "frame_width": 8,
                "frame_height": 8,
                "frame_count": 2,
                "columns": 2,
                "rows": 1,
                "fps": 8,
                "image": "sheet.png",
            }
        ),
        encoding="utf-8",
    )
    return sprite_dir


def _lighting_contract() -> dict:
    return {
        "lighting_maps": {
            "schema": "spriteforge.lighting_maps.v1",
            "server_bake": "normal_specular_ao",
            "normal": {"available": True, "frame_count": 2},
            "specular": {"available": True, "frame_count": 2},
            "ao": {"available": True, "frame_count": 2},
        },
        "rendering": {
            "schema": "spriteforge.lighting_preview_render.v1",
            "normal_compositing": True,
            "specular_compositing": True,
            "ao_compositing": True,
            "texture_filter": "nearest",
        },
    }


def test_validate_export_checks_optional_lighting_sidecar(tmp_path):
    from spriteforge_engine_export import validate_export

    sprite_dir = _make_sprite_dir(tmp_path)
    Image.new("RGBA", (8, 8), (10, 10, 10, 255)).save(sprite_dir / "lighting_preview.gif")
    (sprite_dir / "lighting_preview.lighting_preview.json").write_text(
        json.dumps(
            {
                "schema": "spriteforge.lighting_preview.v1",
                "file": "lighting_preview.gif",
                "frame_count": 2,
                "engine_ready": {"godot": True, "web": True},
                **_lighting_contract(),
            }
        ),
        encoding="utf-8",
    )

    report = validate_export(sprite_dir, return_dict=True)

    assert report["ok"] is True
    labels = {row["label"] for row in report["results"]}
    assert "lighting_preview.lighting_preview.json schema present" in labels
    assert "lighting_preview.lighting_preview.json referenced asset exists" in labels
    assert "lighting_preview.lighting_preview.json lighting maps contract valid" in labels
    assert "lighting_preview.lighting_preview.json lighting render contract valid" in labels


def test_validate_export_fails_bad_sidecar_frame_count(tmp_path):
    from spriteforge_engine_export import validate_export

    sprite_dir = _make_sprite_dir(tmp_path)
    Image.new("RGBA", (8, 8), (10, 10, 10, 255)).save(sprite_dir / "lighting_preview.gif")
    (sprite_dir / "lighting_preview.lighting_preview.json").write_text(
        json.dumps(
            {
                "schema": "spriteforge.lighting_preview.v1",
                "file": "lighting_preview.gif",
                "frame_count": 99,
                "engine_ready": {"godot": True},
                **_lighting_contract(),
            }
        ),
        encoding="utf-8",
    )

    report = validate_export(sprite_dir, return_dict=True)

    assert report["ok"] is False
    bad = [row for row in report["results"] if row["label"].endswith("frame_count matches sheet")]
    assert bad and bad[0]["ok"] is False


def test_validate_export_checks_audio_cue_handoff(tmp_path):
    from services.audio_cue_service import upsert_audio_cue
    from spriteforge_engine_export import validate_export

    sprite_dir = _make_sprite_dir(tmp_path)
    audio_dir = sprite_dir / "input" / "sfx"
    audio_dir.mkdir(parents=True)
    (audio_dir / "step.wav").write_bytes(b"RIFF....WAVEfmt ")

    manifest = upsert_audio_cue(sprite_dir, 1, "input/sfx/step.wav", "step")
    assert manifest["engine_import"]["fps"] == 8.0
    assert manifest["cues"][0]["time_seconds"] == 0.125

    report = validate_export(sprite_dir, return_dict=True)

    assert report["ok"] is True
    labels = {row["label"] for row in report["results"]}
    assert "audio_cues.json schema valid" in labels
    assert "audio_cues.json engine sync metadata present" in labels
    assert "audio_cues.json cue timing matches fps" in labels
    assert "audio_cues.json referenced audio exists" in labels


def test_validate_export_checks_tilemap_engine_manifest(tmp_path):
    from services.tilemap_service import build_tilemap_engine_manifest
    from spriteforge_engine_export import validate_export

    sprite_dir = _make_sprite_dir(tmp_path)
    Image.new("RGBA", (16, 16), (30, 120, 60, 255)).save(sprite_dir / "terrain.png")
    engine_manifest = build_tilemap_engine_manifest(
        "autotile_16",
        "terrain.png",
        8,
        8,
        2,
        2,
        [
            {"index": 0, "open_neighbors": {"north": True}},
            {"index": 1, "open_neighbors": {"east": True}},
            {"index": 2, "open_neighbors": {"south": True}},
            {"index": 3, "open_neighbors": {"west": True}},
        ],
    )
    (sprite_dir / "terrain.tilemap.json").write_text(
        json.dumps({"engine_manifest": engine_manifest}),
        encoding="utf-8",
    )

    report = validate_export(sprite_dir, return_dict=True)

    assert report["ok"] is True
    labels = {row["label"] for row in report["results"]}
    assert "terrain.tilemap.json tilemap engine schema valid" in labels
    assert "terrain.tilemap.json tilemap image exists" in labels
    assert "terrain.tilemap.json tile index table complete" in labels
    assert "terrain.tilemap.json tilemap engine import targets present" in labels
    assert "terrain.tilemap.json tilemap image dimensions match" in labels


def test_validate_export_checks_skeletal_manifest_handoff(tmp_path):
    from services.skeletal_export_service import export_skeletal_parts
    from spriteforge_engine_export import validate_export

    sprite_dir = _make_sprite_dir(tmp_path)
    body = Image.new("RGBA", (16, 8), (0, 0, 0, 0))
    for x in range(2, 7):
        for y in range(1, 8):
            body.putpixel((x, y), (220, 20, 20, 255))
    body.save(sprite_dir / "sheet_body.png")

    export_skeletal_parts(sprite_dir, output_dir=sprite_dir / "skeletal_export", name="hero_idle")

    report = validate_export(sprite_dir, return_dict=True)

    assert report["ok"] is True
    labels = {row["label"] for row in report["results"]}
    assert "skeletal_manifest.json schema valid" in labels
    assert "skeletal_manifest.json engine import contract valid" in labels
    assert "skeletal spine.json exists" in labels
    assert "skeletal dragonbones.json exists" in labels
    assert "skeletal part sheets and pivots valid" in labels
    assert "skeletal spine slot order matches manifest" in labels
    assert "skeletal dragonbones armature matches manifest" in labels


def test_validate_export_checks_scene_compositor_handoff(tmp_path):
    from services.scene_compositor_service import build_scene_manifest
    from spriteforge_engine_export import validate_export

    sprite_dir = _make_sprite_dir(tmp_path)
    layer_dir = sprite_dir / "output" / "hero_idle"
    layer_dir.mkdir(parents=True)
    Image.new("RGBA", (16, 8), (40, 90, 160, 255)).save(layer_dir / "sheet.png")
    (layer_dir / "sheet.json").write_text(
        json.dumps({
            "animation": "idle",
            "image": "sheet.png",
            "frame_width": 8,
            "frame_height": 8,
            "frame_count": 2,
            "columns": 2,
            "rows": 1,
            "fps": 8,
        }),
        encoding="utf-8",
    )

    build_scene_manifest(
        sprite_dir,
        {
            "name": "battle_scene",
            "write_exports": True,
            "output_dir": "scenes/battle_scene",
            "layers": [{"name": "Hero", "sprite_path": "output/hero_idle", "x": 64, "y": 64}],
        },
    )

    report = validate_export(sprite_dir, return_dict=True)

    assert report["ok"] is True
    labels = {row["label"] for row in report["results"]}
    assert "scene_manifest.json scene handoff schema valid" in labels
    assert "scene_manifest.json engine import metadata valid" in labels
    assert "scene_manifest.json dependencies valid" in labels
    assert "scene_manifest.json layer count matches" in labels
    assert "scene_manifest.json Godot scaffold exists" in labels
    assert "scene_manifest.json composite export plan valid" in labels


def test_validate_export_checks_cloud_generation_manifest(tmp_path):
    from services.cloud_image_generation_service import build_cloud_sprite_sheet
    from spriteforge_engine_export import validate_export

    source = tmp_path / "cloud_source.png"
    image = Image.new("RGBA", (64, 64), (255, 0, 255, 255))
    for x in range(20, 44):
        for y in range(12, 58):
            image.putpixel((x, y), (40, 180, 220, 255))
    image.save(source)

    sprite_dir = tmp_path / "cloud_sprite"
    build_cloud_sprite_sheet(
        prompt="blue cloud hero",
        output_dir=sprite_dir,
        provider="openai",
        source_images=[str(source)],
        cell_size="32x32",
        palette_colors=8,
        animation_name="idle",
    )

    report = validate_export(sprite_dir, return_dict=True)

    assert report["ok"] is True
    labels = {row["label"] for row in report["results"]}
    assert "cloud_generation.json schema valid" in labels
    assert "cloud_generation.json frame_count matches sheet" in labels
    assert "cloud_generation.json processing contract valid" in labels
    assert "cloud_generation.json generation contract valid" in labels
    assert "cloud_generation.json frame source files exist" in labels
    assert "cloud_generation.json cleanup metrics valid" in labels
    assert "cloud_generation.json provider metadata present" in labels


def test_validate_export_checks_release_handoff_manifest(tmp_path):
    import zipfile
    from spriteforge_engine_export import validate_export

    sprite_dir = _make_sprite_dir(tmp_path)
    release_dir = tmp_path / "release"
    release_sprite = release_dir / "sprites" / "sprite"
    preflight_dir = release_dir / "preflight"
    release_sprite.mkdir(parents=True)
    preflight_dir.mkdir(parents=True)
    (release_sprite / "sheet.png").write_bytes((sprite_dir / "sheet.png").read_bytes())
    (release_sprite / "sheet.json").write_text((sprite_dir / "sheet.json").read_text(encoding="utf-8"), encoding="utf-8")
    (preflight_dir / "preflight.json").write_text("{}", encoding="utf-8")
    (preflight_dir / "preflight.html").write_text("<html></html>", encoding="utf-8")
    (release_dir / "manifest.json").write_text(
        json.dumps({
            "schema": "spriteforge_release_v12",
            "name": "release",
            "handoff": {
                "schema": "spriteforge.release_handoff.v1",
                "preflight": {"json": "preflight/preflight.json", "html": "preflight/preflight.html"},
            },
        }),
        encoding="utf-8",
    )
    zip_path = tmp_path / "release.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        for path in release_dir.rglob("*"):
            if path.is_file():
                zf.write(path, path.relative_to(tmp_path))

    report = validate_export(sprite_dir, release_zip=zip_path, return_dict=True)

    assert report["ok"] is True
    labels = {row["label"] for row in report["results"]}
    assert "Release manifest schema valid" in labels
    assert "Release handoff schema valid" in labels
    assert "Release handoff preflight JSON exists" in labels
    assert "Release handoff preflight HTML exists" in labels
    assert "Release zip excludes restricted/heavy files" in labels


def test_validate_export_fails_release_zip_with_restricted_member(tmp_path):
    import zipfile
    from spriteforge_engine_export import validate_export

    sprite_dir = _make_sprite_dir(tmp_path)
    release_dir = tmp_path / "release"
    release_dir.mkdir()
    (release_dir / "manifest.json").write_text(
        json.dumps({
            "schema": "spriteforge_release_v12",
            "handoff": {"schema": "spriteforge.release_handoff.v1", "preflight": {}},
        }),
        encoding="utf-8",
    )
    zip_path = tmp_path / "release.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.write(release_dir / "manifest.json", "release/manifest.json")
        zf.writestr("release/models/big_model.safetensors", b"not allowed")

    report = validate_export(sprite_dir, release_zip=zip_path, return_dict=True)

    assert report["ok"] is False
    restricted = [row for row in report["results"] if row["label"] == "Release zip excludes restricted/heavy files"]
    assert restricted and restricted[0]["ok"] is False
    assert "big_model.safetensors" in restricted[0]["detail"]


def test_validate_export_checks_optional_animated_export_sidecar(tmp_path):
    from spriteforge_engine_export import validate_export

    sprite_dir = _make_sprite_dir(tmp_path)
    animated_exports_dir = sprite_dir / "animated_exports"
    animated_exports_dir.mkdir()
    (animated_exports_dir / "idle.apng").write_bytes(b"PNG...")
    
    (animated_exports_dir / "idle.apng.manifest.json").write_text(
        json.dumps(
            {
                "schema": "spriteforge.animated_export.v1",
                "format": "apng",
                "file": "idle.apng",
                "frame_count": 2,
                "engine_ready": {"godot": True, "web": True},
                "format_capabilities": {
                    "schema": "spriteforge.animated_export_format.v1",
                    "format": "apng",
                    "animated_raster": True,
                    "runtime_asset": True,
                    "metadata_asset": False,
                    "transparent_animation": True,
                    "engine_targets": {
                        "godot": True,
                        "unity": True,
                        "web": True
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    report = validate_export(sprite_dir, return_dict=True)

    assert report["ok"] is True
    labels = {row["label"] for row in report["results"]}
    assert "idle.apng.manifest.json schema present" in labels
    assert "idle.apng.manifest.json referenced asset exists" in labels
    assert "idle.apng.manifest.json format_capabilities contract valid" in labels

