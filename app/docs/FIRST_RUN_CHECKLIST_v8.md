# SpriteForge Studio v12 First Run Checklist

This guide keeps its historical filename for compatibility, but the workflow below reflects the v12 browser dashboard.

1. Extract the ZIP. Do not run it from inside the compressed ZIP window.
2. Double-click `START_HERE.bat`.
3. Open **Home** and choose **Try a demo**. The demo should open in Play
   Workbench without a GPU or model download.
4. Choose **Start creating** and walk through the character wizard to see the
   default name, description, first moves, and ready check.
5. Open **Settings** and run **Start First Run Diagnostic** when you are ready
   for AI generation.
6. Run **Install Everything: Safe Wan 2.1** if the setup summary says art tools
   are missing.
7. Let SpriteForge start ComfyUI when you create, or use **Launch ComfyUI** in
   Settings if you prefer to start it first.
8. Use the `debug` profile and a single short action for the first WAN test.
9. After that works, use a recommended local profile such as `rtx3060_12gb`.

Safe first prompt:

```text
single full body original game hero, idle cycle, front view, locked camera, centered, plain bright green background, clean silhouette, game sprite animation
```

Avoid these until the pipeline works:

```text
cinematic camera, camera movement, zoom, close-up, complex background, dramatic lighting, motion blur
```

When you are ready to share outputs, build a fresh package from the **Release** tab. Release and project bundles should not contain `app/vendor/`, model weights, logs, uploaded videos, or generated release folders.

Optional follow-up checks:

1. In **Create**, use **Customize** to reach advanced prompt controls and **AI
   Auto Fix** before your first real generation.
2. Try selecting multiple actions and **All** directions only after the single debug sprite works.
3. In **LPC**, click **Load Pickers**, compose a character, and confirm the center preview zooms with the mouse wheel or slider.
4. In **Setup** or **Cloud Hub**, add only the API keys you want stored locally for cloud image/provider experiments.
