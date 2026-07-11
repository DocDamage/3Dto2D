import importlib


def test_lpc_bake_route_rejects_sheet_outside_workspace(tmp_path, monkeypatch):
    from flask import Flask

    routes = importlib.import_module("web_routes.routes_misc")
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    outside = tmp_path / "outside.png"
    outside.write_bytes(b"not-an-image")
    monkeypatch.setattr(routes, "ROOT", workspace)
    app = Flask(__name__)
    app.register_blueprint(routes.routes_misc)

    response = app.test_client().post(
        "/api/lpc/bake-edits",
        json={"sheet": str(outside), "layers": [{"frames": []}]},
    )

    assert response.status_code == 400
    assert "workspace" in response.get_json()["message"]
