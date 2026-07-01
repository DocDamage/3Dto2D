# SpriteForge Studio v12 - WAN Model Tiers

This guide keeps its historical filename for compatibility. The model-tier system remains current in v12 and lets users choose between safe local setup, advanced local setup, and remote/cloud generation.

## Tiers

| Tier | Local? | Use case |
|---|---:|---|
| Safe / Wan 2.1 1.3B | Yes | First install, RTX 3060 12GB default, fastest path to a working sprite workflow. |
| Better / Wan 2.2 TI2V 5B | Yes | Advanced local mode with better motion/prompt adherence, after the safe setup works. |
| Cloud / Wan 2.2 14B | Not local by default | Remote ComfyUI/cloud GPU only. Not auto-downloaded. |

## First-run recommendation

Run `START_HERE.bat`, then in the Setup tab click:

1. `Install Everything: Safe Wan 2.1`
2. `Run Doctor`
3. `Launch ComfyUI`
4. Make a debug sprite
5. Then click `Add Better Mode: Wan 2.2 5B` if the safe path works

## CLI examples

Safe install:

```bat
python spriteforge_unified.py install-all --model-tier safe
```

Advanced install:

```bat
python spriteforge_unified.py install-all --model-tier advanced
```

Download only Wan 2.2 5B:

```bat
python spriteforge_unified.py download-model-tier --tier wan22_only
```

Generate with safe model:

```bat
python spriteforge_unified.py generate-sprite --start-comfy --tier wan21_safe --profile auto --action walk --direction right --character "single full body original game hero"
```

Generate with Wan 2.2 5B:

```bat
python spriteforge_unified.py generate-sprite --start-comfy --tier wan22_5b --profile auto --action walk --direction right --character "single full body original game hero"
```

## Cloud tier

The cloud tier is intentionally not auto-downloaded. Use it with a remote ComfyUI server and exported API workflows.

## Distribution note

Model checkpoints are not bundled with SpriteForge source or release ZIPs. Setup downloads or validates them locally under the configured ComfyUI model folders.
