"""Procedural study model of the wilderness Tabernacle (Mishkan).

Primary sources: Exodus 25--30 and 35--40.  The 30 x 10 cubit footprint,
20/10 cubit inner division, one-cubit board thickness and vessel positions
follow the rabbinic/traditional reconstruction summarized in Hebrew
Wikipedia's "The Tabernacle" article.

Run from this directory with Blender 4.2 or later:

    blender --background --python tabernacle.py -- \
      --save tabernacle.blend --export tabernacle.glb --render

Add ``--interior`` to create the open cutaway companion model.  All source
measurements are in cubits; one cubit is represented as 0.5 metres.
"""

from __future__ import annotations

import argparse
import math
import os
import sys

import bpy
from mathutils import Vector


CUBIT_M = 0.5

SOURCE = {
    "courtyard": (100.0, 50.0, 5.0),       # Exodus 27:9-18
    "courtyard_gate": 20.0,                # Exodus 27:16
    "tabernacle": (30.0, 10.0, 10.0),      # traditional reconstruction
    "board": (1.5, 1.0, 10.0),             # Exodus 26:16; Shabbat 98b
    "inner_curtain": (28.0, 4.0, 10),      # Exodus 26:1-2
    "goat_curtain": (30.0, 4.0, 11),       # Exodus 26:7-8
    "altar": (5.0, 5.0, 3.0),              # Exodus 27:1
    "ark": (2.5, 1.5, 1.5),                # Exodus 25:10
    "table": (2.0, 1.0, 1.5),              # Exodus 25:23
    "incense_altar": (1.0, 1.0, 2.0),      # Exodus 30:2
}

# The text gives no dimensions for these items or construction details.
ASSUMED = {
    "laver_size": 1.35,
    "cover_thickness": 0.10,
    "curtain_thickness": 0.08,
    "post_radius": 0.14,
    "cherub_form": "schematic winged figures",
    "lamp_height": 3.0,
    # Hebrew Wikipedia describes a ramp and a projecting foundation for the
    # wilderness altar but supplies no plan dimensions for either.
    "altar_foundation_projection": 0.30,
    "altar_ramp_length": 8.0,
    "altar_ramp_width": 2.5,
}

MATERIALS: dict[str, bpy.types.Material] = {}
COLLECTIONS: dict[str, bpy.types.Collection] = {}


def m(value: float) -> float:
    return value * CUBIT_M


def clear_scene() -> None:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for blocks in (bpy.data.meshes, bpy.data.curves, bpy.data.materials,
                   bpy.data.cameras, bpy.data.lights):
        for block in list(blocks):
            if block.users == 0:
                blocks.remove(block)
    for child in list(bpy.context.scene.collection.children):
        bpy.context.scene.collection.children.unlink(child)
    MATERIALS.clear()
    COLLECTIONS.clear()


def collection(name: str) -> bpy.types.Collection:
    if name not in COLLECTIONS:
        group = bpy.data.collections.new(name)
        bpy.context.scene.collection.children.link(group)
        COLLECTIONS[name] = group
    return COLLECTIONS[name]


def move_to(obj: bpy.types.Object, group: str) -> bpy.types.Object:
    target = collection(group)
    for current in list(obj.users_collection):
        current.objects.unlink(obj)
    target.objects.link(obj)
    return obj


def material(name: str, color: tuple[float, float, float, float], *,
             metallic: float = 0.0, roughness: float = 0.65,
             emission: tuple[float, float, float, float] | None = None,
             emission_strength: float = 0.0) -> bpy.types.Material:
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = color
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = color
    bsdf.inputs["Metallic"].default_value = metallic
    bsdf.inputs["Roughness"].default_value = roughness
    if emission:
        bsdf.inputs["Emission Color"].default_value = emission
        bsdf.inputs["Emission Strength"].default_value = emission_strength
    MATERIALS[name] = mat
    return mat


def add_materials() -> None:
    material("חול המדבר", (0.43, 0.29, 0.15, 1), roughness=0.98)
    material("שש משזר", (0.88, 0.82, 0.68, 1), roughness=0.9)
    material("תכלת", (0.08, 0.28, 0.62, 1), roughness=0.72)
    material("ארגמן", (0.33, 0.035, 0.36, 1), roughness=0.72)
    material("תולעת שני", (0.68, 0.035, 0.025, 1), roughness=0.72)
    # Artistic reconstruction only: the Torah names the constituent coloured
    # threads but does not specify one uniform ground colour for the finished
    # textile. A deep blue-purple ground makes the raised embroidery legible.
    material("אריג כחול־ארגמני – שחזור משוער", (0.045, 0.055, 0.16, 1),
             roughness=0.86)
    material("עיזים", (0.17, 0.14, 0.11, 1), roughness=0.95)
    material("עורות אילים מאדמים", (0.42, 0.045, 0.025, 1), roughness=0.88)
    material("עורות תחשים – גוון סכמטי", (0.11, 0.25, 0.30, 1), roughness=0.82)
    material("עצי שיטים", (0.34, 0.13, 0.035, 1), roughness=0.68)
    material("זהב", (0.88, 0.55, 0.07, 1), metallic=0.9, roughness=0.2)
    material("כסף", (0.72, 0.76, 0.80, 1), metallic=0.92, roughness=0.18)
    material("נחושת", (0.48, 0.21, 0.055, 1), metallic=0.72, roughness=0.3)
    material("מים", (0.05, 0.30, 0.52, 1), metallic=0.05, roughness=0.12)
    material("לחם הפנים", (0.63, 0.31, 0.07, 1), roughness=0.82)
    material("כהה", (0.018, 0.012, 0.008, 1), roughness=1.0)
    material("פרשנות", (0.27, 0.45, 0.55, 1), roughness=0.72)
    material("להבה", (0.95, 0.15, 0.015, 1), roughness=0.25,
             emission=(1.0, 0.08, 0.005, 1), emission_strength=4.0)


