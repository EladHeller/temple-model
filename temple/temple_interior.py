"""Cutaway interior of the Second Temple sanctuary, with sacred vessels.

The scene is a companion to temple_middot.py and is intentionally roofless
and open on the south so that the interior can be inspected in a web viewer.

Interior cutaway coordinates use +Y = south and -Y = north. This mirrors the
standalone cutaway toward its open viewing side; +X remains west.

Run:
    blender --background --python temple_interior.py -- \
        --save temple_middot_interior.blend \
        --export temple_middot_interior.glb --render
"""

from __future__ import annotations

import argparse
import math
import os
import sys
from pathlib import Path

import bpy
from mathutils import Vector

# Blender does not always add the script folder to sys.path in background mode.
SCRIPT_DIR = str(Path(__file__).resolve().parent)
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

import temple_middot as base


ARCH = "20 פנים ההיכל – אדריכלות"
VESSELS = "21 כלי הקודש"
CURTAINS = "22 הפרוכות"
LABELS = "23 תוויות פנים"
LIGHTS = "24 תאורה ומצלמה"


def interior_label(
    text: str, x: float, y: float, z: float, size: float = 2.5
) -> bpy.types.Object:
    """Place floor text so it is upright from the open southern wall."""
    obj = base.label(text, x, y, z, size)
    obj.rotation_euler.z = math.pi
    return obj


def add_between(
    name: str,
    start: tuple[float, float, float],
    end: tuple[float, float, float],
    radius: float,
    material_name: str = "Gold",
    group: str = VESSELS,
    vertices: int = 24,
) -> bpy.types.Object:
    """Create a cylinder between two cubit-space points."""
    start_v = Vector(tuple(base.m(value) for value in start))
    end_v = Vector(tuple(base.m(value) for value in end))
    direction = end_v - start_v
    midpoint = (start_v + end_v) / 2
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=vertices,
        radius=base.m(radius),
        depth=direction.length,
        location=midpoint,
    )
    obj = bpy.context.object
    obj.name = name
    obj.data.name = name
    obj.rotation_mode = "QUATERNION"
    obj.rotation_quaternion = direction.to_track_quat("Z", "Y")
    obj.data.materials.append(base.MATERIALS[material_name])
    base.move_to_collection(obj, group)
    return obj


def add_frustum(
    name: str,
    radius_bottom: float,
    radius_top: float,
    depth: float,
    location: tuple[float, float, float],
    material_name: str = "Gold",
    group: str = VESSELS,
    vertices: int = 32,
) -> bpy.types.Object:
    """Create a truncated cone for a pedestal or flared menorah cup."""
    bpy.ops.mesh.primitive_cone_add(
        vertices=vertices,
        radius1=base.m(radius_bottom),
        radius2=base.m(radius_top),
        depth=base.m(depth),
        location=tuple(base.m(value) for value in location),
    )
    obj = bpy.context.object
    obj.name = name
    obj.data.name = name
    obj.data.materials.append(base.MATERIALS[material_name])
    base.move_to_collection(obj, group)
    return obj


def add_curved_branch(
    name: str,
    start: tuple[float, float, float],
    end: tuple[float, float, float],
    radius: float,
    material_name: str = "Gold",
    group: str = VESSELS,
) -> bpy.types.Object:
    """Create a smooth, round tube between two menorah branch points."""
    start_v = Vector(tuple(base.m(value) for value in start))
    end_v = Vector(tuple(base.m(value) for value in end))
    horizontal = end_v.x - start_v.x
    vertical = end_v.z - start_v.z

    curve = bpy.data.curves.new(name, type="CURVE")
    curve.dimensions = "3D"
    curve.resolution_u = 24
    curve.bevel_depth = base.m(radius)
    curve.bevel_resolution = 5
    curve.resolution_v = 5
    curve.use_fill_caps = True

    spline = curve.splines.new(type="BEZIER")
    spline.bezier_points.add(1)
    lower, upper = spline.bezier_points
    lower.co = start_v
    upper.co = end_v
    # The lower handle lets the branch open gently from the central stem;
    # the upper handle is vertical so every lamp sits on a rounded upright end.
    lower.handle_left_type = "FREE"
    lower.handle_right_type = "FREE"
    lower.handle_left = start_v
    lower.handle_right = start_v + Vector((horizontal * 0.52, 0, vertical * 0.06))
    upper.handle_left_type = "FREE"
    upper.handle_right_type = "FREE"
    upper.handle_left = end_v - Vector((0, 0, vertical * 0.54))
    upper.handle_right = end_v

    obj = bpy.data.objects.new(name, curve)
    curve.materials.append(base.MATERIALS[material_name])
    base.move_to_collection(obj, group)
    return obj


