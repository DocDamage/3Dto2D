#!/usr/bin/env python3
"""Prompt Linter Service: Scores prompts for sprite-generation quality heuristics."""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

# Known good/bad terms for sprite generation
NEGATIVE_CAMERA_TERMS = {
    "camera movement", "zoom", "pan", "tilt", "dolly", "tracking shot",
    "dynamic camera", "moving camera", "camera shake", "crane shot",
    "drone shot", "steadicam", "handheld", "spin", "rotate around",
    "camera orbit", "camera fly", "camera pan", "camera zoom"
}

POSITIVE_CAMERA_TERMS = {
    "locked camera", "fixed camera", "static camera", "locked-off",
    "stationary camera", "still camera", "fixed viewpoint"
}

CHROMA_KEY_TERMS = {
    "green screen", "greenscreen", "green background", "chroma key",
    "chromakey", "blue screen", "bluescreen", "solid green",
    "bright green background", "plain green"
}

STYLE_QUALITY_TERMS = {
    "game sprite", "pixel art", "2d sprite", "sprite sheet",
    "character sprite", "game asset", "animation frame",
    "spritesheet", "pixel-art", "cel shaded", "cel-shaded",
    "clean silhouette", "readable silhouette", "strong silhouette"
}

STYLE_NEGATIVE_TERMS = {
    "3d render", "photorealistic", "realistic photo", "cinematic",
    "depth of field", "motion blur", "lens flare", "bokeh",
    "film grain", "vignette", "chromatic aberration"
}

PROMPT_MAX_LENGTH = 500
PROMPT_WARN_LENGTH = 350


def lint_prompt(prompt: str, negative: Optional[str] = None, 
                action: Optional[str] = None) -> Dict[str, Any]:
    """Score a prompt and return warnings + suggestions.
    
    Returns a dict with:
        score: 0-100 overall quality score
        warnings: list of warning strings
        suggestions: list of improvement suggestions
        checks: detailed check results
    """
    warnings: List[str] = []
    suggestions: List[str] = []
    checks: Dict[str, Any] = {}
    score = 100
    
    prompt_lower = prompt.lower().strip()
    negative_lower = (negative or "").lower().strip()
    combined = prompt_lower + " " + negative_lower
    
    # 1. Check for contradictory camera terms
    has_positive_camera = any(term in prompt_lower for term in POSITIVE_CAMERA_TERMS)
    has_negative_camera = any(term in prompt_lower for term in NEGATIVE_CAMERA_TERMS)
    
    if has_negative_camera:
        found = [t for t in NEGATIVE_CAMERA_TERMS if t in prompt_lower]
        warnings.append(f"Avoid camera-movement terms: {', '.join(found)}")
        suggestions.append("Use 'locked camera' or 'fixed camera' for sprite generation")
        score -= 15
    
    if not has_positive_camera and not has_negative_camera:
        suggestions.append("Consider adding 'locked camera' for consistent sprite frames")
        score -= 5
    
    checks["camera"] = {
        "ok": not has_negative_camera and (has_positive_camera or not has_negative_camera),
        "has_positive_camera": has_positive_camera,
        "has_negative_camera": has_negative_camera
    }
    
    # 2. Check for chroma key presence
    has_chroma = any(term in prompt_lower for term in CHROMA_KEY_TERMS)
    if not has_chroma:
        suggestions.append("Add 'plain bright green chroma key background' for clean extraction")
        score -= 10
    checks["chroma_key"] = {
        "ok": has_chroma,
        "has_chroma": has_chroma
    }
    
    # 3. Check prompt length
    prompt_len = len(prompt.strip())
    if prompt_len > PROMPT_MAX_LENGTH:
        warnings.append(f"Prompt is very long ({prompt_len} chars). WAN may ignore tokens beyond ~{PROMPT_MAX_LENGTH}")
        score -= 10
    elif prompt_len > PROMPT_WARN_LENGTH:
        warnings.append(f"Prompt is long ({prompt_len} chars). Consider trimming for better adherence")
        score -= 3
    
    checks["length"] = {
        "ok": prompt_len <= PROMPT_WARN_LENGTH,
        "length": prompt_len,
        "max_recommended": PROMPT_MAX_LENGTH
    }
    
    # 4. Check for style quality markers
    has_style_quality = any(term in prompt_lower for term in STYLE_QUALITY_TERMS)
    has_style_negative = any(term in prompt_lower for term in STYLE_NEGATIVE_TERMS)
    
    if has_style_negative:
        found_neg = [t for t in STYLE_NEGATIVE_TERMS if t in prompt_lower]
        warnings.append(f"Terms better suited for negative prompt found in positive: {', '.join(found_neg)}")
        suggestions.append("Move cinematic/photorealistic terms to negative prompt")
        score -= 12
    
    if not has_style_quality:
        suggestions.append("Include style descriptors like 'game sprite', 'pixel art', or 'cel shaded'")
        score -= 5
    
    checks["style"] = {
        "ok": has_style_quality and not has_style_negative,
        "has_quality_terms": has_style_quality,
        "has_negative_terms": has_style_negative
    }
    
    # 5. Check for action/animation descriptions
    if action:
        action_terms = _action_hints(action)
        missing = [t for t in action_terms if t not in prompt_lower]
        if missing:
            suggestions.append(f"For '{action}' action, consider including: {', '.join(missing)}")
            score -= 3
    
    # 6. Check for contradictory/conflicting terms
    contradictions = _find_contradictions(prompt_lower)
    if contradictions:
        for contra in contradictions:
            warnings.append(f"Contradictory terms: {contra}")
        score -= 8
    checks["contradictions"] = {
        "ok": len(contradictions) == 0,
        "found": contradictions
    }
    
    # 7. Check negative prompt quality
    negative_issues = _lint_negative(negative_lower)
    warnings.extend(negative_issues)
    if negative_issues:
        score -= len(negative_issues) * 2
    checks["negative"] = {
        "ok": len(negative_issues) == 0,
        "issues": negative_issues
    }
    
    # 8. Check for structural issues
    if prompt.strip().endswith(","):
        warnings.append("Prompt ends with a comma - this may cause parsing issues")
        score -= 2
    
    if prompt.strip().startswith(","):
        warnings.append("Prompt starts with a comma")
        score -= 2
    
    comma_count = prompt.count(",")
    if comma_count > 15:
        warnings.append(f"Prompt has {comma_count} comma-separated phrases. Consider grouping related concepts")
        score -= 3
    
    checks["structure"] = {
        "ok": not (prompt.strip().endswith(",") or prompt.strip().startswith(",")),
        "comma_count": comma_count
    }
    
    # Clamp score
    score = max(0, min(100, score))
    
    # Build overall summary
    severity = "good"
    if score < 40:
        severity = "poor"
    elif score < 65:
        severity = "fair"
    elif score < 80:
        severity = "good"
    else:
        severity = "excellent"
    
    return {
        "score": score,
        "severity": severity,
        "warnings": warnings,
        "suggestions": suggestions,
        "checks": checks,
        "prompt_length": prompt_len,
        "action": action
    }


