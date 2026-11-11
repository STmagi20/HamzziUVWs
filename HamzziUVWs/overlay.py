# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 StudyingHamzzi

"""Connected-edge display in the UV editor (like the blue shared edges in 3ds Max)."""

import traceback

import bmesh
import bpy
import gpu
from gpu_extras.batch import batch_for_shader

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
        if not s.show_links or sp is None or sp.type != 'IMAGE_EDITOR' or not sp.show_uvedit:
            return
        geo = link_geometry(context, s.link_limit)
        if not geo or not (geo[0] or geo[1]):
            return
        draw_link_batches(context.region, geo[0], geo[1], tuple(s.link_color), s.link_width)
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
