from __future__ import annotations

from typing import Any, Dict

from spriteforge_prompts import ACTION_TEMPLATES, DIRECTIONS, build_prompt


BODY_STYLES = {
    "heroic": "heroic adult proportions, confident stance, strong readable silhouette",
    "compact": "compact game character proportions, readable small-scale details, sturdy stance",
    "slender": "slender agile proportions, elegant pose language, clear limbs",
    "heavy": "broad sturdy proportions, grounded weight, powerful silhouette",
}

ART_STYLES = {
    "pixel": "pixel-art inspired 2D game sprite, crisp edges, limited palette, readable clusters",
    "cel": "polished cel-shaded 2D game sprite, clean linework, crisp highlights",
    "painted": "painterly 2D game sprite, controlled brush texture, readable game silhouette",
    "retro": "retro console sprite style, restrained colors, sharp game-ready readability",
}

CAMERA_STYLES = {
    "side": "side-view locked camera, character facing right or left, feet visible",
    "topdown": "top-down RPG camera, readable head and shoulders, stable floor contact",
    "front": "front-facing locked camera, symmetrical readable stance",
    "three_quarter": "three-quarter locked camera, slight turn, readable silhouette",
}


def _clean(value: Any) -> str:
    return str(value or "").strip()


def prompt_builder_options() -> Dict[str, Any]:
    return {
        "actions": sorted(ACTION_TEMPLATES.keys()),
        "directions": sorted(DIRECTIONS.keys()),
        "body_styles": BODY_STYLES,
        "art_styles": ART_STYLES,
        "camera_styles": CAMERA_STYLES,
    }


def build_structured_prompt(fields: Dict[str, Any]) -> Dict[str, Any]:
    action = _clean(fields.get("action") or fields.get("sprite_action") or "idle")
    direction = _clean(fields.get("direction") or "right")
    if action not in ACTION_TEMPLATES:
        raise ValueError(f"Unknown action '{action}'.")
    if direction not in DIRECTIONS:
        raise ValueError(f"Unknown direction '{direction}'.")

    character_type = _clean(fields.get("character_type")) or "original game character"
    body_style_key = _clean(fields.get("body_style") or "heroic")
    outfit = _clean(fields.get("outfit")) or "distinctive adventure outfit"
    camera_key = _clean(fields.get("camera") or fields.get("camera_style") or "side")
    art_key = _clean(fields.get("art_style") or "cel")
    extra = _clean(fields.get("extra"))
    negative_extra = _clean(fields.get("negative_extra"))

    body_style = BODY_STYLES.get(body_style_key, body_style_key)
    camera_style = CAMERA_STYLES.get(camera_key, camera_key)
    art_style = ART_STYLES.get(art_key, art_key)
    character = (
        f"single full body {character_type}, {body_style}, {outfit}, "
        "professional appealing character design, consistent face, consistent outfit"
    )
    style = (
        f"{art_style}, {camera_style}, production sprite sheet style, "
        "clean silhouette, cohesive palette, transparent-ready chroma background"
    )
    prompt = build_prompt(
        action=action,
        direction=direction,
        character=character,
        style=style,
        extra=extra,
        reference=bool(fields.get("reference")),
        pose_guided=bool(fields.get("pose_guided")),
    )
    if negative_extra:
        prompt["negative"] = f"{prompt['negative']}, {negative_extra}"
    prompt["builder_fields"] = {
        "character_type": character_type,
        "body_style": body_style_key,
        "outfit": outfit,
        "camera": camera_key,
        "art_style": art_key,
        "extra": extra,
        "negative_extra": negative_extra,
    }
    prompt["generated_character"] = character
    prompt["generated_style"] = style
    return prompt
