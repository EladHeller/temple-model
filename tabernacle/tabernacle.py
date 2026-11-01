"""Procedural study model of the wilderness Tabernacle (Mishkan).

Primary sources: Exodus 25--30 and 35--40.  The 30 x 10 cubit footprint,
20/10 cubit inner division, one-cubit board thickness and vessel positions
follow the rabbinic/traditional reconstruction summarized in Hebrew
Wikipedia's "The Tabernacle" article.

Run from this directory with Blender 4.2 or later:

    blender --background --python tabernacle.py -- \
      --save tabernacle.blend --export tabernacle.glb --render

Add ``--interior`` to create the open cutaway companion model.
Add ``--covered`` to create the complete covered companion model.  All source
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
    "board_socket": (0.75, 1.0, 1.0),       # Rashi on Exodus 26:17
    "board_tenon": (0.25, 0.50, 1.0),       # traditional reconstruction
    "inner_curtain": (28.0, 4.0, 10),      # Exodus 26:1-2
    "goat_curtain": (30.0, 4.0, 11),       # Exodus 26:7-8
    "altar": (5.0, 5.0, 3.0),              # Exodus 27:1
    "ark": (2.5, 1.5, 1.5),                # Exodus 25:10
    "table": (2.0, 1.0, 1.5),              # Exodus 25:23
    "incense_altar": (1.0, 1.0, 2.0),      # Exodus 30:2
}

# Dimensions supplied by a named traditional interpretation rather than by
# the biblical construction text itself.
INTERPRETED = {
    # Malbim on Exodus 25:14: the poles made by Moses were ten cubits long,
    # matching the depth of the Tabernacle's Holy of Holies.
    "roof_hides": (30.0, 10.0),  # Rashi Exodus 26:14: two superposed roof covers
    "ark_pole_length": 10.0,
    # Rashi on Exodus 25:20, following Sukkah 5b: ten handbreadths of clear
    # space separated the spread wings from the upper face of the cover.
    # This model uses the six-handbreadth cubit applied to the Ark there.
    "cherub_wing_spread_height": 10.0 / 6.0,
}

# The text gives no dimensions for these items or construction details.
ASSUMED = {
    "laver_size": 1.35,
    "cover_thickness": 0.025,
    "cover_layer_separation": 0.065,  # display clearance, not a source dimension
    "cover_corner_tucks": "diagonal overlapping folds",
    "cover_woven_motifs": "schematic lion outside and eagle inside; repeat artistic",
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
    # Rashi Exodus 25:5 describes many colours. The palette is artistic.
    material("עורות תחשים – גוון סכמטי", (0.06, 0.22, 0.30, 1), roughness=0.65)
    material("עצי שיטים", (0.34, 0.13, 0.035, 1), roughness=0.68)
    material("זהב", (0.88, 0.55, 0.07, 1), metallic=0.9, roughness=0.2)
    material("כסף", (0.72, 0.76, 0.80, 1), metallic=0.92, roughness=0.18)
    material("נחושת", (0.48, 0.21, 0.055, 1), metallic=0.72, roughness=0.3)
    material("מים", (0.05, 0.30, 0.52, 1), metallic=0.05, roughness=0.12)
    material("לחם הפנים", (0.63, 0.31, 0.07, 1), roughness=0.82)
    material("כהה", (0.018, 0.012, 0.008, 1), roughness=1.0)
    material("להבה", (0.95, 0.15, 0.015, 1), roughness=0.25,
             emission=(1.0, 0.08, 0.005, 1), emission_strength=4.0)

    for name, color, metal in (
        ("אריג יריעות המשכן", (.16, .055, .22, 1), 0),
        ("אריג עיזים שחור", (.025, .021, .018, 1), 0),
        ("מכסה אילים", (.45, .025, .015, 1), 0),
        ("מכסה תחשים", (.06, .22, .30, 1), 0),
        ("לולאות תכלת – יריעות", (.08, .28, .62, 1), 0),
        ("לולאות עיזים", (.035, .028, .02, 1), 0),
        ("קרסי זהב – יריעות", (.88, .55, .07, 1), .9),
        ("קרסי נחושת – יריעות", (.48, .21, .055, 1), .72),
        ("אריגה תכלת", (.08, .28, .62, 1), 0),
        ("אריגה שני", (.68, .035, .025, 1), 0),
        ("אריגה שש", (.88, .82, .68, 1), 0),
    ):
        material(name, color, metallic=metal, roughness=.85 if not metal else .3)


def add_covering_textures() -> None:
    # These UV textures are embedded in GLB, including their thread normal map.
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from covering_textures import create_textures
    texture_dir = create_textures(os.path.join(os.path.dirname(__file__), "textures"))
    normal_image = bpy.data.images.load(str(texture_dir / "weave_normal.png"), check_existing=True)
    normal_image.colorspace_settings.name = "Non-Color"
    hide_normal = bpy.data.images.load(str(texture_dir / "hide_normal.png"), check_existing=True)
    hide_normal.colorspace_settings.name = "Non-Color"
    for name, texture in (("אריג יריעות המשכן", "woven"), ("אריג עיזים שחור", "goat"),
                          ("מכסה אילים", "ram"), ("מכסה תחשים", "tahash")):
        mat = MATERIALS[name]
        nodes = mat.node_tree.nodes
        bsdf = nodes.get("Principled BSDF")
        image = nodes.new("ShaderNodeTexImage")
        image.image = bpy.data.images.load(str(texture_dir / (texture + ".png")), check_existing=True)
        mat.node_tree.links.new(image.outputs["Color"], bsdf.inputs["Base Color"])
        normal_texture = nodes.new("ShaderNodeTexImage")
        normal_texture.image = hide_normal if texture in ("ram", "tahash") else normal_image
        if texture in ("ram", "tahash"):
            bsdf.inputs["Roughness"].default_value = .65
        normal = nodes.new("ShaderNodeNormalMap")
        normal.inputs["Strength"].default_value = .35
        mat.node_tree.links.new(normal_texture.outputs["Color"], normal.inputs["Color"])
        mat.node_tree.links.new(normal.outputs["Normal"], bsdf.inputs["Normal"])


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
    for polygon in obj.data.polygons:
        polygon.use_smooth = True
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


def ellipsoid_between(name: str, start: tuple[float, float, float],
                      end: tuple[float, float, float], width: float,
                      depth: float, mat: str, group: str) -> bpy.types.Object:
    """Create a softly modelled limb or torso aligned between two points."""
    a = Vector(tuple(m(v) for v in start))
    b = Vector(tuple(m(v) for v in end))
    direction = b - a
    bpy.ops.mesh.primitive_uv_sphere_add(
        segments=24, ring_count=12, radius=1, location=(a + b) / 2)
    obj = bpy.context.object
    obj.name = name
    obj.data.name = name
    obj.scale = (m(width), m(depth), direction.length / 2)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.rotation_mode = "QUATERNION"
    obj.rotation_quaternion = direction.to_track_quat("Z", "Y")
    for polygon in obj.data.polygons:
        polygon.use_smooth = True
    obj.data.materials.append(MATERIALS[mat])
    return move_to(obj, group)


def frustum(name: str, radius_bottom: float, radius_top: float, depth: float,
            location: tuple[float, float, float], mat: str, group: str,
            vertices: int = 32) -> bpy.types.Object:
    """Create a truncated cone for a pedestal or flared menorah cup."""
    bpy.ops.mesh.primitive_cone_add(
        vertices=vertices, radius1=m(radius_bottom), radius2=m(radius_top),
        depth=m(depth), location=tuple(m(v) for v in location),
    )
    obj = bpy.context.object
    obj.name = name
    obj.data.name = name
    obj.data.materials.append(MATERIALS[mat])
    return move_to(obj, group)


def curved_rod(name: str, start: tuple[float, float, float],
               end: tuple[float, float, float], radius: float,
               mat: str, group: str) -> bpy.types.Object:
    """Make a smooth U-shaped menorah branch with an upright upper end."""
    start_v = Vector(tuple(m(v) for v in start))
    end_v = Vector(tuple(m(v) for v in end))
    horizontal = end_v.x - start_v.x
    vertical = end_v.z - start_v.z

    curve = bpy.data.curves.new(name, type="CURVE")
    curve.dimensions = "3D"
    curve.resolution_u = 24
    curve.bevel_depth = m(radius)
    curve.bevel_resolution = 5
    curve.resolution_v = 5
    curve.use_fill_caps = True
    spline = curve.splines.new(type="BEZIER")
    spline.bezier_points.add(1)
    lower, upper = spline.bezier_points
    lower.co = start_v
    upper.co = end_v
    lower.handle_left_type = "FREE"
    lower.handle_right_type = "FREE"
    lower.handle_left = start_v
    lower.handle_right = start_v + Vector((horizontal * 0.52, 0, vertical * 0.06))
    upper.handle_left_type = "FREE"
    upper.handle_right_type = "FREE"
    upper.handle_left = end_v - Vector((0, 0, vertical * 0.54))
    upper.handle_right = end_v

    obj = bpy.data.objects.new(name, curve)
    curve.materials.append(MATERIALS[mat])
    collection(group).objects.link(obj)
    return obj


def open_socket(name: str, location: tuple[float, float, float], *,
                west: bool, group: str) -> None:
    """Build Rashi's hollow, one-cubit-high silver board socket."""
    # Each socket is 1 x 3/4 x 1 cubit, with quarter-cubit walls.  Rotating
    # those dimensions at the west wall leaves the same 1/2 x 1/4 cavity for
    # the matching board tenon.
    sx, sy, sz = ((1.0, 0.75, 1.0) if west else (0.75, 1.0, 1.0))
    hx, hy = ((0.50, 0.25) if west else (0.25, 0.50))
    z0, z1 = -m(sz) / 2, m(sz) / 2
    ox, oy = m(sx) / 2, m(sy) / 2
    ix, iy = m(hx) / 2, m(hy) / 2
    vertices = (
        (-ox, -oy, z0), (ox, -oy, z0), (ox, oy, z0), (-ox, oy, z0),
        (-ox, -oy, z1), (ox, -oy, z1), (ox, oy, z1), (-ox, oy, z1),
        (-ix, -iy, z0), (ix, -iy, z0), (ix, iy, z0), (-ix, iy, z0),
        (-ix, -iy, z1), (ix, -iy, z1), (ix, iy, z1), (-ix, iy, z1),
    )
    faces = (
        # Outer faces.
        (0, 1, 5, 4), (1, 2, 6, 5),
        (2, 3, 7, 6), (3, 0, 4, 7),
        # Top and bottom rims.
        (4, 5, 13, 12), (5, 6, 14, 13),
        (6, 7, 15, 14), (7, 4, 12, 15),
        (0, 8, 9, 1), (1, 9, 10, 2),
        (2, 10, 11, 3), (3, 11, 8, 0),
        # Inner faces, wound toward the open cavity.
        (8, 12, 13, 9), (9, 13, 14, 10),
        (10, 14, 15, 11), (11, 15, 12, 8),
    )
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    obj.location = tuple(m(value) for value in location)
    mesh.materials.append(MATERIALS["כסף"])
    collection(group).objects.link(obj)
    bevel = obj.modifiers.new("עיגול קצוות", "BEVEL")
    bevel.width = m(0.018)
    bevel.segments = 2


