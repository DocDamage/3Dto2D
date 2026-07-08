from __future__ import annotations

import copy
import datetime as dt
import json
import re
import uuid
from pathlib import Path
from typing import Any, Dict, List

from spriteforge_utils import ROOT, load_json, save_json


RECIPES_DIR = ROOT / "output" / "pixel_assets" / "recipes"
RECIPE_SCHEMA = "spriteforge.pixel_recipe.v1"

BUILT_IN_RECIPES: Dict[str, Dict[str, Any]] = {
    "rpg_starter": {
        "recipe_id": "rpg_starter",
        "name": "RPG Hero Starter",
        "description": "Hero, enemy, weapon, potion, item, and dungeon tile starter set.",
        "tags": ["rpg", "starter", "characters", "tiles"],
        "items": [
            {"type": "characters", "prompt": "rpg warrior hero", "resolution": "32x32", "count": 1},
            {"type": "characters", "prompt": "rpg goblin thief", "resolution": "32x32", "count": 1},
            {"type": "weapons", "prompt": "iron broadsword", "resolution": "16x16", "count": 1},
            {"type": "potions", "prompt": "mana potion", "resolution": "16x16", "count": 1},
            {"type": "items", "prompt": "treasure chest container", "resolution": "32x32", "count": 1},
            {"type": "tilesets", "prompt": "dungeon floor stone tile", "resolution": "32x32", "count": 1},
        ],
    },
    "dungeon_crawler": {
        "recipe_id": "dungeon_crawler",
        "name": "Dungeon Crawler",
        "description": "A compact dungeon encounter pack with enemies, equipment, and map tiles.",
        "tags": ["rpg", "dungeon", "encounter"],
        "items": [
            {"type": "characters", "prompt": "skeleton archer", "resolution": "32x32", "count": 1},
            {"type": "characters", "prompt": "wizard cleric", "resolution": "32x32", "count": 1},
            {"type": "weapons", "prompt": "fire staff", "resolution": "16x16", "count": 1},
            {"type": "potions", "prompt": "antidote elixir", "resolution": "16x16", "count": 1},
            {"type": "items", "prompt": "iron key", "resolution": "16x16", "count": 1},
            {"type": "tilesets", "prompt": "mossy brick wall tile", "resolution": "32x32", "count": 1},
        ],
    },
    "platformer_starter": {
        "recipe_id": "platformer_starter",
        "name": "Platformer Starter",
        "description": "Runner, enemy, pickup, hazard, and ground tile starter set.",
        "tags": ["platformer", "starter", "side-scroller"],
        "items": [
            {"type": "characters", "prompt": "platformer runner hero", "resolution": "32x32", "count": 1},
            {"type": "characters", "prompt": "spiky crawler enemy", "resolution": "32x32", "count": 1},
            {"type": "weapons", "prompt": "bouncing cherry bomb", "resolution": "16x16", "count": 1},
            {"type": "potions", "prompt": "haste elixir", "resolution": "16x16", "count": 1},
            {"type": "items", "prompt": "spinning gold coin currency", "resolution": "16x16", "count": 1},
            {"type": "tilesets", "prompt": "grass dirt block tile", "resolution": "32x32", "count": 1},
        ],
    },
    "potion_shop": {
        "recipe_id": "potion_shop",
        "name": "Potion / Item Shop",
        "description": "A small shop catalog with potion variants and furniture props.",
        "tags": ["shop", "items", "potions"],
        "items": [
            {"type": "potions", "prompt": "health recovery potion", "resolution": "16x16", "count": 1},
            {"type": "potions", "prompt": "mana recovery potion", "resolution": "16x16", "count": 1},
            {"type": "potions", "prompt": "stamina vigor potion", "resolution": "16x16", "count": 1},
            {"type": "potions", "prompt": "deadly poison vial", "resolution": "16x16", "count": 1},
            {"type": "items", "prompt": "wooden shop counter shelf", "resolution": "32x32", "count": 1},
            {"type": "items", "prompt": "potion storage rack container", "resolution": "32x32", "count": 1},
        ],
    },
    "ui_hud_pack": {
        "recipe_id": "ui_hud_pack",
        "name": "UI HUD Pack",
        "description": "Hearts, mana, inventory slot, button, border, and cursor icons.",
        "tags": ["ui", "hud", "icons"],
        "items": [
            {"type": "ui_icons", "prompt": "red heart health icon", "resolution": "16x16", "count": 1},
            {"type": "ui_icons", "prompt": "blue mana drop icon", "resolution": "16x16", "count": 1},
            {"type": "ui_icons", "prompt": "inventory slot frame", "resolution": "32x32", "count": 1},
            {"type": "ui_icons", "prompt": "menu button frame", "resolution": "32x16", "count": 1},
            {"type": "ui_icons", "prompt": "ornate window border corner", "resolution": "16x16", "count": 1},
            {"type": "ui_icons", "prompt": "gold cursor pointer", "resolution": "16x16", "count": 1},
        ],
    },
}


