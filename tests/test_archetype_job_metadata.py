import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "app"
sys.path.insert(0, str(APP))


def test_archetype_generation_provenance_is_versioned_and_secret_free():
    from web_routes.routes_jobs import _archetype_generation_provenance

    provenance = _archetype_generation_provenance({
        "archetype_id": "hero_knight",
        "archetype_name": "Hero Knight",
        "archetype_tags": "human, melee, fantasy",
        "archetype_palette_hint": "silver, blue, gold",
        "archetype_customized": True,
    })

    assert provenance == {
        "schema": "spriteforge.archetype_generation_provenance.v1",
        "id": "hero_knight",
        "name": "Hero Knight",
        "tags": ["human", "melee", "fantasy"],
        "palette_hint": "silver, blue, gold",
        "customized": True,
        "source": "generate_view_visual_card",
    }


def test_archetype_generation_provenance_skips_plain_generations():
    from web_routes.routes_jobs import _archetype_generation_provenance

    assert _archetype_generation_provenance({"character": "plain custom hero"}) is None


def test_archetype_generation_provenance_parses_false_string():
    from web_routes.routes_jobs import _archetype_generation_provenance

    provenance = _archetype_generation_provenance({
        "archetype_id": "hero_knight",
        "archetype_customized": "false",
    })

    assert provenance["customized"] is False
