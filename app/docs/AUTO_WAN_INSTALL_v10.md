# Auto WAN Install v11

The full installer now downloads the required local WAN files automatically.

## Model set

Default manifest:

```text
model_manifests/wan21_t2v_1_3b_native.json
```

Target ComfyUI folders:

```text
ComfyUI/models/text_encoders/umt5_xxl_fp8_e4m3fn_scaled.safetensors
ComfyUI/models/vae/wan_2.1_vae.safetensors
ComfyUI/models/diffusion_models/wan2.1_t2v_1.3B_fp16.safetensors
```

## Commands

Full install:

```bat
python spriteforge_unified.py install-all
```

Resume only the model download:

```bat
python spriteforge_unified.py download-wan-native
```

Check installed model files:

```bat
python spriteforge_unified.py model-report --json
```

## Notes

The installer skips model files already present unless `--force-models` is used with `install-all`, or `--force` is used with `download-wan-native`.
