# SpriteForge Studio v12 — Auto WAN Visual Edition

This version keeps the v9 visual UI and changes the installer so WAN model files are downloaded automatically during full installation.

## First install

Double-click:

```bat
INSTALL_EVERYTHING_WITH_WAN.bat
```

It runs:

1. SpriteForge dependency install/repair
2. Hardware profile apply
3. ComfyUI install/update
4. WAN/video custom-node install
5. ComfyUI Manager install
6. Wan 2.1 T2V 1.3B model download
7. Model report
8. Doctor report

The Wan 2.1 local model set is roughly 9.8 GB plus cache space. Interrupted downloads can be resumed by running the same installer again.

## Normal use

After install:

```bat
START_HERE.bat
```

Then use the visual UI.

## Repair

Inside the Setup tab, use **Repair WAN model download** if the model step was interrupted.
