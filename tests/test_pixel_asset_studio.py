import json
import sys
import pytest
import zipfile
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "app"
sys.path.insert(0, str(APP))

from services.pixel_asset_schema import (
    validate_pixel_asset, validate_pixel_style_profile, validate_pixel_asset_batch
)
import services.pixel_asset_service as pas_mod
from services.pixel_asset_service import PixelAssetService
from services.pixel_normalization_service import PixelNormalizationService
from services.pixel_direction_service import PixelDirectionService
from services.pixel_export_service import PixelExportService
from services.pixel_tileset_service import PixelTilesetService
from services.pixel_inpaint_service import PixelInpaintService
from services.pixel_animation_service import PixelAnimationService
from services.pixel_transfer_service import PixelTransferService
from services.pixel_rig_service import PixelRigService
from services.pixel_pack_service import PixelPackService
from services.pixel_recipe_service import PixelRecipeService
from services.pixel_style_service import PixelStyleService
from services.pixel_asset_memory_service import PixelAssetMemoryService
from services.pixel_part_apply_service import PixelPartApplyService
from services.pixel_reskin_service import PixelReskinService
from services.pixel_cleanup_service import PixelCleanupService
from services.failure_explainer_service import explain_pixel_failure
from spriteforge_web import app

@pytest.fixture(autouse=True)
def mock_pixel_paths(tmp_path, monkeypatch):
    """Insulates the filesystem side-effects by redirecting directories to a temp directory."""
    temp_root = tmp_path / "pixel_assets"
    assets = temp_root / "assets"
    batches = temp_root / "batches"
    styles = temp_root / "styles"

    monkeypatch.setattr(pas_mod, "PIXEL_ASSETS_DIR", temp_root)
    monkeypatch.setattr(pas_mod, "ASSETS_DIR", assets)
    monkeypatch.setattr(pas_mod, "BATCHES_DIR", batches)
    monkeypatch.setattr(pas_mod, "STYLES_DIR", styles)

    # Re-patch other services to align on the same temp paths
    import services.pixel_direction_service as pds_mod
    monkeypatch.setattr(pds_mod, "ROOT", tmp_path)
    monkeypatch.setattr(pds_mod, "PIXEL_ASSETS_DIR", temp_root)
    monkeypatch.setattr(pds_mod, "ASSETS_DIR", assets)
    monkeypatch.setattr(pds_mod, "BATCHES_DIR", batches)

    import services.pixel_export_service as pes_mod
    monkeypatch.setattr(pes_mod, "ROOT", tmp_path)
    monkeypatch.setattr(pes_mod, "PIXEL_ASSETS_DIR", temp_root)
    monkeypatch.setattr(pes_mod, "ASSETS_DIR", assets)
    monkeypatch.setattr(pes_mod, "BATCHES_DIR", batches)

    import services.pixel_tileset_service as pts_mod
    monkeypatch.setattr(pts_mod, "ROOT", tmp_path)
    monkeypatch.setattr(pts_mod, "PIXEL_ASSETS_DIR", temp_root)
    monkeypatch.setattr(pts_mod, "ASSETS_DIR", assets)
    monkeypatch.setattr(pts_mod, "BATCHES_DIR", batches)

    import services.pixel_inpaint_service as pis_mod
    monkeypatch.setattr(pis_mod, "ASSETS_DIR", assets)

    import services.pixel_animation_service as pas_srv_mod
    monkeypatch.setattr(pas_srv_mod, "ASSETS_DIR", assets)
    monkeypatch.setattr(pas_srv_mod, "BATCHES_DIR", batches)

    import services.pixel_transfer_service as pts_srv_mod
    monkeypatch.setattr(pts_srv_mod, "ASSETS_DIR", assets)
    monkeypatch.setattr(pts_srv_mod, "BATCHES_DIR", batches)

    import services.pixel_rig_service as prs_srv_mod
    monkeypatch.setattr(prs_srv_mod, "ASSETS_DIR", assets)
    monkeypatch.setattr(prs_srv_mod, "BATCHES_DIR", batches)

    import services.pixel_part_apply_service as ppa_srv_mod
    monkeypatch.setattr(ppa_srv_mod, "ROOT", tmp_path)
    monkeypatch.setattr(ppa_srv_mod, "ASSETS_DIR", assets)

    import services.pixel_reskin_service as reskin_srv_mod
    monkeypatch.setattr(reskin_srv_mod, "ROOT", tmp_path)
    monkeypatch.setattr(reskin_srv_mod, "ASSETS_DIR", assets)

    import services.pixel_cleanup_service as cleanup_srv_mod
    monkeypatch.setattr(cleanup_srv_mod, "ROOT", tmp_path)
    monkeypatch.setattr(cleanup_srv_mod, "ASSETS_DIR", assets)

    import services.pixel_recipe_service as recipe_mod
    monkeypatch.setattr(recipe_mod, "RECIPES_DIR", temp_root / "recipes")

    import services.experiment_service as exp_mod
    monkeypatch.setattr(exp_mod, "EXPERIMENT_PATH", tmp_path / "experiments" / "experiment_history.json")

    import services.web_helpers_library as library_mod
    monkeypatch.setattr(library_mod, "ROOT", tmp_path)

    import sys
    routes_module = sys.modules.get("web_routes.routes_pixel_asset")
    if routes_module:
        monkeypatch.setattr(routes_module, "ROOT", tmp_path)
        monkeypatch.setattr(routes_module, "ASSETS_DIR", assets)

    # Initialize the temporary directories
    PixelAssetService.initialize()

@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client

def test_schema_validations():
    valid_asset = {
        "schema": "spriteforge.pixel_asset.v1",
        "asset_id": "pxa_test_asset",
        "asset_type": "weapon",
        "prompt": "ruby dagger",
        "resolution": [32, 32],
        "palette": {
            "max_colors": 16,
            "colors": ["#000000", "#ffffff"]
        },
        "outputs": {
            "png": "output/pixel_assets/assets/test.png",
            "preview": "output/pixel_assets/assets/preview.png",
            "metadata": "output/pixel_assets/assets/pixel_asset.json"
        }
    }
    ok, err = validate_pixel_asset(valid_asset)
    assert ok is True

    invalid_asset = dict(valid_asset)
    invalid_asset["asset_type"] = "invalid_type"
    ok, err = validate_pixel_asset(invalid_asset)
    assert ok is False
    assert "asset_type" in err

