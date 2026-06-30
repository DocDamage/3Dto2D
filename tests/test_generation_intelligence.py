import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "app"
sys.path.insert(0, str(APP))


def test_comfy_progress_bridge_applies_websocket_progress():
    from services.generation_intelligence import apply_comfy_ws_message

    job = {"progress": 0.0, "progress_mode": "estimated", "metadata": {"comfy_prompt_id": "abc"}}

    apply_comfy_ws_message(job, {"type": "executing", "data": {"prompt_id": "abc", "node": "wan_sampler"}})
    assert job["stage"] == "wan_sampling"
    assert job["progress_mode"] == "comfy_ws"

    apply_comfy_ws_message(job, {"type": "progress", "data": {"prompt_id": "abc", "value": 7, "max": 20}})
    assert job["metadata"]["comfy_progress"]["value"] == 7
    assert job["metadata"]["comfy_progress"]["max"] == 20
    assert 32.0 <= job["progress"] <= 34.0

    apply_comfy_ws_message(job, {"type": "executed", "data": {"prompt_id": "abc", "node": "save_video"}})
    assert job["metadata"]["comfy_last_node"] == "save_video"


def test_eta_uses_past_runs_with_same_model_profile_action(tmp_path, monkeypatch):
    from services import job_service as js_mod
    from services.generation_intelligence import estimate_job_eta

    monkeypatch.setattr(js_mod, "HISTORY_PATH", tmp_path / "jobs" / "job_history.json")
    now = time.time()
    history = [
        {
            "title": "Generate WAN sprite",
            "started_at": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(now - 500)),
            "finished_at": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(now - 260)),
            "metadata": {"tier": "wan22_5b", "profile": "wan22_5b_3060_best", "sprite_action": "walk"},
        },
        {
            "title": "Generate WAN sprite",
            "started_at": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(now - 800)),
            "finished_at": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(now - 500)),
            "metadata": {"tier": "wan22_5b", "profile": "wan22_5b_3060_best", "sprite_action": "walk"},
        },
    ]
    js_mod.HISTORY_PATH.parent.mkdir(parents=True)
    js_mod.HISTORY_PATH.write_text(json.dumps(history), encoding="utf-8")

    eta = estimate_job_eta({"tier": "wan22_5b", "profile": "wan22_5b_3060_best", "sprite_action": "walk"})

    assert eta["sample_count"] == 2
    assert eta["seconds"] == 270
    assert eta["label"] == "about 4m 30s"


def test_qa_gate_summary_pass_warning_fail():
    from services.generation_intelligence import summarize_qa_gates

    passed = summarize_qa_gates({"issues": [], "score": 96})
    warned = summarize_qa_gates({"issues": [{"level": "warn", "message": "Loop may pop"}], "score": 82})
    failed = summarize_qa_gates({"issues": [{"level": "error", "message": "Missing sheet.png"}], "score": 20})

    assert passed["status"] == "pass"
    assert "No blocking" in passed["reasons"][0]
    assert warned["status"] == "warning"
    assert warned["reasons"] == ["Loop may pop"]
    assert failed["status"] == "fail"
    assert failed["reasons"] == ["Missing sheet.png"]


def test_visual_report_writes_contact_sheet_and_manifest(tmp_path):
    from PIL import Image
    from services.generation_intelligence import build_visual_report

    sprite_dir = tmp_path / "output" / "hero_walk"
    frames = sprite_dir / "frames_processed"
    frames.mkdir(parents=True)
    for i, color in enumerate([(255, 0, 0), (0, 255, 0), (0, 0, 255)]):
        Image.new("RGBA", (16, 16), color + (255,)).save(frames / f"frame_{i:04d}.png")
    (sprite_dir / "sheet.json").write_text(json.dumps({"frame_count": 3, "fps": 12}), encoding="utf-8")

    report = build_visual_report(sprite_dir)

    assert (sprite_dir / "visual_report" / "contact_sheet.jpg").exists()
    assert report["best_frame"]["index"] == 0
    assert report["contact_sheet"].endswith("visual_report/contact_sheet.jpg")


def test_review_actions_star_reject_and_rerun_payload(tmp_path, monkeypatch):
    from services import experiment_service as es_mod
    from services.experiment_service import ExperimentService
    from services.generation_intelligence import mark_review_decision, rerun_similar_payload

    monkeypatch.setattr(es_mod, "EXPERIMENT_PATH", tmp_path / "experiments" / "history.json")
    run_id = ExperimentService.append_run(
        prompt="hero walk",
        negative="blur",
        seed=123,
        model_tier="wan22_5b",
        profile="wan22_5b_3060_best",
        sprite_action="walk",
        direction="right",
    )

    assert mark_review_decision(run_id, "star")["review_status"] == "starred"
    assert ExperimentService.get_run(run_id)["starred"] is True
    assert mark_review_decision(run_id, "reject")["review_status"] == "rejected"

    payload = rerun_similar_payload(ExperimentService.get_run(run_id))
    assert payload["action"] == "generate_sprite"
    assert payload["prompt"] == "hero walk"
    assert payload["seed"] == -1
    assert payload["profile"] == "wan22_5b_3060_best"


def test_preflight_and_retry_advice_for_memory_missing_model_and_offline(tmp_path, monkeypatch):
    from services.generation_intelligence import preflight_generation, safer_retry_payload

    models = {"ok": False, "advanced_ok": False, "missing_files": ["wan.safetensors"]}
    gpu = {"ok": True, "vram_gb": 8, "memory_free": "2048 MiB"}
    disk = {"ok": False, "free_gb": 3.5}
    preflight = preflight_generation(
        {"action": "generate_sprite", "tier": "wan22_5b", "profile": "wan22_5b_3060_best"},
        models=models,
        gpu=gpu,
        disk=disk,
        comfy_running=False,
    )

    assert preflight["status"] == "fail"
    assert "ComfyUI is offline." in preflight["reasons"]
    assert any("disk" in reason.lower() for reason in preflight["reasons"])
    assert any("VRAM" in reason for reason in preflight["reasons"])

    assert safer_retry_payload("CUDA out of memory", {"profile": "wan22_5b_3060_best"})["profile"] == "wan22_5b_debug"
    assert safer_retry_payload("missing model file", {"tier": "wan22_5b"})["action"] == "download_wan22"
    assert safer_retry_payload("connection refused comfyui", {"action": "generate_sprite"})["action"] == "launch_comfy"


def test_model_explainer_and_cleanup_suggestions(tmp_path, monkeypatch):
    from services.generation_intelligence import cleanup_suggestions, explain_model_profile

    explanation = explain_model_profile("wan22_5b", "wan22_5b_3060_best")
    assert "RTX 3060" in explanation["why_selected"]
    assert explanation["risk_level"] == "medium"

    logs = tmp_path / "logs"
    failed = tmp_path / "output" / "failed_run"
    logs.mkdir()
    failed.mkdir(parents=True)
    (logs / "old.log").write_text("x", encoding="utf-8")
    (failed / "partial.tmp").write_text("x", encoding="utf-8")

    suggestions = cleanup_suggestions(tmp_path)
    categories = {item["category"] for item in suggestions}
    assert "Old Task Logs" in categories
    assert "Failed / Incomplete Outputs" in categories
