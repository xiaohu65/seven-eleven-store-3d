#!/usr/bin/env python3
"""Export the clean model to glTF 2.0 (GLB)."""
from __future__ import annotations

import os
from pathlib import Path

import bpy

ROOT = Path(__file__).resolve().parent.parent
bpy.ops.wm.open_mainfile(filepath=str(ROOT / "build" / "seven_eleven_store_asset.blend"))
scene = bpy.context.scene
bpy.ops.object.select_all(action="DESELECT")
selected = []
for obj in scene.objects:
    if obj.type in {"MESH", "EMPTY"}:
        obj.select_set(True)
        selected.append(obj)
print("SELECTED", len(selected))
bpy.context.view_layer.objects.active = next(o for o in selected if o.type == "MESH")
out = ROOT / "seven_eleven_store.glb"
bpy.ops.export_scene.gltf(
    filepath=str(out),
    export_format="GLB",
    use_selection=True,
    export_apply=True,
    export_yup=True,
    export_texcoords=True,
    export_normals=True,
    export_materials="EXPORT",
    export_image_format="AUTO",
    export_image_quality=90,
    export_cameras=False,
    export_lights=False,
    export_extras=True,
    export_animations=False,
    export_skins=False,
    export_morph=False,
)
print("EXPORTED", out, out.stat().st_size // 1024, "KiB")