def box(name: str, size: tuple[float, float, float],
        location: tuple[float, float, float], mat: str, group: str,
        bevel: float = 0.0) -> bpy.types.Object:
    bpy.ops.mesh.primitive_cube_add(location=tuple(m(v) for v in location))
    obj = bpy.context.object
    obj.name = name
    obj.data.name = name
    obj.scale = tuple(m(v) / 2 for v in size)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.data.materials.append(MATERIALS[mat])
    if bevel:
        modifier = obj.modifiers.new("עיגול קצוות", "BEVEL")
        modifier.width = m(bevel)
        modifier.segments = 3
    return move_to(obj, group)


def cylinder(name: str, radius: float, depth: float,
             location: tuple[float, float, float], mat: str, group: str,
             vertices: int = 32) -> bpy.types.Object:
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=vertices, radius=m(radius), depth=m(depth),
        location=tuple(m(v) for v in location),
    )
    obj = bpy.context.object
    obj.name = name
    obj.data.name = name
    obj.data.materials.append(MATERIALS[mat])
    return move_to(obj, group)


def sphere(name: str, radius: float, location: tuple[float, float, float],
           mat: str, group: str,
           scale: tuple[float, float, float] = (1, 1, 1)) -> bpy.types.Object:
    bpy.ops.mesh.primitive_uv_sphere_add(
        segments=24, ring_count=12, radius=m(radius),
        location=tuple(m(v) for v in location),
    )
    obj = bpy.context.object
    obj.name = name
    obj.data.name = name
    obj.scale = scale
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.data.materials.append(MATERIALS[mat])
    return move_to(obj, group)


def torus(name: str, major: float, minor: float,
          location: tuple[float, float, float], mat: str, group: str,
          rotation: tuple[float, float, float] = (0, 0, 0)) -> bpy.types.Object:
    bpy.ops.mesh.primitive_torus_add(
        major_radius=m(major), minor_radius=m(minor), major_segments=24,
        minor_segments=8, location=tuple(m(v) for v in location),
        rotation=rotation,
    )
    obj = bpy.context.object
    obj.name = name
    obj.data.name = name
    obj.data.materials.append(MATERIALS[mat])
    return move_to(obj, group)


def rod(name: str, start: tuple[float, float, float],
        end: tuple[float, float, float], radius: float,
        mat: str, group: str) -> bpy.types.Object:
    a = Vector(tuple(m(v) for v in start))
    b = Vector(tuple(m(v) for v in end))
    direction = b - a
    obj = cylinder(name, radius, direction.length / CUBIT_M,
                   tuple(v / CUBIT_M for v in ((a + b) / 2)), mat, group, 20)
    obj.rotation_mode = "QUATERNION"
    obj.rotation_quaternion = direction.to_track_quat("Z", "Y")
    return obj


def add_courtyard() -> None:
    group = "01 חצר המשכן"
    box("קרקע החצר", (104, 54, 0.18), (0, 0, -0.09), "חול המדבר", group)

    # Exodus lists 20 posts on each long side and 10 on the west.  Following
    # the Baraita, each five-cubit hanging projects 2.5 cubits past its post.
    def post(name: str, x: float, y: float) -> None:
        cylinder(name, 0.16, 5.25, (x, y, 2.625), "נחושת", group, 20)
        cylinder("אדן " + name, 0.30, 0.25, (x, y, 0.125), "נחושת", group, 24)
        torus("חשוק כסף " + name, 0.18, 0.025, (x, y, 4.25), "כסף", group)

    for side, y in (("צפון", -25), ("דרום", 25)):
        for index in range(20):
            x = -47.5 + index * 5
            post(f"עמוד {side} {index + 1:02d}", x, y)
            box(f"קלע {side} {index + 1:02d}", (5, 0.08, 5),
                (x, y, 2.5), "שש משזר", group)
    for index in range(10):
        y = -22.5 + index * 5
        post(f"עמוד מערב {index + 1:02d}", 50, y)
        box(f"קלע מערב {index + 1:02d}", (0.08, 5, 5),
            (50, y, 2.5), "שש משזר", group)

    # East side: fifteen cubits of linen at either shoulder and a 20-cubit
    # embroidered screen on four posts (Exodus 27:13-16).
    for side, y0 in (("צפון", -17.5), ("דרום", 17.5)):
        for index in range(3):
            y = y0 + (-5 + index * 5 if side == "צפון" else -5 + index * 5)
            post(f"עמוד מזרח {side} {index + 1}", -50, y)
        box(f"קלע מזרח {side}", (0.08, 15, 5), (-50, y0, 2.5),
            "שש משזר", group)
    for index, y in enumerate((-7.5, -2.5, 2.5, 7.5), 1):
        post(f"עמוד מסך שער החצר {index}", -50, y)
    add_patterned_curtain("מסך שער החצר", -50, 0, 20, 5, axis="y", group=group)