def test_normalization_algorithms():
    # 1. Test clean alpha
    img = Image.new("RGBA", (10, 10), (255, 0, 0, 100)) # Alpha = 100
    cleaned = PixelNormalizationService.clean_alpha(img, threshold=120)
    assert cleaned.getpixel((0, 0))[3] == 0

    cleaned_opaque = PixelNormalizationService.clean_alpha(img, threshold=50)
    assert cleaned_opaque.getpixel((0, 0))[3] == 255

    # 2. Test resize
    resized = PixelNormalizationService.resize_canvas(img, (20, 20))
    assert resized.size == (20, 20)

    # 3. Test remove islands
    img_island = Image.new("RGBA", (8, 8), (0, 0, 0, 0))
    # Draw a 4-pixel square (main body)
    img_island.putpixel((1, 1), (255, 255, 255, 255))
    img_island.putpixel((1, 2), (255, 255, 255, 255))
    img_island.putpixel((2, 1), (255, 255, 255, 255))
    img_island.putpixel((2, 2), (255, 255, 255, 255))
    # Draw a 1-pixel floating island
    img_island.putpixel((6, 6), (255, 0, 0, 255))

    no_islands = PixelNormalizationService.remove_islands(img_island, min_size=2)
    assert no_islands.getpixel((1, 1))[3] == 255
    assert no_islands.getpixel((6, 6))[3] == 0 # Island erased

def test_missing_key_error_handling(client):
    payload = {
        "asset_type": "weapons",
        "prompt": "golden bow",
        "resolution": "24x24",
        "palette_size": "16",
        "provider": "openai",
        "count": 2,
        "mock": False # Request real generation to trigger key validation
    }
    response = client.post(
        "/api/pixel-assets/generate",
        data=json.dumps(payload),
        content_type="application/json"
    )
    assert response.status_code == 400
    data = json.loads(response.data.decode("utf-8"))
    assert data["ok"] is False
    assert "Key Validation Failed" in data["message"]

def test_real_generation_mock_mode(client, tmp_path):
    payload = {
        "asset_type": "weapons",
        "prompt": "golden bow",
        "resolution": "24x24",
        "palette_size": "16",
        "provider": "openai",
        "count": 2,
        "project_name": "Memory Test",
        "mock": True # Request mock procedurally generated assets
    }
    response = client.post(
        "/api/pixel-assets/generate",
        data=json.dumps(payload),
        content_type="application/json"
    )
    assert response.status_code == 200
    data = json.loads(response.data.decode("utf-8"))
    assert data["ok"] is True
    assert len(data["assets"]) == 2
    
    asset = data["assets"][0]
    assert asset["schema"] == "spriteforge.pixel_asset.v1"
    assert asset["resolution"] == [24, 24]
    assert len(asset["palette"]["colors"]) > 0
    assert asset["memory"]["experiment_run_id"]
    assert asset["memory"]["library_asset_id"] == asset["asset_id"]

    experiment_rows = PixelAssetMemoryService.pixel_experiment_rows()
    assert len(experiment_rows) == 2
    assert experiment_rows[0]["pixel_asset"]["kind"] == "pixel_asset"

    library_path = tmp_path / "projects" / "Memory_Test" / "library.json"
    library = json.loads(library_path.read_text(encoding="utf-8"))
    assert len(library) == 2
    assert library[0]["category"] == "pixel_asset"

    history_response = client.get("/api/pixel-assets/history")
    assert history_response.status_code == 200
    history_data = json.loads(history_response.data.decode("utf-8"))
    assert len(history_data["history"]) == 2
    assert len(history_data["experiment_history"]) == 2

def test_normalize_endpoint(client, tmp_path):
    # Save a test raw image to normalize
    test_img = Image.new("RGBA", (32, 32), (255, 0, 0, 150))
    raw_dir = tmp_path / "raw_test"
    raw_dir.mkdir()
    raw_path = raw_dir / "raw.png"
    test_img.save(raw_path)

    # Monkeypatch ROOT inside routes module dynamically via sys.modules
    import sys
    routes_module = sys.modules["web_routes.routes_pixel_asset"]
    routes_module.ROOT = tmp_path

    payload = {
        "path": "raw_test/raw.png",
        "resolution": "16x16",
        "clean_alpha": True,
        "quantize_palette": True,
        "max_colors": 8,
        "remove_islands": True,
        "min_island_size": 2,
        "outline": "none"
    }

    response = client.post(
        "/api/pixel-assets/normalize",
        data=json.dumps(payload),
        content_type="application/json"
    )
    print("RESPONSE DATA:", response.data)
    assert response.status_code == 200
    data = json.loads(response.data.decode("utf-8"))
    assert data["ok"] is True
    assert "normalized_path" in data
    assert data["resolution"] == [16, 16]

def test_cleanup_selected_asset_endpoint(client):
    response = client.post(
        "/api/pixel-assets/generate",
        data=json.dumps({
            "asset_type": "items",
            "prompt": "white background coin",
            "resolution": "32x32",
            "palette_size": "16",
            "provider": "openai",
            "count": 1,
            "mock": True
        }),
        content_type="application/json"
    )
    assert response.status_code == 200
    asset = json.loads(response.data.decode("utf-8"))["assets"][0]

    cleanup = client.post(
        "/api/pixel-assets/cleanup",
        data=json.dumps({
            "asset_id": asset["asset_id"],
            "resolution": "16x16",
            "max_colors": 8,
            "remove_background": True,
            "clean_alpha": True,
            "quantize_palette": True,
            "remove_islands": True,
            "outline": "none"
        }),
        content_type="application/json"
    )
    assert cleanup.status_code == 200
    data = json.loads(cleanup.data.decode("utf-8"))
    assert data["ok"] is True
    assert data["asset"]["resolution"] == [16, 16]
    assert data["asset"]["palette"]["max_colors"] == 8
    assert data["asset"]["versions"][0]["label"] == "before cleanup"
    assert data["asset"]["cleanup_history"][0]["after_color_count"] <= 8

