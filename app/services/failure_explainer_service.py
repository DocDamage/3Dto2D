from __future__ import annotations
from typing import Dict, Any

__all__ = ["explain_failure", "explain_pixel_failure"]

def explain_failure(error_text: str) -> Dict[str, Any]:
    if not error_text:
        return {
            "code": "unknown",
            "title": "An unknown error occurred",
            "what_happened": "The operation failed without providing detailed error output.",
            "fix": "Check the system logs or retry the operation.",
            "action": None
        }

    text = error_text.lower()

    if "out of memory" in text or "cuda out of memory" in text or "oom" in text:
        return {
            "code": "cuda_oom",
            "title": "The GPU ran out of memory",
            "what_happened": "The selected model, resolution, or frame count required more VRAM than this system has available.",
            "fix": "Retry the generation with a smaller profile (e.g., debug), a lower resolution, or fewer frames.",
            "action": {"label": "Retry Safely", "kind": "retry_with_safer_profile"}
        }

    if "refused" in text or "unreachable" in text or "failed to establish" in text or "connection refused" in text:
        return {
            "code": "comfyui_unreachable",
            "title": "ComfyUI server is unreachable",
            "what_happened": "The local ComfyUI server is not running or is listening on a different host/port.",
            "fix": "Make sure ComfyUI is launched and running in the background before starting the job.",
            "action": {"label": "Launch ComfyUI", "kind": "launch_comfyui"}
        }

    if "permission denied" in text or "permissionerror" in text:
        return {
            "code": "permission_denied",
            "title": "File permission denied",
            "what_happened": "The application lacks sufficient permissions to write or read target files or folders.",
            "fix": "Run the application with appropriate folder access permissions or check target file lock states.",
            "action": {"label": "Check Permissions", "kind": "check_folder_access"}
        }

    if "ffmpeg" in text or "ffprobe" in text:
        return {
            "code": "ffmpeg_missing",
            "title": "FFmpeg tools not found",
            "what_happened": "The FFmpeg or ffprobe executable is missing from the system path.",
            "fix": "Install FFmpeg and ensure it is registered on your environment PATH.",
            "action": {"label": "View Setup Guide", "kind": "open_setup_docs"}
        }

    if "jsondecodeerror" in text or "expecting value" in text:
        return {
            "code": "malformed_json",
            "title": "Malformed configuration or JSON data",
            "what_happened": "The loaded JSON settings file or API payload has syntax errors and could not be parsed.",
            "fix": "Restore the default settings file or correct the malformed JSON markup.",
            "action": {"label": "Reset Config", "kind": "reset_default_config"}
        }

    if "filenotfounderror" in text or "no such file or directory" in text:
        return {
            "code": "missing_file",
            "title": "Required file or directory missing",
            "what_happened": "A file required for processing (such as a source video or model checkpoint) was not found.",
            "fix": "Confirm that all source reference assets and models exist at their expected paths.",
            "action": {"label": "Scan for Models", "kind": "scan_model_manifest"}
        }

    return {
        "code": "generic_error",
        "title": "Job processing failed",
        "what_happened": f"A processing exception occurred during job execution: {error_text[:120]}...",
        "fix": "Review the full execution logs to identify the root cause.",
        "action": None
    }

def explain_pixel_failure(error_text: str) -> Dict[str, Any]:
    """Return a plain-English Pixel Studio failure explainer."""
    if not error_text:
        return {
            "code": "pixel_unknown",
            "title": "Pixel Studio could not finish the request",
            "what_happened": "The operation stopped without returning a detailed error.",
            "fix": "Try Plan first, then retry with mock mode or a configured provider.",
            "action": {"label": "Open Plan Preview", "kind": "pixel_plan"}
        }

    text = error_text.lower()

    if "key validation failed" in text or "api key" in text or "missing local api key" in text:
        return {
            "code": "pixel_missing_provider_key",
            "title": "Provider key is missing",
            "what_happened": "The selected image provider needs a local API key before real generation can run.",
            "fix": "Open Setup or Cloud Hub, save the provider key, then retry. Use mock mode for local UI testing.",
            "action": {"label": "Open Provider Keys", "kind": "open_provider_keys"}
        }

    if "inpaint" in text and ("does not support" in text or "unsupported" in text or "capability" in text):
        return {
            "code": "pixel_inpaint_unsupported",
            "title": "This provider does not support masked image edit",
            "what_happened": "The selected provider cannot accept the mask/image edit request directly.",
            "fix": "Choose a provider with image-edit support, or generate a variation from the selected sprite and re-normalize it.",
            "action": {"label": "Use Variation Fallback", "kind": "pixel_variation_fallback"}
        }

    if "square" in text or "not square" in text:
        return {
            "code": "pixel_not_square",
            "title": "Image is not square",
            "what_happened": "Pixel Studio expected a square sprite canvas for this workflow.",
            "fix": "Normalize the image to 16x16, 32x32, 64x64, or another square resolution before continuing.",
            "action": {"label": "Run Normalize", "kind": "pixel_normalize"}
        }

    if "too many colors" in text or "color count" in text or "palette" in text:
        return {
            "code": "pixel_too_many_colors",
            "title": "Palette has too many colors",
            "what_happened": "The asset exceeds the palette target for this pixel-art workflow.",
            "fix": "Enable palette quantization or lower the max colors before exporting.",
            "action": {"label": "Quantize Palette", "kind": "pixel_quantize"}
        }

    if "no alpha" in text or "alpha" in text and "missing" in text or "transparent" in text and "background" in text:
        return {
            "code": "pixel_no_alpha",
            "title": "Transparent background is missing",
            "what_happened": "The asset appears to have an opaque background where transparency was expected.",
            "fix": "Run Normalize with alpha cleanup, or use chroma key/background removal before export.",
            "action": {"label": "Clean Alpha", "kind": "pixel_alpha_cleanup"}
        }

    if "style mismatch" in text or "style" in text and "mismatch" in text:
        return {
            "code": "pixel_style_mismatch",
            "title": "Asset does not match the selected style",
            "what_happened": "The palette, outline, or proportions drifted from the selected project style.",
            "fix": "Use a stronger style reference, extract style from a winning sprite, or generate more like the selected asset.",
            "action": {"label": "Extract Style", "kind": "pixel_extract_style"}
        }

    if "seam" in text or "tile" in text and "edge" in text:
        return {
            "code": "pixel_tile_seam",
            "title": "Tile seam check failed",
            "what_happened": "Opposite tile edges differ enough that repetition may show visible seams.",
            "fix": "Use Seam Preview, regenerate the failed tile role, or choose a tileable/edge-aware recipe.",
            "action": {"label": "Open Seam Preview", "kind": "pixel_seam_preview"}
        }

    base = explain_failure(error_text)
    base["code"] = f"pixel_{base['code']}"
    return base
