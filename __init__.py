# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 StudyingHamzzi

"""UV Edit Toolkit - edit UVs that are already unwrapped.

Island tools : align, distribute, move to tile, texel density, scale,
               rotate / flip, auto-orient, orient to edge.
Element tools: align / distribute selected UV vertices (straighten edges).
Stitch       : Stitch Selected - join selected UV edges to their neighbour
               islands (bias / align / scale options, like 3ds Max Unwrap UVW).
Unstretch    : relax selected UVs (pinned re-solve) and toggle the stretch overlay.
Connected    : in the UV editor, shows where the selected UV edges / faces / vertices
               continue on other islands (like the blue edges in 3ds Max).

Works in the UV Editor and the 3D Viewport (Edit Mode), with UV sync on or off,
and on several objects in Edit Mode at once. If nothing is selected, every
visible island is used.
"""

import math

import bmesh
import bpy
import gpu
import numpy as np
from bpy.props import (
    BoolProperty, EnumProperty, FloatProperty, FloatVectorProperty, IntProperty,
    PointerProperty, StringProperty,
)
from gpu_extras.batch import batch_for_shader
from bpy.types import Operator, Panel, PropertyGroup

EPS = 1e-5

ADDON_NAME = "UV Edit Toolkit"
ADDON_AUTHOR = "StudyingHamzzi"
# shown at the bottom of the sidebar tab; rewrite for every release
UPDATE_NOTES = (
    "패널을 접을 수 있는 섹션으로 분리",
    "연결 엣지 표시 (점 · 선 · 면)",
    "텍셀 밀도 UI 정리",
    "UV Sync의 UV별 선택 지원",
    "상단 이름 · 하단 업데이트 표시",
)


def _read_version():
    """Version from blender_manifest.toml, so it is written in one place only."""
    import os
    import re
    try:
        path = os.path.join(os.path.dirname(__file__), "blender_manifest.toml")
        with open(path, encoding="utf-8") as fh:
            m = re.search(r'^version\s*=\s*"([^"]+)"', fh.read(), re.M)
        return m.group(1) if m else "?"
    except OSError:
        return "?"


ADDON_VERSION = _read_version()


# --------------------------------------------------------------------------
# Data access
# --------------------------------------------------------------------------

def _edit_objects(context):
    # objects_in_mode_unique_type is missing in some editors (UV editor)
    return [o for o in context.view_layer.objects
            if o.type == 'MESH' and o.mode == 'EDIT']


def _edge_uvs(face, edge, uv):
    for l in face.loops:
        if l.edge == edge:
            n = l.link_loop_next
            return {l.vert: l[uv].uv.copy(), n.vert: n[uv].uv.copy()}
    return {}


class _Obj:
    def __init__(self, ob, sync, face_mode):
        self.ob = ob
        self.bm = bmesh.from_edit_mesh(ob.data)
        self.uv = self.bm.loops.layers.uv.active or self.bm.loops.layers.uv.verify()
        self.sync = sync
        self.face_mode = face_mode
        # Blender 5.x keeps a separate per-UV selection even with UV sync on
        # (clicking a UV vertex selects only that UV, not its copies on other
        # islands). When it is valid it is what the UV editor shows.
        self.uv_sync = bool(sync and getattr(self.bm, "uv_select_sync_valid", False))

    def visible(self, f):
        return (not f.hide) and (self.sync or f.select)

    def selected(self, l):
        if self.sync and not self.uv_sync:
            return l.vert.select and (l.face.select or not self.face_mode)
        try:
            return l.uv_select_vert          # Blender 5.x
        except AttributeError:
            return l[self.uv].select         # Blender 4.x

    def update(self):
        bmesh.update_edit_mesh(self.ob.data, loop_triangles=False, destructive=False)

    def islands(self):
        uv = self.uv
        faces = [f for f in self.bm.faces if self.visible(f)]
        idx = {f: i for i, f in enumerate(faces)}
        parent = list(range(len(faces)))

        def find(i):
            while parent[i] != i:
                parent[i] = parent[parent[i]]
                i = parent[i]
            return i

        joined = []
        for e in self.bm.edges:
            lf = [f for f in e.link_faces if f in idx]
            if len(lf) < 2:
                continue
            base = _edge_uvs(lf[0], e, uv)
            for f in lf[1:]:
                other = _edge_uvs(f, e, uv)
                if base and all((base[v] - other[v]).length < EPS for v in base):
                    joined.append((e, lf[0]))
                    a, b = find(idx[lf[0]]), find(idx[f])
                    if a != b:
                        parent[a] = b
        groups = {}
        for i, f in enumerate(faces):
            groups.setdefault(find(i), []).append(f)
        edges = {}
        for e, f in joined:
            edges.setdefault(find(idx[f]), []).append(e)
        return [Island(self, g, edges.get(r, [])) for r, g in groups.items()]


class Island:
    def __init__(self, obj, faces, joined=()):
        self.obj = obj
        self.faces = faces
        self.joined = list(joined)   # mesh edges whose two sides are joined in UV space
        self.loops = [l for f in faces for l in f.loops]

    def pts(self):
        uv = self.obj.uv
        return np.array([tuple(l[uv].uv) for l in self.loops], dtype=float)

    def bounds(self):
        p = self.pts()
        return p[:, 0].min(), p[:, 1].min(), p[:, 0].max(), p[:, 1].max()

    def center(self):
        x0, y0, x1, y1 = self.bounds()
        return (x0 + x1) / 2, (y0 + y1) / 2

    def selected(self):
        return any(self.obj.selected(l) for l in self.loops)

    def apply(self, fn):
        uv = self.obj.uv
        for l in self.loops:
            x, y = fn(l[uv].uv.x, l[uv].uv.y)
            l[uv].uv = (x, y)

    def translate(self, dx, dy):
        self.apply(lambda x, y: (x + dx, y + dy))

    def scale(self, sx, sy, cx, cy):
        self.apply(lambda x, y: (cx + (x - cx) * sx, cy + (y - cy) * sy))

    def rotate(self, ang, cx, cy):
        c, s = math.cos(ang), math.sin(ang)
        self.apply(lambda x, y: (cx + (x - cx) * c - (y - cy) * s,
                                 cy + (x - cx) * s + (y - cy) * c))

    def uv_area(self):
        uv = self.obj.uv
        total = 0.0
        for f in self.faces:
            p = [l[uv].uv for l in f.loops]
            total += abs(sum(p[i].x * p[(i + 1) % len(p)].y - p[(i + 1) % len(p)].x * p[i].y
                             for i in range(len(p)))) / 2
        return total

    def area3d(self):
        m = self.obj.ob.matrix_world.to_3x3()
        s = abs(m.determinant()) ** (1 / 3)
        return sum(f.calc_area() for f in self.faces) * s * s

    def density(self, size):
        a3, auv = self.area3d(), self.uv_area()
        return math.sqrt(auv / a3) * size if a3 > 1e-12 and auv > 1e-12 else 0.0


