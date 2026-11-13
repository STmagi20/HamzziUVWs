"""A mesh with no UV map (or a UV map nobody unwrapped) must not break the tools."""
import math
import unittest

import bmesh
import bpy

import helpers

CALLS = [
    ("align_islands", {"mode": 'LEFT'}), ("distribute_islands", {"axis": 'U'}),
    ("sort_islands", {"axis": 'U'}), ("move_to_tile", {}), ("pack_to_tile", {}),
    ("transform_islands", {"mode": 'CCW90'}), ("auto_orient", {"target": 'HORIZONTAL'}),
    ("orient_to_edge", {}), ("scale_islands", {}), ("get_density", {}),
    ("set_density", {"source": 'AVERAGE'}), ("align_elements", {"mode": 'U_AVG'}),
    ("distribute_elements", {"axis": 'U'}), ("stitch_selected", {}), ("relax", {}),
    ("select_flipped", {}),
]


def cube(with_empty_uv_map):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=2.0)
    me = bpy.data.meshes.new("c")
    bm.to_mesh(me)
    bm.free()
    if with_empty_uv_map:
        me.uv_layers.new(name="UVMap")                 # exists, but nothing was unwrapped
    return helpers.link(bpy.data.objects.new("c", me))


class NoUVMap(unittest.TestCase):
    def tearDown(self):
        helpers.leave_edit()

    def test_tools_cancel_and_do_not_add_a_uv_map(self):
        for name, kwargs in CALLS:
            with self.subTest(tool=name):
                helpers.fresh()
                ob = cube(False)
                helpers.enter_edit([ob])
                result = getattr(bpy.ops.uved, name)(**kwargs)
                helpers.leave_edit()
                self.assertEqual(result, {'CANCELLED'})
                self.assertEqual(len(ob.data.uv_layers), 0, "a UV map was created")


class UnwrappedNever(unittest.TestCase):
    def tearDown(self):
        helpers.leave_edit()

    def test_tools_keep_the_uv_values_finite(self):
        for name, kwargs in CALLS:
            with self.subTest(tool=name):
                helpers.fresh()
                ob = cube(True)
                helpers.enter_edit([ob])
                getattr(bpy.ops.uved, name)(**kwargs)       # may finish or cancel, must not raise
                helpers.leave_edit()
                values = [c for d in ob.data.uv_layers.active.data for c in d.uv]
                self.assertTrue(all(math.isfinite(v) for v in values))


if __name__ == "__main__":
    unittest.main()
