# SpriteForge Studio v12 First Run Checklist

This guide keeps its historical filename for compatibility, but the workflow below reflects the v12 browser dashboard.

1. Extract the ZIP. Do not run it from inside the compressed ZIP window.
2. Double-click `START_HERE.bat`.
3. Open **Launchpad**.
4. Run **No-GPU Demo**.
5. Open **Setup** and run **Start First Run Diagnostic**.
6. Run **Install Everything: Safe Wan 2.1**.
7. Click **Launch ComfyUI**.
8. Open **Generate Sprite**.
9. Use profile `debug` for the first WAN test.
10. After that works, use the recommended local profile such as `rtx3060_12gb`.

Safe first prompt:

```text
single full body original game hero, idle cycle, front view, locked camera, centered, plain bright green background, clean silhouette, game sprite animation
```

Avoid these until the pipeline works:

```text
cinematic camera, camera movement, zoom, close-up, complex background, dramatic lighting, motion blur
```

When you are ready to share outputs, build a fresh package from the **Release** tab. Release and project bundles should not contain `app/vendor/`, model weights, logs, uploaded videos, or generated release folders.