def _gather(context):
    ts = context.tool_settings
    m = ts.mesh_select_mode
    face_mode = bool(m[2]) and not m[0] and not m[1]
    return [_Obj(o, ts.use_uv_select_sync, face_mode) for o in _edit_objects(context)]


def _targets(context):
    objs = _gather(context)
    isl = [i for o in objs for i in o.islands()]
    sel = [i for i in isl if i.selected()]
    return objs, (sel or isl)


def _finish(objs):
    for o in objs:
        o.update()


def _group_bounds(islands):
    b = [i.bounds() for i in islands]
    return (min(x[0] for x in b), min(x[1] for x in b),
            max(x[2] for x in b), max(x[3] for x in b))


class _EditOp:
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'EDIT_MESH' and len(_edit_objects(context)) > 0


# --------------------------------------------------------------------------
# Settings
# --------------------------------------------------------------------------

def _redraw_uv_editors(self, context):
    for w in context.window_manager.windows:
        for a in w.screen.areas:
            if a.type == 'IMAGE_EDITOR':
                a.tag_redraw()


class UVED_Settings(PropertyGroup):
    show_links: BoolProperty(
        name="Show Connected Edges", default=True, update=_redraw_uv_editors,
        description="In the UV editor, highlight where the selected UV edges, faces or "
                    "vertices continue on another island (the other side of a seam)")
    link_color: FloatVectorProperty(
        name="Color", subtype='COLOR', size=4, min=0.0, max=1.0,
        default=(0.1, 0.45, 1.0, 1.0), update=_redraw_uv_editors)
    link_width: FloatProperty(
        name="Line Width", default=3.0, min=1.0, max=10.0, update=_redraw_uv_editors)
    link_limit: IntProperty(
        name="Face Limit", default=50000, min=100, soft_max=500000,
        description="Skip the display when more faces than this are in Edit Mode, "
                    "to keep the UV editor responsive")
    align_relative: EnumProperty(
        name="Align To", default='SELECTION',
        items=[('SELECTION', "Selection", "Bounds of the selected islands"),
               ('TILE', "UV Tile", "The 0-1 tile under the selection")])
    gap_mode: EnumProperty(
        name="Spacing", default='EQUAL',
        items=[('EQUAL', "Equal Gaps", "Even gaps between the outermost islands"),
               ('FIXED', "Fixed Gap", "Use the gap value below")])
    gap: FloatProperty(name="Gap", default=0.01, min=-1.0, max=1.0, precision=4)
    tile_u: IntProperty(name="U", default=0)
    tile_v: IntProperty(name="V", default=0)
    texture_size: IntProperty(
        name="Texture Size", default=1024, min=1, max=65536,
        description="Texture width in pixels. Only used to express density as px/m; "
                    "changing it does not move any UVs")
    target_density: FloatProperty(
        name="Target (px/m)", default=512.0, min=0.0, soft_max=8192.0,
        description="Texture pixels per metre of 3D surface. Measure fills this in")
    scale_u: FloatProperty(name="U", default=1.0, min=0.001, soft_max=10.0,
                           description="Multiply island width by this factor")
    scale_v: FloatProperty(name="V", default=1.0, min=0.001, soft_max=10.0,
                           description="Multiply island height by this factor")
    rot_angle: FloatProperty(name="Angle", default=math.radians(15.0), subtype='ANGLE')
    readout: StringProperty(name="Readout", default="")
    stretch_type: EnumProperty(
        name="Stretch", default='AREA',
        items=[('AREA', "Area", ""), ('ANGLE', "Angle", "")])
    relax_method: EnumProperty(
        name="Method", default='ANGLE_BASED',
        items=[('ANGLE_BASED', "Angle Based", "Preserves angles, good general choice"),
               ('CONFORMAL', "Conformal", "Preserves shape, may change scale")])
    relax_blend: FloatProperty(
        name="Amount", default=1.0, min=0.0, max=1.0,
        description="How far to move toward the relaxed result (1 = fully relaxed)")
    stitch_bias: FloatProperty(
        name="Bias", default=0.0, min=0.0, max=1.0,
        description="0 = the selected island stays and the neighbour moves, "
                    "1 = the neighbour stays and the selected island moves, "
                    "0.5 = both meet in the middle")
    stitch_align: BoolProperty(
        name="Align Clusters", default=True,
        description="Rotate the moving island so the edges line up")
    stitch_scale: BoolProperty(
        name="Scale Clusters", default=True,
        description="Scale the moving island so the edges have the same length")


# --------------------------------------------------------------------------
# Island operators
# --------------------------------------------------------------------------

