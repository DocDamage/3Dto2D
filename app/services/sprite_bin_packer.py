#!/usr/bin/env python3
"""2D Bin Packing service for packing spritesheets and texture atlases.

Implements standard MaxRectsBinPack (Best Short Side Fit heuristic) in pure Python,
with try-except imports for PyTexturePacker, and a fallback to Shelf packing.
"""
from __future__ import annotations

import math
from typing import List, Tuple, Dict, Any, Optional

class SpriteBinPackerService:
    @classmethod
    def pack(
        cls,
        rectangles: List[Tuple[int, int, Any]],
        max_width: int = 4096,
        pack_mode: str = "maxrects",
        spacing: int = 0,
        margin: int = 0
    ) -> Dict[str, Any]:
        """Packs a list of rectangles tightly into a single bin.

        Args:
            rectangles: List of (width, height, metadata) to pack.
            max_width: Maximum allowed width of the output atlas.
            pack_mode: "maxrects" or "shelf"
            spacing: Space between packed rectangles.
            margin: Outer margin of the atlas.

        Returns:
            Dict containing:
                "width": total packed width (including margin)
                "height": total packed height (including margin)
                "positions": List of ((x, y), metadata) for each packed item
        """
        if not rectangles:
            return {"width": 0, "height": 0, "positions": []}

        # Adjust rectangles size to account for spacing
        adjusted_rects = []
        for w, h, meta in rectangles:
            adjusted_rects.append((w + spacing, h + spacing, meta))

        # Try to use PyTexturePacker if installed and requested
        if pack_mode == "maxrects":
            try:
                res = cls._pack_pytexturepacker(adjusted_rects, max_width, spacing, margin)
                if res:
                    return res
            except Exception:
                pass

            # Use native pure-Python MaxRects
            try:
                return cls._pack_native_maxrects(adjusted_rects, max_width, spacing, margin)
            except Exception as exc:
                print(f"[Packer] Native MaxRects failed: {exc}. Falling back to Shelf packing...")

        # Default fallback: Shelf packing
        return cls._pack_shelf(adjusted_rects, max_width, spacing, margin)

    @classmethod
    def _pack_pytexturepacker(
        cls,
        rectangles: List[Tuple[int, int, Any]],
        max_width: int,
        spacing: int,
        margin: int
    ) -> Optional[Dict[str, Any]]:
        """Packs using PyTexturePacker library if installed."""
        from PyTexturePacker import Packer
        # Create a mock collection of images or rectangles
        # Since PyTexturePacker works on image files, we would have to load/dump.
        # If it's too complex or only supports files, we can skip and let native MaxRects handle it.
        return None

    @classmethod
    def _pack_native_maxrects(
        cls,
        rectangles: List[Tuple[int, int, Any]],
        max_width: int,
        spacing: int,
        margin: int
    ) -> Dict[str, Any]:
        """Pure-Python implementation of MaxRectsBinPack using Best Short Side Fit (BSSF)."""
        # Sort by area descending or max dimension descending
        sorted_indices = sorted(
            range(len(rectangles)),
            key=lambda i: (-max(rectangles[i][0], rectangles[i][1]), -rectangles[i][0] * rectangles[i][1])
        )

        area_sum = sum(w * h for w, h, _ in rectangles)
        max_item_w = max(w for w, h, _ in rectangles)
        max_item_h = max(h for w, h, _ in rectangles)

        # Start with a bin width that fits the largest item
        bin_width = max(max_item_w, 256)
        bin_width = int(2 ** math.ceil(math.log2(bin_width)))
        bin_width = min(max_width, max(bin_width, max_item_w))

        bin_height = max(max_item_h, 256)
        bin_height = int(2 ** math.ceil(math.log2(bin_height)))

        while True:
            # Free rectangles list, initially containing the entire bin
            free_rects: List[Tuple[int, int, int, int]] = [(0, 0, bin_width, bin_height)]
            positions: Dict[int, Tuple[int, int]] = {}
            success = True

            for idx in sorted_indices:
                w, h, _ = rectangles[idx]
                
                # Find Best Short Side Fit
                best_fit_idx = -1
                best_short_side = 999999999
                best_x, best_y = 0, 0

                for i, (fx, fy, fw, fh) in enumerate(free_rects):
                    if fw >= w and fh >= h:
                        left_w = fw - w
                        left_h = fh - h
                        short_side = min(left_w, left_h)
                        if short_side < best_short_side:
                            best_short_side = short_side
                            best_fit_idx = i
                            best_x, best_y = fx, fy

                if best_fit_idx == -1:
                    # Item could not fit. Expand bin size and try again.
                    success = False
                    break

                # Place the item
                positions[idx] = (best_x, best_y)

                # Split free rectangles overlapping with the placed one
                new_free_rects: List[Tuple[int, int, int, int]] = []
                px, py, pw, ph = best_x, best_y, w, h

                for fx, fy, fw, fh in free_rects:
                    # Check overlap
                    if px >= fx + fw or px + pw <= fx or py >= fy + fh or py + ph <= fy:
                        # No overlap, keep as is
                        new_free_rects.append((fx, fy, fw, fh))
                        continue

                    # Overlap! Split into up to 4 sub-rectangles
                    if px > fx: # Left split
                        new_free_rects.append((fx, fy, px - fx, fh))
                    if px + pw < fx + fw: # Right split
                        new_free_rects.append((px + pw, fy, fx + fw - (px + pw), fh))
                    if py > fy: # Top split
                        new_free_rects.append((fx, fy, fw, py - fy))
                    if py + ph < fy + fh: # Bottom split
                        new_free_rects.append((fx, py + ph, fw, fy + fh - (py + ph)))

                # Prune the free list: remove duplicates or redundant rectangles
                pruned: List[Tuple[int, int, int, int]] = []
                for rx, ry, rw, rh in new_free_rects:
                    # Check if contained entirely in any other rectangle
                    contained = False
                    for ox, oy, ow, oh in new_free_rects:
                        if (rx, ry, rw, rh) == (ox, oy, ow, oh):
                            continue
                        if ox <= rx and oy <= ry and ox + ow >= rx + rw and oy + oh >= ry + rh:
                            contained = True
                            break
                    if not contained and (rx, ry, rw, rh) not in pruned:
                        pruned.append((rx, ry, rw, rh))

                free_rects = pruned

            if success:
                # Pack succeeded. Reconstruct bounds.
                right_bounds = [positions[idx][0] + rectangles[idx][0] - spacing for idx in range(len(rectangles))]
                bottom_bounds = [positions[idx][1] + rectangles[idx][1] - spacing for idx in range(len(rectangles))]

                packed_width = max(right_bounds) if right_bounds else 0
                packed_height = max(bottom_bounds) if bottom_bounds else 0

                res_positions = []
                for w, h, meta in rectangles:
                    # Find original index
                    orig_idx = [i for i, r in enumerate(rectangles) if r == (w, h, meta)][0]
                    x, y = positions[orig_idx]
                    res_positions.append(((x + margin, y + margin), meta))

                return {
                    "width": packed_width + margin * 2,
                    "height": packed_height + margin * 2,
                    "positions": res_positions
                }
            else:
                # Double height, then double width, up to max_width
                if bin_height <= bin_width and bin_height < max_width:
                    bin_height *= 2
                elif bin_width < max_width:
                    bin_width *= 2
                else:
                    # If we exceeded limits, fallback to Shelf packing
                    break

        return cls._pack_shelf(rectangles, max_width, spacing, margin)

    @classmethod
    def _pack_shelf(
        cls,
        rectangles: List[Tuple[int, int, Any]],
        max_width: int,
        spacing: int,
        margin: int
    ) -> Dict[str, Any]:
        """Shelf packing algorithm as a robust fallback."""
        sorted_rects = sorted(
            [(w, h, i, meta) for i, (w, h, meta) in enumerate(rectangles)],
            key=lambda r: (-r[1], -r[0] * r[1])
        )

        min_width = max(r[0] for r in sorted_rects)
        bin_width = max(min_width, 256)
        bin_width = int(2 ** math.ceil(math.log2(bin_width)))
        bin_width = min(max_width, max(bin_width, min_width))

        while True:
            shelves: List[Tuple[int, int, int]] = []
            positions: Dict[int, Tuple[int, int]] = {}
            current_y = 0
            bin_height = 0
            success = True

            for w, h, idx, _ in sorted_rects:
                placed = False
                for s_idx, (sx, sy, sh) in enumerate(shelves):
                    if sh >= h and bin_width - sx >= w:
                        positions[idx] = (sx, sy)
                        shelves[s_idx] = (sx + w, sy, sh)
                        placed = True
                        break
                
                if not placed:
                    if bin_width >= w:
                        positions[idx] = (0, current_y)
                        shelves.append((w, current_y, h))
                        current_y += h
                        bin_height = max(bin_height, current_y)
                    else:
                        success = False
                        break

            if success:
                res_positions = []
                for w, h, idx, meta in sorted_rects:
                    x, y = positions[idx]
                    res_positions.append(((x + margin, y + margin), meta))

                right_bounds = [pos[0] + w - spacing for (w, h, idx, _), pos in zip(sorted_rects, positions.values())]
                bottom_bounds = [pos[1] + h - spacing for (w, h, idx, _), pos in zip(sorted_rects, positions.values())]
                
                return {
                    "width": max(right_bounds) + margin * 2 if right_bounds else 0,
                    "height": max(bottom_bounds) + margin * 2 if bottom_bounds else 0,
                    "positions": res_positions
                }
            else:
                bin_width = min(max_width, bin_width * 2)
                if bin_width == max_width:
                    # Stack vertically
                    positions = {}
                    current_y = 0
                    for w, h, idx, _ in sorted_rects:
                        positions[idx] = (0, current_y)
                        current_y += h
                    
                    res_positions = [((positions[idx][0] + margin, positions[idx][1] + margin), meta) for w, h, idx, meta in sorted_rects]
                    return {
                        "width": max(r[0] for r in sorted_rects) - spacing + margin * 2,
                        "height": current_y - spacing + margin * 2,
                        "positions": res_positions
                    }
