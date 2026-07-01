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

## Best output folder files

```text
sheet.png
sheet.json
preview.gif
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
