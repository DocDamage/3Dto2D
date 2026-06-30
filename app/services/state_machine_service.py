"""Animation state-machine manifests and starter engine controllers."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List


def _clean_name(value: str, fallback: str) -> str:
    text = "".join(ch if ch.isalnum() or ch == "_" else "_" for ch in str(value or "").strip())
    text = "_".join(part for part in text.split("_") if part)
    return text or fallback


def _state(row: Dict[str, Any], index: int) -> Dict[str, Any]:
    name = _clean_name(row.get("name"), f"state_{index}")
    return {
        "name": name,
        "sprite_path": str(row.get("sprite_path") or "").replace("\\", "/").strip(),
        "loop": bool(row.get("loop", True)),
    }


def _transition(row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "from": _clean_name(row.get("from"), "idle"),
        "to": _clean_name(row.get("to"), "idle"),
        "condition": str(row.get("condition") or "").strip() or "trigger",
    }


def build_state_machine(payload: Dict[str, Any], output_dir: Path) -> Dict[str, Any]:
    states = [_state(row, i) for i, row in enumerate(payload.get("states") or []) if isinstance(row, dict)]
    states = [state for state in states if state["sprite_path"]]
    if not states:
        raise ValueError("At least one state with a sprite_path is required.")
    transitions = [
        _transition(row) for row in payload.get("transitions") or []
        if isinstance(row, dict) and row.get("from") and row.get("to")
    ]
    initial = _clean_name(payload.get("initial_state"), states[0]["name"])
    if initial not in {state["name"] for state in states}:
        initial = states[0]["name"]
    manifest = {
        "schema": "spriteforge_state_machine.v1",
        "name": _clean_name(payload.get("name"), "sprite_state_machine"),
        "initial_state": initial,
        "states": states,
        "transitions": transitions,
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "state_machine.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (output_dir / "SpriteForgeStateMachine.gd").write_text(godot_script(manifest), encoding="utf-8")
    (output_dir / "SpriteForgeStateMachine.cs").write_text(unity_script(manifest), encoding="utf-8")
    return {
        "ok": True,
        "manifest": manifest,
        "manifest_path": str(output_dir / "state_machine.json"),
        "godot_script": str(output_dir / "SpriteForgeStateMachine.gd"),
        "unity_script": str(output_dir / "SpriteForgeStateMachine.cs"),
    }


def godot_script(manifest: Dict[str, Any]) -> str:
    states = ", ".join(f'"{state["name"]}"' for state in manifest["states"])
    initial = manifest["initial_state"]
    return f'''extends Node

signal state_changed(name: String)

@export var initial_state: String = "{initial}"
var state: String = initial_state
var known_states := [{states}]

func _ready() -> void:
    set_state(initial_state)

func set_state(name: String) -> void:
    if not known_states.has(name):
        push_warning("Unknown SpriteForge state: " + name)
        return
    state = name
    state_changed.emit(state)

func handle_condition(condition: String) -> void:
    match [state, condition]:
{_godot_transition_cases(manifest)}
        _:
            pass
'''


def _godot_transition_cases(manifest: Dict[str, Any]) -> str:
    lines: List[str] = []
    for row in manifest.get("transitions", []):
        lines.append(f'        ["{row["from"]}", "{row["condition"]}"]:')
        lines.append(f'            set_state("{row["to"]}")')
    return "\n".join(lines) if lines else "        _:\n            pass"


def unity_script(manifest: Dict[str, Any]) -> str:
    states = ", ".join(f'"{state["name"]}"' for state in manifest["states"])
    initial = manifest["initial_state"]
    cases = "\n".join(
        f'        if (State == "{row["from"]}" && condition == "{row["condition"]}") SetState("{row["to"]}");'
        for row in manifest.get("transitions", [])
    )
    return f'''using UnityEngine;

public class SpriteForgeStateMachine : MonoBehaviour
{{
    public string InitialState = "{initial}";
    public string State {{ get; private set; }}
    public string[] KnownStates = new[] {{ {states} }};

    void Start() => SetState(InitialState);

    public void SetState(string state)
    {{
        State = state;
    }}

    public void HandleCondition(string condition)
    {{
{cases or "        // Add transitions in state_machine.json."}
    }}
}}
'''
