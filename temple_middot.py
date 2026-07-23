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
    obj.data.materials.append(MATERIALS["White altar stone"])


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

    inset = width / 2 - SOURCE["corner_chamber"][0] / 2
    rooms = [
        ("לשכת הנזירים – דרום מזרח", center_x - inset, COURT_CENTER_Y - inset),
        ("לשכת דיר העצים – צפון מזרח", center_x - inset, COURT_CENTER_Y + inset),
        ("לשכת המצורעים – צפון מערב", center_x + inset, COURT_CENTER_Y + inset),
        ("לשכת בית שמניה – דרום מערב", center_x + inset, COURT_CENTER_Y - inset),
    ]
    for name, x, y in rooms:
        open_room(name, x, y, 40, 40, level)
        label(name, x, y, level + 0.2, 1.65)

    # Fifteen curved steps: successive stacked half-discs make visible treads.
    for index in range(SOURCE["women_steps"]):
        radius = (SOURCE["women_steps"] - index) * 0.5
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
    gated_wall_x("Azarah south wall", center_x, COURT_SOUTH_Y,
                 width_x, wall_t, wall_h, 0,
                 [(x, gate_w) for x in (55, 105, 165)], "06 Azarah")
    gated_wall_x("Azarah north wall", center_x, COURT_NORTH_Y,
                 width_x, wall_t, wall_h, 0,
                 [(x, gate_w) for x in (55, 105, 165)], "06 Azarah")

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

    box("יסוד המזבח 32×32", (32, 32, 1),
        (altar_center_x, altar_center_y, z + 0.5), "White altar stone", group)
    box("גוף המזבח 30×30", (30, 30, 5),
        (altar_center_x, altar_center_y, z + 3.5), "White altar stone", group)
    box("ראש המזבח 28×28", (28, 28, 3),
        (altar_center_x, altar_center_y, z + 7.5), "White altar stone", group)
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
                "White altar stone", group)

    # 32 cubits is the sloped length. With a nine-cubit rise its ground run is
    # about 30.7 cubits, conventionally rounded to 30 in schematic plans.
    ramp_run = math.sqrt(SOURCE["altar_ramp"][1] ** 2 - ASSUMED["altar_height"] ** 2)
    ramp_wedge("כבש המזבח 32×16", altar_center_x,
               altar_center_y - 16 - ramp_run, altar_center_y - 16,
               16, z, ASSUMED["altar_height"], group)

    # Twenty-four slaughter rings, six rows of four north of the altar.
    ring_origin_x = altar_center_x - 6
    ring_origin_y = altar_center_y + 24
    for row in range(6):
        for column in range(4):
            bpy.ops.mesh.primitive_torus_add(
                major_radius=m(0.55), minor_radius=m(0.10),
                major_segments=20, minor_segments=8,
                location=scene_location((ring_origin_x + column * 4,
                                         ring_origin_y + row * 4, z + 0.12)),
            )
            obj = bpy.context.object
            obj.name = f"טבעת שחיטה {row * 4 + column + 1:02d}"
            obj.data.name = obj.name
            obj.data.materials.append(MATERIALS["Bronze"])
            move_to_collection(obj, group)

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
            "White altar stone", group)

    # Laver between the altar and hall, shifted south as stated in Middot 3:6.
    cylinder("Laver basin", 2.0, 1.8,
             (altar_center_x + 28, COURT_CENTER_Y - 18, z + 2.5),
             "Bronze", group)
    cylinder("Laver pedestal", 0.8, 2.5,
             (altar_center_x + 28, COURT_CENTER_Y - 18, z + 1.25),
             "Bronze", group)
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

    # Three visible chamber tiers indicate the 38 surrounding cells described
    # in Middot 4:3-4. Individual cell widths are not specified in the Mishnah.
    for tier, projection in enumerate((5.0, 6.0, 7.0)):
        tier_z = floor_z + 10 + tier * 18
        box(f"North chamber tier {tier + 1}", (body_depth - 8, projection, 14),
            (body_start + body_depth / 2,
             COURT_CENTER_Y + 16 + projection / 2,
             tier_z + 7), "Assumed element", "10 Chambers (schematic)")
        box(f"South chamber tier {tier + 1}", (body_depth - 8, projection, 14),
            (body_start + body_depth / 2,
             COURT_CENTER_Y - 16 - projection / 2,
             tier_z + 7), "Assumed element", "10 Chambers (schematic)")

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
        "06 Azarah", "07 Altar and Service Area", "08 Hall Steps",
        "09 Sanctuary", "10 Chambers (schematic)",
        "11 Lighting and Camera",
    ):
        collection(name)
    build_ground_and_mount()
    build_soreg()
    build_womens_court()
    build_azarah()
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
