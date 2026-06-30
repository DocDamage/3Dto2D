from flask import Blueprint, send_from_directory, abort, current_app, Response
from pathlib import Path
import mimetypes

import web_helpers
from web_helpers import WEB, _safe_preview_file

routes_static = Blueprint("routes_static", __name__)

@routes_static.route("/")
def serve_index():
    return send_from_directory(str(WEB), "index.html")

@routes_static.route("/web/<path:filename>")
def serve_web(filename):
    # Prevent directory traversal
    resolved = (WEB / filename).resolve()
    try:
        resolved.relative_to(WEB.resolve())
    except ValueError:
        abort(403)
    if not resolved.exists() or not resolved.is_file():
        abort(404)
    return send_from_directory(str(WEB), filename, cache_timeout=0)

@routes_static.route("/file/<path:filename>")
def serve_file(filename):
    resolved = (web_helpers.ROOT / filename).resolve()
    if not _safe_preview_file(resolved):
        abort(403)
    if not resolved.exists() or not resolved.is_file():
        abort(404)
        
    # Standard Flask send_from_directory serves files correctly
    # Disable caching for previews and reports to avoid stale assets
    response = send_from_directory(str(web_helpers.ROOT), filename)
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    return response

