"""Shared setup for the tests: load the add-on and build small UV-mapped test meshes.

Every test starts from an empty scene (`fresh`). Read scene settings through
`bpy.context` each time; a reference taken before a factory reset points at freed
memory and can crash Blender."""

import math
import os
import sys

import bmesh
import bpy

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import HamzziUVToolkit as addon                       # noqa: E402
from HamzziUVToolkit import core                      # noqa: E402

if not hasattr(bpy.types.Scene, "uved"):
    addon.register()

CORNERS = ((0, 0), (1, 0), (1, 1), (0, 1))


def fresh():
    """Empty scene, back in Object Mode, with the add-on still registered."""
    bpy.ops.wm.read_factory_settings(use_empty=True)
    if not hasattr(bpy.types.Scene, "uved"):
        addon.register()


def settings():
    return bpy.context.scene.uved


def tool_settings():
    return bpy.context.tool_settings


def link(ob):
    bpy.context.collection.objects.link(ob)
    return ob


def quads_object(items, name="obj", location=(0, 0, 0)):
    """One quad per item. items: [((x, y, z) 3D corner, (u, v, width, height) in UV)].
    Every quad is its own UV island."""
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    uv = bm.loops.layers.uv.new("UVMap")
    for (px, py, pz), (ux, uy, w, h) in items:
        vs = [bm.verts.new((px + a * 0.5, py + b * 0.5, pz)) for a, b in CORNERS]
        f = bm.faces.new(vs)
        for l, (a, b) in zip(f.loops, CORNERS):
            l[uv].uv = (ux + a * w, uy + b * h)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    ob.location = location
    return link(ob)


def polygon_object(uv_points, name="poly"):
    """A single face whose UV corners are `uv_points`."""
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    uv = bm.loops.layers.uv.new("UVMap")
    n = len(uv_points)
    verts = [bm.verts.new((math.cos(2 * math.pi * i / n), math.sin(2 * math.pi * i / n), 0.0))
             for i in range(n)]
    f = bm.faces.new(verts)
    for l, p in zip(f.loops, uv_points):
        l[uv].uv = p
    bm.to_mesh(me)
    bm.free()
    return link(bpy.data.objects.new(name, me))


def plane_object(width=1.0, height=1.0, uv_size=(0.5, 0.5), scale=(1, 1, 1), rotation_z=0.0,
                 name="plane"):
    """A width x height plane mapped to a uv_size rectangle at the UV origin."""
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    uv = bm.loops.layers.uv.new("UVMap")
    vs = [bm.verts.new((a * width, b * height, 0.0)) for a, b in CORNERS]
    f = bm.faces.new(vs)
    for l, (a, b) in zip(f.loops, CORNERS):
        l[uv].uv = (a * uv_size[0], b * uv_size[1])
    bm.to_mesh(me)
    bm.free()
    ob = link(bpy.data.objects.new(name, me))
    ob.scale = scale
    ob.rotation_euler = (0.0, 0.0, rotation_z)
    bpy.context.view_layer.update()
    return ob


def enter_edit(obs, sync=True, select_mode='VERT'):
    """Make `obs` the objects in Edit Mode with everything selected."""
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    bpy.context.view_layer.objects.active = obs[0]
    for o in obs:
        o.select_set(True)
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.context.tool_settings.use_uv_select_sync = sync
    bpy.ops.mesh.select_mode(type=select_mode)
    bpy.ops.mesh.select_all(action='SELECT')


def leave_edit():
    if bpy.context.object is not None and bpy.context.object.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')


def islands():
    return [i for o in core.gather(bpy.context) for i in o.islands()]


def face_indices(ob, attr="select"):
    bm = bmesh.from_edit_mesh(ob.data)
    return sorted(f.index for f in bm.faces if getattr(f, attr))
