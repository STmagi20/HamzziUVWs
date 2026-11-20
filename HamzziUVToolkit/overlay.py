# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 StudyingHamzzi

"""Connected-edge display in the UV editor (like the blue shared edges in 3ds Max)."""

import traceback

import blf
import bmesh
import bpy
import gpu
from gpu_extras.batch import batch_for_shader
from mathutils import Vector
from mathutils.geometry import tessellate_polygon

from .core import EPS, UVObject, edit_objects


_handle = None
_error_logged = False


def _uv_select_mode(ts):
    if ts.use_uv_select_sync:
        m = ts.mesh_select_mode
        return 'VERTEX' if m[0] else 'EDGE' if m[1] else 'FACE'
    return ts.uv_select_mode


def link_geometry(context, limit):
    """UV positions of the elements that share mesh geometry with the selection
    but sit somewhere else in UV space (the other side of a seam).

    Returns (lines, points) as flat lists of (u, v), or None over the face limit.
    Vertex select mode gives points, every other mode gives edges."""
    ts = context.tool_settings
    vert_mode = _uv_select_mode(ts) == 'VERTEX'
    m = ts.mesh_select_mode
    face_mode = bool(m[2]) and not m[0] and not m[1]
    objs = []
    total = 0
    for ob in edit_objects(context):
        bm = bmesh.from_edit_mesh(ob.data)
        if bm.loops.layers.uv.active is None:
            continue
        total += len(bm.faces)
        if total > limit:
            return None
        objs.append(UVObject(ob, ts.use_uv_select_sync, face_mode))

    lines, points = [], []
    for o in objs:
        uv, sel, vis = o.uv, o.selected, o.visible
        for f in o.bm.faces:
            if not vis(f):
                continue
            for l in f.loops:
                if not sel(l):
                    continue
                p = l[uv].uv
                if vert_mode:
                    for ol in l.vert.link_loops:
                        if ol is l or sel(ol) or not vis(ol.face):
                            continue
                        q = ol[uv].uv
                        if (q - p).length > EPS:
                            points.append((q.x, q.y))
                    continue
                n = l.link_loop_next
                if not sel(n):
                    continue
                pn = n[uv].uv
                for ol in l.edge.link_loops:
                    if ol.face is f or not vis(ol.face):
                        continue
                    on = ol.link_loop_next
                    if sel(ol) and sel(on):
                        continue
                    a, b = ol[uv].uv, on[uv].uv
                    if ol.vert is not l.vert:
                        a, b = b, a
                    if (a - p).length > EPS or (b - pn).length > EPS:
                        lines.append((a.x, a.y))
                        lines.append((b.x, b.y))
    return lines, points


def flipped_geometry(context, limit):
    """Triangles (flat list of (u, v), three per triangle) that cover the faces mirrored in
    UV space. Returns None over the face limit."""
    ts = context.tool_settings
    m = ts.mesh_select_mode
    face_mode = bool(m[2]) and not m[0] and not m[1]
    objs = []
    total = 0
    for ob in edit_objects(context):
        bm = bmesh.from_edit_mesh(ob.data)
        if bm.loops.layers.uv.active is None:
            continue
        total += len(bm.faces)
        if total > limit:
            return None
        objs.append(UVObject(ob, ts.use_uv_select_sync, face_mode))

    tris = []
    for o in objs:
        uv = o.uv
        for f in o.flipped_faces():
            p = [l[uv].uv.copy() for l in f.loops]
            if len(p) <= 4:                  # triangles and quads: a fan is exact for convex faces
                for i in range(1, len(p) - 1):
                    tris += [(p[0].x, p[0].y), (p[i].x, p[i].y), (p[i + 1].x, p[i + 1].y)]
            else:                            # n-gons may be concave: let Blender split them
                poly = [Vector((q.x, q.y, 0.0)) for q in p]
                for a, b, c in tessellate_polygon([poly]):
                    tris += [(p[a].x, p[a].y), (p[b].x, p[b].y), (p[c].x, p[c].y)]
    return tris