def add_cutaway_architecture() -> None:
    # The cutaway now begins at the Hall: its full 100-cubit width is retained,
    # while the upper half and south wall remain open for inspection.
    hall_facade_x = -42.0
    heikhal_front_x = -26.0
    base.box("רצפת האולם", (16, 100, 0.5), (-34, 0, -0.25),
             "Pale court stone", ARCH)
    base.building_wall_with_gate(
        "חזית האולם בחתך", -39.5, 0, 100, 5, 46, 0, 20, 40, ARCH
    )
    base.box("כותל האולם הצפוני", (16, 5, 46), (-34, -47.5, 23),
             "Jerusalem limestone", ARCH)
    base.box("כותל האולם הדרומי – חתך", (16, 2, 2), (-34, 49, 1),
             "Assumed element", ARCH)
    for index in range(12):
        remaining = 12 - index
        base.box(f"מעלת האולם בחתך {index + 1:02d}",
                 (remaining, 60, 0.5),
                 (hall_facade_x - remaining / 2, 0, index * 0.5 + 0.25),
                 "Pale court stone", ARCH)
    base.add_hall_facade_details(hall_facade_x, 0, 0, 46, ARCH)
    base.add_hall_interior_details(hall_facade_x, heikhal_front_x, 0, 0, ARCH)

    # Middot 4:7: 40-cubit Holy Place, 1-cubit Traksin, 20-cubit Holy of Holies.
    base.box("רצפת ההיכל", (73, 32, 0.5), (10.5, 0, -0.25),
             "Pale court stone", ARCH)
    base.box("הכותל הצפוני", (73, 6, 40), (10.5, -13, 20),
             "Jerusalem limestone", ARCH)
    base.box("הכותל המערבי", (6, 32, 40), (44, 0, 20),
             "Jerusalem limestone", ARCH)
    # Low south wall preserves the footprint without obscuring the cutaway.
    base.box("הכותל הדרומי – חתך", (73, 2, 2), (10.5, 15, 1),
             "Assumed element", ARCH)

    # The eastern wall and its 10 x 20 cubit opening.
    base.building_wall_with_gate(
        "פתח ההיכל", -23, 0, 32, 6, 40, 0, 10, 20, ARCH
    )

    # Gold plating on the inner stone walls, divided into readable panels.
    base.box("חיפוי זהב צפוני", (61, 0.10, 38), (10.5, -9.94, 19),
             "Gold", ARCH)
    base.box("חיפוי זהב מערבי", (0.10, 20, 38), (40.94, 0, 19),
             "Gold", ARCH)
    for panel_x in range(-18, 42, 6):
        base.box("מסגרת לוח זהב צפוני", (0.12, 0.08, 37),
                 (panel_x, -9.86, 19), "Bronze", ARCH)
    for panel_y in range(-8, 9, 4):
        base.box("מסגרת לוח זהב מערבי", (0.08, 0.12, 37),
                 (40.86, panel_y, 19), "Bronze", ARCH)

    # Slab joints make the stone floor scale visible in the close-up model.
    for floor_x in range(-40, 46, 5):
        base.box("מישק רצפת האבן", (0.08, 30, 0.025),
                 (floor_x, 0, 0.02), "Grout", ARCH)
    for floor_y in range(-9, 10, 3):
        base.box("מישק רצפת האבן", (70, 0.08, 0.025),
                 (10.5, floor_y, 0.02), "Grout", ARCH)

    # Yoma 5:1: two curtains stood on the two sides of the one-cubit Traksin.
    # The outer/eastern curtain opened at the south; the inner/western one
    # opened at the north, creating a bent route through the space between.
    # The 1.5-cubit opening depth is schematic because the source names each
    # end but does not give the size of the opening.
    curtain_thickness = 0.12
    curtain_height = 38.0
    opening_depth = 1.5
    room_south = 10.0
    room_north = -10.0
    curtain_length = 20.0 - opening_depth

    # Outer curtain: from the north wall to the southern opening.
    outer_x = 20.0
    outer_end_y = room_south - opening_depth
    base.box("הפרוכת החיצונית – פתח דרומי",
             (curtain_thickness, curtain_length, curtain_height),
             (outer_x, (room_north + outer_end_y) / 2, curtain_height / 2),
             "Curtain", CURTAINS)
    # A short return makes the southern fold legible without blocking the
    # one-cubit passage; it folds eastward, back into the Holy Place.
    base.box("קפל הפרוכת החיצונית בדרום", (0.35, curtain_thickness, curtain_height),
             (outer_x - 0.175, outer_end_y, curtain_height / 2),
             "Curtain", CURTAINS)

    # Inner curtain: from the northern opening to the south wall.
    inner_x = 21.0
    inner_start_y = room_north + opening_depth
    base.box("הפרוכת הפנימית – פתח צפוני",
             (curtain_thickness, curtain_length, curtain_height),
             (inner_x, (inner_start_y + room_south) / 2, curtain_height / 2),
             "Curtain", CURTAINS)
    # The matching northern fold turns westward into the Holy of Holies.
    base.box("קפל הפרוכת הפנימית בצפון", (0.35, curtain_thickness, curtain_height),
             (inner_x + 0.175, inner_start_y, curtain_height / 2),
             "Curtain", CURTAINS)

    # Narrow woven bands evoke the blue, scarlet and purple threads without
    # claiming a unique reconstructed pattern.
    stripe_mats = ("תכלת", "שני", "ארגמן")
    for curtain_index, (curtain_x, start_y) in enumerate(
        ((outer_x - 0.075, room_north), (inner_x + 0.075, inner_start_y)), 1
    ):
        for stripe_index in range(12):
            stripe_y = start_y + 0.75 + stripe_index * (curtain_length - 1.5) / 11
            base.box(f"פס ארוג בפרוכת {curtain_index}-{stripe_index + 1}",
                     (0.025, 0.28, curtain_height - 1.0),
                     (curtain_x, stripe_y, curtain_height / 2),
                     stripe_mats[stripe_index % len(stripe_mats)], CURTAINS)

    # Full-width rails emphasize that these are two distinct curtain planes.
    for name, x in (("חיצונית", outer_x), ("פנימית", inner_x)):
        add_between(f"מוט הפרוכת ה{name}", (x, room_north, 38.5),
                    (x, room_south, 38.5), 0.10, "Gold", CURTAINS)

    interior_label("הקודש – 40×20 אמה", 0, 0, 0.05, 1.25)
    interior_label("האולם – 11 אמה", -33.5, 0, 0.05, 1.15)
    interior_label("פתח האולם 20×40", -45.0, 0, 0.05, 0.85)
    interior_label("אמה טרקסין", 20.5, 0, 0.05, 0.85)
    # Keep the room title north of the foundation stone so the two labels do
    # not overlap in the overhead/web view.
    interior_label("קודש הקודשים – 20×20 אמה", 31, -6, 0.05, 1.1)
    interior_label("צפון", -18, -13.5, 0.05, 0.85)
    interior_label("דרום", -18, 13.5, 0.05, 0.85)


