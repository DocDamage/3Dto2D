# ComfyUI / WAN sprite notes

Recommended pattern:

1. Generate or stylize the motion in ComfyUI/WAN.
2. Keep the camera locked.
3. Keep the character full-body and centered.
4. Use a flat chroma background or transparent output if your workflow supports it.
5. Convert the resulting video with SpriteForge.

Recommended prompt:

```text
single full body character, side view, game sprite animation, walking cycle, locked camera, fixed orthographic-like side angle, centered character, consistent outfit, clean silhouette, plain bright green background, no camera movement, no zoom, no cuts, no motion blur
```

Negative prompt ideas:

```text
camera movement, zoom, pan, closeup, cut, multiple characters, changing outfit, changing hairstyle, complex background, shadow on background, motion blur, cropped body, out of frame
```

For ComfyUI video I/O, ComfyUI-VideoHelperSuite is commonly used for loading videos, image sequences, and combining image batches into videos. Use its frame-rate controls to keep your output at the same FPS you intend for the sprite.

For RTX 3060 12GB, start with smaller WAN models or optimized/quantized workflows before trying heavier 14B-class models. Generate short clips first.
