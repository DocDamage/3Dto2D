#!/usr/bin/env python3
"""
SpriteForge Blender orthographic animation renderer v2.

Single direction:
blender -b --python blender_render_ortho.py -- --blend input/character.blend --output output/ortho_frames --direction front --resolution 512 --fps 12 --start 1 --end 32 --transparent

Multiple directions:
blender -b --python blender_render_ortho.py -- --blend input/character.blend --output output/ortho_frames --directions front,right,left,back --resolution 512 --fps 12 --start 1 --end 32 --transparent

All actions on all armatures:
blender -b --python blender_render_ortho.py -- --blend input/character.blend --output output/actions --actions all --directions front,right --resolution 512 --fps 12 --transparent
"""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Tuple

import bpy
from mathutils import Vector


DIRECTION_TABLE = {
    "front": Vector((0, -1, 0.18)),
    "back": Vector((0, 1, 0.18)),
    "left": Vector((-1, 0, 0.18)),
    "right": Vector((1, 0, 0.18)),
    "iso": Vector((1, -1, 0.65)),
}


def parse_args():
    argv = sys.argv
    if "--" in argv:
        argv = argv[argv.index("--") + 1 :]
    else:
        argv = []

    p = argparse.ArgumentParser(description="Render Blender animation from an orthographic camera")
    p.add_argument("--blend", default=None, help="Blend file to open")
    p.add_argument("--fbx", default=None, help="FBX file to import")
    p.add_argument("--output", required=True, help="Output frame folder")
    p.add_argument("--prefix", default="frame_", help="Output file prefix")
    p.add_argument("--direction", choices=list(DIRECTION_TABLE.keys()), default="front")
    p.add_argument("--directions", default=None, help="Comma-separated directions, e.g. front,right,left,back")
    p.add_argument("--resolution", type=int, default=512, help="Square render resolution")
    p.add_argument("--fps", type=int, default=12)
    p.add_argument("--start", type=int, default=None, help="Start frame")
    p.add_argument("--end", type=int, default=None, help="End frame")
    p.add_argument("--action", default=None, help="Action name to render")
    p.add_argument("--actions", choices=["current", "all"], default="current", help="Render current action or every action")
    p.add_argument("--ortho-scale", type=float, default=None, help="Orthographic camera scale. Auto if omitted.")
    p.add_argument("--camera-distance", type=float, default=6.0, help="Distance multiplier from subject center")
    p.add_argument("--transparent", action="store_true", help="Transparent background")
    p.add_argument("--engine", default="BLENDER_EEVEE_NEXT", help="Render engine: BLENDER_EEVEE_NEXT, BLENDER_EEVEE, BLENDER_WORKBENCH, CYCLES")
    p.add_argument("--samples", type=int, default=32, help="Render samples where applicable")
    p.add_argument("--add-light", action="store_true", help="Add simple sun and area light if the scene is dark/no lights")
    p.add_argument("--fit-padding", type=float, default=1.25, help="Auto ortho scale multiplier")
    return p.parse_args(argv)


def import_fbx(path: str):
    bpy.ops.import_scene.fbx(filepath=path)


def mesh_bounds_world():
    depsgraph = bpy.context.evaluated_depsgraph_get()
    coords = []

    for obj in bpy.context.scene.objects:
        if obj.hide_get():
            continue
        if obj.type != "MESH":
            continue
        try:
            eval_obj = obj.evaluated_get(depsgraph)
            mesh = eval_obj.to_mesh()
            for v in mesh.vertices:
                coords.append(eval_obj.matrix_world @ v.co)
            eval_obj.to_mesh_clear()
        except Exception:
            for corner in obj.bound_box:
                coords.append(obj.matrix_world @ Vector(corner))

    if not coords:
        return Vector((0, 0, 0)), Vector((0, 0, 2))

    min_v = Vector((min(c.x for c in coords), min(c.y for c in coords), min(c.z for c in coords)))
    max_v = Vector((max(c.x for c in coords), max(c.y for c in coords), max(c.z for c in coords)))
    return min_v, max_v


def look_at(obj, target: Vector):
    direction = target - obj.location
    obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()


def ensure_camera(name="SpriteForge_Ortho_Camera"):
    existing = bpy.data.objects.get(name)
    if existing and existing.type == "CAMERA":
        cam = existing
    else:
        cam_data = bpy.data.cameras.new(name)
        cam = bpy.data.objects.new(name, cam_data)
        bpy.context.collection.objects.link(cam)
    bpy.context.scene.camera = cam
    cam.data.type = "ORTHO"
    cam.data.clip_end = 10000
    return cam


def direction_vector(direction: str) -> Vector:
    v = DIRECTION_TABLE[direction].copy()
    v.normalize()
    return v