def add_patterned_curtain(name: str, x: float, y: float, length: float,
                          height: float, *, axis: str, group: str) -> None:
    thickness = ASSUMED["curtain_thickness"]
    size = (thickness, length, height) if axis == "y" else (length, thickness, height)
    box(name, size, (x, y, height / 2), "שש משזר", group)
    colors = ("תכלת", "ארגמן", "תולעת שני")
    for index in range(12):
        offset = -length / 2 + (index + 0.5) * length / 12
        stripe_size = (thickness + 0.02, length / 28, height * 0.88)
        stripe_loc = (x - 0.01, y + offset, height / 2)
        if axis == "x":
            stripe_size = (length / 28, thickness + 0.02, height * 0.88)
            stripe_loc = (x + offset, y - 0.01, height / 2)
        box(f"פס {name} {index + 1:02d}", stripe_size, stripe_loc,
            colors[index % 3], group)


def add_embroidered_textile(name: str, x: float, half_span: float,
                            height: float, group: str, *, veil: bool = False) -> None:
    """Create a complete hanging textile with raised embroidered threadwork."""
    width_segments = 48
    height_segments = 32
    vertices: list[tuple[float, float, float]] = []
    faces: list[tuple[int, int, int, int]] = []
    for z_index in range(height_segments + 1):
        z_ratio = z_index / height_segments
        z = height * z_ratio
        for y_index in range(width_segments + 1):
            y_ratio = y_index / width_segments
            y = -half_span + 2 * half_span * y_ratio
            # Only the minute irregularity of a heavy woven textile: there is
            # no gathering, centre opening or curtain-like tieback.
            weave = (0.018 * math.sin(y_ratio * math.pi * 16)
                     + 0.008 * math.sin(z_ratio * math.pi * 12 + y_ratio * 3))
            vertices.append((m(x + weave), m(y), m(z)))
    row = width_segments + 1
    for z_index in range(height_segments):
        for y_index in range(width_segments):
            a = z_index * row + y_index
            faces.append((a, a + 1, a + row + 1, a + row))
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    cloth = bpy.data.objects.new(name, mesh)
    mesh.materials.append(MATERIALS["אריג כחול־ארגמני – שחזור משוער"])
    collection(group).objects.link(cloth)
    solidify = cloth.modifiers.new("עובי אריג", "SOLIDIFY")
    solidify.thickness = m(0.045)
    solidify.offset = 0.0

    # Raised coloured threads make the decoration legible as embroidery from
    # both faces of the model instead of as printed stripes.
    thread = 0.035
    edge = half_span - 0.18
    rod(f"שפת ארגמן צפונית – {name}", (x, -edge, 0.18),
        (x, -edge, height - 0.18), thread, "ארגמן", group)
    rod(f"שפת ארגמן דרומית – {name}", (x, edge, 0.18),
        (x, edge, height - 0.18), thread, "ארגמן", group)
    rod(f"שפת תכלת עליונה – {name}", (x, -edge, height - 0.18),
        (x, edge, height - 0.18), thread, "תכלת", group)
    rod(f"שפת תולעת שני תחתונה – {name}", (x, -edge, 0.18),
        (x, edge, 0.18), thread, "תולעת שני", group)

    if veil:
        # Schematic winged figures represent the cherubim worked into the
        # parokhet (Exodus 26:31). They are decorative textile motifs, not
        # freestanding sculpture.
        for row_index, z in enumerate((3.0, 6.8), 1):
            for column_index, y in enumerate((-2.75, 0.0, 2.75), 1):
                prefix = f"כרוב רקום {row_index}-{column_index} – {name}"
                sphere(f"ראש {prefix}", 0.13, (x, y, z + 0.58),
                       "תולעת שני", group, scale=(0.32, 1, 1))
                rod(f"גוף {prefix}", (x, y, z + 0.42),
                    (x, y, z - 0.42), thread, "שש משזר", group)
                for side in (-1, 1):
                    rod(f"כנף עליונה {side} {prefix}", (x, y, z + 0.25),
                        (x, y + side * 0.82, z + 0.72), thread, "תכלת", group)
                    rod(f"כנף תחתונה {side} {prefix}",
                        (x, y + side * 0.82, z + 0.72),
                        (x, y + side * 0.64, z - 0.08), thread,
                        "תולעת שני", group)
    else:
        # Repeating diamonds distinguish the entrance screen's embroidered
        # work from the cherubim pattern of the veil.
        colors = ("תכלת", "שש משזר", "תולעת שני")
        for row_index, z in enumerate((1.7, 4.9, 8.1), 1):
            for column_index, y in enumerate((-3.25, -1.1, 1.1, 3.25), 1):
                mat = colors[(row_index + column_index) % len(colors)]
                prefix = f"מעוין רקום {row_index}-{column_index} – {name}"
                points = ((y, z + 0.72), (y + 0.64, z),
                          (y, z - 0.72), (y - 0.64, z), (y, z + 0.72))
                for segment in range(4):
                    y1, z1 = points[segment]
                    y2, z2 = points[segment + 1]
                    rod(f"{prefix} קטע {segment + 1}", (x, y1, z1),
                        (x, y2, z2), thread, mat, group)
                sphere(f"מרכז {prefix}", 0.10, (x, y, z), "שש משזר", group,
                       scale=(0.32, 1, 1))