def _action_hints(action: str) -> List[str]:
    """Return terms that should appear in a prompt for the given action."""
    hints_map = {
        "idle": ["idle", "standing", "breathing", "loop", "ready stance"],
        "walk": ["walking", "walk cycle", "stride", "stepping", "loop"],
        "run": ["running", "sprinting", "dashing", "run cycle", "loop"],
        "jump": ["jumping", "leap", "airborne", "ascending", "descending"],
        "attack_light": ["slashing", "swinging", "striking", "attack", "weapon swing"],
        "attack_heavy": ["powerful strike", "heavy attack", "overhead swing", "slam"],
        "hurt": ["taking damage", "flinching", "recoiling", "stagger", "hit reaction"],
        "death": ["dying", "falling", "defeated", "collapse", "fainting"],
        "cast": ["casting spell", "magic", "summoning", "spellcasting", "conjuring"],
        "shoot": ["shooting", "firing", "projectile", "bow", "crossbow", "gun"],
        "block": ["blocking", "defending", "shield", "guard", "parry"],
    }
    return hints_map.get(action, [f"{action} animation"])


def _find_contradictions(prompt_lower: str) -> List[str]:
    """Find contradictory term pairs in the prompt."""
    contradictions = []
    pairs = [
        ({"2d", "two dimensional"}, {"3d", "three dimensional", "3-d"}),
        ({"pixel art", "pixel-art"}, {"realistic", "photorealistic", "high detail"}),
        ({"static", "still", "stationary"}, {"animated", "moving", "dynamic"}),
        ({"top-down", "top down"}, {"side view", "side-view", "platformer"}),
        ({"cartoon", "stylized"}, {"realistic", "photoreal"}),
        ({"minimal", "simple"}, {"detailed", "intricate", "complex"}),
    ]
    for set_a, set_b in pairs:
        found_a = any(t in prompt_lower for t in set_a)
        found_b = any(t in prompt_lower for t in set_b)
        if found_a and found_b:
            a_term = next(t for t in set_a if t in prompt_lower)
            b_term = next(t for t in set_b if t in prompt_lower)
            contradictions.append(f"'{a_term}' vs '{b_term}'")
    return contradictions


def _lint_negative(negative_lower: str) -> List[str]:
    """Check negative prompt for issues."""
    issues = []
    good_negative_terms = {
        "camera movement", "zoom", "pan", "blur", "distorted",
        "bad anatomy", "extra limbs", "mutation", "deformed",
        "text", "watermark", "signature", "ui", "logo"
    }
    has_camera_neg = any(t in negative_lower for t in ["camera movement", "zoom", "pan", "camera"])
    if not has_camera_neg and negative_lower:
        issues.append("Consider adding camera movement terms to negative prompt")
    
    if not negative_lower or len(negative_lower.strip()) < 10:
        issues.append("Negative prompt is missing or very short")
    
    # Check for terms that should NOT be in negative
    bad_in_negative = {"locked camera", "fixed camera", "static camera", "chroma key", "green screen"}
    found_bad = [t for t in bad_in_negative if t in negative_lower]
    if found_bad:
        issues.append(f"These belong in the positive prompt, not negative: {', '.join(found_bad)}")
    
    return issues


def quick_score(prompt: str) -> Dict[str, Any]:
    """Fast check returning just the score and top issues."""
    result = lint_prompt(prompt)
    return {
        "score": result["score"],
        "severity": result["severity"],
        "top_warnings": result["warnings"][:3],
        "top_suggestions": result["suggestions"][:3]
    }


def lint_from_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Lint a full generation payload (from web UI or CLI)."""
    prompt = payload.get("prompt", "") or payload.get("positive", "") or ""
    negative = payload.get("negative", "") or payload.get("negative_prompt", "") or ""
    action = payload.get("sprite_action") or payload.get("action") or ""
    return lint_prompt(prompt, negative=negative, action=action)