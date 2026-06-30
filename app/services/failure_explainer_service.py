from __future__ import annotations
from typing import Dict, Any, Optional

__all__ = ["explain_failure"]

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
