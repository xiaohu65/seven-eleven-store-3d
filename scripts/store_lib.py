"""Geometry, material and helper library for the 7-Eleven corner-store build.

The library is intentionally small and dependency-free inside Blender: every
part is generated as a normal mesh with explicit normals/UVs, so the resulting
GLB is portable and needs no baking.
"""
from __future__ import annotations

import math
import os
import random
from pathlib import Path

import bpy
from mathutils import Matrix, Vector

ROOT = Path(__file__).resolve().parent.parent
TEX = ROOT / "textures"
TAU = math.tau
PI = math.pi


# ---------------------------------------------------------------------------
# Colour / maths
# ---------------------------------------------------------------------------
def srgb(hex_color: str) -> tuple[float, float, float, float]:
    h = hex_color.lstrip("#")
    vals = []
    for i in (0, 2, 4):
        c = int(h[i:i + 2], 16) / 255.0
        vals.append(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4)
    return (vals[0], vals[1], vals[2], 1.0)


def rot_z(v: tuple[float, float, float], angle: float) -> Vector:
    c, s = math.cos(angle), math.sin(angle)
    x, y, z = v
    return Vector((x * c - y * s, x * s + y * c, z))


# ---------------------------------------------------------------------------
# Mesh builder
# ---------------------------------------------------------------------------
class MeshBuilder:
    def __init__(self, name: str, material: bpy.types.Material, uv: bool = False):
        self.name = name
        self.material = material
        self.verts: list[tuple[float, float, float]] = []
        self.faces: list[list[int]] = []
        self.uvs: list[list[tuple[float, float]] | None] = []
        self.smooth: list[bool] = []
        self.has_uv = uv

    def add(self, verts, faces, uvs=None, smooth=False):
        off = len(self.verts)
        self.verts.extend(tuple(float(c) for c in v) for v in verts)
        sm = [smooth] * len(faces) if isinstance(smooth, bool) else list(smooth)
        for i, face in enumerate(faces):
            self.faces.append([int(k) + off for k in face])
            self.smooth.append(bool(sm[i]))
            if uvs is not None:
                self.uvs.append(list(uvs[i]))
                self.has_uv = True
            else:
                self.uvs.append(None)

    def add_box(self, center, size, rot=0.0, uv_scale: float | None = None):
        verts, faces, face_uvs = box_geo(center, size, rot)
        if uv_scale:
            face_uvs = [[(u / uv_scale, v / uv_scale) for u, v in f] for f in face_uvs]
        self.add(verts, faces, face_uvs if uv_scale else None)

    def add_quad(self, corners, uv=True):
        self.add(corners, [[0, 1, 2, 3]], [[(0, 0), (1, 0), (1, 1), (0, 1)]] if uv else None)

    def add_cyl(self, p0, p1, r0, r1=None, seg=12, caps=True, uv_scale=None):
        verts, faces, uvs, smooth = cylinder_geo(p0, p1, r0, r1 if r1 is not None else r0,
                                                 seg, caps, uv_scale)
        self.add(verts, faces, uvs if uv_scale else None, smooth=smooth)

    def add_torus(self, center, major, minor, axis="Z", seg_major=24, seg_minor=8):
        verts, faces = torus_geo(center, major, minor, axis, seg_major, seg_minor)
        self.add(verts, faces, smooth=True)

    def build(self, collection):
        if not self.faces:
            return None
        me = bpy.data.meshes.new(self.name)
        me.from_pydata(self.verts, [], self.faces)
        me.validate(verbose=False)
        me.materials.append(self.material)
        if self.has_uv:
            layer = me.uv_layers.new(name="UVMap")
            for poly, face_uv in zip(me.polygons, self.uvs):
                if not face_uv:
                    face_uv = [(0.0, 0.0)] * poly.loop_total
                for li, uv in zip(poly.loop_indices, face_uv):
                    layer.data[li].uv = uv
        for poly, sm in zip(me.polygons, self.smooth):
            poly.use_smooth = sm
        me.update()
        ob = bpy.data.objects.new(self.name, me)
        collection.objects.link(ob)
        return ob


