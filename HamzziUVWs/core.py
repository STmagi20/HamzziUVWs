# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 StudyingHamzzi

"""UV data access shared by every tool: edit objects, selection and islands."""

import math

import bmesh
import numpy as np

EPS = 1e-5


def edit_objects(context):
    # objects_in_mode_unique_type is missing in some editors (UV editor)
    return [o for o in context.view_layer.objects
            if o.type == 'MESH' and o.mode == 'EDIT']


def _edge_uvs(face, edge, uv):
    for l in face.loops:
        if l.edge == edge:
            n = l.link_loop_next
            return {l.vert: l[uv].uv.copy(), n.vert: n[uv].uv.copy()}
    return {}


class UVObject:
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


def gather(context):
    ts = context.tool_settings
    m = ts.mesh_select_mode
    face_mode = bool(m[2]) and not m[0] and not m[1]
    return [UVObject(o, ts.use_uv_select_sync, face_mode) for o in edit_objects(context)]


def targets(context):
    objs = gather(context)
    isl = [i for o in objs for i in o.islands()]
    sel = [i for i in isl if i.selected()]
    return objs, (sel or isl)


def finish(objs):
    for o in objs:
        o.update()


def group_bounds(islands):
    b = [i.bounds() for i in islands]
    return (min(x[0] for x in b), min(x[1] for x in b),
            max(x[2] for x in b), max(x[3] for x in b))


class EditOp:
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'EDIT_MESH' and len(edit_objects(context)) > 0


def face_winding(face, uv):
    p = [l[uv].uv for l in face.loops]
    return sum(p[i].x * p[(i + 1) % len(p)].y - p[(i + 1) % len(p)].x * p[i].y
               for i in range(len(p)))