def add_boards(*, cutaway: bool = False) -> None:
    group = "02 קרשים אדנים ובריחים"
    # Rabbi Nehemiah's constant one-cubit thickness is selected.  It is a
    # visible parameter, since Rabbi Judah's tapering boards are an alternative.
    for side, y in (("צפון", -4.5), ("דרום", 4.5)):
        for index in range(20):
            x = 0.75 + index * 1.5
            if cutaway and side == "דרום":
                # Low traces retain the footprint while opening the interior.
                box(f"קרש {side} בחתך {index + 1:02d}", (1.48, 1, 0.35),
                    (x, y, 0.175), "פרשנות", group, 0.02)
                continue
            box(f"קרש {side} {index + 1:02d}", (1.48, 1, 9),
                (x, y, 5.5), "זהב", group, 0.025)
            add_board_sockets(x, y, side, index + 1, group)
        if not (cutaway and side == "דרום"):
            # Four half-wall bars and the full middle bar.
            for z in (2.5, 7.5):
                rod(f"בריח {side} מזרחי בגובה {z}", (0, y + (0.56 if side == "דרום" else -0.56), z),
                    (15, y + (0.56 if side == "דרום" else -0.56), z), 0.075, "זהב", group)
                rod(f"בריח {side} מערבי בגובה {z}", (15, y + (0.56 if side == "דרום" else -0.56), z),
                    (30, y + (0.56 if side == "דרום" else -0.56), z), 0.075, "זהב", group)
            rod(f"בריח תיכון {side}", (0, y, 5), (30, y, 5), 0.065, "פרשנות", group)

    # Six rear boards, with the two corner boards shown as narrower visible
    # returns.  Their exact joining geometry is one of the textual ambiguities.
    for index in range(6):
        y = -3.75 + index * 1.5
        box(f"קרש מערב {index + 1:02d}", (1, 1.48, 9), (29.5, y, 5.5),
            "זהב", group, 0.025)
        add_board_sockets(29.5, y, "מערב", index + 1, group, west=True)
    for side, y in (("צפון", -4.75), ("דרום", 4.75)):
        if cutaway and side == "דרום":
            continue
        box(f"קרש מקצוע {side}", (1, 0.5, 9), (29.5, y, 5.5),
            "פרשנות", group, 0.025)

    # Five gilded entrance posts on copper sockets.
    for index, y in enumerate((-4, -2, 0, 2, 4), 1):
        cylinder(f"עמוד פתח המשכן {index}", 0.12, 10, (0, y, 5), "זהב", group, 20)
        cylinder(f"אדן נחושת לפתח {index}", 0.23, 0.35, (0, y, 0.175), "נחושת", group, 24)


def add_board_sockets(x: float, y: float, side: str, index: int,
                      group: str, west: bool = False) -> None:
    if west:
        for dy in (-0.375, 0.375):
            box(f"אדן כסף {side} {index}-{dy:+}", (1, 0.7, 1),
                (29.5, y + dy, 0.5), "כסף", group, 0.035)
    else:
        for dx in (-0.375, 0.375):
            box(f"אדן כסף {side} {index}-{dx:+}", (0.7, 1, 1),
                (x + dx, y, 0.5), "כסף", group, 0.035)