def add_golden_altar() -> None:
    # Exodus 30:2: one cubit square and two cubits high.
    x, y = -9.0, 0.0
    base.box("מזבח הזהב", (1, 1, 2), (x, y, 1), "Gold", VESSELS, 0.04)
    for dx in (-0.4, 0.4):
        for dy in (-0.4, 0.4):
            base.box("קרן מזבח הזהב", (0.16, 0.16, 0.22),
                     (x + dx, y + dy, 2.11), "Gold", VESSELS, 0.02)
    # Crown around the top.
    for yy in (-0.53, 0.53):
        add_between("זר מזבח הזהב", (x - 0.53, y + yy, 2.05),
                    (x + 0.53, y + yy, 2.05), 0.045)
    for xx in (-0.53, 0.53):
        add_between("זר מזבח הזהב", (x + xx, y - 0.53, 2.05),
                    (x + xx, y + 0.53, 2.05), 0.045)
    base.box("גחלי מזבח הקטורת", (0.72, 0.72, 0.08),
             (x, y, 2.08), "Ash", VESSELS, 0.08)
    for coal_x, coal_y in ((-0.22, -0.18), (0.20, -0.08),
                           (-0.05, 0.18), (0.24, 0.22)):
        base.sphere("גחל קטורת", 0.10, (x + coal_x, y + coal_y, 2.17),
                    "Ember", VESSELS, scale=(1.0, 0.8, 0.55), subdivisions=2)
    for side in (-1, 1):
        base.torus("טבעת מזבח הזהב", 0.13, 0.035,
                   (x, y + side * 0.54, 1.55), "Gold", VESSELS,
                   rotation=(math.pi / 2, 0, 0))
    interior_label("מזבח הזהב", x, y + 1.45, 0.06, 0.7)


