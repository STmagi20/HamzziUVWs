# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 StudyingHamzzi

"""Selected UV vertices: align and distribute."""

from bpy.props import EnumProperty
from bpy.types import Operator

from ..core import EPS, EditOp, finish, gather


def _selected_loops(context):
    objs = gather(context)
    out = []
    for o in objs:
        for f in o.bm.faces:
            if not o.visible(f):
                continue
            for l in f.loops:
                if o.selected(l):
                    out.append((o, l))
    return objs, out


class UVED_OT_align_elements(EditOp, Operator):
    bl_idname = "uved.align_elements"
    bl_label = "Align UV Vertices"
    bl_description = "Align the selected UV vertices (use average to straighten edges)"

    mode: EnumProperty(items=[(k, k, "") for k in
                              ('U_MIN', 'U_AVG', 'U_MAX', 'V_MIN', 'V_AVG', 'V_MAX')])

    @classmethod
    def description(cls, context, properties):
        return {
            'U_MIN': "Move the selected UV vertices to the leftmost one",
            'U_AVG': "Line the selected UV vertices up vertically at their average U",
            'U_MAX': "Move the selected UV vertices to the rightmost one",
            'V_MIN': "Move the selected UV vertices to the lowest one",
            'V_AVG': "Line the selected UV vertices up horizontally at their average V",
            'V_MAX': "Move the selected UV vertices to the highest one",
        }.get(properties.mode, cls.bl_description)

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
        finish(objs)
        return {'FINISHED'}


class UVED_OT_distribute_elements(EditOp, Operator):
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
        finish(objs)
        return {'FINISHED'}