def draw_fill(region, tris, color):
    """Fill UV-space triangles in a UV editor region (POST_PIXEL)."""
    to_px = region.view2d.view_to_region
    pos = [to_px(u, v, clip=False) for u, v in tris]
    gpu.state.blend_set('ALPHA')
    sh = gpu.shader.from_builtin('UNIFORM_COLOR')
    batch = batch_for_shader(sh, 'TRIS', {"pos": pos})
    sh.bind()
    sh.uniform_float("color", color)
    batch.draw(sh)
    gpu.state.blend_set('NONE')


def draw_link_batches(region, lines, points, color, width):
    """Draw UV-space lines / points in a UV editor region (POST_PIXEL)."""
    to_px = region.view2d.view_to_region
    gpu.state.blend_set('ALPHA')
    if lines:
        pos = [to_px(u, v, clip=False) + (0.0,) for u, v in lines]
        sh = gpu.shader.from_builtin('POLYLINE_UNIFORM_COLOR')
        batch = batch_for_shader(sh, 'LINES', {"pos": pos})
        sh.bind()
        sh.uniform_float("viewportSize", (region.width, region.height))
        sh.uniform_float("lineWidth", width)
        sh.uniform_float("color", color)
        batch.draw(sh)
    if points:
        r = width + 2.0
        pos = []
        for u, v in points:
            x, y = to_px(u, v, clip=False)
            pos += [(x - r, y - r), (x + r, y - r), (x + r, y + r),
                    (x - r, y - r), (x + r, y + r), (x - r, y + r)]
        sh = gpu.shader.from_builtin('UNIFORM_COLOR')
        batch = batch_for_shader(sh, 'TRIS', {"pos": pos})
        sh.bind()
        sh.uniform_float("color", color)
        batch.draw(sh)
    gpu.state.blend_set('NONE')


def draw_notice(region, lines):
    """Lines of text in the top left corner of a UV editor region (POST_PIXEL), to the right
    of the tool shelf."""
    font = 0
    blf.size(font, 13.0)
    blf.color(font, 1.0, 0.75, 0.25, 1.0)
    for n, text in enumerate(lines):
        blf.position(font, 80.0, region.height - 24.0 - 18.0 * n, 0.0)
        blf.draw(font, text)


def _draw():
    global _error_logged
    context = bpy.context
    try:
        if context.mode != 'EDIT_MESH':
            return
        # While a modal tool (move, rotate, scale ...) is running, the edit mesh is
        # being rewritten on every mouse move. Reading it here would slow the drag
        # down and could touch data that is changing, so draw nothing until it ends.
        if context.window is not None and len(context.window.modal_operators):
            return
        s = context.scene.uved
        sp = context.space_data
        if sp is None or sp.type != 'IMAGE_EDITOR' or not sp.show_uvedit:
            return
        skipped = []
        if s.show_flipped:
            tris = flipped_geometry(context, s.link_limit)
            if tris is None:
                skipped.append("Flipped Faces")
            elif tris:
                draw_fill(context.region, tris, tuple(s.flipped_color))
        if s.show_links:
            geo = link_geometry(context, s.link_limit)
            if geo is None:
                skipped.append("Connected Edges")
            elif geo[0] or geo[1]:
                draw_link_batches(context.region, geo[0], geo[1], tuple(s.link_color), s.link_width)
        if skipped:
            draw_notice(context.region, (
                f"Hamzzi UV Toolkit: {', '.join(skipped)} not shown",
                f"More than {s.link_limit} faces - raise Face Limit in the Connected Edges panel"))
    except Exception:       # a draw callback must never raise
        if not _error_logged:
            # print the first failure to the system console so it can be found;
            # later ones are dropped, the callback runs on every redraw
            _error_logged = True
            traceback.print_exc()


def register():
    global _handle
    if _handle is None:
        _handle = bpy.types.SpaceImageEditor.draw_handler_add(_draw, (), 'WINDOW', 'POST_PIXEL')


def unregister():
    global _handle
    if _handle is not None:
        bpy.types.SpaceImageEditor.draw_handler_remove(_handle, 'WINDOW')
        _handle = None
