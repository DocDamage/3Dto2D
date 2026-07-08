import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "app"
sys.path.insert(0, str(APP))


def test_launcher_skips_comfy_autostart_when_not_installed(monkeypatch, tmp_path):
    import spriteforge_launcher as launcher

    app_root = tmp_path / "app"
    app_root.mkdir()
    (app_root / "config").mkdir()
    (app_root / "config" / "spriteforge_config.json").write_text(
        '{"paths":{"comfyui_dir":"vendor/ComfyUI"},"comfy":{"host":"127.0.0.1","port":8188}}',
        encoding="utf-8",
    )
    monkeypatch.setattr(launcher, "ROOT", app_root)
    monkeypatch.setattr(launcher, "_comfy_is_running", lambda host, port: False)

    calls = []
    monkeypatch.setattr(launcher.subprocess, "Popen", lambda *args, **kwargs: calls.append((args, kwargs)))

    assert launcher.launch_comfy_for_default_start(app_root / ".venv" / "Scripts" / "python.exe") is False
    assert calls == []


def test_launcher_starts_comfy_when_installed_and_offline(monkeypatch, tmp_path):
    import spriteforge_launcher as launcher

    app_root = tmp_path / "app"
    comfy_dir = app_root / "vendor" / "ComfyUI"
    comfy_dir.mkdir(parents=True)
    (app_root / "config").mkdir()
    (app_root / "config" / "spriteforge_config.json").write_text(
        '{"paths":{"comfyui_dir":"vendor/ComfyUI"},"comfy":{"host":"127.0.0.1","port":8188}}',
        encoding="utf-8",
    )
    py = app_root / ".venv" / "Scripts" / "python.exe"
    monkeypatch.setattr(launcher, "ROOT", app_root)
    monkeypatch.setattr(launcher, "_comfy_is_running", lambda host, port: False)

    calls = []
    monkeypatch.setattr(launcher.subprocess, "Popen", lambda *args, **kwargs: calls.append((args, kwargs)))

    assert launcher.launch_comfy_for_default_start(py) is True
    assert calls[0][0][0] == [str(py), "spriteforge_unified.py", "launch-comfy"]
    assert calls[0][1]["cwd"] == str(app_root)


def test_launcher_does_not_duplicate_comfy_when_already_running(monkeypatch, tmp_path):
    import spriteforge_launcher as launcher

    app_root = tmp_path / "app"
    (app_root / "vendor" / "ComfyUI").mkdir(parents=True)
    (app_root / "config").mkdir()
    (app_root / "config" / "spriteforge_config.json").write_text(
        '{"paths":{"comfyui_dir":"vendor/ComfyUI"},"comfy":{"host":"127.0.0.1","port":8188}}',
        encoding="utf-8",
    )
    monkeypatch.setattr(launcher, "ROOT", app_root)
    monkeypatch.setattr(launcher, "_comfy_is_running", lambda host, port: True)

    calls = []
    monkeypatch.setattr(launcher.subprocess, "Popen", lambda *args, **kwargs: calls.append((args, kwargs)))

    assert launcher.launch_comfy_for_default_start(app_root / ".venv" / "Scripts" / "python.exe") is True
    assert calls == []
