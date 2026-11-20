"""World-space surface area and texel density, including per-axis object scale."""
import math
import unittest

import bmesh
import bpy

import helpers

SIZE = 1024


def _island(ob):
    helpers.enter_edit([ob])
    return helpers.islands()[0]


class SurfaceArea(unittest.TestCase):
    def setUp(self):
        helpers.fresh()

    def tearDown(self):
        helpers.leave_edit()

    def test_unscaled_plane(self):
        self.assertAlmostEqual(_island(helpers.plane_object()).area3d(), 1.0, places=9)

    def test_scale_that_differs_per_axis(self):
        for scale, area in (((2, 1, 1), 2.0), ((3, 2, 1), 6.0), ((1, 4, 5), 4.0)):
            with self.subTest(scale=scale):
                helpers.fresh()
                self.assertAlmostEqual(
                    _island(helpers.plane_object(scale=scale)).area3d(), area, places=9)
                helpers.leave_edit()

    def test_rotated_and_scaled_object(self):
        ob = helpers.plane_object(scale=(3, 2, 1), rotation_z=math.radians(45))
        self.assertAlmostEqual(_island(ob).area3d(), 6.0, places=9)

    def test_quad_is_split_into_triangles_correctly(self):
        ob = helpers.plane_object(width=2.0, height=3.0)
        self.assertAlmostEqual(_island(ob).area3d(), 6.0, places=9)

    def test_concave_face_is_not_counted_twice(self):
        # arrowhead quad whose second corner points inward: a fan from the first corner
        # covers part of it twice. Its area is 1.6 (2 x the scale along X)
        for scale, area in (((1, 1, 1), 1.6), ((2, 1, 1), 3.2)):
            with self.subTest(scale=scale):
                helpers.fresh()
                me = bpy.data.meshes.new("arrow")
                bm = bmesh.new()
                bm.loops.layers.uv.new("UVMap")
                bm.faces.new([bm.verts.new(p) for p in
                              ((0, 0, 0), (1, 0.4, 0), (2, 0, 0), (1, 2, 0))])
                bm.to_mesh(me)
                bm.free()
                ob = helpers.link(bpy.data.objects.new("arrow", me))
                ob.scale = scale
                bpy.context.view_layer.update()
                # 0.4 is stored as a 32-bit float in the mesh, hence 6 places
                self.assertAlmostEqual(_island(ob).area3d(), area, places=6)
                helpers.leave_edit()


class Density(unittest.TestCase):
    def setUp(self):
        helpers.fresh()

    def tearDown(self):
        helpers.leave_edit()

    def test_density_follows_the_world_area(self):
        isl = _island(helpers.plane_object(scale=(2, 1, 1)))      # world area 2, UV area 0.25
        self.assertAlmostEqual(isl.density(SIZE), math.sqrt(0.25 / 2.0) * SIZE, places=6)

    def test_set_density_to_a_value(self):
        ob = helpers.plane_object(scale=(2, 1, 1))
        helpers.enter_edit([ob])
        self.assertEqual(bpy.ops.uved.set_density(source='VALUE', texture_size=SIZE,
                                                  target_density=512.0), {'FINISHED'})
        self.assertAlmostEqual(helpers.islands()[0].density(SIZE), 512.0, places=4)

    def test_equalize_makes_different_objects_match(self):
        a = helpers.plane_object(scale=(1, 1, 1), name="a")
        b = helpers.plane_object(scale=(4, 1, 1), uv_size=(0.2, 0.7), name="b")
        helpers.enter_edit([a, b])
        before = [i.density(SIZE) for i in helpers.islands()]
        self.assertGreater(abs(before[0] - before[1]), 1.0)
        self.assertEqual(bpy.ops.uved.set_density(source='AVERAGE', texture_size=SIZE), {'FINISHED'})
        after = [i.density(SIZE) for i in helpers.islands()]
        self.assertAlmostEqual(after[0], after[1], places=4)
        self.assertAlmostEqual(after[0], sum(before) / 2, places=4)

    def test_measure_fills_the_target(self):
        ob = helpers.plane_object(scale=(3, 2, 1))
        helpers.enter_edit([ob])
        s = helpers.settings()
        s.texture_size = SIZE
        self.assertEqual(bpy.ops.uved.get_density(), {'FINISHED'})
        self.assertAlmostEqual(helpers.settings().target_density,
                               math.sqrt(0.25 / 6.0) * SIZE, places=4)


class DensityOptions(unittest.TestCase):
    """The buttons copy the panel values into the operator (invoke). A background Blender
    has no window, so it never calls invoke: that part has to be checked in a GUI session."""

    def test_operator_defaults_match_the_panel_defaults(self):
        helpers.fresh()
        panel = helpers.settings().bl_rna.properties
        op = bpy.ops.uved.set_density.get_rna_type().properties
        for name in ("texture_size", "target_density"):
            with self.subTest(option=name):
                self.assertEqual(op[name].default, panel[name].default)


if __name__ == "__main__":
    unittest.main()
