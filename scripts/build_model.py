#!/usr/bin/env python3
"""Build the 7-Eleven corner store model procedurally in Blender.

Run:
    /Applications/Blender.app/Contents/MacOS/Blender -b --factory-startup \
        --python scripts/build_model.py

Outputs:
    build/seven_eleven_store_asset.blend  (clean model, no lights/camera)
    seven_eleven_store.blend              (lit night scene with camera)
    seven_eleven_store.glb                (portable glTF model)
"""
from __future__ import annotations

import math
import os
import random
import sys
from pathlib import Path

import bpy
from mathutils import Vector

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import store_lib as L
from store_lib import PI, TAU

# Core dimensions -----------------------------------------------------------
HALF_W = 6.6
FRONT_Y = -4.8
BACK_Y = 4.8
FLOOR_Z = 0.20
CEIL_Z = 3.55
ROOF_Z = 4.70
SIDEWALK_Z = 0.15

LEFT_WIN = (-6.30, -1.30)
RIGHT_WIN = (2.10, 6.30)
DOOR = (-0.90, 1.70)
PIER_L = (-1.30, -0.90)
PIER_R = (1.70, 2.10)
GLASS_BOTTOM = 0.58
GLASS_TOP = 3.28
SIGN_BOTTOM = 3.62
SIGN_TOP = 4.46


AUTO_UV = {"wall": 2.4, "wall_panel": 2.4, "concrete": 2.5, "sidewalk": 2.4,
           "roof": 3.0, "store_floor": 2.4, "ceiling": 2.4, "asphalt": 5.2}

def box(ctx, M, group, mat, name, center, size, rot=0.0, uv_scale=None):
    if uv_scale is None:
        uv_scale = AUTO_UV.get(mat)
    b = ctx.b(group, M[mat], name, uv=uv_scale is not None)
    L.add_box(b, center, size, rot=rot, uv_scale=uv_scale)
    return b


def cyl(ctx, M, group, mat, name, p0, p1, r0, r1=None, seg=12, caps=True):
    b = ctx.b(group, M[mat], name)
    L.add_cyl(b, p0, p1, r0, r1, seg=seg, caps=caps)
    return b


def plane(ctx, M, group, mat, name, center, w, h, facing="-Y"):
    b = ctx.b(group, M[mat], name, uv=True)
    L.add_plane(b, center, w, h, facing=facing, uv=True)
    return b


def rod(ctx, M, group, mat, name, p0, p1, r=0.02, seg=6):
    return cyl(ctx, M, group, mat, name, p0, p1, r, r, seg=seg, caps=False)


# Atlas UV helpers -----------------------------------------------------------
PACK_COLS = 8
PACK_ROWS = 8
TAG_COLS = 8
TAG_ROWS = 4
MAG_COLS = 8
MAG_ROWS = 8


def pack_uv(index, pad=0.006):
    index %= PACK_COLS * PACK_ROWS
    col = index % PACK_COLS
    row = index // PACK_COLS
    u0 = col / PACK_COLS + pad
    u1 = (col + 1) / PACK_COLS - pad
    v0 = 1 - (row + 1) / PACK_ROWS + pad
    v1 = 1 - row / PACK_ROWS - pad
    return (u0, v0, u1, v1)


def tag_uv(index, pad=0.005):
    index %= TAG_COLS * TAG_ROWS
    col = index % TAG_COLS
    row = index // TAG_COLS
    u0 = col / TAG_COLS + pad
    u1 = (col + 1) / TAG_COLS - pad
    v0 = 1 - (row + 1) / TAG_ROWS + pad
    v1 = 1 - row / TAG_ROWS - pad
    return (u0, v0, u1, v1)


def mag_uv(index, pad=0.004):
    index %= MAG_COLS * MAG_ROWS
    col = index % MAG_COLS
    row = index // MAG_COLS
    u0 = col / MAG_COLS + pad
    u1 = (col + 1) / MAG_COLS - pad
    v0 = 1 - (row + 1) / MAG_ROWS + pad
    v1 = 1 - row / MAG_ROWS - pad
    return (u0, v0, u1, v1)


def add_pack(ctx, M, group, center, size, index, rot=0.0):
    b = ctx.b(group, M["product_pack"], "Textured_Products", uv=True)
    L.add_box_uvrect(b, center, size, pack_uv(index), rot=rot)


def add_price_tag(ctx, M, group, center, width, height, index):
    b = ctx.b(group, M["shelf_tag"], "Shelf_Price_Tags", uv=True)
    x, y, z = center
    hw, hh = width / 2, height / 2
    corners = [(x - hw, y, z - hh), (x + hw, y, z - hh),
               (x + hw, y, z + hh), (x - hw, y, z + hh)]
    L.add_quad_uvrect(b, corners, tag_uv(index))
    # A small black rail clip makes the paper tag read as a physical object.
    clip = ctx.b(group, M["trim_dark"], "Shelf_Tag_Clips", uv=False)
    L.add_box(clip, (x, y - 0.002, z + hh - 0.005), (width * 0.5, 0.008, 0.012))


def add_magazine(ctx, M, group, center, width, height, index):
    b = ctx.b(group, M["magazines"], "Magazine_Covers", uv=True)
    x, y, z = center
    hw, hh = width / 2, height / 2
    corners = [(x - hw, y, z - hh), (x + hw, y, z - hh),
               (x + hw, y, z + hh), (x - hw, y, z + hh)]
    L.add_quad_uvrect(b, corners, mag_uv(index))


# ---------------------------------------------------------------------------
# Site
# ---------------------------------------------------------------------------
def build_site(ctx, M):
    g = "00_Site"
    # Expansive asphalt road. The viewer extends the city beyond this apron.
    box(ctx, M, g, "asphalt", "Road", (0, -25.5, -0.06), (74, 34, 0.12),
        uv_scale=5.2)
    # Sidewalk apron and wrapping walkways.
    box(ctx, M, g, "sidewalk", "Sidewalk_Front", (0, -7.35, 0.075), (38, 5.1, 0.15),
        uv_scale=2.4)
    box(ctx, M, g, "sidewalk", "Sidewalk_Left", (-9.6, 0.1, 0.075), (6.0, 10.0, 0.15),
        uv_scale=2.4)
    box(ctx, M, g, "sidewalk", "Sidewalk_Right", (9.6, 0.1, 0.075), (6.0, 10.0, 0.15),
        uv_scale=2.4)
    box(ctx, M, g, "sidewalk", "Sidewalk_Back", (0, 8.4, 0.075), (38, 7.2, 0.15),
        uv_scale=2.4)
    # Curb and gutter.
    box(ctx, M, g, "concrete", "Curb", (0, -9.94, 0.095), (38, 0.28, 0.19),
        uv_scale=2.5)
    box(ctx, M, g, "concrete_plain", "Curb_Top", (0, -9.94, 0.196), (38, 0.34, 0.025))
    box(ctx, M, g, "trim_mid", "Gutter", (0, -10.16, 0.015), (38, 0.18, 0.025))
    # Red no-parking curb line, characteristic of Taipei streets.
    box(ctx, M, g, "red", "Curb_Paint", (0, -9.815, 0.202), (38, 0.05, 0.009))
    # Lane dashes.
    for i in range(-11, 12):
        x = i * 5.2
        box(ctx, M, g, "paint", "Lane_Dash", (x, -18.4, 0.002), (3.0, 0.13, 0.008))
    box(ctx, M, g, "paint", "Edge_Line", (0, -11.0, 0.002), (74, 0.11, 0.008))
    # Crosswalk at left foreground (bars perpendicular to pedestrian travel).
    for i in range(10):
        y = -10.7 - i * 0.82
        box(ctx, M, g, "paint", "Crosswalk_Bar", (-16.0, y, 0.004), (3.6, 0.43, 0.008))
    # Stop bar near crosswalk.
    box(ctx, M, g, "paint", "Stop_Bar", (-12.7, -12.3, 0.004), (0.42, 5.2, 0.008))
    # Drain near curb.
    box(ctx, M, g, "steel_dark", "Storm_Drain", (-4.6, -9.86, 0.202), (0.72, 0.28, 0.012))
    for i in range(7):
        box(ctx, M, g, "black", "Drain_Slot", (-4.92 + i * 0.105, -9.86, 0.210),
            (0.035, 0.22, 0.004))
    # Manhole cover.
    cyl(ctx, M, g, "steel_dark", "Manhole", (-2.0, -13.6, 0.004), (-2.0, -13.6, 0.012),
        0.42, seg=28)
    cyl(ctx, M, g, "trim_mid", "Manhole_Inner", (-2.0, -13.6, 0.005), (-2.0, -13.6, 0.014),
        0.35, seg=28)
    # Tactile paving strip near the crossing.
    for i in range(18):
        box(ctx, M, g, "paint_warm", "Tactile", (-17.55 + i * 0.18, -9.53, 0.202),
            (0.11, 0.24, 0.008))
    # Small painted curb number.
    box(ctx, M, g, "trim_dark", "Curb_Shadow", (0, -10.04, 0.03), (38, 0.02, 0.06))


def add_streetlight(ctx, M):
    g = "00_Site"
    x, y = -9.35, -9.15
    cyl(ctx, M, g, "steel_dark", "Streetlight_Base", (x, y, 0.12), (x, y, 0.65),
        0.17, 0.13, seg=14)
    cyl(ctx, M, g, "steel_dark", "Streetlight_Pole", (x, y, 0.62), (x, y, 6.55),
        0.085, 0.06, seg=12)
    # Slightly curved arm reaching over the road.
    L.add_tube(ctx.b(g, M["steel_dark"], "Streetlight_Arm"),
               [(x, y, 6.55), (x, y - 0.9, 6.96), (x, y - 2.0, 7.08),
                (x, y - 3.05, 6.98)], 0.055, seg=8)
    # Lamp head.
    box(ctx, M, g, "steel_dark", "Lamp_Head", (x, y - 3.35, 6.88), (0.36, 0.82, 0.14))
    box(ctx, M, g, "metal_black", "Lamp_Rim", (x, y - 3.35, 6.80), (0.31, 0.74, 0.035))
    plane(ctx, M, g, "street_glow", "Lamp_Lens", (x, y - 3.35, 6.775), 0.27, 0.68,
          facing="-Z")
    # Small service access panel.
    box(ctx, M, g, "trim_mid", "Streetlight_Access", (x + 0.091, y, 1.05),
        (0.015, 0.13, 0.35))
    # Road name blade attached to the pole.
    plane(ctx, M, g, "road_sign", "Road_Sign_Front", (x + 0.02, y + 0.02, 4.2),
          1.5, 0.47, facing="-Y")
    box(ctx, M, g, "trim_dark", "Road_Sign_Back", (x + 0.02, y + 0.055, 4.2),
        (1.55, 0.04, 0.52))
    return x, y


def add_utility_pole(ctx, M):
    g = "00_Site"
    x, y = 12.7, -9.0
    cyl(ctx, M, g, "concrete_plain", "Utility_Pole", (x, y, 0.14), (x, y, 8.6),
        0.14, 0.1, seg=12, caps=True)
    # Footing.
    cyl(ctx, M, g, "trim_mid", "Utility_Footing", (x, y, 0.14), (x, y, 0.32),
        0.24, 0.24, seg=14)
    # Crossarms and insulators.
    box(ctx, M, g, "steel_dark", "Utility_Crossarm", (x, y, 7.55), (2.2, 0.11, 0.11))
    for sx in (-0.85, -0.4, 0.4, 0.85):
        cyl(ctx, M, g, "ceramic", "Insulator", (x + sx, y, 7.61), (x + sx, y, 7.82),
            0.045, 0.035, seg=8)
    # Transformer drums.
    for dx in (-0.42, 0.38):
        cyl(ctx, M, g, "steel", "Transformer", (x + dx, y - 0.22, 6.35),
            (x + dx, y - 0.22, 7.12), 0.25, 0.25, seg=14)
        cyl(ctx, M, g, "trim_dark", "Transformer_Ring", (x + dx, y - 0.22, 6.45),
            (x + dx, y - 0.22, 6.53), 0.27, 0.27, seg=14)
    # Overhead lines, sagging across the street.
    for k, dz in enumerate((0.0, -0.22, -0.44)):
        pts_a = [(x + 0.85, y, 7.8 + dz)]
        for t in (0.25, 0.5, 0.75):
            xx = x + 0.85 - t * 32
            pts_a.append((xx, y + 0.2 * math.sin(t * PI), 7.8 + dz - 0.65 * math.sin(t * PI)))
        pts_a.append((x - 31.2, y, 7.8 + dz))
        L.add_tube(ctx.b(g, M["black"], f"PowerLine_{k}"), pts_a, 0.014, seg=4)
    for dz in (0.0, -0.2):
        pts_b = [(x + 0.4, y, 7.55 + dz), (x + 8.0, y + 1.2, 7.25 + dz),
                 (x + 18.0, y + 0.2, 7.35 + dz)]
        L.add_tube(ctx.b(g, M["black"], f"PowerLine_Right_{dz}"), pts_b, 0.012, seg=4)
    # Service drop to the store roof.
    L.add_tube(ctx.b(g, M["black"], "Service_Drop"),
               [(x, y, 7.4), (10.2, -7.2, 6.9), (7.2, -4.8, 5.9)], 0.012, seg=4)


def add_tree(ctx, M, x, y, scale=1.0, seed=1):
    g = "00_Site"
    rng = random.Random(seed)
    base = L.Vector((x, y, SIDEWALK_Z)) if hasattr(L, "Vector") else Vector((x, y, SIDEWALK_Z))
    trunk_b = ctx.b(g, M["bark"], "Tree_Trunk")
    cyl(ctx, M, g, "bark", "Tree_Trunk", (x, y, 0.15), (x, y, 3.5 * scale),
        0.23 * scale, 0.13 * scale, seg=10)
    # Planter grate.
    box(ctx, M, g, "trim_mid", "Tree_Grate", (x, y, 0.158), (1.3, 1.3, 0.018))
    box(ctx, M, g, "black", "Tree_Grate_Hole", (x, y, 0.169), (0.7, 0.7, 0.012))
    # Branches.
    for k in range(5):
        a = k / 5 * TAU + 0.4
        p0 = (x, y, 2.2 * scale)
        p1 = (x + math.cos(a) * 0.9 * scale, y + math.sin(a) * 0.9 * scale,
              3.3 * scale + rng.uniform(-0.2, 0.3))
        L.add_tube(trunk_b, [p0, p1], 0.08 * scale, seg=6)
    # Foliage clouds.
    leaf_mats = ["foliage_a", "foliage_b", "foliage_c", "foliage_d", "foliage_e"]
    for k in range(26):
        a = rng.uniform(0, TAU)
        rad = rng.uniform(0.12, 1.65) * scale
        z = (3.85 + rng.uniform(-0.55, 1.15)) * scale
        r = rng.uniform(0.42, 1.08) * scale
        b = ctx.b(g, M[leaf_mats[k % len(leaf_mats)]], f"Tree_Leaves_{k % len(leaf_mats)}")
        L.add_sphere(b, (x + math.cos(a) * rad, y + math.sin(a) * rad, z), r,
                     seg_u=9, seg_v=6, scale=(1.18, 1.06, 0.68))
    # A couple of branches poking through the canopy.
    for k in range(3):
        a = 1.1 + k * 2.1
        L.add_tube(trunk_b, [(x, y, 3.0 * scale),
                             (x + math.cos(a) * 1.45 * scale,
                              y + math.sin(a) * 1.45 * scale, 4.9 * scale)],
                   0.035 * scale, seg=5)