class Context:
    def __init__(self):
        self.collections: dict[str, bpy.types.Collection] = {}
        self.builders: dict[tuple[str, str, str], MeshBuilder] = {}

    def coll(self, name: str):
        if name not in self.collections:
            c = bpy.data.collections.new(name)
            bpy.context.scene.collection.children.link(c)
            self.collections[name] = c
        return self.collections[name]

    def b(self, group: str, material, name: str, uv=False) -> MeshBuilder:
        key = (group, material.name, name)
        if key not in self.builders:
            self.builders[key] = MeshBuilder(f"{group}_{name}", material, uv=uv)
        return self.builders[key]

    def finish(self):
        for (group, _mat, _name), b in self.builders.items():
            b.build(self.coll(group))


# ---------------------------------------------------------------------------
# Primitives
# ---------------------------------------------------------------------------
def box_geo(center, size, rot=0.0):
    cx, cy, cz = center
    sx, sy, sz = size
    hx, hy, hz = sx / 2, sy / 2, sz / 2
    local = [(-hx, -hy, -hz), (hx, -hy, -hz), (hx, hy, -hz), (-hx, hy, -hz),
             (-hx, -hy, hz), (hx, -hy, hz), (hx, hy, hz), (-hx, hy, hz)]
    if rot:
        c, s = math.cos(rot), math.sin(rot)
        verts = []
        for x, y, z in local:
            verts.append((x * c - y * s + cx, x * s + y * c + cy, z + cz))
    else:
        verts = [(x + cx, y + cy, z + cz) for x, y, z in local]
    faces = [
        [3, 2, 1, 0],
        [4, 5, 6, 7],
        [0, 1, 5, 4],
        [1, 2, 6, 5],
        [2, 3, 7, 6],
        [0, 4, 7, 3],
    ]
    # Per-face UVs in local metres.
    face_uvs = [
        [(0, 0), (sx, 0), (sx, sy), (0, sy)],
        [(0, 0), (sx, 0), (sx, sy), (0, sy)],
        [(0, 0), (sx, 0), (sx, sz), (0, sz)],
        [(0, 0), (sy, 0), (sy, sz), (0, sz)],
        [(0, 0), (sx, 0), (sx, sz), (0, sz)],
        [(0, 0), (sy, 0), (sy, sz), (0, sz)],
    ]
    # The top face needs a proper (x,y) mapping, not a side mapping.
    face_uvs[1] = [(0, 0), (sx, 0), (sx, sy), (0, sy)]
    return verts, faces, face_uvs


def add_box(b, center, size, rot=0.0, uv_scale=None):
    b.add_box(center, size, rot=rot, uv_scale=uv_scale)


def frame_axes(axis: Vector):
    axis = axis.normalized()
    ref = Vector((1, 0, 0)) if abs(axis.dot(Vector((1, 0, 0)))) < 0.9 else Vector((0, 1, 0))
    u = axis.cross(ref).normalized()
    v = axis.cross(u).normalized()
    return u, v


def cylinder_geo(p0, p1, r0, r1, segments=12, caps=True, uv_scale=None):
    a = Vector(p0)
    b = Vector(p1)
    axis = b - a
    length = axis.length
    if length < 1e-8:
        return [], [], [], []
    u, v = frame_axes(axis)
    verts = []
    for p, r in ((a, r0), (b, r1)):
        for k in range(segments):
            ang = TAU * k / segments
            q = p + u * (math.cos(ang) * r) + v * (math.sin(ang) * r)
            verts.append((q.x, q.y, q.z))
    faces = []
    uvs = []
    smooth = []
    for k in range(segments):
        k2 = (k + 1) % segments
        faces.append([k, k2, segments + k2, segments + k])
        uvs.append([
            (k / segments * TAU * ((r0 + r1) / 2) / (uv_scale or 1), 0),
            ((k + 1) / segments * TAU * ((r0 + r1) / 2) / (uv_scale or 1), 0),
            ((k + 1) / segments * TAU * ((r0 + r1) / 2) / (uv_scale or 1), length / (uv_scale or 1)),
            (k / segments * TAU * ((r0 + r1) / 2) / (uv_scale or 1), length / (uv_scale or 1)),
        ])
        smooth.append(True)
    if caps:
        faces.append(list(range(segments - 1, -1, -1)))
        uvs.append([(0, 0)] * segments)
        smooth.append(False)
        faces.append(list(range(segments, segments * 2)))
        uvs.append([(0, 0)] * segments)
        smooth.append(False)
    return verts, faces, uvs, smooth