def wedge_prism(name: str, *, x_center: float, y_high: float, y_low: float,
                width: float, height: float, mat: str,
                group: str) -> bpy.types.Object:
    """Create a closed triangular prism with its high end at ``y_high``."""
    x0 = m(x_center - width / 2)
    x1 = m(x_center + width / 2)
    yh = m(y_high)
    yl = m(y_low)
    h = m(height)
    vertices = (
        (x0, yh, 0), (x1, yh, 0), (x0, yl, 0), (x1, yl, 0),
        (x0, yh, h), (x1, yh, h),
    )
    faces = (
        (0, 2, 3, 1),       # floor
        (0, 1, 5, 4),       # high end
        (0, 4, 2),          # west side
        (1, 3, 5),          # east side
        (4, 5, 3, 2),       # sloping top
    )
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    mesh.materials.append(MATERIALS[mat])
    collection(group).objects.link(obj)
    bevel = obj.modifiers.new("עיגול קצוות", "BEVEL")
    bevel.width = m(0.025)
    bevel.segments = 2
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


def add_boards(*, cutaway: bool = False, full_width: bool = False) -> None:
    group = "02 קרשים אדנים ובריחים"
    # Rabbi Nehemiah's constant one-cubit thickness is selected.  It is a
    # visible parameter, since Rabbi Judah's tapering boards are an alternative.
    side_center = 5.5 if full_width else 4.5
    rear_x = 30.5 if full_width else 29.5
    bar_offset = 0.5 if full_width else 0.56
    bar_radius = 0.04 if full_width else 0.075
    for side, y in (("צפון", -side_center), ("דרום", side_center)):
        for index in range(20):
            x = 0.75 + index * 1.5
            if cutaway and side == "דרום":
                # The removed display wall leaves its forty silver sockets in
                # place.  Their open mortises show where the two tenons of
                # every board would have fitted.
                for tenon, dx in enumerate((-0.375, 0.375), 1):
                    open_socket(
                        f"אדן כסף דרום {index + 1:02d}-{tenon}",
                        (x + dx, y, 0.5), west=False, group=group,
                    )
                continue
            box(f"קרש {side} {index + 1:02d}", (1.48, 1, 9),
                (x, y, 5.5), "זהב", group, 0.025)
            add_board_sockets(x, y, side, index + 1, group)
        if not (cutaway and side == "דרום"):
            # Four half-wall bars and the full middle bar.
            for z in (2.5, 7.5):
                rod(f"בריח {side} מזרחי בגובה {z}", (0, y + (bar_offset if side == "דרום" else -bar_offset), z),
                    (15, y + (bar_offset if side == "דרום" else -bar_offset), z), bar_radius, "זהב", group)
                rod(f"בריח {side} מערבי בגובה {z}", (15, y + (bar_offset if side == "דרום" else -bar_offset), z),
                    (30, y + (bar_offset if side == "דרום" else -bar_offset), z), bar_radius, "זהב", group)
            rod(f"בריח תיכון {side}", (0, y, 5), (30, y, 5), 0.065, "זהב", group)

    # Six rear boards and two full-width corner boards.  Following Rashi's
    # constant-thickness reconstruction, one cubit of each 1.5-cubit corner
    # board overlaps the adjoining structure and half a cubit completes the
    # west face. The covered model uses the full 12-cubit outside width;
    # legacy cutaways retain their earlier 10-cubit outside footprint.
    for index in range(6):
        y = -3.75 + index * 1.5
        box(f"קרש מערב {index + 1:02d}", (1, 1.48, 9), (rear_x, y, 5.5),
            "זהב", group, 0.025)
        add_board_sockets(rear_x, y, "מערב", index + 1, group, west=True)
    for side, y in (("צפון", -5.25 if full_width else -4.25), ("דרום", 5.25 if full_width else 4.25)):
        if cutaway and side == "דרום":
            # The cutaway also removes the southern corner board, but its two
            # sockets remain so that all 96 board sockets are represented.
            for tenon, dy in enumerate((-0.375, 0.375), 1):
                open_socket(f"אדן כסף קרש מקצוע {side}-{tenon}",
                            (29.5, y + dy, 0.5), west=True, group=group)
            continue
        box(f"קרש מקצוע {side}", (1, 1.5, 9), (rear_x, y, 5.5),
            "זהב", group, 0.025)
        add_board_sockets(rear_x, y, f"מקצוע {side}", 1, group, west=True)

    # Five gilded entrance posts on copper sockets.
    for index, y in enumerate((-5, -2.5, 0, 2.5, 5) if full_width else (-4, -2, 0, 2, 4), 1):
        cylinder(f"עמוד פתח המשכן {index}", 0.12, 10, (0, y, 5), "זהב", group, 20)
        cylinder(f"אדן נחושת לפתח {index}", 0.23, 0.35, (0, y, 0.175), "נחושת", group, 24)


