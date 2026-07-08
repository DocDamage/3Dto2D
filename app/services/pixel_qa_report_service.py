from __future__ import annotations

import html
from pathlib import Path
from typing import Any, Dict, List

from services.pixel_asset_service import ASSETS_DIR
from spriteforge_utils import load_json


PIXEL_QA_SCHEMA = "spriteforge.pixel_visual_qa.v1"


class PixelQAReportService:
    @staticmethod
    def build_report(payload: Dict[str, Any]) -> Dict[str, Any]:
        asset_id = str(payload.get("asset_id") or "").strip()
        asset = payload.get("asset") if isinstance(payload.get("asset"), dict) else None
        if not asset:
            if not asset_id:
                raise ValueError("asset_id or asset metadata is required")
            asset = PixelQAReportService._load_asset(asset_id)
        asset_id = str(asset.get("asset_id") or asset_id)

        qa = asset.get("qa") or {}
        palette = asset.get("palette") or {}
        gates: List[Dict[str, Any]] = [
            PixelQAReportService._color_gate(qa, palette),
            PixelQAReportService._alpha_gate(qa, asset),
            PixelQAReportService._blur_gate(qa),
        ]

        seam_gate = PixelQAReportService._seam_gate(qa)
        if seam_gate:
            gates.append(seam_gate)

        style_gate = PixelQAReportService._style_gate(asset)
        if style_gate:
            gates.append(style_gate)

        workflow_gates = PixelQAReportService._workflow_gates(asset)
        gates.extend(workflow_gates)

        score = int(round(sum(gate["score"] for gate in gates) / max(len(gates), 1)))
        status = "pass" if score >= 85 else "warn" if score >= 60 else "fail"
        recommendations = [
            gate["recommendation"]
            for gate in gates
            if gate.get("status") != "pass" and gate.get("recommendation")
        ]
        if not recommendations:
            recommendations = ["Asset passes the current Pixel Studio QA checks."]

        return {
            "ok": True,
            "schema": PIXEL_QA_SCHEMA,
            "asset_id": asset_id,
            "asset_type": asset.get("asset_type", ""),
            "status": status,
            "score": score,
            "gates": gates,
            "recommendations": recommendations,
            "source": {
                "png": (asset.get("outputs") or {}).get("png", ""),
                "metadata": (asset.get("outputs") or {}).get("metadata", ""),
            },
        }

    @staticmethod
    def write_html_report(payload: Dict[str, Any]) -> Path:
        report = PixelQAReportService.build_report(payload)
        asset_id = str(report.get("asset_id") or "").strip()
        if not asset_id:
            raise ValueError("asset_id is required for HTML QA report")

        asset_dir = ASSETS_DIR / asset_id
        asset_dir.mkdir(parents=True, exist_ok=True)
        html_path = asset_dir / "pixel_qa_report.html"
        gates = "\n".join(
            "<tr>"
            f"<td>{html.escape(str(gate.get('label') or gate.get('id') or 'Gate'))}</td>"
            f"<td class='{html.escape(str(gate.get('status') or 'warn'))}'>{html.escape(str(gate.get('status') or 'warn')).upper()}</td>"
            f"<td>{html.escape(str(gate.get('value') or ''))}</td>"
            f"<td>{html.escape(str(gate.get('recommendation') or ''))}</td>"
            "</tr>"
            for gate in report.get("gates", [])
        )
        recommendations = "\n".join(
            f"<li>{html.escape(str(item))}</li>"
            for item in report.get("recommendations", [])
        )
        source_png = html.escape(str((report.get("source") or {}).get("png") or ""))
        body = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>Pixel Studio QA - {html.escape(asset_id)}</title>
  <style>
    body {{ background: #0d1020; color: #edf2ff; font-family: Segoe UI, Arial, sans-serif; margin: 0; padding: 24px; }}
    main {{ max-width: 960px; margin: 0 auto; }}
    h1 {{ font-size: 24px; margin: 0 0 8px; }}
    .meta {{ color: #aab4d4; margin-bottom: 18px; }}
    .score {{ display: inline-block; padding: 6px 10px; border: 1px solid #3ad8ff; border-radius: 6px; color: #3ad8ff; }}
    table {{ width: 100%; border-collapse: collapse; margin-top: 18px; background: #141a2e; }}
    th, td {{ border: 1px solid #2c3658; padding: 9px; text-align: left; vertical-align: top; }}
    th {{ background: #1d2642; }}
    .pass {{ color: #73e29b; font-weight: 700; }}
    .warn {{ color: #ffd36d; font-weight: 700; }}
    .fail {{ color: #ff7d7d; font-weight: 700; }}
    code {{ color: #b7e9ff; }}
  </style>
</head>
<body>
  <main>
    <h1>Pixel Studio Visual QA</h1>
    <div class="meta">Asset <code>{html.escape(asset_id)}</code> · Type {html.escape(str(report.get("asset_type") or ""))} · <span class="score">{html.escape(str(report.get("status") or "")).upper()} {int(report.get("score") or 0)}/100</span></div>
    <p>Source PNG: <code>{source_png}</code></p>
    <h2>Gates</h2>
    <table>
      <thead><tr><th>Check</th><th>Status</th><th>Value</th><th>Recommendation</th></tr></thead>
      <tbody>{gates}</tbody>
    </table>
    <h2>Recommendations</h2>
    <ul>{recommendations}</ul>
  </main>
</body>
</html>
"""
        html_path.write_text(body, encoding="utf-8")
        return html_path

    @staticmethod
    def _load_asset(asset_id: str) -> Dict[str, Any]:
        meta_path = ASSETS_DIR / asset_id / "pixel_asset.json"
        if not meta_path.exists():
            raise FileNotFoundError(f"Pixel asset not found: {asset_id}")
        return load_json(meta_path, {})

    @staticmethod
    def _color_gate(qa: Dict[str, Any], palette: Dict[str, Any]) -> Dict[str, Any]:
        color_count = int(qa.get("color_count") or len(palette.get("colors") or []))
        max_colors = int(palette.get("max_colors") or 24)
        ok = color_count <= max_colors
        return {
            "id": "palette",
            "label": "Palette count",
            "status": "pass" if ok else "fail",
            "score": 100 if ok else 35,
            "value": f"{color_count}/{max_colors}",
            "recommendation": "" if ok else "Run Cleanup or lower palette size before export.",
        }

    @staticmethod
    def _alpha_gate(qa: Dict[str, Any], asset: Dict[str, Any]) -> Dict[str, Any]:
        transparent_required = bool((asset.get("pixel_rules") or {}).get("transparent_background", True))
        alpha_ok = bool(qa.get("alpha_ok", False))
        ok = alpha_ok or not transparent_required
        return {
            "id": "alpha",
            "label": "Alpha/background",
            "status": "pass" if ok else "warn",
            "score": 100 if ok else 60,
            "value": "transparent" if alpha_ok else "opaque",
            "recommendation": "" if ok else "Run Cleanup to remove the background or confirm opacity is intentional.",
        }

    @staticmethod
    def _blur_gate(qa: Dict[str, Any]) -> Dict[str, Any]:
        blur_score = float(qa.get("blur_score") or 0.0)
        status = "pass" if blur_score <= 0.05 else "warn" if blur_score <= 0.15 else "fail"
        return {
            "id": "sharpness",
            "label": "Pixel sharpness",
            "status": status,
            "score": 100 if status == "pass" else 70 if status == "warn" else 35,
            "value": f"{blur_score:.3f}",
            "recommendation": "" if status == "pass" else "Re-normalize with nearest-neighbor cleanup before export.",
        }

    @staticmethod
    def _seam_gate(qa: Dict[str, Any]) -> Dict[str, Any] | None:
        seam = qa.get("seam_check")
        if not isinstance(seam, dict):
            return None
        left_right = float(seam.get("left_right_delta") or 0.0)
        top_bottom = float(seam.get("top_bottom_delta") or 0.0)
        worst = max(left_right, top_bottom)
        status = "pass" if worst < 0.2 else "warn" if worst < 0.35 else "fail"
        return {
            "id": "tile_seams",
            "label": "Tile seam continuity",
            "status": status,
            "score": 100 if status == "pass" else 65 if status == "warn" else 30,
            "value": f"lr {left_right:.3f}, tb {top_bottom:.3f}",
            "recommendation": "" if status == "pass" else "Use seam preview and regenerate or cleanup the tile edges.",
        }

    @staticmethod
    def _style_gate(asset: Dict[str, Any]) -> Dict[str, Any] | None:
        match = asset.get("style_match")
        if not isinstance(match, dict):
            return None
        overall = float(match.get("overall") or 0.0)
        status = "pass" if overall >= 0.85 else "warn" if overall >= 0.65 else "fail"
        return {
            "id": "style_match",
            "label": "Project style match",
            "status": status,
            "score": int(round(overall * 100)),
            "value": f"{overall:.2f}",
            "recommendation": "" if status == "pass" else "Use Make match project style or pick a closer style profile.",
        }

    @staticmethod
    def _workflow_gates(asset: Dict[str, Any]) -> List[Dict[str, Any]]:
        gates: List[Dict[str, Any]] = []
        versions = asset.get("versions") or []
        if versions:
            gates.append({
                "id": "versions",
                "label": "Version safety",
                "status": "pass",
                "score": 100,
                "value": f"{len(versions)} saved",
                "recommendation": "",
            })
        if asset.get("inpaint_history"):
            gates.append({
                "id": "inpaint_trace",
                "label": "Inpaint trace",
                "status": "pass",
                "score": 100,
                "value": f"{len(asset.get('inpaint_history') or [])} edits",
                "recommendation": "",
            })
        if asset.get("cleanup_history"):
            gates.append({
                "id": "cleanup_trace",
                "label": "Cleanup trace",
                "status": "pass",
                "score": 100,
                "value": f"{len(asset.get('cleanup_history') or [])} passes",
                "recommendation": "",
            })
        return gates
