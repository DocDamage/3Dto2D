from __future__ import annotations

import base64
import hashlib
import json
import os
import random
import shutil
import time
from collections import Counter
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, List, Tuple

from PIL import Image

from spriteforge_utils import IMAGE_SUFFIXES, ROOT, safe_name


DEFAULT_OUTPUT = ROOT / "output" / "lpc_parts"
DEFAULT_LPC_SOURCE = ROOT / "input" / "lpc_assets" / "Universal-LPC-Spritesheet-Character-Generator"

LPC_ACTION_ALIASES = {
    "backslash": "back_slash",
    "combat_idle": "combat_idle",
    "halfslash": "half_slash",
    "spellcast": "cast",
}

LPC_BODY_TYPES = {
    "adult", "child", "female", "male", "muscular", "pregnant", "teen", "thin",
}

LPC_LAYER_ORDER = [
    "body",
    "head",
    "eyes",
    "facial",
    "hair",
    "legs",
    "feet",
    "torso",
    "arms",
    "shoulders",
    "neck",
    "cape",
    "back",
    "hat",
    "weapons",
    "tools",
]


def _spritesheets_root(root: Path) -> Path:
    root = root.resolve()
    candidates = [
        root / "dist" / "spritesheets",
        root / "spritesheets",
        root / "public" / "spritesheets",
        root,
    ]
    for candidate in candidates:
        if candidate.is_dir() and _has_png(candidate):
            if candidate.name.lower() == "spritesheets":
                return candidate
    for candidate in candidates:
        if candidate.is_dir() and _has_png(candidate):
            return candidate
    raise FileNotFoundError(f"No LPC spritesheets folder found under {root}")


def _has_png(root: Path) -> bool:
    try:
        next(root.rglob("*.png"))
        return True
    except StopIteration:
        return False
    except OSError:
        return False


def _image_paths(root: Path, limit: int = 0) -> List[Path]:
    paths: List[Path] = []
    for current, _dirs, files in os.walk(root, onerror=lambda _exc: None):
        current_path = Path(current)
        for filename in files:
            path = current_path / filename
            if path.suffix.lower() in IMAGE_SUFFIXES:
                paths.append(path)
                if limit and limit > 0 and len(paths) >= limit:
                    paths.sort()
                    return paths[:limit]
    paths.sort()
    if limit and limit > 0:
        return paths[:limit]
    return paths


def _normalize_action(stem: str) -> str:
    action = stem.lower().replace("-", "_").replace(" ", "_")
    return LPC_ACTION_ALIASES.get(action, action)


def _infer_part(root: Path, path: Path) -> Dict[str, Any]:
    rel = path.relative_to(root)
    pieces = list(rel.parts)
    category = pieces[0] if pieces else "parts"
    action = _normalize_action(path.stem)
    variant_parts = pieces[1:-1]
    body_type = next((part for part in reversed(variant_parts) if part.lower() in LPC_BODY_TYPES), "")
    layer_phase = next((part for part in reversed(variant_parts) if part.lower() in {"fg", "bg"}), "")
    label_bits = [part for part in variant_parts if part.lower() not in LPC_BODY_TYPES and part.lower() not in {"fg", "bg"}]
    variant = " ".join(label_bits) or category
    return {
        "id": safe_name("__".join(rel.with_suffix("").parts)),
        "category": category,
        "layer_order": LPC_LAYER_ORDER.index(category) if category in LPC_LAYER_ORDER else 999,
        "variant": variant.replace("_", " "),
        "body_type": body_type,
        "layer_phase": layer_phase,
        "action": action,
        "relative_path": rel.as_posix(),
        "path": str(path),
    }


