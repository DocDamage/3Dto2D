import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "app"
sys.path.insert(0, str(APP))


def _write_lpc_sheet(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.rectangle((20, 12, 44, 54), fill=(190, 130, 80, 255))
    img.save(path)


def test_lpc_parts_scan_indexes_paper_doll_layers(tmp_path):
    from services.lpc_parts_service import scan_lpc_parts

    root = tmp_path / "Universal-LPC"
    _write_lpc_sheet(root / "dist" / "spritesheets" / "body" / "bodies" / "male" / "idle.png")
    _write_lpc_sheet(root / "dist" / "spritesheets" / "arms" / "armour" / "plate" / "male" / "spellcast.png")

    out = tmp_path / "catalog"
    result = scan_lpc_parts(root, output_dir=out, thumbnail_limit=2)

    assert result["schema"] == "spriteforge.lpc_parts_catalog.v1"
    assert result["part_count"] == 2
    assert result["readable_part_count"] == 2
    assert result["unreadable_part_count"] == 0
    assert result["category_counts"]["arms"] == 1
    assert result["action_counts"]["cast"] == 1
    assert result["body_type_counts"]["male"] == 2
    assert result["parts"][0]["layer_order"] >= 0
    assert result["samples"][0]["thumbnail_data_uri"].startswith("data:image/png;base64,")
    assert (out / "catalog.json").exists()


def test_lpc_part_dataset_writes_captions(tmp_path):
    from services.lpc_parts_service import build_lpc_part_dataset

    root = tmp_path / "Universal-LPC"
    _write_lpc_sheet(root / "dist" / "spritesheets" / "hair" / "plain" / "male" / "walk.png")

    out = tmp_path / "dataset"
    result = build_lpc_part_dataset(root, output_dir=out, trigger="lpc_parts")

    assert result["dataset_kind"] == "lpc_parts"
    assert result["sample_count"] == 1
    captions = sorted((out / "captions").glob("*.txt"))
    assert len(captions) == 1
    text = captions[0].read_text(encoding="utf-8")
    assert "lpc_parts" in text
    assert "hair layer" in text
    assert (out / "manifest.json").exists()


def test_lpc_composer_layers_matching_parts(tmp_path):
    from services.lpc_parts_service import compose_lpc_character

    root = tmp_path / "Universal-LPC"
    _write_lpc_sheet(root / "dist" / "spritesheets" / "body" / "bodies" / "male" / "idle.png")
    _write_lpc_sheet(root / "dist" / "spritesheets" / "hair" / "plain" / "male" / "idle.png")

    out = tmp_path / "composed"
    result = compose_lpc_character(
        root,
        output_dir=out,
        action="idle",
        body_type="male",
        selections={"hair": "plain"},
        name="test_hero",
    )

    assert result["schema"] == "spriteforge.lpc_composition.v1"
    assert result["name"] == "test_hero"
    assert result["frame_count"] == 1
    assert len(result["layers"]) == 2
    assert result["thumbnail_data_uri"].startswith("data:image/png;base64,")
    assert (out / "sheet.png").exists()
    assert (out / "sheet.json").exists()
    assert (out / "lpc_composition.json").exists()


def test_lpc_composer_allows_adult_accessories_on_male_body(tmp_path):
    from services.lpc_parts_service import compose_lpc_character

    root = tmp_path / "Universal-LPC"
    _write_lpc_sheet(root / "dist" / "spritesheets" / "body" / "bodies" / "male" / "idle.png")
    _write_lpc_sheet(root / "dist" / "spritesheets" / "hair" / "afro" / "adult" / "idle.png")

    result = compose_lpc_character(root, output_dir=tmp_path / "composed", selections={"hair": "afro"})

    assert [layer["category"] for layer in result["layers"]] == ["body", "hair"]
    assert result["missing"] == []


def test_lpc_composer_preserves_repeated_category_selections_and_aliases(tmp_path):
    from services.lpc_parts_service import compose_lpc_character, lpc_catalog_options, scan_lpc_parts

    root = tmp_path / "Universal-LPC"
    _write_lpc_sheet(root / "spritesheets" / "body" / "bodies" / "male" / "idle.png")
    _write_lpc_sheet(root / "spritesheets" / "body" / "wings" / "bat" / "adult" / "bg" / "idle.png")
    _write_lpc_sheet(root / "spritesheets" / "body" / "tail" / "lizard" / "adult" / "fg" / "idle.png")
    _write_lpc_sheet(root / "spritesheets" / "weapon" / "sword" / "male" / "slash" / "steel.png")

    catalog = scan_lpc_parts(root, thumbnail_limit=0)
    slash_weapon = next(part for part in catalog["parts"] if part["category"] == "weapon")
    assert slash_weapon["action"] == "slash"
    assert slash_weapon["variant"] == "sword"

    options = lpc_catalog_options(root, categories=["weapons", "ammo"])
    assert "weapons" in options["options"]

    result = compose_lpc_character(
        root,
        output_dir=tmp_path / "composed",
        selections=[
            {"category": "body", "query": "wings bat"},
            {"category": "body", "query": "tail lizard"},
        ],
    )

    assert [layer["category"] for layer in result["layers"]] == ["body", "body", "body"]
    assert result["selections"]["body"] == ["bodies", "wings bat", "tail lizard"]
    assert result["missing"] == []


def test_lpc_rules_palettes_presets_and_preview(tmp_path, monkeypatch):
    from services import lpc_parts_service
    from services.lpc_parts_service import (
        compose_lpc_character,
        compose_lpc_batch,
        delete_lpc_preset,
        list_lpc_presets,
        lpc_palette_options,
        lpc_rules_report,
        preview_lpc_dataset,
        save_lpc_preset,
    )

    monkeypatch.setattr(lpc_parts_service, "LPC_PRESETS_PATH", tmp_path / "lpc_presets.json")
    root = tmp_path / "Universal-LPC"
    _write_lpc_sheet(root / "spritesheets" / "body" / "bodies" / "male" / "idle.png")
    _write_lpc_sheet(root / "spritesheets" / "hair" / "plain" / "male" / "idle.png")
    _write_lpc_sheet(root / "spritesheets" / "weapon" / "sword" / "male" / "slash" / "steel.png")

    palettes = lpc_palette_options()
    assert any(item["id"] == "moonlit" for item in palettes["palettes"])

    composed = compose_lpc_character(
        root,
        output_dir=tmp_path / "composed",
        selections={"hair": "plain"},
        palette="moonlit",
    )
    assert composed["palette"] == "moonlit"
    assert composed["rules"]["ok"] is True

    rules = lpc_rules_report(root, action="idle", body_type="male", selections={"weapons": "sword"})
    assert rules["ok"] is True
    assert any("not for the idle action" in issue["message"] for issue in rules["issues"])
    assert rules["resolved"][0]["category"] == "body"

    saved = save_lpc_preset({
        "name": "Hero Recipe",
        "action": "idle",
        "body_type": "male",
        "palette": "moonlit",
        "selections": [{"category": "hair", "query": "plain"}],
    })
    assert saved["preset"]["id"] == "Hero_Recipe"
    listed = list_lpc_presets()
    assert listed["presets"][0]["palette"] == "moonlit"
    removed = delete_lpc_preset("Hero Recipe")
    assert removed["removed"] == 1

    batch = compose_lpc_batch(
        root,
        output_dir=tmp_path / "batch",
        count=1,
        action="idle",
        body_type="male",
        categories=["hair"],
        palette="ghost",
    )
    preview = preview_lpc_dataset(batch["output_dir"], limit=8)
    assert preview["schema"] == "spriteforge.lpc_dataset_preview.v1"
    assert preview["samples"][0]["thumbnail_data_uri"].startswith("data:image/png;base64,")


def test_lpc_catalog_options_and_batch_composition(tmp_path):
    from services.lpc_parts_service import lpc_catalog_options, compose_lpc_batch, qa_lpc_dataset, lpc_lora_prefill

    root = tmp_path / "Universal-LPC"
    for body in ["male", "female"]:
        for action in ["idle", "walk"]:
            _write_lpc_sheet(root / "dist" / "spritesheets" / "body" / "bodies" / body / f"{action}.png")
            _write_lpc_sheet(root / "dist" / "spritesheets" / "hair" / "afro" / "adult" / f"{action}.png")
            _write_lpc_sheet(root / "dist" / "spritesheets" / "legs" / "pants" / body / f"{action}.png")

    options = lpc_catalog_options(root, categories=["hair", "legs"])
    assert options["schema"] == "spriteforge.lpc_catalog_options.v1"
    assert any(item["value"] == "afro" for item in options["options"]["hair"])
    assert any(item["value"] == "pants" for item in options["options"]["legs"])

    batch = compose_lpc_batch(
        root,
        output_dir=tmp_path / "batch",
        count=3,
        action="idle",
        body_type="male",
        actions=["idle", "walk"],
        body_types=["male", "female"],
        categories=["hair", "legs"],
        seed=7,
    )

    assert batch["schema"] == "spriteforge.lpc_composed_batch.v1"
    assert batch["dataset_kind"] == "lpc_composed"
    assert batch["sample_count"] == 3
    assert batch["actions"] == ["idle", "walk"]
    assert batch["body_types"] == ["male", "female"]
    assert sum(batch["balance"].values()) == 3
    assert (tmp_path / "batch" / "manifest.json").exists()
    assert (tmp_path / "batch" / "images").is_dir()
    assert (tmp_path / "batch" / "captions").is_dir()
    assert len(list((tmp_path / "batch" / "images").glob("*.png"))) == 3
    assert len(list((tmp_path / "batch" / "captions").glob("*.txt"))) == 3
    assert (tmp_path / "batch" / "README_TRAINING_DATASET.md").exists()
    assert all("caption" in sample for sample in batch["samples"])
    assert all("training_image" in sample for sample in batch["samples"])

    qa = qa_lpc_dataset(tmp_path / "batch", min_layers=2)
    assert qa["schema"] == "spriteforge.lpc_dataset_qa.v1"
    assert qa["ok"] is True
    assert qa["sample_count"] == 3
    assert qa["image_count"] == 3
    assert qa["caption_count"] == 3
    assert (tmp_path / "batch" / "qa_report.json").exists()

    strict_qa = qa_lpc_dataset(tmp_path / "batch", min_layers=5)
    assert strict_qa["ok"] is True
    assert any(issue["severity"] == "warn" for issue in strict_qa["issues"])

    prefill = lpc_lora_prefill(tmp_path / "batch")
    assert prefill["schema"] == "spriteforge.lpc_lora_prefill.v1"
    assert prefill["recommendation"]["dataset_dir"] == str((tmp_path / "batch").resolve())
    assert prefill["recommendation"]["trigger"] == "lpc_composed"
    assert prefill["recommendation"]["resolution"] == 512
    assert (tmp_path / "batch" / "lora_prefill.json").exists()


def test_lpc_parts_endpoints(tmp_path):
    from flask import Flask
    from services import lpc_parts_service
    from web_routes.routes_misc import routes_misc

    lpc_parts_service.LPC_PRESETS_PATH = tmp_path / "lpc_presets.json"
    root = tmp_path / "Universal-LPC"
    _write_lpc_sheet(root / "dist" / "spritesheets" / "feet" / "shoes" / "female" / "idle.png")
    _write_lpc_sheet(root / "dist" / "spritesheets" / "body" / "bodies" / "female" / "idle.png")
    _write_lpc_sheet(root / "dist" / "spritesheets" / "weapon" / "sword" / "female" / "slash" / "steel.png")

    app = Flask(__name__)
    app.register_blueprint(routes_misc)
    response = app.test_client().post(
        "/api/lpc/parts/scan",
        json={"source_dir": str(root), "output": str(tmp_path / "catalog"), "thumbnail_limit": 1},
    )
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["part_count"] == 3
    assert payload["category_counts"]["feet"] == 1

    compose_response = app.test_client().post(
        "/api/lpc/compose",
        json={
            "source_dir": str(root),
            "compose_output": str(tmp_path / "composed"),
            "compose_action": "idle",
            "body_type": "female",
            "selections": {"feet": "shoes"},
            "palette": "ember",
        },
    )
    composed = compose_response.get_json()

    assert compose_response.status_code == 200
    assert composed["ok"] is True
    assert composed["palette"] == "ember"
    assert composed["sheet"].endswith("sheet.png")

    palette_response = app.test_client().get("/api/lpc/palettes")
    assert palette_response.status_code == 200
    assert palette_response.get_json()["palettes"]

    rules_response = app.test_client().post(
        "/api/lpc/rules",
        json={
            "source_dir": str(root),
            "action": "idle",
            "body_type": "female",
            "selections": {"weapons": "sword"},
        },
    )
    assert rules_response.status_code == 200
    assert any("not for the idle action" in issue["message"] for issue in rules_response.get_json()["issues"])

    save_preset_response = app.test_client().post(
        "/api/lpc/presets",
        json={
            "name": "Endpoint Hero",
            "action": "idle",
            "body_type": "female",
            "palette": "ember",
            "selections": [{"category": "feet", "query": "shoes"}],
        },
    )
    assert save_preset_response.status_code == 200
    presets_response = app.test_client().get("/api/lpc/presets")
    assert presets_response.status_code == 200
    assert presets_response.get_json()["presets"][0]["id"] == "Endpoint_Hero"

    options_response = app.test_client().post(
        "/api/lpc/options",
        json={"source_dir": str(root), "categories": ["feet"]},
    )
    assert options_response.status_code == 200
    assert options_response.get_json()["options"]["feet"]

    batch_response = app.test_client().post(
        "/api/lpc/batch-compose",
        json={
            "source_dir": str(root),
            "batch_output": str(tmp_path / "batch"),
            "batch_count": 2,
            "batch_action": "idle",
            "batch_actions": "idle,walk",
            "body_type": "female",
            "batch_body_types": "female",
            "batch_categories": "feet",
            "batch_seed": "4",
        },
    )
    assert batch_response.status_code == 200
    assert batch_response.get_json()["sample_count"] == 2

    preview_response = app.test_client().post(
        "/api/lpc/dataset-preview",
        json={"dataset_dir": str(tmp_path / "batch"), "limit": 2},
    )
    assert preview_response.status_code == 200
    assert preview_response.get_json()["preview_count"] == 2

    qa_response = app.test_client().post(
        "/api/lpc/dataset-qa",
        json={"dataset_dir": str(tmp_path / "batch"), "min_layers": 2},
    )
    assert qa_response.status_code == 200
    assert qa_response.get_json()["schema"] == "spriteforge.lpc_dataset_qa.v1"

    prefill_response = app.test_client().post(
        "/api/lpc/lora-prefill",
        json={"dataset_dir": str(tmp_path / "batch")},
    )
    assert prefill_response.status_code == 200
    assert prefill_response.get_json()["recommendation"]["name"] == "lpc_composed_lora"


def test_training_lab_exposes_lpc_parts_controls():
    html = (APP / "web" / "components" / "training.html").read_text(encoding="utf-8")
    js = (APP / "web" / "js" / "app_forms.js").read_text(encoding="utf-8")

    assert 'id="lpcPartsForm"' in html
    assert 'id="scanLpcParts"' in html
    assert 'id="buildLpcPartDataset"' in html
    assert 'id="lpcComposerForm"' in html
    assert 'id="composeLpcCharacter"' in html
    assert 'id="loadLpcComposerOptions"' in html
    assert 'id="lpcBatchComposerForm"' in html
    assert 'id="composeLpcBatch"' in html
    assert 'id="qaLpcBatch"' in html
    assert 'id="useLpcBatchForLora"' in html
    assert 'id="prepareLpcLoraRun"' in html
    assert 'name="min_layers"' in html
    assert 'name="batch_actions"' in html
    assert 'name="batch_body_types"' in html
    assert "/api/lpc/parts/scan" in js
    assert "/api/lpc/parts/dataset" in js
    assert "/api/lpc/compose" in js
    assert "/api/lpc/options" in js
    assert "/api/lpc/batch-compose" in js
    assert "/api/lpc/dataset-qa" in js
    assert "/api/lpc/lora-prefill" in js
    assert "/api/lpc/dataset-preview" in js
    assert "function qaLpcBatch()" in js
    assert "async function useLpcBatchForLora()" in js
    assert "async function prepareLpcLoraRun()" in js
    assert "runAction('lora_training'" in js


def test_lpc_source_paths_accept_app_and_repo_relative_forms(tmp_path, monkeypatch):
    from services import lpc_parts_service

    app_root = tmp_path / "app"
    repo_root = tmp_path
    source = app_root / "input" / "lpc_assets" / "Universal-LPC-Spritesheet-Character-Generator"
    _write_lpc_sheet(source / "dist" / "spritesheets" / "feet" / "shoes" / "female" / "idle.png")

    monkeypatch.setattr(lpc_parts_service, "ROOT", app_root)
    monkeypatch.setattr(lpc_parts_service, "REPO_ROOT", repo_root)
    monkeypatch.setattr(lpc_parts_service, "DEFAULT_OUTPUT", tmp_path / "output" / "lpc_parts")
    monkeypatch.setattr(lpc_parts_service, "DEFAULT_LPC_SOURCE", source)

    app_relative = lpc_parts_service.lpc_catalog_options(
        "input/lpc_assets/Universal-LPC-Spritesheet-Character-Generator",
        categories=["feet"],
    )
    repo_relative = lpc_parts_service.lpc_catalog_options(
        "app/input/lpc_assets/Universal-LPC-Spritesheet-Character-Generator",
        categories=["feet"],
    )

    assert app_relative["options"]["feet"]
    assert repo_relative["options"]["feet"]


def test_dedicated_lpc_tab_is_wired():
    html = (APP / "web" / "components" / "lpc.html").read_text(encoding="utf-8")
    index = (APP / "web" / "index.html").read_text(encoding="utf-8")
    ux = (APP / "web" / "js" / "ux_enhancements.js").read_text(encoding="utf-8")
    js = (APP / "web" / "js" / "app_forms.js").read_text(encoding="utf-8")
    css = (APP / "web" / "css" / "components.css").read_text(encoding="utf-8")

    assert 'id="lpcPreviewImage"' in html
    assert 'id="lpcPreviewWindow"' in html
    assert 'id="lpcZoom"' in html
    assert 'id="lpcComposeCharacter"' in html
    assert 'id="lpcBuildBatch"' in html
    assert 'id="lpcPrepareLora"' in html
    assert 'id="lpcPresetSelect"' in html
    assert 'id="lpcSavePreset"' in html
    assert 'id="lpcCheckRules"' in html
    assert 'id="lpcRulesPanel"' in html
    assert 'id="lpcBatchGallery"' in html
    assert 'data-lpc-slot="hair"' in html
    assert 'data-lpc-slot="torso"' in html
    assert 'data-lpc-slot="weapons"' in html
    assert 'data-view="lpc"' in index
    assert 'id="view-lpc"' in index
    assert "'ab_runs', 'library', 'qa_dashboard', 'training', 'lpc'" in index
    assert "lpc: 'LPC'" in ux
    assert "'guide', 'training', 'generate', 'lpc', 'pixel_studio', 'convert'" in ux
    assert "async function loadDedicatedLpcPickers" in js
    assert "function dedicatedLpcSetZoom" in js
    assert "async function composeDedicatedLpcCharacter" in js
    assert "async function buildDedicatedLpcBatch" in js
    assert "async function qaDedicatedLpcBatch" in js
    assert "async function prepareDedicatedLpcLora" in js
    assert "async function loadDedicatedLpcPalettes" in js
    assert "async function loadDedicatedLpcPresets" in js
    assert "async function checkDedicatedLpcRules" in js
    assert "async function saveDedicatedLpcPreset" in js
    assert "/api/lpc/options" in js
    assert "/api/lpc/compose" in js
    assert "/api/lpc/rules" in js
    assert "/api/lpc/presets" in js
    assert "/api/lpc/palettes" in js
    assert "/api/lpc/batch-compose" in js
    assert "/api/lpc/dataset-qa" in js
    assert ".lpc-preview-window" in css
    assert ".lpc-batch-gallery" in css
    assert (ROOT / "RUN_LPC_RELEASE_CONFIDENCE.bat").exists()