def test_direction_service_logic():
    # 1. Test get direction suffixes
    four_dirs = PixelDirectionService.get_direction_suffixes(4)
    assert len(four_dirs) == 4
    assert four_dirs[0][0] == "front"
    assert four_dirs[1][0] == "right"
    assert four_dirs[2][0] == "back"
    assert four_dirs[3][0] == "left"

    eight_dirs = PixelDirectionService.get_direction_suffixes(8)
    assert len(eight_dirs) == 8
    assert eight_dirs[1][0] == "front_right"

    # 2. Test consistency calculations
    img1 = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
    img1.putpixel((4, 4), (255, 0, 0, 255))
    img1.putpixel((4, 5), (255, 0, 0, 255))

    img2 = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
    img2.putpixel((4, 4), (255, 0, 0, 255))
    img2.putpixel((4, 5), (255, 0, 0, 255))

    scores = PixelDirectionService.calculate_consistency_scores([img1, img2])
    assert scores["palette_overlap"] == 1.0
    assert scores["height_consistency"] == 1.0
    assert scores["position_consistency"] == 1.0
    assert scores["overall"] == 1.0

def test_direction_generation_endpoint(client, tmp_path):
    payload = {
        "prompt": "elf rogue",
        "resolution": "32x32",
        "palette_size": 16,
        "provider": "gemini",
        "count": 4,
        "mock": True
    }

    response = client.post(
        "/api/pixel-assets/directions",
        data=json.dumps(payload),
        content_type="application/json"
    )
    print("DIRECTIONS RESPONSE DATA:", response.data)
    assert response.status_code == 200
    data = json.loads(response.data.decode("utf-8"))
    assert data["ok"] is True
    assert "batch_id" in data
    assert len(data["assets"]) == 4
    assert "consistency_scores" in data
    assert data["consistency_scores"]["overall"] >= 0.8

def test_lora_schema_validation():
    # Valid style profile with LoRA fields
    valid_profile = {
        "schema": "spriteforge.pixel_style_profile.v1",
        "style_id": "style_cyberpunk",
        "name": "Cyberpunk Retro",
        "lora_name": "neon-cyberpunk-lora",
        "lora_weight": 0.85,
        "base_model": "stable-diffusion-xl"
    }
    ok, err = validate_pixel_style_profile(valid_profile)
    assert ok is True

    # Valid weights limits boundaries
    for weight in [0.1, 1.5]:
        profile = dict(valid_profile)
        profile["lora_weight"] = weight
        ok, err = validate_pixel_style_profile(profile)
        assert ok is True

    # Invalid weights boundaries (under 0.1)
    profile = dict(valid_profile)
    profile["lora_weight"] = 0.05
    ok, err = validate_pixel_style_profile(profile)
    assert ok is False
    assert "lora_weight" in err

    # Invalid weights boundaries (over 1.5)
    profile = dict(valid_profile)
    profile["lora_weight"] = 1.6
    ok, err = validate_pixel_style_profile(profile)
    assert ok is False
    assert "lora_weight" in err

def test_loras_list_endpoint(client):
    response = client.get("/api/pixel-assets/loras")
    assert response.status_code == 200
    data = json.loads(response.data.decode("utf-8"))
    assert data["ok"] is True
    assert len(data["loras"]) == 3
    assert data["loras"][0]["lora_id"] == "pixel-art-v1"

def test_lora_payload_in_dry_run(client):
    payload = {
        "asset_type": "characters",
        "prompt": "neon ninja",
        "resolution": "32x32",
        "palette_size": "24",
        "provider": "openai",
        "lora_name": "neon-cyberpunk-lora",
        "lora_weight": 0.9,
        "base_model": "stable-diffusion-xl",
        "dry_run": True
    }
    response = client.post(
        "/api/pixel-assets/generate",
        data=json.dumps(payload),
        content_type="application/json"
    )
    assert response.status_code == 200
    data = json.loads(response.data.decode("utf-8"))
    assert data["ok"] is True
    
    contract = data["plan"]["cloud_plan"]["generation_contract"]
    assert "lora_config" in contract
    assert contract["lora_config"]["lora_name"] == "neon-cyberpunk-lora"
    assert contract["lora_config"]["lora_weight"] == 0.9

def test_mode_configs_and_mode_specific_prompt_options(client):
    response = client.get("/api/pixel-assets/modes")
    assert response.status_code == 200
    data = json.loads(response.data.decode("utf-8"))
    assert data["ok"] is True
    assert "weapons" in data["mode_configs"]
    assert "class" in data["mode_configs"]["weapons"]["controls"]

    payload = {
        "asset_type": "weapons",
        "prompt": "moonlit blade",
        "resolution": "32x32",
        "palette_size": "16",
        "provider": "openai",
        "mode_options": {
            "class": "sword",
            "material": "crystal",
            "angle": "diagonal",
            "handedness": "one-handed",
            "effects": "ice"
        },
        "dry_run": True
    }
    response = client.post(
        "/api/pixel-assets/generate",
        data=json.dumps(payload),
        content_type="application/json"
    )
    assert response.status_code == 200
    plan = json.loads(response.data.decode("utf-8"))["plan"]
    assert "class: sword" in plan["expanded_prompt"]
    assert "material: crystal" in plan["expanded_prompt"]
    assert plan["parameters"]["mode_options"]["effects"] == "ice"

def test_invalid_mode_options_are_rejected(client):
    payload = {
        "asset_type": "weapons",
        "prompt": "bad weapon",
        "resolution": "32x32",
        "palette_size": "16",
        "provider": "openai",
        "mode_options": {"class": "laser cannon"},
        "dry_run": True
    }
    response = client.post(
        "/api/pixel-assets/generate",
        data=json.dumps(payload),
        content_type="application/json"
    )
    assert response.status_code == 400
    data = json.loads(response.data.decode("utf-8"))
    assert data["ok"] is False
    assert "Invalid class" in data["message"]

