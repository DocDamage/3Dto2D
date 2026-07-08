# SpriteForge One-Page Cheat Sheet

## Start

Double-click:

```text
START_HERE.bat
```

## First setup

Click:

```text
Launchpad -> Run No-GPU Demo
Setup -> Start First Run Diagnostic
Setup -> Install Everything: Safe Wan 2.1
Setup -> Launch ComfyUI
```

## First safe test

```text
Profile: debug
Action: idle
Direction: front
Character: single full body original game hero, simple outfit, boots, clean silhouette
```

## Real local test for RTX 3060 12GB

```text
Profile: rtx3060_12gb
Action: walk
Direction: right
Character: single full body original game hero, simple outfit, boots, clean silhouette
```

## Sprite Lab must-knows

```text
Use AI Auto Fix in Final prompt preview
Choose multiple actions when building a pack
Choose All directions for full directional coverage
Keep Start ComfyUI if needed enabled for local WAN generation
```

## LPC builder

```text
LPC -> Load Pickers
Pick body/hair/clothes/weapons/accessories
Compose
Zoom the center character preview with mouse wheel or slider
Build Batch -> Run QA -> Prepare LoRA
```

## API keys and free providers

```text
Setup or Cloud Hub -> Provider keys
Save local keys for Hugging Face, OpenAI, Google/Gemini, Anthropic, Kimi, GLM, DeepSeek, or Grok/xAI
Free/community availability depends on each provider account and model
```

## Pixel Studio

```text
Pixel Studio -> choose asset type -> prompt/reference/style -> Generate
Provider panel -> confirm generate/edit/inpaint/prompt-help support before running
Normalize for fixed size, palette, alpha, and cleanup
Directions for 1/4/8-direction sheets
Tileset for tile roles and seam QA
Repair tile seams -> version selected tile and refresh seam score
Paint & Edit -> AI Mask -> set opacity/variants -> Run AI Edit
Hold Before to compare against the saved pre-inpaint image
Animate / Transfer / Rig for motion sheets
Use as style reference -> reuse palette/style memory
Visual QA report -> review palette, alpha, sharpness, seam, style, and edit trace gates
Search/filter recipe cards -> reuse built-in or saved recipes
Save/import/export recipe JSON -> reuse or share current settings
Gallery History -> search/filter saved Pixel Studio assets and reload them into the inspector
Cohesive Pack Builder -> Generate Complete Pack -> Export Complete Pack ZIP
```

## Pixel Studio first workflows

```text
First asset: Characters -> prompt -> Plan -> Generate -> Visual QA report
First tileset: Tilesets -> choose tileset type -> Generate -> Seam Preview
First animation: select asset -> Animation Settings -> Animate Selected Sprite
First pack: Cohesive Pack Builder -> recipe card -> Generate Complete Pack -> Export Complete Pack ZIP
```

## Best output folder files

```text
sheet.png
sheet.json
preview.gif
preview.png
preview.webp
report.html
```

## Use green background

For WAN videos, ask for:

```text
plain bright green background, locked camera, centered, no zoom
```

## When output is bad

Use:

```text
Quality Lab -> Run QA
Quality Lab -> Auto-Fix / one-click repair
Release -> Build package when QA passes
```

## Before sharing a build

Use a freshly built Release ZIP. Do not share local uploads, logs, `app/vendor/`, model weights, or old workspace archives.
