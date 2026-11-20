# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 StudyingHamzzi

"""Island tools: align, distribute, tile, scale, rotate / flip, orient."""

import math

import numpy as np
from bpy.props import BoolProperty, EnumProperty, FloatProperty, IntProperty
from bpy.types import Operator

from ..core import EPS, EditOp, finish, group_bounds, targets, targets_or_warn


def _gap_mode():
    return EnumProperty(
        name="Spacing", default='EQUAL',
        items=[('EQUAL', "Equal Gaps", "Even gaps between the outermost islands"),
               ('FIXED', "Fixed Gap", "Use the gap value below")])


def _gap():
    return FloatProperty(name="Gap", default=0.01, min=-1.0, max=1.0, precision=4)


def _draw_gap(op):
    op.layout.prop(op, "gap_mode", expand=True)
    if op.gap_mode == 'FIXED':
        op.layout.prop(op, "gap")


class UVED_OT_align_islands(EditOp, Operator):
    bl_idname = "uved.align_islands"
    bl_label = "Align Islands"
    bl_description = "Align the selected islands"

    mode: EnumProperty(items=[(k, k, "") for k in
                              ('LEFT', 'RIGHT', 'TOP', 'BOTTOM', 'CENTER_H', 'CENTER_V')])

    @classmethod
    def description(cls, context, properties):
        return {
            'LEFT': "Align the selected islands to the left edge",
            'CENTER_H': "Center the selected islands horizontally",
            'RIGHT': "Align the selected islands to the right edge",
            'BOTTOM': "Align the selected islands to the bottom edge",
            'CENTER_V': "Center the selected islands vertically",
            'TOP': "Align the selected islands to the top edge",
        }.get(properties.mode, cls.bl_description)

    def execute(self, context):
        s = context.scene.uved
        objs, isl = targets_or_warn(self, context)
        if not isl:
            return {'CANCELLED'}
        x0, y0, x1, y1 = group_bounds(isl)
        if s.align_relative == 'TILE':
            tx, ty = math.floor((x0 + x1) / 2), math.floor((y0 + y1) / 2)
            x0, y0, x1, y1 = tx, ty, tx + 1, ty + 1
        # axis, then where each island's (low edge, high edge) goes: low, high or middle
        k, side = {'LEFT': (0, 0.0), 'CENTER_H': (0, 0.5), 'RIGHT': (0, 1.0),
                   'BOTTOM': (1, 0.0), 'CENTER_V': (1, 0.5), 'TOP': (1, 1.0)}[self.mode]
        box = (x0, y0, x1, y1)
        target = box[k] + (box[k + 2] - box[k]) * side
        for i in isl:
            b = i.bounds()
            i.shift(k, target - (b[k] + (b[k + 2] - b[k]) * side))
        finish(objs)
        return {'FINISHED'}


class UVED_OT_distribute_islands(EditOp, Operator):
    bl_idname = "uved.distribute_islands"
    bl_label = "Distribute Islands"
    bl_description = "Space the selected islands evenly"

    axis: EnumProperty(items=[('U', "U", ""), ('V', "V", "")])
    # Own copies of the panel values (see UVED_OT_pack_to_tile)
    gap_mode: _gap_mode()
    gap: _gap()

    panel_values = (("gap_mode", "gap_mode"), ("gap", "gap"))

    def draw(self, context):
        _draw_gap(self)

    def execute(self, context):
        objs, isl = targets_or_warn(self, context, 2, "Select at least two islands")
        if not isl:
            return {'CANCELLED'}
        k = 0 if self.axis == 'U' else 1
        info = []
        for i in isl:
            b = i.bounds()
            info.append((b[k], b[k + 2], i))
        info.sort(key=lambda t: t[0])
        if self.gap_mode == 'EQUAL':
            span = max(t[1] for t in info) - info[0][0]
            gap = (span - sum(t[1] - t[0] for t in info)) / (len(info) - 1)
        else:
            gap = self.gap
        pos = info[0][0]
        for lo, hi, i in info:
            i.shift(k, pos - lo)
            pos += (hi - lo) + gap
        finish(objs)
        return {'FINISHED'}


