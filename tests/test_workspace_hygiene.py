from pathlib import Path


def test_workspace_hygiene_report_is_read_only_and_structured(tmp_path):
    from app.tools.workspace_hygiene import build_report

    (tmp_path / "output").mkdir()
    (tmp_path / "output" / "asset.bin").write_bytes(b"1234")

    report = build_report(tmp_path)

    assert report["root"] == str(tmp_path)
    assert report["sizes"]["output"]["bytes"] == 4
    assert report["recommendations"]


def test_config_environment_overrides_runtime_paths(monkeypatch):
    from services.config_service import ConfigService

    monkeypatch.setenv("SPRITEFORGE_COMFYUI_DIR", str(Path("D:/AI/ComfyUI")))
    cfg = ConfigService.get_config()

    assert cfg["paths"]["comfyui_dir"].replace("\\", "/") == "D:/AI/ComfyUI"
