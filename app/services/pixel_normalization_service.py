from __future__ import annotations
import numpy as np
from PIL import Image
from typing import Any, Dict, Tuple, List
from collections import deque

from services.sprite_chroma_alpha import apply_native_pixel_cleanup, add_outline

class PixelNormalizationService:
    @staticmethod
    def resize_canvas(img: Image.Image, size: Tuple[int, int]) -> Image.Image:
        """Resizes the image to the target resolution using nearest-neighbor interpolation."""
        if img.size == size:
            return img.convert("RGBA")
        return img.convert("RGBA").resize(size, Image.Resampling.NEAREST)

    @staticmethod
    def clean_alpha(img: Image.Image, threshold: int = 128) -> Image.Image:
        """Forces alpha values to be fully opaque or fully transparent."""
        arr = np.asarray(img.convert("RGBA")).copy()
        alpha = arr[:, :, 3]
        arr[:, :, 3] = np.where(alpha > threshold, 255, 0).astype(np.uint8)
        return Image.fromarray(arr, mode="RGBA")

    @staticmethod
    def remove_islands(img: Image.Image, min_size: int = 2) -> Image.Image:
        """Removes small isolated pixel islands smaller than min_size using BFS."""
        if min_size <= 1:
            return img.convert("RGBA")

        arr = np.asarray(img.convert("RGBA")).copy()
        h, w = arr.shape[:2]
        alpha = arr[:, :, 3]
        visible = alpha > 0

        visited = np.zeros((h, w), dtype=bool)

        for y in range(h):
            for x in range(w):
                if visible[y, x] and not visited[y, x]:
                    # Start BFS
                    component = []
                    queue = deque([(y, x)])
                    visited[y, x] = True

                    while queue:
                        cy, cx = queue.popleft()
                        component.append((cy, cx))

                        # 8-connectivity neighbors
                        for dy in [-1, 0, 1]:
                            for dx in [-1, 0, 1]:
                                if dy == 0 and dx == 0:
                                    continue
                                ny, nx = cy + dy, cx + dx
                                if 0 <= ny < h and 0 <= nx < w:
                                    if visible[ny, nx] and not visited[ny, nx]:
                                        visited[ny, nx] = True
                                        queue.append((ny, nx))

                    # If component is smaller than threshold, erase it
                    if len(component) < min_size:
                        for cy, cx in component:
                            arr[cy, cx] = [0, 0, 0, 0]

        return Image.fromarray(arr, mode="RGBA")

    @staticmethod
    def normalize_asset(img: Image.Image, rules: Dict[str, Any]) -> Image.Image:
        """Runs the complete pixel normalization pipeline."""
        # 1. Enforce resolution (resize canvas first)
        res = rules.get("resolution", (32, 32))
        if isinstance(res, list):
            res = tuple(res)
        img = PixelNormalizationService.resize_canvas(img, res)

        # 2. Alpha cleanup
        if rules.get("clean_alpha", True):
            img = PixelNormalizationService.clean_alpha(img)

        # 3. Palette reduction
        if rules.get("quantize_palette", True):
            max_colors = rules.get("max_colors", 24)
            img = apply_native_pixel_cleanup(img, colors=max_colors)

        # 4. Remove small floating pixel islands
        if rules.get("remove_islands", True):
            min_island_size = rules.get("min_island_size", 2)
            img = PixelNormalizationService.remove_islands(img, min_island_size)

        # 5. Add outline pass
        outline_style = rules.get("outline", "none")
        if outline_style != "none":
            # Add a 1-pixel dark outline around the sprite
            img = add_outline(img, width=1, color=(0, 0, 0, 255))

        return img