def add_scooter(ctx, M, x0=7.8, y0=-5.9):
    """A parked delivery scooter, axis along +X."""
    g = "05_Props"
    body_y = y0
    # Wheels (torus normal +-Y, so axis Y).
    for wx, front in ((x0 - 0.68, False), (x0 + 0.68, True)):
        b = ctx.b(g, M["rubber"], "Scooter_Tires")
        L.add_torus(b, (wx, body_y, 0.41), 0.255, 0.062, axis="Y", seg_major=22, seg_minor=7)
        b2 = ctx.b(g, M["chrome"], "Scooter_Rims")
        L.add_torus(b2, (wx, body_y, 0.41), 0.15, 0.018, axis="Y", seg_major=18, seg_minor=5)
        L.add_cyl(b2, (wx, body_y - 0.028, 0.41), (wx, body_y + 0.028, 0.41),
                  0.055, seg=12)
        # Fender arc (simple bent strip made from short boxes).
        for k in range(5):
            a = math.radians(35 + k * 22)
            fx = wx + math.cos(a) * 0.28 * (1 if front else -1)
            fz = 0.41 + math.sin(a) * 0.28
            box(ctx, M, g, "scooter_cream", "Scooter_Fender",
                (fx, body_y, fz), (0.13, 0.2, 0.045), rot=0.0)
    # Floorboard and underbody.
    box(ctx, M, g, "scooter_cream", "Scooter_Floorboard", (x0, body_y, 0.44),
        (0.9, 0.34, 0.14))
    box(ctx, M, g, "metal_black", "Scooter_Underbody", (x0, body_y, 0.34),
        (0.72, 0.26, 0.08))
    # Rear body and seat.
    box(ctx, M, g, "scooter_cream", "Scooter_RearBody", (x0 - 0.36, body_y, 0.61),
        (0.72, 0.38, 0.36))
    box(ctx, M, g, "metal_black", "Scooter_Seat", (x0 - 0.39, body_y, 0.84),
        (0.62, 0.35, 0.14))
    box(ctx, M, g, "scooter_red", "Scooter_SeatStripe", (x0 - 0.39, body_y, 0.915),
        (0.42, 0.30, 0.018))
    # Front shield / leg shield, with a cream face.
    box(ctx, M, g, "scooter_cream", "Scooter_FrontShield", (x0 + 0.46, body_y, 0.78),
        (0.19, 0.39, 0.7), rot=0.0)
    box(ctx, M, g, "scooter_red", "Scooter_Strip", (x0 + 0.565, body_y, 0.75),
        (0.018, 0.3, 0.26))
    # Handlebar post and bars.
    cyl(ctx, M, g, "metal_black", "Scooter_Stem", (x0 + 0.51, body_y, 1.11),
        (x0 + 0.48, body_y, 1.35), 0.04, seg=8)
    cyl(ctx, M, g, "chrome", "Scooter_Handlebar", (x0 + 0.48, body_y - 0.32, 1.36),
        (x0 + 0.48, body_y + 0.32, 1.36), 0.025, seg=8)
    for sy in (-0.31, 0.31):
        box(ctx, M, g, "rubber", "Scooter_Grip", (x0 + 0.48, body_y + sy, 1.36),
            (0.11, 0.1, 0.07))
        # Mirror stalk and mirror.
        cyl(ctx, M, g, "chrome", "Mirror_Stalk", (x0 + 0.48, body_y + sy, 1.38),
            (x0 + 0.42, body_y + sy * 1.22, 1.64), 0.012, seg=6)
        L.add_sphere(ctx.b(g, M["metal_black"], "Scooter_Mirror"),
                     (x0 + 0.41, body_y + sy * 1.24, 1.66), 0.07, 10, 6,
                     scale=(0.5, 1.2, 0.8))
    # Headlamp, tail lamp, plate.
    L.add_sphere(ctx.b(g, M["warm_glow"], "Scooter_Headlamp"),
                 (x0 + 0.57, body_y, 1.02), 0.09, 12, 8, scale=(0.55, 1, 0.72))
    box(ctx, M, g, "red", "Scooter_Taillight", (x0 - 0.72, body_y, 0.72),
        (0.035, 0.2, 0.09))
    box(ctx, M, g, "ceramic", "Scooter_Plate", (x0 - 0.77, body_y, 0.53),
        (0.02, 0.23, 0.12))
    # Kickstand and exhaust.
    cyl(ctx, M, g, "metal_black", "Scooter_Kickstand", (x0 - 0.15, body_y + 0.1, 0.3),
        (x0 - 0.3, body_y + 0.28, 0.15), 0.018, seg=5)
    cyl(ctx, M, g, "chrome", "Scooter_Exhaust", (x0 - 0.25, body_y + 0.2, 0.32),
        (x0 - 0.6, body_y + 0.23, 0.36), 0.05, 0.06, seg=8)
    # Delivery box at the rear.
    box(ctx, M, g, "scooter_red", "Delivery_Box", (x0 - 0.67, body_y, 1.07),
        (0.45, 0.42, 0.4))
    box(ctx, M, g, "cream", "Delivery_Box_Top", (x0 - 0.67, body_y, 1.285),
        (0.47, 0.44, 0.03))
    box(ctx, M, g, "cream", "Delivery_Box_Label", (x0 - 0.895, body_y, 1.08),
        (0.01, 0.23, 0.13))


