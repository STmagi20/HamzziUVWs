# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 StudyingHamzzi

"""UV editor displays: connected edges (like the blue shared edges in 3ds Max) and
flipped faces."""

import traceback

import blf
import bmesh
import bpy
import gpu
from gpu_extras.batch import batch_for_shader
from mathutils import Vector
from mathutils.geometry import tessellate_polygon

from .core import EPS, gather


_handle = None
_error_logged = False


def _uv_select_mode(ts):
    if ts.use_uv_select_sync:
        m = ts.mesh_select_mode
        return 'VERTEX' if m[0] else 'EDGE' if m[1] else 'FACE'
    return ts.uv_select_mode


def uv_objects(context, limit):
    """The edit meshes that have a UV map, or None when together they have more faces
    than `limit` (the displays are skipped then, to keep the UV editor responsive)."""
    objs = gather(context)
    if sum(len(o.bm.faces) for o in objs) > limit:
        return None
    return objs


def link_geometry(context, limit, objs=None):
    """UV positions of the elements that share mesh geometry with the selection
    but sit somewhere else in UV space (the other side of a seam).

    Returns (lines, points) as flat lists of (u, v), or None over the face limit.
    Vertex select mode gives points, every other mode gives edges. `objs` (from
    uv_objects) skips looking them up again; the limit is not checked then."""
    if objs is None:
        objs = uv_objects(context, limit)
        if objs is None:
            return None
    vert_mode = _uv_select_mode(context.tool_settings) == 'VERTEX'
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


def flipped_geometry(context, limit, objs=None):
    """Triangles (flat list of (u, v), three per triangle) that cover the faces mirrored in
    UV space. Returns None over the face limit. `objs` as in link_geometry."""
    if objs is None:
        objs = uv_objects(context, limit)
        if objs is None:
            return None
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


# ---------------------------------------------------------------------------------------
# Cache. Working out the displays reads the whole mesh: about 130 ms per redraw with both
# on, on a 10,000-face mesh, and the UV editor redraws on every pan, zoom and mouse move.
# Blender does not reliably say when the edit mesh changed (4.x sends no update at all
# for a UV move or a UV-only selection), so every redraw takes a fingerprint of what the
# displays read, which is about four times cheaper, and works them out again only when
# it differs. The results are kept as GPU batches in UV units, so a pan or zoom only
# changes the matrix they are drawn with.

_UV_SELECT_5X = hasattr(bmesh.types.BMLoop, "uv_select_vert")
_cache = {"key": None}


def _fingerprint(o):
    """Hash of what the displays read from one object: vertex positions and selection,
    face selection, visibility and loop order, UV positions and UV selection."""
    bm, uv = o.bm, o.uv
    data = [o.ob.name, o.ob.data.as_pointer(), o.ob.matrix_world.determinant() >= 0,
            o.uv_sync, len(bm.verts), len(bm.edges)]
    for v in bm.verts:
        data += v.co[:]
        data.append(v.select)
    for f in bm.faces:
        data.append(f.select)
        data.append(f.hide)
        data.append(len(f.loops))
        for l in f.loops:
            data += l[uv].uv[:]
            data.append(l.uv_select_vert if _UV_SELECT_5X else l[uv].select)
    return hash(tuple(data))


def state_key(context, objs):
    """Changes whenever the result of either display could change."""
    ts = context.tool_settings
    return (ts.use_uv_select_sync, tuple(ts.mesh_select_mode), ts.uv_select_mode,
            tuple(_fingerprint(o) for o in objs))


def cached(name, key, compute):
    """compute() once per state `key`; later calls with the same key return that result."""
    if _cache["key"] != key:
        _cache.clear()
        _cache["key"] = key
    if name not in _cache:
        _cache[name] = compute()
    return _cache[name]


def clear_cache():
    _cache.clear()
    _cache["key"] = None


def uv_to_pixels(view2d, width, height):
    """(offset, scale) that turn UV units into region pixels: px = offset + uv * scale."""
    u0, v0 = view2d.region_to_view(0.0, 0.0)
    u1, v1 = view2d.region_to_view(float(width), float(height))
    sx = width / (u1 - u0) if u1 != u0 else 1.0
    sy = height / (v1 - v0) if v1 != v0 else 1.0
    return (-u0 * sx, -v0 * sy), (sx, sy)


