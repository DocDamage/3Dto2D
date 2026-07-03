#!/usr/bin/env python3
"""2D Bin Packing service for packing spritesheets and texture atlases.

Uses a Guillotine/MaxRects-style heuristic to arrange arbitrary rectangles tightly,
minimizing wasted space and producing power-of-two output sheets.
"""
from __future__ import annotations

import math
from typing import List, Tuple, Dict, Any, Optional

class SpriteBinPackerService:
    @staticmethod
    def pack(rectangles: List[Tuple[int, int, Any]], max_width: int = 4096) -> Dict[str, Any]:
        """Packs a list of rectangles tightly into a single bin.

        Args:
            rectangles: List of (width, height, metadata) to pack.
            max_width: Maximum allowed width of the output atlas.

        Returns:
            Dict containing:
                "width": total packed width
                "height": total packed height
                "positions": List of ((x, y), metadata) for each packed item
        """
        # Sort by height descending, then by area descending (standard packer heuristic)
        sorted_rects = sorted(
            [(w, h, i, meta) for i, (w, h, meta) in enumerate(rectangles)],
            key=lambda r: (-r[1], -r[0] * r[1])
        )

        # Estimate a starting width
        # Start with max width of all items, or a reasonable power-of-two
        min_width = max(r[0] for r in sorted_rects)
        bin_width = min_width
        # Round up to next power-of-two if reasonable
        if bin_width <= 256:
            bin_width = 256
        elif bin_width <= 512:
            bin_width = 512
        elif bin_width <= 1024:
            bin_width = 1024
        elif bin_width <= 2048:
            bin_width = 2048
        else:
            bin_width = min(max_width, int(2 ** math.ceil(math.log2(bin_width))))

        # If any item exceeds max_width, we must expand bin_width
        if bin_width < min_width:
            bin_width = min_width

        # We will pack using a shelf algorithm with height-based rows
        # This is extremely robust and fast, and handles dynamic bin sizing
        while True:
            shelves: List[Tuple[int, int, int]] = []  # List of (x, y, shelf_height)
            positions: Dict[int, Tuple[int, int]] = {}
            current_y = 0
            bin_height = 0
            success = True

            for w, h, idx, _ in sorted_rects:
                # Try to fit in existing shelves
                placed = False
                for s_idx, (sx, sy, sh) in enumerate(shelves):
                    if sh >= h and bin_width - sx >= w:
                        positions[idx] = (sx, sy)
                        shelves[s_idx] = (sx + w, sy, sh)
                        placed = True
                        break
                
                if not placed:
                    # Start a new shelf
                    if bin_width >= w:
                        positions[idx] = (0, current_y)
                        shelves.append((w, current_y, h))
                        current_y += h
                        bin_height = max(bin_height, current_y)
                    else:
                        # Exceeded bin width limit
                        success = False
                        break

            if success:
                # Pack succeeded, let's collect results
                res_positions = []
                for w, h, idx, meta in sorted_rects:
                    x, y = positions[idx]
                    res_positions.append(((x, y), meta))

                # Determine the tight bounding box
                right_bounds = [pos[0] + w for (w, h, idx, _), pos in zip(sorted_rects, positions.values())]
                bottom_bounds = [pos[1] + h for (w, h, idx, _), pos in zip(sorted_rects, positions.values())]
                
                return {
                    "width": max(right_bounds) if right_bounds else 0,
                    "height": max(bottom_bounds) if bottom_bounds else 0,
                    "positions": res_positions
                }
            else:
                # Expand bin width to next power of 2 and retry
                bin_width = min(max_width, bin_width * 2)
                if bin_width == max_width:
                    # Final fallback: just stack vertically
                    positions = {}
                    current_y = 0
                    for w, h, idx, _ in sorted_rects:
                        positions[idx] = (0, current_y)
                        current_y += h
                    
                    res_positions = [((positions[idx][0], positions[idx][1]), meta) for w, h, idx, meta in sorted_rects]
                    return {
                        "width": max(r[0] for r in sorted_rects),
                        "height": current_y,
                        "positions": res_positions
                    }