def test_export_packaging_service(client):
    # 1. First generate a directions batch
    payload = {
        "prompt": "wizard cleric",
        "resolution": "32x32",
        "palette_size": 8,
        "provider": "gemini",
        "count": 4,
        "mock": True
    }
    res = client.post(
        "/api/pixel-assets/directions",
        data=json.dumps(payload),
        content_type="application/json"
    )
    data = json.loads(res.data.decode("utf-8"))
    batch_id = data["batch_id"]

    # 2. Export to Godot
    godot_zip = PixelExportService.export_batch_to_zip(batch_id, "godot")
    assert godot_zip.exists()
    with zipfile.ZipFile(godot_zip, "r") as zf:
        members = zf.namelist()
        assert "sheet.png" in members
        assert "sheet.json" in members
        assert "godot_notes.txt" in members
        assert "sheet.png.import" in members

    # 3. Export to Unity
    unity_zip = PixelExportService.export_batch_to_zip(batch_id, "unity")
    assert unity_zip.exists()
    with zipfile.ZipFile(unity_zip, "r") as zf:
        members = zf.namelist()
        assert "sheet.png" in members
        assert "sheet.json" in members
        assert "sheet.png.meta" in members

    # 4. Export to Aseprite
    ase_zip = PixelExportService.export_batch_to_zip(batch_id, "aseprite")
    assert ase_zip.exists()
    with zipfile.ZipFile(ase_zip, "r") as zf:
        members = zf.namelist()
        assert "sheet.png" in members
        assert "sheet.json" in members
        assert "sheet_aseprite.json" in members

def test_export_endpoint(client):
    # Generate a directions batch
    payload = {
        "prompt": "warrior knight",
        "resolution": "32x32",
        "palette_size": 8,
        "provider": "gemini",
        "count": 4,
        "mock": True
    }
    res = client.post(
        "/api/pixel-assets/directions",
        data=json.dumps(payload),
        content_type="application/json"
    )
    data = json.loads(res.data.decode("utf-8"))
    batch_id = data["batch_id"]

    # Request the export ZIP package
    res_export = client.get(f"/api/pixel-assets/export?batch_id={batch_id}&engine=godot")
    assert res_export.status_code == 200
    assert res_export.mimetype == "application/zip"
    assert "Content-Disposition" in res_export.headers
    assert f"attachment; filename={batch_id}_export_godot.zip" in res_export.headers["Content-Disposition"]

def test_tileset_roles_and_seam_check():
    # 1. Check roles
    td_roles = PixelTilesetService.get_tileset_roles("top-down")
    assert len(td_roles) == 10
    assert "floor" in td_roles
    assert "door" in td_roles

    # 2. Check perfect seams
    perfect_img = Image.new("RGBA", (16, 16), (200, 200, 200, 255))
    seams = PixelTilesetService.calculate_seam_deltas(perfect_img)
    assert seams["left_right_delta"] == 0.0
    assert seams["top_bottom_delta"] == 0.0

    # 3. Check imperfect seams
    bad_img = Image.new("RGBA", (16, 16), (200, 200, 200, 255))
    # Draw dark left border and light right border
    for y in range(16):
        bad_img.putpixel((0, y), (0, 0, 0, 255))
        bad_img.putpixel((15, y), (255, 255, 255, 255))
    seams_bad = PixelTilesetService.calculate_seam_deltas(bad_img)
    assert seams_bad["left_right_delta"] > 0.5

def test_tileset_generation_endpoint(client):
    payload = {
        "prompt": "ruins cobblestone",
        "tileset_type": "side-scroller",
        "resolution": "16x16",
        "palette_size": 16,
        "provider": "gemini",
        "mock": True
    }
    response = client.post(
        "/api/pixel-assets/tileset",
        data=json.dumps(payload),
        content_type="application/json"
    )
    assert response.status_code == 200
    data = json.loads(response.data.decode("utf-8"))
    assert data["ok"] is True
    assert "batch_id" in data
    assert len(data["assets"]) == 6
    
    asset = data["assets"][0]
    assert asset["asset_type"] == "tileset"
    assert asset["role"] == "ground"
    assert "seam_check" in asset["qa"]

def test_edit_asset_endpoint(client):
    # 1. Generate an asset
    payload = {
        "asset_type": "weapons",
        "prompt": "iron mace",
        "resolution": "16x16",
        "palette_size": "8",
        "provider": "openai",
        "count": 1,
        "mock": True
    }
    res = client.post(
        "/api/pixel-assets/generate",
        data=json.dumps(payload),
        content_type="application/json"
    )
    data = json.loads(res.data.decode("utf-8"))
    asset_id = data["assets"][0]["asset_id"]

    # 2. Make base64 encoded edit image (2x2 red block)
    red_2x2_base64 = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAYAAABytg0kAAAAFUlEQVR4nGP8z8Dwn4GBgYEJRIAwAB8XAgICR7MUAAAAAElFTkSuQmCC"

    payload_edit = {
        "asset_id": asset_id,
        "image_data": red_2x2_base64
    }

    res_edit = client.post(
        "/api/pixel-assets/edit",
        data=json.dumps(payload_edit),
        content_type="application/json"
    )
    print("EDIT RESPONSE DATA:", res_edit.data)
    assert res_edit.status_code == 200
    data_edit = json.loads(res_edit.data.decode("utf-8"))
    assert data_edit["ok"] is True
    assert data_edit["asset"]["qa"]["color_count"] > 0

    res_edit_alias = client.post(
        "/api/pixel-assets/edit/save",
        data=json.dumps(payload_edit),
        content_type="application/json"
    )
    assert res_edit_alias.status_code == 200

    res_version = client.post(
        "/api/pixel-assets/version/save",
        data=json.dumps({"asset_id": asset_id, "label": "red edit"}),
        content_type="application/json"
    )
    assert res_version.status_code == 200
    version_data = json.loads(res_version.data.decode("utf-8"))
    assert version_data["ok"] is True
    assert version_data["asset"]["versions"][0]["label"] == "red edit"

