import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Tuple
from PIL import Image

from spriteforge_utils import ROOT

logger = logging.getLogger(__name__)

AUTOTILE_EDGE_BITS = [
    {"index": i, "north": bool(i & 1), "south": bool(i & 2), "east": bool(i & 4), "west": bool(i & 8)}
    for i in range(16)
]


def _resolve_tile_path(value: str) -> Path:
    path = Path(str(value or ""))
    return path if path.is_absolute() else ROOT / path


def _rel_output(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT.resolve())).replace("\\", "/")
    except Exception as exc:
        logger.debug("Could not render tilemap output path %s relative to %s: %s", path, ROOT, exc)
        return str(path).replace("\\", "/")


def build_autotile_engine_layouts(tile_width: int, tile_height: int) -> Dict[str, Any]:
    tiles = []
    for bits in AUTOTILE_EDGE_BITS:
        index = bits["index"]
        col = index % 4
        row = index // 4
        neighbors = {
            "north": not bits["north"],
            "south": not bits["south"],
            "east": not bits["east"],
            "west": not bits["west"],
        }
        tiles.append({
            "index": index,
            "rect": {
                "x": col * tile_width,
                "y": row * tile_height,
                "w": tile_width,
                "h": tile_height,
            },
            "border_bits": {key: bits[key] for key in ("north", "south", "east", "west")},
            "open_neighbors": neighbors,
            "godot_terrain_peering_bits": {
                "top_side": neighbors["north"],
                "bottom_side": neighbors["south"],
                "right_side": neighbors["east"],
                "left_side": neighbors["west"],
            },
            "rpg_maker_tile_id": f"A2_{index:02d}",
        })
    return {
        "godot": {
            "terrain_set": "matches_sides",
            "tile_shape": "square",
            "tile_layout": "4x4",
            "tiles": tiles,
        },
        "rpg_maker": {
            "format": "A2-compatible-16tile-subset",
            "tile_layout": "4x4",
            "tiles": [
                {
                    "tile_id": tile["rpg_maker_tile_id"],
                    "source_index": tile["index"],
                    "rect": tile["rect"],
                    "open_neighbors": tile["open_neighbors"],
                }
                for tile in tiles
            ],
        },
    }


def build_tilemap_engine_manifest(
    tile_type: str,
    image_name: str,
    tile_width: int,
    tile_height: int,
    columns: int,
    rows: int,
    rules: List[Dict[str, Any]] | Dict[str, Any],
) -> Dict[str, Any]:
    tile_count = columns * rows
    if isinstance(rules, list):
        rule_by_index = {
            int(rule.get("index", index)): rule
            for index, rule in enumerate(rules)
            if isinstance(rule, dict)
        }
    else:
        rule_by_index = {
            int(key): {"description": value}
            for key, value in rules.items()
            if str(key).isdigit()
        }
    tiles = []
    for index in range(tile_count):
        col = index % columns
        row = index // columns
        rule = rule_by_index.get(index, {})
        tiles.append({
            "index": index,
            "rect": {
                "x": col * tile_width,
                "y": row * tile_height,
                "w": tile_width,
                "h": tile_height,
            },
            "rule": rule,
            "godot": {
                "atlas_coords": [col, row],
                "terrain_peering_bits": rule.get("open_neighbors") or rule.get("edges") or {},
            },
            "tiled": {
                "id": index,
                "type": tile_type,
                "properties": rule,
            },
            "rpg_maker": {
                "tile_id": f"A2_{index:02d}" if tile_type == "autotile_16" else f"WANG_{index:02d}",
            },
        })
    return {
        "schema": "spriteforge.tilemap_engine_manifest.v1",
        "type": tile_type,
        "image": image_name,
        "tile_width": tile_width,
        "tile_height": tile_height,
        "columns": columns,
        "rows": rows,
        "tile_count": tile_count,
        "tiles": tiles,
        "import": {
            "godot": {
                "resource_type": "TileSet",
                "texture_region_size": [tile_width, tile_height],
                "terrain_set_mode": "match_sides" if tile_type == "autotile_16" else "wang_edge_labels",
                "recommended_physics_layer": 0,
            },
            "rpg_maker": {
                "sheet_type": "A2-compatible-16tile-subset" if tile_type == "autotile_16" else "manual_wang_sheet",
                "tile_size": [tile_width, tile_height],
            },
            "tiled": {
                "tilewidth": tile_width,
                "tileheight": tile_height,
                "columns": columns,
                "tilecount": tile_count,
            },
        },
        "collision": {
            "default": "solid_on_border_tiles",
            "shapes": [
                {
                    "tile_index": index,
                    "shape": "rectangle",
                    "rect": {"x": 0, "y": 0, "w": tile_width, "h": tile_height},
                }
                for index in range(tile_count)
            ],
        },
        "rules": rules,
    }


