# SpriteForge application folder

This folder contains the local application, browser UI, example character, and
runtime documentation used by SpriteForge Studio.

## Start the application

From the package root, use:

```text
START_HERE.bat
```

The normal path in the browser is:

1. **Home → Start creating** for a guided character workflow.
2. **Try a demo** to open the bundled demo character in Play Workbench without
   configuring AI generation.
3. **Review** to check motion and repair a creation.
4. **Export** to make a clean game-ready package.

Use **Settings** for first-run checks, optional ComfyUI/WAN generation, provider
keys, controller navigation, and the local Forge companion.

## Important folders

```text
web/                         browser UI assets and components
docs/                        user and setup documentation
examples/prebuilt_demo_sprite/ bundled no-setup demo character
config/                      local configuration templates
output/                      generated local work (not source-controlled)
input/                       local source media and optional payloads
```

## Current guides

- `docs/END_USER_GUIDE.md`
- `docs/FIRST_RUN_CHECKLIST_v8.md`
- `docs/ONE_PAGE_CHEAT_SHEET.md`
- `docs/TROUBLESHOOTING_v8.md`
- `docs/LOCAL_FORGE_GUIDE.md`
- `docs/api.md`

See the repository [README](../README.md) for the product overview,
documentation map, licensing, and development checks.
