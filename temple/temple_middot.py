"""Procedural first-stage model of the Temple described in Mishnah Middot.

Run inside Blender's Scripting workspace, or from the command line:

    blender --background --python temple_middot.py -- \
        --save temple_middot.blend --export temple_middot.glb

Coordinates:
    Source-plan inputs use +X = west, +Y = north, +Z = up. Because Blender
    is right-handed, plan Y is reflected during construction; in the actual
    Blender scene +X = west, +Y = south, -Y = north, +Z = up.
    All source dimensions are expressed in cubits and converted by CUBIT_M.

This is an architectural study model, not a claim that uncertain details have
been historically resolved.  Explicit Mishnah measurements and modelling
assumptions are separated below.
"""

from __future__ import annotations

import argparse
import math
import os
import re
import sys

import bpy
from mathutils import Vector


# ---------------------------------------------------------------------------
# Scale and source dimensions (Mishnah Middot)
# ---------------------------------------------------------------------------

CUBIT_M = 0.50
TEFACH_M = CUBIT_M / 6.0

# +X west and +Y north form a left-handed plan basis. Blender and glTF are
# right-handed, so exterior plan coordinates must be reflected on Y. The
# standalone interior script already authors its geometry in scene coordinates
# (+Y south) and disables this conversion before building.
MIRROR_PLAN_Y = True

SOURCE = {
    "temple_mount": (500.0, 500.0),       # Middot 2:1
    "women_court": (135.0, 135.0),       # Middot 2:5
    "corner_chamber": (40.0, 40.0),      # Middot 2:5
    "azarah": (187.0, 135.0),            # Middot 2:6; 5:1
    "israel_court_depth": 11.0,           # Middot 2:6; 5:1
    "priests_court_depth": 11.0,          # Middot 2:6; 5:1
    "altar": (32.0, 32.0),                # Middot 3:1
    "altar_ramp": (16.0, 32.0),           # Middot 3:3
    "altar_to_hall": 22.0,                # Middot 3:6
    "sanctuary": (100.0, 100.0, 100.0),  # Middot 4:6-7
    "sanctuary_body_width": 70.0,         # Middot 4:7
    "hall_depth": 16.0,                   # 5 cubit wall + 11 cubit hall
    "behind_sanctuary": 11.0,             # Middot 5:1
    "standard_gate": (10.0, 20.0),        # Middot 2:3
    "hall_gate": (20.0, 40.0),            # Middot 3:7
    "soreg_height_tefach": 10.0,          # Middot 2:3
    "cheil_steps": 12,                    # Middot 2:3
    "women_steps": 15,                    # Middot 2:5
    "hall_steps": 12,                     # Middot 3:6
    "women_court_level": 6.0,             # 12 steps x 0.5 cubit
    "israel_court_level": 13.5,           # +15 steps x 0.5 cubit
}


# Measurements supported by a documented interpretation rather than stated
# unambiguously in Middot itself.
INTERPRETED = {
    # Prevailing traditional interpretation; Hebrew Wikipedia, "Ha-cheil".
    "cheil_width": 10.0,
}


# ---------------------------------------------------------------------------
# Explicit modelling assumptions (easy to revise)
# ---------------------------------------------------------------------------

ASSUMED = {
    "mount_wall_thickness": 5.0,
    "mount_wall_height": 12.0,
    "court_wall_thickness": 3.0,
    "court_wall_height": 24.0,
    "soreg_post_spacing": 8.0,
    "priests_court_level": 16.0,     # R. Eliezer b. Jacob, Middot 2:6
    # The altar is placed south of the Azarah centreline. Together with its
    # ramp this leaves the service/ring area to its north (Middot 5:2).
    "altar_north_offset": -9.0,
    "altar_height": 9.0,
    "altar_horn_height": 1.0,
    "label_height": 0.35,
    # Middot names the gates and chambers but does not provide complete plans
    # for their masonry. These values keep the reconstructions readable while
    # preserving the sourced 10 x 20 cubit clear gate openings.
    "azarah_gatehouse_width": 15.0,
    "azarah_gatehouse_depth": 8.0,
    "azarah_chamber_depth": 14.0,
    "azarah_chamber_height": 12.0,
    # Middot gives the number and rise of the semicircular steps, but not
    # their tread depth. One cubit keeps the fifteen-step ascent usable at
    # human scale and gives it the prominence expected before Nicanor's Gate.
    "women_step_tread": 1.0,
    # Leave the western gallery open above and beside the full stair fan.
    "womens_balcony_stair_clearance": 2.0,
    # The Rambam placement summarized in Hebrew Wikipedia puts the chamber at
    # the Azarah's north-east corner. Yoma 25a gives the boundary relationship
    # and two doors, but no source supplies plan dimensions.
    "gazit_chamber_width": 20.0,
    "gazit_chamber_depth": 24.0,
    "gazit_chamber_height": 14.0,
    "gazit_chamber_center_x": 33.0,
}


def m(cubits: float) -> float:
    return cubits * CUBIT_M


def scene_location(values: tuple[float, float, float]) -> tuple[float, float, float]:
    """Convert cubit plan coordinates to Blender's right-handed scene."""
    x, y, z = values
    scene_y = -y if MIRROR_PLAN_Y else y
    return (m(x), m(scene_y), m(z))


# The court complex is offset within the 500-cubit square so that the open
# areas follow Middot 2:1 qualitatively: most to the south, then east, north,
# and least to the west.  The Mishnah does not give exact offsets.
AZARAH_EAST_X = 23.0
AZARAH_WEST_X = AZARAH_EAST_X + SOURCE["azarah"][0]
WOMEN_EAST_X = AZARAH_EAST_X - SOURCE["women_court"][0]
COURT_CENTER_Y = 80.0
COURT_SOUTH_Y = COURT_CENTER_Y - SOURCE["azarah"][1] / 2
COURT_NORTH_Y = COURT_CENTER_Y + SOURCE["azarah"][1] / 2


MATERIALS: dict[str, bpy.types.Material] = {}
COLLECTIONS: dict[str, bpy.types.Collection] = {}

COLLECTION_NAMES_HE = {
    "00 Labels": "00 תוויות",
    "01 Temple Mount": "01 הר הבית",
    "02 Mount Walls and Gates": "02 חומות ושערי הר הבית",
    "03 Soreg and Cheil (interpreted footprint)": "03 הסורג והחיל – פרשנות",
    "04 Women's Court": "04 עזרת הנשים",
    "04 Women's Court Chambers": "04 לשכות עזרת הנשים",
    "05 Fifteen Curved Steps": "05 חמש עשרה המעלות",
    "06 Azarah": "06 העזרה",
    "06 Azarah Gates": "06 שערי העזרה ובתי־השער",
    "06 Azarah Chambers": "06 לשכות העזרה",
    "07 Altar and Service Area": "07 המזבח ובית המטבחיים",
    "08 Hall Steps": "08 מעלות האולם",
    "09 Sanctuary": "09 ההיכל",
    "10 Chambers (schematic)": "10 תאי ההיכל – סכמטי",
    "11 Lighting and Camera": "11 תאורה ומצלמה",
}

MATERIAL_NAMES_HE = {
    "Jerusalem limestone": "אבן ירושלמית",
    "Pale court stone": "אבן בהירה לעזרות",
    "White altar stone": "אבן לבנה למזבח",
    "Gold": "זהב",
    "Bronze": "נחושת",
    "Sikra red": "אדום סיקרא",
    "Curtain": "פרוכת",
    "Dark opening": "פתח כהה",
    "Wood": "עץ",
    "Ground": "קרקע",
    "Assumed element": "רכיב פרשני",
    "Text": "טקסט",
    "Silver": "כסף",
    "Cedar": "ארז",
    "Ash": "אפר המזבח",
    "Ember": "גחלים לוחשות",
    "Water": "מים",
    "Wine": "יין",
    "Terracotta": "חרס",
    "Olive oil": "שמן זית",
    "Hair and soot": "שיער ופיח",
    "Altar limestone": "אבן מזבח חמימה",
    "Altar shadow stone": "אבן מזבח – גוון צל",
    "Altar upper stone": "אבן מזבח – גוון עליון",
}

# Prefix translations keep generated Blender Outliner names readable while
# leaving the modelling code and historical source comments easy to maintain.
NAME_PREFIXES_HE = (
    ("Temple Mount surface", "משטח הר הבית"),
    ("Women's Court platform", "משטח עזרת הנשים"),
    ("Women's Court south wall", "הכותל הדרומי של עזרת הנשים"),
    ("Women's Court north wall", "הכותל הצפוני של עזרת הנשים"),
    ("Women's Court east wall", "הכותל המזרחי של עזרת הנשים"),
    ("Priests court raised platform", "המפלס המוגבה של עזרת הכוהנים"),
    ("Priests court step", "מעלת עזרת הכוהנים"),
    ("Azarah east wall", "הכותל המזרחי של העזרה"),
    ("Azarah west wall", "הכותל המערבי של העזרה"),
    ("Azarah south wall", "הכותל הדרומי של העזרה"),
    ("Azarah north wall", "הכותל הצפוני של העזרה"),
    ("Azarah gate", "שער העזרה"),
    ("Azarah chamber", "לשכת העזרה"),
    ("Altar foundation", "יסוד המזבח"),
    ("Altar middle", "גוף המזבח"),
    ("Altar upper", "ראש המזבח"),
    ("Altar horn", "קרן המזבח"),
    ("Altar ramp", "כבש המזבח"),
    ("Scarlet line", "חוט הסיקרא"),
    ("Slaughter ring", "טבעת שחיטה"),
    ("Dwarf pillar", "עמוד ננס"),
    ("Marble table", "שולחן שיש"),
    ("Laver basin", "אגן הכיור"),
    ("Laver pedestal", "בסיס הכיור"),
    ("Curved step", "מעלה מעוגלת"),
    ("Cheil step", "מעלת החיל"),
    ("Cheil north band", "רצועת החיל הצפונית"),
    ("Cheil south band", "רצועת החיל הדרומית"),
    ("Cheil east band", "רצועת החיל המזרחית"),
    ("Cheil west band", "רצועת החיל המערבית"),
    ("Soreg post", "עמוד הסורג"),
    ("South wall", "חומה דרומית"),
    ("North wall", "חומה צפונית"),
    ("East wall", "חומה מזרחית"),
    ("West wall", "חומה מערבית"),
    ("Azarah base", "בסיס העזרה"),
    ("Hall east facade", "חזית האולם המזרחית"),
    ("Hall north wall", "כותל האולם הצפוני"),
    ("Hall south wall", "כותל האולם הדרומי"),
    ("Hall roof", "גג האולם"),
    ("Hall north wing partition", "מחיצת בית החליפות הצפוני"),
    ("Hall south wing partition", "מחיצת בית החליפות הדרומי"),
    ("Hall step", "מעלת האולם"),
    ("Sanctuary inner facade", "חזית ההיכל הפנימית"),
    ("Sanctuary north outer wall", "הכותל החיצוני הצפוני של ההיכל"),
    ("Sanctuary south outer wall", "הכותל החיצוני הדרומי של ההיכל"),
    ("Sanctuary west outer wall", "הכותל החיצוני המערבי של ההיכל"),
    ("Sanctuary roof", "גג ההיכל"),
    ("Holy Place north wall", "הכותל הצפוני של הקודש"),
    ("Holy Place south wall", "הכותל הדרומי של הקודש"),
    ("Holy of Holies west wall", "הכותל המערבי של קודש הקודשים"),
    ("Traksin curtain east - south opening",
     "הפרוכת החיצונית – פתח דרומי"),
    ("Traksin curtain west - north opening",
     "הפרוכת הפנימית – פתח צפוני"),
    ("Traksin curtain east", "הפרוכת המזרחית"),
    ("Traksin curtain west", "הפרוכת המערבית"),
    ("Traksin curtain south fold", "קפל הפרוכת החיצונית בדרום"),
    ("Traksin curtain north fold", "קפל הפרוכת הפנימית בצפון"),
    ("North chamber tier", "קומת התאים הצפונית"),
    ("South chamber tier", "קומת התאים הדרומית"),
    ("East-west scale bar", "סרגל קנה מידה מזרח–מערב"),
    ("Scale segment", "מקטע קנה מידה"),
    ("Ground", "קרקע"),
    ("Sun", "שמש"),
    ("Sky fill", "תאורת מילוי"),
    ("Overview Camera", "מצלמת מבט כללי"),
    ("Label - ", "תווית – "),
)


def hebrew_name(name: str) -> str:
    for english, hebrew in NAME_PREFIXES_HE:
        if name.startswith(english):
            return hebrew + name[len(english):]
    return name


def rtl_for_blender(text: str) -> str:
    """Visual-order Hebrew for Blender text, preserving numeric runs."""
    if not re.search(r"[\u0590-\u05ff]", text):
        return text
    numeric = r"\d+(?:[.,]\d+)?(?:\s*[×x]\s*\d+(?:[.,]\d+)?)*"
    tokens = re.findall(f"{numeric}|.", text, flags=re.DOTALL)
    return "".join(reversed(tokens))


def clear_scene() -> None:
    MATERIALS.clear()
    COLLECTIONS.clear()
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for datablocks in (bpy.data.meshes, bpy.data.curves, bpy.data.materials):
        for datablock in list(datablocks):
            if datablock.users == 0:
                datablocks.remove(datablock)
    for item in list(bpy.data.collections):
        bpy.data.collections.remove(item)


def collection(name: str) -> bpy.types.Collection:
    if name not in COLLECTIONS:
        item = bpy.data.collections.new(COLLECTION_NAMES_HE.get(name, name))
        bpy.context.scene.collection.children.link(item)
        COLLECTIONS[name] = item
    return COLLECTIONS[name]


def move_to_collection(obj: bpy.types.Object, group: str) -> None:
    target = collection(group)
    for current in list(obj.users_collection):
        current.objects.unlink(obj)
    target.objects.link(obj)


def material(
    name: str,
    rgba: tuple[float, float, float, float],
    metallic: float = 0.0,
    roughness: float = 0.6,
) -> bpy.types.Material:
    mat = bpy.data.materials.new(MATERIAL_NAMES_HE.get(name, name))
    mat.diffuse_color = rgba
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = rgba
    bsdf.inputs["Metallic"].default_value = metallic
    bsdf.inputs["Roughness"].default_value = roughness
    MATERIALS[name] = mat
    return mat


def add_materials() -> None:
    material("Jerusalem limestone", (0.72, 0.62, 0.45, 1.0), roughness=0.82)
    material("Pale court stone", (0.82, 0.77, 0.64, 1.0), roughness=0.75)
    material("White altar stone", (0.86, 0.84, 0.76, 1.0), roughness=0.9)
    material("Gold", (0.83, 0.52, 0.08, 1.0), metallic=0.85, roughness=0.22)
    material("Bronze", (0.42, 0.19, 0.06, 1.0), metallic=0.7, roughness=0.3)
    material("Sikra red", (0.52, 0.025, 0.018, 1.0), roughness=0.62)
    material("Curtain", (0.24, 0.025, 0.22, 1.0), roughness=0.72)
    material("Dark opening", (0.025, 0.018, 0.012, 1.0), roughness=1.0)
    material("Wood", (0.23, 0.09, 0.025, 1.0), roughness=0.72)
    material("Ground", (0.34, 0.29, 0.19, 1.0), roughness=1.0)
    material("Assumed element", (0.30, 0.47, 0.58, 1.0), roughness=0.65)
    material("Text", (0.08, 0.055, 0.025, 1.0), roughness=0.8)
    material("Silver", (0.68, 0.72, 0.75, 1.0), metallic=0.9, roughness=0.18)
    material("Cedar", (0.34, 0.12, 0.025, 1.0), roughness=0.58)
    material("Ash", (0.12, 0.105, 0.09, 1.0), roughness=1.0)
    ember = material("Ember", (0.82, 0.075, 0.008, 1.0), roughness=0.42)
    ember_bsdf = ember.node_tree.nodes.get("Principled BSDF")
    if "Emission Color" in ember_bsdf.inputs:
        ember_bsdf.inputs["Emission Color"].default_value = (1.0, 0.055, 0.002, 1.0)
        ember_bsdf.inputs["Emission Strength"].default_value = 2.2
    material("Water", (0.08, 0.34, 0.58, 1.0), metallic=0.05, roughness=0.16)
    material("Wine", (0.34, 0.012, 0.02, 1.0), roughness=0.26)
    material("Terracotta", (0.48, 0.16, 0.065, 1.0), roughness=0.86)
    material("Olive oil", (0.52, 0.40, 0.055, 1.0), roughness=0.22)
    material("Hair and soot", (0.035, 0.022, 0.014, 1.0), roughness=0.96)
    # Deliberately deeper warm limestone values keep the altar distinct from
    # the pale court paving.  The wider value steps also preserve the profile
    # of the foundation, body and upper ledges under flat web lighting.
    material("Altar limestone", (0.26, 0.21, 0.15, 1.0), roughness=0.94)
    material("Altar shadow stone", (0.12, 0.09, 0.06, 1.0), roughness=0.98)
    material("Altar upper stone", (0.35, 0.29, 0.20, 1.0), roughness=0.92)