def add_board_sockets(x: float, y: float, side: str, index: int,
                      group: str, west: bool = False) -> None:
    if west:
        for tenon, dy in enumerate((-0.375, 0.375), 1):
            open_socket(f"אדן כסף {side} {index:02d}-{tenon}",
                        (x, y + dy, 0.5), west=True, group=group)
            box(f"יד קרש {side} {index:02d}-{tenon}", (0.50, 0.25, 1.0),
                (x, y + dy, 0.5), "זהב", group, 0.01)
    else:
        for tenon, dx in enumerate((-0.375, 0.375), 1):
            open_socket(f"אדן כסף {side} {index:02d}-{tenon}",
                        (x + dx, y, 0.5), west=False, group=group)
            box(f"יד קרש {side} {index:02d}-{tenon}", (0.25, 0.50, 1.0),
                (x + dx, y, 0.5), "זהב", group, 0.01)


def covering_point(u: float, v: float, lift: float = 0.0) -> Vector:
    """Fold cloth coordinates (cubits) over a 31 x 12 outer board footprint.

    The rear corner squares fold back on their diagonals; their tuck and tiny
    display separation are artistic, not an additional sourced measurement.
    Negative u is the two-cubit front fold of the sixth goat curtain.
    """
    side = max(0.0, abs(v) - 6.0)
    sign = -1 if v < 0 else 1
    y = max(-6.0, min(6.0, v))
    if 0 <= u <= 31:
        x, z = u, 10.0 - side
        if side:
            # Free-hanging cloth has shallow folds and a softly uneven hem.
            drape = .055 + .065 * math.sin(u * math.pi) ** 2 * min(1, side / 6)
            y += sign * (lift + drape)
        else:
            # A modest sag between joins conveys a stretched textile roof.
            z -= .10 * (1 - (v / 6) ** 2) * math.sin(u * math.pi / 4) ** 2
    else:
        back = u > 31
        drop = u - 31 if back else -u
        x = 31.0 + lift if back else -lift
        z = 10.0 - drop
        if side:
            y = sign * (6.0 - min(side, drop))
            z = 10.0 - max(side, drop)
            # The two halves of a diagonal tuck need separate surfaces.
            # Otherwise coincident cloth faces flicker once they carry a pattern.
            tuck = .012 * min(side, drop)
            if side > drop:
                tuck += .08 * min(side, drop) * (side-drop)/(side+drop)
            x += (1 if back else -1) * tuck
        if z < 0.03:
            x += (1 if back else -1) * (0.03 - z)
            z = 0.03
    # Very shallow fabric ripples, not a pitched roof or rigid slab.
    ripple = (0.012 * math.sin(u * math.pi * 2) * math.sin(v * math.pi)
              if side else 0.0)
    return Vector((x, y, z + lift + ripple))