class UVED_OT_sort_islands(EditOp, Operator):
    bl_idname = "uved.sort_islands"
    bl_label = "Sort Islands"
    bl_description = ("Line the selected islands up side by side, in the order of their position "
                      "in 3D space along the chosen axis. Islands keep their size and are not rotated")

    axis: EnumProperty(items=[('U', "U", "Place the islands in a row, left to right"),
                              ('V', "V", "Place the islands in a column, bottom to top")])
    # Own copies of the panel values (see UVED_OT_pack_to_tile)
    order_by: EnumProperty(
        name="Order By", default='X',
        items=[('X', "X", "Order the islands by their X position in 3D space"),
               ('Y', "Y", "Order the islands by their Y position in 3D space"),
               ('Z', "Z", "Order the islands by their Z position in 3D space")])
    reverse: BoolProperty(
        name="Reverse", default=False,
        description="Reverse the order (highest 3D position first)")
    gap_mode: _gap_mode()
    gap: _gap()

    panel_values = (
        ("order_by", "sort_axis"),
        ("reverse", "sort_reverse"),
        ("gap_mode", "gap_mode"),
        ("gap", "gap"),
    )

    def draw(self, context):
        row = self.layout.row(align=True)
        row.prop(self, "order_by", expand=True)
        row.prop(self, "reverse", text="", icon='ARROW_LEFTRIGHT', toggle=True)
        _draw_gap(self)

    def execute(self, context):
        objs, isl = targets_or_warn(self, context, 2, "Select at least two islands")
        if not isl:
            return {'CANCELLED'}
        k = 0 if self.axis == 'U' else 1          # direction of the line
        ax = {'X': 0, 'Y': 1, 'Z': 2}[self.order_by]
        order = sorted(isl, key=lambda i: (round(i.center3d()[ax], 5), i.bounds()[k]))
        if self.reverse:
            order.reverse()
        box = group_bounds(isl)
        start, base = box[k], box[1 - k]          # first island and the common edge
        size = [i.bounds() for i in order]
        widths = [b[k + 2] - b[k] for b in size]
        if self.gap_mode == 'FIXED':
            gap = self.gap
        else:
            # keep the width of the group, but never let the islands overlap
            gap = max(((box[k + 2] - box[k]) - sum(widths)) / (len(order) - 1), 0.0)
        pos = start
        for i, b, w in zip(order, size, widths):
            d = [0.0, 0.0]
            d[k], d[1 - k] = pos - b[k], base - b[1 - k]
            i.translate(*d)
            pos += w + gap
        finish(objs)
        return {'FINISHED'}


class UVED_OT_move_to_tile(EditOp, Operator):
    bl_idname = "uved.move_to_tile"
    bl_label = "Move to Tile"
    bl_description = "Move each selected island into the given UDIM tile (keeps its position inside the tile)"

    # Own copies of the panel values, so the tile can be changed in the Adjust Last
    # Operation panel after the run. Pressing the button starts them from the panel.
    tile_u: IntProperty(name="U", default=0, description="UDIM tile column to move into")
    tile_v: IntProperty(name="V", default=0, description="UDIM tile row to move into")

    panel_values = (("tile_u", "tile_u"), ("tile_v", "tile_v"))

    def execute(self, context):
        objs, isl = targets_or_warn(self, context)
        if not isl:
            return {'CANCELLED'}
        for i in isl:
            cx, cy = i.center()
            i.translate(self.tile_u - math.floor(cx), self.tile_v - math.floor(cy))
        finish(objs)
        return {'FINISHED'}


def _shelf_layout(sizes, k, margin):
    """Place boxes (w, h) scaled by k in rows inside the 0-1 square, left to right
    and bottom to top. Returns the lower-left corners, or None if they do not fit."""
    lim = 1.0 - margin + 1e-9
    x = y = margin
    row_h = 0.0
    out = []
    for w, h in sizes:
        w, h = w * k, h * k
        if x > margin and x + w > lim:
            x, y, row_h = margin, y + row_h + margin, 0.0
        if x + w > lim or y + h > lim:
            return None
        out.append((x, y))
        x += w + margin
        row_h = max(row_h, h)
    return out