def box(
    name: str,
    size_cubit: tuple[float, float, float],
    location_cubit: tuple[float, float, float],
    mat: str,
    group: str,
    bevel_cubit: float = 0.0,
) -> bpy.types.Object:
    bpy.ops.mesh.primitive_cube_add(
        location=scene_location(location_cubit)
    )
    obj = bpy.context.object
    obj.name = hebrew_name(name)
    obj.data.name = obj.name
    obj.dimensions = tuple(m(value) for value in size_cubit)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    if bevel_cubit:
        modifier = obj.modifiers.new("ריכוך שפות האבן", "BEVEL")
        modifier.width = m(bevel_cubit)
        modifier.segments = 2
    obj.data.materials.append(MATERIALS[mat])
    move_to_collection(obj, group)
    return obj


def cylinder(
    name: str,
    radius_cubit: float,
    depth_cubit: float,
    location_cubit: tuple[float, float, float],
    mat: str,
    group: str,
    vertices: int = 48,
) -> bpy.types.Object:
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=vertices,
        radius=m(radius_cubit),
        depth=m(depth_cubit),
        location=scene_location(location_cubit),
    )
    obj = bpy.context.object
    obj.name = hebrew_name(name)
    obj.data.name = obj.name
    obj.data.materials.append(MATERIALS[mat])
    move_to_collection(obj, group)
    return obj


def sphere(
    name: str,
    radius_cubit: float,
    location_cubit: tuple[float, float, float],
    mat: str,
    group: str,
    scale: tuple[float, float, float] = (1.0, 1.0, 1.0),
    subdivisions: int = 2,
) -> bpy.types.Object:
    """Create a low-poly rounded detail in cubit space."""
    bpy.ops.mesh.primitive_ico_sphere_add(
        subdivisions=subdivisions,
        radius=m(radius_cubit),
        location=scene_location(location_cubit),
    )
    obj = bpy.context.object
    obj.name = hebrew_name(name)
    obj.data.name = obj.name
    obj.scale = scale
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.data.materials.append(MATERIALS[mat])
    move_to_collection(obj, group)
    return obj


def beam_between(
    name: str,
    start_cubit: tuple[float, float, float],
    end_cubit: tuple[float, float, float],
    radius_cubit: float,
    mat: str,
    group: str,
    vertices: int = 16,
) -> bpy.types.Object:
    """Create a round beam, rod, chain segment, or pipe between two points."""
    start = Vector(scene_location(start_cubit))
    end = Vector(scene_location(end_cubit))
    direction = end - start
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=vertices,
        radius=m(radius_cubit),
        depth=direction.length,
        location=(start + end) / 2,
    )
    obj = bpy.context.object
    obj.name = hebrew_name(name)
    obj.data.name = obj.name
    obj.rotation_mode = "QUATERNION"
    obj.rotation_quaternion = direction.to_track_quat("Z", "Y")
    obj.data.materials.append(MATERIALS[mat])
    move_to_collection(obj, group)
    return obj


def torus(
    name: str,
    major_radius_cubit: float,
    minor_radius_cubit: float,
    location_cubit: tuple[float, float, float],
    mat: str,
    group: str,
    rotation: tuple[float, float, float] = (0.0, 0.0, 0.0),
) -> bpy.types.Object:
    bpy.ops.mesh.primitive_torus_add(
        major_radius=m(major_radius_cubit),
        minor_radius=m(minor_radius_cubit),
        major_segments=24,
        minor_segments=8,
        location=scene_location(location_cubit),
        rotation=rotation,
    )
    obj = bpy.context.object
    obj.name = hebrew_name(name)
    obj.data.name = obj.name
    obj.data.materials.append(MATERIALS[mat])
    move_to_collection(obj, group)
    return obj


def cone(
    name: str,
    radius_cubit: float,
    depth_cubit: float,
    location_cubit: tuple[float, float, float],
    mat: str,
    group: str,
    vertices: int = 12,
) -> bpy.types.Object:
    bpy.ops.mesh.primitive_cone_add(
        vertices=vertices,
        radius1=m(radius_cubit),
        radius2=0.0,
        depth=m(depth_cubit),
        location=scene_location(location_cubit),
    )
    obj = bpy.context.object
    obj.name = hebrew_name(name)
    obj.data.name = obj.name
    obj.data.materials.append(MATERIALS[mat])
    move_to_collection(obj, group)
    return obj


def label(
    text: str, x: float, y: float, z: float, size: float = 2.5
) -> bpy.types.Object:
    bpy.ops.object.text_add(location=scene_location((x, y, z)))
    obj = bpy.context.object
    obj.name = f"תווית – {text}"
    obj.data.name = obj.name
    obj.data.body = rtl_for_blender(text)
    font_path = "/System/Library/Fonts/Supplemental/Arial.ttf"
    if os.path.exists(font_path):
        font = bpy.data.fonts.get("Arial") or bpy.data.fonts.load(font_path)
        obj.data.font = font
    obj.data.align_x = "CENTER"
    obj.data.align_y = "CENTER"
    obj.data.size = m(size)
    obj.data.extrude = m(0.03)
    obj.data.materials.append(MATERIALS["Text"])
    move_to_collection(obj, "00 Labels")
    return obj


def label_on_y_wall(
    text: str,
    x: float,
    y: float,
    z: float,
    facing_plan_y: int,
    size: float = 2.5,
) -> bpy.types.Object:
    """Place upright text on a Y-aligned wall, facing the requested plan side."""
    obj = label(text, x, y, z, size)
    facing_scene_y = -facing_plan_y if MIRROR_PLAN_Y else facing_plan_y
    if facing_scene_y < 0:
        obj.rotation_euler = (math.pi / 2, 0.0, 0.0)
    else:
        # Turning around local Y keeps the lettering upright when it faces +Y.
        obj.rotation_euler = (-math.pi / 2, math.pi, 0.0)
    return obj


def gated_wall_x(
    name: str,
    center_x: float,
    center_y: float,
    length: float,
    thickness: float,
    height: float,
    base_z: float,
    openings: list[tuple[float, float]],
    group: str,
    mat: str = "Jerusalem limestone",
) -> None:
    """Wall running along X; openings are (x_center, width), in cubits."""
    west = center_x - length / 2
    east = center_x + length / 2
    spans = sorted((max(west, x - w / 2), min(east, x + w / 2)) for x, w in openings)
    cursor = west
    part = 1
    for start, end in spans + [(east, east)]:
        if start > cursor:
            segment = start - cursor
            box(
                f"{name} {part}",
                (segment, thickness, height),
                ((cursor + start) / 2, center_y, base_z + height / 2),
                mat,
                group,
            )
            part += 1
        cursor = max(cursor, end)


def gated_wall_y(
    name: str,
    center_x: float,
    center_y: float,
    length: float,
    thickness: float,
    height: float,
    base_z: float,
    openings: list[tuple[float, float]],
    group: str,
    mat: str = "Jerusalem limestone",
) -> None:
    """Wall running along Y; openings are (y_center, width), in cubits."""
    south = center_y - length / 2
    north = center_y + length / 2
    spans = sorted((max(south, y - w / 2), min(north, y + w / 2)) for y, w in openings)
    cursor = south
    part = 1
    for start, end in spans + [(north, north)]:
        if start > cursor:
            segment = start - cursor
            box(
                f"{name} {part}",
                (thickness, segment, height),
                (center_x, (cursor + start) / 2, base_z + height / 2),
                mat,
                group,
            )
            part += 1
        cursor = max(cursor, end)


def open_room(
    name: str,
    center_x: float,
    center_y: float,
    width_x: float,
    width_y: float,
    base_z: float,
    wall_height: float = 8.0,
    wall_thickness: float = 1.0,
    group: str = "04 Women's Court Chambers",
) -> None:
    box(
        f"{name} – כותל צפוני", (width_x, wall_thickness, wall_height),
        (center_x, center_y + width_y / 2, base_z + wall_height / 2),
        "Jerusalem limestone", group,
    )
    box(
        f"{name} – כותל דרומי", (width_x, wall_thickness, wall_height),
        (center_x, center_y - width_y / 2, base_z + wall_height / 2),
        "Jerusalem limestone", group,
    )
    box(
        f"{name} – כותל מזרחי", (wall_thickness, width_y, wall_height),
        (center_x - width_x / 2, center_y, base_z + wall_height / 2),
        "Jerusalem limestone", group,
    )
    box(
        f"{name} – כותל מערבי", (wall_thickness, width_y, wall_height),
        (center_x + width_x / 2, center_y, base_z + wall_height / 2),
        "Jerusalem limestone", group,
    )


def add_womens_chamber_shell(
    name: str, center_x: float, center_y: float, base_z: float,
    doorway_x_side: int,
) -> None:
    """Build one of Middot 2:5's unroofed 40-cubit corner chambers.

    The size and lack of a roof are sourced. Door, paving, masonry articulation,
    drainage and fittings are deliberately legible reconstruction details.
    """
    group = "04 Women's Court Chambers"
    width = SOURCE["corner_chamber"][0]
    wall, height = 0.9, 10.0
    inner_wall_x = center_x + doorway_x_side * (width / 2 - wall / 2)
    outer_wall_x = center_x - doorway_x_side * (width / 2 - wall / 2)
    doorway_w, doorway_h = 6.0, 7.5
    side_span = (width - doorway_w) / 2

    # Stone paving is split into large slabs so the open-to-sky courts read at
    # close range without producing an excessive web-model mesh count.
    for row, offset_y in enumerate((-13.95, -4.65, 4.65, 13.95), 1):
        for column, offset_x in enumerate((-13.95, -4.65, 4.65, 13.95), 1):
            tile = box(
                f"{name} – אבן ריצוף {row:02d}-{column:02d}",
                (9.0, 9.0, 0.22),
                (center_x + offset_x, center_y + offset_y, base_z + 0.11),
                "Pale court stone", group, 0.035,
            )
            tile["certainty"] = "schematic"

    # Three solid walls and an inward-facing wall with a proper doorway.
    box(f"{name} – כותל חיצוני", (wall, width, height),
        (outer_wall_x, center_y, base_z + height / 2),
        "Jerusalem limestone", group, 0.08)
    for y_side, direction in ((-1, "דרומי"), (1, "צפוני")):
        box(f"{name} – כותל {direction}", (width, wall, height),
            (center_x, center_y + y_side * (width / 2 - wall / 2),
             base_z + height / 2), "Jerusalem limestone", group, 0.08)
    for y_side, direction in ((-1, "דרומי"), (1, "צפוני")):
        box(f"{name} – חזית פנימית {direction}",
            (wall, side_span, height),
            (inner_wall_x,
             center_y + y_side * (doorway_w / 2 + side_span / 2),
             base_z + height / 2), "Jerusalem limestone", group, 0.08)
    box(f"{name} – משקוף הפתח", (wall, doorway_w, height - doorway_h),
        (inner_wall_x, center_y,
         base_z + doorway_h + (height - doorway_h) / 2),
        "Jerusalem limestone", group, 0.08)
    box(f"{name} – אבן הסף", (1.5, doorway_w, 0.32),
        (inner_wall_x, center_y, base_z + 0.16),
        "Pale court stone", group, 0.05)
    for y_side in (-1, 1):
        box(f"{name} – אומנת פתח", (1.35, 1.25, 8.4),
            (inner_wall_x - doorway_x_side * 0.15,
             center_y + y_side * (doorway_w / 2 + 0.25),
             base_z + 4.2), "Pale court stone", group, 0.09)

    # A timber leaf stands open against the inside wall, with bronze hinge and
    # studs. Its geometry is schematic because Middot gives no door design.
    leaf_x = inner_wall_x - doorway_x_side * 3.15
    leaf_y = center_y + doorway_w / 2 + 0.30
    box(f"{name} – דלת פתוחה", (5.8, 0.32, 7.0),
        (leaf_x, leaf_y, base_z + 3.5), "Wood", group, 0.07)
    beam_between(f"{name} – ציר הדלת",
                 (inner_wall_x - doorway_x_side * 0.25, leaf_y, base_z + 0.4),
                 (inner_wall_x - doorway_x_side * 0.25, leaf_y, base_z + 6.7),
                 0.11, "Bronze", group, 12)
    for stud_x in (-1.6, 0.0, 1.6):
        for stud_z in (1.7, 3.5, 5.3):
            sphere(f"{name} – מסמר דלת", 0.11,
                   (leaf_x + stud_x, leaf_y - 0.18, base_z + stud_z),
                   "Bronze", group, subdivisions=1)

    # A moulded coping caps each wall but leaves the chamber explicitly
    # unroofed, as stated by Middot and its citation of Ezekiel 46.
    box(f"{name} – כרכוב צפוני", (width + 0.6, 1.25, 0.55),
        (center_x, center_y + width / 2, base_z + height + 0.275),
        "Pale court stone", group, 0.08)
    box(f"{name} – כרכוב דרומי", (width + 0.6, 1.25, 0.55),
        (center_x, center_y - width / 2, base_z + height + 0.275),
        "Pale court stone", group, 0.08)
    for x_side, direction in ((-1, "מזרחי"), (1, "מערבי")):
        box(f"{name} – כרכוב {direction}", (1.25, width - 1.2, 0.55),
            (center_x + x_side * width / 2, center_y,
             base_z + height + 0.275), "Pale court stone", group, 0.08)

    # Small central drain and bronze grate explain how an unroofed paved room
    # can shed rainwater; their exact form is an architectural reconstruction.
    box(f"{name} – פתח ניקוז", (2.1, 2.1, 0.08),
        (center_x, center_y, base_z + 0.245), "Dark opening", group, 0.02)
    for offset in (-0.7, -0.23, 0.23, 0.7):
        box(f"{name} – סורג ניקוז", (0.10, 1.9, 0.10),
            (center_x + offset, center_y, base_z + 0.33),
            "Bronze", group, 0.02)

    # Put the chamber name on the north/south wall that faces the open court,
    # rather than laying it across the chamber floor.
    court_wall_side = -1 if center_y > COURT_CENTER_Y else 1
    label_on_y_wall(
        name,
        center_x,
        center_y + court_wall_side * (width / 2 + 0.04),
        base_z + height * 0.55,
        court_wall_side,
        1.65,
    )