def add_outer_structure() -> None:
    add_boards(cutaway=False)
    group = "03 יריעות וכיסויים"
    # A raised/exploded corner exposes all four prescribed layers.  The top
    # hides the boards as the completed tent would have done.
    box("יריעות המשכן – גג", (30, 10, 0.10), (15, 0, 10.10), "ארגמן", group)
    for side, y in (("צפון", -4.96), ("דרום", 4.96)):
        box(f"יריעות המשכן – דופן {side}", (30, 0.10, 9),
            (15, y, 5.55), "ארגמן", group)
        for index in range(10):
            x = 2 + index * 3
            box(f"פס ארוג בדופן {side} {index + 1}", (0.18, 0.115, 8.5),
                (x, y + (-0.01 if side == "צפון" else 0.01), 5.55),
                ("תכלת", "תולעת שני", "שש משזר")[index % 3], group)
    box("יריעות המשכן – אחוריים", (0.10, 10, 10), (29.96, 0, 5),
        "ארגמן", group)

    # The outer layers are stepped back to make the prescribed order legible.
    box("יריעות עיזים – גג", (30.4, 10.4, 0.10), (15, 0, 10.26), "עיזים", group)
    box("מכסה עורות אילים מאדמים", (27.5, 10.8, 0.10), (16.4, 0, 10.42),
        "עורות אילים מאדמים", group)
    box("מכסה עורות תחשים – מידה סכמטית", (24.5, 11.2, 0.10),
        (17.9, 0, 10.58), "עורות תחשים – גוון סכמטי", group)

    add_altar_and_laver()


def add_altar_and_laver() -> None:
    group = "04 מזבח העולה והכיור"
    x = -26
    # Hebrew Wikipedia, "Altar of burnt offering" (Tabernacle section): the
    # acacia-and-copper body was hollow but filled with earth at every camp.
    # Internal wall thickness remains schematic.
    foundation = ASSUMED["altar_foundation_projection"]
    box("יסוד מזבח הנחושת – בליטה סכמטית",
        (5 + foundation * 2, 5 + foundation * 2, 1),
        (x, 0, 0.5), "נחושת", group, 0.04)
    for side_y in (-2.4, 2.4):
        box("דופן מזבח הנחושת", (5, 0.20, 3), (x, side_y, 1.5), "נחושת", group, 0.04)
    for side_x in (-2.4, 2.4):
        box("דופן מזבח הנחושת", (0.20, 5, 3), (x + side_x, 0, 1.5), "נחושת", group, 0.04)
    box("מילוי אדמה במזבח", (4.58, 4.58, 2.82),
        (x, 0, 1.41), "חול המדבר", group, 0.03)
    box("פני אדמת המזבח", (4.58, 4.58, 0.16),
        (x, 0, 2.92), "חול המדבר", group, 0.03)

    # The horns were hewn as part of the altar rather than attached later.
    # Separate touching meshes keep that source relationship legible in GLB.
    for dx in (-2.32, 2.32):
        for dy in (-2.32, 2.32):
            box("קרן מזבח הנחושת", (0.34, 0.34, 0.55),
                (x + dx, dy, 3.18), "נחושת", group, 0.06)

    # Copper mesh around the body reaches the altar's halfway line. Rabbi
    # Yose's one-cubit-wide reading is used for the visible band.
    mesh_center_z = 1.5
    for index in range(11):
        offset = -2.25 + index * 0.45
        for y in (-2.515, 2.515):
            box("רשת נחושת – צלע אורך", (0.035, 0.045, 1.0),
                (x + offset, y, mesh_center_z), "נחושת", group)
        for side_x in (x - 2.515, x + 2.515):
            box("רשת נחושת – צלע רוחב", (0.045, 0.035, 1.0),
                (side_x, offset, mesh_center_z), "נחושת", group)
    for z in (1.0, 1.25, 1.5, 1.75, 2.0):
        for y in (-2.515, 2.515):
            box("רשת נחושת – חוט אופקי", (4.55, 0.045, 0.035),
                (x, y, z), "נחושת", group)
        for side_x in (x - 2.515, x + 2.515):
            box("רשת נחושת – חוט אופקי", (0.045, 4.55, 0.035),
                (side_x, 0, z), "נחושת", group)

    # Four rings receive the copper-plated carrying poles.
    for ring_x in (x - 1.85, x + 1.85):
        for ring_y in (-2.67, 2.67):
            torus("טבעת נשיאת המזבח", 0.16, 0.035,
                  (ring_x, ring_y, 1.45), "נחושת", group,
                  rotation=(math.pi / 2, 0, 0))
    for y in (-2.72, 2.72):
        rod("בד מזבח הנחושת", (x - 3.7, y, 1.45), (x + 3.7, y, 1.45),
            0.09, "נחושת", group)

    # Permanent fire, shown over a simple crossed wood arrangement.
    for index, angle in enumerate((-0.55, 0.55, -0.18, 0.18), 1):
        dx = 1.35 * math.cos(angle)
        dy = 1.35 * math.sin(angle)
        rod(f"עץ מערכת אש התמיד {index}",
            (x - dx, -dy, 3.08), (x + dx, dy, 3.08),
            0.12, "עצי שיטים", group)
    for flame_x, flame_y, flame_h in (
        (x - 0.75, -0.35, 0.70), (x, 0.25, 0.95),
        (x + 0.72, -0.10, 0.66), (x + 0.20, -0.60, 0.58),
    ):
        sphere("אש תמיד", 0.22, (flame_x, flame_y, 3.18 + flame_h / 2),
               "להבה", group, scale=(0.65, 0.65, flame_h / 0.44))

    # The article identifies a ramp as a basic altar component. Its dimensions
    # for the wilderness altar are not supplied, so the blue-grey ramp is a
    # visible modelling assumption rather than a sourced measurement.
    ramp_length = ASSUMED["altar_ramp_length"]
    ramp_width = ASSUMED["altar_ramp_width"]
    bpy.ops.mesh.primitive_cube_add(location=(m(x), m(2.5 + ramp_length / 2), m(1.5)))
    ramp = bpy.context.object
    ramp.name = "כבש המזבח – מידות סכמטיות"
    ramp.data.name = ramp.name
    ramp.scale = (m(ramp_width / 2), m(ramp_length / 2), m(0.12))
    # Local +Y points away from the altar, so a negative X rotation keeps the
    # altar-side end high and the outer end at ground level.
    ramp.rotation_euler.x = -math.atan2(3.0, ramp_length)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    ramp.data.materials.append(MATERIALS["פרשנות"])
    move_to(ramp, group)

    x = -10
    cylinder("בסיס הכיור", 0.72, 0.65, (x, 0, 0.325), "נחושת", group, 36)
    cylinder("רגל הכיור", 0.34, 0.75, (x, 0, 0.95), "נחושת", group, 28)
    cylinder("כיור הנחושת – מידה סכמטית", ASSUMED["laver_size"], 0.72,
             (x, 0, 1.55), "נחושת", group, 48)
    cylinder("מי הכיור", 1.12, 0.04, (x, 0, 1.93), "מים", group, 48)


