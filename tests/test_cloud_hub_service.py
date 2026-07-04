import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "app"
sys.path.insert(0, str(APP))


def test_cloud_hub_normalizes_saves_and_selects_priority(tmp_path):
    from services.cloud_hub_service import load_cloud_nodes, save_cloud_nodes, select_cloud_node

    path = tmp_path / "config" / "cloud_nodes.json"
    save_cloud_nodes([
        {"id": "slow", "url": "http://slow.example", "priority": 50, "enabled": True},
        {"id": "fast", "url": "fast.example", "priority": 10, "enabled": True},
        {"id": "off", "url": "http://off.example", "priority": 1, "enabled": False},
    ], path=path)

    nodes = load_cloud_nodes(path)
    selected = select_cloud_node(nodes)

    assert len(nodes) == 3
    assert nodes[1]["url"] == "http://fast.example"
    assert selected["id"] == "fast"


def test_cloud_hub_selection_prefers_ready_capacity_over_busy_priority():
    from services.cloud_hub_service import select_cloud_node

    selected = select_cloud_node([
        {"id": "busy-fast", "url": "http://busy.example", "priority": 1, "status": "busy", "active_jobs": 1, "max_jobs": 1},
        {"id": "ready-slower", "url": "http://ready.example", "priority": 50, "status": "ready", "active_jobs": 0, "max_jobs": 2},
    ])

    assert selected["id"] == "ready-slower"
    assert selected["max_jobs"] == 2


def test_cloud_dispatch_plan_explains_ranked_and_rejected_nodes():
    from services.cloud_hub_service import plan_cloud_dispatch

    plan = plan_cloud_dispatch([
        {"id": "disabled", "url": "http://disabled.example", "enabled": False},
        {"id": "busy-fast", "url": "http://busy.example", "priority": 1, "status": "busy", "active_jobs": 1, "max_jobs": 1},
        {"id": "ready-slower", "url": "http://ready.example", "priority": 50, "status": "ready", "active_jobs": 0, "max_jobs": 2},
        {"id": "wrong-cap", "url": "http://wrong.example", "capabilities": ["preview"]},
    ])

    assert plan["schema"] == "spriteforge_cloud_dispatch_plan_v1"
    assert plan["selected"]["id"] == "ready-slower"
    assert [row["id"] for row in plan["ranked"]][:2] == ["ready-slower", "busy-fast"]
    rejected = {row["id"]: row["reasons"] for row in plan["rejected"]}
    assert "disabled" in rejected["disabled"]
    assert "missing_capability:remote_generate" in rejected["wrong-cap"]


def test_cloud_hub_status_includes_dispatch_plan(tmp_path):
    from services.cloud_hub_service import cloud_hub_status, save_cloud_nodes

    path = tmp_path / "config" / "cloud_nodes.json"
    save_cloud_nodes([
        {"id": "gpu-a", "url": "http://gpu-a.example", "priority": 10, "enabled": True},
    ], path=path)

    status = cloud_hub_status(path=path)

    assert status["selected"]["id"] == "gpu-a"
    assert status["dispatch_plan"]["selected"]["id"] == "gpu-a"
    assert status["queue_plan"]["schema"] == "spriteforge_cloud_queue_assignment_v1"


def test_cloud_queue_assignment_plans_jobs_across_free_node_slots():
    from services.cloud_hub_service import plan_cloud_queue_assignments

    plan = plan_cloud_queue_assignments(
        [
            {"id": "idle", "label": "Idle pose", "priority": 20},
            {"id": "walk", "label": "Walk pose", "priority": 10},
            {"id": "attack", "label": "Attack pose", "priority": 30},
        ],
        [
            {"id": "gpu-a", "url": "http://a.example", "priority": 10, "active_jobs": 1, "max_jobs": 2},
            {"id": "gpu-b", "url": "http://b.example", "priority": 20, "active_jobs": 0, "max_jobs": 1},
            {"id": "full", "url": "http://full.example", "active_jobs": 1, "max_jobs": 1},
        ],
    )

    assert plan["schema"] == "spriteforge_cloud_queue_assignment_v1"
    assert plan["dry_run"] is True
    assert plan["non_destructive"] is True
    assert [row["job"]["id"] for row in plan["assignments"]] == ["walk", "idle"]
    assert [row["node_id"] for row in plan["assignments"]] == ["gpu-a", "gpu-b"]
    first_dispatch = plan["assignments"][0]["dispatch"]
    assert first_dispatch["schema"] == "spriteforge_cloud_queue_dispatch_v1"
    assert first_dispatch["dispatch_url"] == "http://a.example/prompt"
    assert first_dispatch["queue_position"] == 1
    assert first_dispatch["capacity_snapshot"]["planned_slot"] == 2
    assert "--cloud-node gpu-a" in first_dispatch["command_hint"]
    assert plan["unassigned"][0]["job"]["id"] == "attack"
    rejected = {row["id"]: row["reasons"] for row in plan["rejected_nodes"]}
    assert "at_capacity" in rejected["full"]


def test_cloud_hub_check_node_uses_comfy_system_stats(monkeypatch):
    from services.cloud_hub_service import check_cloud_node

    seen = {}

    class FakeResponse:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

    def fake_urlopen(request, timeout):
        seen["url"] = request.full_url
        seen["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr("services.cloud_hub_service.urllib.request.urlopen", fake_urlopen)

    status = check_cloud_node({"url": "http://node.example"}, timeout=0.25)

    assert status["ok"] is True
    assert seen["url"] == "http://node.example/system_stats"
    assert seen["timeout"] == 0.25


def test_remote_generate_parser_accepts_cloud_node_without_server():
    from spriteforge_unified import build_parser

    args = build_parser().parse_args([
        "remote-generate",
        "--cloud-node",
        "gpu-a",
        "--workflow",
        "workflow.json",
        "--prompt",
        "idle sprite",
    ])

    assert args.server is None
    assert args.cloud_node == "gpu-a"


def test_remote_generate_resolves_configured_cloud_node(monkeypatch):
    import spriteforge_unified_parser as parser

    captured = {}

    monkeypatch.setattr(parser, "run", lambda cmd: captured.setdefault("cmd", cmd))
    monkeypatch.setattr(
        "services.cloud_hub_service.cloud_hub_status",
        lambda prefer_id="": {
            "selected": {
                "id": prefer_id,
                "url": "http://selected.example",
            }
        },
    )

    parser.cmd_remote_generate(argparse.Namespace(
        server=None,
        cloud_node="gpu-a",
        workflow="workflow.json",
        prompt="idle sprite",
        output_prefix="SpriteForge/remote_sprite",
        timeout=10,
        cell_size="512x512",
        key_color="auto",
        seed=-1,
        negative=None,
        reference_image=None,
        width=None,
        height=None,
        frames=None,
        video_fps=None,
        output=None,
        convert=False,
        extra=[],
    ))

    assert "--server" in captured["cmd"]
    assert "http://selected.example" in captured["cmd"]