class UVED_OT_align_islands(_EditOp, Operator):
    bl_idname = "uved.align_islands"
    bl_label = "Align Islands"
    bl_description = "Align the selected islands"

    mode: EnumProperty(items=[(k, k, "") for k in
                              ('LEFT', 'RIGHT', 'TOP', 'BOTTOM', 'CENTER_H', 'CENTER_V')])

    def execute(self, context):
        s = context.scene.uved
        objs, isl = _targets(context)
        if not isl:
            self.report({'WARNING'}, "No UV islands found")
            return {'CANCELLED'}
        x0, y0, x1, y1 = _group_bounds(isl)
        if s.align_relative == 'TILE':
            tx, ty = math.floor((x0 + x1) / 2), math.floor((y0 + y1) / 2)
            x0, y0, x1, y1 = tx, ty, tx + 1, ty + 1
        for i in isl:
            a, b, c, d = i.bounds()
            dx = dy = 0.0
            if self.mode == 'LEFT':
                dx = x0 - a
            elif self.mode == 'RIGHT':
                dx = x1 - c
            elif self.mode == 'BOTTOM':
                dy = y0 - b
            elif self.mode == 'TOP':
                dy = y1 - d
            elif self.mode == 'CENTER_H':
                dx = (x0 + x1) / 2 - (a + c) / 2
            elif self.mode == 'CENTER_V':
                dy = (y0 + y1) / 2 - (b + d) / 2
            i.translate(dx, dy)
        _finish(objs)
        return {'FINISHED'}


class UVED_OT_distribute_islands(_EditOp, Operator):
    bl_idname = "uved.distribute_islands"
    bl_label = "Distribute Islands"
    bl_description = "Space the selected islands evenly"

    axis: EnumProperty(items=[('U', "U", ""), ('V', "V", "")])

    def execute(self, context):
        s = context.scene.uved
        objs, isl = _targets(context)
        if len(isl) < 2:
            self.report({'WARNING'}, "Select at least two islands")
            return {'CANCELLED'}
        k = 0 if self.axis == 'U' else 1
        info = []
        for i in isl:
            b = i.bounds()
            info.append((b[k], b[k + 2], i))
        info.sort(key=lambda t: t[0])
        if s.gap_mode == 'EQUAL':
            span = max(t[1] for t in info) - info[0][0]
            gap = (span - sum(t[1] - t[0] for t in info)) / (len(info) - 1)
        else:
            gap = s.gap
        pos = info[0][0]
        for lo, hi, i in info:
            d = pos - lo
            i.translate(d, 0) if k == 0 else i.translate(0, d)
            pos += (hi - lo) + gap
        _finish(objs)
        return {'FINISHED'}


class UVED_OT_move_to_tile(_EditOp, Operator):
    bl_idname = "uved.move_to_tile"
    bl_label = "Move to Tile"
    bl_description = "Move each selected island into the given UDIM tile (keeps its position inside the tile)"

    def execute(self, context):
        s = context.scene.uved
        objs, isl = _targets(context)
        if not isl:
            return {'CANCELLED'}
        for i in isl:
            cx, cy = i.center()
            i.translate(s.tile_u - math.floor(cx), s.tile_v - math.floor(cy))
        _finish(objs)
        return {'FINISHED'}


class UVED_OT_get_density(_EditOp, Operator):
    bl_idname = "uved.get_density"
    bl_label = "Measure Density"
    bl_description = ("Measure the texel density of the selected islands and put the "
                      "average into Target (px/m). Does not change any UVs")

    def execute(self, context):
        s = context.scene.uved
        objs, isl = _targets(context)
        d = [i.density(s.texture_size) for i in isl]
        d = [x for x in d if x > 0]
        if not d:
            self.report({'WARNING'}, "No measurable islands")
            return {'CANCELLED'}
        avg = sum(d) / len(d)
        s.target_density = avg
        if max(d) - min(d) < 0.05:
            s.readout = f"Measured: {avg:.1f} px/m ({len(d)} islands, uniform)"
        else:
            s.readout = f"Measured: {min(d):.1f} - {max(d):.1f} px/m ({len(d)} islands)"
        self.report({'INFO'}, s.readout)
        return {'FINISHED'}


class UVED_OT_set_density(_EditOp, Operator):
    bl_idname = "uved.set_density"
    bl_label = "Set Texel Density"
    bl_description = ("Resize each selected island around its own center so its texel "
                      "density matches. Islands are not moved, so they may overlap")

    source: EnumProperty(
        name="Match To", default='VALUE',
        items=[('VALUE', "Target Value", "Use the Target (px/m) value"),
               ('AVERAGE', "Selection Average",
                "Make all selected islands the same density, keeping their overall size"),
               ('ACTIVE', "Active Face Island", "Copy the density of the active face's island")])

    @classmethod
    def description(cls, context, properties):
        return {
            'VALUE': "Resize each selected island so its density equals Target (px/m)",
            'AVERAGE': "Make all selected islands the same density (their average), "
                       "so the overall size stays about the same",
            'ACTIVE': "Resize the selected islands to the density of the island "
                      "that holds the active face",
        }[properties.source] + ". Islands are resized around their own center and may overlap"

    def execute(self, context):
        s = context.scene.uved
        objs, isl = _targets(context)
        dens = [(i, i.density(s.texture_size)) for i in isl]
        dens = [(i, d) for i, d in dens if d > 0]
        if not dens:
            self.report({'WARNING'}, "No measurable islands")
            return {'CANCELLED'}
        if self.source == 'VALUE':
            target = s.target_density
            if target <= 0:
                self.report({'WARNING'}, "Target (px/m) must be above zero")
                return {'CANCELLED'}
        elif self.source == 'AVERAGE':
            target = sum(d for _, d in dens) / len(dens)
        else:
            target = 0.0
            for o in objs:
                af = o.bm.faces.active
                if af is not None:
                    for i in o.islands():
                        if af in i.faces:
                            target = i.density(s.texture_size)
            if target <= 0:
                self.report({'WARNING'}, "No active face - select a face first")
                return {'CANCELLED'}
        for i, d in dens:
            k = target / d
            cx, cy = i.center()
            i.scale(k, k, cx, cy)
        s.readout = ""      # the last measurement no longer describes these UVs
        _finish(objs)
        self.report({'INFO'}, f"Set {len(dens)} island(s) to {target:.1f} px/m")
        return {'FINISHED'}


class UVED_OT_scale_islands(_EditOp, Operator):
    bl_idname = "uved.scale_islands"
    bl_label = "Scale Islands"
    bl_description = "Scale each selected island around its own center"

    def execute(self, context):
        s = context.scene.uved
        objs, isl = _targets(context)
        for i in isl:
            cx, cy = i.center()
            i.scale(s.scale_u, s.scale_v, cx, cy)
        _finish(objs)
        return {'FINISHED'}