def add_interior_architecture() -> None:
    add_boards(cutaway=True)
    group = "03 פנים המשכן"
    box("רצפת הקודש", (30, 9, 0.14), (15, 0, 0.07), "חול המדבר", group)
    # A complete embroidered textile closes the eastern entrance. It is a
    # single hanging sheet, without a theatrical centre opening or tiebacks.
    add_embroidered_textile("מסך פתח אוהל מועד", 0.08, 4.35, 9.85, group)

    # Traditional division: 20 cubits of Holy Place and 10 of Holy of Holies.
    for index, y in enumerate((-3.75, -1.25, 1.25, 3.75), 1):
        cylinder(f"עמוד הפרוכת {index}", 0.12, 10, (20, y, 5), "זהב", group, 20)
        cylinder(f"אדן כסף לפרוכת {index}", 0.23, 0.35,
                 (20, y, 0.175), "כסף", group, 24)
    add_embroidered_textile("הפרוכת", 20, 4.35, 9.85, group, veil=True)

def add_ark() -> None:
    group = "04 כלי הקודש"
    x, y = 25, 0
    box("ארון העדות", (2.5, 1.5, 1.5), (x, y, 0.75), "זהב", group, 0.05)
    box("כפורת", (2.62, 1.62, 0.14), (x, y, 1.57), "זהב", group, 0.04)
    for side in (-1, 1):
        cx = x + side * 0.72
        sphere("ראש כרוב – סכמטי", 0.19, (cx, 0, 2.15), "זהב", group)
        cylinder("גוף כרוב – סכמטי", 0.16, 0.56, (cx, 0, 1.88), "זהב", group, 20)
        wing_tip = x + side * 0.08
        rod("כנף כרוב – סכמטי", (cx, -0.08, 2.02), (wing_tip, -0.28, 2.48),
            0.10, "זהב", group)
        rod("כנף כרוב – סכמטי", (cx, 0.08, 2.02), (wing_tip, 0.28, 2.48),
            0.10, "זהב", group)
    for ypole in (-0.95, 0.95):
        rod("בד הארון", (x - 2.1, ypole, 0.72), (x + 2.1, ypole, 0.72),
            0.085, "זהב", group)
        for ring_x in (x - 1.15, x + 1.15):
            torus("טבעת הארון", 0.15, 0.035, (ring_x, ypole, 0.72),
                  "זהב", group, rotation=(math.pi / 2, 0, 0))


def add_incense_altar() -> None:
    group = "04 כלי הקודש"
    x = 10
    box("מזבח הקטורת", (1, 1, 2), (x, 0, 1), "זהב", group, 0.04)
    for dx in (-0.42, 0.42):
        for dy in (-0.42, 0.42):
            box("קרן מזבח הקטורת", (0.15, 0.15, 0.25),
                (x + dx, dy, 2.12), "זהב", group, 0.025)
    for y in (-0.62, 0.62):
        rod("בד מזבח הקטורת", (x - 1.25, y, 0.9),
            (x + 1.25, y, 0.9), 0.06, "זהב", group)