class UVED_OT_pack_to_tile(EditOp, Operator):
    bl_idname = "uved.pack_to_tile"
    bl_label = "Pack into Tile"
    bl_description = ("Arrange the selected islands in tidy rows inside the given UDIM tile, "
                      "starting at its lower-left corner. Islands are not rotated and all "
                      "get the same scale, so the texel density ratio is kept")

    # Own copies of the panel values, so they can be changed in the Adjust Last Operation
    # panel after the run. Pressing the button starts them from the panel (panel_values).
    margin: FloatProperty(
        name="Margin", default=0.0, min=0.0, max=0.25, precision=4,
        description="Space left between the islands and along the tile border, in UV units")
    fit: BoolProperty(
        name="Scale to Fit", default=True,
        description="Resize all islands by the same factor so they fill the tile. "
                    "When off, islands keep their size and are only moved")
    tile_u: IntProperty(name="U", default=0, description="UDIM tile column to pack into")
    tile_v: IntProperty(name="V", default=0, description="UDIM tile row to pack into")

    panel_values = (
        ("margin", "pack_margin"),
        ("fit", "pack_fit"),
        ("tile_u", "tile_u"),
        ("tile_v", "tile_v"),
    )

    def execute(self, context):
        objs, isl = targets_or_warn(self, context)
        if not isl:
            return {'CANCELLED'}
        m = self.margin
        info = []
        for i in isl:
            x0, y0, x1, y1 = i.bounds()
            info.append((i, x0, y0, max(x1 - x0, EPS), max(y1 - y0, EPS)))
        # tallest first; islands of the same height keep their left-to-right order
        info.sort(key=lambda t: (-round(t[4], 5), t[1], t[2]))
        sizes = [(t[3], t[4]) for t in info]

        k, pos = 1.0, None
        if self.fit:
            room = 1.0 - 2 * m
            hi = min(room / max(w for w, _ in sizes), room / max(h for _, h in sizes))
            # a single row is a quick lower bound; when the gaps alone fill it, fall back
            # to a tiny scale (several rows, or a grid of gaps, still fit)
            lo = min(hi, (room - (len(sizes) - 1) * m) / sum(w for w, _ in sizes))
            if lo <= 0 or _shelf_layout(sizes, lo, m) is None:
                lo = 1e-6
            if _shelf_layout(sizes, lo, m) is not None:
                for _ in range(40):
                    mid = (lo + hi) / 2
                    if _shelf_layout(sizes, mid, m) is None:
                        hi = mid
                    else:
                        lo = mid
                k, pos = lo, _shelf_layout(sizes, lo, m)
        else:
            pos = _shelf_layout(sizes, 1.0, m)
        if pos is None:
            if self.fit:
                self.report({'WARNING'}, "The margin is too large for this many islands - lower the margin")
            else:
                self.report({'WARNING'}, "The islands do not fit in one tile - enable Scale to Fit "
                                         "or lower the margin")
            return {'CANCELLED'}

        for (i, x0, y0, _, _), (px, py) in zip(info, pos):
            tx, ty = self.tile_u + px, self.tile_v + py
            i.apply(lambda x, y, x0=x0, y0=y0, tx=tx, ty=ty: (tx + (x - x0) * k, ty + (y - y0) * k))
        finish(objs)
        self.report({'INFO'}, f"Packed {len(info)} island(s) at {k:.3f}x scale")
        return {'FINISHED'}


class UVED_OT_scale_islands(EditOp, Operator):
    bl_idname = "uved.scale_islands"
    bl_label = "Scale Islands"
    bl_description = "Scale each selected island around its own center"

    # Own copies of the panel values (see UVED_OT_pack_to_tile)
    scale_u: FloatProperty(name="U", default=1.0, min=0.001, soft_max=10.0,
                           description="Multiply island width by this factor")
    scale_v: FloatProperty(name="V", default=1.0, min=0.001, soft_max=10.0,
                           description="Multiply island height by this factor")

    panel_values = (("scale_u", "scale_u"), ("scale_v", "scale_v"))

    def execute(self, context):
        objs, isl = targets_or_warn(self, context)
        if not isl:
            return {'CANCELLED'}
        for i in isl:
            cx, cy = i.center()
            i.scale(self.scale_u, self.scale_v, cx, cy)
        finish(objs)
        return {'FINISHED'}


class UVED_OT_transform_islands(EditOp, Operator):
    bl_idname = "uved.transform_islands"
    bl_label = "Rotate / Flip Islands"
    bl_description = "Rotate or flip each selected island around its own center"

    mode: EnumProperty(items=[(k, k, "") for k in
                              ('CW90', 'CCW90', 'ROT180', 'ANGLE', 'FLIP_H', 'FLIP_V')])
    # Own copy of the panel angle, used by the ANGLE mode only (see UVED_OT_pack_to_tile)
    angle: FloatProperty(name="Angle", default=math.radians(15.0), subtype='ANGLE',
                         description="Counter-clockwise rotation of each island")

    panel_values = (("angle", "rot_angle"),)

    def draw(self, context):
        if self.mode == 'ANGLE':
            self.layout.prop(self, "angle")

    @classmethod
    def description(cls, context, properties):
        return {
            'CCW90': "Rotate each island 90 degrees counter-clockwise",
            'CW90': "Rotate each island 90 degrees clockwise",
            'ROT180': "Rotate each island 180 degrees",
            'ANGLE': "Rotate each island by the angle on the left",
            'FLIP_H': "Flip each island left to right",
            'FLIP_V': "Flip each island top to bottom",
        }.get(properties.mode, cls.bl_description)

    def execute(self, context):
        objs, isl = targets_or_warn(self, context)
        if not isl:
            return {'CANCELLED'}
        flip = {'FLIP_H': (-1, 1), 'FLIP_V': (1, -1)}.get(self.mode)
        angle = {'CW90': -math.pi / 2, 'CCW90': math.pi / 2, 'ROT180': math.pi,
                 'ANGLE': self.angle}.get(self.mode)
        for i in isl:
            cx, cy = i.center()
            if flip:
                i.scale(*flip, cx, cy)
            else:
                i.rotate(angle, cx, cy)
        finish(objs)
        return {'FINISHED'}