class UVED_OT_transform_islands(_EditOp, Operator):
    bl_idname = "uved.transform_islands"
    bl_label = "Rotate / Flip Islands"
    bl_description = "Rotate or flip each selected island around its own center"

    mode: EnumProperty(items=[(k, k, "") for k in
                              ('CW90', 'CCW90', 'ROT180', 'ANGLE', 'FLIP_H', 'FLIP_V')])

    def execute(self, context):
        s = context.scene.uved
        objs, isl = _targets(context)
        for i in isl:
            cx, cy = i.center()
            if self.mode == 'CW90':
                i.rotate(-math.pi / 2, cx, cy)
            elif self.mode == 'CCW90':
                i.rotate(math.pi / 2, cx, cy)
            elif self.mode == 'ROT180':
                i.rotate(math.pi, cx, cy)
            elif self.mode == 'ANGLE':
                i.rotate(s.rot_angle, cx, cy)
            elif self.mode == 'FLIP_H':
                i.scale(-1, 1, cx, cy)
            elif self.mode == 'FLIP_V':
                i.scale(1, -1, cx, cy)
        _finish(objs)
        return {'FINISHED'}


class UVED_OT_auto_orient(_EditOp, Operator):
    bl_idname = "uved.auto_orient"
    bl_label = "Auto Orient"
    bl_description = "Rotate each island to its minimum-area bounding box"

    target: EnumProperty(
        name="Longest Side", default='ANY',
        items=[('ANY', "Keep", "Only minimise the box"),
               ('HORIZONTAL', "Horizontal", "Longest side along U"),
               ('VERTICAL', "Vertical", "Longest side along V")])

    def execute(self, context):
        objs, isl = _targets(context)
        angles = np.radians(np.arange(0.0, 90.0, 0.5))
        for i in isl:
            p = i.pts()
            cx, cy = i.center()
            p = np.unique(np.round(p, 6), axis=0) - (cx, cy)
            best, best_a = None, 0.0
            for a in angles:
                c, s = math.cos(a), math.sin(a)
                x = p[:, 0] * c - p[:, 1] * s
                y = p[:, 0] * s + p[:, 1] * c
                area = (x.max() - x.min()) * (y.max() - y.min())
                if best is None or area < best - 1e-12:
                    best, best_a = area, a
            i.rotate(best_a, cx, cy)
            x0, y0, x1, y1 = i.bounds()
            w, h = x1 - x0, y1 - y0
            if (self.target == 'HORIZONTAL' and h > w) or (self.target == 'VERTICAL' and w > h):
                i.rotate(math.pi / 2, cx, cy)
        _finish(objs)
        return {'FINISHED'}


class UVED_OT_orient_to_edge(_EditOp, Operator):
    bl_idname = "uved.orient_to_edge"
    bl_label = "Orient to Edge"
    bl_description = "Rotate each island so its selected UV edge lies on the nearest axis"

    def execute(self, context):
        objs, isl = _targets(context)
        done = 0
        for i in isl:
            uv = i.obj.uv
            for l in i.loops:
                n = l.link_loop_next
                if i.obj.selected(l) and i.obj.selected(n):
                    d = n[uv].uv - l[uv].uv
                    if d.length < EPS:
                        continue
                    a = math.atan2(d.y, d.x)
                    rot = -(a - round(a / (math.pi / 2)) * (math.pi / 2))
                    cx, cy = i.center()
                    i.rotate(rot, cx, cy)
                    done += 1
                    break
        if not done:
            self.report({'WARNING'}, "Select a UV edge inside the island")
            return {'CANCELLED'}
        _finish(objs)
        return {'FINISHED'}


# --------------------------------------------------------------------------
# Element operators (selected UV vertices)
# --------------------------------------------------------------------------

def _selected_loops(context):
    objs = _gather(context)
    out = []
    for o in objs:
        for f in o.bm.faces:
            if not o.visible(f):
                continue
            for l in f.loops:
                if o.selected(l):
                    out.append((o, l))
    return objs, out


class UVED_OT_align_elements(_EditOp, Operator):
    bl_idname = "uved.align_elements"
    bl_label = "Align UV Vertices"
    bl_description = "Align the selected UV vertices (use average to straighten edges)"

    mode: EnumProperty(items=[(k, k, "") for k in
                              ('U_MIN', 'U_AVG', 'U_MAX', 'V_MIN', 'V_AVG', 'V_MAX')])

    def execute(self, context):
        objs, sel = _selected_loops(context)
        if len(sel) < 2:
            self.report({'WARNING'}, "Select at least two UV vertices")
            return {'CANCELLED'}
        k = 0 if self.mode.startswith('U') else 1
        vals = [l[o.uv].uv[k] for o, l in sel]
        kind = self.mode[2:]
        t = min(vals) if kind == 'MIN' else max(vals) if kind == 'MAX' else sum(vals) / len(vals)
        for o, l in sel:
            p = l[o.uv].uv.copy()
            p[k] = t
            l[o.uv].uv = p
        _finish(objs)
        return {'FINISHED'}


class UVED_OT_distribute_elements(_EditOp, Operator):
    bl_idname = "uved.distribute_elements"
    bl_label = "Distribute UV Vertices"
    bl_description = "Space the selected UV vertices evenly between the outermost ones"

    axis: EnumProperty(items=[('U', "U", ""), ('V', "V", "")])

    def execute(self, context):
        objs, sel = _selected_loops(context)
        k = 0 if self.axis == 'U' else 1
        groups = {}
        for o, l in sel:
            p = l[o.uv].uv
            groups.setdefault((id(o), round(p.x / EPS), round(p.y / EPS)), []).append((o, l))
        if len(groups) < 3:
            self.report({'WARNING'}, "Select at least three UV vertices")
            return {'CANCELLED'}
        keyed = sorted(groups.values(), key=lambda g: g[0][1][g[0][0].uv].uv[k])
        lo = keyed[0][0][1][keyed[0][0][0].uv].uv[k]
        hi = keyed[-1][0][1][keyed[-1][0][0].uv].uv[k]
        for n, g in enumerate(keyed):
            t = lo + (hi - lo) * n / (len(keyed) - 1)
            for o, l in g:
                p = l[o.uv].uv.copy()
                p[k] = t
                l[o.uv].uv = p
        _finish(objs)
        return {'FINISHED'}


