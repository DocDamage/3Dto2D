import os
import sys
import importlib.util
from pathlib import Path
from typing import Any, Dict, List, Callable

ROOT = Path(__file__).resolve().parent.parent
PLUGINS_DIR = ROOT / "plugins"

class PluginManager:
    _plugins: List[Any] = []
    _loaded: bool = False

    @staticmethod
    def load_plugins() -> None:
        """Discover and load all Python plugins in the plugins/ directory."""
        if PluginManager._loaded:
            return
            
        PLUGINS_DIR.mkdir(parents=True, exist_ok=True)
        PluginManager._plugins = []
        
        # Look for any .py file directly in plugins/
        for p in PLUGINS_DIR.glob("*.py"):
            try:
                module_name = f"plugins.{p.stem}"
                spec = importlib.util.spec_from_file_location(module_name, str(p))
                if spec and spec.loader:
                    module = importlib.util.module_from_spec(spec)
                    sys.modules[module_name] = module
                    spec.loader.exec_module(module)
                    PluginManager._plugins.append(module)
                    print(f"Loaded plugin: {p.name}")
            except Exception as e:
                print(f"Error loading plugin {p.name}: {e}", file=sys.stderr)
                
        PluginManager._loaded = True

    @staticmethod
    def trigger_hook(hook_name: str, *args, **kwargs) -> None:
        """Trigger a specific hook on all loaded plugins."""
        PluginManager.load_plugins()
        for plugin in PluginManager._plugins:
            if hasattr(plugin, hook_name):
                try:
                    hook_fn = getattr(plugin, hook_name)
                    if callable(hook_fn):
                        hook_fn(*args, **kwargs)
                except Exception as e:
                    print(f"Error executing hook '{hook_name}' in plugin '{plugin.__name__}': {e}", file=sys.stderr)

    @staticmethod
    def filter_hook(hook_name: str, value: Any, *args, **kwargs) -> Any:
        """Trigger a filtering hook that takes a value and returns a modified value."""
        PluginManager.load_plugins()
        current_value = value
        for plugin in PluginManager._plugins:
            if hasattr(plugin, hook_name):
                try:
                    hook_fn = getattr(plugin, hook_name)
                    if callable(hook_fn):
                        current_value = hook_fn(current_value, *args, **kwargs)
                except Exception as e:
                    print(f"Error executing filter hook '{hook_name}' in plugin '{plugin.__name__}': {e}", file=sys.stderr)
        return current_value
