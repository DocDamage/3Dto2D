from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def test_env_files_are_ignored_but_example_is_shareable():
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    example = (ROOT / ".env.example").read_text(encoding="utf-8")

    assert "\n.env\n" in f"\n{gitignore}\n"
    assert "\napp/.env\n" in f"\n{gitignore}\n"
    assert "OPENAI_API_KEY=" in example
    assert "GEMINI_API_KEY=" in example
    assert "sk-" not in example
    assert "AIza" not in example
