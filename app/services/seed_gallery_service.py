from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional


def _valid_seed(value: Any) -> Optional[int]:
    try:
        seed = int(value)
    except (TypeError, ValueError):
        return None
    return seed if seed >= 0 else None


def build_seed_gallery(
    records: Iterable[Dict[str, Any]],
    *,
    root: Path,
    rel_path: Callable[[Path], str],
    limit: int = 24,
) -> List[Dict[str, Any]]:
    grouped: Dict[int, Dict[str, Any]] = {}
    for rec in records:
        seed = _valid_seed(rec.get("seed"))
        if seed is None:
            continue
        item = grouped.setdefault(seed, {
            "seed": seed,
            "uses": 0,
            "starred": False,
            "best_score": None,
            "latest_at": "",
            "examples": [],
        })
        item["uses"] += 1
        item["starred"] = bool(item["starred"] or rec.get("starred"))
        score = rec.get("qa_score")
        if score is not None:
            score_val = float(score)
            item["best_score"] = score_val if item["best_score"] is None else max(item["best_score"], score_val)
        created = str(rec.get("created_at") or "")
        if created > item["latest_at"]:
            item["latest_at"] = created
        sprite_folder = str(rec.get("sprite_folder") or "").strip()
        preview_url = ""
        if sprite_folder:
            sprite_dir = (root / sprite_folder).resolve()
            preview = sprite_dir / "preview.gif"
            sheet = sprite_dir / "sheet.png"
            if preview.is_file():
                preview_url = "/file/" + rel_path(preview)
            elif sheet.is_file():
                preview_url = "/file/" + rel_path(sheet)
        item["examples"].append({
            "run_id": rec.get("id") or "",
            "action": rec.get("sprite_action") or "",
            "direction": rec.get("direction") or "",
            "profile": rec.get("profile") or "",
            "sprite_folder": sprite_folder,
            "preview_url": preview_url,
            "qa_score": rec.get("qa_score"),
        })

    seeds = list(grouped.values())
    seeds.sort(key=lambda x: (
        1 if x["starred"] else 0,
        x["best_score"] if x["best_score"] is not None else -1,
        x["latest_at"],
    ), reverse=True)
    for item in seeds:
        item["examples"] = item["examples"][:4]
    return seeds[:limit]
