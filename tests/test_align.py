"""Align Islands, quarter turns, and Align / Distribute UV Vertices."""
import unittest

import bmesh
import bpy

import helpers

# island A: (0.2, 0.3) - (0.6, 0.4), island B: (1.5, 0.5) - (1.7, 0.8)
RECTS = [((0, 0, 0), (0.2, 0.3, 0.4, 0.1)),
         ((2, 0, 0), (1.5, 0.5, 0.2, 0.3))]


def boxes():
    return [tuple(round(float(v), 5) for v in i.bounds()) for i in helpers.islands()]


def uvs():
    bm = bmesh.from_edit_mesh(bpy.context.object.data)
    uv = bm.loops.layers.uv.active
    return [(round(l[uv].uv.x, 5), round(l[uv].uv.y, 5)) for f in bm.faces for l in f.loops]


class AlignIslands(unittest.TestCase):
    def setUp(self):
        helpers.fresh()
        helpers.enter_edit([helpers.quads_object(RECTS)])

    def tearDown(self):
        helpers.leave_edit()

    def check(self, mode, k, side, value):
        """After aligning, every island's low edge / middle / high edge on axis k is at value."""
        self.assertEqual(bpy.ops.uved.align_islands(mode=mode), {'FINISHED'})
        for b in boxes():
            self.assertAlmostEqual(b[k] + (b[k + 2] - b[k]) * side, value, places=5)

    def test_to_the_selection_bounds(self):
        helpers.settings().align_relative = 'SELECTION'
        for mode, k, side, value in (('LEFT', 0, 0.0, 0.2), ('RIGHT', 0, 1.0, 1.7),
                                     ('CENTER_H', 0, 0.5, 0.95), ('BOTTOM', 1, 0.0, 0.3),
                                     ('TOP', 1, 1.0, 0.8), ('CENTER_V', 1, 0.5, 0.55)):
            with self.subTest(mode=mode):
                self.setUp()
                helpers.settings().align_relative = 'SELECTION'
                self.check(mode, k, side, value)

    def test_to_the_tile(self):
        # the selection's centre (0.95, 0.55) is in tile (0, 0)
        for mode, k, side, value in (('LEFT', 0, 0.0, 0.0), ('RIGHT', 0, 1.0, 1.0),
                                     ('CENTER_H', 0, 0.5, 0.5), ('BOTTOM', 1, 0.0, 0.0),
                                     ('TOP', 1, 1.0, 1.0), ('CENTER_V', 1, 0.5, 0.5)):
            with self.subTest(mode=mode):
                self.setUp()
                helpers.settings().align_relative = 'TILE'
                self.check(mode, k, side, value)

    def test_the_other_axis_does_not_move(self):
        before = boxes()
        bpy.ops.uved.align_islands(mode='LEFT')
        self.assertEqual([(b[1], b[3]) for b in boxes()], [(b[1], b[3]) for b in before])


class QuarterTurns(unittest.TestCase):
    def setUp(self):
        helpers.fresh()
        helpers.enter_edit([helpers.quads_object(RECTS[:1])])

    def tearDown(self):
        helpers.leave_edit()

    def test_direction(self):
        # island A's lower-left corner is (-0.2, -0.05) from its centre (0.4, 0.35)
        for mode, expected in (('CCW90', (0.45, 0.15)), ('CW90', (0.35, 0.55))):
            with self.subTest(mode=mode):
                self.setUp()
                bm = bmesh.from_edit_mesh(bpy.context.object.data)
                uv = bm.loops.layers.uv.active
                corner = min((l for f in bm.faces for l in f.loops),
                             key=lambda l: (l[uv].uv.x, l[uv].uv.y))
                self.assertEqual(bpy.ops.uved.transform_islands(mode=mode), {'FINISHED'})
                self.assertAlmostEqual(corner[uv].uv.x, expected[0], places=5)
                self.assertAlmostEqual(corner[uv].uv.y, expected[1], places=5)


class AlignVertices(unittest.TestCase):
    def setUp(self):
        helpers.fresh()
        helpers.enter_edit([helpers.quads_object(RECTS)])

    def tearDown(self):
        helpers.leave_edit()

    def test_every_mode(self):
        # U of the 8 corners: 0.2, 0.6, 0.6, 0.2, 1.5, 1.7, 1.7, 1.5 (average 1.0)
        # V of the 8 corners: 0.3, 0.3, 0.4, 0.4, 0.5, 0.5, 0.8, 0.8 (average 0.5)
        for mode, k, value in (('U_MIN', 0, 0.2), ('U_AVG', 0, 1.0), ('U_MAX', 0, 1.7),
                               ('V_MIN', 1, 0.3), ('V_AVG', 1, 0.5), ('V_MAX', 1, 0.8)):
            with self.subTest(mode=mode):
                self.setUp()
                before = uvs()
                self.assertEqual(bpy.ops.uved.align_elements(mode=mode), {'FINISHED'})
                after = uvs()
                self.assertEqual({p[k] for p in after}, {value})
                self.assertEqual([p[1 - k] for p in after], [p[1 - k] for p in before])


class DistributeVertices(unittest.TestCase):
    POINTS = [(0.0, 0.0), (0.1, 0.5), (0.7, 0.2), (1.0, 0.9)]

    def setUp(self):
        helpers.fresh()
        helpers.enter_edit([helpers.polygon_object(self.POINTS)])

    def tearDown(self):
        helpers.leave_edit()

    def test_even_spacing_between_the_outermost(self):
        third = round(1 / 3, 5)
        for axis, expected in (
                ('U', [(0.0, 0.0), (third, 0.5), (round(2 / 3, 5), 0.2), (1.0, 0.9)]),
                ('V', [(0.0, 0.0), (0.1, 0.6), (0.7, 0.3), (1.0, 0.9)])):
            with self.subTest(axis=axis):
                self.setUp()
                self.assertEqual(bpy.ops.uved.distribute_elements(axis=axis), {'FINISHED'})
                self.assertEqual(uvs(), expected)

    def test_needs_three_positions(self):
        helpers.fresh()
        helpers.enter_edit([helpers.polygon_object([(0, 0), (1, 0), (1, 0), (0, 0)])])
        self.assertEqual(bpy.ops.uved.distribute_elements(axis='U'), {'CANCELLED'})


if __name__ == "__main__":
    unittest.main()
