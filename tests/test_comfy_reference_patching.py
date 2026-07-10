import json
import sys
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "app"
sys.path.insert(0, str(APP))


def test_single_image_reference_workflow_keeps_character_reference_primary():
    from services.comfy_workflow_service import patch_workflow_images

    workflow = json.loads((APP / "workflows" / "wan22_ti2v_5b_ipadapter_api.json").read_text(encoding="utf-8"))

    ref_count, style_count = patch_workflow_images(workflow, "hero_reference.png", "style_reference.png")

    assert ref_count == 1
    assert style_count == 0
    load_images = [
        node
        for node in workflow.values()
        if isinstance(node, dict) and node.get("class_type") in {"LoadImage", "LoadImageMask", "LoadImageUpload"}
    ]
    assert len(load_images) == 1
    assert load_images[0]["inputs"]["image"] == "hero_reference.png"


def test_style_only_reference_workflow_can_patch_single_image_node():
    from services.comfy_workflow_service import patch_workflow_images

    workflow = json.loads((APP / "workflows" / "wan22_ti2v_5b_ipadapter_api.json").read_text(encoding="utf-8"))

    ref_count, style_count = patch_workflow_images(workflow, None, "style_reference.png")

    assert ref_count == 0
    assert style_count == 1


def test_cli_reference_run_selects_reference_capable_workflow_without_explicit_workflow():
    from services.config_service import ConfigService
    from services.wan_generation_service import reference_capable_workflow_for_args

    cfg = ConfigService.get_config()
    args = SimpleNamespace(
        workflow=None,
        reference_image="input/uploaded_videos/south.png",
        tier="wan22_5b",
        mode="auto",
    )

    workflow = reference_capable_workflow_for_args(args, cfg)

    assert workflow is not None
    assert workflow.name == "wan22_ti2v_5b_ipadapter_api.json"


def test_reference_workflow_falls_back_when_ipadapter_nodes_are_missing(monkeypatch):
    from services.config_service import ConfigService
    from services.wan_generation_service import reference_capable_workflow_for_args

    cfg = SimpleNamespace(raw=ConfigService.get_config(), base_url="http://127.0.0.1:8188")
    args = SimpleNamespace(
        workflow=None,
        reference_image="input/uploaded_videos/south.png",
        tier="wan22_5b",
        mode="auto",
    )
    available_nodes = {
        "UNETLoader",
        "CLIPLoader",
        "VAELoader",
        "Wan22ImageToVideoLatent",
        "CLIPTextEncode",
        "ModelSamplingSD3",
        "KSampler",
        "VAEDecode",
        "SaveWEBM",
    }

    monkeypatch.setattr("services.wan_generation_service.api_get", lambda *_args, **_kwargs: {name: {} for name in available_nodes})

    workflow = reference_capable_workflow_for_args(args, cfg)

    assert workflow is not None
    assert workflow.name == "wan22_ti2v_5b_native_api.json"


def test_native_wan22_reference_workflow_injects_start_image():
    from services.wan_generation_service import attach_reference_to_start_image

    workflow = json.loads((APP / "workflows" / "wan22_ti2v_5b_native_api.json").read_text(encoding="utf-8"))

    patched = attach_reference_to_start_image(workflow, "SpriteForge/south.png")

    assert patched == 1
    load_images = [
        (node_id, node)
        for node_id, node in workflow.items()
        if isinstance(node, dict) and node.get("class_type") == "LoadImage"
    ]
    assert len(load_images) == 1
    load_image_id, load_image = load_images[0]
    assert load_image["inputs"]["image"] == "SpriteForge/south.png"
    assert workflow["55"]["inputs"]["start_image"] == [load_image_id, 0]
