#!/usr/bin/env python3
"""Pixel-art grid snapping and anti-aliasing edge cleanup service."""
from __future__ import annotations

import numpy as np
from PIL import Image

class SpritePixelSnapper:
    @staticmethod
    def snap_pixels_to_grid(
        img: Image.Image,
        scale: int = 2,
        alpha_threshold: int = 128
    ) -> Image.Image:
        """Snap image pixels to a grid of size `scale` x `scale` and sharpen edges.

        This removes soft anti-aliased edge pixels and aligns the character to a
        crisp visual pixel grid.
        """
        if scale <= 1:
            return img.convert("RGBA")

        # Convert to numpy RGBA array
        arr = np.asarray(img.convert("RGBA")).copy()
        h, w, c = arr.shape

        # Process in blocks of size `scale` x `scale`
        for y in range(0, h, scale):
            for x in range(0, w, scale):
                # Calculate slice boundaries
                y_end = min(y + scale, h)
                x_end = min(x + scale, w)
                
                block = arr[y:y_end, x:x_end]
                block_h, block_w, _ = block.shape
                
                # Reshape to 2D list of pixels
                pixels = block.reshape(-1, 4)
                alphas = pixels[:, 3]
                
                # Check average alpha of the block
                avg_alpha = np.mean(alphas)
                
                if avg_alpha < alpha_threshold:
                    # Clear block to transparent
                    arr[y:y_end, x:x_end] = [0, 0, 0, 0]
                else:
                    # Find non-transparent pixels
                    visible_mask = alphas > 32
                    if visible_mask.any():
                        visible_pixels = pixels[visible_mask]
                        # Compute mean color of visible pixels
                        mean_color = np.mean(visible_pixels[:, :3], axis=0).astype(np.uint8)
                        # Fill block with the mean color and fully opaque alpha
                        arr[y:y_end, x:x_end] = [mean_color[0], mean_color[1], mean_color[2], 255]
                    else:
                        arr[y:y_end, x:x_end] = [0, 0, 0, 0]

        return Image.fromarray(arr, mode="RGBA")
