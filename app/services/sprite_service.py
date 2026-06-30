import re
import math
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple, Union
import numpy as np
from PIL import Image, ImageChops, ImageFilter
try:
    import cv2  # type: ignore
except Exception:  # pragma: no cover - optional acceleration
    cv2 = None

__all__ = ["SpriteService"]

class SpriteService:
    @staticmethod
    def guess_key_color_from_corners(img: Image.Image) -> Tuple[int, int, int]:
        arr = np.asarray(img.convert("RGBA"))
        h, w, _ = arr.shape
        band = max(1, min(24, h // 8, w // 8))
        border = np.concatenate(
            [
                arr[:band, :, :3].reshape(-1, 3),
                arr[h - band :, :, :3].reshape(-1, 3),
                arr[:, :band, :3].reshape(-1, 3),
                arr[:, w - band :, :3].reshape(-1, 3),
            ],
            axis=0,
        )

        rgb_float = border.astype(np.float32)
        saturation = rgb_float.max(axis=1) - rgb_float.min(axis=1)
        brightness = rgb_float.max(axis=1)
        saturated = border[(saturation >= 35) & (brightness >= 50)]
        pixels = saturated if len(saturated) >= max(16, len(border) // 20) else border

        quantized = (pixels // 16).astype(np.int16)
        bins, counts = np.unique(quantized, axis=0, return_counts=True)
        dominant_bin = bins[int(np.argmax(counts))]
        dominant_pixels = pixels[np.all(quantized == dominant_bin, axis=1)]
        rgb = np.median(dominant_pixels, axis=0)
        return tuple(int(round(x)) for x in rgb)  # type: ignore

    @staticmethod
    def apply_chroma_key(img: Image.Image, key_color: Union[Tuple[int, int, int], str], tolerance: float, feather: float) -> Image.Image:
        img = img.convert("RGBA")
        auto_key = key_color == "auto"
        if key_color == "auto":
            rgb = SpriteService.guess_key_color_from_corners(img)
        else:
            rgb = key_color  # type: ignore

        arr = np.asarray(img).astype(np.float32)
        color = np.array(rgb, dtype=np.float32).reshape(1, 1, 3)
        dist = np.linalg.norm(arr[:, :, :3] - color, axis=2)

        tol = float(tolerance)
        feather = max(0.0, float(feather))
        if auto_key:
            rgb_sum = np.maximum(arr[:, :, :3].sum(axis=2, keepdims=True), 1.0)
            key_sum = max(float(np.sum(rgb)), 1.0)
            chroma_dist = np.linalg.norm((arr[:, :, :3] / rgb_sum) - (color / key_sum), axis=2) * 255.0
            dist = np.minimum(dist, chroma_dist * 1.8)

        if feather <= 0:
            alpha_factor = (dist > tol).astype(np.float32)
        else:
            alpha_factor = np.clip((dist - tol) / feather, 0.0, 1.0)

        if auto_key:
            background = SpriteService._border_connected_background_mask(arr[:, :, :3])
            alpha_factor[background] = 0.0
            dark_border = SpriteService._border_connected_dark_mask(arr[:, :, :3])
            alpha_factor[dark_border] = 0.0

        # Spill suppression on the color channels
        r_k, g_k, b_k = rgb
        spill_weight = np.clip(1.0 - alpha_factor, 0.0, 1.0)
        if g_k > r_k and g_k > b_k:
            r_chan = arr[:, :, 0]
            g_chan = arr[:, :, 1]
            b_chan = arr[:, :, 2]
            spill = np.maximum(0.0, g_chan - np.maximum(r_chan, b_chan))
            arr[:, :, 1] = g_chan - spill * spill_weight
        elif b_k > r_k and b_k > g_k:
            r_chan = arr[:, :, 0]
            g_chan = arr[:, :, 1]
            b_chan = arr[:, :, 2]
            spill = np.maximum(0.0, b_chan - np.maximum(r_chan, g_chan))
            arr[:, :, 2] = b_chan - spill * spill_weight
        elif r_k > g_k and r_k > b_k:
            r_chan = arr[:, :, 0]
            g_chan = arr[:, :, 1]
            b_chan = arr[:, :, 2]
            spill = np.maximum(0.0, r_chan - np.maximum(g_chan, b_chan))
            arr[:, :, 0] = r_chan - spill * spill_weight

        arr[:, :, 3] = arr[:, :, 3] * alpha_factor
        return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), mode="RGBA")

    @staticmethod
    def _border_connected_background_mask(rgb: np.ndarray, tolerance: int = 24) -> np.ndarray:
        data = np.clip(rgb, 0, 255).astype(np.uint8)
        h, w = data.shape[:2]
        if cv2 is not None:
            work = data.copy()
            mask = np.zeros((h + 2, w + 2), dtype=np.uint8)
            flags = 4 | (255 << 8)
            diff = (tolerance, tolerance, tolerance)
            for x in range(w):
                if mask[1, x + 1] == 0:
                    cv2.floodFill(work, mask, (x, 0), (255, 0, 255), diff, diff, flags)
                if mask[h, x + 1] == 0:
                    cv2.floodFill(work, mask, (x, h - 1), (255, 0, 255), diff, diff, flags)
            for y in range(h):
                if mask[y + 1, 1] == 0:
                    cv2.floodFill(work, mask, (0, y), (255, 0, 255), diff, diff, flags)
                if mask[y + 1, w] == 0:
                    cv2.floodFill(work, mask, (w - 1, y), (255, 0, 255), diff, diff, flags)
            return mask[1:-1, 1:-1] != 0

        seen = np.zeros((h, w), dtype=bool)
        stack = []
        for x in range(w):
            stack.append((0, x))
            stack.append((h - 1, x))
        for y in range(h):
            stack.append((y, 0))
            stack.append((y, w - 1))

        while stack:
            y, x = stack.pop()
            if seen[y, x]:
                continue
            seen[y, x] = True
            color = data[y, x].astype(np.int16)
            for yy, xx in ((y - 1, x), (y + 1, x), (y, x - 1), (y, x + 1)):
                if yy < 0 or yy >= h or xx < 0 or xx >= w or seen[yy, xx]:
                    continue
                if np.linalg.norm(data[yy, xx].astype(np.int16) - color) <= tolerance:
                    stack.append((yy, xx))
        return seen

    @staticmethod
    def _border_connected_dark_mask(rgb: np.ndarray) -> np.ndarray:
        max_channel = rgb.max(axis=2)
        saturation = rgb.max(axis=2) - rgb.min(axis=2)
        dark = (max_channel <= 38) & (saturation <= 28)
        h, w = dark.shape
        seen = np.zeros((h, w), dtype=bool)
        stack = []

        for x in range(w):
            if dark[0, x]:
                stack.append((0, x))
            if dark[h - 1, x]:
                stack.append((h - 1, x))
        for y in range(h):
            if dark[y, 0]:
                stack.append((y, 0))
            if dark[y, w - 1]:
                stack.append((y, w - 1))

        while stack:
            y, x = stack.pop()
            if seen[y, x] or not dark[y, x]:
                continue
            seen[y, x] = True
            if y > 0:
                stack.append((y - 1, x))
            if y + 1 < h:
                stack.append((y + 1, x))
            if x > 0:
                stack.append((y, x - 1))
            if x + 1 < w:
                stack.append((y, x + 1))
        return seen

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
        import copy
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
                copied_item = copy.copy(frames[idx_end])
                copied_item.image = blended
                out[idx_end] = copied_item
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

    PICO8 = [
        (0, 0, 0), (29, 43, 83), (126, 37, 83), (0, 135, 81),
        (171, 82, 54), (95, 87, 79), (194, 195, 199), (255, 241, 232),
        (255, 0, 77), (255, 163, 0), (255, 236, 39), (0, 228, 54),
        (41, 173, 255), (131, 118, 156), (255, 119, 168), (255, 204, 170)
    ]
    GAMEBOY = [
        (15, 56, 15), (48, 98, 48), (139, 172, 15), (155, 188, 15)
    ]
    NES_HEX = [
        "7C7C7C", "0000FC", "0000BC", "4428BC", "940084", "A80020", "A81000", "881400",
        "503000", "007800", "006800", "005800", "004058", "000000", "000000", "000000",
        "BCBCBC", "0078F8", "0058F8", "6844FC", "D800CC", "E40058", "F83800", "E45C10",
        "AC7C00", "00B800", "00A800", "00A844", "008888", "000000", "000000", "000000",
        "F8F8F8", "3CBCFC", "6888FC", "9878FC", "F878F8", "F85898", "F87858", "FCA044",
        "FCA800", "BCBC00", "B8F818", "58D854", "58F898", "00E8D8", "787878", "000000",
        "FCFCFC", "A4E4FC", "B8B8F8", "D8B8F8", "F8B8F8", "F8A4C0", "F0D0B0", "FCE0A8",
        "FCD8A8", "D8F8A8", "C8F8B8", "B8F8D8", "00FCFC", "F8D8F8", "000000", "000000"
    ]
    NES = [tuple(int(h[i:i+2], 16) for i in (0, 2, 4)) for h in NES_HEX]

    @staticmethod
    def parse_palette(name_or_list: str) -> Optional[List[Tuple[int, int, int]]]:
        if not name_or_list:
            return None
        cleaned = name_or_list.lower().strip()
        if cleaned == "pico8":
            return SpriteService.PICO8
        if cleaned == "gameboy":
            return SpriteService.GAMEBOY
        if cleaned == "nes":
            return SpriteService.NES
        try:
            colors = []
            for item in cleaned.split(","):
                item = item.strip().lstrip("#")
                if len(item) == 6:
                    colors.append((int(item[0:2], 16), int(item[2:4], 16), int(item[4:6], 16)))
            if colors:
                return colors
        except Exception:
            pass
        return None

    @staticmethod
    def apply_palette_lock(img: Image.Image, palette: List[Tuple[int, int, int]]) -> Image.Image:
        img = img.convert("RGBA")
        arr = np.asarray(img).copy()
        alpha = arr[:, :, 3]
        visible = alpha > 0
        if not np.any(visible):
            return img
        pixels = arr[visible, :3].astype(np.float32)
        pal_arr = np.array(palette, dtype=np.float32)
        pixels_sq = np.sum(pixels**2, axis=1, keepdims=True)
        pal_sq = np.sum(pal_arr**2, axis=1, keepdims=True).T
        dot = np.dot(pixels, pal_arr.T)
        dists = pixels_sq - 2.0 * dot + pal_sq
        nearest_indices = np.argmin(dists, axis=1)
        arr[visible, :3] = pal_arr[nearest_indices].astype(np.uint8)
        return Image.fromarray(arr, mode="RGBA")
