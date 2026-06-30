#!/usr/bin/env python3
"""CI Check Service: Machine-readable QA pass/fail for CI/CD pipelines."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from spriteforge_utils import ROOT, load_json


def ci_check_directory(
    root_dir: Path,
    fail_under: float = 70.0,
    output_junit: Optional[Path] = None,
    output_json: Optional[Path] = None,
) -> Dict[str, Any]:
    """Run QA on all sprite outputs in a directory, return CI-compatible results.
    
    Returns non-zero exit code if any sprite fails below threshold.
    """
    import xml.etree.ElementTree as ET
    
    results: List[Dict[str, Any]] = []
    total_score = 0.0
    passed = 0
    failed = 0
    skipped = 0
    
    # Find all sprite directories (those with sheet.json)
    sprite_dirs = []
    for d in root_dir.rglob("sheet.json"):
        sprite_dir = d.parent
        if sprite_dir.name not in {"jobs", "packs", "temp", "sprite_compare"}:
            sprite_dirs.append(sprite_dir)
    
    if not sprite_dirs:
        # Look one level deeper
        for d in root_dir.iterdir():
            if d.is_dir() and (d / "sheet.json").exists():
                sprite_dirs.append(d)
    
    for sprite_dir in sorted(sprite_dirs):
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
        
        # Extract QA scores from metadata
        extra = sheet.get("extra", {})
        qa = extra.get("qa", {})
        overall = qa.get("overall_score", 0)
        
        if not overall:
            # Try alternate locations
            qa_report = load_json(sprite_dir / "qa_report.json", {})
            overall = qa_report.get("overall_score", 0) or qa.get("overall_score", 0)
        
        if not overall:
            # Try loading from quality report
            quality_path = sprite_dir / "quality_report.json"
            if quality_path.exists():
                quality = load_json(quality_path, {})
                overall = quality.get("score", 0)
        
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
            "qa_details": qa,
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
    root_path = (ROOT / opts.root).resolve()
    
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
        print("CI Check: PASSED ✓")
        return 0
    else:
        print(f"CI Check: FAILED ✗ ({summary['failed']} below threshold)", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(run_ci_check())