def covering_mesh(name: str, u0: float, u1: float, span: float,
                  mat: str, layer: int) -> bpy.types.Object:
    us = sorted(set([u0, u1] + [u0 + i / 4 for i in range(1, int((u1-u0)*4))]
                    + [u for u in (0, 31) if u0 < u < u1]))
    vs = sorted(set([-span / 2, span / 2, -6.0, 6.0]
                    + [-span / 2 + i / 2 for i in range(1, int(span*2))]))
    lift = layer * ASSUMED["cover_layer_separation"]
    vertices = [tuple(m(c) for c in covering_point(u, v, lift)) for u in us for v in vs]
    faces = []
    n = len(vs)
    for i in range(len(us)-1):
        for j in range(n-1):
            a = i*n+j
            faces.append((a, a+n, a+n+1, a+1))
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    mesh.materials.append(MATERIALS[mat])
    uv = mesh.uv_layers.new(name="אריגה לפי מידות היריעה")
    for polygon in mesh.polygons:
        polygon.use_smooth = True
        for loop_index in polygon.loop_indices:
            vertex = mesh.loops[loop_index].vertex_index
            i, j = divmod(vertex, n)
            if layer >= 3:
                # Each hide cover has one organic field, without a fabric repeat.
                uv.data[loop_index].uv = ((us[i]-u0)/(u1-u0), (vs[j]+span/2)/span)
            else:
                uv.data[loop_index].uv = ((us[i]-u0)/4, (vs[j]+14)/4)
    obj = bpy.data.objects.new(name, mesh)
    collection(f"03.{layer} כיסוי").objects.link(obj)
    obj["covering_layer"] = layer
    obj["flat_width_cubits"] = u1-u0
    obj["flat_length_cubits"] = span
    obj["cloth_u_start"] = u0
    obj["cloth_u_end"] = u1
    solidify = obj.modifiers.new("עובי אריג משוער", "SOLIDIFY")
    solidify.thickness = m(ASSUMED["cover_thickness"])
    solidify.offset = 0
    return obj