def test_style_extraction_endpoint(client):
    payload = {
        "asset_type": "weapons",
        "prompt": "silver dagger",
        "resolution": "16x16",
        "palette_size": "8",
        "provider": "openai",
        "count": 1,
        "mock": True
    }
    res = client.post(
        "/api/pixel-assets/generate",
        data=json.dumps(payload),
        content_type="application/json"
    )
    data = json.loads(res.data.decode("utf-8"))
    asset_id = data["assets"][0]["asset_id"]

    extract = client.post(
        "/api/pixel-assets/style/extract",
        data=json.dumps({"asset_id": asset_id, "name": "Silver Dagger Style"}),
        content_type="application/json"
    )
    assert extract.status_code == 200
    style_data = json.loads(extract.data.decode("utf-8"))
    assert style_data["ok"] is True
    assert style_data["style"]["schema"] == "spriteforge.pixel_style_profile.v1"
    assert style_data["style"]["name"] == "Silver Dagger Style"
    assert style_data["style"]["palette"]

    compare = client.post(
        "/api/pixel-assets/style/compare",
        data=json.dumps({"asset_id": asset_id, "style_id": style_data["style"]["style_id"]}),
        content_type="application/json"
    )
    assert compare.status_code == 200
    compare_data = json.loads(compare.data.decode("utf-8"))
    assert compare_data["ok"] is True
    assert compare_data["match"]["schema"] == "spriteforge.pixel_style_match.v1"
    assert compare_data["match"]["overall"] >= 0.9

def test_inpaint_service_mock(tmp_path):
    # Setup test asset
    asset_id = "pxa_test_inpaint"
    asset_dir = tmp_path / "pixel_assets" / "assets" / asset_id
    asset_dir.mkdir(parents=True, exist_ok=True)

    # Save a test 16x16 image and json manifest
    img = Image.new("RGBA", (16, 16), (200, 200, 200, 255))
    img.save(asset_dir / "asset.png")

    meta = {
        "schema": "spriteforge.pixel_asset.v1",
        "asset_id": asset_id,
        "asset_type": "weapons",
        "palette": {
            "max_colors": 16,
            "colors": ["#c8c8c8"]
        },
        "qa": {
            "color_count": 1,
            "alpha_ok": True,
            "blur_score": 0.00
        }
    }
    with open(asset_dir / "pixel_asset.json", "w") as f:
        json.dump(meta, f)

    # Encode inputs to base64 data URIs
    # 2x2 white base image
    base_data = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAYAAABytg0kAAAAFUlEQVR4nGP8z8Dwn4GBgYEJRIAwAB8XAgICR7MUAAAAAElFTkSuQmCC"
    # 2x2 mask image with non-zero alpha pixels
    mask_data = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAYAAABytg0kAAAAFUlEQVR4nGP8z8Dwn4GBgYEJRIAwAB8XAgICR7MUAAAAAElFTkSuQmCC"

    payload = {
        "asset_id": asset_id,
        "image_data": base_data,
        "mask_data": mask_data,
        "prompt": "change to blue hood",
        "mock": True
    }

    # Redirect ASSETS_DIR inside inpaint service to temp path
    import services.pixel_inpaint_service as pis_mod
    pis_mod.ASSETS_DIR = tmp_path / "pixel_assets" / "assets"

    result = PixelInpaintService.inpaint_asset(payload)
    assert result["ok"] is True
    assert result["asset"]["qa"]["color_count"] > 0
    # Confirm it added custom inpaint_history tracking field
    assert len(result["asset"]["inpaint_history"]) == 1

def test_inpaint_endpoint(client):
    # 1. Generate an asset
    payload = {
        "asset_type": "weapons",
        "prompt": "heavy club",
        "resolution": "16x16",
        "palette_size": "8",
        "provider": "openai",
        "count": 1,
        "mock": True
    }
    res = client.post(
        "/api/pixel-assets/generate",
        data=json.dumps(payload),
        content_type="application/json"
    )
    data = json.loads(res.data.decode("utf-8"))
    asset_id = data["assets"][0]["asset_id"]

    # 2. Call inpaint route
    base_data = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAYAAABytg0kAAAAFUlEQVR4nGP8z8Dwn4GBgYEJRIAwAB8XAgICR7MUAAAAAElFTkSuQmCC"
    mask_data = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAYAAABytg0kAAAAFUlEQVR4nGP8z8Dwn4GBgYEJRIAwAB8XAgICR7MUAAAAAElFTkSuQmCC"

    payload_inpaint = {
        "asset_id": asset_id,
        "image_data": base_data,
        "mask_data": mask_data,
        "prompt": "make it gold color",
        "mock": True
    }

    res_inpaint = client.post(
        "/api/pixel-assets/inpaint",
        data=json.dumps(payload_inpaint),
        content_type="application/json"
    )
    print("INPAINT ROUTE RESPONSE:", res_inpaint.data)
    assert res_inpaint.status_code == 200
    data_inpaint = json.loads(res_inpaint.data.decode("utf-8"))
    assert data_inpaint["ok"] is True
    assert len(data_inpaint["asset"]["inpaint_history"]) > 0

def test_part_apply_variants_and_accept_endpoint(client):
    response = client.post(
        "/api/pixel-assets/generate",
        data=json.dumps({
            "asset_type": "characters",
            "prompt": "zombie guard",
            "resolution": "32x32",
            "palette_size": "16",
            "provider": "openai",
            "count": 1,
            "mock": True
        }),
        content_type="application/json"
    )
    assert response.status_code == 200
    asset = json.loads(response.data.decode("utf-8"))["assets"][0]

    apply_res = client.post(
        "/api/pixel-assets/part/apply",
        data=json.dumps({
            "asset_id": asset["asset_id"],
            "part_prompt": "gold chest armor",
            "count": 3,
            "mock": True
        }),
        content_type="application/json"
    )
    assert apply_res.status_code == 200
    apply_data = json.loads(apply_res.data.decode("utf-8"))
    assert apply_data["ok"] is True
    assert apply_data["manifest"]["schema"] == "spriteforge.pixel_part_apply.v1"
    assert len(apply_data["variants"]) == 3

    accept_res = client.post(
        "/api/pixel-assets/part/accept",
        data=json.dumps({
            "asset_id": asset["asset_id"],
            "variant_path": apply_data["variants"][0]["path"],
            "label": "gold chest armor"
        }),
        content_type="application/json"
    )
    assert accept_res.status_code == 200
    accept_data = json.loads(accept_res.data.decode("utf-8"))
    assert accept_data["ok"] is True
    assert accept_data["asset"]["part_apply_history"][0]["label"] == "gold chest armor"
    assert accept_data["asset"]["versions"][0]["label"] == "before gold chest armor"