def add_showbread_table() -> None:
    # Exodus 25:23: 2 x 1 cubits and 1.5 cubits high; north of the Menorah.
    x, y = 1.0, -6.0
    base.box("משטח שולחן לחם הפנים", (2, 1, 0.16),
             (x, y, 1.42), "Gold", VESSELS, 0.04)
    for dx in (-0.82, 0.82):
        for dy in (-0.34, 0.34):
            base.box("רגל שולחן לחם הפנים", (0.13, 0.13, 1.35),
                     (x + dx, y + dy, 0.675), "Gold", VESSELS, 0.025)
    for yy in (-0.54, 0.54):
        add_between("זר השולחן", (x - 1.02, y + yy, 1.57),
                    (x + 1.02, y + yy, 1.57), 0.045)
    for xx in (-1.02, 1.02):
        add_between("זר השולחן", (x + xx, y - 0.54, 1.57),
                    (x + xx, y + 0.54, 1.57), 0.045)

    # Four upright frames and transverse supports represent the qesawot and
    # menaqqiyyot that supported the two bread stacks.
    for support_x in (x - 0.92, x + 0.92):
        for support_y in (y - 0.48, y + 0.48):
            add_between("קשות השולחן", (support_x, support_y, 1.5),
                        (support_x, support_y, 2.55), 0.035)
    for level in range(6):
        support_z = 1.64 + level * 0.12
        for stack_x in (x - 0.55, x + 0.55):
            add_between("מנקיות השולחן", (stack_x - 0.37, y - 0.40, support_z),
                        (stack_x - 0.37, y + 0.40, support_z), 0.025)
            add_between("מנקיות השולחן", (stack_x + 0.37, y - 0.40, support_z),
                        (stack_x + 0.37, y + 0.40, support_z), 0.025)

    # Two stacks of six loaves; their detailed curvature is schematic.
    for stack_x in (x - 0.55, x + 0.55):
        for level in range(6):
            base.box("לחם הפנים", (0.72, 0.62, 0.10),
                     (stack_x, y, 1.57 + level * 0.12),
                     "לחם הפנים", VESSELS, 0.035)
    # Small golden service vessels stand at the ends of the table.
    for vessel_x, vessel_name in ((x - 0.86, "קערת השולחן"),
                                  (x + 0.86, "כף לבונה")):
        base.cylinder(vessel_name, 0.16, 0.08, (vessel_x, y, 1.66),
                      "Gold", VESSELS, 24)
        base.torus(f"שפת {vessel_name}", 0.16, 0.025,
                   (vessel_x, y, 1.71), "Gold", VESSELS)
    interior_label("שולחן לחם הפנים", x, y + 1.45, 0.06, 0.7)