def add_covering_join(u: float, span: float, layer: int, metal: str) -> None:
    """Exactly 50 hooks and two matching sets of 50 loops per join."""
    group = f"03.{layer} כיסוי"
    loop_mat = "לולאות תכלת – יריעות" if layer == 1 else "לולאות עיזים"
    for i in range(50):
        v = -span / 2 + (i + 0.5) * span / 50
        for side in (-1, 1):
            p = covering_point(u + side * 0.05, v, layer * 0.065 + 0.012)
            torus(f"לולאה כיסוי {layer} צד {side} {i+1:02d}", 0.03, 0.009,
                  tuple(p), loop_mat, group)
        p1 = covering_point(u-0.05, v, layer*0.065+0.012)
        p2 = covering_point(u+0.05, v, layer*0.065+0.012)
        rod(f"קרס כיסוי {layer} {i+1:02d}", tuple(p1), tuple(p2),
            0.012, metal, group)


def add_woven_figures() -> None:
    """Flat coloured woven silhouettes: eagle inside, lion outside (Rashi 26:1).

    The pattern, colour distribution and repeat are artistic. Thin face meshes
    express woven figures rather than free-standing embroidered sculpture.
    """
    eagle = [(0,.8),(.2,.65),(.1,.5),(.2,.2),(.95,.6),(.75,.05),
             (.35,-.15),(.15,-.4),(.3,-.7),(0,-.55),(-.3,-.7),
             (-.15,-.4),(-.35,-.15),(-.75,.05),(-.95,.6),(-.2,.2),
             (-.1,.5),(-.12,.65)]
    lion = [(-.8,.15),(-.65,.3),(-.35,.3),(-.2,.52),(.05,.55),(.22,.4),
            (.3,.12),(.68,.12),(.8,.4),(.88,.35),(.78,-.1),(.48,-.22),
            (.42,-.58),(.25,-.58),(.24,-.2),(-.3,-.2),(-.4,-.58),
            (-.57,-.58),(-.55,-.15),(-.8,-.05)]
    for underside, shape in ((True, eagle), (False, lion)):
        vertices, faces = [], []
        for u in range(2, 40, 4):
            for v in (-12, -8, -4, 0, 4, 8, 12):
                from mathutils.geometry import tessellate_polygon
                outline = [Vector((du, dv, 0)) for du, dv in shape]
                for tessellated in tessellate_polygon([outline]):
                    triangle = [outline[p] if isinstance(p, int) else p for p in tessellated]
                    divisions = 5
                    grid = {}
                    for i in range(divisions+1):
                        for j in range(divisions+1-i):
                            du, dv, _ = (triangle[0] + (triangle[1]-triangle[0])*(i/divisions)
                                         + (triangle[2]-triangle[0])*(j/divisions))
                            p = covering_point(u+du, v+dv, .065)
                            tangent_u = covering_point(u+du+.001, v+dv, .065)-p
                            tangent_v = covering_point(u+du, v+dv+.001, .065)-p
                            normal = tangent_u.cross(tangent_v).normalized()
                            p += normal * (-.045 if underside else .045)
                            grid[i,j] = len(vertices)
                            vertices.append(tuple(m(c) for c in p))
                    for i in range(divisions):
                        for j in range(divisions-i):
                            faces.append((grid[i,j], grid[i+1,j], grid[i,j+1]))
                            if i+j < divisions-1:
                                faces.append((grid[i+1,j], grid[i+1,j+1], grid[i,j+1]))
        mesh = bpy.data.meshes.new("אריגה נשר" if underside else "אריגה אריה")
        mesh.from_pydata(vertices, [], faces)
        for mat in ("אריגה תכלת", "אריגה שני", "אריגה שש"):
            mesh.materials.append(MATERIALS[mat])
        mesh.update()
        for i, face in enumerate(mesh.polygons):
            face.material_index = (i // ((len(shape)-2)*25)) % 3
        obj = bpy.data.objects.new(mesh.name, mesh)
        obj["covering_layer"] = 1
        collection("03.1 כיסוי").objects.link(obj)


def add_outer_structure() -> None:
    # Rashi's constant-thickness reconstruction: 10 cubits CLEAR inside,
    # plus a one-cubit board on each side. Keep the older cutaways unchanged.
    add_covering_textures()
    add_boards(cutaway=False, full_width=True)
    box("רצפת המשכן המכוסה", (30, 10, .14), (15, 0, .07),
        "חול המדבר", "03 פנים המשכן")
    add_embroidered_textile("מסך פתח אוהל מועד", -.08, 5, 10, "03 פנים המשכן")
    for i, y in enumerate((-3.75, -1.25, 1.25, 3.75), 1):
        cylinder(f"עמוד הפרוכת {i}", .12, 10, (20, y, 5), "זהב", "03 פנים המשכן", 20)
        cylinder(f"אדן כסף לפרוכת {i}", .23, .35, (20, y, .175), "כסף", "03 פנים המשכן", 24)
    add_embroidered_textile("הפרוכת", 20, 5, 10, "03 פנים המשכן", veil=True)
    for add_vessel in (add_ark, add_incense_altar, add_table, add_menorah):
        add_vessel()
    for i in range(10):
        covering_mesh(f"יריעת משכן {i+1:02d} – מחברת {1+i//5}", i*4, (i+1)*4,
                      SOURCE["inner_curtain"][0], "אריג יריעות המשכן", 1)
    add_woven_figures()
    add_covering_join(20, 28, 1, "קרסי זהב – יריעות")
    # Six panels (-2..22) toward the east, five (22..42) toward the west.
    # Two cubits fold over the entrance; the remaining two extend behind.
    for i in range(11):
        covering_mesh(f"יריעת עיזים {i+1:02d} – מחברת {1 if i<6 else 2}",
                      -2+i*4, 2+i*4, SOURCE["goat_curtain"][0], "אריג עיזים שחור", 2)
    add_covering_join(22, 30, 2, "קרסי נחושת – יריעות")
    # Rashi 26:14: two superposed 30 x 10 roof hides; neither covers the walls.
    for layer, name, mat in ((3, "מכסה עורות אילים מאדמים", "מכסה אילים"),
                             (4, "מכסה עורות תחשים", "מכסה תחשים")):
        hide_length, hide_width = INTERPRETED["roof_hides"]
        covering_mesh(name, 0, hide_length, hide_width, mat, layer)
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
    # and construction for the wilderness altar are not supplied.  It is shown
    # here as copper side walls retaining compacted earth, matching the altar's
    # copper shell and earth filling instead of using a generic schematic hue.
    ramp_length = ASSUMED["altar_ramp_length"]
    ramp_width = ASSUMED["altar_ramp_width"]
    ramp_wall = 0.18
    y_high = 2.5
    y_low = y_high + ramp_length
    for side, ramp_x in (("מערב", x - ramp_width / 2 + ramp_wall / 2),
                         ("מזרח", x + ramp_width / 2 - ramp_wall / 2)):
        wedge_prism(
            f"דופן נחושת כבש המזבח {side}", x_center=ramp_x,
            y_high=y_high, y_low=y_low, width=ramp_wall, height=3.0,
            mat="נחושת", group=group,
        )
    wedge_prism(
        "מילוי אדמה בכבש המזבח – מידות סכמטיות", x_center=x,
        y_high=y_high + 0.06, y_low=y_low - 0.10,
        width=ramp_width - ramp_wall * 2, height=2.92,
        mat="חול המדבר", group=group,
    )
    box("סף נחושת בתחתית כבש המזבח", (ramp_width, 0.16, 0.16),
        (x, y_low - 0.08, 0.08), "נחושת", group, 0.025)

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
    # Menachot 98b places the Ark's 2.5-cubit length north-south and the poles
    # east-west.  With +X west and +Y south, the source dimensions are thus
    # rotated relative to most of the other furnishings in this scene.
    box("ארון העדות", (1.5, 2.5, 1.5), (x, y, 0.75), "זהב", group, 0.045)
    # A restrained framed panel treatment follows the Temple Institute visual
    # reference while keeping the sourced rectangular dimensions unchanged.
    for panel_y in (-1.265, 1.265):
        box("לוח דופן אורכי של הארון", (1.08, 0.045, 0.78),
            (x, panel_y, 0.72), "זהב", group, 0.025)
    for panel_x in (x - 0.765, x + 0.765):
        box("לוח דופן רוחבי של הארון", (0.045, 1.82, 0.78),
            (panel_x, y, 0.72), "זהב", group, 0.025)

    cover_size = (1.62, 2.62, 1 / 6)
    cover_center_z = 1.5 + cover_size[2] / 2
    box("כפורת", cover_size, (x, y, cover_center_z), "זהב", group, 0.04)
    crown_z = cover_center_z + cover_size[2] / 2 + 0.035
    for crown_y in (-1.32, 1.32):
        box("זר זהב לאורך הכפורת", (1.72, 0.055, 0.07),
            (x, crown_y, crown_z), "זהב", group, 0.018)
    for crown_x in (x - 0.84, x + 0.84):
        box("זר זהב לרוחב הכפורת", (0.055, 2.64, 0.07),
            (crown_x, y, crown_z), "זהב", group, 0.018)

    cover_top = cover_center_z + cover_size[2] / 2
    spread_wing_height = cover_top + INTERPRETED["cherub_wing_spread_height"]

    # The anatomy follows the kneeling, youthful figures and high feather fans
    # in the Temple Institute reconstruction.  Exact anatomy and wingspan are
    # still interpretive; the sourced facing direction and high spread remain.
    for north_south in (-1, 1):
        cy = y + north_south * 0.84
        inward = -north_south
        pelvis = (x, cy, 1.80)
        shoulders = (x, cy + inward * 0.30, 2.18)
        ellipsoid_between("גוף כרוב כורע ופשוט", pelvis, shoulders,
                          0.19, 0.15,
                          "זהב", group)
        # One low continuous kneeling base replaces the previous collection of
        # separate hips, knees, feet, elbows and hands.
        sphere("בסיס כרוב כורע", 0.23,
               (x, cy - inward * 0.02, 1.72), "זהב", group,
               scale=(0.72, 1.04, 0.30))

        neck_base = (x, cy + inward * 0.31, 2.16)
        head_center = (x, cy + inward * 0.47, 2.38)
        ellipsoid_between("צוואר כרוב", neck_base, head_center,
                          0.075, 0.070, "זהב", group)
        sphere("ראש כרוב – פני תינוק סכמטיים", 0.16, head_center,
               "זהב", group, scale=(0.88, 0.94, 1.04))

        # A single shoulder blade overlaps the torso and every feather root,
        # making both wings grow visibly from the body instead of floating.
        wing_joint = (x, cy + inward * 0.22, 2.20)
        sphere("חיבור כנפי הכרוב לגוף", 0.16, wing_joint, "זהב", group,
               scale=(1.45, 0.62, 0.70))

        for east_west in (-1, 1):
            feather_specs = (
                (0.58, 0.30, -0.28, 0.105),
                (0.49, 0.44, -0.08, 0.115),
                (0.36, 0.56, 0.00, 0.120),
                (0.22, 0.62, -0.18, 0.110),
            )
            for feather_index, (dx, dy, dz, feather_width) in enumerate(
                    feather_specs, 1):
                fraction = (feather_index - 1) / (len(feather_specs) - 1)
                feather_root = (
                    x + east_west * (0.08 + 0.03 * fraction),
                    cy + inward * (0.22 + 0.02 * fraction),
                    2.20 + 0.07 * fraction,
                )
                feather_tip = (
                    x + east_west * dx,
                    cy + inward * dy,
                    spread_wing_height + dz,
                )
                ellipsoid_between(f"נוצת כנף כרוב מעוגלת {feather_index}",
                                  feather_root, feather_tip, feather_width,
                                  0.050, "זהב", group)

    pole_half = INTERPRETED["ark_pole_length"] / 2
    pole_z = 0.56
    for pole_y in (-1.38, 1.38):
        rod("בד הארון – עשר אמות לפי המלבי״ם",
            (x - pole_half, pole_y, pole_z),
            (x + pole_half, pole_y, pole_z), 0.075, "זהב", group)
        for ring_x in (x - 0.66, x + 0.66):
            torus("טבעת הארון", 0.16, 0.038, (ring_x, pole_y, pole_z),
                  "זהב", group, rotation=(0, math.pi / 2, 0))


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
                "זהב", group, 0.018)

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
    # The silhouette and ornamental rhythm follow the Temple Institute's
    # full-size reconstruction: a broad polygonal stepped base, rounded U
    # branches, and repeated almond-like cups, knobs and flowers below each
    # oil lamp.  The Torah gives no total height for the Tabernacle menorah;
    # the existing three-cubit display height remains an explicit assumption.
    cylinder("מדרגת בסיס תחתונה", 0.64, 0.10, (x, y, 0.05), "זהב", group, 6)
    cylinder("מדרגת בסיס אמצעית", 0.55, 0.10, (x, y, 0.15), "זהב", group, 6)
    cylinder("בסיס מעוטר", 0.47, 0.18, (x, y, 0.29), "זהב", group, 6)
    cylinder("שפת בסיס עליונה", 0.50, 0.05, (x, y, 0.405), "זהב", group, 6)
    frustum("רגל המנורה המדורגת", 0.27, 0.15, 0.30,
            (x, y, 0.58), "זהב", group, 32)
    torus("חישוק רגל המנורה", 0.15, 0.028, (x, y, 0.74), "זהב", group)
    rod("קנה מרכזי", (x, y, 0.70), (x, y, 2.38), 0.072, "זהב", group)

    branch_specs = (
        (1.05, 1.55),  # the widest pair leaves the stem lowest
        (1.39, 1.08),
        (1.73, 0.59),
    )
    lamp_xs = [x]
    for pair_index, (join_z, spread) in enumerate(branch_specs, 1):
        sphere(f"כפתור זוג קנים {pair_index}", 0.13, (x, y, join_z),
               "זהב", group, scale=(1.05, 1.05, 0.78))
        torus(f"חישוק זוג קנים {pair_index}", 0.12, 0.022,
              (x, y, join_z + 0.09), "זהב", group)
        for side in (-1, 1):
            lamp_x = x + side * spread
            curved_rod(f"קנה המנורה {pair_index}-{side:+d}",
                       (x, y, join_z), (lamp_x, y, 2.38),
                       0.064, "זהב", group)
            lamp_xs.append(lamp_x)

    # A flower above the base and the paired-branch knobs articulate the
    # central shaft in the same tiered manner visible in the reconstruction.
    sphere("פרח תחתון בקנה המרכזי", 0.16, (x, y, 0.86), "זהב", group,
           scale=(1.30, 1.30, 0.42))
    torus("חישוק הפרח התחתון", 0.14, 0.025, (x, y, 0.91), "זהב", group)

    for lamp_index, lamp_x in enumerate(sorted(lamp_xs), 1):
        # Three flared cups separated by rounded flowers form the prominent
        # upper ornament seen beneath every lamp in the reference photograph.
        sphere(f"כפתור קנה {lamp_index}", 0.12, (lamp_x, y, 2.39),
               "זהב", group, scale=(1.10, 1.10, 0.70))
        frustum(f"גביע תחתון {lamp_index}", 0.09, 0.15, 0.12,
                (lamp_x, y, 2.49), "זהב", group, 24)
        torus(f"שפת גביע תחתון {lamp_index}", 0.145, 0.018,
              (lamp_x, y, 2.55), "זהב", group)
        sphere(f"פרח אמצעי {lamp_index}", 0.145, (lamp_x, y, 2.62),
               "זהב", group, scale=(1.22, 1.22, 0.42))
        frustum(f"גביע אמצעי {lamp_index}", 0.09, 0.15, 0.12,
                (lamp_x, y, 2.72), "זהב", group, 24)
        torus(f"שפת גביע אמצעי {lamp_index}", 0.145, 0.018,
              (lamp_x, y, 2.78), "זהב", group)
        sphere(f"פרח עליון {lamp_index}", 0.14, (lamp_x, y, 2.84),
               "זהב", group, scale=(1.20, 1.20, 0.40))

        # The lamps are shallow, elongated oil bowls rather than candles.
        sphere(f"קערת נר {lamp_index}", 0.17, (lamp_x, y, 2.93), "זהב", group,
               scale=(1.24, 0.84, 0.32))
        rim = torus(f"שפת נר {lamp_index}", 0.155, 0.018,
                    (lamp_x, y, 2.955), "זהב", group)
        rim.scale = (1.24, 0.84, 1.0)
        cylinder(f"פתילת נר {lamp_index}", 0.023, 0.09,
                 (lamp_x, y, 3.01), "כהה", group, 16)
        sphere(f"להבת נר {lamp_index}", 0.075, (lamp_x, y, 3.13),
               "להבה", group, scale=(0.62, 0.62, 1.65))


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