def add_amphora(
    name: str, x: float, y: float, base_z: float,
    contents: str = "Olive oil", scale: float = 1.0,
) -> None:
    """Add a readable low-poly storage jar with neck, rim and two handles."""
    group = "04 Women's Court Chambers"
    body = sphere(name, 1.05 * scale, (x, y, base_z + 1.18 * scale),
                  "Terracotta", group, scale=(0.78, 0.78, 1.12), subdivisions=2)
    body["contents"] = "wine" if contents == "Wine" else "olive oil"
    cylinder(f"{name} – צוואר", 0.38 * scale, 0.75 * scale,
             (x, y, base_z + 2.42 * scale), "Terracotta", group, 24)
    torus(f"{name} – שפה", 0.42 * scale, 0.09 * scale,
          (x, y, base_z + 2.82 * scale), "Terracotta", group)
    cylinder(f"{name} – תכולה", 0.31 * scale, 0.08 * scale,
             (x, y, base_z + 2.78 * scale), contents, group, 24)
    box(f"{name} – רגל", (0.48 * scale, 0.48 * scale, 0.28 * scale),
        (x, y, base_z + 0.14 * scale), "Terracotta", group, 0.06)
    for side in (-1, 1):
        torus(f"{name} – ידית", 0.36 * scale, 0.075 * scale,
              (x + side * 0.72 * scale, y, base_z + 2.08 * scale),
              "Terracotta", group, rotation=(math.pi / 2, 0, 0))


def add_cauldron(name: str, x: float, y: float, base_z: float) -> None:
    """Add a pot over an ember hearth for the Nazirite peace offering."""
    group = "04 Women's Court Chambers"
    box(f"{name} – מוקד אבן", (5.6, 5.0, 0.55),
        (x, y, base_z + 0.275), "Jerusalem limestone", group, 0.10)
    cylinder(f"{name} – אפר", 1.75, 0.14, (x, y, base_z + 0.62),
             "Ash", group, 32)
    for ember_index, (dx, dy) in enumerate(((-0.8, -0.4), (0.0, 0.55),
                                             (0.85, -0.25), (0.1, -0.65)), 1):
        sphere(f"{name} – גחל {ember_index}", 0.34,
               (x + dx, y + dy, base_z + 0.82), "Ember", group,
               scale=(1.5, 0.65, 0.45), subdivisions=1)
    for leg_x, leg_y in ((-1.35, -0.75), (1.35, -0.75), (0.0, 1.35)):
        beam_between(f"{name} – רגל דוד",
                     (x + leg_x, y + leg_y, base_z + 0.65),
                     (x + leg_x, y + leg_y, base_z + 2.05),
                     0.14, "Bronze", group, 12)
    cylinder(f"{name} – דוד", 2.05, 1.65, (x, y, base_z + 2.75),
             "Bronze", group, 40)
    torus(f"{name} – שפת הדוד", 2.02, 0.14,
          (x, y, base_z + 3.60), "Bronze", group)
    cylinder(f"{name} – תבשיל השלמים", 1.82, 0.10,
             (x, y, base_z + 3.58), "Wine", group, 40)
    for side in (-1, 1):
        torus(f"{name} – ידית", 0.52, 0.10,
              (x + side * 2.05, y, base_z + 3.02), "Bronze", group,
              rotation=(math.pi / 2, 0, 0))


def add_log_bundle(
    name: str, x: float, y: float, base_z: float,
    length: float = 6.0, rejected: bool = False,
) -> None:
    """Stack six inspectable altar-wood logs; rejected bundles show bore marks."""
    group = "04 Women's Court Chambers"
    log_index = 0
    for row, z_offset in enumerate((0.34, 0.92, 1.50)):
        count = 3 if row == 0 else 2 if row == 1 else 1
        for column in range(count):
            log_index += 1
            dx = (column - (count - 1) / 2) * 0.72
            beam_between(f"{name} – קורה {log_index}",
                         (x + dx, y - length / 2, base_z + z_offset),
                         (x + dx, y + length / 2, base_z + z_offset),
                         0.30, "Cedar", group, 12)
            if rejected and log_index <= 3:
                for mark_index, along in enumerate((-1.2, 0.55), 1):
                    sphere(f"{name} – נקב תולעת {log_index}-{mark_index}",
                           0.10, (x + dx - 0.29, y + along,
                                  base_z + z_offset + 0.05),
                           "Hair and soot", group, subdivisions=1)


def add_nazirite_chamber_details(x: float, y: float, base_z: float) -> None:
    group = "04 Women's Court Chambers"
    add_cauldron("לשכת הנזירים – דוד שלמים מזרחי", x - 9.0, y - 8.5, base_z)
    add_cauldron("לשכת הנזירים – דוד שלמים מערבי", x + 7.5, y - 8.5, base_z)
    # Hair/soot beneath the cauldron visualises the explicit ritual action.
    for index, offset in enumerate((-0.7, -0.35, 0.0, 0.35, 0.7), 1):
        beam_between(f"לשכת הנזירים – שיער תחת הדוד {index}",
                     (x + 7.5 + offset, y - 9.1, base_z + 0.98),
                     (x + 7.0 + offset, y - 8.0, base_z + 0.90),
                     0.035, "Hair and soot", group, 8)
    box("לשכת הנזירים – ספסל גילוח", (8.0, 2.2, 0.55),
        (x - 6.0, y + 8.5, base_z + 1.65), "Cedar", group, 0.08)
    for leg_x in (-3.3, 3.3):
        box("לשכת הנזירים – רגל ספסל", (0.45, 1.55, 1.4),
            (x - 6.0 + leg_x, y + 8.5, base_z + 0.7), "Cedar", group, 0.04)
    box("לשכת הנזירים – תער", (1.8, 0.36, 0.08),
        (x - 6.0, y + 8.0, base_z + 2.02), "Bronze", group, 0.04)
    box("לשכת הנזירים – ידית התער", (0.9, 0.22, 0.18),
        (x - 7.1, y + 8.0, base_z + 2.05), "Wood", group, 0.04)
    add_log_bundle("לשכת הנזירים – עצי הסקה", x + 10.0, y + 8.0,
                   base_z, length=5.0)
    for basket_index, basket_x in enumerate((x + 3.0, x + 6.0), 1):
        torus(f"לשכת הנזירים – סל מצות {basket_index}", 1.25, 0.14,
              (basket_x, y + 9.0, base_z + 0.65), "Cedar", group)
        cylinder(f"לשכת הנזירים – מצות {basket_index}", 1.05, 0.16,
                 (basket_x, y + 9.0, base_z + 0.70),
                 "Pale court stone", group, 24)


def add_wood_chamber_details(x: float, y: float, base_z: float) -> None:
    group = "04 Women's Court Chambers"
    for index, (dx, dy) in enumerate(((-11, -10), (-5, -10), (1, -10),
                                      (-11, 7), (-5, 7), (1, 7)), 1):
        add_log_bundle(f"לשכת דיר העצים – ערמת עצים כשרה {index}",
                       x + dx, y + dy, base_z, length=6.4)
    add_log_bundle("לשכת דיר העצים – עצים פסולים ומתולעים",
                   x + 11.0, y + 9.0, base_z, length=6.0, rejected=True)
    box("לשכת דיר העצים – שולחן בדיקה", (9.0, 3.0, 0.45),
        (x + 6.0, y - 3.0, base_z + 2.55), "Cedar", group, 0.07)
    for dx in (-3.7, 3.7):
        box("לשכת דיר העצים – רגל שולחן", (0.45, 2.2, 2.3),
            (x + 6.0 + dx, y - 3.0, base_z + 1.15), "Cedar", group, 0.04)
    beam_between("לשכת דיר העצים – קורה בבדיקה",
                 (x + 2.3, y - 3.0, base_z + 3.15),
                 (x + 9.7, y - 3.0, base_z + 3.15),
                 0.34, "Cedar", group, 16)
    # Simple axe and awl communicate inspection/sorting without asserting a
    # specific ancient tool kit.
    beam_between("לשכת דיר העצים – ידית גרזן",
                 (x + 5.0, y - 2.2, base_z + 2.90),
                 (x + 7.3, y - 2.2, base_z + 3.00),
                 0.10, "Wood", group, 12)
    box("לשכת דיר העצים – להב גרזן", (0.55, 0.16, 0.75),
        (x + 7.55, y - 2.2, base_z + 3.0), "Bronze", group, 0.04)
    box("לשכת דיר העצים – מחיצת עצים פסולים", (0.35, 10.0, 3.0),
        (x + 14.8, y + 8.0, base_z + 1.5), "Assumed element", group, 0.04)


def add_lepers_chamber_details(x: float, y: float, base_z: float) -> None:
    group = "04 Women's Court Chambers"
    bath_x, bath_y = x - 5.0, y - 2.5
    stair_center_x = bath_x + 3.0
    stair_opening_width = 6.0
    # Raised cutaway edges keep the immersion pool visible above the existing
    # solid court platform; the historical pool would of course be excavated.
    for dx in (-6.5, 6.5):
        box("לשכת המצורעים – דופן המקווה", (0.8, 10.0, 3.0),
            (bath_x + dx, bath_y, base_z + 1.5),
            "Jerusalem limestone", group, 0.08)
    # Split the southern wall around the stair, giving the raised cutaway pool
    # a real walkable entrance instead of a solid wall across its top step.
    wall_left = bath_x - 6.9
    wall_right = bath_x + 6.9
    opening_left = stair_center_x - stair_opening_width / 2
    opening_right = stair_center_x + stair_opening_width / 2
    for start_x, end_x in ((wall_left, opening_left),
                           (opening_right, wall_right)):
        if end_x <= start_x:
            continue
        box("לשכת המצורעים – דופן המקווה דרומית",
            (end_x - start_x, 0.8, 3.0),
            ((start_x + end_x) / 2, bath_y - 5.0, base_z + 1.5),
            "Jerusalem limestone", group, 0.08)
    box("לשכת המצורעים – דופן המקווה צפונית", (13.8, 0.8, 3.0),
        (bath_x, bath_y + 5.0, base_z + 1.5),
        "Jerusalem limestone", group, 0.08)
    box("לשכת המצורעים – חלל המקווה", (12.0, 8.2, 0.35),
        (bath_x, bath_y, base_z + 0.36), "Dark opening", group, 0.03)
    box("לשכת המצורעים – מי המקווה", (11.7, 7.9, 0.16),
        (bath_x, bath_y, base_z + 0.62), "Water", group, 0.02)
    for step_index in range(6):
        step_w = 5.4 - step_index * 0.72
        box(f"לשכת המצורעים – מעלה במקווה {step_index + 1}",
            (step_w, 1.0, 0.42),
            (bath_x + 3.0 + step_index * 0.55,
             bath_y - 4.0 + step_index * 0.75,
             base_z + 2.65 - step_index * 0.38),
            "Pale court stone", group, 0.04)
    # Because the didactic pool is raised above the court platform, this short
    # outer flight connects the chamber floor to the descending immersion steps.
    for step_index in range(7):
        step_height = (step_index + 1) * 0.4
        box(f"לשכת המצורעים – מעלה חיצונית למקווה {step_index + 1}",
            (5.4, 1.15, step_height),
            (stair_center_x, bath_y - 11.0 + step_index,
             base_z + step_height / 2),
            "Pale court stone", group, 0.04)
    beam_between("לשכת המצורעים – מאחז ירידה",
                 (bath_x + 5.5, bath_y - 4.0, base_z + 3.5),
                 (bath_x + 3.5, bath_y + 0.5, base_z + 1.5),
                 0.10, "Bronze", group, 12)
    box("לשכת המצורעים – ספסל הכנה", (9.0, 2.2, 0.48),
        (x + 7.0, y + 10.0, base_z + 1.55), "Pale court stone", group, 0.08)
    for dx in (-3.6, 3.6):
        box("לשכת המצורעים – רגל ספסל", (0.55, 1.6, 1.3),
            (x + 7.0 + dx, y + 10.0, base_z + 0.65),
            "Jerusalem limestone", group, 0.05)
    cylinder("לשכת המצורעים – כד מים", 0.85, 1.65,
             (x + 9.5, y + 9.8, base_z + 2.62), "Terracotta", group, 24)
    torus("לשכת המצורעים – שפת כד", 0.82, 0.10,
          (x + 9.5, y + 9.8, base_z + 3.46), "Terracotta", group)
    box("לשכת המצורעים – תעלת ניקוז", (14.0, 0.75, 0.28),
        (bath_x + 3.0, bath_y + 6.0, base_z + 0.20),
        "Assumed element", group, 0.03)


def add_oil_chamber_details(x: float, y: float, base_z: float) -> None:
    group = "04 Women's Court Chambers"
    # Stone-and-timber shelving, large storage jars and smaller measuring jars
    # distinguish wine from oil while preserving the sourced shared storage use.
    for shelf_y in (y - 12.5, y + 12.5):
        for shelf_z in (1.2, 3.8):
            box("לשכת בית שמניה – מדף קנקנים", (22.0, 1.4, 0.35),
                (x - 3.0, shelf_y, base_z + shelf_z), "Cedar", group, 0.05)
        for shelf_x in (x - 13.0, x + 7.0):
            box("לשכת בית שמניה – תמיכת מדף", (0.5, 1.2, 4.2),
                (shelf_x, shelf_y, base_z + 2.1), "Cedar", group, 0.04)
    jar_positions = ((-11, -12.3), (-6, -12.3), (-1, -12.3), (4, -12.3),
                     (-11, 12.3), (-6, 12.3), (-1, 12.3), (4, 12.3),
                     (10, -7), (10, 0), (10, 7))
    for index, (dx, dy) in enumerate(jar_positions, 1):
        contents = "Wine" if index % 3 == 0 else "Olive oil"
        add_amphora(f"לשכת בית שמניה – קנקן {index:02d}",
                    x + dx, y + dy, base_z + (1.4 if abs(dy) > 10 else 0.0),
                    contents, scale=0.88 if abs(dy) > 10 else 1.20)
    box("לשכת בית שמניה – שולחן מזיגה", (9.0, 4.0, 0.48),
        (x - 4.0, y, base_z + 2.55), "Pale court stone", group, 0.08)
    for dx in (-3.7, 3.7):
        box("לשכת בית שמניה – רגל שולחן", (0.55, 3.1, 2.3),
            (x - 4.0 + dx, y, base_z + 1.15),
            "Jerusalem limestone", group, 0.05)
    for vessel_index, (dx, contents) in enumerate(((-2.0, "Olive oil"),
                                                   (0.0, "Wine"),
                                                   (2.0, "Olive oil")), 1):
        cylinder(f"לשכת בית שמניה – כלי מידה {vessel_index}", 0.65, 0.9,
                 (x - 4.0 + dx, y, base_z + 3.25),
                 "Bronze", group, 24)
        cylinder(f"לשכת בית שמניה – תכולת כלי מידה {vessel_index}",
                 0.57, 0.06, (x - 4.0 + dx, y, base_z + 3.72),
                 contents, group, 24)
    cylinder("לשכת בית שמניה – אגן איסוף", 2.2, 0.28,
             (x - 4.0, y + 4.0, base_z + 0.35), "Bronze", group, 32)
    cylinder("לשכת בית שמניה – שמן באגן", 2.0, 0.08,
             (x - 4.0, y + 4.0, base_z + 0.52), "Olive oil", group, 32)


def add_gate_doors_x(
    name: str, center_x: float, center_y: float, threshold_z: float,
    mat: str, group: str,
) -> None:
    """Two gate leaves shown folded open against a wall running east-west."""
    for side in (-1, 1):
        leaf_x = center_x + side * 4.55
        box(f"{name} – כנף דלת {'מערבית' if side > 0 else 'מזרחית'}",
            (0.42, 4.8, 18.5),
            (leaf_x, center_y, threshold_z + 9.25), mat, group, 0.08)
        beam_between(f"{name} – ציר דלת",
                     (center_x + side * 4.82, center_y, threshold_z + 0.7),
                     (center_x + side * 4.82, center_y, threshold_z + 17.8),
                     0.14, "Bronze", group, 12)
        for stud_y in (-1.45, 0.0, 1.45):
            for stud_z in (4.0, 9.2, 14.4):
                sphere(f"{name} – מסמר דלת", 0.16,
                       (leaf_x - side * 0.24, center_y + stud_y,
                        threshold_z + stud_z),
                       "Bronze", group, subdivisions=1)
        torus(f"{name} – טבעת משיכה", 0.42, 0.08,
              (leaf_x - side * 0.26, center_y, threshold_z + 8.8),
              "Bronze", group, rotation=(0, math.pi / 2, 0))