def add_table() -> None:
    group = "04 כלי הקודש"
    x, y = 15, -2.5
    # Exodus 25:23-30 and Hebrew Wikipedia, "Table of the Showbread": a
    # 2 x 1 x 1.5-cubit acacia table overlaid with pure gold.
    box("טבלת שולחן הפנים", (2, 1, 0.16), (x, y, 1.42), "זהב", group, 0.04)
    for dx in (-0.82, 0.82):
        for dy in (-0.34, 0.34):
            cylinder("רגל השולחן", 0.075, 1.42, (x + dx, y + dy, 0.71),
                     "זהב", group, 16)

    # One-handbreadth frame above the tabletop, following one of the two
    # opinions summarized in the article. A second opinion puts it below.
    tefach = 1 / 6
    frame_center_z = 1.50 + tefach / 2
    for yy in (y - 0.47, y + 0.47):
        box("מסגרת השולחן – טפח", (2.0, 0.055, tefach),
            (x, yy, frame_center_z), "זהב", group, 0.018)
    for xx in (x - 0.97, x + 0.97):
        box("מסגרת השולחן – טפח", (0.055, 0.94, tefach),
            (xx, y, frame_center_z), "זהב", group, 0.018)

    # The two gold crowns are represented as slim rails: one around the table
    # edge and one around the top of the frame.
    for crown_z, crown_name in ((1.50, "זר טבלת השולחן"),
                                (1.50 + tefach, "זר מסגרת השולחן")):
        for yy in (y - 0.505, y + 0.505):
            rod(crown_name, (x - 1.02, yy, crown_z),
                (x + 1.02, yy, crown_z), 0.025, "זהב", group)
        for xx in (x - 1.02, x + 1.02):
            rod(crown_name, (xx, y - 0.505, crown_z),
                (xx, y + 0.505, crown_z), 0.025, "זהב", group)

    # Four rings at the legs receive the two gold-covered carrying poles.
    pole_y_values = (y - 0.64, y + 0.64)
    for ring_x in (x - 0.82, x + 0.82):
        for ring_y in pole_y_values:
            torus("טבעת שולחן הפנים", 0.13, 0.028,
                  (ring_x, ring_y, 1.22), "זהב", group,
                  rotation=(0, math.pi / 2, 0))
    for ypole in pole_y_values:
        rod("בד השולחן", (x - 1.6, ypole, 1.22), (x + 1.6, ypole, 1.22),
            0.055, "זהב", group)

    # Two stacks of six open-box-shaped loaves. Each loaf is a base with two
    # raised sides ("teivah perutzah"), rather than the former flat block.
    stack_centers = (x - 0.50, x + 0.50)
    first_loaf_z = 1.74
    level_step = 0.25
    for stack_number, stack_x in enumerate(stack_centers, 1):
        for level in range(6):
            loaf_z = first_loaf_z + level * level_step
            box(f"לחם הפנים – מערכת {stack_number} לחם {level + 1} בסיס",
                (0.68, 0.64, 0.09), (stack_x, y, loaf_z),
                "לחם הפנים", group, 0.025)
            for side_y in (-0.29, 0.29):
                box(f"לחם הפנים – מערכת {stack_number} לחם {level + 1} דופן",
                    (0.68, 0.10, 0.20),
                    (stack_x, y + side_y, loaf_z + 0.055),
                    "לחם הפנים", group, 0.025)

        # Fourteen half-pipe canes per stack: three in each of the first four
        # gaps and two beneath the upper loaf, 28 in all.
        for gap in range(5):
            cane_count = 2 if gap == 4 else 3
            if cane_count == 3:
                cane_xs = (stack_x - 0.20, stack_x, stack_x + 0.20)
            else:
                cane_xs = (stack_x - 0.14, stack_x + 0.14)
            cane_z = first_loaf_z + gap * level_step + 0.16
            for cane_index, cane_x in enumerate(cane_xs, 1):
                rod(f"קנה זהב – מערכת {stack_number} רווח {gap + 1}-{cane_index}",
                    (cane_x, y - 0.31, cane_z),
                    (cane_x, y + 0.31, cane_z), 0.018, "זהב", group)

        # Two tall side supports (senifin) for each stack. Their precise form
        # is disputed; the selected straight-board form is kept schematic.
        support_top = first_loaf_z + 5 * level_step + 0.24
        for side_x in (stack_x - 0.38, stack_x + 0.38):
            box(f"סניף מערכת {stack_number}",
                (0.055, 0.82, support_top - 1.50),
                (side_x, y, 1.50 + (support_top - 1.50) / 2),
                "פרשנות", group, 0.018)

        # Most opinions place each frankincense bowl in the cavity of the top
        # loaf; that placement is selected here.
        top_z = first_loaf_z + 5 * level_step + 0.17
        cylinder(f"בזיך לבונה מערכת {stack_number}", 0.105, 0.08,
                 (stack_x, y, top_z), "זהב", group, 24)
        cylinder(f"לבונה מערכת {stack_number}", 0.078, 0.025,
                 (stack_x, y, top_z + 0.05), "שש משזר", group, 24)


