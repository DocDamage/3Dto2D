# WAN / ComfyUI Integration Notes

## Native ComfyUI route

The included one-click path targets native ComfyUI Wan 2.1 nodes and the official ComfyUI-repackaged Wan model files:

```text
text_encoders/umt5_xxl_fp8_e4m3fn_scaled.safetensors
vae/wan_2.1_vae.safetensors
diffusion_models/wan2.1_t2v_1.3B_fp16.safetensors
```

This is the best default for an RTX 3060 12GB because it avoids the 14B model class and keeps output at 480p-ish resolution.

## Kijai WanVideoWrapper route

The installer also installs Kijai's wrapper nodes. Use these when you want:

- Kijai FP8/GGUF models
- newer experimental WAN variants
- WanAnimate / related workflows
- wrapper-specific workflows from the community

The default SpriteForge watcher still works with wrapper outputs because it simply watches ComfyUI's output folder for videos.

## VideoHelperSuite route

VideoHelperSuite is useful for loading videos, loading image sequences, combining images into video, controlling frame rate, and previewing video inside ComfyUI.

## Model storage

ComfyUI models are expected in:

```text
vendor/ComfyUI/models/diffusion_models
vendor/ComfyUI/models/text_encoders
vendor/ComfyUI/models/vae
vendor/ComfyUI/models/clip_vision
```

## Sprite-oriented WAN settings

Use:

```text
width: 832
height: 480
frames: 33
fps: 12
steps: 24-30
cfg: 6
shift: 8
sampler: uni_pc
scheduler: simple
```

Use plain green or blue background for chroma keying.