def _draw_in_uv_units(region, batch, shader):
    (ox, oy), (sx, sy) = uv_to_pixels(region.view2d, region.width, region.height)
    with gpu.matrix.push_pop():
        gpu.matrix.translate((ox, oy))
        gpu.matrix.scale((sx, sy))
        batch.draw(shader)


def fill_batch(tris):
    """GPU batch of UV-space triangles, or None when there are none."""
    if not tris:
        return None
    sh = gpu.shader.from_builtin('UNIFORM_COLOR')
    return batch_for_shader(sh, 'TRIS', {"pos": tris}), sh


def line_batch(lines):
    """GPU batch of UV-space line segments, or None when there are none."""
    if not lines:
        return None
    sh = gpu.shader.from_builtin('POLYLINE_UNIFORM_COLOR')
    return batch_for_shader(sh, 'LINES', {"pos": [(u, v, 0.0) for u, v in lines]}), sh


def draw_fill(region, fill, color):
    """Draw a fill_batch() in a UV editor region (POST_PIXEL)."""
    batch, sh = fill
    gpu.state.blend_set('ALPHA')
    sh.bind()
    sh.uniform_float("color", color)
    _draw_in_uv_units(region, batch, sh)
    gpu.state.blend_set('NONE')


def draw_links(region, lines, points, color, width):
    """Draw a line_batch() and points (UV positions, drawn as squares a few pixels wide)
    in a UV editor region (POST_PIXEL)."""
    gpu.state.blend_set('ALPHA')
    if lines is not None:
        batch, sh = lines
        sh.bind()
        sh.uniform_float("viewportSize", (region.width, region.height))
        sh.uniform_float("lineWidth", width)
        sh.uniform_float("color", color)
        _draw_in_uv_units(region, batch, sh)
    if points:
        to_px = region.view2d.view_to_region
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


def notice_origin(regions, region, scale):
    """Where the first notice line starts in `region`: clear of the tool shelf and the
    headers when they are drawn over the editor (Region Overlap). `regions` are the
    area's regions; anything with x, y, width, height and type works."""
    left = top = 0
    for r in regions:
        if r.type not in {'TOOLS', 'HEADER', 'TOOL_HEADER'} or r.width <= 1 or r.height <= 1:
            continue
        if not (r.x < region.x + region.width and r.x + r.width > region.x
                and r.y < region.y + region.height and r.y + r.height > region.y):
            continue                        # beside the editor, not over it
        if r.type == 'TOOLS':
            left = max(left, r.x + r.width - region.x)
        else:
            top = max(top, region.y + region.height - r.y)
    return left + 12.0 * scale, region.height - top - 20.0 * scale


def draw_notice(context, lines):
    """Lines of text in the top left corner of a UV editor region (POST_PIXEL)."""
    scale = context.preferences.system.ui_scale
    x, y = notice_origin(context.area.regions, context.region, scale)
    font = 0
    blf.size(font, 13.0 * scale)
    blf.color(font, 1.0, 0.75, 0.25, 1.0)
    for n, text in enumerate(lines):
        blf.position(font, x, y - 18.0 * scale * n, 0.0)
        blf.draw(font, text)


def _links_for_drawing(context, objs):
    lines, points = link_geometry(context, 0, objs)
    return line_batch(lines), points


def _draw_displays(context, s, objs):
    key = state_key(context, objs)
    region = context.region
    if s.show_flipped:
        fill = cached("flipped", key, lambda: fill_batch(flipped_geometry(context, 0, objs)))
        if fill is not None:
            draw_fill(region, fill, tuple(s.flipped_color))
    if s.show_links:
        lines, points = cached("links", key, lambda: _links_for_drawing(context, objs))
        if lines is not None or points:
            draw_links(region, lines, points, tuple(s.link_color), s.link_width)


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
        if not (s.show_flipped or s.show_links):
            return
        objs = uv_objects(context, s.link_limit)
        if objs is not None:
            _draw_displays(context, s, objs)
            return
        skipped = [name for on, name in ((s.show_flipped, "Flipped Faces"),
                                         (s.show_links, "Connected Edges")) if on]
        draw_notice(context, (
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
    clear_cache()
    if _handle is not None:
        bpy.types.SpaceImageEditor.draw_handler_remove(_handle, 'WINDOW')
        _handle = None
