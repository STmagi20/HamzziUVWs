# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 StudyingHamzzi

"""Stitch Selected (like 3ds Max Unwrap UVW)."""

import math

import numpy as np
from bpy.types import Operator

from ..core import EPS, EditOp, face_winding, finish, gather


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


class UVED_OT_stitch_selected(EditOp, Operator):
    bl_idname = "uved.stitch_selected"
    bl_label = "Stitch Selected"
    bl_description = ("Join each selected UV edge to its matching edge on a neighbouring "
                      "island. With UV sync on, the island of the active face is the "
                      "'selected' one")

    def execute(self, context):
        s = context.scene.uved
        objs = gather(context)
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
                if (face_winding(la.face, uv) * face_winding(lb.face, uv)) < 0:
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
        finish(objs)
        if not stitched:
            self.report({'WARNING'}, "Select UV edges that have a matching edge on another island")
            return {'CANCELLED'}
        msg = f"Stitched {stitched} edge(s)"
        if skipped:
            msg += f", skipped {skipped} that would close a loop of islands"
        self.report({'INFO'}, msg)
        return {'FINISHED'}