def test_reskin_variants_and_accept_endpoint(client):
    response = client.post(
        "/api/pixel-assets/generate",
        data=json.dumps({
            "asset_type": "items",
            "prompt": "small shield",
            "resolution": "32x32",
            "palette_size": "16",
            "provider": "openai",
            "count": 1,
            "mock": True
        }),
        content_type="application/json"
    )
    assert response.status_code == 200
    asset = json.loads(response.data.decode("utf-8"))["assets"][0]

    reskin_res = client.post(
        "/api/pixel-assets/reskin",
        data=json.dumps({
            "asset_id": asset["asset_id"],
            "prompt": "ice blue variant",
            "count": 4,
            "mock": True
        }),
        content_type="application/json"
    )
    assert reskin_res.status_code == 200
    reskin_data = json.loads(reskin_res.data.decode("utf-8"))
    assert reskin_data["ok"] is True
    assert reskin_data["manifest"]["schema"] == "spriteforge.pixel_reskin.v1"
    assert len(reskin_data["variants"]) == 4

    accept_res = client.post(
        "/api/pixel-assets/reskin/accept",
        data=json.dumps({
            "asset_id": asset["asset_id"],
            "variant_path": reskin_data["variants"][0]["path"],
            "label": "ice blue variant"
        }),
        content_type="application/json"
    )
    assert accept_res.status_code == 200
    accept_data = json.loads(accept_res.data.decode("utf-8"))
    assert accept_data["ok"] is True
    assert accept_data["asset"]["reskin_history"][0]["label"] == "ice blue variant"
    assert accept_data["asset"]["versions"][0]["label"] == "before ice blue variant"

def test_animation_generation_service(tmp_path):
    # Setup test asset
    asset_id = "pxa_test_animate"
    asset_dir = tmp_path / "pixel_assets" / "assets" / asset_id
    asset_dir.mkdir(parents=True, exist_ok=True)

    # Save a test 16x16 reference image
    img = Image.new("RGBA", (16, 16), (150, 150, 150, 255))
    img.save(asset_dir / "asset.png")

    payload = {
        "asset_id": asset_id,
        "action_type": "walk",
        "frame_count": 4,
        "fps": 10,
        "mock": True
    }

    # Redirect directories
    import services.pixel_animation_service as pas_srv_mod
    pas_srv_mod.ASSETS_DIR = tmp_path / "pixel_assets" / "assets"
    pas_srv_mod.BATCHES_DIR = tmp_path / "pixel_assets" / "batches"

    result = PixelAnimationService.generate_animation(payload)
    assert result["ok"] is True
    
    manifest = result["manifest"]
    assert manifest["schema"] == "spriteforge.pixel_animation.v1"
    assert manifest["frame_count"] == 4
    assert manifest["fps"] == 10
    
    # Confirm output files exist
    batch_dir = tmp_path / "pixel_assets" / "batches" / manifest["batch_id"]
    assert (batch_dir / "sheet.png").exists()
    assert (batch_dir / "preview.gif").exists()
    assert (batch_dir / "animation.json").exists()

    # Confirm QA scores are calculated
    qa = manifest["qa"]
    assert "bbox_jitter" in qa
    assert "palette_drift" in qa
    assert "loop_continuity" in qa

def test_animate_endpoint(client):
    # 1. Generate an asset
    payload = {
        "asset_type": "characters",
        "prompt": "forest ranger",
        "resolution": "16x16",
        "palette_size": "16",
        "provider": "gemini",
        "count": 1,
        "mock": True
    }
    res = client.post(
        "/api/pixel-assets/generate",
        data=json.dumps(payload),
        content_type="application/json"
    )
    data = json.loads(res.data.decode("utf-8"))
    asset_id = data["assets"][0]["asset_id"]

    # 2. Call animate endpoint
    payload_anim = {
        "asset_id": asset_id,
        "action_type": "run",
        "frame_count": 6,
        "fps": 12,
        "mock": True
    }
    res_anim = client.post(
        "/api/pixel-assets/animate",
        data=json.dumps(payload_anim),
        content_type="application/json"
    )
    assert res_anim.status_code == 200
    data_anim = json.loads(res_anim.data.decode("utf-8"))
    assert data_anim["ok"] is True
    assert data_anim["manifest"]["frame_count"] == 6
    assert data_anim["manifest"]["fps"] == 12

def test_transfer_animation_service(tmp_path):
    # Create mock source sheet image
    source_sheet_path = tmp_path / "source_sheet.png"
    # A 32x16 sheet containing 2 frames of size 16x16
    src_img = Image.new("RGBA", (32, 16), (255, 255, 255, 255))
    src_img.save(source_sheet_path)

    payload = {
        "source_sheet_path": str(source_sheet_path),
        "rows": 1,
        "cols": 2,
        "prompt": "make it gold knight style",
        "mock": True
    }

    # Redirect paths
    import services.pixel_transfer_service as pts_srv_mod
    pts_srv_mod.ASSETS_DIR = tmp_path / "pixel_assets" / "assets"
    pts_srv_mod.BATCHES_DIR = tmp_path / "pixel_assets" / "batches"

    result = PixelTransferService.transfer_animation(payload)
    assert result["ok"] is True
    manifest = result["manifest"]
    assert manifest["schema"] == "spriteforge.pixel_animation_transfer.v1"
    assert manifest["frame_count"] == 2
    assert manifest["resolution"] == [16, 16]

    batch_dir = tmp_path / "pixel_assets" / "batches" / manifest["batch_id"]
    assert (batch_dir / "sheet_transferred.png").exists()
    assert (batch_dir / "preview.gif").exists()
    assert (batch_dir / "transfer_manifest.json").exists()