class PixelRecipeService:
    @staticmethod
    def initialize() -> None:
        RECIPES_DIR.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def list_recipes() -> List[Dict[str, Any]]:
        PixelRecipeService.initialize()
        recipes: List[Dict[str, Any]] = []
        for recipe in BUILT_IN_RECIPES.values():
            item = PixelRecipeService._with_defaults(recipe, source="built_in")
            recipes.append(item)
        for file_path in RECIPES_DIR.glob("recipe_*.json"):
            try:
                data = load_json(file_path, {})
            except (OSError, json.JSONDecodeError, ValueError):
                continue
            if data:
                data["source"] = "user"
                recipes.append(data)
        return sorted(recipes, key=lambda item: (item.get("source") != "built_in", item.get("name", "")))

    @staticmethod
    def get_recipe(recipe_id: str) -> Dict[str, Any]:
        if recipe_id in BUILT_IN_RECIPES:
            return PixelRecipeService._with_defaults(BUILT_IN_RECIPES[recipe_id], source="built_in")
        PixelRecipeService.initialize()
        file_path = RECIPES_DIR / f"{recipe_id}.json"
        if not file_path.exists():
            raise FileNotFoundError(f"Recipe not found: {recipe_id}")
        data = load_json(file_path, {})
        ok, message = PixelRecipeService.validate_recipe(data)
        if not ok:
            raise ValueError(message)
        data["source"] = "user"
        return data

    @staticmethod
    def save_recipe(data: Dict[str, Any]) -> Dict[str, Any]:
        PixelRecipeService.initialize()
        recipe = PixelRecipeService._with_defaults(data, source="user")
        if not recipe.get("recipe_id") or recipe["recipe_id"] in BUILT_IN_RECIPES:
            recipe["recipe_id"] = f"recipe_{uuid.uuid4().hex[:12]}"
        recipe["recipe_id"] = PixelRecipeService._safe_id(recipe["recipe_id"])
        recipe["updated_at"] = dt.datetime.utcnow().isoformat() + "Z"

        ok, message = PixelRecipeService.validate_recipe(recipe)
        if not ok:
            raise ValueError(message)

        save_json(RECIPES_DIR / f"{recipe['recipe_id']}.json", recipe)
        return recipe

    @staticmethod
    def import_recipe(data: Dict[str, Any]) -> Dict[str, Any]:
        return PixelRecipeService.save_recipe(data)

    @staticmethod
    def export_recipe(recipe_id: str) -> Path:
        recipe = PixelRecipeService.get_recipe(recipe_id)
        PixelRecipeService.initialize()
        export_path = RECIPES_DIR / f"{recipe_id}_export.json"
        save_json(export_path, recipe)
        return export_path

    @staticmethod
    def validate_recipe(data: Any) -> tuple[bool, str]:
        if not isinstance(data, dict):
            return False, "Recipe must be a JSON object."
        if data.get("schema") != RECIPE_SCHEMA:
            return False, f"Recipe schema must be {RECIPE_SCHEMA}."
        if not isinstance(data.get("recipe_id"), str) or not data["recipe_id"].strip():
            return False, "Recipe must include a recipe_id."
        if not isinstance(data.get("name"), str) or not data["name"].strip():
            return False, "Recipe must include a name."
        items = data.get("items")
        if not isinstance(items, list) or not items:
            return False, "Recipe must include at least one item."
        for index, item in enumerate(items, start=1):
            if not isinstance(item, dict):
                return False, f"Recipe item {index} must be an object."
            if item.get("type") not in {"characters", "creatures", "items", "weapons", "potions", "ui_icons", "tilesets", "backgrounds"}:
                return False, f"Recipe item {index} has an unsupported type."
            if not isinstance(item.get("prompt"), str) or not item["prompt"].strip():
                return False, f"Recipe item {index} must include a prompt."
            count = item.get("count", 1)
            if not isinstance(count, int) or count < 1 or count > 64:
                return False, f"Recipe item {index} count must be between 1 and 64."
        return True, ""

    @staticmethod
    def _with_defaults(data: Dict[str, Any], source: str) -> Dict[str, Any]:
        recipe = copy.deepcopy(data)
        recipe.setdefault("schema", RECIPE_SCHEMA)
        recipe.setdefault("recipe_id", f"recipe_{uuid.uuid4().hex[:12]}")
        recipe.setdefault("name", recipe["recipe_id"].replace("_", " ").title())
        recipe.setdefault("description", "")
        recipe.setdefault("tags", [])
        recipe.setdefault("created_at", dt.datetime.utcnow().isoformat() + "Z")
        recipe["source"] = source
        return recipe

    @staticmethod
    def _safe_id(value: str) -> str:
        safe = re.sub(r"[^a-zA-Z0-9_]+", "_", value.strip()).strip("_").lower()
        if not safe.startswith("recipe_"):
            safe = f"recipe_{safe}"
        return safe[:80] or f"recipe_{uuid.uuid4().hex[:12]}"


PixelRecipeService.initialize()