def add_gate_doors_y(
    name: str, center_x: float, center_y: float, threshold_z: float,
    mat: str, group: str,
) -> None:
    """Two gate leaves shown folded open against a wall running north-south."""
    for side in (-1, 1):
        leaf_y = center_y + side * 4.55
        box(f"{name} – כנף דלת {'צפונית' if side > 0 else 'דרומית'}",
            (4.8, 0.42, 18.5),
            (center_x, leaf_y, threshold_z + 9.25), mat, group, 0.08)
        beam_between(f"{name} – ציר דלת",
                     (center_x, center_y + side * 4.82, threshold_z + 0.7),
                     (center_x, center_y + side * 4.82, threshold_z + 17.8),
                     0.14, "Bronze", group, 12)
        for stud_x in (-1.45, 0.0, 1.45):
            for stud_z in (4.0, 9.2, 14.4):
                sphere(f"{name} – מסמר דלת", 0.16,
                       (center_x + stud_x, leaf_y + side * 0.24,
                        threshold_z + stud_z),
                       "Bronze", group, subdivisions=1)
        torus(f"{name} – טבעת משיכה", 0.42, 0.08,
              (center_x, leaf_y + side * 0.26, threshold_z + 8.8),
              "Bronze", group, rotation=(math.pi / 2, 0, 0))


def add_azarah_gatehouse_x(
    name: str, center_x: float, center_y: float, threshold_z: float,
    door_mat: str = "Wood", upper_storey: bool = False,
) -> None:
    """Detailed square-headed gatehouse for a north or south Azarah wall."""
    group = "06 Azarah Gates"
    width = ASSUMED["azarah_gatehouse_width"]
    depth = ASSUMED["azarah_gatehouse_depth"]
    for side in (-1, 1):
        box(f"{name} – אומנת שער",
            (2.0, depth, 22.0),
            (center_x + side * (width / 2 - 1.0), center_y,
             threshold_z + 11.0),
            "Jerusalem limestone", group, 0.16)
        box(f"{name} – בסיס אומנה", (2.7, depth + 0.8, 0.8),
            (center_x + side * (width / 2 - 1.0), center_y,
             threshold_z + 0.4), "Pale court stone", group, 0.10)
        box(f"{name} – כותרת אומנה", (2.8, depth + 0.8, 1.0),
            (center_x + side * (width / 2 - 1.0), center_y,
             threshold_z + 20.5), "Pale court stone", group, 0.12)
    box(f"{name} – משקוף", (width, depth, 3.0),
        (center_x, center_y, threshold_z + 21.5),
        "Jerusalem limestone", group, 0.12)
    box(f"{name} – כרכוב", (width + 1.2, depth + 1.2, 0.8),
        (center_x, center_y, threshold_z + 23.4),
        "Pale court stone", group, 0.12)
    box(f"{name} – אבן הסף", (10.5, depth, 0.55),
        (center_x, center_y, threshold_z + 0.275),
        "Pale court stone", group, 0.06)
    add_gate_doors_x(name, center_x, center_y, threshold_z, door_mat, group)

    if upper_storey:
        box(f"{name} – עליית השומרים", (13.0, depth - 0.6, 8.0),
            (center_x, center_y, threshold_z + 27.8),
            "Assumed element", group, 0.14)
        for side in (-1, 1):
            box(f"{name} – חלון העלייה", (2.4, 0.16, 3.0),
                (center_x + side * 3.5, center_y - depth / 2 - 0.10,
                 threshold_z + 28.0), "Dark opening", group, 0.08)
        box(f"{name} – גג העלייה", (14.0, depth + 0.5, 0.7),
            (center_x, center_y, threshold_z + 32.15),
            "Pale court stone", group, 0.10)
    label(name, center_x, center_y, threshold_z + (33.0 if upper_storey else 24.2),
          1.45)


def add_azarah_gatehouse_y(
    name: str, center_x: float, center_y: float, threshold_z: float,
    door_mat: str = "Wood",
) -> None:
    """Detailed gatehouse for the eastern Nicanor opening."""
    group = "06 Azarah Gates"
    width = ASSUMED["azarah_gatehouse_width"]
    depth = ASSUMED["azarah_gatehouse_depth"]
    for side in (-1, 1):
        box(f"{name} – אומנת שער",
            (depth, 2.0, 22.0),
            (center_x, center_y + side * (width / 2 - 1.0),
             threshold_z + 11.0),
            "Jerusalem limestone", group, 0.16)
        box(f"{name} – בסיס אומנה", (depth + 0.8, 2.7, 0.8),
            (center_x, center_y + side * (width / 2 - 1.0),
             threshold_z + 0.4), "Pale court stone", group, 0.10)
        box(f"{name} – כותרת אומנה", (depth + 0.8, 2.8, 1.0),
            (center_x, center_y + side * (width / 2 - 1.0),
             threshold_z + 20.5), "Pale court stone", group, 0.12)
    box(f"{name} – משקוף", (depth, width, 3.0),
        (center_x, center_y, threshold_z + 21.5),
        "Jerusalem limestone", group, 0.12)
    box(f"{name} – כרכוב", (depth + 1.2, width + 1.2, 0.8),
        (center_x, center_y, threshold_z + 23.4),
        "Pale court stone", group, 0.12)
    box(f"{name} – אבן הסף", (depth, 10.5, 0.55),
        (center_x, center_y, threshold_z + 0.275),
        "Pale court stone", group, 0.06)
    add_gate_doors_y(name, center_x, center_y, threshold_z, door_mat, group)
    label(name, center_x, center_y, threshold_z + 24.2, 1.7)


def add_chamber_shell(
    name: str, center_x: float, side: int, width: float, base_z: float,
) -> tuple[float, float]:
    """Add a north/south wall chamber with a didactic partial roof cutaway."""
    group = "06 Azarah Chambers"
    depth = ASSUMED["azarah_chamber_depth"]
    height = ASSUMED["azarah_chamber_height"]
    outer_y = COURT_CENTER_Y + side * SOURCE["azarah"][1] / 2
    inner_y = outer_y - side * depth
    center_y = (outer_y + inner_y) / 2
    wall = 0.8
    box(f"{name} – כותל חיצוני", (width, wall, height),
        (center_x, outer_y - side * wall / 2, base_z + height / 2),
        "Jerusalem limestone", group, 0.08)
    for end in (-1, 1):
        box(f"{name} – כותל צד", (wall, depth, height),
            (center_x + end * (width / 2 - wall / 2), center_y,
             base_z + height / 2), "Jerusalem limestone", group, 0.08)
    door_w, door_h = 4.0, 7.0
    side_span = (width - door_w) / 2
    for end in (-1, 1):
        box(f"{name} – חזית {'מערבית' if end > 0 else 'מזרחית'}",
            (side_span, wall, height),
            (center_x + end * (door_w / 2 + side_span / 2),
             inner_y + side * wall / 2, base_z + height / 2),
            "Jerusalem limestone", group, 0.08)
    box(f"{name} – משקוף הפתח", (door_w, wall, height - door_h),
        (center_x, inner_y + side * wall / 2,
         base_z + door_h + (height - door_h) / 2),
        "Jerusalem limestone", group, 0.08)
    box(f"{name} – דלת פתוחה", (3.7, 0.28, 6.6),
        (center_x + 2.05, inner_y + side * 1.9, base_z + 3.3),
        "Wood", group, 0.06)
    # Only the outer half is roofed, exposing the characteristic contents in
    # the overview while still reading as a chamber rather than a low pen.
    roof_depth = depth * 0.54
    box(f"{name} – גג חתוך לתצוגה", (width + 0.6, roof_depth, 0.65),
        (center_x, outer_y - side * roof_depth / 2, base_z + height + 0.325),
        "Pale court stone", group, 0.10)
    box(f"{name} – כרכוב", (width + 0.8, 0.9, 0.7),
        (center_x, outer_y - side * 0.45, base_z + height + 0.35),
        "Pale court stone", group, 0.08)
    label(name, center_x, center_y, base_z + height + 1.0, 1.18)
    return center_y, inner_y


def add_gazit_chamber(base_z: float) -> tuple[float, float]:
    """Build the distinctive, boundary-straddling Chamber of Hewn Stone.

    Middot 5:4 identifies this as the seat of the Great Sanhedrin. This model
    follows the Rambam placement summarized in Hebrew Wikipedia: the Azarah's
    north-east corner, with the southern half sacred and the northern half in
    the Cheil. Yoma 25a gives a doorway to each domain. The unrecorded plan
    dimensions and furnishings remain deliberately schematic.
    """
    group = "06 Azarah Chambers"
    name = "לשכת הגזית"
    width = ASSUMED["gazit_chamber_width"]
    depth = ASSUMED["gazit_chamber_depth"]
    height = ASSUMED["gazit_chamber_height"]
    center_x = ASSUMED["gazit_chamber_center_x"]
    boundary_y = COURT_NORTH_Y
    south_y = boundary_y - depth / 2
    north_y = boundary_y + depth / 2
    wall = 0.9
    door_w = 5.0
    door_h = 8.0

    # The non-sacred half projects beyond the raised Azarah platform, so a
    # schematic stone substructure carries it up to the court floor level.
    box(f"{name} – מסד המחצית שבחול", (width, depth / 2, base_z),
        (center_x, boundary_y + depth / 4, base_z / 2),
        "Assumed element", group, 0.08)

    # Two floor tones make the sourced half-sacred / half-non-sacred
    # relationship readable without implying a known boundary treatment.
    box(f"{name} – מחצית קודש", (width, depth / 2, 0.5),
        (center_x, boundary_y - depth / 4, base_z + 0.25),
        "Pale court stone", group, 0.05)
    box(f"{name} – מחצית חול", (width, depth / 2, 0.5),
        (center_x, boundary_y + depth / 4, base_z + 0.25),
        "Assumed element", group, 0.05)
    box(f"{name} – סימון גבול קודש וחול", (width - 1.0, 0.35, 0.10),
        (center_x, boundary_y, base_z + 0.56),
        "Bronze", group, 0.02)

    for side_x, side_name in ((center_x - width / 2, "מזרח"),
                              (center_x + width / 2, "מערב")):
        box(f"{name} – כותל {side_name}", (wall, depth, height),
            (side_x, boundary_y, base_z + height / 2),
            "Jerusalem limestone", group, 0.10)
        # Projecting ashlar bands distinguish this hall from the smaller
        # service rooms at overview scale.
        for course_z in (3.5, 7.0, 10.5):
            box(f"{name} – נדבך גזית {side_name}",
                (wall + 0.22, depth + 0.18, 0.22),
                (side_x, boundary_y, base_z + course_z),
                "Pale court stone", group, 0.03)

    jamb_span = (width - door_w) / 2
    for doorway_y, doorway_name, inward in (
        (south_y, "פתח אל הקודש", 1),
        (north_y, "פתח אל החול", -1),
    ):
        for side_x in (-1, 1):
            box(f"{name} – אומנת {doorway_name}",
                (jamb_span, wall, height),
                (center_x + side_x * (door_w / 2 + jamb_span / 2),
                 doorway_y, base_z + height / 2),
                "Jerusalem limestone", group, 0.10)
        box(f"{name} – משקוף {doorway_name}",
            (door_w, wall, height - door_h),
            (center_x, doorway_y,
             base_z + door_h + (height - door_h) / 2),
            "Jerusalem limestone", group, 0.10)
        box(f"{name} – {doorway_name}", (door_w - 0.35, 0.18, door_h - 0.4),
            (center_x, doorway_y, base_z + (door_h - 0.4) / 2),
            "Dark opening", group, 0.03)
        box(f"{name} – דלת פתוחה של {doorway_name}",
            (door_w - 0.7, 0.28, door_h - 0.8),
            (center_x + 2.8, doorway_y + inward * 2.0,
             base_z + (door_h - 0.8) / 2),
            "Cedar", group, 0.05)

    # A perimeter roof leaves the centre open as a didactic cutaway while
    # preserving the reading of a substantial roofed hall.
    for roof_x in (center_x - width / 2 + 2.3,
                   center_x + width / 2 - 2.3):
        box(f"{name} – גג חתוך לתצוגה", (4.6, depth + 0.8, 0.75),
            (roof_x, boundary_y, base_z + height + 0.375),
            "Pale court stone", group, 0.08)
    for roof_y in (south_y, north_y):
        box(f"{name} – כרכוב", (width + 0.8, 1.0, 0.75),
            (center_x, roof_y, base_z + height + 0.375),
            "Pale court stone", group, 0.08)

    # Mishnah Sanhedrin 4:3 describes the court sitting in a semicircle.
    # Two stepped arcs make that institution visible without claiming a
    # measured seating plan for this room.
    seats_center_x = center_x + 1.5  # western side of the non-sacred half
    seats_center_y = north_y - 3.7
    seat_number = 1
    for tier, radius, count in ((1, 5.8, 9), (2, 8.0, 13)):
        for index in range(count):
            angle = math.radians(14 + 152 * index / (count - 1))
            seat_x = seats_center_x + radius * math.cos(angle)
            seat_y = seats_center_y - radius * math.sin(angle)
            seat = box(
                f"{name} – מושב הסנהדרין {seat_number:02d}",
                (2.25, 0.95, 0.95),
                (seat_x, seat_y, base_z + 0.98 + (tier - 1) * 0.45),
                "Cedar", group, 0.08,
            )
            seat.rotation_euler[2] = -(angle + math.pi / 2)
            seat_number += 1
    box(f"{name} – שולחן בית הדין", (5.2, 2.4, 0.4),
        (seats_center_x, seats_center_y - 1.4, base_z + 2.3),
        "Cedar", group, 0.08)

    label("לשכת הגזית – הסנהדרין הגדולה", center_x, boundary_y,
          base_z + height + 1.2, 1.45)
    return center_x, boundary_y


def semi_disc(
    name: str,
    center_x: float,
    center_y: float,
    radius: float,
    base_z: float,
    height: float,
    group: str,
    segments: int = 48,
) -> None:
    """Extruded half-disc extending east (-X), used for the curved steps."""
    top_z = base_z + height
    vertices: list[tuple[float, float, float]] = []
    for z in (base_z, top_z):
        vertices.append(scene_location((center_x, center_y, z)))
        for index in range(segments + 1):
            theta = -math.pi / 2 + math.pi * index / segments
            x = center_x - radius * math.cos(theta)
            y = center_y + radius * math.sin(theta)
            vertices.append(scene_location((x, y, z)))
    ring = segments + 2
    faces: list[tuple[int, ...]] = []
    for index in range(segments):
        faces.append((0, index + 1, index + 2))
        faces.append((ring, ring + index + 2, ring + index + 1))
    for index in range(segments + 1):
        next_index = (index + 1) % (segments + 1)
        if index < segments:
            faces.append((index + 1, ring + index + 1, ring + next_index + 1, next_index + 1))
    faces.append((0, ring, ring + 1, 1))
    faces.append((0, segments + 1, ring + segments + 1, ring))
    if MIRROR_PLAN_Y:
        faces = [tuple(reversed(face)) for face in faces]
    mesh = bpy.data.meshes.new(hebrew_name(name))
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(hebrew_name(name), mesh)
    collection(group).objects.link(obj)
    obj.data.materials.append(MATERIALS["Pale court stone"])


def ramp_wedge(
    name: str,
    center_x: float,
    south_y: float,
    north_y: float,
    width_x: float,
    base_z: float,
    rise: float,
    group: str,
    mat: str = "White altar stone",
) -> None:
    half = width_x / 2
    vertices = [
        scene_location((center_x - half, south_y, base_z)),
        scene_location((center_x + half, south_y, base_z)),
        scene_location((center_x - half, north_y, base_z)),
        scene_location((center_x + half, north_y, base_z)),
        scene_location((center_x - half, north_y, base_z + rise)),
        scene_location((center_x + half, north_y, base_z + rise)),
    ]
    faces = [
        (0, 1, 3, 2), (2, 3, 5, 4), (0, 2, 4),
        (1, 5, 3), (0, 4, 5, 1),
    ]
    if MIRROR_PLAN_Y:
        faces = [tuple(reversed(face)) for face in faces]
    mesh = bpy.data.meshes.new(hebrew_name(name))
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(hebrew_name(name), mesh)
    collection(group).objects.link(obj)
    obj.data.materials.append(MATERIALS[mat])