def torus_geo(center, major, minor, axis="Z", seg_major=24, seg_minor=8):
    cx, cy, cz = center
    verts = []
    for i in range(seg_major):
        u = TAU * i / seg_major
        cu, su = math.cos(u), math.sin(u)
        for j in range(seg_minor):
            v = TAU * j / seg_minor
            cv, sv = math.cos(v), math.sin(v)
            rr = major + minor * cv
            if axis == "Z":
                verts.append((cx + rr * cu, cy + rr * su, cz + minor * sv))
            elif axis == "X":
                verts.append((cx + minor * sv, cy + rr * cu, cz + rr * su))
            else:  # Y
                verts.append((cx + rr * cu, cy + minor * sv, cz + rr * su))
    faces = []
    for i in range(seg_major):
        i2 = (i + 1) % seg_major
        for j in range(seg_minor):
            j2 = (j + 1) % seg_minor
            a = i * seg_minor + j
            b = i2 * seg_minor + j
            c = i2 * seg_minor + j2
            d = i * seg_minor + j2
            faces.append([a, b, c, d])
    return verts, faces


def add_cyl(b, p0, p1, r0, r1=None, seg=12, caps=True, uv_scale=None):
    b.add_cyl(p0, p1, r0, r1, seg=seg, caps=caps, uv_scale=uv_scale)


def add_torus(b, center, major, minor, axis="Z", seg_major=24, seg_minor=8):
    b.add_torus(center, major, minor, axis, seg_major, seg_minor)


def add_quad(b, corners, uvs=None):
    b.add(corners, [[0, 1, 2, 3]], [uvs] if uvs else [[(0, 0), (1, 0), (1, 1), (0, 1)]])


def add_plane(b, center, width, height, facing="-Y", uv=True):
    """Rectangular double-checked plane with correct outward normal."""
    x, y, z = center
    hw, hh = width / 2, height / 2
    if facing == "-Y":
        corners = [(x - hw, y, z - hh), (x + hw, y, z - hh),
                   (x + hw, y, z + hh), (x - hw, y, z + hh)]
    elif facing == "+Y":
        corners = [(x + hw, y, z - hh), (x - hw, y, z - hh),
                   (x - hw, y, z + hh), (x + hw, y, z + hh)]
    elif facing == "-X":
        corners = [(x, y + hw, z - hh), (x, y - hw, z - hh),
                   (x, y - hw, z + hh), (x, y + hw, z + hh)]
    elif facing == "+X":
        corners = [(x, y - hw, z - hh), (x, y + hw, z - hh),
                   (x, y + hw, z + hh), (x, y - hw, z + hh)]
    elif facing == "+Z":
        corners = [(x - hw, y - hh, z), (x + hw, y - hh, z),
                   (x + hw, y + hh, z), (x - hw, y + hh, z)]
    elif facing == "-Z":
        corners = [(x - hw, y + hh, z), (x + hw, y + hh, z),
                   (x + hw, y - hh, z), (x - hw, y - hh, z)]
    else:
        raise ValueError(facing)
    b.add(corners, [[0, 1, 2, 3]], [[(0, 0), (1, 0), (1, 1), (0, 1)]] if uv else None)


def add_box_uvrect(b, center, size, uv_rect, rot=0.0):
    """Add a box whose six faces sample a sub-rectangle of an atlas image.

    This lets hundreds of products share one packaging material while each
    package gets its own printed label. The same rectangle is used on all six
    faces; at shelf scale this is more convincing than a flat colour and it
    keeps the draw-call count low.
    """
    verts, faces, _ = box_geo(center, size, rot)
    u0, v0, u1, v1 = uv_rect
    face_uv = [(u0, v0), (u1, v0), (u1, v1), (u0, v1)]
    b.add(verts, faces, [list(face_uv) for _ in faces])


