import json
import logging
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "app"
sys.path.insert(0, str(APP))


def test_save_json_uses_unique_temp_files_for_concurrent_writes(tmp_path):
    from spriteforge_utils import load_json, save_json

    target = tmp_path / "state.json"

    def write_value(value: int) -> None:
        save_json(target, {"value": value})

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(write_value, range(40)))

    data = load_json(target, {})
    assert isinstance(data, dict)
    assert set(data) == {"value"}
    assert isinstance(data["value"], int)
    assert not list(tmp_path.glob("*.tmp"))


def test_load_json_warns_and_returns_default_for_invalid_json(tmp_path, caplog):
    from spriteforge_utils import load_json

    target = tmp_path / "broken.json"
    target.write_text("{not json", encoding="utf-8")

    with caplog.at_level(logging.WARNING, logger="spriteforge_utils"):
        data = load_json(target, {"fallback": True})

    assert data == {"fallback": True}
    assert "Could not load JSON" in caplog.text


def test_config_service_uses_shared_json_helpers(tmp_path):
    from services.config_service import load_json, save_json

    target = tmp_path / "config.json"
    save_json(target, {"ok": True})

    assert json.loads(target.read_text(encoding="utf-8")) == {"ok": True}
    assert load_json(target, {}) == {"ok": True}
