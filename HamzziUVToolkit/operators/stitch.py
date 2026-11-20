# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 StudyingHamzzi

"""Stitch Selected (like 3ds Max Unwrap UVW)."""

import math

import numpy as np
from bpy.props import BoolProperty, FloatProperty
from bpy.types import Operator
from mathutils import Vector

from ..core import EPS, EditOp, UnionFind, face_winding, finish, gather


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


def _weld_all(pairs, face_island, uv, bias):
    """Make every stitched seam vertex coincide exactly.

    The islands are only moved as a whole, so when their shapes differ (not clean
    squares, or Align / Scale are off) the seam ends can still be apart. All UVs
    that stitch edges tie together are snapped to one point: `bias` of the way from
    the staying side to the moving side. Doing it for all pairs at once keeps a
    vertex shared by several seams consistent. UVs of the same island that sit at
    the same spot move along, so no island is torn."""
    sets = UnionFind()
    stay, move = set(), set()
    for la, lb in pairs:
        na, nb = la.link_loop_next, lb.link_loop_next
        same = lb.vert == la.vert
        for sa, sb in ((la, lb if same else nb), (na, nb if same else lb)):
            sets.union(sa, sb)
            stay.add(sa)
            move.add(sb)

    def mean(loops):
        return sum((l[uv].uv for l in loops), Vector((0.0, 0.0))) / len(loops)

    target_of = {}
    for loops in sets.groups().values():
        a = [l for l in loops if l in stay]
        b = [l for l in loops if l in move]
        pa, pb = (mean(a) if a else None), (mean(b) if b else None)
        target = pa.lerp(pb, bias) if pa is not None and pb is not None else (pa or pb)
        if all((l[uv].uv - target).length < EPS for l in loops):
            continue
        for l in loops:
            island = face_island.get(l.face)
            for c in l.vert.link_loops:
                if face_island.get(c.face) is island and (c[uv].uv - l[uv].uv).length < 1e-4:
                    target_of[c] = target
    for l, target in target_of.items():
        l[uv].uv = target


def _find_pairs(o, isl, face_island):
    """(stay loop, move loop, stay island, move island) for each selected UV edge that
    has a matching edge on another island. With both sides selected (UV sync on), the
    island holding the active face is the one that stays."""
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
                pairs.append((lb, l, ib, ia))
            else:
                pairs.append((l, lb, ia, ib))
    return pairs


def _group_pairs(pairs):
    """All edges between the same two islands, to be solved together."""
    groups = {}
    for la, lb, ia, ib in pairs:
        g = groups.setdefault(frozenset((id(ia), id(ib))),
                              {"stay": ia, "move": ib, "edges": []})
        if g["stay"] is not ia:
            la, lb = lb, la
        g["edges"].append((la, lb))
    return list(groups.values())


def _solve_groups(groups, isl, uv, bias, align, scale):
    """Move the islands of each group onto each other. Returns the number of
    stitched edges and the (stay, move) loop pairs to weld."""
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

    stitched = 0
    weld_pairs = []
    for g in groups:
        ia, ib, edges = g["stay"], g["move"], g["edges"]
        weld_pairs.extend(edges)
        stitched += len(edges)
        if cluster[id(ia)] is cluster[id(ib)]:
            # already one piece (a loop of islands): do not move anything
            # again, the weld closes the seam
            continue
        A, B = points(edges)
        if all((a - b).length < EPS for a, b in zip(A, B)):
            # an earlier group already brought these edges together
            merge(ia, ib)
            continue
        # a face that is mirrored in UV space has to be flipped to unfold correctly
        la, lb = edges[0]
        if (face_winding(la.face, uv) * face_winding(lb.face, uv)) < 0:
            if bias >= 1.0:
                move(ia, _mirror_fn(A[0], A[1]))
            else:
                move(ib, _mirror_fn(B[0], B[1]))
            A, B = points(edges)
        if bias >= 1.0:
            move(ia, _fit_fn(A, B, align, scale))
        elif bias <= 0.0:
            move(ib, _fit_fn(B, A, align, scale))
        else:
            move(ia, _fit_fn(A, [a.lerp(b, bias) for a, b in zip(A, B)], align, scale))
            A, B = points(edges)
            move(ib, _fit_fn(B, A, align, scale))
        merge(ia, ib)
    return stitched, weld_pairs