def add_quad_uvrect(b, corners, uv_rect):
    u0, v0, u1, v1 = uv_rect
    b.add(corners, [[0, 1, 2, 3]], [[(u0, v0), (u1, v0), (u1, v1), (u0, v1)]])


def add_tube(b, points, radius, seg=6):
    for p0, p1 in zip(points, points[1:]):
        b.add_cyl(p0, p1, radius, radius, seg=seg, caps=False)


def add_cross_brace(b, p0, p1, width=0.04):
    a = Vector(p0)
    c = Vector(p1)
    mid = (a + c) / 2
    length = (c - a).length
    add_box(b, tuple(mid), (length, width, width), rot=math.atan2((c - a).y, (c - a).x))


# ---------------------------------------------------------------------------
# Materials
# ---------------------------------------------------------------------------
def _principled(name, color="#ffffff", metallic=0.0, roughness=0.5,
                emission=None, emission_strength=0.0, alpha=1.0):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    mat.use_backface_culling = False
    nt = mat.node_tree
    bsdf = nt.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = srgb(color) if isinstance(color, str) else (*color, 1)
    bsdf.inputs["Metallic"].default_value = metallic
    bsdf.inputs["Roughness"].default_value = roughness
    if alpha < 1.0:
        bsdf.inputs["Alpha"].default_value = alpha
        try:
            mat.surface_render_method = "DITHERED"
        except Exception:
            pass
        try:
            mat.blend_method = "BLEND"
        except Exception:
            pass
        mat.use_transparent_shadow = True
        mat.diffuse_color = (srgb(color)[0], srgb(color)[1], srgb(color)[2], alpha)
    if emission:
        bsdf.inputs["Emission Color"].default_value = srgb(emission)
        bsdf.inputs["Emission Strength"].default_value = emission_strength
    mat.diffuse_color = srgb(color) if isinstance(color, str) else (*color, 1)
    return mat


def _image(filename):
    p = TEX / filename
    img = bpy.data.images.load(str(p), check_existing=True)
    img.colorspace_settings.name = "sRGB"
    return img


def image_material(name, filename, metallic=0.0, roughness=0.45,
                   emission=False, emission_strength=1.0, alpha=False,
                   interpolation="Linear"):
    mat = _principled(name, "#ffffff", metallic, roughness)
    nt = mat.node_tree
    bsdf = nt.nodes.get("Principled BSDF")
    node = nt.nodes.new("ShaderNodeTexImage")
    node.image = _image(filename)
    node.interpolation = interpolation
    node.extension = "CLIP" if alpha else "REPEAT"
    nt.links.new(node.outputs["Color"], bsdf.inputs["Base Color"])
    if alpha:
        nt.links.new(node.outputs["Alpha"], bsdf.inputs["Alpha"])
        bsdf.inputs["Alpha"].default_value = 1.0
        try:
            mat.surface_render_method = "DITHERED"
        except Exception:
            pass
        try:
            mat.blend_method = "BLEND"
        except Exception:
            pass
        mat.use_transparent_shadow = True
    if emission:
        nt.links.new(node.outputs["Color"], bsdf.inputs["Emission Color"])
        bsdf.inputs["Emission Strength"].default_value = emission_strength
        if alpha:
            # Keep alpha separate from the emission; the socket still uses it.
            pass
    return mat


