import re
import math
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple, Union
import numpy as np
from PIL import Image, ImageChops, ImageFilter

class SpriteService:
    @staticmethod
    def guess_key_color_from_corners(img: Image.Image) -> Tuple[int, int, int]:
        arr = np.asarray(img.convert("RGBA"))
        h, w, _ = arr.shape
        # Sample corners
        corners = [
            arr[0, 0, :3],
            arr[0, w - 1, :3],
            arr[h - 1, 0, :3],
            arr[h - 1, w - 1, :3]
        ]
        pixels = np.array(corners)
        rgb = np.median(pixels, axis=0)
        return tuple(int(round(x)) for x in rgb)  # type: ignore

    @staticmethod
    def apply_chroma_key(img: Image.Image, key_color: Union[Tuple[int, int, int], str], tolerance: float, feather: float) -> Image.Image:
        img = img.convert("RGBA")
        if key_color == "auto":
            rgb = SpriteService.guess_key_color_from_corners(img)
        else:
            rgb = key_color  # type: ignore

        arr = np.asarray(img).astype(np.float32)
        color = np.array(rgb, dtype=np.float32).reshape(1, 1, 3)
        dist = np.linalg.norm(arr[:, :, :3] - color, axis=2)

        tol = float(tolerance)
        feather = max(0.0, float(feather))
        if feather <= 0:
            alpha_factor = (dist > tol).astype(np.float32)
        else:
            alpha_factor = np.clip((dist - tol) / feather, 0.0, 1.0)

        arr[:, :, 3] = arr[:, :, 3] * alpha_factor
        return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), mode="RGBA")

    @staticmethod
    def alpha_bbox(img: Image.Image, threshold: int = 8) -> Optional[Tuple[int, int, int, int]]:
        arr = np.asarray(img.convert("RGBA"))
        alpha = arr[:, :, 3]
        ys, xs = np.where(alpha > threshold)
        if len(xs) == 0 or len(ys) == 0:
            return None
        return int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1

    @staticmethod
    def smooth_sequence(coords: List[float], window_size: int = 5) -> List[float]:
        if len(coords) < window_size:
            return coords
        smoothed = []
        half = window_size // 2
        for idx in range(len(coords)):
            start_idx = max(0, idx - half)
            end_idx = min(len(coords), idx + half + 1)
            smoothed.append(float(np.median(coords[start_idx:end_idx])))
        return smoothed

    @staticmethod
    def blend_loop_seam(frames: List[Any], blend_frames: int) -> List[Any]:
        if blend_frames <= 0 or len(frames) <= blend_frames * 2:
            return frames
        out = list(frames)
        n = len(frames)
        # Verify if frames are objects with an image attribute
        has_image_attr = hasattr(frames[0], "image")
        
        for i in range(blend_frames):
            idx_start = i
            idx_end = n - blend_frames + i
            alpha = (i + 0.5) / blend_frames
            
            img_start = frames[idx_start].image if has_image_attr else frames[idx_start]
            img_end = frames[idx_end].image if has_image_attr else frames[idx_end]
            
            blended = Image.blend(img_end, img_start, alpha)
            
            if has_image_attr:
                # Reconstruct the dataclass/FrameRecord object
                record_class = frames[idx_end].__class__
                out[idx_end] = record_class(frames[idx_end].index, blended, frames[idx_end].name)
            else:
                out[idx_end] = blended
        return out

    @staticmethod
    def solidify_transparent_rgb(img: Image.Image, radius: int = 2) -> Image.Image:
        if radius <= 0:
            return img.convert("RGBA")
        img = img.convert("RGBA")
        arr = np.asarray(img).copy()
        alpha = arr[:, :, 3]
        rgb_img = Image.fromarray(arr[:, :, :3], mode="RGB")
        blur = rgb_img.filter(ImageFilter.GaussianBlur(radius=radius))
        blur_arr = np.asarray(blur)
        transparent = alpha == 0
        arr[:, :, :3][transparent] = blur_arr[transparent]
        return Image.fromarray(arr, mode="RGBA")

    @staticmethod
    def stabilize_frame(img: Image.Image, target_anchor: Tuple[float, float], bbox: Optional[Tuple[int, int, int, int]] = None) -> Image.Image:
        img = img.convert("RGBA")
        bbox = bbox or SpriteService.alpha_bbox(img)
        if not bbox:
            return img
        l, t, r, b = bbox
        src_anchor_x = (l + r) / 2.0
        src_anchor_y = float(b)
        dx = int(round(target_anchor[0] - src_anchor_x))
        dy = int(round(target_anchor[1] - src_anchor_y))
        out = Image.new("RGBA", img.size, (0, 0, 0, 0))
        out.alpha_composite(img, (dx, dy))
        return out