def build_ground_and_mount() -> None:
    size_x, size_y = SOURCE["temple_mount"]
    box("Ground", (620, 620, 2), (0, 0, -2), "Ground", "01 Temple Mount")
    box("Temple Mount surface", (size_x, size_y, 1), (0, 0, -0.5),
        "Pale court stone", "01 Temple Mount")

    t = ASSUMED["mount_wall_thickness"]
    h = ASSUMED["mount_wall_height"]
    gate = SOURCE["standard_gate"][0]
    gated_wall_x("South wall", 0, -250, 500, t, h, 0,
                 [(-35, gate), (35, gate)], "02 Mount Walls and Gates")
    gated_wall_x("North wall", 0, 250, 500, t, h, 0,
                 [(0, gate)], "02 Mount Walls and Gates")
    gated_wall_y("East wall", -250, 0, 500, t, h, 0,
                 [(COURT_CENTER_Y, gate)], "02 Mount Walls and Gates")
    gated_wall_y("West wall", 250, 0, 500, t, h, 0,
                 [(COURT_CENTER_Y, gate)], "02 Mount Walls and Gates")
    label("מזרח / שער שושן", -237, COURT_CENTER_Y, h + 1)
    label("שערי חולדה", 0, -237, h + 1)
    label("מערב / שער קיפונוס", 237, COURT_CENTER_Y, h + 1)
    label("צפון / שער טדי", 0, 237, h + 1)


def build_soreg() -> None:
    clearance = INTERPRETED["cheil_width"]
    east = WOMEN_EAST_X - clearance
    west = AZARAH_WEST_X + clearance
    south = COURT_SOUTH_Y - clearance
    north = COURT_NORTH_Y + clearance
    height = SOURCE["soreg_height_tefach"] / 6.0
    spacing = ASSUMED["soreg_post_spacing"]
    post = 0.35
    group = "03 Soreg and Cheil (interpreted footprint)"

    # A thin contrasting paving band makes the interpreted ten-cubit cheil
    # legible. Its height and finish are visual conventions, not source data.
    inner_width_x = AZARAH_WEST_X - WOMEN_EAST_X
    inner_width_y = COURT_NORTH_Y - COURT_SOUTH_Y
    outer_width_x = inner_width_x + 2 * clearance
    box("Cheil north band", (outer_width_x, clearance, 0.2),
        ((east + west) / 2, COURT_NORTH_Y + clearance / 2, 0.1),
        "Assumed element", group)
    box("Cheil south band", (outer_width_x, clearance, 0.2),
        ((east + west) / 2, COURT_SOUTH_Y - clearance / 2, 0.1),
        "Assumed element", group)
    box("Cheil east band", (clearance, inner_width_y, 0.2),
        (WOMEN_EAST_X - clearance / 2, COURT_CENTER_Y, 0.1),
        "Assumed element", group)
    box("Cheil west band", (clearance, inner_width_y, 0.2),
        (AZARAH_WEST_X + clearance / 2, COURT_CENTER_Y, 0.1),
        "Assumed element", group)
    for x in frange(east, west, spacing):
        box("Soreg post", (post, post, height), (x, south, height / 2),
            "Assumed element", group)
        box("Soreg post", (post, post, height), (x, north, height / 2),
            "Assumed element", group)
    for y in frange(south, north, spacing):
        box("Soreg post", (post, post, height), (east, y, height / 2),
            "Assumed element", group)
        box("Soreg post", (post, post, height), (west, y, height / 2),
            "Assumed element", group)
    # Two continuous rails turn the posts into the low lattice described by
    # the term soreg; gate interruptions are schematic in this overview model.
    for rail_z in (height * 0.42, height * 0.82):
        box("קורת הסורג הדרומית", (west - east, 0.16, 0.16),
            ((east + west) / 2, south, rail_z), "Assumed element", group)
        box("קורת הסורג הצפונית", (west - east, 0.16, 0.16),
            ((east + west) / 2, north, rail_z), "Assumed element", group)
        box("קורת הסורג המזרחית", (0.16, north - south, 0.16),
            (east, (south + north) / 2, rail_z), "Assumed element", group)
        box("קורת הסורג המערבית", (0.16, north - south, 0.16),
            (west, (south + north) / 2, rail_z), "Assumed element", group)


def frange(start: float, stop: float, step: float):
    value = start
    while value <= stop + 1e-6:
        yield value
        value += step


def build_womens_court() -> None:
    level = SOURCE["women_court_level"]
    width = SOURCE["women_court"][0]
    center_x = (WOMEN_EAST_X + AZARAH_EAST_X) / 2
    box("Women's Court platform", (width, width, level),
        (center_x, COURT_CENTER_Y, level / 2),
        "Pale court stone", "04 Women's Court")

    wall_t = ASSUMED["court_wall_thickness"]
    wall_h = ASSUMED["court_wall_height"]
    gate_w = SOURCE["standard_gate"][0]
    gated_wall_x("Women's Court south wall", center_x, COURT_SOUTH_Y,
                 width, wall_t, wall_h, 0, [], "04 Women's Court")
    gated_wall_x("Women's Court north wall", center_x, COURT_NORTH_Y,
                 width, wall_t, wall_h, 0, [], "04 Women's Court")
    gated_wall_y("Women's Court east wall", WOMEN_EAST_X, COURT_CENTER_Y,
                 width, wall_t, wall_h, 0, [(COURT_CENTER_Y, gate_w)],
                 "04 Women's Court")

    # Twelve steps from the cheil into the Women's Court: half a cubit rise
    # and half a cubit tread per Middot 2:3. They approach from the east.
    for index in range(SOURCE["cheil_steps"]):
        remaining = SOURCE["cheil_steps"] - index
        depth = remaining * 0.5
        box(f"Cheil step {index + 1:02d}", (depth, gate_w, 0.5),
            (WOMEN_EAST_X - depth / 2, COURT_CENTER_Y,
             index * 0.5 + 0.25),
            "Pale court stone", "04 Women's Court")

    # This is the eastern entrance into the Women's Court, not Nicanor's
    # Gate. Its architectural treatment is schematic because Middot does not
    # give it the name or detailed construction supplied for Nicanor.
    for side in (-1, 1):
        box("הפתח המזרחי לעזרת הנשים – אומנה סכמטית", (4.5, 1.6, 14.0),
            (WOMEN_EAST_X, COURT_CENTER_Y + side * 6.0, level + 7.0),
            "Assumed element", "04 Women's Court", 0.12)
        box("הפתח המזרחי לעזרת הנשים – כנף פתוחה", (3.8, 0.32, 12.0),
            (WOMEN_EAST_X - 1.8, COURT_CENTER_Y + side * 4.7,
             level + 6.0), "Wood", "04 Women's Court", 0.06)
    box("הפתח המזרחי לעזרת הנשים – משקוף סכמטי", (4.5, 14.0, 2.0),
        (WOMEN_EAST_X, COURT_CENTER_Y, level + 15.0),
        "Assumed element", "04 Women's Court", 0.12)
    label("הפתח המזרחי לעזרת הנשים", WOMEN_EAST_X, COURT_CENTER_Y,
          level + 16.2, 1.35)

    inset = width / 2 - SOURCE["corner_chamber"][0] / 2
    rooms = [
        ("לשכת הנזירים – דרום מזרח", center_x - inset,
         COURT_CENTER_Y - inset, 1, add_nazirite_chamber_details),
        ("לשכת דיר העצים – צפון מזרח", center_x - inset,
         COURT_CENTER_Y + inset, 1, add_wood_chamber_details),
        ("לשכת המצורעים – צפון מערב", center_x + inset,
         COURT_CENTER_Y + inset, -1, add_lepers_chamber_details),
        ("לשכת בית שמניה – דרום מערב", center_x + inset,
         COURT_CENTER_Y - inset, -1, add_oil_chamber_details),
    ]
    for name, x, y, doorway_side, detail_builder in rooms:
        add_womens_chamber_shell(name, x, y, level, doorway_side)
        detail_builder(x, y, level + 0.34)

    # The Second Temple balcony (gezuztra) around the Women's Court is shown
    # as a narrow timber gallery with a simple balustrade.
    balcony_z = level + 15.0
    for side, side_y in (("דרום", COURT_CENTER_Y - width / 2 + 4.0),
                         ("צפון", COURT_CENTER_Y + width / 2 - 4.0)):
        box(f"גזוזטרה בעזרת הנשים – {side}", (width - 8, 4, 0.45),
            (center_x, side_y, balcony_z), "Cedar", "04 Women's Court", 0.06)
        box(f"מעקה הגזוזטרה – {side}", (width - 8, 0.25, 3.0),
            (center_x,
             side_y + (1.8 if side == "דרום" else -1.8),
             balcony_z + 1.5), "Cedar", "04 Women's Court")
    # The eastern gallery is continuous. On the west, two shorter runs leave
    # the stair and Nicanor axis open instead of forming a slab above them.
    box("גזוזטרה בעזרת הנשים – מזרח", (4, width - 8, 0.45),
        (WOMEN_EAST_X + 4.0, COURT_CENTER_Y, balcony_z),
        "Cedar", "04 Women's Court", 0.06)
    box("מעקה הגזוזטרה – מזרח", (0.25, width - 8, 3.0),
        (WOMEN_EAST_X + 5.8, COURT_CENTER_Y, balcony_z + 1.5),
        "Cedar", "04 Women's Court")

    stair_radius = (
        gate_w / 2
        + SOURCE["women_steps"] * ASSUMED["women_step_tread"]
    )
    west_gallery_x = AZARAH_EAST_X - 4.0
    stair_opening_half_width = (
        stair_radius + ASSUMED["womens_balcony_stair_clearance"]
    )
    gallery_inner_half_length = width / 2 - 4.0
    west_run_length = gallery_inner_half_length - stair_opening_half_width
    for side, direction in (("דרום", -1), ("צפון", 1)):
        run_center_y = COURT_CENTER_Y + direction * (
            stair_opening_half_width + west_run_length / 2
        )
        box(f"גזוזטרה בעזרת הנשים – מערב {side}",
            (4, west_run_length, 0.45),
            (west_gallery_x, run_center_y, balcony_z),
            "Cedar", "04 Women's Court", 0.06)
        box(f"מעקה הגזוזטרה – מערב {side}",
            (0.25, west_run_length, 3.0),
            (west_gallery_x - 1.8, run_center_y, balcony_z + 1.5),
            "Cedar", "04 Women's Court")
    for support_index, support_y in enumerate(frange(COURT_SOUTH_Y + 8,
                                                      COURT_NORTH_Y - 8, 16), 1):
        support_xs = [WOMEN_EAST_X + 4.0]
        if abs(support_y - COURT_CENTER_Y) >= stair_opening_half_width:
            support_xs.append(west_gallery_x)
        for support_x in support_xs:
            cylinder(f"עמוד גזוזטרה {support_index}", 0.22, 15.0,
                     (support_x, support_y, level + 7.5),
                     "Cedar", "04 Women's Court", 16)

    # Fifteen curved steps: successive stacked half-discs make visible treads.
    for index in range(SOURCE["women_steps"]):
        radius = (
            gate_w / 2
            + (SOURCE["women_steps"] - index)
            * ASSUMED["women_step_tread"]
        )
        semi_disc(
            f"Curved step {index + 1:02d}", AZARAH_EAST_X,
            COURT_CENTER_Y, radius, level + index * 0.5, 0.5,
            "05 Fifteen Curved Steps",
        )
    label("עזרת הנשים 135×135 אמה", center_x, COURT_CENTER_Y,
          level + 0.3, 3.0)


def build_azarah() -> None:
    israel = SOURCE["israel_court_level"]
    priests = ASSUMED["priests_court_level"]
    width_x, width_y = SOURCE["azarah"]
    center_x = (AZARAH_EAST_X + AZARAH_WEST_X) / 2

    # The whole platform is raised to the Israel court; the western portion is
    # raised again according to R. Eliezer b. Jacob's level sequence.
    box("Azarah base", (width_x, width_y, israel),
        (center_x, COURT_CENTER_Y, israel / 2),
        "Pale court stone", "06 Azarah")
    priests_start = AZARAH_EAST_X + SOURCE["israel_court_depth"]
    box("Priests court raised platform",
        (AZARAH_WEST_X - priests_start, width_y, priests - israel),
        ((priests_start + AZARAH_WEST_X) / 2, COURT_CENTER_Y,
         israel + (priests - israel) / 2),
        "Pale court stone", "06 Azarah")

    wall_t = ASSUMED["court_wall_thickness"]
    wall_h = ASSUMED["court_wall_height"]
    gate_w = SOURCE["standard_gate"][0]
    gated_wall_y("Azarah east wall", AZARAH_EAST_X, COURT_CENTER_Y,
                 width_y, wall_t, wall_h, israel,
                 [(COURT_CENTER_Y, gate_w)], "06 Azarah")
    gated_wall_y("Azarah west wall", AZARAH_WEST_X, COURT_CENTER_Y,
                 width_y, wall_t, wall_h, priests,
                 [], "06 Azarah")
    side_openings = [(x, gate_w) for x in (55, 105, 165)]
    gazit_opening = (ASSUMED["gazit_chamber_center_x"], 5.0)
    # The flat-mount reconstruction needs a retaining section below the side
    # walls. Both it and the upper wall are interrupted at the gates so that
    # the passages remain visible instead of becoming shallow notches.
    for wall_name, wall_y, extra_openings in (
        ("Azarah south wall", COURT_SOUTH_Y, []),
        ("Azarah north wall", COURT_NORTH_Y, [gazit_opening]),
    ):
        openings = side_openings + extra_openings
        gated_wall_x(f"{wall_name} – מסד", center_x, wall_y,
                     width_x, wall_t, israel, 0,
                     openings, "06 Azarah")
        gated_wall_x(wall_name, center_x, wall_y,
                     width_x, wall_t, wall_h, israel,
                     openings, "06 Azarah")

    # Three half-cubit steps above the one-cubit rise in Middot 2:6.
    for index in range(3):
        box(f"Priests court step {index + 1}", (0.5, 40, 0.5),
            (priests_start - 1.25 + index * 0.5, COURT_CENTER_Y,
             israel + 1.0 + index * 0.5 - 0.25),
            "Pale court stone", "06 Azarah")

    label("עזרת ישראל – 11 אמה", AZARAH_EAST_X + 5.5, COURT_CENTER_Y,
          israel + 0.2, 1.5)
    label("עזרת הכוהנים – 11 אמה", AZARAH_EAST_X + 16.5, COURT_CENTER_Y,
          priests + 0.2, 1.5)