class UVED_OT_stitch_selected(EditOp, Operator):
    bl_idname = "uved.stitch_selected"
    bl_label = "Stitch Selected"
    bl_description = ("Join each selected UV edge to its matching edge on a neighbouring "
                      "island. With UV sync on, the island of the active face is the "
                      "'selected' one")

    # Own copies of the panel values, so they can be changed in the Adjust Last Operation
    # panel after the run. Pressing the button starts them from the panel (see invoke).
    bias: FloatProperty(
        name="Bias", default=0.0, min=0.0, max=1.0, subtype='FACTOR',
        description="0 = the selected island stays and the neighbour moves, "
                    "1 = the neighbour stays and the selected island moves, "
                    "0.5 = both meet in the middle")
    align: BoolProperty(
        name="Align Clusters", default=True,
        description="Rotate the moving island so the edges line up")
    scale: BoolProperty(
        name="Scale Clusters", default=True,
        description="Scale the moving island so the edges have the same length")

    def invoke(self, context, event):
        s = context.scene.uved
        self.bias, self.align, self.scale = s.stitch_bias, s.stitch_align, s.stitch_scale
        return self.execute(context)

    def execute(self, context):
        objs = gather(context)
        stitched = 0
        for o in objs:
            isl = o.islands()
            face_island = {f: i for i in isl for f in i.faces}
            groups = _group_pairs(_find_pairs(o, isl, face_island))
            n, weld_pairs = _solve_groups(groups, isl, o.uv, self.bias,
                                          self.align, self.scale)
            _weld_all(weld_pairs, face_island, o.uv, self.bias)
            stitched += n
        finish(objs)
        if not stitched:
            self.report({'WARNING'}, "Select UV edges that have a matching edge on another island")
            return {'CANCELLED'}
        self.report({'INFO'}, f"Stitched {stitched} edge(s)")
        return {'FINISHED'}


def _cut_edges(o, isl):
    """Mesh edges inside the island whose UV edge is selected."""
    inside = set(isl.faces)
    cut = set()
    for e in isl.joined:
        if any(o.selected(x) and o.selected(x.link_loop_next) for x in e.link_loops
               if x.face in inside):
            cut.add(e)
    return cut


def _split_pieces(isl, cut):
    """Face groups of an island that stay joined once the `cut` edges are separated."""
    sets = UnionFind()
    for f in isl.faces:
        sets.find(f)
    for e in isl.joined:
        if e not in cut:
            fs = [f for f in e.link_faces if f in isl.faces]
            for f in fs[1:]:
                sets.union(fs[0], f)
    return list(sets.groups().values())


class UVED_OT_detach_selected(EditOp, Operator):
    bl_idname = "uved.detach_selected"
    bl_label = "Detach Selected"
    bl_description = ("Cut an island apart along the selected UV edges (the opposite of Stitch). "
                      "The pieces move away from each other so the cut shows")

    distance: FloatProperty(
        name="Gap", default=0.02, min=0.0, soft_max=0.2, precision=3,
        description="How far apart the pieces end up, in UV units")

    def execute(self, context):
        objs = gather(context)
        uv_of = {}
        done = 0
        for o in objs:
            for isl in o.islands():
                cut = _cut_edges(o, isl)
                if not cut:
                    continue
                pieces = _split_pieces(isl, cut)
                if len(pieces) < 2:
                    continue
                pts = isl.pts()
                mid = pts.mean(axis=0)
                for faces in pieces:
                    loops = [l for f in faces for l in f.loops]
                    c = np.array([tuple(l[o.uv].uv) for l in loops], dtype=float).mean(axis=0)
                    away = c - mid
                    n = float(np.hypot(away[0], away[1]))
                    if n < EPS:
                        continue            # a piece in the middle stays where it is
                    dx, dy = away / n * (self.distance / 2.0)
                    for l in loops:
                        l[o.uv].uv = (l[o.uv].uv.x + dx, l[o.uv].uv.y + dy)
                done += 1
        if not done:
            self.report({'WARNING'}, "Select UV edges that cut an island in two (the cut has to "
                                     "reach the border of the island)")
            return {'CANCELLED'}
        finish(objs)
        self.report({'INFO'}, f"Detached {done} island(s)")
        return {'FINISHED'}
