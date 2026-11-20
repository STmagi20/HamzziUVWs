"""Straighten: a chain of selected UV edges goes onto the line between its ends."""
import math
import unittest

import bmesh
import bpy

import helpers


def grid(sync=True):
    """A 6x2 grid with UVs; the bottom row of corners is pushed off a straight line
    with uneven spacing. Returns (object, original positions of that row, left to right)."""
    helpers.fresh()
    bpy.ops.mesh.primitive_grid_add(x_subdivisions=6, y_subdivisions=2, size=2)
    ob = bpy.context.view_layer.objects.active
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.context.tool_settings.use_uv_select_sync = sync
    bm = bmesh.from_edit_mesh(ob.data)
    uv = bm.loops.layers.uv.active
    ymin = min(v.co.y for v in bm.verts)
    row = sorted((v for v in bm.verts if abs(v.co.y - ymin) < 1e-6), key=lambda v: v.co.x)
    xs = [0.0, 0.05, 0.2, 0.45, 0.6, 0.9, 1.0]
    ys = [0.02, 0.1, -0.05, 0.12, 0.0, 0.08, 0.03]
    for v, x, y in zip(row, xs, ys):
        for l in v.link_loops:
            l[uv].uv = (x, y)
    for v in bm.verts:
        v.select_set(v in row)
    bm.select_flush_mode()
    bmesh.update_edit_mesh(ob.data)
    return ob, list(zip(xs, ys))


def row_uvs(ob, count):
    bm = bmesh.from_edit_mesh(ob.data)
    uv = bm.loops.layers.uv.active
    seen = {}
    for f in bm.faces:
        for l in f.loops:
            if l.vert.select:
                seen[l.vert.index] = tuple(l[uv].uv)
    pts = sorted(seen.values())
    assert len(pts) == count, pts
    return pts


class Straighten(unittest.TestCase):
    def tearDown(self):
        helpers.leave_edit()

    def test_chain_lands_on_the_line_between_its_ends(self):
        ob, orig = grid()
        self.assertEqual(bpy.ops.uved.straighten_edges(), {'FINISHED'})
        pts = row_uvs(ob, 7)
        (x0, y0), (x1, y1) = orig[0], orig[-1]
        self.assertAlmostEqual(pts[0][0], x0, places=5)
        self.assertAlmostEqual(pts[0][1], y0, places=5)
        self.assertAlmostEqual(pts[-1][0], x1, places=5)
        self.assertAlmostEqual(pts[-1][1], y1, places=5)
        for x, y in pts:
            t = (x - x0) / (x1 - x0)
            self.assertAlmostEqual(y, y0 + (y1 - y0) * t, places=5)

    def test_spacing_stays_in_proportion(self):
        ob, orig = grid()
        seg = [math.dist(a, b) for a, b in zip(orig, orig[1:])]
        want = [sum(seg[:n]) / sum(seg) for n in range(len(seg) + 1)]
        self.assertEqual(bpy.ops.uved.straighten_edges(), {'FINISHED'})
        pts = row_uvs(ob, 7)
        total = math.dist(pts[0], pts[-1])
        got = [math.dist(pts[0], p) / total for p in pts]
        for a, b in zip(got, want):
            self.assertAlmostEqual(a, b, places=4)

    def test_without_uv_sync(self):
        ob, orig = grid(sync=False)
        bm = bmesh.from_edit_mesh(ob.data)
        uv = bm.loops.layers.uv.active
        row = {v.index for v in bm.verts if v.select}
        bpy.ops.mesh.select_all(action='SELECT')           # faces visible; the UV selection is its own
        bm = bmesh.from_edit_mesh(ob.data)
        for second in (False, True):       # edge flags first: clearing one also clears vertex flags
            for f in bm.faces:
                for l in f.loops:
                    on = l.vert.index in row
                    edge = on and l.link_loop_next.vert.index in row
                    if hasattr(l, "uv_select_vert_set"):    # Blender 5.x
                        l.uv_select_vert_set(on) if second else l.uv_select_edge_set(edge)
                    elif not second:                       # Blender 4.x
                        l[uv].select, l[uv].select_edge = on, edge
        bmesh.update_edit_mesh(ob.data)
        self.assertEqual(bpy.ops.uved.straighten_edges(), {'FINISHED'})
        bm = bmesh.from_edit_mesh(ob.data)
        uv = bm.loops.layers.uv.active
        (x0, y0), (x1, y1) = orig[0], orig[-1]
        pts = {tuple(round(c, 5) for c in l[uv].uv) for f in bm.faces for l in f.loops
               if l.vert.index in row}
        self.assertEqual(len(pts), 7)
        for x, y in pts:
            self.assertAlmostEqual(y, y0 + (y1 - y0) * (x - x0) / (x1 - x0), places=4)

    def test_a_branching_selection_is_refused(self):
        ob, _ = grid()
        bpy.ops.mesh.select_all(action='SELECT')
        self.assertEqual(bpy.ops.uved.straighten_edges(), {'CANCELLED'})

    def test_single_vertex_is_refused(self):
        ob, _ = grid()
        bm = bmesh.from_edit_mesh(ob.data)
        first = next(v for v in bm.verts if v.select)
        for v in bm.verts:
            v.select_set(v is first)
        bm.select_flush_mode()
        bmesh.update_edit_mesh(ob.data)
        self.assertEqual(bpy.ops.uved.straighten_edges(), {'CANCELLED'})


if __name__ == "__main__":
    unittest.main()