def build_materials():
    M = {}
    # Image-based materials --------------------------------------------------
    M["fascia"] = image_material("M_Sign_Fascia", "fascia_sign.png", roughness=0.55,
                                 emission=True, emission_strength=1.85)
    # The pylon face is deliberately more diffuse: a close point light used to
    # produce a single specular pin-prick on this large acrylic face.
    M["pylon"] = image_material("M_Sign_Pylon", "pylon_sign.png", roughness=0.68,
                                emission=True, emission_strength=1.55)
    M["open_neon"] = image_material("M_Neon_Open", "open_neon.png", roughness=0.3,
                                    emission=True, emission_strength=4.4, alpha=True)
    M["window_decal"] = image_material("M_Decal_Window", "window_decal.png", roughness=0.3,
                                       emission=True, emission_strength=1.6, alpha=True)
    M["poster_coffee"] = image_material("M_Poster_Coffee", "poster_coffee.png", roughness=0.6)
    M["poster_slurpee"] = image_material("M_Poster_Slurpee", "poster_slurpee.png", roughness=0.6)
    M["poster_food"] = image_material("M_Poster_Food", "poster_food.png", roughness=0.6)
    M["menu"] = image_material("M_Menu_Coffee", "menu_coffee.png", roughness=0.6)
    M["road_sign"] = image_material("M_Road_Sign", "road_sign.png", roughness=0.4,
                                    emission=True, emission_strength=0.15, alpha=True)
    M["a_frame"] = image_material("M_A_Frame", "a_frame.png", roughness=0.55)
    M["ice_label"] = image_material("M_Ice_Label", "ice_label.png", roughness=0.35,
                                    emission=True, emission_strength=0.6)
    M["fridge_header"] = image_material("M_Fridge_Header", "fridge_header.png", roughness=0.4,
                                        emission=True, emission_strength=1.2)
    for i in range(1, 4):
        M[f"aisle_{i}"] = image_material(f"M_Aisle_{i}", f"aisle_{i}.png", roughness=0.45,
                                         emission=True, emission_strength=0.35, alpha=True)
    M["logo"] = image_material("M_Logo_Wall", "logo_7eleven.png", roughness=0.5,
                                emission=True, emission_strength=0.55)
    M["slurpee_label"] = image_material("M_Slurpee_Label", "slurpee_machine_label.png",
                                        roughness=0.4, emission=True, emission_strength=1.7)
    M["condiment_sign"] = image_material("M_Condiment_Sign", "condiment_sign.png",
                                         roughness=0.45, emission=True, emission_strength=0.85)
    M["exit_sign"] = image_material("M_Exit_Sign", "exit_sign.png", roughness=0.35,
                                    emission=True, emission_strength=2.3)
    M["atm_sign"] = image_material("M_ATM_Sign", "atm_sign.png", roughness=0.35,
                                   emission=True, emission_strength=1.5)
    M["store_plaque"] = image_material("M_Store_Plaque", "store_plaque.png", roughness=0.5)
    M["promo_tag"] = image_material("M_Promo_Tag", "promo_tag.png", roughness=0.6,
                                    emission=True, emission_strength=0.25)
    M["icecream_label"] = image_material("M_IceCream_Label", "icecream_label.png",
                                         roughness=0.55, emission=True, emission_strength=0.35)
    M["product_pack"] = image_material("M_Product_Packaging", "product_packaging.png",
                                       roughness=0.48, metallic=0.02)
    M["hotfood_menu"] = image_material("M_HotFood_Menu", "hotfood_menu.png",
                                       roughness=0.5, emission=True, emission_strength=0.6)
    M["magazine_sign"] = image_material("M_Magazine_Sign", "magazine_sign.png",
                                        roughness=0.45, emission=True, emission_strength=0.45)
    M["newspaper_box"] = image_material("M_Newspaper_Box", "newspaper_box.png",
                                        roughness=0.5, emission=True, emission_strength=0.16)
    M["sidewalk_stain"] = image_material("M_Sidewalk_Stain", "sidewalk_stains.png",
                                         roughness=0.92, alpha=True)
    M["door_stickers"] = image_material("M_Door_Stickers", "door_stickers.png",
                                        roughness=0.5, alpha=True)
    M["bike_parking"] = image_material("M_Bike_Parking", "bike_parking.png",
                                       roughness=0.55, emission=True, emission_strength=0.22)
    M["payment_methods"] = image_material("M_Payment_Methods", "payment_methods.png",
                                          roughness=0.52, emission=True, emission_strength=0.1)
    M["shelf_tag"] = image_material("M_Shelf_Tag", "shelf_tags.png",
                                    roughness=0.58, emission=True, emission_strength=0.12)
    M["magazines"] = image_material("M_Magazines", "magazines.png", roughness=0.65,
                                    metallic=0.0)
    M["products_atlas"] = image_material("M_Product_Atlas", "product_atlas.png", roughness=0.55)
    M["sidewalk"] = image_material("M_Sidewalk", "sidewalk_tiles.png", roughness=0.8)
    M["store_floor"] = image_material("M_Store_Floor", "store_floor.png", roughness=0.36)
    M["store_tiles"] = image_material("M_Store_Tiles", "store_tiles.png", roughness=0.36)
    M["asphalt"] = image_material("M_Asphalt", "asphalt.png", roughness=0.88)
    M["concrete"] = image_material("M_Concrete_Wall", "concrete_wall.png", roughness=0.78)
    M["roof"] = image_material("M_Roof_Gravel", "roof_gravel.png", roughness=0.93)
    M["ceiling"] = image_material("M_Ceiling_Tile", "ceiling_tile.png", roughness=0.72)
    M["wall"] = image_material("M_Wall_White", "facade_panels.png", roughness=0.62)

    # Plain architecture -----------------------------------------------------
    plain = {
        "wall": ("M_Wall_White", "#e7e4da", 0.0, 0.52),
        "wall_warm": ("M_Wall_Warm", "#f1ead9", 0.0, 0.56),
        "wall_interior": ("M_Wall_Interior", "#f6f1e3", 0.0, 0.68),
        "wall_panel": ("M_Wall_Panel", "#d9d6cb", 0.0, 0.6),
        "trim_dark": ("M_Trim_Dark", "#202725", 0.5, 0.38),
        "trim_mid": ("M_Trim_Mid", "#444c47", 0.4, 0.46),
        "frame": ("M_Aluminium_Frame", "#b2b7b4", 0.75, 0.3),
        "frame_dark": ("M_Frame_Dark", "#3a4240", 0.65, 0.34),
        "chrome": ("M_Chrome", "#d4d9d7", 1.0, 0.17),
        "steel": ("M_Steel", "#7c8582", 0.8, 0.35),
        "steel_dark": ("M_Steel_Dark", "#414947", 0.7, 0.42),
        "orange": ("M_Accent_Orange", "#f5821f", 0.0, 0.45),
        "green": ("M_Accent_Green", "#008061", 0.0, 0.42),
        "red": ("M_Accent_Red", "#ed1b2d", 0.0, 0.43),
        "cream": ("M_Cream", "#f4efdf", 0.0, 0.55),
        "counter_top": ("M_Counter_Top", "#313b37", 0.2, 0.34),
        "black": ("M_Black", "#0c100e", 0.0, 0.55),
        "rubber": ("M_Rubber", "#171a19", 0.0, 0.92),
        "shelf": ("M_Shelf_White", "#d6d4c9", 0.15, 0.5),
        "shelf_green": ("M_Shelf_Green", "#17654f", 0.15, 0.5),
        "product_label": ("M_Product_Label", "#f2eddd", 0.0, 0.68),
        "product_cap": ("M_Product_Cap", "#bfc6c2", 0.4, 0.38),
        "fridge_inside": ("M_Fridge_Inside", "#dff5f6", 0.0, 0.78),
        "screen": ("M_Screen_Black", "#060a0a", 0.2, 0.16),
        "screen_glow": ("M_Screen_Glow", "#7be3d0", 0.0, 0.4),
        "foliage_a": ("M_Foliage_A", "#365c3c", 0.0, 0.8),
        "foliage_b": ("M_Foliage_B", "#4f764c", 0.0, 0.78),
        "foliage_c": ("M_Foliage_C", "#2b472f", 0.0, 0.82),
        "foliage_d": ("M_Foliage_D", "#3f5d39", 0.0, 0.86),
        "foliage_e": ("M_Foliage_E", "#687a46", 0.0, 0.82),
        "bark": ("M_Bark", "#4b3827", 0.0, 0.9),
        "paint": ("M_Road_Paint", "#dddccc", 0.0, 0.6),
        "paint_warm": ("M_Road_Paint_Warm", "#e1b45f", 0.0, 0.62),
        "glass": ("M_Glass_Store", "#9fbfba", 0.05, 0.07),
        "glass_fridge": ("M_Glass_Fridge", "#a9c5c2", 0.05, 0.05),
        "glass_dark": ("M_Glass_Dark", "#26332f", 0.1, 0.12),
        "lightbox": ("M_Lightbox_White", "#f5f2e5", 0.0, 0.4),
        "led": ("M_Interior_LED", "#fff4dc", 0.0, 0.35),
        "fridge_glow": ("M_Fridge_Glow", "#e8fbff", 0.0, 0.55),
        "warm_glow": ("M_Warm_Glow", "#ffc27b", 0.0, 0.4),
        "street_glow": ("M_Streetlight_Glow", "#dcefff", 0.0, 0.3),
        "neon_red": ("M_Neon_Red", "#ff4d3c", 0.0, 0.3),
        "ceramic": ("M_Ceramic_White", "#f4f1e7", 0.0, 0.28),
        "wood": ("M_Wood_Warm", "#7a5232", 0.0, 0.6),
        "metal_black": ("M_Metal_Black", "#171c1a", 0.8, 0.36),
        "bin_grey": ("M_Bin_Grey", "#5e6662", 0.2, 0.52),
        "concrete_plain": ("M_Concrete_Plain", "#bdbcb1", 0.0, 0.8),
        "scooter_cream": ("M_Scooter_Cream", "#e6ddc9", 0.1, 0.38),
        "scooter_red": ("M_Scooter_Red", "#a73b2e", 0.1, 0.4),
        "tactile": ("M_Tactile_Yellow", "#d7a637", 0.0, 0.7),
        "crate_blue": ("M_Crate_Blue", "#1c5f84", 0.0, 0.6),
        "crate_orange": ("M_Crate_Orange", "#c9582f", 0.0, 0.62),
        "shelf_led": ("M_Shelf_LED", "#fff1d2", 0.0, 0.3),
    }
    for key, (name, color, metal, rough) in plain.items():
        M[key] = _principled(name, color, metallic=metal, roughness=rough)
    # Transparent glass tweaks.
    for key in ("glass", "glass_fridge", "glass_dark"):
        mat = M[key]
        b = mat.node_tree.nodes.get("Principled BSDF")
        b.inputs["Alpha"].default_value = 0.16 if key == "glass" else (0.1 if key == "glass_fridge" else 0.55)
        try:
            mat.surface_render_method = "DITHERED"
        except Exception:
            pass
        try:
            mat.blend_method = "BLEND"
        except Exception:
            pass
        mat.use_transparent_shadow = True
        mat.diffuse_color = (0.52, 0.68, 0.66, 0.16)
        # A subtle clearcoat / specular highlight reads as glazing.
        b.inputs["Coat Weight"].default_value = 0.6
        b.inputs["Coat Roughness"].default_value = 0.08
    # Emissive surfaces.
    emis = {
        "led": ("#fff4dc", 7.5),
        "fridge_glow": ("#e8fbff", 5.0),
        "warm_glow": ("#ffc27b", 5.0),
        "street_glow": ("#e2f4ff", 9.0),
        "neon_red": ("#ff5a46", 9.0),
        "screen_glow": ("#6ee6d1", 2.2),
        "lightbox": ("#fff8e8", 0.2),
        "shelf_led": ("#fff1d2", 1.15),
    }
    for key, (color, strength) in emis.items():
        b = M[key].node_tree.nodes.get("Principled BSDF")
        b.inputs["Emission Color"].default_value = srgb(color)
        b.inputs["Emission Strength"].default_value = strength
    # Product palette. These are deliberately saturated, but with realistic
    # roughness so the interior reads as packaging rather than neon.
    prod_cols = ["#d94a45", "#eaa432", "#4d9fc5", "#4c9f6f", "#7d63a8",
                 "#e7834f", "#2b4a63", "#e6d9bb", "#c84262", "#9ebd4e",
                 "#5fb4a8", "#f0c84e", "#7b473f", "#c7ccc4", "#9b2e35", "#2f7d59"]
    for i, c in enumerate(prod_cols):
        M[f"prod_{i}"] = _principled(f"M_Product_{i:02d}", c, metallic=0.05,
                                     roughness=0.42 if i % 4 else 0.32)
    return M