class TilemapService:
    @staticmethod
    def generate_16_autotiles(base_path: str, border_path: str, output_path: str) -> Dict[str, Any]:
        """Compile a 16-tile autotile spritesheet by overlaying borders onto a base texture."""
        base_file = _resolve_tile_path(base_path)
        border_file = _resolve_tile_path(border_path)
        out_file = _resolve_tile_path(output_path)
        
        if not base_file.exists():
            return {"ok": False, "message": f"Base tile image not found: {base_path}"}
        if not border_file.exists():
            return {"ok": False, "message": f"Border tile image not found: {border_path}"}
            
        try:
            base_img = Image.open(base_file).convert("RGBA")
            border_img = Image.open(border_file).convert("RGBA")
            
            w, h = base_img.size
            border_img = border_img.resize((w, h), Image.Resampling.NEAREST)
            
            # Slice edges from border tile (default 12.5% thickness)
            edge = max(2, w // 8)
            top_b = border_img.crop((0, 0, w, edge))
            bot_b = border_img.crop((0, h - edge, w, h))
            left_b = border_img.crop((0, 0, edge, h))
            right_b = border_img.crop((w - edge, 0, w, h))
            
            # Create a 4x4 grid of tiles
            sheet = Image.new("RGBA", (w * 4, h * 4), (0, 0, 0, 0))
            
            for i in range(16):
                # Bit representation of N, S, E, W borders
                n = (i & 1) != 0
                s = (i & 2) != 0
                e = (i & 4) != 0
                w_b = (i & 8) != 0
                
                tile = base_img.copy()
                # Paste borders where active
                if n:
                    tile.alpha_composite(top_b, (0, 0))
                if s:
                    tile.alpha_composite(bot_b, (0, h - edge))
                if e:
                    tile.alpha_composite(right_b, (w - edge, 0))
                if w_b:
                    tile.alpha_composite(left_b, (0, 0))
                    
                col = i % 4
                row = i // 4
                sheet.paste(tile, (col * w, row * h))
                
            out_file.parent.mkdir(parents=True, exist_ok=True)
            sheet.save(out_file, "PNG")
            
            # Also write Godot/Unity autotile metadata notes
            metadata_file = out_file.with_suffix(".json")
            rules = {
                "0": "isolated (borders on N,S,E,W)",
                "1": "open north (borders on S,E,W)",
                "2": "open south (borders on N,E,W)",
                "3": "open north-south (borders on E,W)",
                "4": "open east (borders on N,S,W)",
                "5": "open north-east (borders on S,W)",
                "6": "open south-east (borders on N,W)",
                "7": "open north-south-east (border on W)",
                "8": "open west (borders on N,S,E)",
                "9": "open north-west (borders on S,E)",
                "10": "open south-west (borders on N,E)",
                "11": "open north-south-west (border on E)",
                "12": "open east-west (borders on N,S)",
                "13": "open north-east-west (border on S)",
                "14": "open south-east-west (border on N)",
                "15": "center / fully open (no borders)"
            }
            engine_manifest = build_tilemap_engine_manifest("autotile_16", out_file.name, w, h, 4, 4, rules)
            metadata_file.write_text(json.dumps({
                "type": "autotile_16",
                "tile_width": w,
                "tile_height": h,
                "columns": 4,
                "rows": 4,
                "bitmask_mode": "2x2",
                "engine_layouts": build_autotile_engine_layouts(w, h),
                "engine_manifest": engine_manifest,
                "rules": rules,
            }, indent=2), encoding="utf-8")
            
            return {
                "ok": True,
                "message": "Autotile sheet successfully generated.",
                "image_path": _rel_output(out_file),
                "metadata_path": _rel_output(metadata_file),
                "tile_size": f"{w}x{h}"
            }
        except Exception as exc:
            return {"ok": False, "message": str(exc)}

    @staticmethod
    def generate_wang_tiles(
        north_path: str,
        east_path: str,
        south_path: str,
        west_path: str,
        output_path: str,
        tile_size: int = 0,
    ) -> Dict[str, Any]:
        """Generate a 16-tile Wang sheet from four directional material tiles.

        Each output tile is a quadrant blend of the material assigned to its
        north/east/south/west edge code. Metadata records edge colors so game
        engines or downstream tools can match neighbors deterministically.
        """
        source_paths = {
            "north": _resolve_tile_path(north_path),
            "east": _resolve_tile_path(east_path),
            "south": _resolve_tile_path(south_path),
            "west": _resolve_tile_path(west_path),
        }
        missing = [name for name, path in source_paths.items() if not path.exists()]
        if missing:
            return {"ok": False, "message": "Missing Wang source tile(s): " + ", ".join(missing)}

        try:
            sources = {name: Image.open(path).convert("RGBA") for name, path in source_paths.items()}
            if tile_size <= 0:
                tile_size = min(min(img.size) for img in sources.values())
            tile_size = max(4, int(tile_size))
            sources = {
                name: img.resize((tile_size, tile_size), Image.Resampling.NEAREST)
                for name, img in sources.items()
            }
            out_file = _resolve_tile_path(output_path)
            sheet = Image.new("RGBA", (tile_size * 4, tile_size * 4), (0, 0, 0, 0))
            rules: List[Dict[str, Any]] = []

            for idx in range(16):
                edges = {
                    "north": "north" if idx & 1 else "south",
                    "east": "east" if idx & 2 else "west",
                    "south": "south" if idx & 4 else "north",
                    "west": "west" if idx & 8 else "east",
                }
                tile = TilemapService._compose_wang_tile(sources, edges, tile_size)
                col = idx % 4
                row = idx // 4
                sheet.alpha_composite(tile, (col * tile_size, row * tile_size))
                rules.append({
                    "index": idx,
                    "x": col * tile_size,
                    "y": row * tile_size,
                    "edges": edges,
                })

            out_file.parent.mkdir(parents=True, exist_ok=True)
            sheet.save(out_file, "PNG")
            metadata = {
                "type": "wang_16",
                "tile_width": tile_size,
                "tile_height": tile_size,
                "columns": 4,
                "rows": 4,
                "edge_order": ["north", "east", "south", "west"],
                "source_tiles": {name: _rel_output(path) for name, path in source_paths.items()},
                "rules": rules,
                "engine_manifest": build_tilemap_engine_manifest("wang_16", out_file.name, tile_size, tile_size, 4, 4, rules),
                "godot_notes": "Use edge labels to create Terrain Set peering bits or custom Wang matching.",
            }
            out_file.with_suffix(".json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
            return {
                "ok": True,
                "message": "Wang tile sheet successfully generated.",
                "image_path": _rel_output(out_file),
                "metadata_path": _rel_output(out_file.with_suffix(".json")),
                "tile_size": f"{tile_size}x{tile_size}",
                "tile_count": 16,
            }
        except Exception as exc:
            return {"ok": False, "message": str(exc)}

    @staticmethod
    def _compose_wang_tile(
        sources: Dict[str, Image.Image],
        edges: Dict[str, str],
        tile_size: int,
    ) -> Image.Image:
        half = tile_size // 2
        tile = Image.new("RGBA", (tile_size, tile_size), (0, 0, 0, 0))
        quadrants: List[Tuple[str, Tuple[int, int, int, int]]] = [
            (edges["north"], (0, 0, half, half)),
            (edges["east"], (half, 0, tile_size, half)),
            (edges["south"], (half, half, tile_size, tile_size)),
            (edges["west"], (0, half, half, tile_size)),
        ]
        for source_name, box in quadrants:
            tile.alpha_composite(sources[source_name].crop(box), (box[0], box[1]))
        return tile
