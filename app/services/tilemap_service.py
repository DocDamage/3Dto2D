import os
import json
from pathlib import Path
from typing import Dict, Any, List, Optional
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent

class TilemapService:
    @staticmethod
    def generate_16_autotiles(base_path: str, border_path: str, output_path: str) -> Dict[str, Any]:
        """Compile a 16-tile autotile spritesheet by overlaying borders onto a base texture."""
        base_file = ROOT / base_path
        border_file = ROOT / border_path
        out_file = ROOT / output_path
        
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
            metadata_file.write_text(json.dumps({
                "type": "autotile_16",
                "tile_width": w,
                "tile_height": h,
                "columns": 4,
                "rows": 4,
                "bitmask_mode": "2x2",
                "rules": {
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
            }, indent=2), encoding="utf-8")
            
            return {
                "ok": True,
                "message": "Autotile sheet successfully generated.",
                "image_path": str(output_path).replace("\\", "/"),
                "tile_size": f"{w}x{h}"
            }
        except Exception as exc:
            return {"ok": False, "message": str(exc)}