def test_transfer_endpoint(client, tmp_path):
    # Create mock source sheet in workspace path
    source_sheet_path = tmp_path / "source_sheet_route.png"
    src_img = Image.new("RGBA", (32, 16), (200, 200, 200, 255))
    src_img.save(source_sheet_path)

    # Monkeypatch the assets/batches inside routes module
    import sys
    routes_module = sys.modules["web_routes.routes_pixel_asset"]
    routes_module.ROOT = tmp_path

    payload = {
        "source_sheet_path": str(source_sheet_path),
        "rows": 1,
        "cols": 2,
        "prompt": "change to blue wizard",
        "mock": True
    }

    response = client.post(
        "/api/pixel-assets/animation-transfer",
        data=json.dumps(payload),
        content_type="application/json"
    )
    assert response.status_code == 200
    data = json.loads(response.data.decode("utf-8"))
    assert data["ok"] is True
    assert data["manifest"]["frame_count"] == 2

def test_rig_render_service(tmp_path):
    # Setup test asset
    asset_id = "pxa_test_rig"
    asset_dir = tmp_path / "pixel_assets" / "assets" / asset_id
    asset_dir.mkdir(parents=True, exist_ok=True)

    # Save a test 16x16 reference image
    img = Image.new("RGBA", (16, 16), (180, 180, 180, 255))
    img.save(asset_dir / "asset.png")

    payload = {
        "asset_id": asset_id,
        "bones": [],
        "keyframes": [],
        "frame_count": 4,
        "mock": True
    }

    # Redirect paths
    import services.pixel_rig_service as prs_srv_mod
    prs_srv_mod.ASSETS_DIR = tmp_path / "pixel_assets" / "assets"
    prs_srv_mod.BATCHES_DIR = tmp_path / "pixel_assets" / "batches"

    result = PixelRigService.render_rig_animation(payload)
    assert result["ok"] is True
    manifest = result["manifest"]
    assert manifest["schema"] == "spriteforge.pixel_skeletal_rig.v1"
    assert manifest["frame_count"] == 4
    assert "spine_compat" in manifest

    batch_dir = tmp_path / "pixel_assets" / "batches" / manifest["batch_id"]
    assert (batch_dir / "sheet.png").exists()
    assert (batch_dir / "preview.gif").exists()
    assert (batch_dir / "rig_manifest.json").exists()

def test_rig_render_endpoint(client):
    # 1. Generate a character asset
    payload = {
        "asset_type": "characters",
        "prompt": "heavy knight",
        "resolution": "16x16",
        "palette_size": "16",
        "provider": "gemini",
        "count": 1,
        "mock": True
    }
    res = client.post(
        "/api/pixel-assets/generate",
        data=json.dumps(payload),
        content_type="application/json"
    )
    data = json.loads(res.data.decode("utf-8"))
    asset_id = data["assets"][0]["asset_id"]

    # 2. Call rig render route
    payload_rig = {
        "asset_id": asset_id,
        "bones": [],
        "keyframes": [],
        "frame_count": 4,
        "mock": True
    }
    res_rig = client.post(
        "/api/pixel-assets/rig/render",
        data=json.dumps(payload_rig),
        content_type="application/json"
    )
    assert res_rig.status_code == 200
    data_rig = json.loads(res_rig.data.decode("utf-8"))
    assert data_rig["ok"] is True
    assert data_rig["manifest"]["frame_count"] == 4

    res_skeleton = client.post(
        "/api/pixel-assets/skeleton/render",
        data=json.dumps(payload_rig),
        content_type="application/json"
    )
    assert res_skeleton.status_code == 200
    data_skeleton = json.loads(res_skeleton.data.decode("utf-8"))
    assert data_skeleton["ok"] is True
    assert data_skeleton["manifest"]["schema"] == "spriteforge.pixel_skeletal_rig.v1"

def test_pack_generation_service(tmp_path):
    # Redirect paths inside pack service to temp directories
    import services.pixel_pack_service as pps_mod
    pps_mod.PACKS_DIR = tmp_path / "pixel_assets" / "packs"
    import services.pixel_asset_service as pas_mod
    pas_mod.ASSETS_DIR = tmp_path / "pixel_assets" / "assets"
    pas_mod.BATCHES_DIR = tmp_path / "pixel_assets" / "batches"

    payload = {
        "recipe_type": "rpg_starter",
        "style_profile_id": "style_fantasy",
        "mock": True
    }

    result = PixelPackService.generate_pack(payload)
    assert result["ok"] is True
    
    manifest = result["manifest"]
    assert manifest["schema"] == "spriteforge.pixel_pack.v1"
    assert manifest["recipe_type"] == "rpg_starter"
    assert len(manifest["assets"]) == 6

    # Verify manifest exists
    pack_dir = tmp_path / "pixel_assets" / "packs" / manifest["pack_id"]
    assert (pack_dir / "pack_manifest.json").exists()

    # Test release ZIP building
    zip_path = PixelPackService.export_pack_to_zip(manifest["pack_id"])
    assert zip_path.exists()
    
    with zipfile.ZipFile(zip_path, "r") as zf:
        members = zf.namelist()
        assert "pack_manifest.json" in members
        assert "catalog.html" in members
        # Assets are stored under assets/{asset_id}/ subfolders to avoid name collisions
        assert any("/" in m and m.startswith("assets/") for m in members)

def test_pack_endpoints(client, tmp_path):
    # Monkeypatch the pack folder paths
    import services.pixel_pack_service as pps_mod
    pps_mod.PACKS_DIR = tmp_path / "pixel_assets" / "packs"
    import services.pixel_asset_service as pas_mod
    pas_mod.ASSETS_DIR = tmp_path / "pixel_assets" / "assets"
    pas_mod.BATCHES_DIR = tmp_path / "pixel_assets" / "batches"

    payload = {
        "recipe_type": "potion_shop",
        "style_profile_id": "",
        "mock": True
    }

    response = client.post(
        "/api/pixel-assets/pack/generate",
        data=json.dumps(payload),
        content_type="application/json"
    )
    print("RESPONSE STATUS:", response.status_code)
    print("RESPONSE DATA:", response.data)
    assert response.status_code == 200
    data = json.loads(response.data.decode("utf-8"))
    assert data["ok"] is True
    
    pack_id = data["manifest"]["pack_id"]
    assert len(data["manifest"]["assets"]) == 6

    # Verify export endpoint
    res_export = client.get(f"/api/pixel-assets/pack/export?pack_id={pack_id}")
    assert res_export.status_code == 200
    assert res_export.mimetype == "application/zip"
    assert "Content-Disposition" in res_export.headers
    assert f"attachment; filename={pack_id}_release.zip" in res_export.headers["Content-Disposition"]