# ---------------------------------------------------------------------------
# Scene helpers
# ---------------------------------------------------------------------------
def clean_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.length_unit = "METERS"
    scene.render.engine = "BLENDER_EEVEE"
    return scene


def add_empty(name, collection, location=(0, 0, 0)):
    e = bpy.data.objects.new(name, None)
    e.empty_display_size = 1.0
    e.empty_display_type = "PLAIN_AXES"
    collection.objects.link(e)
    e.location = location
    return e


def add_light_area(collection, name, loc, target, energy, color, size=4.0, shape="RECTANGLE"):
    data = bpy.data.lights.new(name, type="AREA")
    data.energy = energy
    data.color = srgb(color)[:3]
    data.shape = shape
    data.size = size
    obj = bpy.data.objects.new(name, data)
    collection.objects.link(obj)
    obj.location = loc
    obj.rotation_euler = (Vector(target) - obj.location).to_track_quat("-Z", "Y").to_euler()
    return obj


def add_light_point(collection, name, loc, energy, color, radius=0.2):
    data = bpy.data.lights.new(name, type="POINT")
    data.energy = energy
    data.color = srgb(color)[:3]
    data.shadow_soft_size = radius
    obj = bpy.data.objects.new(name, data)
    collection.objects.link(obj)
    obj.location = loc
    return obj


