# SpriteForge Studio v8 - Userproof Edition

Use this version like a normal app:

1. Extract the ZIP.
2. For first install, double-click `INSTALL_EVERYTHING_WITH_WAN.bat`. After it finishes, double-click `START_HERE.bat`.
3. The first-run wizard opens.
4. Click **Run Preflight Check**.
5. Click **Make No-GPU Demo Sprite** first.
6. Then install ComfyUI/WAN and download models.
7. Open Easy Mode and make a sprite.

Useful launchers:

```text
START_HERE.bat                 Main app / first-run wizard
RUN_DEMO_NO_GPU.bat            Verifies sprite conversion without ComfyUI or GPU
COLLECT_SUPPORT_BUNDLE.bat     Collects diagnostics into a zip
OPEN_OUTPUTS.bat               Opens finished sprites
OPEN_DOCS.bat                  Opens guides
RESET_TO_FIRST_RUN_WIZARD.bat  Shows the setup wizard again
```

The no-GPU demo should create:

```text
app/output/demo_sprite_no_gpu/sheet.png
app/output/demo_sprite_no_gpu/sheet.json
app/output/demo_sprite_no_gpu/preview.gif
app/output/demo_sprite_no_gpu/report.html
```

If the demo works but WAN does not, the problem is not the sprite converter. It is ComfyUI, models, GPU memory, driver setup, or workflow setup.

A prebuilt example is included at `app/examples/prebuilt_demo_sprite/` so users can see what a successful output looks like before running anything.


## v10 Auto WAN install

The full installer now auto-downloads the Wan 2.1 T2V 1.3B model set during installation. Rerun `INSTALL_EVERYTHING_WITH_WAN.bat` to resume interrupted downloads.
