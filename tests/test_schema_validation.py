import pytest
from services.schema_validation_service import (
    validate_config, validate_project, validate_queue, validate_sheet
)

def test_validate_config():
    # Valid configs
    ok, err = validate_config({})
    assert ok is True
    ok, err = validate_config({"comfy": {"host": "127.0.0.1", "port": 8188}})
    assert ok is True

    # Invalid configs
    ok, err = validate_config("not-a-dict")
    assert ok is False
    ok, err = validate_config({"comfy": "not-a-dict"})
    assert ok is False
    assert "comfy" in err

def test_validate_project():
    # Valid project
    ok, err = validate_project({"project_name": "hero", "project_root": "projects/hero"})
    assert ok is True

    # Invalid projects
    ok, err = validate_project({})
    assert ok is False
    ok, err = validate_project({"project_name": "", "project_root": "projects/hero"})
    assert ok is False
    assert "project_name" in err

def test_validate_queue():
    # Valid queue
    ok, err = validate_queue({"id": "job-1", "status": "pending", "title": "Generate"})
    assert ok is True

    # Invalid queue
    ok, err = validate_queue({})
    assert ok is False
    ok, err = validate_queue({"id": "job-1", "status": "bad-status", "title": "Generate"})
    assert ok is False
    assert "status" in err

def test_validate_sheet():
    # Valid sheet
    valid_sheet = {
        "frame_count": 2,
        "fps": 12.0,
        "image": "sheet.png",
        "frame_width": 64,
        "frame_height": 64,
        "columns": 2,
        "rows": 1,
        "frames": [
            {"index": 0, "x": 0, "y": 0, "w": 64, "h": 64},
            {"index": 1, "x": 64, "y": 0, "w": 64, "h": 64}
        ]
    }
    ok, err = validate_sheet(valid_sheet)
    assert ok is True

    # Invalid sheet missing frames list
    invalid = dict(valid_sheet)
    del invalid["frames"]
    ok, err = validate_sheet(invalid)
    assert ok is False
    assert "frames" in err

    # Invalid frame coordinate type
    invalid_coord = dict(valid_sheet)
    invalid_coord["frames"] = [{"index": 0, "x": "not-an-int", "y": 0, "w": 64, "h": 64}]
    ok, err = validate_sheet(invalid_coord)
    assert ok is False
    assert "frames[0].x" in err