def add_light_spot(collection, name, loc, target, energy, color, size_deg=55, blend=0.5, radius=0.2):
    data = bpy.data.lights.new(name, type="SPOT")
    data.energy = energy
    data.color = srgb(color)[:3]
    data.spot_size = math.radians(size_deg)
    data.spot_blend = blend
    data.shadow_soft_size = radius
    obj = bpy.data.objects.new(name, data)
    collection.objects.link(obj)
    obj.location = loc
    obj.rotation_euler = (Vector(target) - obj.location).to_track_quat("-Z", "Y").to_euler()
    return obj


def add_light_sun(collection, name, direction_to_sun, energy, color, angle=1.0):
    data = bpy.data.lights.new(name, type="SUN")
    data.energy = energy
    data.color = srgb(color)[:3]
    data.angle = math.radians(angle)
    obj = bpy.data.objects.new(name, data)
    collection.objects.link(obj)
    direction = -Vector(direction_to_sun).normalized()
    obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    return obj


def add_camera(collection, name, loc, target, lens=50, resolution=(1920, 1080)):
    data = bpy.data.cameras.new(name)
    data.lens = lens
    data.sensor_width = 36
    data.clip_end = 2000
    obj = bpy.data.objects.new(name, data)
    collection.objects.link(obj)
    obj.location = loc
    obj.rotation_euler = (Vector(target) - obj.location).to_track_quat("-Z", "Y").to_euler()
    return obj