def build_azarah_gates_and_chambers() -> None:
    """Seven-gate tradition (Middot 1:4-5) and six court chambers (5:3-4)."""
    threshold = SOURCE["israel_court_level"]
    gate_xs = (55.0, 105.0, 165.0)

    # South, east-to-west. The Mishna names these three gates but does not
    # state their spacing; the coordinates retain the earlier schematic plan.
    south_gates = (
        (gate_xs[0], "שער המים"),
        (gate_xs[1], "שער הבכורות"),
        (gate_xs[2], "שער הדלק"),
    )
    for gate_x, gate_name in south_gates:
        add_azarah_gatehouse_x(gate_name, gate_x, COURT_SOUTH_Y,
                               threshold, "Wood")

    # North, east-to-west. The Gate of the Spark carried an upper chamber;
    # the House of the Hearth is expanded below as a roofed guard building.
    north_gates = (
        (gate_xs[0], "שער בית המוקד", False),
        (gate_xs[1], "שער הקרבן", False),
        (gate_xs[2], "שער הניצוץ", True),
    )
    for gate_x, gate_name, upper in north_gates:
        add_azarah_gatehouse_x(gate_name, gate_x, COURT_NORTH_Y,
                               threshold, "Wood", upper)

    # Nicanor's eastern doors famously remained bronze. Their chambers stood
    # one on either side: Pinchas the vestment keeper and the griddle-cake
    # makers. Their exact dimensions here are deliberately schematic.
    nicanor_name = "שער העזרה המזרחי – שער ניקנור"
    add_azarah_gatehouse_y(nicanor_name, AZARAH_EAST_X, COURT_CENTER_Y,
                           threshold, "Bronze")
    nicanor_room_x = AZARAH_EAST_X + 8.5
    for side, room_name in ((-1, "לשכת עושי חביתין"),
                            (1, "לשכת פנחס המלביש")):
        room_y = COURT_CENTER_Y + side * 13.0
        box(f"{room_name} – רצפה", (14, 10, 0.5),
            (nicanor_room_x, room_y, threshold + 0.25),
            "Pale court stone", "06 Azarah Gates", 0.06)
        open_room(room_name, nicanor_room_x, room_y, 14, 10, threshold,
                  wall_height=9.0, wall_thickness=0.8,
                  group="06 Azarah Gates")
        # A recessed doorway on the side facing Nicanor's passage makes the
        # relationship between the gate and its two flanking chambers clear.
        doorway_y = room_y - side * 5.05
        box(f"{room_name} – פתח אל שער ניקנור", (4.0, 0.16, 6.5),
            (nicanor_room_x, doorway_y, threshold + 3.25),
            "Dark opening", "06 Azarah Gates", 0.08)
        box(f"{room_name} – דלת פתוחה", (3.7, 0.28, 6.2),
            (nicanor_room_x + 2.1, doorway_y - side * 1.8,
             threshold + 3.1), "Wood", "06 Azarah Gates", 0.06)
        box(f"{room_name} – גג אחורי", (14.5, 5.0, 0.6),
            (nicanor_room_x + 0.2, room_y + side * 2.5,
             threshold + 9.3),
            "Pale court stone", "06 Azarah Gates", 0.08)
        label(room_name, nicanor_room_x, room_y, threshold + 10.2, 1.1)

    # Contents make the two Nicanor chambers legible at close range.
    for rack_y in (COURT_CENTER_Y + 10.5, COURT_CENTER_Y + 15.5):
        beam_between("מתלה בגדי כהונה",
                     (nicanor_room_x + 2.0, rack_y, threshold + 1.0),
                     (nicanor_room_x + 2.0, rack_y, threshold + 7.0),
                     0.11, "Cedar", "06 Azarah Gates", 12)
        for hook_z in (2.4, 4.2, 6.0):
            box("בגד כהונה מקופל", (0.6, 1.5, 0.25),
                (nicanor_room_x + 1.7, rack_y, threshold + hook_z),
                "Curtain", "06 Azarah Gates", 0.05)
    box("שולחן הכנת חביתין", (4.5, 2.2, 0.35),
        (nicanor_room_x + 1.0, COURT_CENTER_Y - 13.0, threshold + 2.4),
        "Cedar", "06 Azarah Gates", 0.08)
    for leg_x in (-0.5, 2.5):
        for leg_y in (-0.75, 0.75):
            cylinder("רגל שולחן החביתין", 0.10, 2.2,
                     (nicanor_room_x + leg_x,
                      COURT_CENTER_Y - 13.0 + leg_y, threshold + 1.1),
                     "Cedar", "06 Azarah Gates", 10)
    cylinder("מחבת החביתין", 1.15, 0.22,
             (nicanor_room_x + 1.0, COURT_CENTER_Y - 13.0,
              threshold + 2.72), "Bronze", "06 Azarah Gates", 32)

    # The gate's eastern threshold served as the standing place for several
    # purification rites. Keep the interpretive marker on the upper platform;
    # placing it east of the threshold would leave it floating over the steps.
    box("מעמד הטהרה בפתח שער ניקנור", (4.0, 8.0, 0.22),
        (AZARAH_EAST_X + 2.0, COURT_CENTER_Y, threshold + 0.12),
        "Assumed element", "06 Azarah Gates", 0.05)

    # The House of the Hearth was a large domed building with four inner
    # chambers. The open colonnade below preserves sight through its gate.
    hearth_x = gate_xs[0]
    hearth_y = COURT_NORTH_Y + 9.0
    for dx in (-8.0, 8.0):
        for dy in (-5.0, 5.0):
            cylinder("בית המוקד – עמוד", 0.55, 12.0,
                     (hearth_x + dx, hearth_y + dy, threshold + 6.0),
                     "Jerusalem limestone", "06 Azarah Gates", 20)
    sphere("בית המוקד – כיפה", 11.5,
           (hearth_x, hearth_y, threshold + 12.2),
           "Assumed element", "06 Azarah Gates",
           scale=(1.0, 0.78, 0.34), subdivisions=3)
    for dx in (-6.2, 6.2):
        for dy in (-3.8, 3.8):
            box("בית המוקד – אחת מארבע הלשכות", (6.0, 4.5, 5.0),
                (hearth_x + dx, hearth_y + dy, threshold + 2.5),
                "Assumed element", "06 Azarah Gates", 0.12)
    cylinder("בית המוקד – מדורת הכוהנים", 2.1, 0.45,
             (hearth_x, hearth_y, threshold + 0.25),
             "Bronze", "06 Azarah Gates", 32)
    for ember_index in range(7):
        angle = 2 * math.pi * ember_index / 7
        sphere("בית המוקד – גחלת", 0.34,
               (hearth_x + 1.25 * math.cos(angle),
                hearth_y + 1.25 * math.sin(angle), threshold + 0.65),
               "Ember", "06 Azarah Gates", subdivisions=1)
    label("בית המוקד – כיפה וארבע לשכות", hearth_x, hearth_y,
          threshold + 16.5, 1.25)

    # Gate-specific cues: water channel, animal tethers, fuel racks and the
    # sacrificial-animal approach. They are didactic, not measured remains.
    beam_between("שער המים – אמת מים",
                 (gate_xs[0] - 5.0, COURT_SOUTH_Y + 3.0, threshold + 0.8),
                 (gate_xs[0] + 5.0, COURT_SOUTH_Y + 3.0, threshold + 0.8),
                 0.22, "Bronze", "06 Azarah Gates", 16)
    for tether_x, side_y in (
        (gate_xs[1] - 3.0, COURT_SOUTH_Y + 3.0),
        (gate_xs[1] + 3.0, COURT_SOUTH_Y + 3.0),
        (gate_xs[1] - 3.0, COURT_NORTH_Y - 3.0),
        (gate_xs[1] + 3.0, COURT_NORTH_Y - 3.0),
    ):
        cylinder("עמוד קשירת קרבן", 0.22, 3.2,
                 (tether_x, side_y, threshold + 1.6),
                 "Bronze", "06 Azarah Gates", 14)
        torus("טבעת קשירה", 0.34, 0.07,
              (tether_x, side_y, threshold + 2.4),
              "Bronze", "06 Azarah Gates")
    for rack_x in (gate_xs[2] - 3.0, gate_xs[2], gate_xs[2] + 3.0):
        beam_between("שער הדלק – עצי מערכה",
                     (rack_x - 1.8, COURT_SOUTH_Y + 2.8, threshold + 0.5),
                     (rack_x + 1.8, COURT_SOUTH_Y + 2.8, threshold + 4.6),
                     0.28, "Cedar", "06 Azarah Gates", 12)

    # Six chambers along the court walls. Their width and exact east-west
    # positions are unspecified in Middot and therefore remain schematic.
    chamber_specs = (
        (-1, 79.0, 18.0, "לשכת המלח"),
        (-1, 134.0, 18.0, "לשכת הפרווה"),
        (-1, 190.0, 18.0, "לשכת המדיחין"),
        (1, 79.0, 18.0, "לשכת העץ"),
        (1, 134.0, 18.0, "לשכת הגולה"),
    )
    chamber_centers: dict[str, tuple[float, float]] = {}
    for side, chamber_x, chamber_w, chamber_name in chamber_specs:
        center_y, _ = add_chamber_shell(
            chamber_name, chamber_x, side, chamber_w, threshold
        )
        chamber_centers[chamber_name] = (chamber_x, center_y)
    add_gazit_chamber(threshold)

    group = "06 Azarah Chambers"
    salt_x, salt_y = chamber_centers["לשכת המלח"]
    for dx in (-4.5, -1.5, 1.5, 4.5):
        box("לשכת המלח – תא אחסון", (2.3, 3.0, 2.2),
            (salt_x + dx, salt_y, threshold + 1.1),
            "White altar stone", group, 0.10)
        cone("לשכת המלח – ערמת מלח", 0.9, 1.2,
             (salt_x + dx, salt_y, threshold + 2.8),
             "White altar stone", group, 18)

    parvah_x, parvah_y = chamber_centers["לשכת הפרווה"]
    for dx in (-3.5, 3.5):
        box("לשכת הפרווה – שולחן מליחה", (5.0, 1.7, 0.35),
            (parvah_x + dx, parvah_y, threshold + 2.3),
            "Pale court stone", group, 0.06)
        for leg in (-1.7, 1.7):
            cylinder("לשכת הפרווה – רגל שולחן", 0.10, 2.1,
                     (parvah_x + dx + leg, parvah_y,
                      threshold + 1.05), "Pale court stone", group, 10)
    bath_z = threshold + ASSUMED["azarah_chamber_height"] + 0.8
    box("בית הטבילה על גג לשכת הפרווה – אגן", (7.5, 5.5, 1.2),
        (parvah_x, parvah_y - 2.5, bath_z),
        "Pale court stone", group, 0.12)
    box("בית הטבילה על גג לשכת הפרווה – מים", (6.2, 4.2, 0.18),
        (parvah_x, parvah_y - 2.5, bath_z + 0.68),
        "Water", group, 0.04)

    rinse_x, rinse_y = chamber_centers["לשכת המדיחין"]
    box("לשכת המדיחין – אגן רחיצה", (8.0, 3.0, 1.5),
        (rinse_x, rinse_y, threshold + 0.75),
        "Pale court stone", group, 0.10)
    box("לשכת המדיחין – מים", (7.0, 2.2, 0.18),
        (rinse_x, rinse_y, threshold + 1.56), "Water", group, 0.04)
    for stair in range(7):
        box("המסיבה מלשכת המדיחין לגג הפרווה",
            (2.2, 1.1 + stair * 0.72, 0.5),
            (rinse_x - 6.0, rinse_y - 3.5 + stair * 0.36,
             threshold + stair * 1.7 + 0.25),
            "Assumed element", group, 0.05)

    wood_x, wood_y = chamber_centers["לשכת העץ"]
    for rack in (-4.5, 0.0, 4.5):
        for shelf_z in (1.5, 4.0, 6.5):
            box("לשכת העץ – מדף ארז", (3.5, 1.0, 0.28),
                (wood_x + rack, wood_y, threshold + shelf_z),
                "Cedar", group, 0.04)

    golah_x, golah_y = chamber_centers["לשכת הגולה"]
    cylinder("לשכת הגולה – בור הגולה", 2.5, 1.1,
             (golah_x, golah_y, threshold + 0.55),
             "Jerusalem limestone", group, 32)
    torus("לשכת הגולה – שפת הבור", 2.5, 0.24,
          (golah_x, golah_y, threshold + 1.15),
          "Bronze", group)
    beam_between("לשכת הגולה – קורת הגלגל",
                 (golah_x - 3.5, golah_y, threshold + 5.5),
                 (golah_x + 3.5, golah_y, threshold + 5.5),
                 0.22, "Cedar", group, 14)
    for post_x in (-3.5, 3.5):
        beam_between("לשכת הגולה – עמוד הגלגל",
                     (golah_x + post_x, golah_y, threshold + 0.8),
                     (golah_x + post_x, golah_y, threshold + 5.5),
                     0.22, "Cedar", group, 14)
    torus("לשכת הגולה – גלגל", 1.25, 0.16,
          (golah_x, golah_y - 0.2, threshold + 4.0),
          "Bronze", group, rotation=(math.pi / 2, 0, 0))

