# First Run Checklist

1. Extract the ZIP. Do not run it from inside the compressed ZIP window.
2. Double-click `START_HERE.bat`.
3. In the wizard, click **Run Preflight Check**.
4. Click **Make No-GPU Demo Sprite**.
5. If the demo works, click **Install ComfyUI + WAN Nodes**.
6. Click **Download WAN 2.1 1.3B Models**.
7. Click **Validate / Doctor**.
8. Click **Open Easy Mode**.
9. In Easy Mode, use profile `debug` for the first WAN test.
10. After that works, use `rtx3060_12gb`.

Safe first prompt:

```text
single full body original game hero, idle cycle, front view, locked camera, centered, plain bright green background, clean silhouette, game sprite animation
```

Avoid these until the pipeline works:

```text
cinematic camera, camera movement, zoom, close-up, complex background, dramatic lighting, motion blur
```