def add_menorah() -> None:
    # Menachot 28b: 18 handbreadths = 3 six-handbreadth cubits high.
    x, y = 1.0, 6.0
    # The 18-handbreadth height is retained from the source.  The silhouette
    # and ornamental rhythm follow the Temple Institute reconstruction: a
    # polygonal stepped base, rounded U branches, and repeated almond-like
    # cups, knobs and flowers beneath seven shallow oil lamps.
    base.cylinder("מדרגת בסיס תחתונה", 0.64, 0.10, (x, y, 0.05),
                  "Gold", VESSELS, 6)
    base.cylinder("מדרגת בסיס אמצעית", 0.55, 0.10, (x, y, 0.15),
                  "Gold", VESSELS, 6)
    base.cylinder("בסיס מעוטר", 0.47, 0.18, (x, y, 0.29),
                  "Gold", VESSELS, 6)
    base.cylinder("שפת בסיס עליונה", 0.50, 0.05, (x, y, 0.405),
                  "Gold", VESSELS, 6)
    add_frustum("רגל המנורה המדורגת", 0.27, 0.15, 0.30,
                (x, y, 0.58), vertices=32)
    base.torus("חישוק רגל המנורה", 0.15, 0.028,
               (x, y, 0.74), "Gold", VESSELS)
    add_between("הקנה המרכזי", (x, y, 0.70), (x, y, 2.38), 0.072)

    branch_specs = (
        (1.05, 1.55),  # the widest pair leaves the stem lowest
        (1.39, 1.08),
        (1.73, 0.59),
    )
    lamp_x_positions = [x]
    for pair_index, (join_z, spread) in enumerate(branch_specs, 1):
        base.sphere(f"כפתור זוג קנים {pair_index}", 0.13,
                    (x, y, join_z), "Gold", VESSELS,
                    scale=(1.05, 1.05, 0.78), subdivisions=2)
        base.torus(f"חישוק זוג קנים {pair_index}", 0.12, 0.022,
                   (x, y, join_z + 0.09), "Gold", VESSELS)
        for direction in (-1, 1):
            lamp_x = x + direction * spread
            add_curved_branch(f"קנה המנורה {pair_index}-{direction:+d}",
                              (x, y, join_z), (lamp_x, y, 2.38), 0.064)
            lamp_x_positions.append(lamp_x)

    base.sphere("פרח תחתון בקנה המרכזי", 0.16, (x, y, 0.86),
                "Gold", VESSELS, scale=(1.30, 1.30, 0.42), subdivisions=2)
    base.torus("חישוק הפרח התחתון", 0.14, 0.025,
               (x, y, 0.91), "Gold", VESSELS)

    for lamp_index, lamp_x in enumerate(sorted(lamp_x_positions), 1):
        base.sphere(f"כפתור קנה {lamp_index}", 0.12,
                    (lamp_x, y, 2.39), "Gold", VESSELS,
                    scale=(1.10, 1.10, 0.70), subdivisions=2)
        add_frustum(f"גביע תחתון {lamp_index}", 0.09, 0.15, 0.12,
                    (lamp_x, y, 2.49), vertices=24)
        base.torus(f"שפת גביע תחתון {lamp_index}", 0.145, 0.018,
                   (lamp_x, y, 2.55), "Gold", VESSELS)
        base.sphere(f"פרח אמצעי {lamp_index}", 0.145,
                    (lamp_x, y, 2.62), "Gold", VESSELS,
                    scale=(1.22, 1.22, 0.42), subdivisions=2)
        add_frustum(f"גביע אמצעי {lamp_index}", 0.09, 0.15, 0.12,
                    (lamp_x, y, 2.72), vertices=24)
        base.torus(f"שפת גביע אמצעי {lamp_index}", 0.145, 0.018,
                   (lamp_x, y, 2.78), "Gold", VESSELS)
        base.sphere(f"פרח עליון {lamp_index}", 0.14,
                    (lamp_x, y, 2.84), "Gold", VESSELS,
                    scale=(1.20, 1.20, 0.40), subdivisions=2)

        # Shallow elongated bowls, visible oil and wicks replace candle forms.
        base.sphere(f"קערת נר {lamp_index}", 0.17,
                    (lamp_x, y, 2.93), "Gold", VESSELS,
                    scale=(1.24, 0.84, 0.32), subdivisions=2)
        rim = base.torus(f"שפת נר {lamp_index}", 0.155, 0.018,
                         (lamp_x, y, 2.955), "Gold", VESSELS)
        rim.scale = (1.24, 0.84, 1.0)
        base.cylinder(f"שמן זית בנר {lamp_index}", 0.105, 0.014,
                      (lamp_x, y, 2.972), "Olive oil", VESSELS, 24)
        base.cylinder(f"פתילת נר {lamp_index}", 0.023, 0.09,
                      (lamp_x, y, 3.01), "Hair and soot", VESSELS, 16)
        base.sphere(f"להבת נר {lamp_index}", 0.075,
                    (lamp_x, y, 3.13), "אור הנרות", VESSELS,
                    scale=(0.62, 0.62, 1.65), subdivisions=2)
    interior_label("המנורה", x, y + 1.3, 0.06, 0.7)


def add_foundation_stone() -> None:
    # Mishnah Yoma 5:2: three fingerbreadths above the floor; footprint unknown.
    x, y = 31.0, 0.0
    bpy.ops.mesh.primitive_ico_sphere_add(
        subdivisions=3,
        radius=1,
        location=(base.m(x), base.m(y), base.m(0.12)),
    )
    stone = bpy.context.object
    stone.name = "אבן השתייה"
    stone.data.name = stone.name
    stone.scale = (base.m(2.4), base.m(1.7), base.m(0.18))
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    stone.data.materials.append(base.MATERIALS["אבן השתייה"])
    base.move_to_collection(stone, VESSELS)
    base.cylinder("מחתת יום הכיפורים", 0.32, 0.10, (x, y, 0.38),
                  "Gold", VESSELS, 32)
    interior_label("אבן השתייה", x, y + 2.2, 0.06, 0.75)