def build_altar_and_service_area() -> None:
    z = ASSUMED["priests_court_level"]
    altar_east = (
        AZARAH_EAST_X
        + SOURCE["israel_court_depth"]
        + SOURCE["priests_court_depth"]
    )
    altar_center_x = altar_east + SOURCE["altar"][0] / 2
    altar_center_y = COURT_CENTER_Y + ASSUMED["altar_north_offset"]
    group = "07 Altar and Service Area"

    # Middot 3:1: the one-cubit foundation runs along the north and west,
    # with only one-cubit returns on the east and south. It is therefore an
    # L-shape rather than the full 32 x 32 block shown by the earlier model.
    box("יסוד המזבח – צפון 32×1", (32, 1, 1),
        (altar_center_x, altar_center_y + 15.5, z + 0.5),
        "Altar shadow stone", group, 0.10)
    box("יסוד המזבח – מערב 1×31", (1, 31, 1),
        (altar_center_x + 15.5, altar_center_y - 0.5, z + 0.5),
        "Altar shadow stone", group, 0.10)
    box("גוף המזבח עד הסובב 30×30", (30, 30, 6),
        (altar_center_x, altar_center_y, z + 3.0),
        "Altar limestone", group, 0.12)
    box("ראש המזבח מעל הסובב 28×28", (28, 28, 3),
        (altar_center_x, altar_center_y, z + 7.5),
        "Altar upper stone", group, 0.12)
    # A thin contrasting inset makes the one-cubit priestly walkway and the
    # 24 x 24 fire area readable without changing the sourced dimensions.
    box("מקום הילוך רגלי הכוהנים", (26, 26, 0.08),
        (altar_center_x, altar_center_y, z + 9.04),
        "Pale court stone", group)
    box("מקום המערכה 24×24", (24, 24, 0.10),
        (altar_center_x, altar_center_y, z + 9.10), "Ash", group)
    # The scarlet line circles the altar at half its nine-cubit body height.
    box("חוט הסיקרא – מזרח–מערב", (30.15, 0.12, 0.15),
        (altar_center_x, altar_center_y - 15.06, z + 4.5), "Sikra red", group)
    box("חוט הסיקרא – מערב–מזרח", (30.15, 0.12, 0.15),
        (altar_center_x, altar_center_y + 15.06, z + 4.5), "Sikra red", group)
    box("חוט הסיקרא – דרום–צפון", (0.12, 30.15, 0.15),
        (altar_center_x - 15.06, altar_center_y, z + 4.5), "Sikra red", group)
    box("חוט הסיקרא – צפון–דרום", (0.12, 30.15, 0.15),
        (altar_center_x + 15.06, altar_center_y, z + 4.5), "Sikra red", group)
    for dx in (-12.5, 12.5):
        for dy in (-12.5, 12.5):
            box("Altar horn", (1, 1, ASSUMED["altar_horn_height"]),
                (altar_center_x + dx, altar_center_y + dy,
                 z + ASSUMED["altar_height"] + 0.5),
                "Altar upper stone", group, 0.10)

    # 32 cubits is the sloped length. With a nine-cubit rise its ground run is
    # about 30.7 cubits, conventionally rounded to 30 in schematic plans.
    ramp_run = math.sqrt(SOURCE["altar_ramp"][1] ** 2 - ASSUMED["altar_height"] ** 2)
    ramp_wedge("כבש המזבח 32×16", altar_center_x,
               altar_center_y - 16 - ramp_run, altar_center_y - 16,
               16, z, ASSUMED["altar_height"], group, "Altar limestone")
    # Two narrow subsidiary ramps give access to the foundation and the
    # surrounding ledge. Their exact attachment geometry is interpretive.
    ramp_wedge("כבש קטן ליסוד", altar_center_x + 9.2,
               altar_center_y - 21, altar_center_y - 16,
               2.0, z, 1.0, group, "Altar shadow stone")
    ramp_wedge("כבש קטן לסובב", altar_center_x - 9.2,
               altar_center_y - 36, altar_center_y - 16,
               2.0, z, 6.0, group, "Altar upper stone")

    # Three daily wood arrangements and the central ash heap (the "apple").
    arrangements = (
        (altar_center_x - 6.5, altar_center_y + 4.5, 5.2),
        (altar_center_x + 5.0, altar_center_y + 4.0, 4.2),
        (altar_center_x - 1.0, altar_center_y - 5.5, 3.6),
    )
    for arrangement_index, (fire_x, fire_y, length) in enumerate(arrangements, 1):
        for log_index in range(5):
            offset = (log_index - 2) * 0.48
            beam_between(
                f"מערכה {arrangement_index} – גזיר עץ {log_index + 1}",
                (fire_x - length / 2, fire_y + offset, z + 9.32 + 0.10 * (log_index % 2)),
                (fire_x + length / 2, fire_y + offset, z + 9.32 + 0.10 * (log_index % 2)),
                0.16, "Cedar", group, 12,
            )
        sphere(f"גחלים במערכה {arrangement_index}", 1.25,
               (fire_x, fire_y, z + 9.48), "Ember", group,
               (1.65, 0.72, 0.22), 2)
    sphere("התפוח – ערמת דשן", 2.0,
           (altar_center_x + 2.0, altar_center_y - 1.0, z + 9.42),
           "Ash", group, (1.25, 1.0, 0.32), 3)

    # Two silver libation bowls beside the south-west horn, with visible
    # wine/water surfaces and the openings leading to the shittin below.
    cup_x = altar_center_x + 11.2
    for cup_index, (cup_y, liquid) in enumerate(
        ((altar_center_y - 11.5, "Wine"), (altar_center_y - 9.8, "Water")), 1
    ):
        cylinder(f"ספל ניסוך {cup_index}", 0.48, 0.42,
                 (cup_x, cup_y, z + 9.31), "Silver", group, 32)
        cylinder(f"תכולת ספל ניסוך {cup_index}", 0.38, 0.025,
                 (cup_x, cup_y, z + 9.535), liquid, group, 32)
        cylinder(f"נקב השיתין {cup_index}", 0.10, 0.05,
                 (cup_x, cup_y, z + 9.56), "Dark opening", group, 20)

    # Twenty-four slaughter rings, six rows of four north of the altar.
    ring_origin_x = altar_center_x - 6
    ring_origin_y = altar_center_y + 24
    for row in range(6):
        for column in range(4):
            torus(f"טבעת שחיטה {row * 4 + column + 1:02d}", 0.55, 0.10,
                  (ring_origin_x + column * 4,
                   ring_origin_y + row * 4, z + 0.12),
                  "Bronze", group)

    # Eight short pillars and four marble tables. Their exact internal spacing
    # is not supplied, so the compact two-row arrangement remains schematic.
    for row in range(2):
        for column in range(4):
            index = row * 4 + column
            box(f"Dwarf pillar {index + 1}", (1, 1, 4),
                (altar_center_x - 12 + column * 8,
                 altar_center_y + 54 + row * 6, z + 2),
                "Assumed element", group)
    for column in range(4):
        box(f"Marble table {column + 1}", (4, 1.5, 1.2),
            (altar_center_x - 12 + column * 8, altar_center_y + 47, z + 0.6),
            "White altar stone", group, 0.10)

    # The service-tool table beside the altar: shovel, rake and bronze fork.
    tool_x, tool_y = altar_center_x + 19.5, altar_center_y + 18.0
    box("שולחן כלי המזבח", (5.0, 2.4, 0.45),
        (tool_x, tool_y, z + 2.6), "White altar stone", group, 0.12)
    for leg_x in (-1.8, 1.8):
        for leg_y in (-0.8, 0.8):
            cylinder("רגל שולחן הכלים", 0.16, 2.4,
                     (tool_x + leg_x, tool_y + leg_y, z + 1.2),
                     "Bronze", group, 16)
    for tool_index, y_offset in enumerate((-0.65, 0.0, 0.65), 1):
        beam_between(f"ידית כלי מזבח {tool_index}",
                     (tool_x - 1.8, tool_y + y_offset, z + 2.92),
                     (tool_x + 1.6, tool_y + y_offset, z + 2.92),
                     0.08, "Bronze", group, 12)
        for tine in (-0.22, 0.0, 0.22):
            beam_between(f"שן קלשון {tool_index}",
                         (tool_x + 1.55, tool_y + y_offset + tine, z + 2.92),
                         (tool_x + 2.05, tool_y + y_offset + tine, z + 2.92),
                         0.045, "Bronze", group, 10)

    # Laver between the altar and hall, shifted south as stated in Middot 3:6.
    laver_x, laver_y = altar_center_x + 28, COURT_CENTER_Y - 18
    cylinder("Laver basin", 2.0, 1.8,
             (laver_x, laver_y, z + 2.7), "Bronze", group)
    cylinder("מי הכיור", 1.72, 0.06,
             (laver_x, laver_y, z + 3.63), "Water", group, 48)
    cylinder("Laver pedestal", 0.8, 2.7,
             (laver_x, laver_y, z + 1.35), "Bronze", group)
    torus("שפת הכיור", 1.95, 0.14, (laver_x, laver_y, z + 3.58),
          "Bronze", group)
    # Ben Katin's twelve taps are shown as small radial bronze spouts.
    for index in range(12):
        angle = 2 * math.pi * index / 12
        inner = (laver_x + 1.65 * math.cos(angle),
                 laver_y + 1.65 * math.sin(angle), z + 2.25)
        outer = (laver_x + 2.25 * math.cos(angle),
                 laver_y + 2.25 * math.sin(angle), z + 2.18)
        beam_between(f"דד הכיור {index + 1:02d}", inner, outer,
                     0.09, "Bronze", group, 12)
        sphere(f"ידית הכיור {index + 1:02d}", 0.13, outer,
               "Bronze", group, subdivisions=2)
    torus("גלגל המוכני", 1.25, 0.16,
          (laver_x + 1.1, laver_y, z + 0.75), "Bronze", group,
          rotation=(math.pi / 2, 0, 0))
    label("המזבח 32×32 אמה", altar_center_x, altar_center_y,
          z + ASSUMED["altar_height"] + 1.2, 2.0)


def build_hall_steps(start_x: float) -> None:
    base_z = ASSUMED["priests_court_level"]
    for index in range(SOURCE["hall_steps"]):
        # The top footprint shrinks as it rises toward the hall in the west.
        remaining = SOURCE["hall_steps"] - index
        depth = remaining * 1.0
        box(f"Hall step {index + 1:02d}", (depth, 60, 0.5),
            (start_x - depth / 2, COURT_CENTER_Y,
             base_z + index * 0.5 + 0.25),
            "Pale court stone", "08 Hall Steps")


def building_wall_with_gate(
    name: str,
    x: float,
    center_y: float,
    width_y: float,
    thickness_x: float,
    height: float,
    base_z: float,
    gate_width: float,
    gate_height: float,
    group: str,
) -> None:
    side = (width_y - gate_width) / 2
    box(f"{name} – דרום", (thickness_x, side, height),
        (x, center_y - (gate_width + side) / 2, base_z + height / 2),
        "Jerusalem limestone", group)
    box(f"{name} – צפון", (thickness_x, side, height),
        (x, center_y + (gate_width + side) / 2, base_z + height / 2),
        "Jerusalem limestone", group)
    lintel_h = height - gate_height
    box(f"{name} – משקוף", (thickness_x, gate_width, lintel_h),
        (x, center_y, base_z + gate_height + lintel_h / 2),
        "Jerusalem limestone", group)
    # A recessed dark plane makes the opening readable in solid previews.
    box(f"{name} – פתח כהה", (0.15, gate_width * 0.96, gate_height * 0.98),
        (x - thickness_x / 2 - 0.08, center_y,
         base_z + gate_height / 2), "Dark opening", group)


def add_hall_facade_details(
    facade_x: float, center_y: float, floor_z: float, height: float, group: str
) -> None:
    """Add sourced facade features while keeping uncertain ornament restrained."""
    east_face_x = facade_x - 0.08
    gate_width, gate_height = SOURCE["hall_gate"]

    # The Hall opening had no doors; a curtain filled its 20 x 40 opening.
    for fold in range(10):
        fold_y = center_y - gate_width / 2 + 1 + fold * 2
        fold_x = east_face_x - (0.12 if fold % 2 else 0.24)
        box(f"פרוכת פתח האולם – קפל {fold + 1:02d}",
            (0.16, 1.92, gate_height - 0.8),
            (fold_x, fold_y, floor_z + gate_height / 2),
            "Curtain", group, 0.03)
    for y in (center_y - gate_width / 2, center_y + gate_width / 2):
        box("מסגרת הזהב של פתח האולם", (0.22, 0.42, gate_height + 1.2),
            (east_face_x - 0.18, y, floor_z + gate_height / 2),
            "Gold", group, 0.05)
    box("מסגרת הזהב העליונה של פתח האולם",
        (0.22, gate_width + 0.8, 0.55),
        (east_face_x - 0.18, center_y, floor_z + gate_height + 0.25),
        "Gold", group, 0.05)
    for tassel in range(12):
        y = center_y - gate_width / 2 + 0.45 + tassel * (gate_width - 0.9) / 11
        sphere("גדיל פרוכת האולם", 0.16,
               (east_face_x - 0.28, y, floor_z + 0.35), "Gold", group,
               scale=(0.7, 0.7, 1.4), subdivisions=2)

    # Shallow stone courses and pilasters break up the otherwise monolithic
    # 100-cubit facade. Their spacing is a visual reconstruction.
    for course_z in range(10, 100, 10):
        if course_z < gate_height:
            side_width = (100 - gate_width) / 2
            for side in (-1, 1):
                box("נדבך מודגש בחזית האולם",
                    (0.22, side_width - 1.0, 0.28),
                    (east_face_x - 0.02,
                     center_y + side * (gate_width / 2 + side_width / 2),
                     floor_z + course_z), "Pale court stone", group, 0.03)
        else:
            box("נדבך מודגש בחזית האולם", (0.22, 98, 0.28),
                (east_face_x - 0.02, center_y, floor_z + course_z),
                "Pale court stone", group, 0.03)
    for pilaster_y in (-36, -14, 14, 36):
        box("אומנת חזית האולם", (0.7, 2.4, 44),
            (east_face_x - 0.18, center_y + pilaster_y, floor_z + 22),
            "Pale court stone", group, 0.16)
        box("כותרת אומנת האולם", (1.1, 3.4, 1.2),
            (east_face_x - 0.24, center_y + pilaster_y, floor_z + 44),
            "Gold", group, 0.12)


def add_hall_interior_details(
    facade_x: float, body_start: float, center_y: float, floor_z: float,
    group: str,
) -> None:
    # Cedar braces joined the high Hall wall to the Heikhal wall.
    for beam_y in (-28, -18, -8, 8, 18, 28):
        beam_between("קורת ארז מן האולם להיכל",
                     (facade_x + 5.2, center_y + beam_y, floor_z + 43),
                     (body_start - 0.4, center_y + beam_y, floor_z + 43),
                     0.32, "Cedar", group, 16)

    # Golden chains and crown-like ornaments descended from the ceiling.
    for chain_y in (-18, -6, 6, 18):
        beam_between("שרשרת זהב באולם",
                     (facade_x + 8.5, center_y + chain_y, floor_z + 88),
                     (facade_x + 8.5, center_y + chain_y, floor_z + 49),
                     0.10, "Gold", group, 12)
        torus("עטרת זהב באולם", 1.15, 0.16,
              (facade_x + 8.5, center_y + chain_y, floor_z + 47.8),
              "Gold", group, rotation=(0, math.pi / 2, 0))

    # Marble and gold tables used when the showbread entered and left.
    for table_y, table_mat, table_name in (
        (center_y - 8, "White altar stone", "שולחן השיש באולם"),
        (center_y + 8, "Gold", "שולחן הזהב באולם"),
    ):
        box(table_name, (3.2, 1.7, 0.28),
            (body_start - 4.0, table_y, floor_z + 2.25),
            table_mat, group, 0.08)
        for dx in (-1.15, 1.15):
            for dy in (-0.55, 0.55):
                cylinder(f"רגל {table_name}", 0.10, 2.1,
                         (body_start - 4.0 + dx, table_y + dy, floor_z + 1.05),
                         table_mat, group, 12)

    # The north auxiliary gate and the permanently closed southern gate.
    for gate_y, gate_name, gate_mat in (
        (center_y + 32.4, "השער הצפוני של האולם", "Dark opening"),
        (center_y - 32.4, "השער הדרומי הסגור של האולם", "Gold"),
    ):
        box(gate_name, (5.0, 0.18, 12.0),
            (facade_x + 10.0, gate_y, floor_z + 6.0), gate_mat, group, 0.06)

    # The golden vine stood over the Heikhal doorway. The exact branching and
    # quantity of donated leaves and clusters are necessarily illustrative.
    vine_x = body_start - 0.22
    beam_between("גזע גפן הזהב",
                 (vine_x, center_y - 6.0, floor_z + 4.0),
                 (vine_x, center_y + 6.0, floor_z + 24.0),
                 0.18, "Gold", group, 16)
    for side in (-1, 1):
        for level in range(4):
            branch_y = center_y + side * (2.2 + level * 2.1)
            branch_z = floor_z + 9.0 + level * 4.1
            beam_between("זמורת גפן הזהב",
                         (vine_x, center_y + side * level * 1.5, branch_z - 1.4),
                         (vine_x, branch_y, branch_z), 0.105, "Gold", group, 12)
            for berry in range(5):
                sphere("גרגר בגפן הזהב", 0.20,
                       (vine_x - 0.12, branch_y + side * 0.22 * (berry % 2),
                        branch_z - 0.34 * berry), "Gold", group,
                       scale=(0.8, 0.8, 1.15), subdivisions=2)
            sphere("עלה בגפן הזהב", 0.48,
                   (vine_x - 0.10, branch_y - side * 0.6, branch_z + 0.25),
                   "Gold", group, scale=(0.24, 1.0, 0.62), subdivisions=2)

    # Helena's chandelier hangs above the Heikhal doorway.
    chandelier_z = floor_z + 27.0
    torus("נברשת הילני המלכה", 2.2, 0.16,
          (vine_x - 0.18, center_y, chandelier_z), "Gold", group,
          rotation=(0, math.pi / 2, 0))
    for spoke in range(8):
        angle = 2 * math.pi * spoke / 8
        beam_between("קרן נברשת הילני",
                     (vine_x - 0.18, center_y, chandelier_z),
                     (vine_x - 0.18,
                      center_y + 2.2 * math.cos(angle),
                      chandelier_z + 2.2 * math.sin(angle)),
                     0.065, "Gold", group, 10)


