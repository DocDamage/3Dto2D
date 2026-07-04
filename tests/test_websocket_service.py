import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "app"
sys.path.insert(0, str(APP))


def test_progress_event_hub_publishes_recent_and_subscriber_events():
    from services.websocket_service import ProgressEventHub

    ProgressEventHub.reset()
    subscriber = ProgressEventHub.subscribe()
    event = ProgressEventHub.publish("job.progress", {"id": "job-1", "progress": 42})

    assert event["seq"] == 1
    assert ProgressEventHub.recent()[0]["payload"]["progress"] == 42
    assert subscriber.get_nowait()["type"] == "job.progress"
    ProgressEventHub.unsubscribe(subscriber)


def test_progress_events_api_returns_recent_events():
    from spriteforge_web import app
    from services.websocket_service import ProgressEventHub

    ProgressEventHub.reset()
    ProgressEventHub.publish("job.stage", {"id": "job-2", "stage": "queued"})

    app.config["TESTING"] = True
    with app.test_client() as client:
        response = client.get("/api/progress/events")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["ok"] is True
    assert payload["events"][0]["type"] == "job.stage"
    assert payload["latest_seq"] == 1


def test_progress_stream_api_replays_recent_events():
    from spriteforge_web import app
    from services.websocket_service import ProgressEventHub

    ProgressEventHub.reset()
    ProgressEventHub.publish("job.progress", {"id": "job-3", "progress": 60})

    app.config["TESTING"] = True
    with app.test_client() as client:
        response = client.get("/api/progress/stream", buffered=False)
        first_chunk = next(response.response).decode("utf-8")

    assert response.status_code == 200
    assert response.mimetype == "text/event-stream"
    assert "event: job.progress" in first_chunk
    assert '"progress": 60' in first_chunk


def test_progress_transport_status_documents_sse_and_websocket_bridge():
    from services.websocket_service import progress_transport_status

    status = progress_transport_status()

    assert status["schema"] == "spriteforge.progress_transport.v1"
    assert status["browser_transport"] == "sse"
    assert status["stream_endpoint"] == "/api/progress/stream"
    assert status["upstream_transports"]["comfyui"] == "websocket"


def test_progress_transport_api_returns_transport_descriptor():
    from spriteforge_web import app

    app.config["TESTING"] = True
    with app.test_client() as client:
        response = client.get("/api/progress/transport")

    payload = response.get_json()
    assert response.status_code == 200
    assert payload["ok"] is True
    assert payload["browser_transport"] == "sse"
