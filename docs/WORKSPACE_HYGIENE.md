# Workspace and Runtime Storage

Keep source code, generated assets, and large AI runtimes in separate locations. This is especially important when the source tree is synchronized by OneDrive.

## Inspect storage safely

The report command is read-only:

```powershell
python app/tools/workspace_hygiene.py
```

It reports the Git object store, local ComfyUI/vendor payload, inputs, outputs, and release archive sizes. It never deletes or moves files.

## Move ComfyUI and models outside the repository

Set these before launching SpriteForge, or place them in a user-level environment configuration:

```powershell
$env:SPRITEFORGE_COMFYUI_DIR = "D:\AI\ComfyUI"
$env:SPRITEFORGE_COMFYUI_OUTPUT = "D:\AI\ComfyUI\output"
```

Environment values override the ComfyUI paths in `app/config/spriteforge_config.json` without writing machine-specific paths into Git.

Move existing runtime data only while SpriteForge and ComfyUI are stopped. Verify the new location before removing the old copy.

## Git cleanup

Large temporary packs or unreachable objects can make `.git` much larger than reachable project history. Before cleanup:

1. Back up the repository.
2. Commit or preserve all wanted work.
3. Inspect `git fsck --unreachable` and reflogs.
4. Run `git gc` only after confirming unreachable objects are disposable.

Do not automate pruning on startup; recovery data may still be valuable.