def test_recipe_service_and_endpoints(client, tmp_path, monkeypatch):
    import services.pixel_recipe_service as recipe_mod
    import services.pixel_pack_service as pps_mod

    recipe_dir = tmp_path / "pixel_assets" / "recipes"
    monkeypatch.setattr(recipe_mod, "RECIPES_DIR", recipe_dir)
    monkeypatch.setattr(pps_mod, "PACKS_DIR", tmp_path / "pixel_assets" / "packs")

    recipes = PixelRecipeService.list_recipes()
    assert any(recipe["recipe_id"] == "ui_hud_pack" for recipe in recipes)

    custom = {
        "schema": "spriteforge.pixel_recipe.v1",
        "recipe_id": "recipe_test_shop",
        "name": "Test Shop",
        "items": [
            {"type": "potions", "prompt": "tiny green potion", "resolution": "16x16", "count": 1},
            {"type": "items", "prompt": "small wooden crate", "resolution": "16x16", "count": 1},
        ],
    }
    saved = client.post(
        "/api/pixel-assets/recipes/save",
        data=json.dumps(custom),
        content_type="application/json"
    )
    assert saved.status_code == 200
    saved_data = json.loads(saved.data.decode("utf-8"))
    assert saved_data["ok"] is True
    assert saved_data["recipe"]["recipe_id"] == "recipe_test_shop"

    listed = client.get("/api/pixel-assets/recipes")
    assert listed.status_code == 200
    listed_data = json.loads(listed.data.decode("utf-8"))
    assert any(recipe["recipe_id"] == "recipe_test_shop" for recipe in listed_data["recipes"])

    exported = client.get("/api/pixel-assets/recipes/export?recipe_id=recipe_test_shop")
    assert exported.status_code == 200
    assert exported.mimetype == "application/json"

    imported = client.post(
        "/api/pixel-assets/recipes/import",
        data=json.dumps({
            **custom,
            "recipe_id": "imported_shop",
            "name": "Imported Shop",
        }),
        content_type="application/json"
    )
    assert imported.status_code == 200
    imported_data = json.loads(imported.data.decode("utf-8"))
    assert imported_data["ok"] is True
    assert imported_data["recipe"]["recipe_id"] == "recipe_imported_shop"

    generated = client.post(
        "/api/pixel-assets/pack/build",
        data=json.dumps({"recipe_type": "recipe_test_shop", "mock": True}),
        content_type="application/json"
    )
    assert generated.status_code == 200
    generated_data = json.loads(generated.data.decode("utf-8"))
    assert generated_data["ok"] is True
    assert generated_data["manifest"]["recipe_name"] == "Test Shop"
    assert len(generated_data["manifest"]["assets"]) == 2

def test_pixel_failure_explainers_and_endpoint(client):
    missing_key = explain_pixel_failure("Key Validation Failed: Missing local API key.")
    assert missing_key["code"] == "pixel_missing_provider_key"
    assert "Provider key" in missing_key["title"]

    too_many_colors = explain_pixel_failure("QA failed: too many colors in palette")
    assert too_many_colors["code"] == "pixel_too_many_colors"

    seam = explain_pixel_failure("tile seam check failed on left edge")
    assert seam["code"] == "pixel_tile_seam"

    response = client.post(
        "/api/pixel-assets/failure/explain",
        data=json.dumps({"message": "No alpha channel detected"}),
        content_type="application/json"
    )
    assert response.status_code == 200
    data = json.loads(response.data.decode("utf-8"))
    assert data["ok"] is True
    assert data["explainer"]["code"] == "pixel_no_alpha"

def test_pixel_studio_polish_ui_assets():
    html = (APP / "web" / "components" / "pixel_studio.html").read_text(encoding="utf-8")
    js = (APP / "web" / "js" / "pixel_studio.js").read_text(encoding="utf-8")

    assert 'id="pixelWorkflowCards"' in html
    assert 'data-pixel-workflow="first_asset"' in html
    assert 'id="pixelFailurePanel"' in html
    assert "showPixelFailure" in js
    assert "/api/pixel-assets/failure/explain" in js
    assert "applyPixelWorkflow" in js
    assert 'id="inspectorGenerateLikeBtn"' in html
    assert 'id="inspectorMatchStyleBtn"' in html
    assert "/api/pixel-assets/style/compare" in js
    assert "compareActiveAssetToStyle" in js
    assert 'id="btnEditorLine"' in html
    assert 'id="btnEditorRect"' in html
    assert 'id="btnEditorSelect"' in html
    assert 'id="btnEditorMove"' in html
    assert 'id="btnEditorImport"' in html
    assert 'id="btnEditorExport"' in html
    assert 'id="btnEditorVersion"' in html
    assert "drawEditorLine" in js
    assert "drawEditorRectangle" in js
    assert "/api/pixel-assets/edit/save" in js
    assert "/api/pixel-assets/version/save" in js
    assert 'id="pixelRecipeImportBtn"' in html
    assert "/api/pixel-assets/recipes/import" in js
    assert 'id="inspectorApplyPartBtn"' in html
    assert 'id="pixelPartApplyModal"' in html
    assert 'id="pixelPartVariantGrid"' in html
    assert "/api/pixel-assets/part/apply" in js
    assert "/api/pixel-assets/part/accept" in js
    assert "renderPartVariants" in js
    assert 'id="inspectorReskinBtn"' in html
    assert 'id="pixelReskinModal"' in html
    assert 'id="pixelReskinVariantGrid"' in html
    assert "/api/pixel-assets/reskin" in js
    assert "/api/pixel-assets/reskin/accept" in js
    assert "renderReskinVariants" in js
    assert 'id="inspectorCleanupBtn"' in html
    assert "/api/pixel-assets/cleanup" in js
    assert "cleanupSelectedAsset" in js