# ---------------------------------------------------------------------------
# Extra organic primitives
# ---------------------------------------------------------------------------
def sphere_geo(center, radius, seg_u=16, seg_v=10, scale=(1, 1, 1)):
    cx, cy, cz = center
    sx, sy, sz = scale
    verts = []
    # top pole
    verts.append((cx, cy, cz + radius * sz))
    for j in range(1, seg_v):
        phi = PI * j / seg_v
        z = math.cos(phi) * radius * sz
        r = math.sin(phi) * radius
        for i in range(seg_u):
            th = TAU * i / seg_u
            verts.append((cx + math.cos(th) * r * sx,
                          cy + math.sin(th) * r * sy,
                          cz + z))
    verts.append((cx, cy, cz - radius * sz))
    faces = []
    # top cap
    for i in range(seg_u):
        i2 = (i + 1) % seg_u
        faces.append([0, 1 + i, 1 + i2])
    # bands
    for j in range(seg_v - 2):
        a = 1 + j * seg_u
        b = 1 + (j + 1) * seg_u
        for i in range(seg_u):
            i2 = (i + 1) % seg_u
            faces.append([a + i, b + i, b + i2, a + i2])
    last = len(verts) - 1
    a = 1 + (seg_v - 2) * seg_u
    for i in range(seg_u):
        i2 = (i + 1) % seg_u
        faces.append([a + i, last, a + i2])
    return verts, faces


def add_sphere(b, center, radius, seg_u=16, seg_v=10, scale=(1, 1, 1)):
    verts, faces = sphere_geo(center, radius, seg_u, seg_v, scale)
    b.add(verts, faces, smooth=True)
