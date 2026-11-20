"""Detach Selected: cut an island along selected UV edges (the opposite of Stitch)."""
import unittest

import bmesh
import bpy

import helpers


def grid():
    """A 6x2 grid whose UV is one continuous island. Returns the object."""
    helpers.fresh()
    bpy.ops.mesh.primitive_grid_add(x_subdivisions=6, y_subdivisions=2, size=2)
    ob = bpy.context.view_layer.objects.active
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.context.tool_settings.use_uv_select_sync = True
    return ob


def select_verts(ob, pick):
    bm = bmesh.from_edit_mesh(ob.data)
    for v in bm.verts:
        v.select_set(pick(v))
    bm.select_flush_mode()
    bmesh.update_edit_mesh(ob.data)


class Detach(unittest.TestCase):
    def tearDown(self):
        helpers.leave_edit()

    def test_a_cut_across_the_island_splits_it_in_two(self):
        ob = grid()
        select_verts(ob, lambda v: abs(v.co.x) < 1e-6)             # the whole middle column
        self.assertEqual(len(helpers.islands()), 1)
        self.assertEqual(bpy.ops.uved.detach_selected(distance=0.1), {'FINISHED'})
        isl = helpers.islands()
        self.assertEqual(len(isl), 2)
        left, right = sorted(isl, key=lambda i: i.center()[0])
        self.assertAlmostEqual(left.bounds()[2] + 0.1, right.bounds()[0], places=5)

    def test_smallest_gap_still_splits_the_island(self):
        # a Gap of 0 would leave the pieces joined in UV space, so the lowest value
        # (0 is raised to it) must still give two islands
        ob = grid()
        select_verts(ob, lambda v: abs(v.co.x) < 1e-6)
        self.assertEqual(bpy.ops.uved.detach_selected(distance=0.0), {'FINISHED'})
        self.assertEqual(len(helpers.islands()), 2)

    def test_cut_that_does_not_reach_the_border_is_refused(self):
        ob = grid()
        select_verts(ob, lambda v: abs(v.co.x) < 1e-6 and v.co.y <= 1e-6)   # the lower half of the column
        self.assertEqual(bpy.ops.uved.detach_selected(), {'CANCELLED'})
        self.assertEqual(len(helpers.islands()), 1)

    def test_nothing_selected_is_refused(self):
        ob = grid()
        select_verts(ob, lambda v: False)
        self.assertEqual(bpy.ops.uved.detach_selected(), {'CANCELLED'})

    def test_detach_then_stitch_joins_it_again(self):
        ob = grid()
        select_verts(ob, lambda v: abs(v.co.x) < 1e-6)
        self.assertEqual(bpy.ops.uved.detach_selected(distance=0.1), {'FINISHED'})
        self.assertEqual(bpy.ops.uved.stitch_selected(), {'FINISHED'})
        self.assertEqual(len(helpers.islands()), 1)


if __name__ == "__main__":
    unittest.main()
