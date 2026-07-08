#!/usr/bin/env python3
"""CI Check Service: Machine-readable QA pass/fail for CI/CD pipelines."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from spriteforge_utils import ROOT, load_json

CI_IGNORE_MARKERS = ("ci_ignore.json", ".spriteforge_ci_ignore")
NON_SPRITE_OUTPUT_DIRS = {
    "jobs",
    "packs",
    "temp",
    "sprite_compare",
    "qa",
    "quality",
    "godot_export",
    "unity_export",
    "unreal_export",
    "animated_exports",
    "skeletal_export",
}


def is_sprite_output_dir(sprite_dir: Path) -> bool:
    return sprite_dir.name not in NON_SPRITE_OUTPUT_DIRS and (sprite_dir / "sheet.json").exists()


def ci_ignore_reason(sprite_dir: Path) -> Optional[str]:
    for marker_name in CI_IGNORE_MARKERS:
        marker = sprite_dir / marker_name
        if not marker.exists():
            continue
        if marker.suffix == ".json":
            data = load_json(marker, {})
            return str(data.get("reason") or "Sprite output is quarantined from CI quality gates.")
        text = marker.read_text(encoding="utf-8", errors="replace").strip()
        return text or "Sprite output is quarantined from CI quality gates."
    return None


def _numeric_score(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _score_from_report(data: Dict[str, Any]) -> float:
    summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
    return _numeric_score(
        data.get("overall_score")
        or data.get("score")
        or summary.get("overall_score")
        or summary.get("score")
    )


def _quality_score(sprite_dir: Path, sheet: Dict[str, Any]) -> Dict[str, Any]:
    extra = sheet.get("extra", {}) if isinstance(sheet.get("extra"), dict) else {}
    qa = extra.get("qa", {}) if isinstance(extra.get("qa"), dict) else {}
    score = _numeric_score(qa.get("overall_score") or qa.get("score"))
    if score:
        return {"score": score, "details": qa, "source": "sheet.extra.qa"}

    for report_path in [
        sprite_dir / "qa_report.json",
        sprite_dir / "quality_report.json",
        sprite_dir / "quality" / "quality_report.json",
    ]:
        if not report_path.exists():
            continue
        report = load_json(report_path, {})
        score = _score_from_report(report)
        if score:
            return {"score": score, "details": report, "source": str(report_path)}

    try:
        import contextlib
        import io
        from spriteforge_quality import quality_report

        with contextlib.redirect_stdout(io.StringIO()):
            report = quality_report(sprite_dir, sprite_dir / "quality", None)
        score = _score_from_report(report)
        return {"score": score, "details": report, "source": "computed"}
    except Exception as exc:
        return {"score": 0.0, "details": {"error": str(exc)}, "source": "error"}


def ci_check_directory(
    root_dir: Path,
    fail_under: float = 70.0,
    output_junit: Optional[Path] = None,
    output_json: Optional[Path] = None,
) -> Dict[str, Any]:
    """Run QA on all sprite outputs in a directory, return CI-compatible results.
    
    Returns non-zero exit code if any sprite fails below threshold.
    """
    results: List[Dict[str, Any]] = []
    total_score = 0.0
    passed = 0
    failed = 0
    skipped = 0
    
    # Find all sprite directories (those with sheet.json)
    sprite_dirs = []
    for d in root_dir.rglob("sheet.json"):
        sprite_dir = d.parent
        if is_sprite_output_dir(sprite_dir):
            sprite_dirs.append(sprite_dir)
    
    if not sprite_dirs:
        # Look one level deeper
        for d in root_dir.iterdir():
            if d.is_dir() and is_sprite_output_dir(d):
                sprite_dirs.append(d)
    
    for sprite_dir in sorted(sprite_dirs):
        ignore_reason = ci_ignore_reason(sprite_dir)
        if ignore_reason:
            skipped += 1
            results.append({
                "name": sprite_dir.name,
                "path": str(sprite_dir),
                "status": "skipped",
                "reason": ignore_reason,
                "score": 0,
            })
            continue

        sheet = load_json(sprite_dir / "sheet.json")
        if not sheet:
            skipped += 1
            results.append({
                "name": sprite_dir.name,
                "status": "skipped",
                "reason": "No sheet.json data",
                "score": 0,
            })
            continue
        
        qa_result = _quality_score(sprite_dir, sheet)
        overall = float(qa_result["score"])
        
        passed_threshold = overall >= fail_under
        total_score += overall
        
        if passed_threshold:
            passed += 1
            status = "passed"
        else:
            failed += 1
            status = "failed"
        
        results.append({
            "name": sprite_dir.name,
            "path": str(sprite_dir),
            "status": status,
            "score": overall,
            "threshold": fail_under,
            "frame_count": sheet.get("frame_count", 0),
            "fps": sheet.get("fps", 0),
            "animation": sheet.get("animation", "unknown"),
            "qa_details": qa_result["details"],
            "qa_source": qa_result["source"],
        })
    
    total = passed + failed + skipped
    avg_score = total_score / max(passed + failed, 1)
    all_passed = failed == 0 or (total == 0)
    
    summary = {
        "total": total,
        "passed": passed,
        "failed": failed,
        "skipped": skipped,
        "average_score": round(avg_score, 2),
        "threshold": fail_under,
        "all_passed": all_passed,
        "results": results,
    }
    
    # Write JUnit XML if requested
    if output_junit:
        _write_junit_xml(results, output_junit, fail_under)
    
    # Write JSON if requested
    if output_json:
        output_json.parent.mkdir(parents=True, exist_ok=True)
        output_json.write_text(
            json.dumps(summary, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )
    
    return summary


def _write_junit_xml(results: List[Dict[str, Any]], path: Path, threshold: float) -> None:
    """Write JUnit XML test report."""
    import xml.etree.ElementTree as ET
    from datetime import datetime
    
    testsuite = ET.Element("testsuite", {
        "name": "SpriteForge QA Check",
        "tests": str(len(results)),
        "failures": str(sum(1 for r in results if r["status"] == "failed")),
        "errors": "0",
        "skipped": str(sum(1 for r in results if r["status"] == "skipped")),
        "time": "0",
        "timestamp": datetime.now().isoformat(),
    })
    
    for result in results:
        testcase = ET.SubElement(testsuite, "testcase", {
            "classname": "SpriteForge",
            "name": result["name"],
            "time": "0",
        })
        
        if result["status"] == "failed":
            failure = ET.SubElement(testcase, "failure", {
                "message": f"Score {result['score']:.1f} below threshold {threshold:.1f}",
                "type": "QualityGate",
            })
            failure.text = json.dumps(result.get("qa_details", {}), indent=2)
        elif result["status"] == "skipped":
            ET.SubElement(testcase, "skipped", {
                "message": result.get("reason", "No data")
            })
        else:
            # Passed - add properties for score
            props = ET.SubElement(testcase, "properties")
            for key in ["score", "frame_count", "fps", "animation"]:
                val = result.get(key)
                if val is not None:
                    ET.SubElement(props, "property", {
                        "name": key,
                        "value": str(val)
                    })
    
    tree = ET.ElementTree(testsuite)
    ET.indent(tree, space="  ")
    tree.write(str(path), encoding="utf-8", xml_declaration=True)


def run_ci_check(args: Optional[List[str]] = None) -> int:
    """CLI entry point for ci-check."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="SpriteForge CI Quality Gate Check"
    )
    parser.add_argument(
        "--root", default="output",
        help="Root directory containing sprite outputs"
    )
    parser.add_argument(
        "--fail-under", type=float, default=70.0,
        help="Minimum QA score threshold (default: 70.0)"
    )
    parser.add_argument(
        "--junit-xml", default=None,
        help="Output JUnit XML report path"
    )
    parser.add_argument(
        "--json", dest="output_json", default=None,
        help="Output JSON report path"
    )
    parser.add_argument(
        "--quiet", action="store_true",
        help="Suppress per-sprite output"
    )
    
    opts = parser.parse_args(args)
    root_arg = Path(opts.root)
    root_path = root_arg.resolve() if root_arg.is_absolute() else (ROOT / root_arg).resolve()
    if not root_path.exists() and not root_arg.is_absolute():
        repo_relative = (ROOT.parent / root_arg).resolve()
        if repo_relative.exists():
            root_path = repo_relative
    
    if not root_path.exists():
        print(f"Error: Directory not found: {root_path}", file=sys.stderr)
        return 1
    
    junit_path = Path(opts.junit_xml) if opts.junit_xml else None
    json_path = Path(opts.output_json) if opts.output_json else None
    
    summary = ci_check_directory(
        root_path,
        fail_under=opts.fail_under,
        output_junit=junit_path,
        output_json=json_path,
    )
    
    if not opts.quiet:
        for r in summary["results"]:
            status_icon = "PASS" if r["status"] == "passed" else "FAIL" if r["status"] == "failed" else "SKIP"
            print(f"  [{status_icon}] {r['name']}: {r['score']:.1f}/100 (threshold: {summary['threshold']:.0f})")
        
        print(f"\nResults: {summary['passed']} passed, {summary['failed']} failed, {summary['skipped']} skipped")
        print(f"Average Score: {summary['average_score']:.1f}/100")
    
    if summary["all_passed"]:
        print("CI Check: PASSED")
        return 0
    else:
        print(f"CI Check: FAILED ({summary['failed']} below threshold)", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(run_ci_check())