def _thumbnail_data_uri(path: Path, size: int = 96) -> str:
    img = Image.open(path).convert("RGBA")
    img.thumbnail((size, size), Image.Resampling.NEAREST)
    buffer = BytesIO()
    img.save(buffer, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")


def _image_size(path: Path) -> Tuple[int, int]:
    with Image.open(path) as img:
        return img.size


def _caption(trigger: str, part: Dict[str, Any]) -> str:
    bits = [
        trigger,
        "LPC paper doll sprite part",
        f"{part['category']} layer",
        str(part.get("variant") or "").strip(),
        str(part.get("body_type") or "").strip(),
        f"{part['action']} animation",
        "transparent background",
        "pixel art",
    ]
    return ", ".join(bit for bit in bits if bit)


def _load_or_scan_catalog(source_dir: Path | str) -> Dict[str, Any]:
    source = Path(source_dir).resolve()
    catalog_path = DEFAULT_OUTPUT / "catalog.json"
    if catalog_path.exists():
        try:
            catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
            if Path(str(catalog.get("source_dir") or "")).resolve() == source:
                return catalog
        except (OSError, json.JSONDecodeError, ValueError):
            return scan_lpc_parts(source, thumbnail_limit=0)
    return scan_lpc_parts(source, thumbnail_limit=0)


def _selection_tokens(value: str) -> List[str]:
    return [
        token.lower()
        for token in str(value or "").replace("_", " ").replace("-", " ").split()
        if token.strip()
    ]


def _csv_items(value: str | List[str] | None, default: List[str]) -> List[str]:
    if isinstance(value, list):
        items = [str(item).strip() for item in value if str(item).strip()]
    else:
        items = [item.strip() for item in str(value or "").split(",") if item.strip()]
    return items or list(default)


def _part_search_text(part: Dict[str, Any]) -> str:
    return " ".join([
        str(part.get("variant") or ""),
        str(part.get("relative_path") or ""),
        str(part.get("id") or ""),
    ]).lower().replace("_", " ").replace("-", " ")


def _phase_rank(part: Dict[str, Any]) -> int:
    phase = str(part.get("layer_phase") or "").lower()
    if phase == "bg":
        return -1
    if phase == "fg":
        return 1
    return 0


def _layer_order(part: Dict[str, Any]) -> int:
    try:
        return int(part.get("layer_order"))
    except (TypeError, ValueError):
        return 999


def _body_compatible(requested: str, part_body: str) -> bool:
    requested = str(requested or "").lower()
    part_body = str(part_body or "").lower()
    if not requested or not part_body or requested == part_body:
        return True
    compatible = {
        "male": {"adult", "thin"},
        "female": {"adult", "thin"},
        "adult": {"male", "female", "thin"},
        "thin": {"adult", "male", "female"},
    }
    return part_body in compatible.get(requested, set())


def _find_lpc_part(
    catalog: Dict[str, Any],
    category: str,
    action: str,
    body_type: str,
    query: str = "",
) -> Dict[str, Any] | None:
    tokens = _selection_tokens(query)
    candidates: List[Tuple[Tuple[int, int, int, int, str], Dict[str, Any]]] = []
    for part in catalog.get("parts") or []:
        if part.get("category") != category:
            continue
        if int(part.get("unreadable") or 0):
            continue
        if part.get("action") != action:
            continue
        text = _part_search_text(part)
        if tokens and not all(token in text for token in tokens):
            continue
        part_body = str(part.get("body_type") or "")
        if not _body_compatible(body_type, part_body):
            continue
        score = (
            0 if part_body == body_type else 1,
            0 if tokens else 1,
            _layer_order(part),
            _phase_rank(part),
            str(part.get("relative_path") or ""),
        )
        candidates.append((score, part))
    if not candidates:
        return None
    candidates.sort(key=lambda item: item[0])
    return candidates[0][1]


def _candidate_lpc_parts(
    catalog: Dict[str, Any],
    category: str,
    action: str,
    body_type: str,
) -> List[Dict[str, Any]]:
    candidates: List[Dict[str, Any]] = []
    seen: set[str] = set()
    for part in catalog.get("parts") or []:
        if part.get("category") != category or part.get("action") != action:
            continue
        if int(part.get("unreadable") or 0):
            continue
        if not _body_compatible(body_type, str(part.get("body_type") or "")):
            continue
        key = str(part.get("relative_path") or part.get("id") or "")
        if key in seen:
            continue
        seen.add(key)
        candidates.append(part)
    candidates.sort(key=lambda part: (_layer_order(part), _phase_rank(part), str(part.get("relative_path") or "")))
    return candidates


def _parse_part_selection(value: str | Dict[str, Any] | None) -> Dict[str, str]:
    if isinstance(value, dict):
        return {str(k).strip(): str(v).strip() for k, v in value.items() if str(k).strip() and str(v).strip()}
    result: Dict[str, str] = {}
    for item in str(value or "").split(";"):
        if not item.strip():
            continue
        if ":" in item:
            category, query = item.split(":", 1)
        elif "=" in item:
            category, query = item.split("=", 1)
        else:
            continue
        category = category.strip()
        query = query.strip()
        if category and query:
            result[category] = query
    return result


def _compose_layers(layers: List[Dict[str, Any]]) -> Tuple[Image.Image, List[Dict[str, Any]]]:
    loaded: List[Tuple[Image.Image, Dict[str, Any]]] = []
    base_size: Tuple[int, int] | None = None
    for layer in layers:
        path = Path(str(layer.get("path") or ""))
        if not path.exists():
            continue
        try:
            img = Image.open(path).convert("RGBA")
        except OSError:
            layer["unreadable"] = True
            continue
        if base_size is None:
            base_size = img.size
        if img.size != base_size:
            continue
        loaded.append((img, layer))
    if not loaded or base_size is None:
        raise ValueError("No compatible readable LPC layers were found to compose. The LPC folder may contain broken links, cloud placeholders, or files on an unavailable drive.")
    canvas = Image.new("RGBA", base_size, (0, 0, 0, 0))
    used: List[Dict[str, Any]] = []
    for img, layer in loaded:
        canvas.alpha_composite(img)
        used.append(layer)
    return canvas, used


def _write_composition(
    sheet: Image.Image,
    used_layers: List[Dict[str, Any]],
    catalog: Dict[str, Any],
    out: Path,
    action: str,
    body_type: str,
    character_name: str,
    selections: Dict[str, str],
    missing: List[Dict[str, str]] | None = None,
) -> Dict[str, Any]:
    out.mkdir(parents=True, exist_ok=True)
    sheet_path = out / "sheet.png"
    sheet.save(sheet_path)
    meta = _sheet_metadata(sheet, action, character_name)
    manifest = {
        "ok": True,
        "schema": "spriteforge.lpc_composition.v1",
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "source_dir": catalog.get("source_dir"),
        "spritesheets_dir": catalog.get("spritesheets_dir"),
        "output_dir": str(out),
        "sheet": str(sheet_path),
        "sheet_json": str(out / "sheet.json"),
        "name": character_name,
        "action": action,
        "body_type": body_type,
        "selections": selections,
        "missing": missing or [],
        "layers": used_layers,
        "frame_width": meta["frame_width"],
        "frame_height": meta["frame_height"],
        "frame_count": meta["frame_count"],
        "columns": meta["columns"],
    }
    (out / "sheet.json").write_text(json.dumps({**meta, "lpc_manifest": "lpc_composition.json"}, indent=2), encoding="utf-8")
    (out / "lpc_composition.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    manifest["thumbnail_data_uri"] = _thumbnail_data_uri(sheet_path, size=160)
    return manifest


def _sheet_metadata(sheet: Image.Image, action: str, name: str) -> Dict[str, Any]:
    frame_width = 64 if sheet.width % 64 == 0 else sheet.width
    frame_height = 64 if sheet.height % 64 == 0 else sheet.height
    columns = max(1, sheet.width // frame_width)
    rows = max(1, sheet.height // frame_height)
    return {
        "image": "sheet.png",
        "animation": action,
        "name": name,
        "frame_width": frame_width,
        "frame_height": frame_height,
        "cell_width": frame_width,
        "cell_height": frame_height,
        "columns": columns,
        "rows": rows,
        "frame_count": columns * rows,
        "fps": 12,
        "source": "lpc_compositor",
    }


def compose_lpc_character(
    source_dir: Path | str,
    output_dir: Path | str | None = None,
    action: str = "idle",
    body_type: str = "male",
    selections: str | Dict[str, Any] | None = None,
    name: str = "",
) -> Dict[str, Any]:
    catalog = _load_or_scan_catalog(source_dir)
    action = _normalize_action(action or "idle")
    body_type = str(body_type or "male").strip().lower()
    chosen = _parse_part_selection(selections)
    chosen.setdefault("body", "bodies")
    selected_layers: List[Dict[str, Any]] = []
    missing: List[Dict[str, str]] = []

    for category, query in chosen.items():
        part = _find_lpc_part(catalog, category, action, body_type, query)
        if part:
            selected_layers.append(part)
        else:
            missing.append({"category": category, "query": query})

    selected_layers.sort(key=lambda part: (_layer_order(part), _phase_rank(part), str(part.get("relative_path") or "")))
    sheet, used_layers = _compose_layers(selected_layers)
    character_name = safe_name(name or f"lpc_{body_type}_{action}_{int(time.time())}")
    out = Path(output_dir).resolve() if output_dir else ROOT / "output" / "lpc_composed" / character_name
    return _write_composition(sheet, used_layers, catalog, out, action, body_type, character_name, chosen, missing)


def lpc_catalog_options(
    source_dir: Path | str,
    categories: List[str] | None = None,
    limit_per_category: int = 240,
) -> Dict[str, Any]:
    catalog = _load_or_scan_catalog(source_dir)
    wanted = categories or ["hair", "torso", "legs", "feet", "weapons", "hat", "cape", "shoulders"]
    options: Dict[str, List[Dict[str, str]]] = {category: [] for category in wanted}
    seen: Dict[str, set[str]] = {category: set() for category in wanted}
    for part in catalog.get("parts") or []:
        category = str(part.get("category") or "")
        if category not in options:
            continue
        variant = str(part.get("variant") or "").strip()
        if not variant or variant in seen[category]:
            continue
        seen[category].add(variant)
        options[category].append({
            "value": variant,
            "label": variant,
            "body_type": str(part.get("body_type") or ""),
            "sample_action": str(part.get("action") or ""),
        })
    for category in options:
        options[category] = sorted(options[category], key=lambda item: item["label"])[: max(1, limit_per_category)]
    return {
        "ok": True,
        "schema": "spriteforge.lpc_catalog_options.v1",
        "source_dir": catalog.get("source_dir"),
        "part_count": catalog.get("part_count", 0),
        "actions": sorted((catalog.get("action_counts") or {}).keys()),
        "body_types": sorted((catalog.get("body_type_counts") or {}).keys()),
        "categories": sorted((catalog.get("category_counts") or {}).keys()),
        "options": options,
    }


def compose_lpc_batch(
    source_dir: Path | str,
    output_dir: Path | str | None = None,
    count: int = 24,
    action: str = "idle",
    body_type: str = "male",
    actions: List[str] | None = None,
    body_types: List[str] | None = None,
    categories: List[str] | None = None,
    seed: int | None = None,
    trigger: str = "lpc_composed",
) -> Dict[str, Any]:
    catalog = _load_or_scan_catalog(source_dir)
    requested_actions = [_normalize_action(item) for item in _csv_items(actions, [action or "idle"])]
    requested_body_types = [item.lower() for item in _csv_items(body_types, [body_type or "male"])]
    wanted = categories or ["hair", "torso", "legs", "feet"]
    rng = random.Random(seed)
    out = Path(output_dir).resolve() if output_dir else ROOT / "output" / "training_datasets" / f"lpc_composed_{int(time.time())}"
    out.mkdir(parents=True, exist_ok=True)
    images_dir = out / "images"
    captions_dir = out / "captions"
    images_dir.mkdir(exist_ok=True)
    captions_dir.mkdir(exist_ok=True)

    candidate_map: Dict[Tuple[str, str], Dict[str, Any]] = {}
    for item_action in requested_actions:
        for item_body in requested_body_types:
            body_candidates = _candidate_lpc_parts(catalog, "body", item_action, item_body)
            candidate_map[(item_action, item_body)] = {
                "body": body_candidates,
                "categories": {
                    category: _candidate_lpc_parts(catalog, category, item_action, item_body)
                    for category in wanted
                },
            }
    valid_slots = [key for key, value in candidate_map.items() if value["body"]]
    if not valid_slots:
        raise ValueError(f"No LPC body sheets found for actions {', '.join(requested_actions)} and bodies {', '.join(requested_body_types)}.")

    samples: List[Dict[str, Any]] = []
    failures: List[str] = []
    target_count = max(1, min(1000, int(count or 1)))
    slot_counts: Counter[str] = Counter()
    attempts = 0
    while len(samples) < target_count and attempts < target_count * 8:
        attempts += 1
        item_action, item_body = valid_slots[len(samples) % len(valid_slots)]
        slot = candidate_map[(item_action, item_body)]
        selected_layers = [rng.choice(slot["body"])]
        selections = {"body": str(selected_layers[0].get("variant") or "bodies")}
        for category in wanted:
            choices = slot["categories"].get(category) or []
            if not choices:
                continue
            if category not in {"hair", "legs", "feet"} and rng.random() < 0.35:
                continue
            part = rng.choice(choices)
            selected_layers.append(part)
            selections[category] = str(part.get("variant") or part.get("relative_path") or category)
        selected_layers.sort(key=lambda part: (_layer_order(part), _phase_rank(part), str(part.get("relative_path") or "")))
        try:
            sheet, used_layers = _compose_layers(selected_layers)
        except ValueError as exc:
            failures.append(str(exc))
            continue
        name = safe_name(f"lpc_{item_body}_{item_action}_{len(samples) + 1:04d}")
        sample_out = out / name
        manifest = _write_composition(sheet, used_layers, catalog, sample_out, item_action, item_body, name, selections)
        caption = ", ".join([
            trigger,
            "LPC composed character spritesheet",
            f"{item_body} body",
            f"{item_action} animation",
            *[f"{layer['category']} {layer.get('variant') or ''}".strip() for layer in used_layers if layer.get("category") != "body"],
            "transparent background",
            "pixel art",
        ])
        (sample_out / "caption.txt").write_text(caption, encoding="utf-8")
        train_image = images_dir / f"{name}.png"
        train_caption = captions_dir / f"{name}.txt"
        train_sidecar = images_dir / f"{name}.txt"
        shutil.copy2(sample_out / "sheet.png", train_image)
        train_caption.write_text(caption, encoding="utf-8")
        train_sidecar.write_text(caption, encoding="utf-8")
        manifest["caption"] = caption
        manifest["training_image"] = str(train_image)
        manifest["training_caption"] = str(train_caption)
        samples.append(manifest)
        slot_counts[f"{item_body}/{item_action}"] += 1

    batch_manifest = {
        "ok": True,
        "schema": "spriteforge.lpc_composed_batch.v1",
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "source_dir": catalog.get("source_dir"),
        "output_dir": str(out),
        "requested_count": target_count,
        "sample_count": len(samples),
        "action": requested_actions[0],
        "body_type": requested_body_types[0],
        "actions": requested_actions,
        "body_types": requested_body_types,
        "categories": wanted,
        "seed": seed,
        "dataset_kind": "lpc_composed",
        "images_dir": str(images_dir),
        "captions_dir": str(captions_dir),
        "balance": dict(sorted(slot_counts.items())),
        "failures": failures[:10],
        "samples": samples,
    }
    (out / "manifest.json").write_text(json.dumps(batch_manifest, indent=2), encoding="utf-8")
    (out / "README_TRAINING_DATASET.md").write_text(
        "# SpriteForge LPC Composed Training Dataset\n\n"
        "This folder contains randomly composed Universal LPC character sheets with exact layer captions.\n"
        "Use the `images/` folder with matching `.txt` sidecars or the paired `captions/` folder for LoRA training.\n"
        f"Trigger token: `{trigger}`\n",
        encoding="utf-8",
    )
    return batch_manifest


def _image_blank(path: Path) -> bool:
    with Image.open(path).convert("RGBA") as img:
        alpha = img.getchannel("A")
        return alpha.getbbox() is None


def qa_lpc_dataset(
    dataset_dir: Path | str,
    min_layers: int = 3,
    max_balance_delta: int = 2,
) -> Dict[str, Any]:
    root = Path(dataset_dir).resolve()
    manifest_path = root / "manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"Missing LPC batch manifest: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    samples = manifest.get("samples") if isinstance(manifest.get("samples"), list) else []
    images_dir = Path(str(manifest.get("images_dir") or root / "images"))
    captions_dir = Path(str(manifest.get("captions_dir") or root / "captions"))

    issues: List[Dict[str, Any]] = []
    blank_samples: List[str] = []
    low_layer_samples: List[Dict[str, Any]] = []
    missing_files: List[str] = []
    hashes: Dict[str, List[str]] = {}
    caption_preview: List[Dict[str, str]] = []

    for sample in samples:
        name = str(sample.get("name") or Path(str(sample.get("sheet") or "")).stem or "sample")
        image_path = Path(str(sample.get("training_image") or images_dir / f"{name}.png"))
        caption_path = Path(str(sample.get("training_caption") or captions_dir / f"{name}.txt"))
        if not image_path.exists():
            missing_files.append(str(image_path))
            continue
        if not caption_path.exists() and not (image_path.with_suffix(".txt")).exists():
            missing_files.append(str(caption_path))
        layer_count = len(sample.get("layers") or [])
        if layer_count < min_layers:
            low_layer_samples.append({"name": name, "layers": layer_count})
        try:
            if _image_blank(image_path):
                blank_samples.append(name)
            digest = hashlib.sha256(image_path.read_bytes()).hexdigest()
            hashes.setdefault(digest, []).append(name)
        except Exception as exc:
            issues.append({"severity": "error", "message": f"Could not inspect {name}: {exc}"})
        caption = str(sample.get("caption") or "")
        if not caption and caption_path.exists():
            caption = caption_path.read_text(encoding="utf-8").strip()
        if len(caption_preview) < 6:
            caption_preview.append({"name": name, "caption": caption[:240]})

    duplicate_groups = [names for names in hashes.values() if len(names) > 1]
    balance = manifest.get("balance") if isinstance(manifest.get("balance"), dict) else {}
    balance_values = [int(value) for value in balance.values()] if balance else []
    balance_delta = (max(balance_values) - min(balance_values)) if balance_values else 0

    if missing_files:
        issues.append({"severity": "error", "message": f"{len(missing_files)} image/caption file(s) are missing."})
    if blank_samples:
        issues.append({"severity": "error", "message": f"{len(blank_samples)} blank image sample(s) found."})
    if low_layer_samples:
        issues.append({"severity": "warn", "message": f"{len(low_layer_samples)} sample(s) have fewer than {min_layers} layers."})
    if duplicate_groups:
        issues.append({"severity": "warn", "message": f"{len(duplicate_groups)} duplicate image group(s) found."})
    if balance_delta > max_balance_delta:
        issues.append({"severity": "warn", "message": f"Action/body balance delta is {balance_delta}."})
    if not samples:
        issues.append({"severity": "error", "message": "No LPC samples found in manifest."})

    ok = not any(issue["severity"] == "error" for issue in issues)
    result = {
        "ok": ok,
        "schema": "spriteforge.lpc_dataset_qa.v1",
        "dataset_dir": str(root),
        "sample_count": len(samples),
        "image_count": len(list(images_dir.glob("*.png"))) if images_dir.exists() else 0,
        "caption_count": len(list(captions_dir.glob("*.txt"))) if captions_dir.exists() else 0,
        "min_layers": min_layers,
        "balance": balance,
        "balance_delta": balance_delta,
        "issues": issues,
        "missing_files": missing_files[:20],
        "blank_samples": blank_samples[:20],
        "low_layer_samples": low_layer_samples[:20],
        "duplicate_groups": duplicate_groups[:10],
        "caption_preview": caption_preview,
    }
    (root / "qa_report.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def lpc_lora_prefill(dataset_dir: Path | str) -> Dict[str, Any]:
    root = Path(dataset_dir).resolve()
    manifest_path = root / "manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"Missing LPC batch manifest: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    qa_path = root / "qa_report.json"
    qa = json.loads(qa_path.read_text(encoding="utf-8")) if qa_path.exists() else qa_lpc_dataset(root)
    sample_count = int(manifest.get("sample_count") or qa.get("sample_count") or 0)
    first_sample = (manifest.get("samples") or [{}])[0]
    width = int(first_sample.get("frame_width") or 64)
    height = int(first_sample.get("frame_height") or 64)
    sheet_area = max(width, height)
    resolution = 512 if sheet_area <= 128 else 768
    if sample_count >= 300:
        steps = 1800
        repeats = 6
    elif sample_count >= 120:
        steps = 1400
        repeats = 8
    elif sample_count >= 48:
        steps = 1000
        repeats = 10
    else:
        steps = 700
        repeats = 12
    warnings: List[str] = []
    if sample_count < 48:
        warnings.append("Dataset is small for LoRA training; consider 48+ composed samples.")
    if not qa.get("ok"):
        warnings.append("Dataset QA has blocking issues; fix QA before training.")
    balance_delta = int(qa.get("balance_delta") or 0)
    if balance_delta > 2:
        warnings.append(f"Dataset balance delta is {balance_delta}; consider a more even batch.")
    prefill = {
        "ok": bool(qa.get("ok")),
        "schema": "spriteforge.lpc_lora_prefill.v1",
        "dataset_dir": str(root),
        "dataset_kind": manifest.get("dataset_kind") or "lpc_composed",
        "sample_count": sample_count,
        "qa_ok": bool(qa.get("ok")),
        "qa_report": str(qa_path),
        "recommendation": {
            "dataset_dir": str(root),
            "name": "lpc_composed_lora",
            "trigger": "lpc_composed",
            "model_family": "sdxl",
            "trainer": "auto",
            "resolution": resolution,
            "max_train_steps": steps,
            "learning_rate": "1e-4",
            "network_dim": 16 if sample_count >= 48 else 8,
            "repeats": repeats,
        },
        "summary": f"{sample_count} LPC composed samples, {resolution}px SDXL LoRA, {steps} steps, repeats {repeats}.",
        "warnings": warnings,
    }
    (root / "lora_prefill.json").write_text(json.dumps(prefill, indent=2), encoding="utf-8")
    return prefill


def scan_lpc_parts(
    source_dir: Path | str,
    output_dir: Path | str | None = None,
    thumbnail_limit: int = 24,
    max_files: int = 0,
) -> Dict[str, Any]:
    source = Path(source_dir).resolve()
    spritesheets = _spritesheets_root(source)
    out = Path(output_dir).resolve() if output_dir else DEFAULT_OUTPUT
    out.mkdir(parents=True, exist_ok=True)

    images = _image_paths(spritesheets, max_files)
    parts: List[Dict[str, Any]] = []
    category_counts: Counter[str] = Counter()
    action_counts: Counter[str] = Counter()
    body_counts: Counter[str] = Counter()
    size_counts: Counter[str] = Counter()
    readable_count = 0
    unreadable_count = 0

    for idx, path in enumerate(images):
        item = _infer_part(spritesheets, path)
        if idx < max(0, thumbnail_limit):
            try:
                width, height = _image_size(path)
                item["width"] = width
                item["height"] = height
                size_counts[f"{width}x{height}"] += 1
                readable_count += 1
                item["thumbnail_data_uri"] = _thumbnail_data_uri(path)
            except Exception:
                item["width"] = 0
                item["height"] = 0
                item["unreadable"] = True
                unreadable_count += 1
        else:
            item["width"] = 0
            item["height"] = 0
        category_counts[item["category"]] += 1
        action_counts[item["action"]] += 1
        if item["body_type"]:
            body_counts[item["body_type"]] += 1
        parts.append(item)

    manifest = {
        "schema": "spriteforge.lpc_parts_catalog.v1",
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "source_dir": str(source),
        "spritesheets_dir": str(spritesheets),
        "output_dir": str(out),
        "part_count": len(parts),
        "readable_part_count": readable_count,
        "unreadable_part_count": unreadable_count,
        "category_counts": dict(sorted(category_counts.items())),
        "action_counts": dict(sorted(action_counts.items())),
        "body_type_counts": dict(sorted(body_counts.items())),
        "sheet_size_counts": dict(size_counts.most_common(12)),
        "layer_order": LPC_LAYER_ORDER,
        "parts": parts,
        "samples": parts[: max(0, thumbnail_limit)],
        "write_performed": True,
    }
    (out / "catalog.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (out / "README_LPC_PARTS.md").write_text(
        "# SpriteForge LPC Parts Catalog\n\n"
        "This catalog indexes Universal LPC paper-doll layers for composition and private training workflows.\n"
        "Use the category, body_type, action, and layer_order fields to build complete characters before LoRA training.\n",
        encoding="utf-8",
    )
    return manifest


def build_lpc_part_dataset(
    source_dir: Path | str,
    output_dir: Path | str | None = None,
    trigger: str = "lpc_parts",
    max_samples: int = 0,
) -> Dict[str, Any]:
    catalog = scan_lpc_parts(source_dir, output_dir=DEFAULT_OUTPUT / "catalog_scan", thumbnail_limit=0)
    out = Path(output_dir).resolve() if output_dir else ROOT / "output" / "training_datasets" / f"lpc_parts_{int(time.time())}"
    images_dir = out / "images"
    captions_dir = out / "captions"
    images_dir.mkdir(parents=True, exist_ok=True)
    captions_dir.mkdir(parents=True, exist_ok=True)

    parts = catalog["parts"]
    if max_samples and max_samples > 0:
        parts = parts[:max_samples]

    samples: List[Dict[str, Any]] = []
    for part in parts:
        source = Path(part["path"])
        stem = safe_name(part["id"])
        dest = images_dir / f"{stem}.png"
        caption_path = captions_dir / f"{stem}.txt"
        sidecar_path = images_dir / f"{stem}.txt"
        shutil.copy2(source, dest)
        caption = _caption(trigger, part)
        caption_path.write_text(caption, encoding="utf-8")
        sidecar_path.write_text(caption, encoding="utf-8")
        samples.append({
            "source": str(source),
            "image": str(dest),
            "caption_file": str(caption_path),
            "caption": caption,
            "category": part["category"],
            "body_type": part.get("body_type") or "",
            "action": part["action"],
        })

    manifest = {
        "schema": "spriteforge.training_dataset.v1",
        "dataset_kind": "lpc_parts",
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "source_dir": catalog["source_dir"],
        "spritesheets_dir": catalog["spritesheets_dir"],
        "output_dir": str(out),
        "trigger": trigger,
        "sample_count": len(samples),
        "category_counts": catalog["category_counts"],
        "action_counts": catalog["action_counts"],
        "samples": samples,
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (out / "README_TRAINING_DATASET.md").write_text(
        "# SpriteForge LPC Part Dataset\n\n"
        "This dataset trains individual LPC-compatible transparent parts. For whole-character style training, build composed characters from the LPC catalog first.\n",
        encoding="utf-8",
    )
    return manifest
