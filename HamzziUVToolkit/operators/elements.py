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


def _chains(sel):
    """Group the selected UV corners by position and join those that sit on a selected
    edge. Returns (chains, skipped): each chain is a list of positions from one end to
    the other, `skipped` counts connected pieces that are not a plain line (a loop or
    a branch)."""
    corners = {}
    for o, l in sel:
        p = l[o.uv].uv
        corners.setdefault((id(o), round(p.x / EPS), round(p.y / EPS)), []).append((o, l))
    links = {k: set() for k in corners}
    for key, group in corners.items():
        for o, l in group:
            nxt = l.link_loop_next
            if not o.selected(nxt):
                continue
            p = nxt[o.uv].uv
            other = (id(o), round(p.x / EPS), round(p.y / EPS))
            if other != key and other in links:
                links[key].add(other)
                links[other].add(key)
    chains, skipped, seen = [], 0, set()
    for start in links:
        if start in seen or not links[start]:
            continue
        piece, todo = [], [start]
        while todo:
            k = todo.pop()
            if k not in seen:
                seen.add(k)
                piece.append(k)
                todo.extend(links[k])
        ends = [k for k in piece if len(links[k]) == 1]
        if len(ends) != 2 or any(len(links[k]) > 2 for k in piece):
            skipped += 1
            continue
        order, prev, cur = [], None, ends[0]
        while cur is not None:
            order.append(cur)
            nxt = [k for k in links[cur] if k != prev]
            prev, cur = cur, (nxt[0] if nxt else None)
        chains.append([corners[k] for k in order])
    return chains, skipped


class UVED_OT_straighten_edges(EditOp, Operator):
    bl_idname = "uved.straighten_edges"
    bl_label = "Straighten UV Edges"
    bl_description = ("Put each chain of selected UV edges on the straight line between its two "
                      "end vertices, keeping the spacing between the vertices in proportion")

    def execute(self, context):
        objs, sel = _selected_loops(context)
        chains, skipped = _chains(sel)
        moved = 0
        for chain in chains:
            pts = [g[0][1][g[0][0].uv].uv.copy() for g in chain]
            seg = [(b - a).length for a, b in zip(pts, pts[1:])]
            total = sum(seg)
            if total < EPS:
                continue
            run = 0.0
            for n, group in enumerate(chain):
                if n:
                    run += seg[n - 1]
                p = pts[0] + (pts[-1] - pts[0]) * (run / total)
                for o, l in group:
                    l[o.uv].uv = p
            moved += 1
        if not moved:
            self.report({'WARNING'}, "Select a chain of connected UV edges to straighten")
            return {'CANCELLED'}
        if skipped:
            self.report({'WARNING'}, f"Skipped {skipped} selection(s) that are loops or branch; "
                                     "select a single open chain")
        finish(objs)
        return {'FINISHED'}