# --------------------------------------------------------------------------
# Stitch Selected (like 3ds Max Unwrap UVW)
# --------------------------------------------------------------------------

def _face_winding(face, uv):
    p = [l[uv].uv for l in face.loops]
    return sum(p[i].x * p[(i + 1) % len(p)].y - p[(i + 1) % len(p)].x * p[i].y
               for i in range(len(p)))


def _fit_fn(src, dst, align, scale):
    """Best-fit move (shift, optional rotation / uniform scale) taking the points
    `src` onto `dst`. For a single edge this lands the edge exactly on its target."""
    src = np.array([tuple(p) for p in src], dtype=float)
    dst = np.array([tuple(p) for p in dst], dtype=float)
    cp, cq = src.mean(axis=0), dst.mean(axis=0)
    X, Y = src - cp, dst - cq
    sx, sy = (X ** 2).sum(), (Y ** 2).sum()
    ang = 0.0
    if align:
        dot = (X * Y).sum()
        cross = (X[:, 0] * Y[:, 1] - X[:, 1] * Y[:, 0]).sum()
        if abs(dot) > 1e-18 or abs(cross) > 1e-18:
            ang = math.atan2(cross, dot)
    k = math.sqrt(sy / sx) if scale and sx > EPS * EPS and sy > EPS * EPS else 1.0
    c, s = math.cos(ang) * k, math.sin(ang) * k
    px, py, qx, qy = cp[0], cp[1], cq[0], cq[1]
    return lambda x, y: (qx + (x - px) * c - (y - py) * s,
                         qy + (x - px) * s + (y - py) * c)


def _mirror_fn(p0, p1):
    """Reflection across the line through p0-p1 (None if the edge has no length)."""
    d = (p1 - p0)
    if d.length < EPS:
        return None
    d = d / d.length
    ox, oy, ux, uy = p0.x, p0.y, d.x, d.y

    def fn(x, y):
        rx, ry = x - ox, y - oy
        t = rx * ux + ry * uy
        return ox + 2 * t * ux - rx, oy + 2 * t * uy - ry
    return fn


def _pair_points(la, lb, uv):
    """UVs of one mesh edge on both sides, in the same vertex order."""
    na, nb = la.link_loop_next, lb.link_loop_next
    a = (la[uv].uv.copy(), na[uv].uv.copy())
    if lb.vert == la.vert:
        b = (lb[uv].uv.copy(), nb[uv].uv.copy())
    else:
        b = (nb[uv].uv.copy(), lb[uv].uv.copy())
    return a, b


class UVED_OT_stitch_selected(_EditOp, Operator):
    bl_idname = "uved.stitch_selected"
    bl_label = "Stitch Selected"
    bl_description = ("Join each selected UV edge to its matching edge on a neighbouring "
                      "island. With UV sync on, the island of the active face is the "
                      "'selected' one")

    def execute(self, context):
        s = context.scene.uved
        objs = _gather(context)
        stitched = skipped = 0
        for o in objs:
            uv = o.uv
            isl = o.islands()
            face_island = {f: i for i in isl for f in i.faces}
            active = o.bm.faces.active
            seen = set()
            pairs = []
            for ia in isl:
                for l in ia.loops:
                    n = l.link_loop_next
                    if not (o.selected(l) and o.selected(n)) or l.edge in seen:
                        continue
                    others = [f for f in l.edge.link_faces
                              if f is not l.face and f in face_island
                              and face_island[f] is not ia]
                    if not others:
                        continue
                    seen.add(l.edge)
                    fb = others[0]
                    ib = face_island[fb]
                    lb = next(x for x in fb.loops if x.edge == l.edge)
                    both = o.selected(lb) and o.selected(lb.link_loop_next)
                    if both and active is not None and active in ib.faces:
                        # the island holding the active face is the one that stays
                        la, lb, ia_, ib_ = lb, l, ib, ia
                    else:
                        la, lb, ia_, ib_ = l, lb, ia, ib
                    pairs.append((la, lb, ia_, ib_))

            # all edges between the same two islands are solved together
            groups = {}
            for la, lb, ia, ib in pairs:
                g = groups.setdefault(frozenset((id(ia), id(ib))),
                                      {"stay": ia, "move": ib, "edges": []})
                if g["stay"] is not ia:
                    la, lb = lb, la
                g["edges"].append((la, lb))

            # islands that were already stitched move together from then on
            cluster = {id(i): [i] for i in isl}

            def move(island, fn):
                if fn is not None:
                    for i in cluster[id(island)]:
                        i.apply(fn)

            def merge(a, b):
                ca, cb = cluster[id(a)], cluster[id(b)]
                if ca is not cb:
                    ca.extend(cb)
                    for i in cb:
                        cluster[id(i)] = ca

            def points(edges):
                pts = [_pair_points(la, lb, uv) for la, lb in edges]
                return ([p for a, _ in pts for p in a], [p for _, b in pts for p in b])

            w = s.stitch_bias
            al, sc = s.stitch_align, s.stitch_scale
            for g in groups.values():
                ia, ib, edges = g["stay"], g["move"], g["edges"]
                if cluster[id(ia)] is cluster[id(ib)]:
                    # closing a loop of islands would tear an earlier stitch
                    skipped += len(edges)
                    continue
                A, B = points(edges)
                if all((a - b).length < EPS for a, b in zip(A, B)):
                    merge(ia, ib)
                    continue
                # a face that is mirrored in UV space has to be flipped to unfold correctly
                la, lb = edges[0]
                if (_face_winding(la.face, uv) * _face_winding(lb.face, uv)) < 0:
                    if w >= 1.0:
                        move(ia, _mirror_fn(A[0], A[1]))
                    else:
                        move(ib, _mirror_fn(B[0], B[1]))
                    A, B = points(edges)
                if w >= 1.0:
                    move(ia, _fit_fn(A, B, al, sc))
                elif w <= 0.0:
                    move(ib, _fit_fn(B, A, al, sc))
                else:
                    move(ia, _fit_fn(A, [a.lerp(b, w) for a, b in zip(A, B)], al, sc))
                    A, B = points(edges)
                    move(ib, _fit_fn(B, A, al, sc))
                merge(ia, ib)
                stitched += len(edges)
        _finish(objs)
        if not stitched:
            self.report({'WARNING'}, "Select UV edges that have a matching edge on another island")
            return {'CANCELLED'}
        msg = f"Stitched {stitched} edge(s)"
        if skipped:
            msg += f", skipped {skipped} that would close a loop of islands"
        self.report({'INFO'}, msg)
        return {'FINISHED'}


