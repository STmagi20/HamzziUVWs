# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 StudyingHamzzi

"""Island tools: align, distribute, tile, scale, rotate / flip, orient."""

import math

import numpy as np
from bpy.props import EnumProperty
from bpy.types import Operator

from ..core import EPS, EditOp, finish, group_bounds, targets, targets_or_warn


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
        finish(objs)
        return {'FINISHED'}


class UVED_OT_distribute_islands(EditOp, Operator):
    bl_idname = "uved.distribute_islands"
    bl_label = "Distribute Islands"
    bl_description = "Space the selected islands evenly"

    axis: EnumProperty(items=[('U', "U", ""), ('V', "V", "")])

    def execute(self, context):
        s = context.scene.uved
        objs, isl = targets_or_warn(self, context, 2, "Select at least two islands")
        if not isl:
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
        finish(objs)
        return {'FINISHED'}


class UVED_OT_sort_islands(EditOp, Operator):
    bl_idname = "uved.sort_islands"
    bl_label = "Sort Islands"
    bl_description = ("Line the selected islands up side by side, in the order of their position "
                      "in 3D space along the chosen axis. Islands keep their size and are not rotated")

    axis: EnumProperty(items=[('U', "U", "Place the islands in a row, left to right"),
                              ('V', "V", "Place the islands in a column, bottom to top")])

    def execute(self, context):
        s = context.scene.uved
        objs, isl = targets_or_warn(self, context, 2, "Select at least two islands")
        if not isl:
            return {'CANCELLED'}
        k = 0 if self.axis == 'U' else 1          # direction of the line
        ax = {'X': 0, 'Y': 1, 'Z': 2}[s.sort_axis]
        order = sorted(isl, key=lambda i: (round(i.center3d()[ax], 5), i.bounds()[k]))
        if s.sort_reverse:
            order.reverse()
        box = group_bounds(isl)
        start, base = box[k], box[1 - k]          # first island and the common edge
        size = [i.bounds() for i in order]
        widths = [b[k + 2] - b[k] for b in size]
        if s.gap_mode == 'FIXED':
            gap = s.gap
        else:
            # keep the width of the group, but never let the islands overlap
            gap = max(((box[k + 2] - box[k]) - sum(widths)) / (len(order) - 1), 0.0)
        pos = start
        for i, b, w in zip(order, size, widths):
            along, across = pos - b[k], base - b[1 - k]
            i.translate(along, across) if k == 0 else i.translate(across, along)
            pos += w + gap
        finish(objs)
        return {'FINISHED'}


class UVED_OT_move_to_tile(EditOp, Operator):
    bl_idname = "uved.move_to_tile"
    bl_label = "Move to Tile"
    bl_description = "Move each selected island into the given UDIM tile (keeps its position inside the tile)"

    def execute(self, context):
        s = context.scene.uved
        objs, isl = targets_or_warn(self, context)
        if not isl:
            return {'CANCELLED'}
        for i in isl:
            cx, cy = i.center()
            i.translate(s.tile_u - math.floor(cx), s.tile_v - math.floor(cy))
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

    def execute(self, context):
        s = context.scene.uved
        objs, isl = targets_or_warn(self, context)
        if not isl:
            return {'CANCELLED'}
        m = s.pack_margin
        info = []
        for i in isl:
            x0, y0, x1, y1 = i.bounds()
            info.append((i, x0, y0, max(x1 - x0, EPS), max(y1 - y0, EPS)))
        # tallest first; islands of the same height keep their left-to-right order
        info.sort(key=lambda t: (-round(t[4], 5), t[1], t[2]))
        sizes = [(t[3], t[4]) for t in info]

        k, pos = 1.0, None
        if s.pack_fit:
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
            if s.pack_fit:
                self.report({'WARNING'}, "The margin is too large for this many islands - lower the margin")
            else:
                self.report({'WARNING'}, "The islands do not fit in one tile - enable Scale to Fit "
                                         "or lower the margin")
            return {'CANCELLED'}

        for (i, x0, y0, _, _), (px, py) in zip(info, pos):
            tx, ty = s.tile_u + px, s.tile_v + py
            i.apply(lambda x, y, x0=x0, y0=y0, tx=tx, ty=ty: (tx + (x - x0) * k, ty + (y - y0) * k))
        finish(objs)
        self.report({'INFO'}, f"Packed {len(info)} island(s) at {k:.3f}x scale")
        return {'FINISHED'}


class UVED_OT_scale_islands(EditOp, Operator):
    bl_idname = "uved.scale_islands"
    bl_label = "Scale Islands"
    bl_description = "Scale each selected island around its own center"

    def execute(self, context):
        s = context.scene.uved
        objs, isl = targets_or_warn(self, context)
        if not isl:
            return {'CANCELLED'}
        for i in isl:
            cx, cy = i.center()
            i.scale(s.scale_u, s.scale_v, cx, cy)
        finish(objs)
        return {'FINISHED'}


class UVED_OT_transform_islands(EditOp, Operator):
    bl_idname = "uved.transform_islands"
    bl_label = "Rotate / Flip Islands"
    bl_description = "Rotate or flip each selected island around its own center"

    mode: EnumProperty(items=[(k, k, "") for k in
                              ('CW90', 'CCW90', 'ROT180', 'ANGLE', 'FLIP_H', 'FLIP_V')])

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
        s = context.scene.uved
        objs, isl = targets_or_warn(self, context)
        if not isl:
            return {'CANCELLED'}
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
        finish(objs)
        return {'FINISHED'}


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
        finish(objs)
        return {'FINISHED'}


class UVED_OT_orient_to_edge(EditOp, Operator):
    bl_idname = "uved.orient_to_edge"
    bl_label = "Orient to Edge"
    bl_description = "Rotate each island so its selected UV edge lies on the nearest axis"

    def execute(self, context):
        objs, isl = targets(context)
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
        finish(objs)
        return {'FINISHED'}