def _convex_hull(p):
    """Convex hull of 2D points (monotone chain), counter-clockwise, no repeats."""
    p = p[np.lexsort((p[:, 1], p[:, 0]))]
    if len(p) < 3:
        return p

    def half(points):
        out = []
        for q in points:
            while len(out) >= 2 and ((out[-1][0] - out[-2][0]) * (q[1] - out[-2][1])
                                     - (out[-1][1] - out[-2][1]) * (q[0] - out[-2][0])) <= 0:
                out.pop()
            out.append(q)
        return out

    lower, upper = half(p), half(p[::-1])
    return np.array(lower[:-1] + upper[:-1])


def min_box_rotation(p):
    """Rotation (radians, between -45 and +45 degrees) that gives the points the
    smallest axis-aligned bounding box.

    The smallest box always has one side along an edge of the convex hull, so only
    those edge directions are tried; the result is exact, not a sampled angle. Among
    rotations that give the same box, the smallest one wins, so an island that is
    already square to the axes is left alone."""
    hull = _convex_hull(np.unique(p, axis=0))
    if len(hull) < 3:
        if len(hull) < 2:
            return 0.0
        edges = hull[1:] - hull[:1]          # a straight line of UVs: lay it on an axis
    else:
        edges = np.roll(hull, -1, axis=0) - hull
    lengths = np.hypot(edges[:, 0], edges[:, 1])
    edges = edges[lengths > 1e-9]
    if not len(edges):
        return 0.0
    quarter = math.pi / 2
    # angle of each edge folded into (-45, 45]: rotating by minus that lays the edge
    # on the nearest axis
    ang = np.arctan2(edges[:, 1], edges[:, 0])
    ang = (ang + quarter / 2) % quarter - quarter / 2
    candidates = np.unique(np.round(np.concatenate(([0.0], -ang)), 12))

    best, best_a = None, 0.0
    for a in sorted(candidates, key=abs):
        c, s = math.cos(a), math.sin(a)
        x = hull[:, 0] * c - hull[:, 1] * s
        y = hull[:, 0] * s + hull[:, 1] * c
        area = (x.max() - x.min()) * (y.max() - y.min())
        if best is None or area < best * (1 - 1e-9):
            best, best_a = area, float(a)
    return best_a


class UVED_OT_auto_orient(EditOp, Operator):
    bl_idname = "uved.auto_orient"
    bl_label = "Auto Orient"
    bl_description = "Rotate each island to its minimum-area bounding box"

    target: EnumProperty(
        name="Longest Side", default='ANY',
        items=[('ANY', "Keep", "Only minimise the box"),
               ('HORIZONTAL', "Horizontal", "Longest side along U"),
               ('VERTICAL', "Vertical", "Longest side along V")])

    def execute(self, context):
        objs, isl = targets_or_warn(self, context)
        if not isl:
            return {'CANCELLED'}
        for i in isl:
            cx, cy = i.center()
            i.rotate(min_box_rotation(i.pts() - (cx, cy)), cx, cy)
            x0, y0, x1, y1 = i.bounds()
            w, h = x1 - x0, y1 - y0
            if (self.target == 'HORIZONTAL' and h > w) or (self.target == 'VERTICAL' and w > h):
                i.rotate(math.pi / 2, cx, cy)
        finish(objs)
        return {'FINISHED'}


class UVED_OT_orient_to_edge(EditOp, Operator):
    bl_idname = "uved.orient_to_edge"
    bl_label = "Orient to Edge"
    bl_description = ("Rotate each island so its longest selected UV edge lies on the nearest "
                      "axis")

    def execute(self, context):
        objs, isl = targets(context)
        done = 0
        for i in isl:
            uv = i.obj.uv
            longest = None
            for l in i.loops:
                n = l.link_loop_next
                if i.obj.selected(l) and i.obj.selected(n):
                    d = n[uv].uv - l[uv].uv
                    if d.length >= EPS and (longest is None or d.length > longest.length):
                        longest = d.copy()
            if longest is None:
                continue
            a = math.atan2(longest.y, longest.x)
            rot = -(a - round(a / (math.pi / 2)) * (math.pi / 2))
            cx, cy = i.center()
            i.rotate(rot, cx, cy)
            done += 1
        if not done:
            self.report({'WARNING'}, "Select a UV edge inside the island")
            return {'CANCELLED'}
        finish(objs)
        return {'FINISHED'}
