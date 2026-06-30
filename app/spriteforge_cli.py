"""SpriteForge CLI Routing Launcher Command."""
import sys
import importlib

def main():
    if len(sys.argv) < 2:
        print("SpriteForge CLI v1.2.0")
        print("\nAvailable commands:")
        print("  ui          Start the local Flask Web UI server")
        print("  generate    Generate WAN sprites and control ComfyUI")
        print("  tool        Slices, chroma-keys, and packages sheets")
        print("  export      Export sheets to Godot, Unity, or Unreal")
        print("  prompts     Build posepacks and text prompts")
        print("  maintenance Manage ComfyUI git state and updates")
        print("\nRun: spriteforge <command> [args]")
        sys.exit(1)

    cmd = sys.argv[1]
    # Shift arguments to pass to sub-scripts
    sys.argv = [sys.argv[0]] + sys.argv[2:]

    try:
        if cmd == "ui":
            mod = importlib.import_module("spriteforge_web")
            sys.exit(mod.main())
        elif cmd == "generate":
            mod = importlib.import_module("spriteforge_unified")
            sys.exit(mod.main())
        elif cmd == "tool":
            mod = importlib.import_module("spriteforge")
            sys.exit(mod.main())
        elif cmd == "export":
            mod = importlib.import_module("spriteforge_engine_export")
            sys.exit(mod.main())
        elif cmd == "prompts":
            mod = importlib.import_module("spriteforge_prompts")
            sys.exit(mod.main())
        elif cmd == "maintenance":
            mod = importlib.import_module("spriteforge_maintenance")
            sys.exit(mod.main())
        else:
            print(f"Unknown command: {cmd}")
            print("Run 'spriteforge' without arguments for help.")
            sys.exit(1)
    except Exception as e:
        print(f"Error executing command '{cmd}': {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