def setup_scene(interior: bool, covered: bool = False) -> None:
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
    if covered:
        camera_location = (m(-32), m(52), m(32))
        camera_target = Vector((m(12), 0, m(4)))
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
        "tabernacle_covered_preview.png" if covered else
        "tabernacle_interior_preview.png" if interior else "tabernacle_preview.png"
    )
    scene["model_title"] = (
        "Wilderness Tabernacle covered tent" if covered else
        "Wilderness Tabernacle cutaway" if interior
        else "Wilderness Tabernacle and courtyard"
    )
    scene["primary_sources"] = "Exodus 25-30, 35-40"
    scene["interpretation"] = "Rabbinic/traditional reconstruction"
    scene["cubit_meters"] = CUBIT_M
    scene["accuracy_note"] = (
        "SOURCE values are textual or traditional dimensions. ASSUMED values "
        "are schematic educational completions shown in the estimated material "
        "colour of each object."
    )


def build(interior: bool = False, covered: bool = False) -> None:
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
        if covered:
            add_outer_structure()
        else:
            add_open_tabernacle_in_courtyard()
    setup_scene(interior, covered)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(add_help=False)
    variant = parser.add_mutually_exclusive_group()
    variant.add_argument("--interior", action="store_true")
    variant.add_argument("--covered", action="store_true")
    parser.add_argument("--save", default="")
    parser.add_argument("--export", default="")
    parser.add_argument("--render", action="store_true")
    parser.add_argument("--preview-layer", type=int, choices=(1, 2, 3, 4), default=4)
    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    return parser.parse_args(args)


def finish(args: argparse.Namespace) -> None:
    if args.render:
        hidden = []
        if args.covered:
            for layer in range(args.preview_layer+1, 5):
                group = COLLECTIONS[f"03.{layer} כיסוי"]
                group.hide_render = True
                hidden.append(group)
        try:
            bpy.ops.render.render(write_still=True)
        finally:
            for group in hidden:
                group.hide_render = False
    if args.save:
        bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(args.save))
    if args.export:
        bpy.ops.export_scene.gltf(filepath=os.path.abspath(args.export), export_format="GLB",
                                  export_extras=True)


if __name__ == "__main__":
    parsed = parse_args()
    build(parsed.interior, parsed.covered)
    finish(parsed)