# --------------------------------------------------------------------------
# Unstretch
# --------------------------------------------------------------------------

def _fit_back(old, new):
    """Similarity transform (rotation, uniform scale, shift) that maps `new` onto `old`."""
    mx, my = old.mean(axis=0), new.mean(axis=0)
    X, Y = old - mx, new - my
    denom = (Y ** 2).sum()
    if denom < 1e-18:
        return new
    U, S, Vt = np.linalg.svd(X.T @ Y)
    d = 1.0 if np.linalg.det(U @ Vt) >= 0 else -1.0
    D = np.diag([1.0, d])
    R = U @ D @ Vt
    k = (S * np.diag(D)).sum() / denom
    return (k * (R @ Y.T)).T + (mx - k * (R @ my))


def _save_mesh_state(o):
    bm = o.bm
    bm.faces.ensure_lookup_table()
    bm.edges.ensure_lookup_table()
    bm.faces.index_update()
    bm.edges.index_update()
    st = {
        "v": [v.select for v in bm.verts],
        "e": [e.select for e in bm.edges],
        "f": [f.select for f in bm.faces],
        "seam": [e.seam for e in bm.edges],
        "pin": [[l[o.uv].pin_uv for l in f.loops] for f in bm.faces],
        "active": bm.faces.active.index if bm.faces.active else -1,
        "uvsel": None,
        "uv_sync": o.uv_sync,
    }
    if (not o.sync or o.uv_sync) and hasattr(bmesh.types.BMLoop, "uv_select_vert"):
        st["uvsel"] = [(f.uv_select, [(l.uv_select_vert, l.uv_select_edge) for l in f.loops])
                       for f in bm.faces]
    return st


def _restore_mesh_state(o, st):
    bm = bmesh.from_edit_mesh(o.ob.data)
    o.bm = bm
    uv = bm.loops.layers.uv.active
    bm.faces.ensure_lookup_table()
    bm.edges.ensure_lookup_table()
    bm.verts.ensure_lookup_table()
    for v in bm.verts:
        v.select_set(False)
    for e in bm.edges:
        e.select_set(False)
    for f in bm.faces:
        f.select_set(False)
    for v, s in zip(bm.verts, st["v"]):
        if s:
            v.select_set(True)
    for e, s in zip(bm.edges, st["e"]):
        if s:
            e.select_set(True)
    for f, s in zip(bm.faces, st["f"]):
        if s:
            f.select_set(True)
    for e, s in zip(bm.edges, st["seam"]):
        e.seam = s
    for f, pins in zip(bm.faces, st["pin"]):
        for l, p in zip(f.loops, pins):
            l[uv].pin_uv = p
    if st["active"] >= 0:
        bm.faces.active = bm.faces[st["active"]]
    bm.select_flush_mode()
    if st["uvsel"] is not None:
        # clearing an edge or face flag also clears its vertex flags, so the
        # vertex flags go last, in a pass of their own
        for f, (fs, ls) in zip(bm.faces, st["uvsel"]):
            f.uv_select_set(fs)
        for f, (fs, ls) in zip(bm.faces, st["uvsel"]):
            for l, (sv, se) in zip(f.loops, ls):
                l.uv_select_edge_set(se)
        for f, (fs, ls) in zip(bm.faces, st["uvsel"]):
            for l, (sv, se) in zip(f.loops, ls):
                l.uv_select_vert_set(sv)
        if st["uv_sync"]:
            bm.uv_select_sync_valid = True
    bmesh.update_edit_mesh(o.ob.data, loop_triangles=False, destructive=False)