def add_street_props(ctx, M):
    g = "05_Props"
    # A-frame sidewalk sign.
    ax, ay = -2.35, -6.15
    # Two leaning boards, hinge at the top.
    front = [(ax - 0.38, ay - 0.16, 0.16), (ax + 0.38, ay - 0.16, 0.16),
             (ax + 0.38, ay + 0.08, 1.05), (ax - 0.38, ay + 0.08, 1.05)]
    plane_data = ctx.b(g, M["a_frame"], "AFrame_Front", uv=True)
    plane_data.add(front, [[0, 1, 2, 3]], [[(0, 0), (1, 0), (1, 1), (0, 1)]])
    back = [(ax + 0.38, ay - 0.08, 0.16), (ax - 0.38, ay - 0.08, 0.16),
            (ax - 0.38, ay + 0.16, 1.05), (ax + 0.38, ay + 0.16, 1.05)]
    b = ctx.b(g, M["trim_dark"], "AFrame_Back", uv=False)
    b.add(back, [[0, 1, 2, 3]])
    # Side frame tubes.
    for sx in (-0.38, 0.38):
        L.add_tube(ctx.b(g, M["steel"], "AFrame_Frame"),
                   [(ax + sx, ay - 0.16, 0.16), (ax + sx, ay - 0.16, 0.05),
                    (ax + sx, ay + 0.14, 1.05)], 0.012, seg=5)
    box(ctx, M, g, "steel", "AFrame_Hinge", (ax, ay + 0.02, 1.05), (0.8, 0.04, 0.04))
    # Ice merchandiser to the left of the shop.
    ix, iy = -7.7, -5.55
    box(ctx, M, g, "ceramic", "Ice_Box", (ix, iy, 0.65), (1.25, 0.82, 0.95))
    box(ctx, M, g, "glass_dark", "Ice_Lid", (ix, iy, 1.14), (1.18, 0.76, 0.06))
    box(ctx, M, g, "chrome", "Ice_Handle", (ix + 0.43, iy - 0.41, 1.16),
        (0.26, 0.035, 0.035))
    plane(ctx, M, g, "ice_label", "Ice_Label", (ix, iy - 0.417, 0.72), 0.78, 0.29,
          facing="-Y")
    box(ctx, M, g, "street_glow", "Ice_CoolStrip", (ix, iy - 0.418, 1.075),
        (0.96, 0.012, 0.018))
    box(ctx, M, g, "trim_dark", "Ice_Foot", (ix, iy, 0.17), (1.08, 0.7, 0.06))
    # Twin recycling bins.
    bx, by = 6.72, -5.25
    box(ctx, M, g, "bin_grey", "Bins", (bx, by, 0.52), (0.72, 0.56, 0.82))
    for dx in (-0.18, 0.18):
        box(ctx, M, g, "trim_dark", "Bin_Lid", (bx + dx, by, 0.95), (0.33, 0.5, 0.05))
    box(ctx, M, g, "green", "Bin_Label_A", (bx - 0.18, by - 0.286, 0.66),
        (0.23, 0.012, 0.16))
    box(ctx, M, g, "orange", "Bin_Label_B", (bx + 0.18, by - 0.286, 0.66),
        (0.23, 0.012, 0.16))
    # Planters at the shop corners.
    for px, seed in ((-7.0, 3), (7.1, 8)):
        box(ctx, M, g, "concrete", "Planter", (px, -5.0, 0.34), (0.78, 0.78, 0.5),
            uv_scale=2.0)
        box(ctx, M, g, "trim_dark", "Planter_Rim", (px, -5.0, 0.59), (0.82, 0.82, 0.045))
        rng = random.Random(seed)
        for k in range(5):
            mat = ("foliage_a", "foliage_b", "foliage_c", "foliage_d", "foliage_e")[k % 5]
            L.add_sphere(ctx.b(g, M[mat], "Planter_Shrub"),
                         (px + rng.uniform(-0.18, 0.18), -5.0 + rng.uniform(-0.18, 0.18),
                          0.72 + rng.uniform(0, 0.18)),
                         rng.uniform(0.2, 0.3), 9, 6, scale=(1.1, 1.1, 0.65))
    # Store umbrella stand just inside the doorway.
    ux, uy = 1.36, -4.22
    cyl(ctx, M, g, "metal_black", "Umbrella_Stand", (ux, uy, FLOOR_Z + 0.01),
        (ux, uy, FLOOR_Z + 0.42), 0.16, 0.14, seg=14)
    for k, col in enumerate(("green", "red", "orange", "trim_dark")):
        px = ux - 0.08 + (k % 2) * 0.14
        py = uy - 0.05 + (k // 2) * 0.1
        cyl(ctx, M, g, col, "Umbrella_Shaft", (px, py, FLOOR_Z + 0.1),
            (px + 0.02, py, FLOOR_Z + 0.85), 0.025, 0.02, seg=6)
        # Tapered folded canopy.
        cyl(ctx, M, g, col, "Umbrella_Canopy", (px, py, FLOOR_Z + 0.35),
            (px + 0.02, py, FLOOR_Z + 0.82), 0.055, 0.012, seg=7)


# ---------------------------------------------------------------------------
# Building shell and facade
# ---------------------------------------------------------------------------
def add_door_leaf(ctx, M, label, x0, x1, handle_x):
    """Build one complete sliding door leaf as a named, movable assembly.

    The two leaves are parented to empty nodes after the build so the glTF
    viewer can slide the complete glass/frame/handle group automatically.
    """
    g = "01_Shell"
    cx = (x0 + x1) / 2.0
    prefix = f"DoorLeaf{label}"
    box(ctx, M, g, "frame_dark", f"{prefix}_Top", (cx, FRONT_Y - 0.03, 3.16),
        (x1 - x0, 0.09, 0.1))
    box(ctx, M, g, "frame_dark", f"{prefix}_Bottom", (cx, FRONT_Y - 0.03, 0.31),
        (x1 - x0, 0.09, 0.12))
    for xx, side_name in ((x0 + 0.03, "Outer"), (x1 - 0.03, "Inner")):
        box(ctx, M, g, "frame_dark", f"{prefix}_{side_name}Stile",
            (xx, FRONT_Y - 0.03, 1.73), (0.06, 0.09, 2.92))
    plane(ctx, M, g, "glass", f"{prefix}_Glass",
          (cx, FRONT_Y + 0.07, 1.73), x1 - x0 - 0.11, 2.77, facing="-Y")
    box(ctx, M, g, "chrome", f"{prefix}_Handle",
        (handle_x, FRONT_Y - 0.085, 1.31), (0.032, 0.05, 0.86))
    for zz in (0.90, 1.72):
        cyl(ctx, M, g, "chrome", f"{prefix}_HandleMount",
            (handle_x, FRONT_Y - 0.08, zz), (handle_x, FRONT_Y - 0.035, zz), 0.018, seg=6)
    # Bottom brush seal.
    box(ctx, M, g, "rubber", f"{prefix}_Seal",
        (cx, FRONT_Y - 0.005, 0.255), (x1 - x0 - 0.12, 0.02, 0.035))


def build_shell(ctx, M):
    g = "01_Shell"
    # Base / floor structure.
    box(ctx, M, g, "concrete", "Foundation", (0, 0, 0.09), (13.6, 9.9, 0.18),
        uv_scale=2.5)
    # Dark plinth around the solid sides only; the shopfront has its own sill.
    box(ctx, M, g, "trim_dark", "Base_Skirting_L", (-6.55, 0, 0.23), (0.1, 9.7, 0.16))
    box(ctx, M, g, "trim_dark", "Base_Skirting_R", (6.55, 0, 0.23), (0.1, 9.7, 0.16))
    box(ctx, M, g, "trim_dark", "Base_Skirting_B", (0, 4.68, 0.23), (13.2, 0.1, 0.16))
    # Side and back walls.
    box(ctx, M, g, "wall", "Wall_Left", (-6.45, 0, FLOOR_Z + 2.25), (0.3, 9.6, 4.5))
    box(ctx, M, g, "wall", "Wall_Right", (6.45, 0, FLOOR_Z + 2.25), (0.3, 9.6, 4.5))
    box(ctx, M, g, "wall", "Wall_Back", (0, 4.65, FLOOR_Z + 2.25), (13.2, 0.3, 4.5))
    # Front header / structural band above the glazing.
    box(ctx, M, g, "wall", "Facade_Header", (0, FRONT_Y + 0.15, 4.09), (13.2, 0.3, 1.25))
    box(ctx, M, g, "trim_mid", "Facade_Header_Trim", (0, FRONT_Y - 0.015, 3.44),
        (13.24, 0.08, 0.12))
    # Piers.
    for name, x0, x1 in (("Border_L", -6.6, -6.3), ("Pier_A", -1.3, -0.9),
                         ("Pier_B", 1.7, 2.1), ("Border_R", 6.3, 6.6)):
        w = x1 - x0
        box(ctx, M, g, "wall", f"Pier_{name}", ((x0 + x1) / 2, FRONT_Y + 0.15, 2.34),
            (w, 0.3, 4.28))
    # Low spandrel beneath each shop window.
    for i, (x0, x1) in enumerate((LEFT_WIN, RIGHT_WIN)):
        box(ctx, M, g, "trim_dark", f"Window_Base_{i}", ((x0 + x1) / 2, FRONT_Y + 0.1, 0.365),
            (x1 - x0, 0.22, 0.43))
        box(ctx, M, g, "wall_panel", f"Window_Sill_{i}", ((x0 + x1) / 2, FRONT_Y - 0.01, 0.575),
            (x1 - x0 + 0.1, 0.16, 0.08))
    # Door threshold and transom.
    box(ctx, M, g, "chrome", "Door_Threshold", ((DOOR[0] + DOOR[1]) / 2, FRONT_Y + 0.02, FLOOR_Z + 0.01),
        (DOOR[1] - DOOR[0], 0.22, 0.035))
    box(ctx, M, g, "trim_dark", "Door_Header", ((DOOR[0] + DOOR[1]) / 2, FRONT_Y + 0.02, 3.32),
        (DOOR[1] - DOOR[0] + 0.12, 0.2, 0.16))
    # Window framing.
    for i, (x0, x1) in enumerate((LEFT_WIN, RIGHT_WIN)):
        # Bottom sill + top header rails.
        box(ctx, M, g, "frame", f"Win_Sill_{i}", ((x0 + x1) / 2, FRONT_Y - 0.035, 0.625),
            (x1 - x0 + 0.05, 0.09, 0.07))
        box(ctx, M, g, "frame", f"Win_Head_{i}", ((x0 + x1) / 2, FRONT_Y - 0.035, 3.255),
            (x1 - x0 + 0.05, 0.09, 0.08))
        # Jambs.
        box(ctx, M, g, "frame", f"Win_JambL_{i}", (x0 + 0.025, FRONT_Y - 0.035, 1.94),
            (0.07, 0.09, 2.68))
        box(ctx, M, g, "frame", f"Win_JambR_{i}", (x1 - 0.025, FRONT_Y - 0.035, 1.94),
            (0.07, 0.09, 2.68))
        # Mullions.
        n = max(1, int(round((x1 - x0) / 1.45)) - 1)
        for k in range(1, n + 1):
            xx = x0 + (x1 - x0) * k / (n + 1)
            box(ctx, M, g, "frame", f"Win_Mullion_{i}_{k}", (xx, FRONT_Y - 0.035, 1.94),
                (0.055, 0.08, 2.62))
        # Glazing (single transparent plane per bay).
        plane(ctx, M, g, "glass", f"Window_Glass_{i}", ((x0 + x1) / 2, FRONT_Y + 0.08, 1.94),
              x1 - x0 - 0.06, 2.61, facing="-Y")
    # Entrance sliding doors: two complete, movable leaves.
    door_cx = (DOOR[0] + DOOR[1]) / 2
    add_door_leaf(ctx, M, "L", -0.90, 0.36, 0.25)
    add_door_leaf(ctx, M, "R", 0.44, 1.70, 0.55)
    # Threshold sensor and little green occupancy LED.
    box(ctx, M, g, "black", "Door_Sensor", (door_cx, FRONT_Y - 0.06, 3.23),
        (0.24, 0.07, 0.08))
    box(ctx, M, g, "screen_glow", "Door_Sensor_LED", (door_cx + 0.075, FRONT_Y - 0.098, 3.235),
        (0.018, 0.008, 0.018))
    # Canopy.
    cx0, cx1 = -1.45, 2.25
    box(ctx, M, g, "lightbox", "Canopy", ((cx0 + cx1) / 2, -5.37, 3.51),
        (cx1 - cx0, 1.35, 0.18))
    box(ctx, M, g, "trim_dark", "Canopy_Under", ((cx0 + cx1) / 2, -5.37, 3.412),
        (cx1 - cx0 - 0.1, 1.22, 0.03))
    box(ctx, M, g, "trim_mid", "Canopy_Edge", ((cx0 + cx1) / 2, -6.045, 3.51),
        (cx1 - cx0, 0.05, 0.2))
    for ix in (-1.0, 0.4, 1.8):
        cyl(ctx, M, g, "warm_glow", "Canopy_Downlight", (ix, -5.45, 3.405),
            (ix, -5.45, 3.39), 0.065, seg=12)
        cyl(ctx, M, g, "chrome", "Canopy_Downlight_Rim", (ix, -5.45, 3.412),
            (ix, -5.45, 3.404), 0.08, seg=12)
    # Security camera under the canopy, pointed at the door.
    cyl(ctx, M, g, "ceramic", "Camera_Bracket", (2.04, -5.42, 3.39), (2.04, -5.42, 3.28),
        0.025, seg=6)
    box(ctx, M, g, "ceramic", "Camera_Body", (2.02, -5.48, 3.24), (0.11, 0.2, 0.1))
    plane(ctx, M, g, "glass_dark", "Camera_Lens", (2.02, -5.585, 3.24), 0.06, 0.06,
          facing="-Y")
    # Small façade light bar under the sign for a wash of light.
    box(ctx, M, g, "chrome", "Cove_Light_Housing", (0, FRONT_Y - 0.08, 3.535),
        (12.8, 0.08, 0.045))
    box(ctx, M, g, "warm_glow", "Cove_Light", (0, FRONT_Y - 0.121, 3.53),
        (12.6, 0.01, 0.022))
    # Roof slab and parapet.
    box(ctx, M, g, "roof", "Roof_Slab", (0, 0, 4.73), (13.2, 9.6, 0.18),
        uv_scale=3.0)
    parapet = [
        ((0, FRONT_Y + 0.03, 4.84), (13.2, 0.14, 0.34)),
        ((0, BACK_Y - 0.03, 4.84), (13.2, 0.14, 0.34)),
        ((-6.6, 0, 4.84), (0.14, 9.6, 0.34)),
        ((6.6, 0, 4.84), (0.14, 9.6, 0.34)),
    ]
    for i, (c, s) in enumerate(parapet):
        box(ctx, M, g, "wall", f"Parapet_{i}", c, s)
        box(ctx, M, g, "chrome", f"Parapet_Cap_{i}", (c[0], c[1], 5.025),
            (s[0] + 0.04, s[1] + 0.04, 0.035))
    # Thin exterior panel seams.
    for zz in (1.05, 1.72, 2.39, 3.06):
        box(ctx, M, g, "trim_mid", "Side_Seam_L", (-6.605, 0, zz), (0.012, 9.48, 0.018))
        box(ctx, M, g, "trim_mid", "Side_Seam_R", (6.605, 0, zz), (0.012, 9.48, 0.018))
    for sx in (-6.35, 6.35):
        box(ctx, M, g, "trim_mid", "Corner_Trim", (sx, FRONT_Y + 0.06, 2.4),
            (0.07, 0.1, 4.3))
    # Right-side service door + utility recess.
    box(ctx, M, g, "trim_mid", "Service_Door_Frame", (6.613, 2.9, 1.35),
        (0.025, 1.06, 2.12))
    box(ctx, M, g, "trim_dark", "Service_Door", (6.628, 2.9, 1.31),
        (0.022, 0.92, 1.92))
    box(ctx, M, g, "chrome", "Service_Door_Handle", (6.645, 2.52, 1.25),
        (0.02, 0.04, 0.22))
    # Vents and meters on the side walls.
    for side, sx in ((-1, -6.61), (1, 6.61)):
        for i in range(2):
            yy = -2.7 + i * 4.5
            box(ctx, M, g, "steel", "AC_Bracket", (sx, yy, 3.92), (0.25, 0.8, 0.06))
            box(ctx, M, g, "ceramic", "AC_Outdoor", (sx + side * 0.19, yy, 4.22),
                (0.35, 0.82, 0.56))
            for k in range(5):
                box(ctx, M, g, "trim_mid", "AC_Grille",
                    (sx + side * 0.38, yy - 0.28 + k * 0.14, 4.25),
                    (0.02, 0.1, 0.42))
        box(ctx, M, g, "trim_dark", "Utility_Meter", (sx, 2.0, 1.5),
            (0.06, 0.32, 0.44))
    # Downpipes.
    for sx in (-6.62, 6.62):
        cyl(ctx, M, g, "steel", "Downpipe", (sx, BACK_Y - 0.48, 0.2),
            (sx, BACK_Y - 0.48, 4.6), 0.055, seg=8)
        cyl(ctx, M, g, "steel", "Downpipe_Elbow", (sx, BACK_Y - 0.48, 0.2),
            (sx, BACK_Y - 0.18, 0.09), 0.055, seg=8)
    # Rooftop units, vents and hatch.
    for i, (ux, uy) in enumerate(((-4.2, 2.5), (-1.0, 2.2), (3.8, 3.1))):
        box(ctx, M, g, "ceramic", f"Roof_AC_{i}", (ux, uy, 5.08), (1.2, 0.92, 0.55))
        box(ctx, M, g, "trim_mid", f"Roof_AC_Grille_{i}", (ux, uy - 0.468, 5.12),
            (0.9, 0.02, 0.36))
        cyl(ctx, M, g, "steel", f"Roof_Fan_{i}", (ux, uy - 0.475, 5.12),
            (ux, uy - 0.49, 5.12), 0.23, seg=18)
        for k in range(4):
            box(ctx, M, g, "steel_dark", f"Fan_Blade_{k}",
                (ux, uy - 0.49, 5.12), (0.45, 0.015, 0.045), rot=k * PI / 4)
    box(ctx, M, g, "steel", "Roof_Pipe", (4.9, 1.4, 5.0), (0.18, 0.18, 0.75))
    cyl(ctx, M, g, "steel", "Roof_Pipe_Elbow", (4.9, 1.4, 5.38), (5.35, 1.4, 5.38),
        0.09, seg=8)
    box(ctx, M, g, "trim_dark", "Roof_Hatch", (-5.1, -2.1, 4.86), (1.1, 0.9, 0.2))
    # A couple of bollards by the loading area.
    for i in range(3):
        x = 7.55
        y = -3.6 + i * 1.9
        cyl(ctx, M, g, "steel_dark", "Bollard", (x, y, 0.16), (x, y, 0.95),
            0.07, 0.06, seg=8)
        cyl(ctx, M, g, "paint", "Bollard_Band", (x, y, 0.78), (x, y, 0.85),
            0.073, seg=8)


def add_bicycle(ctx, M, x=10.2, y=-6.4):
    """A compact city bicycle parked on the sidewalk near the pylon."""
    g = "05_Props"
    wheel_z = 0.47
    rear_x, front_x = x - 0.58, x + 0.58
    # Tires, rims, spokes and hubs.
    for wx in (rear_x, front_x):
        L.add_torus(ctx.b(g, M["rubber"], "Bike_Tire"), (wx, y, wheel_z),
                    0.325, 0.025, axis="Y", seg_major=28, seg_minor=5)
        L.add_torus(ctx.b(g, M["chrome"], "Bike_Rim"), (wx, y, wheel_z),
                    0.282, 0.007, axis="Y", seg_major=28, seg_minor=4)
        for k in range(8):
            a = k / 8 * TAU
            rod(ctx, M, g, "chrome", "Bike_Spoke",
                (wx, y, wheel_z),
                (wx + math.cos(a) * 0.28, y, wheel_z + math.sin(a) * 0.28),
                0.0035, seg=3)
        cyl(ctx, M, g, "chrome", "Bike_Hub", (wx, y - 0.045, wheel_z),
            (wx, y + 0.045, wheel_z), 0.028, seg=8)
    # Frame: rear axle, seat cluster, down tube, top tube, head tube and forks.
    rear_axle = (rear_x, y, wheel_z)
    bb = (x - 0.22, y, 0.5)
    seat_top = (x - 0.38, y, 1.0)
    head_top = (x + 0.25, y, 0.97)
    front_axle = (front_x, y, wheel_z)
    frame_col = "red"
    rod(ctx, M, g, frame_col, "Bike_SeatTube", rear_axle, seat_top, 0.025, seg=7)
    rod(ctx, M, g, frame_col, "Bike_ChainStay", rear_axle, bb, 0.022, seg=7)
    rod(ctx, M, g, frame_col, "Bike_SeatStay", seat_top, bb, 0.02, seg=7)
    rod(ctx, M, g, frame_col, "Bike_DownTube", head_top, bb, 0.028, seg=7)
    rod(ctx, M, g, frame_col, "Bike_TopTube", seat_top, head_top, 0.025, seg=7)
    rod(ctx, M, g, "steel_dark", "Bike_HeadTube", (x + 0.24, y, 0.82),
        (x + 0.27, y, 1.0), 0.03, seg=7)
    for fy in (-0.055, 0.055):
        rod(ctx, M, g, frame_col, "Bike_Fork", (x + 0.26, y + fy, 0.94),
            (front_x, y + fy, wheel_z), 0.014, seg=5)
    # Seat, seat post, handlebar, stem and grips.
    rod(ctx, M, g, "chrome", "Bike_SeatPost", (x - 0.38, y, 0.98),
        (x - 0.4, y, 1.11), 0.016, seg=5)
    box(ctx, M, g, "rubber", "Bike_Saddle", (x - 0.4, y, 1.13),
        (0.25, 0.13, 0.045))
    box(ctx, M, g, "red", "Bike_SaddleTail", (x - 0.52, y, 1.14),
        (0.03, 0.1, 0.03))
    rod(ctx, M, g, "chrome", "Bike_Stem", (x + 0.26, y, 0.99),
        (x + 0.22, y, 1.13), 0.014, seg=5)
    rod(ctx, M, g, "chrome", "Bike_Handlebar", (x + 0.22, y - 0.32, 1.13),
        (x + 0.22, y + 0.32, 1.13), 0.014, seg=6)
    for sy in (-1, 1):
        rod(ctx, M, g, "rubber", "Bike_Grip",
            (x + 0.22, y + sy * 0.3, 1.13), (x + 0.22, y + sy * 0.39, 1.13),
            0.021, seg=6)
    # Front basket, bell and kickstand.
    bx, by, bz = x + 0.52, y, 0.8
    for dz in (0.0, 0.17):
        box(ctx, M, g, "steel", "Bike_BasketRail", (bx, by, bz + dz),
            (0.26, 0.3, 0.012))
    for sy in (-0.15, 0.15):
        box(ctx, M, g, "steel", "Bike_BasketSide", (bx, by + sy, bz + 0.085),
            (0.26, 0.012, 0.18))
    for sx in (-0.13, 0.13):
        box(ctx, M, g, "steel", "Bike_BasketSideX", (bx + sx, by, bz + 0.085),
            (0.012, 0.3, 0.18))
    L.add_sphere(ctx.b(g, M["chrome"], "Bike_Bell"), (x + 0.3, y - 0.13, 1.17),
                 0.035, 10, 6, scale=(1, 1, 0.7))
    rod(ctx, M, g, "steel_dark", "Bike_Kickstand", (x - 0.16, y + 0.08, 0.48),
        (x - 0.3, y + 0.19, 0.16), 0.012, seg=5)
    # A small rear reflector and a chain guard block.
    box(ctx, M, g, "red", "Bike_Reflector", (x - 0.78, y, 0.62),
        (0.012, 0.07, 0.035))
    box(ctx, M, g, "trim_dark", "Bike_ChainGuard", (x - 0.08, y + 0.05, 0.52),
        (0.3, 0.02, 0.06))
    # Simple U-rack beside the bike.
    rx = x + 1.22
    L.add_tube(ctx.b(g, M["steel"], "Bike_Rack"),
               [(rx, y - 0.28, 0.16), (rx, y - 0.28, 0.72),
                (rx, y + 0.28, 0.72), (rx, y + 0.28, 0.16)], 0.025, seg=7)
    box(ctx, M, g, "paint", "Bike_Rack_Plate", (rx, y, 0.17), (0.06, 0.72, 0.012))


def add_street_furnishings(ctx, M):
    """Bench, newspaper box, hydrant, utility cabinet and tactile paving."""
    g = "05_Props"
    # Wooden bench facing the street, left of the shop.
    bx, by = -7.2, -7.82
    for sy in (-0.22, -0.11, 0.0, 0.11, 0.22):
        box(ctx, M, g, "wood", "Bench_SeatSlat", (bx, by + sy, 0.47),
            (1.55, 0.095, 0.035))
    for sz in (0.66, 0.78, 0.9):
        box(ctx, M, g, "wood", "Bench_BackSlat", (bx, by + 0.25, sz),
            (1.55, 0.035, 0.08))
    for sx in (-0.63, 0.63):
        box(ctx, M, g, "steel_dark", "Bench_Leg", (bx + sx, by, 0.31),
            (0.055, 0.45, 0.34))
        box(ctx, M, g, "steel_dark", "Bench_BackPost", (bx + sx, by + 0.25, 0.67),
            (0.055, 0.055, 0.72))
        box(ctx, M, g, "steel_dark", "Bench_Arm", (bx + sx, by - 0.05, 0.66),
            (0.055, 0.45, 0.035))
    box(ctx, M, g, "steel_dark", "Bench_Foot", (bx, by, 0.17), (1.45, 0.06, 0.04))
    # Newspaper vending machine, its clear front and a stack of papers.
    nx, ny = -4.85, -8.2
    box(ctx, M, g, "trim_dark", "Newspaper_Box", (nx, ny, 0.7), (0.56, 0.46, 1.0))
    box(ctx, M, g, "trim_mid", "Newspaper_Box_Cap", (nx, ny, 1.22), (0.62, 0.52, 0.055))
    plane(ctx, M, g, "glass_fridge", "Newspaper_Window", (nx, ny - 0.235, 0.88),
          0.39, 0.35, facing="-Y")
    for i in range(3):
        box(ctx, M, g, "ceramic", "Newspaper_Stack", (nx - 0.02, ny - 0.12, 0.75 + i * 0.025),
            (0.34, 0.22, 0.014))
        box(ctx, M, g, "trim_dark", "Newspaper_Text", (nx - 0.02, ny - 0.235, 0.76 + i * 0.025),
            (0.26, 0.003, 0.004))
    box(ctx, M, g, "trim_dark", "Newspaper_CoinSlot", (nx + 0.2, ny - 0.24, 1.02),
        (0.07, 0.02, 0.1))
    box(ctx, M, g, "chrome", "Newspaper_Handle", (nx - 0.2, ny - 0.25, 0.96),
        (0.07, 0.02, 0.05))
    box(ctx, M, g, "trim_dark", "Newspaper_Base", (nx, ny, 0.18), (0.6, 0.5, 0.06))
    plane(ctx, M, g, "newspaper_box", "Newspaper_Label", (nx, ny - 0.245, 0.55),
          0.48, 0.31, facing="-Y")
    # Fire hydrant near the curb.
    hx, hy = -3.2, -9.1
    cyl(ctx, M, g, "red", "Hydrant_Base", (hx, hy, 0.15), (hx, hy, 0.28),
        0.17, 0.15, seg=12)
    cyl(ctx, M, g, "red", "Hydrant_Body", (hx, hy, 0.28), (hx, hy, 0.72),
        0.11, 0.1, seg=12)
    L.add_sphere(ctx.b(g, M["red"], "Hydrant_Dome"), (hx, hy, 0.72),
                 0.11, 14, 8, scale=(1, 1, 0.62))
    cyl(ctx, M, g, "chrome", "Hydrant_TopNut", (hx, hy, 0.79), (hx, hy, 0.85),
        0.035, seg=6)
    for sx in (-1, 1):
        rod(ctx, M, g, "red", "Hydrant_Nozzle", (hx + sx * 0.08, hy, 0.54),
            (hx + sx * 0.22, hy, 0.54), 0.055, seg=8)
        cyl(ctx, M, g, "chrome", "Hydrant_Cap", (hx + sx * 0.22, hy - 0.004, 0.54),
            (hx + sx * 0.25, hy - 0.004, 0.54), 0.06, 0.055, seg=8)
    box(ctx, M, g, "paint_warm", "Hydrant_Band", (hx, hy, 0.38),
        (0.23, 0.23, 0.024))
    # Low, robust utility cabinet.
    ux, uy = -9.4, -8.4
    box(ctx, M, g, "bin_grey", "Utility_Cabinet", (ux, uy, 0.67), (0.86, 0.58, 1.05))
    box(ctx, M, g, "trim_dark", "Utility_Cabinet_Cap", (ux, uy, 1.22), (0.94, 0.66, 0.06))
    for sx in (-0.22, 0.22):
        box(ctx, M, g, "trim_dark", "Utility_Door", (ux + sx, uy - 0.292, 0.66),
            (0.4, 0.015, 0.88))
        box(ctx, M, g, "chrome", "Utility_Handle", (ux + sx * 0.4, uy - 0.31, 0.68),
            (0.025, 0.018, 0.12))
    for i in range(5):
        box(ctx, M, g, "metal_black", "Utility_Vent", (ux - 0.25 + i * 0.125, uy - 0.305, 1.03),
            (0.07, 0.006, 0.08))
    box(ctx, M, g, "paint_warm", "Utility_Warning", (ux + 0.21, uy - 0.305, 0.72),
        (0.13, 0.006, 0.16))
    box(ctx, M, g, "trim_dark", "Utility_Warning_Border", (ux + 0.21, uy - 0.309, 0.72),
        (0.1, 0.003, 0.12))
    # Yellow tactile guide strip from the store to the curb.
    tx, ty0, ty1 = 0.4, -5.15, -9.35
    box(ctx, M, g, "tactile", "Tactile_Path", (tx, (ty0 + ty1) / 2, 0.156),
        (0.55, ty1 - ty0, 0.012))
    for i in range(5):
        box(ctx, M, g, "tactile", "Tactile_Bar",
            (tx - 0.2 + i * 0.1, (ty0 + ty1) / 2, 0.166),
            (0.026, ty1 - ty0 - 0.12, 0.007))
    for row in range(3):
        for col in range(4):
            cyl(ctx, M, g, "tactile", "Tactile_Dot",
                (tx - 0.2 + col * 0.13, -9.1 + row * 0.11, 0.162),
                (tx - 0.2 + col * 0.13, -9.1 + row * 0.11, 0.174),
                0.022, 0.022, seg=8)
    # A small painted accessibility mark at the head of the path.
    box(ctx, M, g, "paint", "Tactile_Head", (tx, -5.17, 0.162), (0.7, 0.08, 0.006))


def add_litter_and_stains(ctx, M):
    """Low-cost lived-in details: grime, fallen leaves, butts and a cone."""
    g = "05_Props"
    # Damp-looking dirt patches on the pavement, kept very transparent.
    for x, y, w, d, zz in ((-2.2, -7.4, 1.7, 1.1, 0.154), (5.3, -7.2, 2.0, 1.0, 0.154),
                           (-6.9, -8.6, 1.3, 0.9, 0.154), (9.7, -7.0, 1.4, 0.9, 0.154),
                           (2.5, -10.4, 2.2, 1.0, 0.004)):
        plane(ctx, M, g, "sidewalk_stain", "Sidewalk_Stain", (x, y, zz), w, d, facing="+Z")
    # Fallen leaves under the two street trees.
    rng = random.Random(313)
    for tx, ty, count in ((13.8, -5.9, 20), (-10.6, -6.2, 14)):
        for i in range(count):
            lx = tx + rng.uniform(-1.8, 1.8)
            ly = ty + rng.uniform(-1.8, 1.8)
            if ly > -5.1 or ly < -9.6:
                continue
            mat = rng.choice(("orange", "bark", "foliage_c", "foliage_b"))
            box(ctx, M, g, mat, "Fallen_Leaf", (lx, ly, 0.157),
                (rng.uniform(0.035, 0.075), rng.uniform(0.018, 0.04), 0.002),
                rot=rng.uniform(0, TAU))
    # Old chewing-gum spots by the entrance.
    for i in range(11):
        gx = rng.uniform(-1.4, 2.6)
        gy = rng.uniform(-8.4, -5.4)
        cyl(ctx, M, g, "trim_dark", "Gum_Spot", (gx, gy, 0.153),
            (gx, gy, 0.156), rng.uniform(0.008, 0.018), seg=6)
    # Cigarette ends near the bench.
    for i in range(4):
        bx = rng.uniform(-7.7, -6.4)
        by = rng.uniform(-8.3, -7.4)
        cyl(ctx, M, g, "ceramic", "Cigarette", (bx, by, 0.158),
            (bx + 0.026, by + 0.006, 0.158), 0.005, seg=5, caps=False)
        cyl(ctx, M, g, "wood", "Cigarette_Filter", (bx + 0.021, by + 0.005, 0.158),
            (bx + 0.032, by + 0.008, 0.158), 0.0055, seg=5, caps=False)
    # One road cone near the parking sign gives a spot of safety orange.
    cx, cy = 6.95, -8.3
    box(ctx, M, g, "rubber", "Traffic_Cone_Base", (cx, cy, 0.175), (0.36, 0.36, 0.04))
    cyl(ctx, M, g, "orange", "Traffic_Cone", (cx, cy, 0.19), (cx, cy, 0.64),
        0.13, 0.035, seg=14)
    cyl(ctx, M, g, "ceramic", "Traffic_Cone_Band", (cx, cy, 0.4), (cx, cy, 0.47),
        0.084, 0.072, seg=14)
    cyl(ctx, M, g, "orange", "Traffic_Cone_Tip", (cx, cy, 0.64), (cx, cy, 0.69),
        0.035, 0.02, seg=10)


def add_side_alley_clutter(ctx, M):
    """Practical clutter by the side service door."""
    g = "05_Props"
    # Plastic delivery crates.
    for i, (mat, dz) in enumerate((("crate_blue", 0.0), ("crate_orange", 0.34),
                                    ("crate_blue", 0.68))):
        x, y = 7.05 + (i % 2) * 0.03, 2.95
        box(ctx, M, g, mat, "Side_Crate", (x, y, 0.34 + dz), (0.55, 0.4, 0.3))
        for k in range(4):
            box(ctx, M, g, "trim_dark", "Side_Crate_Slot",
                (x, y - 0.205, 0.26 + dz + k * 0.055), (0.38, 0.006, 0.02))
    # A taped cardboard carton.
    box(ctx, M, g, "wood", "Side_Carton", (7.5, 3.45, 0.37), (0.5, 0.4, 0.42))
    box(ctx, M, g, "paint", "Side_Carton_Tape", (7.5, 3.646, 0.37),
        (0.07, 0.012, 0.43))
    box(ctx, M, g, "trim_dark", "Side_Carton_Label", (7.5, 3.655, 0.42),
        (0.18, 0.003, 0.12))
    # A yellow mop bucket.
    cyl(ctx, M, g, "paint_warm", "Mop_Bucket", (7.25, 2.2, 0.16), (7.25, 2.2, 0.54),
        0.18, 0.16, seg=14)
    box(ctx, M, g, "paint_warm", "Mop_Bucket_Wringer", (7.25, 2.13, 0.56),
        (0.25, 0.18, 0.08))
    rod(ctx, M, g, "steel", "Mop_Handle", (7.35, 2.3, 0.3), (7.2, 2.45, 1.4),
        0.014, seg=5)
    box(ctx, M, g, "ceramic", "Mop_Head", (7.2, 2.45, 1.38), (0.06, 0.3, 0.1))


def add_bike_parking_sign(ctx, M):
    g = "05_Props"
    x, y = 11.9, -7.0
    cyl(ctx, M, g, "steel_dark", "BikeSign_Base", (x, y, 0.15), (x, y, 0.25),
        0.13, 0.1, seg=12)
    cyl(ctx, M, g, "steel", "BikeSign_Post", (x, y, 0.25), (x, y, 1.66),
        0.025, 0.022, seg=8)
    box(ctx, M, g, "trim_dark", "BikeSign_Back", (x, y + 0.015, 1.55),
        (0.4, 0.035, 0.52))
    plane(ctx, M, g, "bike_parking", "BikeSign_Face", (x, y - 0.006, 1.55),
          0.36, 0.47, facing="-Y")
    for zz in (1.3, 1.8):
        box(ctx, M, g, "steel", "BikeSign_Clamp", (x, y + 0.02, zz), (0.08, 0.055, 0.03))


def add_stock_step_stool(ctx, M):
    g = "03_Interior"
    x, y = -0.85, -0.38
    # Small aluminium two-step folding stool by the cross aisle.
    for side in (-1, 1):
        rod(ctx, M, g, "steel", "Stool_LegA",
            (x + side * 0.21, y + 0.17, FLOOR_Z), (x + side * 0.13, y - 0.12, 0.92), 0.016, seg=5)
        rod(ctx, M, g, "steel", "Stool_LegB",
            (x + side * 0.21, y - 0.17, FLOOR_Z), (x + side * 0.13, y + 0.12, 0.92), 0.016, seg=5)
        box(ctx, M, g, "steel", "Stool_SideRail", (x + side * 0.17, y, 0.7),
            (0.035, 0.36, 0.025))
    for i, (zz, ww) in enumerate(((0.42, 0.38), (0.69, 0.3))):
        box(ctx, M, g, "steel", "Stool_Step", (x, y, zz), (ww, 0.24, 0.028))
    box(ctx, M, g, "rubber", "Stool_Top", (x, y, 0.93), (0.34, 0.25, 0.035))
    box(ctx, M, g, "trim_dark", "Stool_Hinge", (x, y, 0.955), (0.35, 0.02, 0.025))
    # A small left-behind shopping basket in the same aisle.
    bx, by = -3.1, -0.35
    box(ctx, M, g, "red", "Loose_Basket_Base", (bx, by, 0.22), (0.42, 0.31, 0.025))
    box(ctx, M, g, "red", "Loose_Basket_WallF", (bx, by - 0.145, 0.305), (0.42, 0.018, 0.15))
    box(ctx, M, g, "red", "Loose_Basket_WallB", (bx, by + 0.145, 0.305), (0.42, 0.018, 0.15))
    for sx in (-1, 1):
        box(ctx, M, g, "red", "Loose_Basket_WallS", (bx + sx * 0.2, by, 0.305),
            (0.018, 0.28, 0.15))
        box(ctx, M, g, "metal_black", "Loose_Basket_Handle", (bx + sx * 0.11, by - 0.155, 0.40),
            (0.12, 0.018, 0.024))
    add_pack(ctx, M, g, (bx - 0.08, by, 0.31), (0.13, 0.1, 0.17), 24)
    add_pack(ctx, M, g, (bx + 0.1, by + 0.02, 0.30), (0.1, 0.08, 0.14), 7)
    # Two cardboard cartons tucked beside the staff door.
    for i, (cx, cy, cz, sx, sy, sz) in enumerate((
            (1.85, 3.35, 0.33, 0.5, 0.42, 0.38),
            (1.92, 3.35, 0.73, 0.44, 0.36, 0.3))):
        box(ctx, M, g, "wood", "Stock_Carton", (cx, cy, cz), (sx, sy, sz))
        box(ctx, M, g, "paint", "Stock_Carton_Tape", (cx, cy - sy / 2 - 0.003, cz),
            (0.06, 0.006, sz * 0.72))
        box(ctx, M, g, "trim_dark", "Stock_Carton_Label", (cx - 0.11, cy - sy / 2 - 0.004, cz),
            (0.17, 0.004, 0.11))


def add_pedestrian_light(ctx, M):
    """A human-scaled street lamp above the bench and newspaper box."""
    g = "00_Site"
    x, y = -6.8, -9.25
    cyl(ctx, M, g, "steel_dark", "PedLight_Base", (x, y, 0.15), (x, y, 0.42),
        0.16, 0.12, seg=14)
    cyl(ctx, M, g, "steel_dark", "PedLight_Pole", (x, y, 0.42), (x, y, 4.72),
        0.07, 0.055, seg=12)
    L.add_tube(ctx.b(g, M["steel_dark"], "PedLight_Arm"),
               [(x, y, 4.72), (x, y + 0.18, 5.02), (x, y + 0.82, 5.13),
                (x, y + 1.25, 5.02)], 0.045, seg=8)
    box(ctx, M, g, "steel_dark", "PedLight_Head", (x, y + 1.4, 4.95),
        (0.31, 0.61, 0.12), rot=0)
    box(ctx, M, g, "metal_black", "PedLight_Rim", (x, y + 1.4, 4.885),
        (0.27, 0.56, 0.03))
    plane(ctx, M, g, "street_glow", "PedLight_Lens", (x, y + 1.4, 4.876),
          0.24, 0.5, facing="-Z")
    # A street-name blade on the pole.
    box(ctx, M, g, "trim_dark", "PedLight_NameBack", (x, y + 0.065, 3.55),
        (0.04, 1.45, 0.48))
    plane(ctx, M, g, "road_sign", "PedLight_Name", (x + 0.025, y + 0.065, 3.55),
          1.4, 0.44, facing="+X")
    # Small access hatch and base grime.
    box(ctx, M, g, "trim_mid", "PedLight_Access", (x + 0.071, y, 1.1),
        (0.015, 0.11, 0.3))
    return x, y


def build_signage(ctx, M):
    g = "04_Signage"
    # Fascia lightbox: cabinet, textured face, metal trim.
    box(ctx, M, g, "lightbox", "Fascia_Box", (0, FRONT_Y - 0.02, 4.04),
        (13.2, 0.18, 0.86))
    box(ctx, M, g, "trim_dark", "Fascia_Frame_Top", (0, FRONT_Y - 0.04, 4.478),
        (13.26, 0.23, 0.052))
    box(ctx, M, g, "trim_dark", "Fascia_Frame_Bottom", (0, FRONT_Y - 0.04, 3.59),
        (13.26, 0.23, 0.065))
    box(ctx, M, g, "trim_dark", "Fascia_Frame_L", (-6.62, FRONT_Y - 0.06, 4.04),
        (0.06, 0.22, 0.9))
    box(ctx, M, g, "trim_dark", "Fascia_Frame_R", (6.62, FRONT_Y - 0.06, 4.04),
        (0.06, 0.22, 0.9))
    plane(ctx, M, g, "fascia", "Fascia_Face", (0, FRONT_Y - 0.118, 4.04),
          13.12, 0.82, facing="-Y")
    # Pylon sign at the curb.
    px, py = 8.55, -7.55
    # Base and posts.
    box(ctx, M, g, "concrete", "Pylon_Footing", (px, py, 0.3), (1.05, 0.95, 0.3),
        uv_scale=1.8)
    for sx in (-0.47, 0.47):
        box(ctx, M, g, "steel_dark", "Pylon_Post", (px + sx, py, 1.25),
            (0.12, 0.16, 2.1))
    box(ctx, M, g, "steel_dark", "Pylon_Brace", (px, py, 0.55), (1.04, 0.1, 0.1))
    # Cabinet.
    box(ctx, M, g, "lightbox", "Pylon_Box", (px, py, 3.55), (1.46, 0.34, 2.98))
    box(ctx, M, g, "trim_dark", "Pylon_Cap", (px, py, 5.065), (1.56, 0.44, 0.09))
    box(ctx, M, g, "trim_dark", "Pylon_Base_Cap", (px, py, 2.075), (1.52, 0.4, 0.08))
    plane(ctx, M, g, "pylon", "Pylon_Face_Front", (px, py - 0.178, 3.56),
          1.4, 2.8, facing="-Y")
    # Back face has its U axis reversed so the wordmark reads correctly from
    # the reverse side instead of appearing as a mirror image.
    bpn = ctx.b(g, M["pylon"], "Pylon_Face_Back", uv=True)
    bx0, bx1 = px - 0.7, px + 0.7
    bz0, bz1 = 3.56 - 1.4, 3.56 + 1.4
    bpn.add([(bx1, py + 0.178, bz0), (bx0, py + 0.178, bz0),
             (bx0, py + 0.178, bz1), (bx1, py + 0.178, bz1)],
            [[0, 1, 2, 3]], [[(1, 0), (0, 0), (0, 1), (1, 1)]])
    # Dark reveal around the pylon faces.
    for zz in (2.1, 5.02):
        box(ctx, M, g, "trim_dark", "Pylon_TrimH", (px, py, zz), (1.5, 0.42, 0.04))
    for sx in (-0.73, 0.73):
        box(ctx, M, g, "trim_dark", "Pylon_TrimV", (px + sx, py, 3.56),
            (0.04, 0.4, 2.95))
    # Wall-mounted logo on the left side (visible in the three-quarter view).
    wx = -6.615
    wy = -1.65
    box(ctx, M, g, "cream", "Wall_Logo_Board", (wx - 0.02, wy, 2.72),
        (0.04, 2.5, 2.5))
    box(ctx, M, g, "trim_dark", "Wall_Logo_Frame_T", (wx - 0.035, wy, 4.0),
        (0.03, 2.62, 0.04))
    box(ctx, M, g, "trim_dark", "Wall_Logo_Frame_B", (wx - 0.035, wy, 1.44),
        (0.03, 2.62, 0.04))
    plane(ctx, M, g, "logo", "Wall_Logo", (wx - 0.05, wy, 2.72), 2.26, 2.19,
          facing="-X")
    # Color bars below the logo.
    for i, col in enumerate(("orange", "green", "red")):
        box(ctx, M, g, col, "Logo_Bar", (wx - 0.052, wy - 0.95 + i * 0.18, 1.36),
            (0.02, 0.16, 0.04))
    # Small parking / no parking sign on a pole near the pylon.
    box(ctx, M, g, "steel", "Parking_Post", (6.25, -9.15, 1.4), (0.06, 0.06, 2.6))
    box(ctx, M, g, "ceramic", "Parking_Sign", (6.25, -9.19, 2.5),
        (0.42, 0.035, 0.56))
    box(ctx, M, g, "red", "Parking_Sign_Stripe", (6.25, -9.212, 2.7),
        (0.34, 0.005, 0.08))
    # Door decal and window graphic are in the glazing group.
    g2 = "02_Glazing"
    plane(ctx, M, g2, "door_stickers", "Door_Stickers", (1.24, FRONT_Y + 0.055, 1.23),
          0.29, 0.29, facing="-Y")
    # Vertical payment plaque on the blank pier left of the entrance.
    box(ctx, M, g2, "trim_dark", "Payment_Plaque_Back", (-1.1, FRONT_Y + 0.006, 1.85),
        (0.3, 0.014, 0.73))
    plane(ctx, M, g2, "payment_methods", "Payment_Plaque", (-1.1, FRONT_Y - 0.002, 1.85),
          0.27, 0.675, facing="-Y")
    for sx in (-0.135, 0.135):
        for sz in (-0.34, 0.34):
            cyl(ctx, M, g2, "chrome", "Payment_Screw", (-1.1 + sx, FRONT_Y - 0.006, 1.85 + sz),
                (-1.1 + sx, FRONT_Y - 0.012, 1.85 + sz), 0.009, seg=6)
    plane(ctx, M, g2, "window_decal", "Window_Decal", (5.5, FRONT_Y + 0.042, 1.26),
          0.95, 0.71, facing="-Y")
    # OPEN neon, inside the left window.
    box(ctx, M, g2, "trim_dark", "Open_Frame", (-1.8, -4.61, 2.2),
        (1.14, 0.03, 0.58))
    plane(ctx, M, g2, "open_neon", "Open_Neon", (-1.8, -4.635, 2.2),
          1.04, 0.52, facing="-Y")


def build_interior(ctx, M):
    g = "03_Interior"
    # Floor and ceiling.
    box(ctx, M, g, "store_floor", "Interior_Floor", (0, -0.06, 0.19),
        (12.5, 9.2, 0.04), uv_scale=2.4)
    box(ctx, M, g, "ceiling", "Interior_Ceiling", (0, 0, 3.60),
        (12.5, 9.2, 0.08), uv_scale=2.4)
    # Interior lining of the outer walls.
    box(ctx, M, g, "wall_interior", "Lining_L", (-6.24, 0, 1.9),
        (0.04, 9.1, 3.38))
    box(ctx, M, g, "wall_interior", "Lining_R", (6.24, 0, 1.9),
        (0.04, 9.1, 3.38))
    box(ctx, M, g, "wall_interior", "Lining_Back", (0, 4.44, 1.9),
        (12.4, 0.04, 3.38))
    # Ceiling light troughs.
    for ix in (-4.25, -1.45, 1.45, 4.25):
        for iy in (-2.35, 1.4):
            box(ctx, M, g, "trim_dark", "LED_Trough", (ix, iy, 3.515),
                (0.64, 2.5, 0.055))
            box(ctx, M, g, "led", "LED_Panel", (ix, iy, 3.485),
                (0.55, 2.4, 0.025))
    # Additional small downlights over the entrance and counter.
    for (ix, iy) in ((0.4, -3.4), (4.4, -1.5), (-3.0, 3.4)):
        cyl(ctx, M, g, "warm_glow", "Downlight", (ix, iy, 3.49), (ix, iy, 3.472),
            0.1, seg=12)
        cyl(ctx, M, g, "chrome", "Downlight_Rim", (ix, iy, 3.495), (ix, iy, 3.487),
            0.12, seg=12)
    # Entry mat and floor decal.
    box(ctx, M, g, "trim_dark", "Entry_Mat", (0.4, -3.85, FLOOR_Z + 0.012),
        (2.05, 1.1, 0.02))
    for i in range(6):
        box(ctx, M, g, "chrome", "Mat_Rib", (0.4, -4.3 + i * 0.18, FLOOR_Z + 0.024),
            (1.85, 0.015, 0.008))
    # Refrigerator bank along the back wall.
    fridge_left, fridge_right = -5.25, -0.25
    bank_w = fridge_right - fridge_left
    fz0, fz1 = FLOOR_Z, 2.58
    box(ctx, M, g, "trim_dark", "Fridge_Frame", ((fridge_left + fridge_right) / 2, 4.02, 1.39),
        (bank_w + 0.14, 0.80, 2.4))
    # Back-lit interior panel, behind the drinks and in front of the wall.
    plane(ctx, M, g, "fridge_glow", "Fridge_Backlight", ((fridge_left + fridge_right) / 2, 4.40, 1.38),
          bank_w - 0.08, 2.15, facing="-Y")
    ndoors = 5
    door_w = bank_w / ndoors
    for d in range(ndoors):
        x0 = fridge_left + d * door_w + 0.035
        x1 = fridge_left + (d + 1) * door_w - 0.035
        # Shelves.
        for si, zz in enumerate((0.62, 1.06, 1.50, 1.94, 2.34)):
            box(ctx, M, g, "shelf", "Fridge_Shelf", ((x0 + x1) / 2, 4.03, zz),
                (x1 - x0 - 0.03, 0.66, 0.025))
            # A strip light under each shelf, close to the back panel.
            box(ctx, M, g, "fridge_glow", "Fridge_Shelf_Light", ((x0 + x1) / 2, 4.31, zz - 0.02),
                (x1 - x0 - 0.15, 0.02, 0.015))
            # Drinks.
            count = 5
            row_mat = f"prod_{(d * 3 + si * 2) % 16}"
            for k in range(count):
                cx = x0 + (k + 0.5) / count * (x1 - x0)
                mat = row_mat if (k // 2) % 2 == 0 else f"prod_{(d * 5 + si + k) % 16}"
                radius = 0.045 if (k + si) % 3 else 0.055
                height = 0.2 + ((k + d) % 3) * 0.025
                cyl(ctx, M, g, mat, "Fridge_Drinks", (cx, 4.02, zz + 0.02),
                    (cx, 4.02, zz + height), radius, radius, seg=10)
                cyl(ctx, M, g, "product_label", "Fridge_LabelBand", (cx, 4.02, zz + height * 0.45),
                    (cx, 4.02, zz + height * 0.72), radius + 0.0015, radius + 0.0015, seg=10)
                cyl(ctx, M, g, "product_cap", "Fridge_Cap", (cx, 4.02, zz + height),
                    (cx, 4.02, zz + height + 0.015), radius * 0.65, seg=8)
        # Shelf-edge price tags behind the glass.
        for si, zz in enumerate((0.62, 1.06, 1.50, 1.94)):
            for ti in range(2):
                add_price_tag(ctx, M, g,
                              (x0 + 0.22 + ti * (x1 - x0 - 0.42), 3.515, zz - 0.065),
                              0.12, 0.07, (d * 13 + si * 3 + ti * 5) % (TAG_COLS * TAG_ROWS))
        # Door frame and glass.
        box(ctx, M, g, "frame_dark", "Fridge_Door_VL", (x0 + 0.02, 3.55, 1.4),
            (0.045, 0.04, 2.25))
        box(ctx, M, g, "frame_dark", "Fridge_Door_VR", (x1 - 0.02, 3.55, 1.4),
            (0.045, 0.04, 2.25))
        box(ctx, M, g, "frame_dark", "Fridge_Door_Top", ((x0 + x1) / 2, 3.55, 2.52),
            (x1 - x0, 0.04, 0.05))
        box(ctx, M, g, "frame_dark", "Fridge_Door_Bottom", ((x0 + x1) / 2, 3.55, 0.33),
            (x1 - x0, 0.04, 0.06))
        plane(ctx, M, g, "glass_fridge", "Fridge_Door_Glass", ((x0 + x1) / 2, 3.56, 1.43),
              x1 - x0 - 0.07, 2.16, facing="-Y")
        box(ctx, M, g, "chrome", "Fridge_Handle", (x1 - 0.11, 3.50, 1.38),
            (0.035, 0.05, 0.55))
    # Fridge header.
    box(ctx, M, g, "lightbox", "Fridge_Header_Board", (-2.75, 3.55, 2.84),
        (2.8, 0.11, 0.42))
    plane(ctx, M, g, "fridge_header", "Fridge_Header", (-2.75, 3.49, 2.84),
          2.68, 0.38, facing="-Y")
    # Staff door to the right of the fridges.
    box(ctx, M, g, "trim_mid", "Staff_Door_Frame", (1.05, 4.40, 1.35),
        (1.0, 0.08, 2.28))
    box(ctx, M, g, "wood", "Staff_Door", (1.05, 4.34, 1.33), (0.86, 0.07, 2.1))
    box(ctx, M, g, "chrome", "Staff_Door_Handle", (1.4, 4.28, 1.28),
        (0.04, 0.04, 0.22))
    # Back counter / coffee station on the right side.
    bx0, bx1 = 2.3, 6.05
    box(ctx, M, g, "cream", "Back_Counter", ((bx0 + bx1) / 2, 3.75, 0.82),
        (bx1 - bx0, 0.7, 1.2))
    box(ctx, M, g, "counter_top", "Back_Counter_Top", ((bx0 + bx1) / 2, 3.75, 1.44),
        (bx1 - bx0 + 0.08, 0.78, 0.06))
    box(ctx, M, g, "green", "Back_Counter_Stripe", ((bx0 + bx1) / 2, 3.38, 0.82),
        (bx1 - bx0, 0.03, 0.12))
    # Coffee machine.
    box(ctx, M, g, "metal_black", "Coffee_Machine", (4.9, 3.75, 1.75), (0.62, 0.5, 0.58))
    box(ctx, M, g, "chrome", "Coffee_Face", (4.9, 3.51, 1.78), (0.5, 0.03, 0.32))
    box(ctx, M, g, "screen_glow", "Coffee_Display", (4.9, 3.492, 1.88), (0.23, 0.012, 0.1))
    cyl(ctx, M, g, "chrome", "Coffee_Spout", (4.9, 3.49, 1.58), (4.9, 3.36, 1.56), 0.018, seg=6)
    box(ctx, M, g, "chrome", "Cup_Plate", (4.9, 3.48, 1.51), (0.3, 0.2, 0.02))
    # Cups and supplies.
    for i in range(3):
        cyl(ctx, M, g, "ceramic", "Cup_Stack", (5.5, 3.7, 1.48 + i * 0.06),
            (5.5, 3.7, 1.53 + i * 0.06), 0.075, 0.055, seg=10)
    for i in range(4):
        cyl(ctx, M, g, "ceramic", "Cup", (3.2 + i * 0.13, 3.6, 1.47),
            (3.2 + i * 0.13, 3.6, 1.58), 0.04, 0.055, seg=8)
    # Menu board on the back wall.
    box(ctx, M, g, "trim_dark", "Menu_Frame", (4.95, 4.41, 2.52), (0.9, 0.03, 1.2))
    plane(ctx, M, g, "menu", "Menu_Board", (4.95, 4.39, 2.52), 0.8, 1.1, facing="-Y")
    # Front service counter, in the right-hand window bay.
    x0, x1 = 2.55, 5.85
    y0, y1 = -2.55, -1.88
    box(ctx, M, g, "cream", "Counter_Base", ((x0 + x1) / 2, (y0 + y1) / 2, 0.72),
        (x1 - x0, y1 - y0, 1.0))
    box(ctx, M, g, "counter_top", "Counter_Top", ((x0 + x1) / 2, (y0 + y1) / 2, 1.25),
        (x1 - x0 + 0.08, y1 - y0 + 0.12, 0.07))
    box(ctx, M, g, "green", "Counter_Stripe", ((x0 + x1) / 2, y0 - 0.006, 0.56),
        (x1 - x0, 0.012, 0.14))
    box(ctx, M, g, "trim_dark", "Counter_Kick", ((x0 + x1) / 2, (y0 + y1) / 2, 0.27),
        (x1 - x0 - 0.04, y1 - y0 - 0.04, 0.14))
    # A low customer-facing transaction screen.
    box(ctx, M, g, "metal_black", "Card_Terminal", (3.0, -2.30, 1.36),
        (0.18, 0.12, 0.18))
    box(ctx, M, g, "screen_glow", "Card_Display", (3.0, -2.365, 1.39),
        (0.1, 0.012, 0.08))
    # Pos terminal and monitor.
    box(ctx, M, g, "metal_black", "POS_Stand", (5.15, -2.2, 1.39), (0.19, 0.14, 0.21))
    box(ctx, M, g, "metal_black", "POS_Monitor", (5.15, -2.3, 1.7), (0.48, 0.08, 0.34))
    plane(ctx, M, g, "screen_glow", "POS_Screen", (5.15, -2.345, 1.7), 0.4, 0.26,
          facing="-Y")
    # Keyboard, receipt printer, scanner.
    box(ctx, M, g, "trim_dark", "POS_Keyboard", (4.92, -2.0, 1.31), (0.42, 0.18, 0.035))
    box(ctx, M, g, "ceramic", "Receipt_Printer", (5.53, -2.0, 1.4), (0.22, 0.18, 0.2))
    box(ctx, M, g, "steel", "Scanner", (4.33, -2.05, 1.34), (0.24, 0.2, 0.1))
    # Hot food warmer, glowing amber through glass.
    wx, wy = 3.55, -2.22
    box(ctx, M, g, "steel", "Warmer_Base", (wx, wy, 1.33), (0.78, 0.5, 0.09))
    box(ctx, M, g, "warm_glow", "Warmer_Tray", (wx, wy, 1.39), (0.7, 0.42, 0.025))
    for i in range(4):
        for j in range(2):
            L.add_sphere(ctx.b(g, M[f"prod_{(i * 2 + j) % 8}"], "Warmer_Food"),
                         (wx - 0.24 + i * 0.16, wy - 0.08 + j * 0.14, 1.44),
                         0.06, 10, 6, scale=(1.2, 1.0, 0.55))
    plane(ctx, M, g, "glass_fridge", "Warmer_Glass_Front", (wx, wy - 0.255, 1.63),
          0.74, 0.4, facing="-Y")
    box(ctx, M, g, "chrome", "Warmer_Frame", (wx, wy - 0.25, 1.84), (0.78, 0.02, 0.025))
    box(ctx, M, g, "chrome", "Warmer_Frame_L", (wx - 0.385, wy - 0.25, 1.63),
        (0.025, 0.02, 0.4))
    box(ctx, M, g, "chrome", "Warmer_Frame_R", (wx + 0.385, wy - 0.25, 1.63),
        (0.025, 0.02, 0.4))
    box(ctx, M, g, "warm_glow", "Warmer_Header", (wx, wy - 0.26, 1.86),
        (0.7, 0.01, 0.05))
    # Under-counter back cabinets.
    box(ctx, M, g, "shelf", "Under_Counter", (4.2, -2.5, 0.55), (2.8, 0.12, 0.5))
    # Candy / impulse rack by the entrance.
    box(ctx, M, g, "steel_dark", "Impulse_Rack", (-2.05, -3.95, 0.62), (1.1, 0.38, 0.85))
    for i in range(4):
        box(ctx, M, g, "shelf", "Impulse_Shelf", (-2.05, -3.95, 0.35 + i * 0.18),
            (1.0, 0.34, 0.025))
        for j in range(7):
            add_pack(ctx, M, g, (-2.49 + j * 0.145, -4.13, 0.43 + i * 0.18),
                     (0.1, 0.08, 0.13), (i * 7 + j * 5) % (PACK_COLS * PACK_ROWS))
    # Gondola shelving, three runs along the left half.
    gondolas = [(-1.9, 4.5), (0.38, 4.5), (3.05, 4.0)]
    for gi, (gy, glen) in enumerate(gondolas):
        gx0 = -5.3
        gx1 = gx0 + glen
        # Base spine.
        box(ctx, M, g, "shelf_green", "Gondola_Kick", ((gx0 + gx1) / 2, gy, 0.32),
            (glen, 0.62, 0.24))
        box(ctx, M, g, "shelf", "Gondola_Spine", ((gx0 + gx1) / 2, gy, 0.83),
            (glen, 0.08, 1.26))
        # Uprights.
        n_up = max(2, int(glen / 1.08) + 1)
        for up in range(n_up):
            xx = gx0 + up * glen / (n_up - 1)
            box(ctx, M, g, "shelf_green", "Gondola_Upright", (xx, gy, 0.85),
                (0.045, 0.56, 1.35))
        # Shelves + products.
        for si, zz in enumerate((0.48, 0.84, 1.20, 1.55)):
            box(ctx, M, g, "shelf", "Gondola_Shelf", ((gx0 + gx1) / 2, gy, zz),
                (glen, 0.65, 0.035))
            box(ctx, M, g, "shelf_green", "Gondola_RailF", ((gx0 + gx1) / 2, gy - 0.33, zz - 0.02),
                (glen, 0.015, 0.055))
            box(ctx, M, g, "shelf_green", "Gondola_RailB", ((gx0 + gx1) / 2, gy + 0.33, zz - 0.02),
                (glen, 0.015, 0.055))
            for side in (-1, 1):
                x = gx0 + 0.12 + (gi * 0.07)
                rng = random.Random(gi * 101 + si * 17 + side * 3 + int(gy * 10))
                # Merchandise is faced in small groups of identical packs,
                # the way a real convenience-store shelf is stocked, instead
                # of being an evenly random confetti of colours.
                while x < gx1 - 0.12:
                    cell = rng.randrange(PACK_COLS * PACK_ROWS)
                    w = rng.uniform(0.105, 0.19)
                    bag = rng.random() < 0.18
                    dep = rng.uniform(0.06, 0.1) if bag else rng.uniform(0.09, 0.16)
                    h = rng.uniform(0.17, 0.28)
                    facing = rng.choice((2, 3, 3, 4))
                    if x + w * 2 > gx1 - 0.05:
                        break
                    yy = gy + side * (0.35 - dep / 2)
                    for k in range(facing):
                        if x + w > gx1 - 0.045:
                            break
                        if rng.random() < 0.9:
                            add_pack(ctx, M, g, (x + w / 2, yy, zz + 0.02 + h / 2),
                                     (w, dep, h), cell)
                        else:
                            mat = f"prod_{rng.randrange(16)}"
                            box(ctx, M, g, mat, "Gondola_Product",
                                (x + w / 2, yy, zz + 0.02 + h / 2), (w, dep, h))
                            box(ctx, M, g, "product_label", "Gondola_Label",
                                (x + w / 2, yy + side * (dep / 2 + 0.003),
                                 zz + 0.02 + h * 0.55),
                                (w * 0.62, 0.005, h * 0.23))
                        x += w + 0.006
                    x += rng.uniform(0.02, 0.055)
                # Price tags on the front rail.
                if side == -1:
                    for ti in range(5):
                        tx = gx0 + 0.45 + ti * (glen - 0.9) / 4
                        add_price_tag(ctx, M, g, (tx, gy - 0.336, zz - 0.068),
                                      0.13, 0.076, (gi * 11 + si * 5 + ti * 3) % (TAG_COLS * TAG_ROWS))
                # A continuous under-shelf LED strip.
                box(ctx, M, g, "shelf_led", "Under_Shelf_LED",
                    ((gx0 + gx1) / 2, gy - 0.31, zz - 0.055),
                    (glen - 0.1, 0.02, 0.008))
                # A handful of slim cans catch the interior light and break up
                # the boxy rhythm of the shelf display.
                if side == -1:
                    can_y = gy - 0.315
                    for ci in range(6):
                        cx = gx0 + 0.55 + ci * (glen - 1.0) / 5.0
                        can_h = 0.15 + (ci % 2) * 0.025
                        mat = f"prod_{(si * 5 + ci * 2 + gi) % 16}"
                        cyl(ctx, M, g, mat, "Gondola_Can",
                            (cx, can_y, zz + 0.025), (cx, can_y, zz + 0.025 + can_h),
                            0.038, 0.038, seg=9)
                        cyl(ctx, M, g, "product_cap", "Gondola_Can_Cap",
                            (cx, can_y, zz + 0.025 + can_h),
                            (cx, can_y, zz + 0.04 + can_h), 0.031, seg=8)
                        box(ctx, M, g, "product_label", "Gondola_Can_Label",
                            (cx, can_y - 0.038, zz + 0.04 + can_h * 0.52),
                            (0.042, 0.004, 0.055))
        # End cap display, facing the front for the nearest run.
        if gi == 0:
            box(ctx, M, g, "shelf_green", "Endcap_Base", (gx1 + 0.22, gy, 0.55),
                (0.43, 0.66, 0.7))
            for k in range(3):
                box(ctx, M, g, "shelf", "Endcap_Shelf", (gx1 + 0.22, gy, 0.38 + k * 0.22),
                    (0.43, 0.62, 0.025))
            for k in range(5):
                add_pack(ctx, M, g, (gx1 + 0.22, gy - 0.22 + k * 0.1, 0.66),
                         (0.3, 0.08, 0.25), (gi * 17 + k * 9) % (PACK_COLS * PACK_ROWS))
            add_price_tag(ctx, M, g, (gx1 + 0.22, gy - 0.27, 0.55),
                          0.16, 0.1, 7)
    # Ice-cream chest freezer tucked under the left-hand window poster.
    box(ctx, M, g, "ceramic", "IceCream_Chest", (-5.55, -3.55, 0.58), (1.3, 0.7, 0.8))
    box(ctx, M, g, "trim_dark", "IceCream_Base", (-5.55, -3.55, 0.24), (1.1, 0.62, 0.08))
    box(ctx, M, g, "glass_dark", "IceCream_Lid", (-5.55, -3.55, 1.02), (1.2, 0.62, 0.04))
    box(ctx, M, g, "chrome", "IceCream_Handle", (-5.2, -3.88, 1.04), (0.3, 0.035, 0.035))
    box(ctx, M, g, "street_glow", "IceCream_Light", (-5.55, -3.8, 1.035), (1.05, 0.02, 0.012))
    box(ctx, M, g, "trim_dark", "IceCream_SignFrame", (-5.55, -3.92, 0.58),
        (1.0, 0.012, 0.3))
    plane(ctx, M, g, "icecream_label", "IceCream_Label", (-5.55, -3.93, 0.58),
          0.9, 0.3, facing="-Y")
    # Window poster panels (inside).
    for name, mat, cx in (("Slurpee_Poster", "poster_slurpee", -5.25),
                          ("Coffee_Poster", "poster_coffee", 4.88)):
        box(ctx, M, g, "trim_dark", f"{name}_Frame", (cx, -4.49, 1.92), (1.25, 0.035, 1.86))
        plane(ctx, M, g, mat, name, (cx, -4.455, 1.92), 1.16, 1.76, facing="-Y")
    # Aisle hanging boards.
    for i, (ax, ay, mat) in enumerate(((-3.4, -1.2, "aisle_1"),
                                       (-2.7, 1.3, "aisle_2"),
                                       (-1.3, 3.25, "aisle_3"))):
        for sx in (-0.5, 0.5):
            rod(ctx, M, g, "steel", "Aisle_Hanger", (ax + sx, ay, 3.5), (ax + sx, ay, 3.2),
                0.006, seg=4)
        box(ctx, M, g, "lightbox", "Aisle_Board", (ax, ay, 3.0), (1.18, 0.035, 0.36))
        plane(ctx, M, g, mat, "Aisle_Sign", (ax, ay - 0.022, 3.0), 1.12, 0.35,
              facing="-Y")
    # Wall shelving above the coffee station.
    for i in range(2):
        box(ctx, M, g, "shelf", "Coffee_Wall_Shelf", (3.55, 4.22, 2.76 + i * 0.32),
            (0.9, 0.32, 0.035))
        for j in range(3):
            cyl(ctx, M, g, "ceramic", "Coffee_Cup_Stock",
                (3.25 + j * 0.24, 4.22, 2.79 + i * 0.32),
                (3.25 + j * 0.24, 4.22, 2.9 + i * 0.32), 0.05, 0.04, seg=8)
    # Fire extinguisher.
    cyl(ctx, M, g, "red", "Fire_Extinguisher", (2.02, -4.28, FLOOR_Z),
        (2.02, -4.28, 0.79), 0.09, seg=12)
    cyl(ctx, M, g, "metal_black", "Fire_Ext_Neck", (2.02, -4.28, 0.79),
        (2.02, -4.28, 0.9), 0.035, seg=8)
    # Interior security camera.
    box(ctx, M, g, "ceramic", "CCTV_Body", (-6.0, -2.6, 3.38), (0.14, 0.24, 0.12))
    plane(ctx, M, g, "glass_dark", "CCTV_Lens", (-6.0, -2.73, 3.36), 0.06, 0.06,
          facing="-Y")
    # Wall clock above the counter.
    cyl(ctx, M, g, "trim_dark", "Wall_Clock", (4.4, 4.38, 3.02), (4.4, 4.36, 3.02),
        0.21, seg=24)
    cyl(ctx, M, g, "ceramic", "Wall_Clock_Face", (4.4, 4.44, 3.02), (4.4, 4.445, 3.02),
        0.185, seg=24)


# ---------------------------------------------------------------------------
# Upgraded interior details
# ---------------------------------------------------------------------------
def add_slurpee_machine(ctx, M):
    """A two-bowl frozen-drink machine by the left window."""
    g = "03_Interior"
    sx, sy = -3.70, -3.33
    # Cabinet and feet.
    box(ctx, M, g, "ceramic", "Slurpee_Cabinet", (sx, sy, 0.59), (0.92, 0.62, 0.78))
    box(ctx, M, g, "trim_dark", "Slurpee_Kick", (sx, sy, 0.235), (0.86, 0.56, 0.07))
    box(ctx, M, g, "trim_dark", "Slurpee_Front_Panel", (sx, sy - 0.316, 0.87),
        (0.9, 0.02, 0.18))
    box(ctx, M, g, "screen_glow", "Slurpee_Display", (sx - 0.22, sy - 0.329, 0.88),
        (0.18, 0.008, 0.07))
    for i, col in enumerate(("red", "orange", "green")):
        box(ctx, M, g, col, "Slurpee_Stripe", (sx + 0.12 + i * 0.16, sy - 0.329, 0.88),
            (0.12, 0.008, 0.025))
    # Drip tray and dispensing taps.
    box(ctx, M, g, "steel", "Slurpee_DripTray", (sx, sy - 0.37, 0.76),
        (0.54, 0.16, 0.035))
    for i in range(5):
        box(ctx, M, g, "chrome", "Slurpee_DripSlot", (sx - 0.2 + i * 0.1, sy - 0.37, 0.779),
            (0.012, 0.12, 0.005))
    # Rear bowl housing.
    box(ctx, M, g, "metal_black", "Slurpee_RearHousing", (sx, sy + 0.18, 1.23),
        (0.86, 0.22, 0.48))
    # Twin transparent bowls, each with a colored frozen core.
    for dx, liquid, stripe in ((-0.22, "prod_0", "red"), (0.22, "prod_2", "green")):
        bx = sx + dx
        cyl(ctx, M, g, "chrome", "Slurpee_BowlBase", (bx, sy + 0.02, 0.985),
            (bx, sy + 0.02, 1.03), 0.155, seg=18)
        cyl(ctx, M, g, liquid, "Slurpee_Mix", (bx, sy + 0.02, 1.03),
            (bx, sy + 0.02, 1.33), 0.119, 0.112, seg=16)
        L.add_sphere(ctx.b(g, M[liquid], "Slurpee_Mix_Top"),
                     (bx, sy + 0.02, 1.33), 0.118, 14, 8, scale=(1, 1, 0.55))
        cyl(ctx, M, g, "glass_fridge", "Slurpee_Glass", (bx, sy + 0.02, 1.01),
            (bx, sy + 0.02, 1.37), 0.145, 0.145, seg=18)
        L.add_sphere(ctx.b(g, M["glass_fridge"], "Slurpee_Dome"),
                     (bx, sy + 0.02, 1.37), 0.145, 16, 9, scale=(1, 1, 0.58))
        cyl(ctx, M, g, "chrome", "Slurpee_Lid", (bx, sy + 0.02, 1.40),
            (bx, sy + 0.02, 1.435), 0.16, 0.16, seg=18)
        cyl(ctx, M, g, "chrome", "Slurpee_Tap", (bx, sy - 0.12, 1.0),
            (bx, sy - 0.25, 0.94), 0.028, 0.022, seg=8)
        box(ctx, M, g, stripe, "Slurpee_TapHandle", (bx, sy - 0.25, 1.03),
            (0.05, 0.04, 0.13))
        # Product label ring.
        cyl(ctx, M, g, "product_label", "Slurpee_LabelRing", (bx, sy + 0.02, 1.08),
            (bx, sy + 0.02, 1.13), 0.151, 0.151, seg=18)
    # Illuminated header.
    box(ctx, M, g, "lightbox", "Slurpee_Header", (sx, sy - 0.18, 1.69),
        (0.94, 0.24, 0.26))
    box(ctx, M, g, "trim_dark", "Slurpee_Header_Trim", (sx, sy - 0.305, 1.69),
        (0.96, 0.025, 0.29))
    plane(ctx, M, g, "slurpee_label", "Slurpee_Header_Face", (sx, sy - 0.320, 1.69),
          0.86, 0.24, facing="-Y")
    box(ctx, M, g, "chrome", "Slurpee_TopCap", (sx, sy - 0.16, 1.835),
        (0.88, 0.28, 0.025))
    # Side logo and a small step.
    box(ctx, M, g, "trim_dark", "Slurpee_Step", (sx, sy - 0.43, 0.22),
        (0.7, 0.16, 0.03))


def add_condiment_station(ctx, M):
    """Self-service coffee and condiments, close to the right window."""
    g = "03_Interior"
    cx, cy = 3.34, -3.72
    box(ctx, M, g, "cream", "Condiment_Base", (cx, cy, 0.56), (1.58, 0.55, 0.72))
    box(ctx, M, g, "green", "Condiment_Stripe", (cx, cy - 0.281, 0.48),
        (1.58, 0.012, 0.14))
    box(ctx, M, g, "trim_dark", "Condiment_Kick", (cx, cy, 0.235), (1.5, 0.48, 0.08))
    box(ctx, M, g, "counter_top", "Condiment_Top", (cx, cy, 0.945),
        (1.64, 0.61, 0.06))
    # Coffee machine.
    box(ctx, M, g, "metal_black", "Condiment_Coffee", (cx - 0.52, cy, 1.27),
        (0.38, 0.36, 0.6))
    box(ctx, M, g, "chrome", "Condiment_CoffeeFace", (cx - 0.52, cy - 0.185, 1.31),
        (0.3, 0.03, 0.4))
    box(ctx, M, g, "screen_glow", "Condiment_CoffeeScreen", (cx - 0.52, cy - 0.204, 1.44),
        (0.17, 0.008, 0.09))
    cyl(ctx, M, g, "chrome", "Condiment_Spout", (cx - 0.52, cy - 0.2, 1.17),
        (cx - 0.52, cy - 0.27, 1.14), 0.014, seg=6)
    box(ctx, M, g, "chrome", "Condiment_DripTray", (cx - 0.52, cy - 0.21, 0.99),
        (0.3, 0.2, 0.025))
    cyl(ctx, M, g, "ceramic", "Condiment_CupUnder", (cx - 0.52, cy - 0.18, 1.0),
        (cx - 0.52, cy - 0.18, 1.1), 0.04, 0.055, seg=9)
    # Cup stacks and condiment supplies.
    for i, ox in enumerate((0.35, 0.53)):
        cyl(ctx, M, g, "ceramic", "Condiment_CupStack", (cx + ox, cy - 0.04, 0.98),
            (cx + ox, cy - 0.04, 1.22), 0.058, 0.044, seg=10)
        cyl(ctx, M, g, "product_label", "Condiment_LidStack", (cx + ox, cy - 0.04, 1.22),
            (cx + ox, cy - 0.04, 1.25), 0.061, seg=10)
    box(ctx, M, g, "metal_black", "Condiment_Napkins", (cx + 0.03, cy - 0.12, 1.05),
        (0.22, 0.15, 0.19))
    box(ctx, M, g, "product_label", "Condiment_Napkin", (cx + 0.03, cy - 0.2, 1.05),
        (0.14, 0.008, 0.1))
    cyl(ctx, M, g, "glass_fridge", "Condiment_StrawCup", (cx + 0.17, cy + 0.13, 0.975),
        (cx + 0.17, cy + 0.13, 1.16), 0.07, 0.06, seg=12)
    for i in range(7):
        cyl(ctx, M, g, "paint", "Condiment_Straw", (cx + 0.15 + (i % 3) * 0.015,
            cy + 0.13 + (i // 3) * 0.012, 1.05),
            (cx + 0.15 + (i % 3) * 0.018, cy + 0.13 + (i // 3) * 0.012, 1.3),
            0.005, seg=4)
    for i, col in enumerate(("prod_0", "prod_4", "prod_5", "prod_8")):
        cyl(ctx, M, g, col, "Condiment_Syrup", (cx + 0.3 + i * 0.11, cy + 0.1, 0.98),
            (cx + 0.3 + i * 0.11, cy + 0.1, 1.1), 0.035, 0.03, seg=8)
        cyl(ctx, M, g, "product_cap", "Condiment_SyrupCap",
            (cx + 0.3 + i * 0.11, cy + 0.1, 1.1),
            (cx + 0.3 + i * 0.11, cy + 0.1, 1.14), 0.022, seg=8)
    box(ctx, M, g, "shelf", "Condiment_Tray", (cx + 0.45, cy + 0.03, 0.98),
        (0.32, 0.3, 0.025))
    # Suspended sign above the counter.
    for sx in (-0.32, 0.32):
        rod(ctx, M, g, "chrome", "Condiment_SignRod", (cx + sx, cy - 0.12, 1.62),
            (cx + sx, cy - 0.12, 1.89), 0.008, seg=5)
    box(ctx, M, g, "lightbox", "Condiment_SignBox", (cx, cy - 0.12, 1.76),
        (1.13, 0.08, 0.38))
    box(ctx, M, g, "trim_dark", "Condiment_SignFrame", (cx, cy - 0.165, 1.76),
        (1.18, 0.02, 0.42))
    plane(ctx, M, g, "condiment_sign", "Condiment_SignFace", (cx, cy - 0.179, 1.76),
          1.05, 0.35, facing="-Y")


def add_basket_stack(ctx, M):
    g = "03_Interior"
    bx, by = -1.20, -3.88
    colors = ("red", "red", "green", "red")
    for k, color in enumerate(colors):
        x = bx + (k % 2) * 0.025
        y = by + (k // 2) * 0.02
        z = 0.245 + k * 0.13
        # Base and four tapered-looking walls, with a small handle at the front.
        box(ctx, M, g, color, "Basket_Base", (x, y, z), (0.43, 0.33, 0.028))
        box(ctx, M, g, color, "Basket_WallF", (x, y - 0.155, z + 0.075),
            (0.43, 0.018, 0.15))
        box(ctx, M, g, color, "Basket_WallB", (x, y + 0.155, z + 0.075),
            (0.43, 0.018, 0.15))
        box(ctx, M, g, color, "Basket_WallL", (x - 0.205, y, z + 0.075),
            (0.018, 0.3, 0.15))
        box(ctx, M, g, color, "Basket_WallR", (x + 0.205, y, z + 0.075),
            (0.018, 0.3, 0.15))
        for sx in (-0.12, 0.12):
            box(ctx, M, g, "metal_black", "Basket_Handle", (x + sx, y - 0.162, z + 0.165),
                (0.12, 0.02, 0.025))
    box(ctx, M, g, "trim_dark", "Basket_FloorSign", (bx, by - 0.22, 0.19),
        (0.5, 0.22, 0.012))


def add_atm_machine(ctx, M):
    g = "03_Interior"
    ax, ay = 5.88, 1.95
    # Cabinet and illuminated top.
    box(ctx, M, g, "trim_dark", "ATM_Base", (ax, ay, 0.87), (0.62, 0.54, 1.34))
    box(ctx, M, g, "trim_mid", "ATM_Bezel", (ax, ay - 0.278, 1.15),
        (0.55, 0.025, 0.62))
    plane(ctx, M, g, "screen_glow", "ATM_Screen", (ax, ay - 0.293, 1.22),
          0.42, 0.28, facing="-Y")
    box(ctx, M, g, "screen_glow", "ATM_Keypad", (ax, ay - 0.292, 0.89),
        (0.34, 0.008, 0.17))
    box(ctx, M, g, "metal_black", "ATM_CardSlot", (ax + 0.19, ay - 0.292, 1.02),
        (0.12, 0.008, 0.02))
    box(ctx, M, g, "trim_dark", "ATM_Topper", (ax, ay, 1.63), (0.7, 0.48, 0.17))
    box(ctx, M, g, "lightbox", "ATM_SignBox", (ax, ay - 0.15, 1.82),
        (0.54, 0.1, 0.42))
    plane(ctx, M, g, "atm_sign", "ATM_Sign", (ax, ay - 0.206, 1.82),
          0.36, 0.36, facing="-Y")
    box(ctx, M, g, "chrome", "ATM_Stool", (ax, ay - 0.6, 0.45), (0.34, 0.34, 0.08))
    cyl(ctx, M, g, "chrome", "ATM_StoolLeg", (ax, ay - 0.6, 0.26), (ax, ay - 0.6, 0.42),
        0.045, seg=8)


def add_microwave_and_counter_details(ctx, M):
    g = "03_Interior"
    for i, x in enumerate((2.62, 3.08)):
        box(ctx, M, g, "metal_black", "Microwave", (x, 3.77, 1.67), (0.4, 0.36, 0.34))
        box(ctx, M, g, "glass_dark", "Microwave_Window", (x, 3.585, 1.68),
            (0.27, 0.012, 0.22))
        box(ctx, M, g, "warm_glow", "Microwave_Display", (x + 0.11, 3.58, 1.8),
            (0.1, 0.008, 0.03))
        box(ctx, M, g, "chrome", "Microwave_Handle", (x - 0.16, 3.57, 1.68),
            (0.02, 0.018, 0.2))
    # Tea-egg warmer and a stack of paper bags on the counter.
    cyl(ctx, M, g, "chrome", "TeaEgg_Warmer", (3.78, 3.7, 1.48),
        (3.78, 3.7, 1.72), 0.16, 0.15, seg=16)
    cyl(ctx, M, g, "glass_dark", "TeaEgg_Lid", (3.78, 3.7, 1.72),
        (3.78, 3.7, 1.76), 0.17, 0.17, seg=16)
    for i in range(3):
        L.add_sphere(ctx.b(g, M["wood"], "TeaEgg"), (3.72 + i * 0.06, 3.7, 1.6),
                     0.045, 8, 5, scale=(1, 1, 0.72))
    box(ctx, M, g, "cream", "PaperBag_Stack", (5.55, 3.75, 1.58), (0.32, 0.22, 0.2))
    box(ctx, M, g, "green", "PaperBag_Logo", (5.55, 3.635, 1.6), (0.1, 0.006, 0.07))
    # A small tray of sugar / stirrers beside the coffee machine.
    box(ctx, M, g, "shelf", "Coffee_Tray", (5.85, 3.5, 1.5), (0.28, 0.25, 0.025))
    for i in range(4):
        box(ctx, M, g, "product_label", "Coffee_Sugar", (5.77 + (i % 2) * 0.1,
            3.44 + (i // 2) * 0.09, 1.53), (0.06, 0.06, 0.06))


def add_interior_signs_and_details(ctx, M):
    g = "03_Interior"
    g2 = "02_Glazing"
    # Exit sign, seen above the doors from outside.
    box(ctx, M, g, "trim_dark", "Exit_Back", (0.4, -4.56, 3.06),
        (0.68, 0.025, 0.24))
    plane(ctx, M, g, "exit_sign", "Exit_Sign", (0.4, -4.578, 3.06),
          0.64, 0.24, facing="-Y")
    # Air curtain above the entrance.
    box(ctx, M, g, "trim_dark", "AirCurtain", (0.4, -4.45, 3.22),
        (2.3, 0.2, 0.1))
    for i in range(9):
        box(ctx, M, g, "metal_black", "AirCurtain_Slot", (-0.6 + i * 0.25, -4.45, 3.17),
            (0.13, 0.18, 0.012))
    # Street-facing store plaque on the pier beside the door.
    box(ctx, M, g, "trim_dark", "Plaque_Back", (1.92, -4.82, 2.16),
        (0.34, 0.022, 0.24))
    plane(ctx, M, g, "store_plaque", "Store_Plaque", (1.92, -4.838, 2.16),
          0.31, 0.21, facing="-Y")
    # ATM window decal, on the right pane.
    # Shelf wobblers.
    for x, z in ((-3.25, 0.89), (-4.55, 1.25)):
        box(ctx, M, g, "trim_dark", "Promo_Clip", (x, -2.30, z + 0.15),
            (0.04, 0.04, 0.03))
        plane(ctx, M, g, "promo_tag", "Promo_Tag", (x, -2.31, z + 0.02),
              0.2, 0.25, facing="-Y")


# ---------------------------------------------------------------------------
# Human scale and lived-in interior details
# ---------------------------------------------------------------------------
def add_magazine_rack(ctx, M):
    """A wall-mounted magazine/newspaper rack on the right-hand wall."""
    g = "03_Interior"
    wx = 6.16
    yc = -0.55
    # Frame and shelves.
    box(ctx, M, g, "trim_dark", "Magazine_Back", (wx, yc, 0.85), (0.045, 1.62, 1.26))
    for zz, depth, yy in ((0.43, 0.08, yc), (0.79, 0.08, yc), (1.15, 0.08, yc),
                          (1.43, 0.06, yc)):
        box(ctx, M, g, "shelf", "Magazine_Shelf", (wx - 0.13, yy, zz),
            (0.3, 1.58, 0.028))
        box(ctx, M, g, "shelf_green", "Magazine_Lip", (wx - 0.28, yy, zz + 0.035),
            (0.02, 1.58, 0.055))
    # Backlit department header.
    box(ctx, M, g, "lightbox", "Magazine_HeaderBox", (wx - 0.11, yc, 1.63),
        (0.08, 1.64, 0.41))
    b = ctx.b(g, M["magazine_sign"], "Magazine_HeaderSign", uv=True)
    x = wx - 0.153
    hw, hh = 0.76, 0.18
    corners = [(x, yc + hw, 1.63 - hh), (x, yc - hw, 1.63 - hh),
               (x, yc - hw, 1.63 + hh), (x, yc + hw, 1.63 + hh)]
    L.add_quad_uvrect(b, corners, (0, 0, 1, 1))
    # Twelve front-facing magazines on three shelves.
    start_y = -1.27
    for row, zz in enumerate((0.62, 0.98, 1.29)):
        for col in range(4):
            yy = start_y + col * 0.36
            idx = row * 11 + col * 5 + 3
            box(ctx, M, g, "trim_dark", "Magazine_Body", (wx - 0.285, yy, zz),
                (0.018, 0.28, 0.39))
            b = ctx.b(g, M["magazines"], "Magazine_Covers", uv=True)
            hw, hh = 0.135, 0.18
            x = wx - 0.296
            corners = [(x, yy + hw, zz - hh), (x, yy - hw, zz - hh),
                       (x, yy - hw, zz + hh), (x, yy + hw, zz + hh)]
            L.add_quad_uvrect(b, corners, mag_uv(idx))
    # A stack of newspapers on the bottom shelf.
    for i in range(3):
        box(ctx, M, g, "ceramic", "Newspaper_Stack", (wx - 0.25, -1.17, 1.18 + i * 0.014),
            (0.24, 0.38, 0.012))
        box(ctx, M, g, "trim_dark", "Newspaper_Line", (wx - 0.38, -1.17, 1.19 + i * 0.014),
            (0.003, 0.3, 0.002))
    add_price_tag(ctx, M, g, (wx - 0.30, -1.25, 0.93), 0.12, 0.08, 5)


def add_counter_display(ctx, M):
    g = "03_Interior"
    # Small tiered acrylic impulse display at the left end of the counter.
    cx, cy = 2.78, -2.14
    box(ctx, M, g, "glass_fridge", "Counter_Display_Back", (cx, cy + 0.06, 1.4),
        (0.3, 0.02, 0.29))
    for k, zz in enumerate((1.29, 1.37, 1.45)):
        box(ctx, M, g, "glass_fridge", "Counter_Display_Shelf", (cx, cy, zz),
            (0.3, 0.14, 0.014))
        for j in range(2):
            add_pack(ctx, M, g, (cx - 0.07 + j * 0.14, cy - 0.005, zz + 0.055),
                     (0.09, 0.055, 0.095), (11 + k * 7 + j * 3))
    box(ctx, M, g, "trim_dark", "Counter_Display_Base", (cx, cy, 1.265),
        (0.32, 0.16, 0.02))
    # Receipt roll and pen pot by the register.
    cyl(ctx, M, g, "ceramic", "Receipt_Roll", (5.34, -2.08, 1.28),
        (5.34, -2.08, 1.315), 0.035, 0.035, seg=12)
    cyl(ctx, M, g, "trim_dark", "Pen_Pot", (5.48, -2.13, 1.28),
        (5.48, -2.13, 1.38), 0.028, 0.03, seg=8)
    for i in range(3):
        cyl(ctx, M, g, "paint", "Pen", (5.47 + i * 0.012, -2.13 + i * 0.006, 1.3),
            (5.46 + i * 0.02, -2.13 + i * 0.008, 1.43), 0.004, seg=4)
    # A tiny stack of folded receipts.
    for i in range(3):
        box(ctx, M, g, "ceramic", "Receipt_Strip", (5.31, -2.2, 1.278 + i * 0.003),
            (0.075, 0.045, 0.002))


def add_ceiling_and_entrance_details(ctx, M):
    g = "03_Interior"
    # Ceiling vents, sprinklers and a smoke detector. These read mainly when
    # orbiting above the storefront but make the interior shell complete.
    for x, y in ((-3.7, 2.5), (1.0, 2.8)):
        box(ctx, M, g, "trim_mid", "Ceiling_Vent", (x, y, 3.47), (0.95, 0.52, 0.05))
        for i in range(6):
            box(ctx, M, g, "metal_black", "Vent_Slat", (x - 0.38 + i * 0.15, y, 3.438),
                (0.035, 0.42, 0.012))
    for x, y in ((-4.9, 0.4), (-1.0, 2.2), (3.0, 1.2), (5.2, 0.2)):
        cyl(ctx, M, g, "chrome", "Sprinkler", (x, y, 3.43), (x, y, 3.5), 0.012, seg=6)
        cyl(ctx, M, g, "chrome", "Sprinkler_Head", (x, y, 3.415), (x, y, 3.45), 0.035, seg=8)
    cyl(ctx, M, g, "ceramic", "Smoke_Detector", (0.4, 1.8, 3.47), (0.4, 1.8, 3.52),
        0.075, 0.06, seg=14)
    # Door-adjacent hand sanitiser stand.
    x, y = 1.93, -4.12
    cyl(ctx, M, g, "chrome", "Sanitiser_Base", (x, y, FLOOR_Z), (x, y, FLOOR_Z + 0.04),
        0.17, 0.15, seg=14)
    cyl(ctx, M, g, "chrome", "Sanitiser_Pole", (x, y, FLOOR_Z + 0.04), (x, y, 1.02),
        0.018, 0.018, seg=8)
    box(ctx, M, g, "ceramic", "Sanitiser_Tray", (x, y, 1.04), (0.24, 0.2, 0.025))
    cyl(ctx, M, g, "glass_fridge", "Sanitiser_Bottle", (x, y, 1.06), (x, y, 1.21),
        0.055, 0.05, seg=10)
    box(ctx, M, g, "ceramic", "Sanitiser_Pump", (x, y - 0.01, 1.22), (0.09, 0.06, 0.035))
    # Interior menu board next to the staff door.
    box(ctx, M, g, "trim_dark", "HotFood_Menu_Frame", (2.3, 4.385, 2.36),
        (0.64, 0.035, 0.86))
    plane(ctx, M, g, "hotfood_menu", "HotFood_Menu", (2.3, 4.36, 2.36),
          0.57, 0.79, facing="-Y")
    # A simple interior fire alarm / strobe near the entrance.
    box(ctx, M, g, "red", "Fire_Alarm", (1.45, -4.58, 3.02), (0.09, 0.035, 0.13))
    cyl(ctx, M, g, "glass_dark", "Fire_Alarm_Light", (1.45, -4.605, 3.02),
        (1.45, -4.61, 3.02), 0.026, seg=10)
    # Small barrier-free / queue marker on the floor just inside the doors.
    box(ctx, M, g, "paint_warm", "Entry_Floor_Marker", (0.4, -3.48, FLOOR_Z + 0.006),
        (1.15, 0.045, 0.003))


# ---------------------------------------------------------------------------
# Glass / interiors finishing touches, signs behind glass
# ---------------------------------------------------------------------------
def build_small_details(ctx, M):
    g = "02_Glazing"
    # A few droplets / streak decals printed on the lower glass? Intentionally
    # left to the real-time rain pass rather than baked into the texture.
    # Window stickers at the very edge of the left bay.
    box(ctx, M, g, "green", "Window_Stripe_A", (-6.14, FRONT_Y - 0.045, 3.02),
        (0.08, 0.02, 0.08))
    box(ctx, M, g, "orange", "Window_Stripe_B", (-6.02, FRONT_Y - 0.045, 3.02),
        (0.08, 0.02, 0.08))
    box(ctx, M, g, "red", "Window_Stripe_C", (-5.90, FRONT_Y - 0.045, 3.02),
        (0.08, 0.02, 0.08))
    # Potted plant / greenery outside the right corner is handled in props.
    # Thin drip flashing over the shop windows.
    box(ctx, M, g, "chrome", "Drip_Flashing", (0, FRONT_Y - 0.1, 3.36),
        (13.22, 0.08, 0.03))


# ---------------------------------------------------------------------------
# Lighting rig for the .blend
# ---------------------------------------------------------------------------
def build_lighting_and_camera(scene):
    coll = bpy.data.collections.new("Render_Environment")
    scene.collection.children.link(coll)
    # World: deep blue night with a faint city glow.
    world = bpy.data.worlds.new("Night_City")
    scene.world = world
    world.use_nodes = True
    nt = world.node_tree
    bg = nt.nodes.get("Background")
    bg.inputs["Color"].default_value = L.srgb("#0a1420")
    bg.inputs["Strength"].default_value = 0.55

    L.add_light_sun(coll, "Moon_Key", (-0.3, -0.5, 0.8), 0.22, "#9dbbd8", angle=8)
    L.add_light_sun(coll, "City_Fill", (0.55, 0.65, 0.3), 0.12, "#6f8ca8", angle=20)
    # Store interiors.
    for i, (x, y) in enumerate(((-3.8, 0.6), (0.4, -0.3), (3.8, 1.4), (-1.2, 2.8))):
        L.add_light_area(coll, f"Interior_Area_{i}", (x, y, 3.24), (x, y + 0.1, 0.2),
                         130, "#ffe4bd", size=3.0)
    L.add_light_area(coll, "Fridge_Glow", (-2.75, 3.5, 2.1), (-2.75, 0.0, 1.4),
                     75, "#d8f7ff", size=2.4)
    # Sign face illumination.
    L.add_light_area(coll, "Sign_Wash", (0, -6.5, 4.1), (0, -4.9, 4.0), 220,
                     "#fff4df", size=5.0)
    L.add_light_area(coll, "Pylon_Glow", (8.55, -8.8, 3.6), (8.55, -7.4, 3.6), 75,
                     "#fff2d8", size=1.4)
    # Canopy downlights.
    for i, x in enumerate((-1.0, 0.4, 1.8)):
        L.add_light_spot(coll, f"Canopy_Spot_{i}", (x, -5.42, 3.34), (x, -5.6, 0.2),
                         80, "#ffd39d", size_deg=58, blend=0.65, radius=0.08)
    # Streetlight.
    L.add_light_spot(coll, "Streetlight_Spot", (-9.35, -12.35, 6.72), (-9.35, -13.4, 0.0),
                     420, "#cfe7ff", size_deg=72, blend=0.55, radius=0.2)
    L.add_light_area(coll, "Street_Fill", (-5.0, -8.0, 5.2), (-2.0, -2.0, 1.0), 55,
                     "#a9c7e2", size=4.0)
    # A faint warm wash on the wet sidewalk from the storefront.
    L.add_light_area(coll, "Spill_Warm", (0.0, -5.0, 1.0), (0.0, -6.6, 0.0), 45,
                     "#ffcf97", size=5.0)

    cam = L.add_camera(coll, "CAM_Hero", (-10.35, -17.15, 5.25), (2.7, -0.35, 2.2),
                       lens=30, resolution=(1920, 1080))
    scene.camera = cam
    cam.data.dof.use_dof = False
    # Slight vertical framing refinement.
    scene.render.resolution_x = 1920
    scene.render.resolution_y = 1080
    scene.render.resolution_percentage = 100
    scene.render.film_transparent = False
    scene.render.image_settings.file_format = "PNG"
    scene.render.engine = "BLENDER_EEVEE"
    scene.eevee.taa_render_samples = 96
    scene.eevee.use_raytracing = True
    scene.eevee.use_shadows = True
    try:
        scene.eevee.ray_tracing_options.use_denoise = True
        scene.eevee.ray_tracing_options.trace_max_roughness = 0.6
    except Exception:
        pass
    scene.view_settings.view_transform = "AgX"
    scene.view_settings.look = "AgX - Medium High Contrast"
    scene.view_settings.exposure = 0.5
    return cam


# ---------------------------------------------------------------------------
# Assembly
# ---------------------------------------------------------------------------
def main():
    scene = L.clean_scene()
    random.seed(711)
    M = L.build_materials()
    ctx = L.Context()

    build_site(ctx, M)
    add_streetlight(ctx, M)
    add_utility_pole(ctx, M)
    add_tree(ctx, M, 13.8, -5.9, scale=1.0, seed=21)
    add_tree(ctx, M, -10.6, -6.2, scale=0.42, seed=77)
    add_tree(ctx, M, -14.0, 1.4, scale=0.85, seed=44)
    build_shell(ctx, M)
    build_signage(ctx, M)
    build_interior(ctx, M)
    add_slurpee_machine(ctx, M)
    add_condiment_station(ctx, M)
    add_basket_stack(ctx, M)
    add_atm_machine(ctx, M)
    add_magazine_rack(ctx, M)
    add_counter_display(ctx, M)
    add_ceiling_and_entrance_details(ctx, M)
    add_microwave_and_counter_details(ctx, M)
    add_interior_signs_and_details(ctx, M)
    build_small_details(ctx, M)
    add_street_props(ctx, M)
    add_street_furnishings(ctx, M)
    add_litter_and_stains(ctx, M)
    add_pedestrian_light(ctx, M)
    add_side_alley_clutter(ctx, M)
    add_bicycle(ctx, M)
    add_bike_parking_sign(ctx, M)
    add_stock_step_stool(ctx, M)
    add_scooter(ctx, M)

    ctx.finish()

    # Give the major architecture and street furniture a tiny bevel. Razor-sharp
    # CG edges are one of the strongest "game asset" tells; a 1.2 cm chamfer
    # catches highlights and makes the store read as built rather than extruded.
    soft_edge_prefixes = (
        "01_Shell_Wall", "01_Shell_Parapet", "01_Shell_Canopy",
        "01_Shell_Pier", "01_Shell_Window_Base", "01_Shell_Facade_Header",
        "01_Shell_Door_", "01_Shell_Base_Skirting", "01_Shell_Roof_AC",
        "01_Shell_Roof_Slab", "01_Shell_Roof_Hatch", "01_Shell_Service_Door",
        "01_Shell_Foundation", "01_Shell_AC_",
        "01_Shell_Corner_Trim", "01_Shell_Utility_Meter", "01_Shell_Parapet_Cap",
        "04_Signage_Fascia_Box", "04_Signage_Fascia_Frame",
        "04_Signage_Pylon_Box", "04_Signage_Pylon_Post", "04_Signage_Pylon_Cap",
        "04_Signage_Pylon_Base_Cap", "04_Signage_Pylon_Trim",
        "00_Site_Bench", "00_Site_Newspaper", "00_Site_Utility_Cabinet",
        "00_Site_Planter", "00_Site_Ice_", "00_Site_Bins", "00_Site_Side_",
        "00_Site_Mop", "00_Site_Hydrant", "00_Site_Tactile",
        "03_Interior_Counter_", "03_Interior_Back_Counter", "03_Interior_ATM_",
        "03_Interior_Bench", "03_Interior_Lining", "03_Interior_Magazine_",
    )
    soft_edge_skip = ("Glass", "Lens", "LED", "Cove", "Decal", "Face",
                      "Label", "Lamp", "Light", "Hinge", "Paper",
                      "Stripe", "Handle", "Rail", "Slot", "Vent")
    import math as _math
    for obj in list(bpy.data.objects):
        if obj.type != "MESH":
            continue
        n = obj.name
        if not any(n.startswith(prefix) or prefix in n for prefix in soft_edge_prefixes):
            continue
        if any(skip in n for skip in soft_edge_skip):
            continue
        if max(obj.dimensions) < 0.12 or min(obj.dimensions) < 0.004:
            continue
        try:
            bpy.ops.object.select_all(action="DESELECT")
            obj.select_set(True)
            bpy.context.view_layer.objects.active = obj
            mod = obj.modifiers.new("Soft_Edges", "BEVEL")
            mod.width = 0.012
            mod.segments = 2
            mod.limit_method = "ANGLE"
            mod.angle_limit = _math.radians(50)
            mod.use_clamp_overlap = True
            bpy.ops.object.modifier_apply(modifier=mod.name)
        except Exception as exc:
            print("BEVEL_SKIP", n, exc)

    # Group the two sliding leaves under dedicated empties. The viewer uses
    # these nodes to animate the complete leaf (glass, stiles, handle, seal).
    door_roots = []
    for emp_name, prefix in (("Door_Leaf_Left", "01_Shell_DoorLeafL_"),
                              ("Door_Leaf_Right", "01_Shell_DoorLeafR_")):
        emp = bpy.data.objects.new(emp_name, None)
        emp.empty_display_type = "PLAIN_AXES"
        emp.empty_display_size = 0.25
        ctx.coll("01_Shell").objects.link(emp)
        for obj in list(bpy.data.objects):
            if obj.type == "MESH" and obj.name.startswith(prefix):
                mw = obj.matrix_world.copy()
                obj.parent = emp
                obj.matrix_parent_inverse = emp.matrix_world.inverted()
                obj.matrix_world = mw
        door_roots.append(emp)

    # Parent the whole asset to a single root empty.
    root_coll = ctx.coll("Seven_Eleven_ROOT")
    root = L.add_empty("Seven_Eleven_STORE_ROOT", root_coll)
    for obj in list(bpy.data.objects):
        if obj is root:
            continue
        if obj.type in {"MESH", "EMPTY"} and obj.parent is None:
            obj.parent = root
    bpy.context.view_layer.update()

    # Report geometry stats.
    meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    tris = sum(sum(len(p.vertices) - 2 for p in o.data.polygons) for o in meshes)
    verts = sum(len(o.data.vertices) for o in meshes)
    mn = Vector((1e9, 1e9, 1e9))
    mx = Vector((-1e9, -1e9, -1e9))
    for o in meshes:
        for c in o.bound_box:
            w = o.matrix_world @ Vector(c)
            for i in range(3):
                mn[i] = min(mn[i], w[i])
                mx[i] = max(mx[i], w[i])
    print(f"BOUNDS min={tuple(round(v, 2) for v in mn)} max={tuple(round(v, 2) for v in mx)}")
    print(f"MESHES {len(meshes)}; VERTS {verts}; TRIS {tris}")
    scene["model_name"] = "7-Eleven Corner Store"
    scene["model_units"] = "metres"
    scene["design_note"] = (
        "Procedural, stylised 7-Eleven corner store and Taipei-inspired street. "
        "Trademarks belong to 7-Eleven, Inc. This is an independent artistic study."
    )
    scene["default_web_mode"] = "night"

    # Pack every generated image into the .blend so both files travel alone.
    try:
        bpy.ops.file.pack_all()
    except Exception as exc:
        print("PACK_WARN", exc)
    asset_path = ROOT / "build" / "seven_eleven_store_asset.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(asset_path))
    print("SAVED", asset_path)

    # Build a lit scene around the same geometry.
    build_lighting_and_camera(scene)
    try:
        bpy.ops.file.pack_all()
    except Exception as exc:
        print("PACK_WARN", exc)
    full_path = ROOT / "seven_eleven_store.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(full_path))
    print("SAVED", full_path)


if __name__ == "__main__":
    main()
