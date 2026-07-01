# SpriteForge Plugin Guide

SpriteForge loads Python plugins from `app/plugins/`. A plugin is a plain `.py`
file with one or more hook functions. Hooks are optional; define only the hooks
your plugin needs.

## Quick Start

1. Create a file such as `app/plugins/my_quality_plugin.py`.
2. Add one or more hook functions from the list below.
3. Open **Setup** to review plugin discovery/status, or run a QA check or engine export from the UI/CLI.

SpriteForge discovers plugin files automatically and exposes plugin status in the Setup UI. Disabled or invalid plugins are skipped by the manager.

## Hook: `on_qa_check`

Called after SpriteForge builds a QA summary.

```python
from pathlib import Path
from typing import Any, Dict


def on_qa_check(sprite_dir: Path, report: Dict[str, Any]) -> None:
    report.setdefault("plugin_metrics", {})["my_metric"] = {
        "label": "My custom metric",
        "value": 1,
        "ok": True,
    }
```

Arguments:
- `sprite_dir`: Path to the sprite output folder.
- `report`: Mutable QA report dictionary.

Use this hook for custom pass/fail checks, studio-specific metrics, or adding
report metadata.

## Hook: `on_export_engine`

Called after an engine export completes.

```python
from pathlib import Path


def on_export_engine(sprite_dir: Path, engine: str, dest: Path) -> None:
    note = Path(dest) / "export_note.txt"
    note.write_text(f"Exported {sprite_dir} to {engine}\n", encoding="utf-8")
```

Arguments:
- `sprite_dir`: Path to the sprite output folder.
- `engine`: Export target, such as `godot`, `unity`, or `unreal`.
- `dest`: Destination folder created by the exporter.

Use this hook to write import notes, copy studio templates, or generate engine
helper files.

## Filter Hooks

The plugin manager also supports filter-style hooks through
`PluginManager.filter_hook(name, value, *args, **kwargs)`. A filter hook receives
a value and returns the updated value. Current built-in pipeline calls mostly
use event hooks, but filters are available for future extension points.

## Safety Rules

- Keep plugin files small and focused.
- Never delete source sprite folders from a plugin.
- Use `Path` objects for paths and create destination folders before writing.
- Catch expected optional dependency failures inside your plugin.
- Prefer adding namespaced keys like `plugin_metrics["my_plugin"]`.

## Included Example

See `app/plugins/example_quality_metric.py`. It demonstrates:
- adding a `plugin_metrics.example_quality_metric` QA block;
- writing a small export note after engine export.