def setup_interior_camera() -> None:
    world = bpy.context.scene.world
    world.color = (0.035, 0.04, 0.055)
    world.use_nodes = True
    background = world.node_tree.nodes.get("Background")
    background.inputs["Color"].default_value = (0.035, 0.04, 0.055, 1)
    background.inputs["Strength"].default_value = 0.32

    bpy.ops.object.light_add(type="AREA", location=(base.m(-5), base.m(14), base.m(28)))
    key = bpy.context.object
    key.name = "תאורה ראשית"
    key.data.name = key.name
    key.data.energy = 1800
    key.data.shape = "RECTANGLE"
    key.data.size = base.m(26)
    key.data.size_y = base.m(14)
    key.rotation_euler = (math.radians(24), 0, 0)
    base.move_to_collection(key, LIGHTS)

    bpy.ops.object.light_add(type="AREA", location=(base.m(27), 0, base.m(16)))
    fill = bpy.context.object
    fill.name = "תאורת קודש הקודשים"
    fill.data.name = fill.name
    fill.data.energy = 900
    fill.data.color = (1.0, 0.68, 0.35)
    fill.data.size = base.m(12)
    fill.rotation_euler = (0, math.radians(-90), 0)
    base.move_to_collection(fill, LIGHTS)

    bpy.ops.object.camera_add(location=(base.m(-18), base.m(84), base.m(50)))
    camera = bpy.context.object
    camera.name = "מצלמת פנים ההיכל"
    camera.data.name = camera.name
    target = Vector((base.m(0), 0, base.m(9)))
    camera.rotation_euler = (target - camera.location).to_track_quat("-Z", "Y").to_euler()
    camera.data.lens = 54
    base.move_to_collection(camera, LIGHTS)

    scene = bpy.context.scene
    scene.camera = camera
    try:
        scene.render.engine = "BLENDER_EEVEE_NEXT"
    except TypeError:
        scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x = 1600
    scene.render.resolution_y = 1000
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.filepath = os.path.abspath("temple_middot_interior_preview.png")


def build_interior() -> None:
    # Interior coordinates are authored directly in Blender's right-handed
    # scene basis: +X west, +Y south, -Y north.
    base.MIRROR_PLAN_Y = False
    base.clear_scene()
    base.add_materials()
    base.material("לחם הפנים", (0.67, 0.35, 0.10, 1), roughness=0.72)
    base.material("אבן השתייה", (0.23, 0.22, 0.20, 1), roughness=0.96)
    base.material("אור הנרות", (1.0, 0.28, 0.025, 1), metallic=0.05, roughness=0.25)
    base.material("Grout", (0.20, 0.18, 0.15, 1), roughness=0.95)
    base.material("תכלת", (0.035, 0.22, 0.62, 1), roughness=0.78)
    base.material("שני", (0.62, 0.025, 0.018, 1), roughness=0.78)
    base.material("ארגמן", (0.36, 0.025, 0.42, 1), roughness=0.78)
    for name in (ARCH, VESSELS, CURTAINS, LABELS, LIGHTS):
        base.collection(name)
    # Labels created by the shared helper go into its translated label group.
    base.collection("00 Labels")

    add_cutaway_architecture()
    add_golden_altar()
    add_showbread_table()
    add_menorah()
    add_foundation_stone()
    setup_interior_camera()

    scene = bpy.context.scene
    scene["model_title"] = "פנים בית המקדש השני לפי מקורות חז״ל"
    scene["accuracy_note"] = (
        "מידות החללים והכלים מבוססות מקורות; עיצוב הפרטים, רוחב המנורה "
        "וצורת אבן השתייה סכמטיים. בית שני מוצג ללא ארון."
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--save", default="")
    parser.add_argument("--export", default="")
    parser.add_argument("--render", action="store_true")
    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    return parser.parse_args(args)


def finish(args: argparse.Namespace) -> None:
    if args.render:
        bpy.ops.render.render(write_still=True)
    if args.save:
        bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(args.save))
    if args.export:
        bpy.ops.export_scene.gltf(
            filepath=os.path.abspath(args.export), export_format="GLB"
        )


if __name__ == "__main__":
    build_interior()
    finish(parse_args())
