# Third-Party Notices & Distribution Details

SpriteForge Studio is distributed under the MIT License. However, to function, it downloads, installs, and connects to external open-source payloads locally. These payloads are **not** bundled inside the release package and must be downloaded onto the target system during setup.

## External Local Payload Details

The first-run setup wizard and setup dashboard automate the local installation of these payloads. They reside inside your local environment under their respective license agreements:

1. **ComfyUI**
   - **Source:** [comfyanonymous/ComfyUI](https://github.com/comfyanonymous/ComfyUI)
   - **License:** GPL-3.0 License
   - **Role:** Web-based node user interface and generation backend for Stable Diffusion and Wan.

2. **Wan 2.1 Model Checkpoints**
   - **Source:** [Wangshuai / Wan-AI](https://github.com/Wan-AI/Wan2.1)
   - **License:** Wan 2.1 License Agreement (Open-weights, free commercial/research use with attribution)
   - **Role:** Model weights utilized for generating high-quality character animation videos.

3. **FFmpeg**
   - **License:** LGPL-2.1 / GPL-3.0
   - **Role:** Handles video frames extraction and compiling animations.

## Python Runtime Dependencies

The local virtual environment runs standard Python packages which are documented inside [requirements-lock.txt](requirements-lock.txt). Key packages include:

- **Pillow (PIL):** HPND License (imaging, frame processing)
- **NumPy:** BSD-3-Clause License (numerical arrays)
- **OpenCV (opencv-python):** Apache-2.0 License (image alignment and processing)
- **Flask:** BSD-3-Clause License (local host web UI server)
- **ImageIO:** BSD-2-Clause License (GIF exporting)
- **HuggingFace Hub:** Apache-2.0 License (automated model downloader)

---

*Note: No proprietary, commercially restricted, or unlicensed models/nodes are packaged with this software.*