def add_sanctuary_chambers(
    body_start: float, body_depth: float, back_x: float,
    center_y: float, floor_z: float,
) -> None:
    """Model the 38 chambers: 15 north, 15 south, and 8 west."""
    group = "10 Chambers (schematic)"
    usable_depth = body_depth - 8.0
    room_x = usable_depth / 5.0
    for tier, projection in enumerate((5.0, 6.0, 7.0)):
        room_z = floor_z + 2.0 + tier * 15.0
        for side, side_name in ((-1, "דרום"), (1, "צפון")):
            outer_y = center_y + side * (35.0 + projection / 2)
            for room in range(5):
                x = body_start + 4.0 + room_x * (room + 0.5)
                box(f"תא {side_name} קומה {tier + 1} חדר {room + 1}",
                    (room_x - 0.42, projection, 13.2),
                    (x, outer_y, room_z + 6.6),
                    "Assumed element", group, 0.10)
                # A recessed outer opening makes each cell individually legible.
                box(f"חלון תא {side_name} {tier + 1}-{room + 1}",
                    (2.2, 0.12, 2.8),
                    (x, center_y + side * (35.0 + projection + 0.07),
                     room_z + 7.0), "Dark opening", group, 0.04)

    for tier, room_count in enumerate((3, 3, 2)):
        room_span = 58.0 / room_count
        projection = 5.0 + tier
        room_z = floor_z + 2.0 + tier * 15.0
        for room in range(room_count):
            y = center_y - 29.0 + room_span * (room + 0.5)
            box(f"תא מערב קומה {tier + 1} חדר {room + 1}",
                (projection, room_span - 0.5, 13.2),
                (back_x + projection / 2, y, room_z + 6.6),
                "Assumed element", group, 0.10)
            box(f"חלון תא מערב {tier + 1}-{room + 1}",
                (0.12, 2.2, 2.8),
                (back_x + projection + 0.07, y, room_z + 7.0),
                "Dark opening", group, 0.04)

    # A compact tower marks the winding stair (mesibah) serving the tiers.
    stair_x, stair_y = body_start + 10.0, center_y + 43.0
    cylinder("המסיבה – מגדל מדרגות לולייני", 4.0, 46.0,
             (stair_x, stair_y, floor_z + 23.0),
             "Assumed element", group, 40)
    for level in (2.0, 17.0, 32.0, 45.0):
        torus("חגורת אבן במסיבה", 4.02, 0.16,
              (stair_x, stair_y, floor_z + level),
              "Pale court stone", group)
    box("פתח המסיבה", (2.2, 0.16, 4.0),
        (stair_x, stair_y - 4.08, floor_z + 2.0),
        "Dark opening", group, 0.08)


def add_roof_parapet_and_spikes(
    facade_x: float, back_x: float, center_y: float, floor_z: float,
    height: float, group: str,
) -> None:
    roof_z = floor_z + height
    # Middot 4:6: a three-cubit parapet and a further cubit of raven spikes.
    box("מעקה הגג – מזרח", (1.0, 100, 3),
        (facade_x + 0.5, center_y, roof_z + 1.5),
        "Jerusalem limestone", group, 0.08)
    box("מעקה הגג – מערב", (1.0, 70, 3),
        (back_x - 0.5, center_y, roof_z + 1.5),
        "Jerusalem limestone", group, 0.08)
    for side in (-1, 1):
        box("מעקה הגג – צפון/דרום", (back_x - facade_x, 1.0, 3),
            ((facade_x + back_x) / 2, center_y + side * 34.5,
             roof_z + 1.5), "Jerusalem limestone", group, 0.08)
    for x in frange(facade_x + 2.0, back_x - 2.0, 4.0):
        for y in (center_y - 33.5, center_y + 33.5):
            cone("כליא עורב", 0.16, 1.0, (x, y, roof_z + 3.5),
                 "Gold", group, 8)
    for y in frange(center_y - 48.0, center_y + 48.0, 4.0):
        cone("כליא עורב", 0.16, 1.0,
             (facade_x + 1.2, y, roof_z + 3.5), "Gold", group, 8)


def build_sanctuary() -> None:
    group = "09 Sanctuary"
    facade_x = (
        AZARAH_EAST_X
        + SOURCE["israel_court_depth"]
        + SOURCE["priests_court_depth"]
        + SOURCE["altar"][0]
        + SOURCE["altar_to_hall"]
    )
    hall_depth = SOURCE["hall_depth"]
    back_x = facade_x + SOURCE["sanctuary"][0]
    floor_z = ASSUMED["priests_court_level"] + SOURCE["hall_steps"] * 0.5
    height = SOURCE["sanctuary"][2]
    hall_width = SOURCE["sanctuary"][1]
    body_width = SOURCE["sanctuary_body_width"]

    build_hall_steps(facade_x)
    building_wall_with_gate(
        "Hall east facade", facade_x + 2.5, COURT_CENTER_Y,
        hall_width, 5, height, floor_z,
        SOURCE["hall_gate"][0], SOURCE["hall_gate"][1], group,
    )
    box("Hall north wall", (hall_depth, 5, height),
        (facade_x + hall_depth / 2, COURT_CENTER_Y + hall_width / 2 - 2.5,
         floor_z + height / 2), "Jerusalem limestone", group)
    box("Hall south wall", (hall_depth, 5, height),
        (facade_x + hall_depth / 2, COURT_CENTER_Y - hall_width / 2 + 2.5,
         floor_z + height / 2), "Jerusalem limestone", group)
    box("Hall roof", (hall_depth, hall_width, 3),
        (facade_x + hall_depth / 2, COURT_CENTER_Y, floor_z + height - 1.5),
        "Jerusalem limestone", group)
    add_hall_facade_details(facade_x, COURT_CENTER_Y, floor_z, height, group)

    # The 100-cubit facade projects 15 cubits beyond the 70-cubit body on
    # either side. These side spaces are the House of Knives (Beit Hahalifot).
    for side, y in (("north", COURT_CENTER_Y + 35),
                    ("south", COURT_CENTER_Y - 35)):
        box(f"Hall {side} wing partition", (11, 1, 28),
            (facade_x + 10.5, y, floor_z + 14),
            "Assumed element", group)

    body_start = facade_x + hall_depth
    body_depth = SOURCE["sanctuary"][0] - hall_depth
    heikhal_wall = 6.0
    outer_wall = 5.0
    building_wall_with_gate(
        "Sanctuary inner facade", body_start + heikhal_wall / 2, COURT_CENTER_Y,
        body_width, heikhal_wall, height, floor_z,
        10, 20, group,
    )
    # Two gilded leaves with recessed panels and pull rings form the Great Gate.
    for side in (-1, 1):
        door_y = COURT_CENTER_Y + side * 2.55
        box("דלת הזהב של ההיכל", (0.24, 4.82, 19.5),
            (body_start - 0.16, door_y, floor_z + 9.75),
            "Gold", group, 0.08)
        for panel_z in (3.5, 9.7, 15.9):
            box("לוח שקוע בדלת ההיכל", (0.12, 3.55, 4.3),
                (body_start - 0.31, door_y, floor_z + panel_z),
                "Bronze", group, 0.05)
        torus("טבעת דלת ההיכל", 0.42, 0.08,
              (body_start - 0.40, COURT_CENTER_Y + side * 1.2, floor_z + 9.0),
              "Gold", group, rotation=(0, math.pi / 2, 0))
    box("Sanctuary north outer wall", (body_depth, outer_wall, height),
        (body_start + body_depth / 2,
         COURT_CENTER_Y + body_width / 2 - outer_wall / 2,
         floor_z + height / 2), "Jerusalem limestone", group)
    box("Sanctuary south outer wall", (body_depth, outer_wall, height),
        (body_start + body_depth / 2,
         COURT_CENTER_Y - body_width / 2 + outer_wall / 2,
         floor_z + height / 2), "Jerusalem limestone", group)
    box("Sanctuary west outer wall", (outer_wall, body_width, height),
        (back_x - outer_wall / 2, COURT_CENTER_Y, floor_z + height / 2),
        "Jerusalem limestone", group)
    box("Sanctuary roof", (body_depth, body_width, 3),
        (body_start + body_depth / 2, COURT_CENTER_Y, floor_z + height - 1.5),
        "Jerusalem limestone", group)
    # High windows light the upper structure; their exact spacing is schematic.
    for side in (-1, 1):
        for window in range(6):
            window_x = body_start + 9 + window * (body_depth - 18) / 5
            box("חלון עליון בהיכל", (4.4, 0.16, 5.5),
                (window_x, COURT_CENTER_Y + side * 35.06,
                 floor_z + 61.0), "Dark opening", group, 0.10)
            for bar in (-1.2, 0.0, 1.2):
                box("סורג חלון ההיכל", (0.13, 0.22, 5.2),
                    (window_x + bar, COURT_CENTER_Y + side * 35.14,
                     floor_z + 61.0), "Gold", group, 0.03)
    add_hall_interior_details(
        facade_x, body_start, COURT_CENTER_Y, floor_z, group
    )

    # Exact east-west interior sequence from Middot 4:7: 40-cubit Holy Place,
    # one-cubit Traksin, 20-cubit Holy of Holies. Yoma 5:1 places one curtain
    # on each side of the Traksin, with the outer/eastern opening at the south
    # and the inner/western opening at the north. The opening depth is
    # schematic because the source does not supply a measurement.
    traksin_east_x = facade_x + 5 + 11 + 6 + 40
    traksin_west_x = traksin_east_x + 1
    inner_center_x = facade_x + 5 + 11 + 6 + (40 + 1 + 20) / 2
    box("Holy Place north wall", (61, 6, 40),
        (inner_center_x, COURT_CENTER_Y + 13, floor_z + 20),
        "Jerusalem limestone", group)
    box("Holy Place south wall", (61, 6, 40),
        (inner_center_x, COURT_CENTER_Y - 13, floor_z + 20),
        "Jerusalem limestone", group)
    box("Holy of Holies west wall", (6, 20, 40),
        (facade_x + 5 + 11 + 6 + 40 + 1 + 20 + 3,
         COURT_CENTER_Y, floor_z + 20), "Jerusalem limestone", group)
    opening_depth = 1.5
    curtain_length = 20 - opening_depth
    inner_south_y = COURT_CENTER_Y - 10
    inner_north_y = COURT_CENTER_Y + 10

    # Source-plan +Y is north. The eastern curtain therefore runs from the
    # north wall toward the south, stopping short of the southern end.
    east_end_y = inner_south_y + opening_depth
    box("Traksin curtain east - south opening", (0.12, curtain_length, 40),
        (traksin_east_x, (east_end_y + inner_north_y) / 2, floor_z + 20),
        "Curtain", group)
    box("Traksin curtain south fold", (0.35, 0.12, 40),
        (traksin_east_x - 0.175, east_end_y, floor_z + 20),
        "Curtain", group)

    # The western curtain starts after a northern opening and reaches south.
    west_start_y = inner_north_y - opening_depth
    box("Traksin curtain west - north opening", (0.12, curtain_length, 40),
        (traksin_west_x, (inner_south_y + west_start_y) / 2, floor_z + 20),
        "Curtain", group)
    box("Traksin curtain north fold", (0.35, 0.12, 40),
        (traksin_west_x + 0.175, west_start_y, floor_z + 20),
        "Curtain", group)

    add_sanctuary_chambers(
        body_start, body_depth, back_x, COURT_CENTER_Y, floor_z
    )
    add_roof_parapet_and_spikes(
        facade_x, back_x, COURT_CENTER_Y, floor_z, height, group
    )

    label("ההיכל 100×100×100 אמה", facade_x + 50, COURT_CENTER_Y,
          floor_z + height + 2, 3.0)


def add_compass_and_scale() -> None:
    group = "00 Labels"
    z = 1.2
    # +X is west, so the east arrow points toward negative X.
    box("East-west scale bar", (50, 1, 0.4), (-180, -210, z),
        "Dark opening", group)
    for index in range(5):
        box(f"Scale segment {index + 1}", (10, 1.2, 0.5),
            (-200 + index * 10 + 5, -210, z + 0.05),
            "Gold" if index % 2 == 0 else "Dark opening", group)
    label("50 אמה / 25 מטר", -175, -216, z + 0.3, 2.2)
    label("מזרח", -218, -195, z + 0.3, 2.5)
    label("מערב", 218, -195, z + 0.3, 2.5)
    label("צפון", 0, 220, z + 0.3, 2.5)


def setup_world_and_camera() -> None:
    world = bpy.context.scene.world
    world.color = (0.045, 0.055, 0.075)
    world.use_nodes = True
    background = world.node_tree.nodes.get("Background")
    background.inputs["Color"].default_value = (0.06, 0.075, 0.11, 1.0)
    background.inputs["Strength"].default_value = 0.45

    bpy.ops.object.light_add(type="SUN", location=scene_location((-120, -160, 280)))
    sun = bpy.context.object
    sun.name = "שמש"
    sun.data.name = sun.name
    sun.rotation_euler = (math.radians(28), math.radians(-24), math.radians(-35))
    sun.data.energy = 3.0
    sun.data.angle = math.radians(12)
    move_to_collection(sun, "11 Lighting and Camera")

    bpy.ops.object.light_add(type="AREA", location=scene_location((-100, -100, 260)))
    fill = bpy.context.object
    fill.name = "תאורת מילוי"
    fill.data.name = fill.name
    fill.data.energy = 2200
    fill.data.shape = "DISK"
    fill.data.size = m(180)
    move_to_collection(fill, "11 Lighting and Camera")

    # A restrained local fill keeps the altar's east/south faces legible
    # without washing out the ledge shadows that reveal its form.
    bpy.ops.object.light_add(type="AREA", location=scene_location((40, 36, 42)))
    altar_fill = bpy.context.object
    altar_fill.name = "תאורת מילוי רכה למזבח"
    altar_fill.data.name = altar_fill.name
    altar_fill.data.energy = 100
    altar_fill.data.color = (1.0, 0.92, 0.80)
    altar_fill.data.shape = "DISK"
    altar_fill.data.size = m(24)
    altar_target = Vector(scene_location((61, 71, 22)))
    altar_fill.rotation_euler = (
        altar_target - altar_fill.location
    ).to_track_quat("-Z", "Y").to_euler()
    move_to_collection(altar_fill, "11 Lighting and Camera")

    bpy.ops.object.camera_add(location=scene_location((-390, -420, 360)))
    camera = bpy.context.object
    camera.name = "מצלמת מבט כללי"
    camera.data.name = camera.name
    move_to_collection(camera, "11 Lighting and Camera")
    point_camera(camera, Vector(scene_location((15, 55, 20))))
    camera.data.lens = 52
    bpy.context.scene.camera = camera

    scene = bpy.context.scene
    # Blender 4.x called the engine BLENDER_EEVEE_NEXT; Blender 5.x renamed
    # it back to BLENDER_EEVEE. Support both without requiring a version check.
    try:
        scene.render.engine = "BLENDER_EEVEE_NEXT"
    except TypeError:
        scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x = 1600
    scene.render.resolution_y = 1000
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.filepath = os.path.abspath("temple_middot_preview.png")


def point_camera(camera: bpy.types.Object, target: Vector) -> None:
    direction = target - camera.location
    camera.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()


def build_model() -> None:
    global MIRROR_PLAN_Y
    MIRROR_PLAN_Y = True
    clear_scene()
    add_materials()
    for name in (
        "00 Labels", "01 Temple Mount", "02 Mount Walls and Gates",
        "03 Soreg and Cheil (interpreted footprint)", "04 Women's Court",
        "04 Women's Court Chambers", "05 Fifteen Curved Steps",
        "06 Azarah", "06 Azarah Gates", "06 Azarah Chambers",
        "07 Altar and Service Area", "08 Hall Steps",
        "09 Sanctuary", "10 Chambers (schematic)",
        "11 Lighting and Camera",
    ):
        collection(name)
    build_ground_and_mount()
    build_soreg()
    build_womens_court()
    build_azarah()
    build_azarah_gates_and_chambers()
    build_altar_and_service_area()
    build_sanctuary()
    add_compass_and_scale()
    setup_world_and_camera()

    scene = bpy.context.scene
    scene["model_title"] = "Temple study model according to Mishnah Middot"
    scene["cubit_meters"] = CUBIT_M
    scene["accuracy_note"] = (
        "SOURCE holds explicit or directly derived Middot dimensions; "
        "INTERPRETED holds documented interpretations; blue elements and "
        "ASSUMED values are schematic reconstructions."
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--save", default="")
    parser.add_argument("--export", default="")
    parser.add_argument("--render", action="store_true")
    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    return parser.parse_args(args)


def finish_outputs(args: argparse.Namespace) -> None:
    if args.render:
        bpy.ops.render.render(write_still=True)
    if args.save:
        bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(args.save))
    if args.export:
        target = os.path.abspath(args.export)
        bpy.ops.export_scene.gltf(filepath=target, export_format="GLB")


if __name__ == "__main__":
    build_model()
    finish_outputs(parse_args())
