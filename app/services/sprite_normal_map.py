#!/usr/bin/env python3
"""2D Sprite Normal, Specular, and Ambient Occlusion (AO) map generator.

Generates game-engine-ready lighting maps from standard transparent 2D sprites.
Uses pure Pillow and NumPy for fast, dependency-free processing.
"""
from __future__ import annotations

import numpy as np
from PIL import Image, ImageFilter

try:
    import cv2
except Exception:
    cv2 = None


class SpriteNormalMapService:
    @staticmethod
    def compute_distance_transform_fallback(alpha_mask: np.ndarray) -> np.ndarray:
        """Fallback chamfer transform used only when OpenCV is unavailable."""
        h, w = alpha_mask.shape
        dist = np.full((h, w), 9999.0, dtype=np.float32)
        dist[alpha_mask <= 0] = 0.0

        for y in range(h):
            for x in range(w):
                val = dist[y, x]
                if y > 0:
                    val = min(val, dist[y-1, x] + 1.0)
                    if x > 0:
                        val = min(val, dist[y-1, x-1] + 1.414)
                    if x < w - 1:
                        val = min(val, dist[y-1, x+1] + 1.414)
                if x > 0:
                    val = min(val, dist[y, x-1] + 1.0)
                dist[y, x] = val

        for y in range(h - 1, -1, -1):
            for x in range(w - 1, -1, -1):
                val = dist[y, x]
                if y < h - 1:
                    val = min(val, dist[y+1, x] + 1.0)
                    if x > 0:
                        val = min(val, dist[y+1, x-1] + 1.414)
                    if x < w - 1:
                        val = min(val, dist[y+1, x+1] + 1.414)
                if x < w - 1:
                    val = min(val, dist[y, x+1] + 1.0)
                dist[y, x] = val

        return dist

    @classmethod
    def compute_distance_transform(cls, alpha_mask: np.ndarray) -> np.ndarray:
        """Return normalized interior alpha distance, strongest at the sprite center.

        OpenCV's compiled distance transform replaces the previous nested Python
        passes for the common path, which keeps normal-map generation responsive
        on larger spritesheets.
        """
        foreground = np.asarray(alpha_mask) > 0
        if not foreground.any():
            return np.zeros(foreground.shape, dtype=np.float32)

        mask = foreground.astype(np.uint8)
        if foreground.all():
            mask = np.pad(mask, 1, mode="constant", constant_values=0)

        if cv2 is not None:
            dist = cv2.distanceTransform(mask, cv2.DIST_L2, 5)
        else:
            dist = cls.compute_distance_transform_fallback(mask)

        if foreground.all():
            dist = dist[1:-1, 1:-1]

        max_dist = dist.max()
        if max_dist > 0:
            dist = np.clip(dist / max_dist, 0.0, 1.0)
        else:
            dist = np.zeros_like(dist)
        return dist.astype(np.float32, copy=False)

    @staticmethod
    def normalize_heightmap(height: np.ndarray) -> np.ndarray:
        height = height.astype(np.float32, copy=False)
        low = float(np.min(height))
        high = float(np.max(height))
        if high - low <= 1e-6:
            return np.zeros_like(height, dtype=np.float32)
        return ((height - low) / (high - low)).astype(np.float32)

    @classmethod
    def build_heightmap(cls, img: Image.Image, engine: str = "height") -> np.ndarray:
        """Build a native height/depth estimate for normal-map generation."""
        img = img.convert("RGBA")
        arr = np.asarray(img)
        rgb = arr[:, :, :3].astype(np.float32)
        alpha = arr[:, :, 3]
        gray = (0.299 * rgb[:, :, 0] + 0.587 * rgb[:, :, 1] + 0.114 * rgb[:, :, 2]) / 255.0
        vol = cls.compute_distance_transform(alpha)

        if engine == "height":
            return np.clip(0.6 * vol + 0.4 * gray, 0.0, 1.0).astype(np.float32)

        if engine not in {"native-depth", "depth"}:
            raise RuntimeError(f"Unknown normal-map engine: {engine}")

        # A native shape-from-sprite approximation: alpha volume gives broad
        # form, luminance contributes local relief, and a vertical bias keeps
        # grounded characters from reading like perfectly flat coins.
        h, w = alpha.shape
        y = np.linspace(1.0, 0.0, h, dtype=np.float32)[:, None]
        vertical_prior = np.repeat(y, w, axis=1)
        alpha_soft = (alpha.astype(np.float32) / 255.0)

        if cv2 is not None:
            smooth_gray = cv2.bilateralFilter(gray.astype(np.float32), 5, 0.12, 4.0)
            edge = cv2.Laplacian(smooth_gray, cv2.CV_32F)
        else:
            smooth_gray_img = Image.fromarray((gray * 255.0).astype(np.uint8)).filter(ImageFilter.GaussianBlur(1.0))
            smooth_gray = np.asarray(smooth_gray_img).astype(np.float32) / 255.0
            gy, gx = np.gradient(smooth_gray)
            edge = gx + gy

        relief = cls.normalize_heightmap(smooth_gray + np.clip(edge, -0.15, 0.15))
        depth = 0.68 * vol + 0.22 * relief + 0.10 * vertical_prior
        depth *= alpha_soft
        return cls.normalize_heightmap(depth)

    @classmethod
    def generate_height_map(cls, img: Image.Image, engine: str = "height") -> Image.Image:
        """Generate a grayscale RGBA height/parallax map using the sprite alpha."""
        rgba = img.convert("RGBA")
        alpha = np.asarray(rgba)[:, :, 3]
        height = cls.build_heightmap(rgba, engine=engine)
        value = np.clip(height * 255.0, 0, 255).astype(np.uint8)
        arr = np.stack([value, value, value, alpha], axis=-1)
        return Image.fromarray(arr, mode="RGBA")

    @classmethod
    def generate_maps(
        cls,
        img: Image.Image,
        engine: str = "height",
        strength: float = 2.0,
        blur_radius: float = 1.0,
        volume_weight: float = 0.6,
        bump_weight: float = 0.4,
    ) -> tuple[Image.Image, Image.Image, Image.Image]:
        """Generates normal, specular, and ambient occlusion (AO) maps.

        Args:
            img: Input RGBA image.
            strength: Strength/height scale of the normal map.
            blur_radius: Softness of the normal/specular maps.
            volume_weight: Weight of the alpha distance transform (overall 3D volume).
            bump_weight: Weight of the pixel luminance (surface details/bumps).
        """
        img = img.convert("RGBA")
        arr = np.asarray(img)
        r, g, b, alpha = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2], arr[:, :, 3]

        gray = (0.299 * r + 0.587 * g + 0.114 * b) / 255.0
        if engine == "height":
            vol = cls.compute_distance_transform(alpha)
            h_map = np.clip(volume_weight * vol + bump_weight * gray, 0.0, 1.0)
        else:
            h_map = cls.build_heightmap(img, engine=engine)

        # 4. Apply optional Pillow blur to smooth gradients
        if blur_radius > 0:
            h_img = Image.fromarray((h_map * 255.0).astype(np.uint8))
            h_img = h_img.filter(ImageFilter.GaussianBlur(blur_radius))
            h_map = np.asarray(h_img).astype(np.float32) / 255.0

        # 5. Compute gradients (central differences)
        dy, dx = np.gradient(h_map)
        dy = -dy  # Invert Y gradient to match standard OpenGL/Godot Y-up normal mapping

        # 6. Construct normal vectors
        nx = dx * strength
        ny = dy * strength
        nz = np.ones_like(h_map)

        # Normalize normal vectors
        norm = np.sqrt(nx**2 + ny**2 + nz**2)
        nx /= norm
        ny /= norm
        nz /= norm

        # Map normals to RGB colorspace
        r_out = ((nx * 0.5 + 0.5) * 255.0).astype(np.uint8)
        g_out = ((ny * 0.5 + 0.5) * 255.0).astype(np.uint8)
        b_out = ((nz * 0.5 + 0.5) * 255.0).astype(np.uint8)

        # Normal image retains original alpha channel
        normal_arr = np.stack([r_out, g_out, b_out, alpha], axis=-1)
        normal_img = Image.fromarray(normal_arr, mode="RGBA")

        # 7. Generate Specular map
        # Higher specular on sharp edges and bright luminance spots
        edge_strength = np.sqrt(dx**2 + dy**2)
        edge_strength = np.clip(edge_strength / (edge_strength.max() or 1.0), 0.0, 1.0)
        spec = 0.5 * gray + 0.5 * edge_strength
        spec_val = (spec * 255.0).astype(np.uint8)
        specular_arr = np.stack([spec_val, spec_val, spec_val, alpha], axis=-1)
        specular_img = Image.fromarray(specular_arr, mode="RGBA")

        # 8. Generate Ambient Occlusion map
        # Darker values in crevices/edges
        ao_val = ((1.0 - edge_strength * 0.7) * 255.0).astype(np.uint8)
        ao_arr = np.stack([ao_val, ao_val, ao_val, alpha], axis=-1)
        ao_img = Image.fromarray(ao_arr, mode="RGBA")

        return normal_img, specular_img, ao_img