class UVED_OT_relax(_EditOp, Operator):
    bl_idname = "uved.relax"
    bl_label = "Relax / Unstretch"
    bl_description = ("Re-solve the selected UV vertices from the 3D shape so they are no "
                      "longer stretched. Unselected and pinned UVs stay where they are")

    def execute(self, context):
        s = context.scene.uved
        ts = context.tool_settings
        objs = _gather(context)
        saved = {o.ob.name: _save_mesh_state(o) for o in objs}

        # one plan per island that contains selected UV vertices
        plans = []
        for o in objs:
            for isl in o.islands():
                free = {(f.index, k) for f in isl.faces for k, l in enumerate(f.loops)
                        if o.selected(l)}
                if not free:
                    continue
                pts = np.array([tuple(l[o.uv].uv) for f in isl.faces for l in f.loops])
                fixed = sum(1 for f in isl.faces for k, l in enumerate(f.loops)
                            if (f.index, k) not in free or l[o.uv].pin_uv)
                plans.append({
                    "o": o, "faces": [f.index for f in isl.faces],
                    "edges": [e.index for e in isl.joined], "free": free,
                    "old": pts, "fixed": fixed,
                    "wind": sum(_face_winding(f, o.uv) for f in isl.faces),
                })
        if not plans:
            self.report({'WARNING'}, "Select the UV vertices you want to relax")
            return {'CANCELLED'}

        sync0 = ts.use_uv_select_sync
        ok = False
        try:
            for o in objs:
                if o.uv_sync:
                    # the unwrap below must follow the mesh selection we set up
                    o.bm.uv_select_sync_valid = False
                for v in o.bm.verts:
                    v.select_set(False)
                for e in o.bm.edges:
                    e.select_set(False)
                for f in o.bm.faces:
                    f.select_set(False)
            for p in plans:
                o, bm, uv = p["o"], p["o"].bm, p["o"].uv
                for fi in p["faces"]:
                    f = bm.faces[fi]
                    f.select_set(True)
                    for k, l in enumerate(f.loops):
                        if (fi, k) not in p["free"]:
                            l[uv].pin_uv = True      # must not move
                for ei in p["edges"]:
                    bm.edges[ei].seam = False        # keep the island in one piece
            for o in objs:
                o.bm.select_flush_mode()
                o.update()

            ts.use_uv_select_sync = True
            res = bpy.ops.uv.unwrap(method=s.relax_method, fill_holes=True, margin=0.0)
            if 'FINISHED' not in res:
                self.report({'WARNING'}, "Relax failed")
                return {'CANCELLED'}

            for o in objs:
                o.bm = bmesh.from_edit_mesh(o.ob.data)
                o.uv = o.bm.loops.layers.uv.active
                o.bm.faces.ensure_lookup_table()
            for p in plans:
                o, bm, uv = p["o"], p["o"].bm, p["o"].uv
                loops = [(fi, k, l) for fi in p["faces"] for k, l in enumerate(bm.faces[fi].loops)]
                new = np.array([tuple(l[uv].uv) for _, _, l in loops])
                if p["fixed"] < 2:
                    # nothing was pinned: put the island back where it was
                    if sum(_face_winding(bm.faces[fi], uv) for fi in p["faces"]) * p["wind"] < 0:
                        new = new * (-1.0, 1.0)
                    new = _fit_back(p["old"], new)
                amount = s.relax_blend
                for (fi, k, l), a, b in zip(loops, p["old"], new):
                    if (fi, k) in p["free"]:
                        l[uv].uv = tuple(a + (b - a) * amount)
            ok = True
        finally:
            ts.use_uv_select_sync = sync0
            for o in objs:
                _restore_mesh_state(o, saved[o.ob.name])
        return {'FINISHED'} if ok else {'CANCELLED'}


class UVED_OT_toggle_stretch(Operator):
    bl_idname = "uved.toggle_stretch"
    bl_label = "Show Stretch"
    bl_description = "Toggle the stretch overlay in the UV editors"

    @classmethod
    def poll(cls, context):
        return context.mode == 'EDIT_MESH'

    def execute(self, context):
        spaces = [sp.uv_editor for w in context.window_manager.windows
                  for a in w.screen.areas if a.type == 'IMAGE_EDITOR'
                  for sp in a.spaces if sp.type == 'IMAGE_EDITOR']
        if not spaces:
            self.report({'WARNING'}, "No UV editor is open")
            return {'CANCELLED'}
        state = not spaces[0].show_stretch
        for ue in spaces:
            ue.show_stretch = state
            ue.display_stretch_type = context.scene.uved.stretch_type
        return {'FINISHED'}


# --------------------------------------------------------------------------
# Connected-edge display (like the blue shared edges in 3ds Max Unwrap UVW)
# --------------------------------------------------------------------------

_link_handle = None


def _uv_select_mode(ts):
    if ts.use_uv_select_sync:
        m = ts.mesh_select_mode
        return 'VERTEX' if m[0] else 'EDGE' if m[1] else 'FACE'
    return ts.uv_select_mode


def _link_geometry(context, limit):
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
    for ob in _edit_objects(context):
        bm = bmesh.from_edit_mesh(ob.data)
        if bm.loops.layers.uv.active is None:
            continue
        total += len(bm.faces)
        if total > limit:
            return None
        objs.append(_Obj(ob, ts.use_uv_select_sync, face_mode))

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


def _draw_link_batches(region, lines, points, color, width):
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


def _draw_links():
    context = bpy.context
    try:
        if context.mode != 'EDIT_MESH':
            return
        s = context.scene.uved
        sp = context.space_data
        if not s.show_links or sp is None or sp.type != 'IMAGE_EDITOR' or not sp.show_uvedit:
            return
        geo = _link_geometry(context, s.link_limit)
        if not geo or not (geo[0] or geo[1]):
            return
        _draw_link_batches(context.region, geo[0], geo[1], tuple(s.link_color), s.link_width)
    except Exception:       # a draw callback must never raise
        pass


# --------------------------------------------------------------------------
# UI - one collapsible panel per tool group
# --------------------------------------------------------------------------

def _op(layout, idname, text, **props):
    o = layout.operator(idname, text=text)
    for k, v in props.items():
        setattr(o, k, v)
    return o


def _ui_align(layout, s):
    layout.prop(s, "align_relative", text="")
    c = layout.column(align=True)
    r = c.row(align=True)
    _op(r, "uved.align_islands", "Left", mode='LEFT')
    _op(r, "uved.align_islands", "Center", mode='CENTER_H')
    _op(r, "uved.align_islands", "Right", mode='RIGHT')
    r = c.row(align=True)
    _op(r, "uved.align_islands", "Bottom", mode='BOTTOM')
    _op(r, "uved.align_islands", "Middle", mode='CENTER_V')
    _op(r, "uved.align_islands", "Top", mode='TOP')


def _ui_distribute(layout, s):
    layout.prop(s, "gap_mode", text="")
    if s.gap_mode == 'FIXED':
        layout.prop(s, "gap")
    r = layout.row(align=True)
    _op(r, "uved.distribute_islands", "Distribute U", axis='U')
    _op(r, "uved.distribute_islands", "Distribute V", axis='V')
    layout.separator()
    r = layout.row(align=True)
    r.prop(s, "tile_u")
    r.prop(s, "tile_v")
    layout.operator("uved.move_to_tile")


def _ui_rotate(layout, s):
    c = layout.column(align=True)
    r = c.row(align=True)
    _op(r, "uved.transform_islands", "90° CCW", mode='CCW90')
    _op(r, "uved.transform_islands", "90° CW", mode='CW90')
    _op(r, "uved.transform_islands", "180°", mode='ROT180')
    r = c.row(align=True)
    _op(r, "uved.transform_islands", "Flip H", mode='FLIP_H')
    _op(r, "uved.transform_islands", "Flip V", mode='FLIP_V')
    r = layout.row(align=True)
    r.prop(s, "rot_angle", text="")
    _op(r, "uved.transform_islands", "Rotate", mode='ANGLE')
    r = layout.row(align=True)
    _op(r, "uved.auto_orient", "Auto H", target='HORIZONTAL')
    _op(r, "uved.auto_orient", "Auto V", target='VERTICAL')
    layout.operator("uved.orient_to_edge")


