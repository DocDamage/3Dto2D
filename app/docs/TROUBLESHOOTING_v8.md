# SpriteForge Studio v12 Troubleshooting

This guide keeps its historical filename for compatibility, but the steps below reflect the v12 browser dashboard and current CLI tools.

## Start with the no-GPU demo

Run:

```bat
RUN_DEMO_NO_GPU.bat
```

If this creates `output/demo_sprite_no_gpu/sheet.png`, `sheet.json`, `preview.gif`, and `report.html`, the sprite packing/conversion side works. Any remaining issue is probably ComfyUI, WAN models, GPU drivers, or workflow configuration.

## Python not found

Run:

```bat
app\Install_Python_And_Git.bat
```

Then close the terminal and run `START_HERE.bat` again.

## Git not found

ComfyUI and custom-node installation use Git. Run:

```bat
app\Install_Python_And_Git.bat
```

## Model download fails or stops

Run the download again. The Hugging Face downloader is resumable in normal cases.

```bat
app\START_SPRITEFORGE.bat --wizard
```

Then open **Setup** and run **Install Everything: Safe Wan 2.1**. The downloader is resumable in normal cases.

## ComfyUI starts but SpriteForge says it cannot connect

Check that ComfyUI is listening on:

```text
http://127.0.0.1:8188
```

If another program is using port 8188, close it or change the port in `app/config/spriteforge_config.json`.

## WAN runs out of memory on RTX 3060 12GB

Use the debug profile first. Then move up slowly:

```text
debug → sprite_fast → rtx3060_12gb → quality_local
```

For a first real test, use fewer frames and fewer steps. Avoid I2V 14B locally unless you are prepared to use heavy offload or cloud GPU.

When a web-launched generation hits CUDA OOM, SpriteForge now retries through a progressive VRAM fallback chain: safer fp8/tier hints, forced batch size 1, reduced output resolutions, then a final CPU/offload hint. The Logs view records each retry attempt and the adjusted command.

## Logging level and JSON logs

Web runs configure named `spriteforge.*` loggers from `app/config/spriteforge_config.json`. Set `logging.level` to `DEBUG`, `INFO`, `WARNING`, or `ERROR`; set `logging.json` to `true` when you want structured JSON records on stderr for log collectors.

## Video converts but background is visible

Use a flat green/blue background in the WAN prompt and convert with chroma key:

```text
plain bright green background, clean silhouette, no shadows on background
```

Then use:

```text
key color = auto
key tolerance = 45 to 65
```

## Sprite jitters or feet slide

Use the one-click repair actions in **Quality Lab**, or use:

```bat
python spriteforge_unified.py autofix-sprite --input output\YOUR_SPRITE --output output\YOUR_SPRITE_fixed --stabilize-anchor --drop-loop-duplicate --deflicker
```

## Pixel Studio provider or AI edit is unavailable

Open **Pixel Studio** and check the provider capability panel before generating. It reports whether the selected provider can generate, edit, inpaint, or help with prompts.

If it says a key is missing, open **Setup** or **Cloud Hub** and save the provider key locally. If it says the provider is capable but not wired for that Pixel Studio workflow, use the local fallback or local ComfyUI until that adapter is enabled.

## Pixel Studio inpaint output is not what you expected

Use **Paint & Edit Pixel**, choose **AI Mask**, then:

```text
Increase mask opacity to inspect the painted area
Keep variants low for local fallback tests
Hold Before to compare against the pre-inpaint image
Run Visual QA report after accepting the result
```

The asset sidecar records the original image, mask, result, prompt, provider, fallback, and version entry under `inpaint_history`.

## Pixel Studio Visual QA warns about an asset

Use the inspector's **Visual QA report**. Common fixes:

```text
Palette count warning -> Cleanup selected asset or reduce palette size
Alpha/background warning -> Cleanup selected asset
Sharpness warning -> Re-normalize with nearest-neighbor cleanup
Tile seam warning -> enable Seam Preview and regenerate/cleanup tile edges
Style match warning -> Make match project style or choose a closer style profile
```

## Pixel Studio recipes or packs do not show up

Use the Cohesive Pack Builder search/filter controls. Set source to **All sources** and type to **All types** if a recipe disappears. Imported recipe JSON must use schema `spriteforge.pixel_recipe.v1` and at least one supported item type.

## Need help debugging

Run:

```bat
COLLECT_SUPPORT_BUNDLE.bat
```

It creates a zip in:

```text
app/output/support_bundles/
```

That bundle includes logs, diagnostics, model reports, and hardware info. It does not include model weights or large videos.

## Release ZIP is unexpectedly huge

Do not ship workspace-local archives that were created before cleanup. A clean release package should exclude:

```text
app/vendor/
app/input/uploaded_videos/
app/output/
app/releases/
app/logs/
*.safetensors
```

Delete the stale archive and rebuild from the **Release** tab after confirming the workspace is clean.
