"""Stitch Selected: islands that share mesh edges end up as one island with no gap,
whatever shape they have and whichever options are on."""
import math
import random
import unittest

import bmesh
import bpy

import helpers
from HamzziUVToolkit import core


def transform(ang, k, dx, dy, mirror=False):
    c, s = math.cos(ang) * k, math.sin(ang) * k

    def fn(x, y):
        if mirror:
            x = -x
        return (x * c - y * s + dx, x * s + y * c + dy)
    return fn


def build_grid(nx, ny, xforms, group):
    """A flat grid of nx*ny faces; each face takes the UV transform of its group."""
    me = bpy.data.meshes.new("g")
    bm = bmesh.new()
    uv = bm.loops.layers.uv.new("UVMap")
    vs = [[bm.verts.new((x, y, 0)) for x in range(nx + 1)] for y in range(ny + 1)]
    for y in range(ny):
        for x in range(nx):
            f = bm.faces.new((vs[y][x], vs[y][x + 1], vs[y + 1][x + 1], vs[y + 1][x]))
            fn = xforms[group(x, y)]
            for l in f.loops:
                l[uv].uv = fn(l.vert.co.x * 0.2, l.vert.co.y * 0.2)
    bm.to_mesh(me)
    bm.free()
    return helpers.link(bpy.data.objects.new("g", me))


def state():
    o = core.gather(bpy.context)[0]
    gap = 0.0
    for e in o.bm.edges:
        if len(e.link_faces) == 2:
            a = core._edge_uvs(e.link_faces[0], e, o.uv)
            b = core._edge_uvs(e.link_faces[1], e, o.uv)
            gap = max(gap, max((a[v] - b[v]).length for v in a))
    return len(o.islands()), gap


class StitchSelected(unittest.TestCase):
    def setUp(self):
        random.seed(2)
        self.rand = {i: transform(random.uniform(-1, 1), random.uniform(0.5, 1.6),
                                  random.uniform(0, 3), random.uniform(0, 3)) for i in range(9)}

    def tearDown(self):
        helpers.leave_edit()

    def run_case(self, nx, ny, xforms, group, align=True, scale=True):
        for bias in (0.0, 0.5, 1.0):
            with self.subTest(bias=bias):
                helpers.fresh()
                helpers.enter_edit([build_grid(nx, ny, xforms, group)])
                self.assertGreater(state()[0], 1)
                self.assertEqual(bpy.ops.uved.stitch_selected(bias=bias, align=align, scale=scale), {'FINISHED'})
                islands, gap = state()
                self.assertEqual(islands, 1)
                self.assertLess(gap, 1e-5)
                helpers.leave_edit()

    def test_chain_of_three(self):
        self.run_case(3, 1, self.rand, lambda x, y: x)

    def test_grid_of_nine_islands(self):
        self.run_case(3, 3, self.rand, lambda x, y: x + 3 * y)

    def test_grid_with_align_and_scale_off(self):
        self.run_case(3, 3, self.rand, lambda x, y: x + 3 * y, align=False, scale=False)

    def test_loop_of_four(self):
        self.run_case(2, 2, self.rand, lambda x, y: x + 2 * y)

    def test_mirrored_middle_island(self):
        mir = dict(self.rand)
        mir[1] = transform(0.4, 1.3, 0.5, 0.5, mirror=True)
        self.run_case(3, 1, mir, lambda x, y: x)


class StitchOptions(unittest.TestCase):
    """The button copies the panel values into the operator (invoke). A background Blender
    has no window, so it never calls invoke: that part has to be checked in a GUI session."""

    def test_operator_defaults_match_the_panel_defaults(self):
        helpers.fresh()
        panel = helpers.settings().bl_rna.properties
        op = bpy.ops.uved.stitch_selected.get_rna_type().properties
        for mine, theirs in (("bias", "stitch_bias"), ("align", "stitch_align"),
                             ("scale", "stitch_scale")):
            with self.subTest(option=mine):
                self.assertEqual(op[mine].default, panel[theirs].default)


if __name__ == "__main__":
    unittest.main()