def _ui_density(layout, s):
    layout.prop(s, "texture_size")
    r = layout.row(align=True)
    r.prop(s, "target_density")
    r.operator("uved.get_density", text="", icon='EYEDROPPER')
    if s.readout:
        layout.label(text=s.readout, icon='INFO')
    c = layout.column(align=True)
    _op(c, "uved.set_density", "Apply Target", source='VALUE')
    r = c.row(align=True)
    _op(r, "uved.set_density", "Equalize", source='AVERAGE')
    _op(r, "uved.set_density", "Match Active", source='ACTIVE')


def _ui_scale(layout, s):
    r = layout.row(align=True)
    r.prop(s, "scale_u")
    r.prop(s, "scale_v")
    r = layout.row()
    r.enabled = abs(s.scale_u - 1.0) > 1e-6 or abs(s.scale_v - 1.0) > 1e-6
    r.operator("uved.scale_islands", text="Scale by U / V")


def _ui_vertices(layout, s):
    c = layout.column(align=True)
    r = c.row(align=True)
    _op(r, "uved.align_elements", "Left", mode='U_MIN')
    _op(r, "uved.align_elements", "Center U", mode='U_AVG')
    _op(r, "uved.align_elements", "Right", mode='U_MAX')
    r = c.row(align=True)
    _op(r, "uved.align_elements", "Bottom", mode='V_MIN')
    _op(r, "uved.align_elements", "Center V", mode='V_AVG')
    _op(r, "uved.align_elements", "Top", mode='V_MAX')
    r = layout.row(align=True)
    _op(r, "uved.distribute_elements", "Distribute U", axis='U')
    _op(r, "uved.distribute_elements", "Distribute V", axis='V')


def _ui_stitch(layout, s):
    layout.prop(s, "stitch_bias", slider=True)
    layout.prop(s, "stitch_align")
    layout.prop(s, "stitch_scale")
    layout.operator("uved.stitch_selected", icon='AUTOMERGE_ON')


def _ui_unstretch(layout, s):
    layout.prop(s, "relax_method", text="")
    layout.prop(s, "relax_blend", slider=True)
    layout.operator("uved.relax", icon='MOD_SMOOTH')
    r = layout.row(align=True)
    r.prop(s, "stretch_type", text="")
    r.operator("uved.toggle_stretch")


def _ui_display(layout, s):
    layout.prop(s, "show_links")
    c = layout.column()
    c.enabled = s.show_links
    c.prop(s, "link_color", text="")
    c.prop(s, "link_width")
    c.prop(s, "link_limit")


def _ui_title(layout, s):
    r = layout.row()
    r.alignment = 'CENTER'
    r.label(text=f"{ADDON_NAME}  v{ADDON_VERSION}", icon='UV')


def _ui_about(layout, s):
    c = layout.column(align=True)
    c.label(text=f"v{ADDON_VERSION} 업데이트", icon='INFO')
    for line in UPDATE_NOTES:
        c.label(text=line, icon='DOT')
    layout.separator()
    layout.label(text=f"제작: {ADDON_AUTHOR}", icon='USER')


# (key, panel title, draw function, panel options)
_SECTIONS = (
    ("title", ADDON_NAME, _ui_title, {'HIDE_HEADER'}),
    ("align", "Align Islands", _ui_align),
    ("distribute", "Distribute / Tile", _ui_distribute),
    ("rotate", "Rotate / Flip / Orient", _ui_rotate),
    ("density", "Texel Density", _ui_density),
    ("scale", "Scale Islands", _ui_scale),
    ("vertices", "UV Vertices", _ui_vertices),
    ("stitch", "Stitch", _ui_stitch),
    ("unstretch", "Unstretch", _ui_unstretch),
    ("display", "Connected Edges", _ui_display),
    ("about", "Updates / About", _ui_about),
)


class _SectionPanel:
    bl_region_type = 'UI'
    bl_category = "UV Edit"

    @classmethod
    def poll(cls, context):
        return context.mode == 'EDIT_MESH'

    def draw(self, context):
        type(self).section(self.layout, context.scene.uved)


def _make_panels():
    out = []
    for order, (key, label, fn, *opts) in enumerate(_SECTIONS):
        for space, tag in (('VIEW_3D', "view3d"), ('IMAGE_EDITOR', "image")):
            name = f"UVED_PT_{tag}_{key}"
            out.append(type(name, (_SectionPanel, Panel), {
                "bl_idname": name, "bl_label": label, "bl_space_type": space,
                "bl_order": order, "section": staticmethod(fn),
                "bl_options": set(opts[0]) if opts else set(),
            }))
    return tuple(out)


classes = (
    UVED_Settings,
    UVED_OT_align_islands, UVED_OT_distribute_islands, UVED_OT_move_to_tile,
    UVED_OT_get_density, UVED_OT_set_density, UVED_OT_scale_islands,
    UVED_OT_transform_islands, UVED_OT_auto_orient, UVED_OT_orient_to_edge,
    UVED_OT_align_elements, UVED_OT_distribute_elements,
    UVED_OT_stitch_selected,
    UVED_OT_relax, UVED_OT_toggle_stretch,
) + _make_panels()


def register():
    global _link_handle
    for c in classes:
        bpy.utils.register_class(c)
    bpy.types.Scene.uved = PointerProperty(type=UVED_Settings)
    if _link_handle is None:
        _link_handle = bpy.types.SpaceImageEditor.draw_handler_add(
            _draw_links, (), 'WINDOW', 'POST_PIXEL')


def unregister():
    global _link_handle
    if _link_handle is not None:
        bpy.types.SpaceImageEditor.draw_handler_remove(_link_handle, 'WINDOW')
        _link_handle = None
    del bpy.types.Scene.uved
    for c in reversed(classes):
        bpy.utils.unregister_class(c)