def add_menorah() -> None:
    group = "04 כלי הקודש"
    x, y = 15, 2.5
    cylinder("בסיס המנורה", 0.52, 0.16, (x, y, 0.08), "זהב", group, 40)
    rod("קנה מרכזי", (x, y, 0.16), (x, y, ASSUMED["lamp_height"]),
        0.075, "זהב", group)
    lamp_xs = [x]
    for spread, join_z in ((0.55, 0.75), (1.05, 1.18), (1.5, 1.62)):
        sphere("כפתור המנורה", 0.12, (x, y, join_z), "זהב", group)
        for side in (-1, 1):
            outer_x = x + side * spread
            # Segmented curves preserve the familiar rounded branch silhouette.
            rod("קנה המנורה", (x, y, join_z), (outer_x, y, 2.45),
                0.06, "זהב", group)
            rod("קנה המנורה", (outer_x, y, 2.45), (outer_x, y, 3.0),
                0.06, "זהב", group)
            lamp_xs.append(outer_x)
    for lamp_x in sorted(lamp_xs):
        cylinder("נר המנורה", 0.14, 0.10, (lamp_x, y, 3.04), "זהב", group, 24)
        sphere("להבת המנורה", 0.09, (lamp_x, y, 3.20), "להבה", group,
               scale=(0.6, 0.6, 1.6))


def add_interior() -> None:
    add_interior_architecture()
    add_ark()
    add_incense_altar()
    add_table()
    add_menorah()


def add_open_tabernacle_in_courtyard() -> None:
    """Show the Mishkan uncovered, with its vessels visible in the courtyard."""
    add_interior()
    add_altar_and_laver()


def setup_scene(interior: bool) -> None:
    world = bpy.context.scene.world
    world.use_nodes = True
    background = world.node_tree.nodes.get("Background")
    background.inputs["Color"].default_value = ((0.025, 0.030, 0.040, 1)
                                                        if interior else
                                                        (0.055, 0.070, 0.095, 1))
    background.inputs["Strength"].default_value = 0.42

    bpy.ops.object.light_add(type="SUN", location=(m(-60), m(30), m(90)))
    sun = bpy.context.object
    sun.name = "שמש"
    sun.data.energy = 3.2
    sun.data.angle = math.radians(10)
    sun.rotation_euler = (math.radians(26), math.radians(-20), math.radians(-40))
    move_to(sun, "09 תאורה ומצלמה")

    bpy.ops.object.light_add(type="AREA", location=(m(4), m(18), m(26)))
    fill = bpy.context.object
    fill.name = "תאורת מילוי"
    fill.data.energy = 1400 if interior else 2400
    fill.data.shape = "DISK"
    fill.data.size = m(30 if interior else 75)
    target = Vector((m(14), 0, m(3)))
    fill.rotation_euler = (target - fill.location).to_track_quat("-Z", "Y").to_euler()
    move_to(fill, "09 תאורה ומצלמה")

    camera_location = ((m(-4), m(38), m(24)) if interior
                       else (m(-92), m(82), m(70)))
    camera_target = (Vector((m(14), 0, m(3.4))) if interior
                     else Vector((0, 0, m(3))))
    bpy.ops.object.camera_add(location=camera_location)
    camera = bpy.context.object
    camera.name = "מצלמת פנים המשכן" if interior else "מצלמת חצר המשכן"
    camera.rotation_euler = (camera_target - camera.location).to_track_quat("-Z", "Y").to_euler()
    camera.data.lens = 55
    move_to(camera, "09 תאורה ומצלמה")

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
    scene.render.film_transparent = False
    scene.render.filepath = os.path.abspath(
        "tabernacle_interior_preview.png" if interior else "tabernacle_preview.png"
    )
    scene["model_title"] = (
        "Wilderness Tabernacle cutaway" if interior
        else "Wilderness Tabernacle and courtyard"
    )
    scene["primary_sources"] = "Exodus 25-30, 35-40"
    scene["interpretation"] = "Rabbinic/traditional reconstruction"
    scene["cubit_meters"] = CUBIT_M
    scene["accuracy_note"] = (
        "SOURCE values are textual or traditional dimensions. ASSUMED values "
        "and blue-grey elements are schematic educational completions."
    )


def build(interior: bool = False) -> None:
    clear_scene()
    add_materials()
    for name in ("01 חצר המשכן", "02 קרשים אדנים ובריחים", "03 יריעות וכיסויים",
                 "03 פנים המשכן", "04 מזבח העולה והכיור", "04 כלי הקודש",
                 "09 תאורה ומצלמה"):
        collection(name)
    if interior:
        add_interior()
    else:
        add_courtyard()
        add_open_tabernacle_in_courtyard()
    setup_scene(interior)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--interior", action="store_true")
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
        bpy.ops.export_scene.gltf(filepath=os.path.abspath(args.export), export_format="GLB")


if __name__ == "__main__":
    parsed = parse_args()
    build(parsed.interior)
    finish(parsed)