def set_render_engine(scene, engine: str, samples: int):
    engines = {item.identifier for item in bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items}
    if engine not in engines:
        if "BLENDER_EEVEE_NEXT" in engines:
            engine = "BLENDER_EEVEE_NEXT"
        elif "BLENDER_EEVEE" in engines:
            engine = "BLENDER_EEVEE"
        elif "BLENDER_WORKBENCH" in engines:
            engine = "BLENDER_WORKBENCH"
        else:
            engine = scene.render.engine

    scene.render.engine = engine

    if scene.render.engine == "CYCLES":
        scene.cycles.samples = samples
        scene.cycles.use_denoising = True
        prefs = bpy.context.preferences
        try:
            prefs.addons["cycles"].preferences.compute_device_type = "CUDA"
            scene.cycles.device = "GPU"
        except Exception:
            pass

    if hasattr(scene, "eevee"):
        try:
            scene.eevee.taa_render_samples = samples
        except Exception:
            pass

    if hasattr(scene, "eevee_next"):
        try:
            scene.eevee_next.taa_render_samples = samples
        except Exception:
            pass


def armatures() -> List[bpy.types.Object]:
    return [obj for obj in bpy.context.scene.objects if obj.type == "ARMATURE"]


def apply_action(action_name: Optional[str]) -> Optional[Tuple[int, int, str]]:
    if not action_name:
        return None
    action = bpy.data.actions.get(action_name)
    if action is None:
        raise RuntimeError(f"Action not found: {action_name}")
    for arm in armatures():
        if arm.animation_data is None:
            arm.animation_data_create()
        arm.animation_data.action = action
    start, end = action.frame_range
    return int(math.floor(start)), int(math.ceil(end)), action.name


def action_names_for_render(mode: str, explicit_action: Optional[str]) -> List[Optional[str]]:
    if explicit_action:
        return [explicit_action]
    if mode == "all":
        names = [a.name for a in bpy.data.actions]
        return names if names else [None]
    return [None]


def ensure_basic_lighting():
    lights = [obj for obj in bpy.context.scene.objects if obj.type == "LIGHT"]
    if lights:
        return
    sun_data = bpy.data.lights.new("SpriteForge_Sun", type="SUN")
    sun = bpy.data.objects.new("SpriteForge_Sun", sun_data)
    bpy.context.collection.objects.link(sun)
    sun.location = (0, -4, 6)
    sun.rotation_euler = (math.radians(55), 0, math.radians(0))
    sun_data.energy = 2.5

    area_data = bpy.data.lights.new("SpriteForge_Area", type="AREA")
    area = bpy.data.objects.new("SpriteForge_Area", area_data)
    bpy.context.collection.objects.link(area)
    area.location = (0, -3, 3)
    area_data.energy = 250
    area_data.size = 5


def configure_camera(direction: str, ortho_scale: Optional[float], camera_distance: float, fit_padding: float):
    min_v, max_v = mesh_bounds_world()
    center = (min_v + max_v) * 0.5
    size = max_v - min_v
    max_dim = max(size.x, size.y, size.z, 1.0)

    cam = ensure_camera()
    cam_dir = direction_vector(direction)
    cam.location = center + cam_dir * (max_dim * camera_distance)
    look_at(cam, center)

    if ortho_scale is not None:
        cam.data.ortho_scale = ortho_scale
    else:
        cam.data.ortho_scale = max(size.z, size.x, size.y, 1.0) * fit_padding

    return cam


def render_one(output: Path, prefix: str, direction: str, args, action_name: Optional[str]):
    scene = bpy.context.scene
    action_range = apply_action(action_name)

    if args.start is not None:
        scene.frame_start = args.start
    elif action_range is not None:
        scene.frame_start = action_range[0]

    if args.end is not None:
        scene.frame_end = args.end
    elif action_range is not None:
        scene.frame_end = action_range[1]

    configure_camera(direction, args.ortho_scale, args.camera_distance, args.fit_padding)

    output.mkdir(parents=True, exist_ok=True)
    scene.render.filepath = str(output / prefix)

    print("SpriteForge Blender render")
    print(f"Output: {output}")
    print(f"Action: {action_name or 'current'}")
    print(f"Direction: {direction}")
    print(f"Frame range: {scene.frame_start}-{scene.frame_end}")
    print(f"Resolution: {args.resolution}x{args.resolution}")
    print(f"Ortho scale: {bpy.context.scene.camera.data.ortho_scale:.4f}")

    bpy.ops.render.render(animation=True)


def main():
    args = parse_args()

    if args.blend:
        bpy.ops.wm.open_mainfile(filepath=str(Path(args.blend).resolve()))

    if args.fbx:
        import_fbx(str(Path(args.fbx).resolve()))

    scene = bpy.context.scene
    scene.render.fps = args.fps
    scene.render.resolution_x = args.resolution
    scene.render.resolution_y = args.resolution
    scene.render.resolution_percentage = 100

    set_render_engine(scene, args.engine, args.samples)

    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    if args.transparent:
        try:
            scene.render.film_transparent = True
        except Exception:
            pass

    if args.add_light:
        ensure_basic_lighting()

    directions = [d.strip() for d in (args.directions or args.direction).split(",") if d.strip()]
    for d in directions:
        if d not in DIRECTION_TABLE:
            raise RuntimeError(f"Unknown direction: {d}")

    output_root = Path(args.output).resolve()
    actions = action_names_for_render(args.actions, args.action)

    multi = len(directions) > 1 or len(actions) > 1
    for action_name in actions:
        for direction in directions:
            action_part = action_name or "current"
            if multi:
                out = output_root / action_part / direction
                prefix = args.prefix
            else:
                out = output_root
                prefix = args.prefix
            render_one(out, prefix, direction, args, action_name)


if __name__ == "__main__":
    main()
