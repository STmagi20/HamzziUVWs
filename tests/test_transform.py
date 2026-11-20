"""Rotate / Flip and Scale: islands turn and grow around their own centre."""
import math
import unittest

import bmesh
import bpy

import helpers

RECTS = [((0, 0, 0), (0.2, 0.3, 0.4, 0.1)),
         ((2, 0, 0), (1.5, 0.5, 0.2, 0.3))]


def boxes():
    return sorted(tuple(round(float(v), 5) for v in i.bounds()) for i in helpers.islands())


def centres():
    return sorted(tuple(round(float(v), 5) for v in i.center()) for i in helpers.islands())


class Transform(unittest.TestCase):
    def setUp(self):
        helpers.fresh()
        helpers.enter_edit([helpers.quads_object(RECTS)])

    def tearDown(self):
        helpers.leave_edit()

    def test_rotate_by_a_given_angle(self):
        # a quarter turn swaps width and height and keeps the centre
        c0 = centres()
        sizes0 = sorted((round(b[2] - b[0], 5), round(b[3] - b[1], 5)) for b in boxes())
        self.assertEqual(bpy.ops.uved.transform_islands(mode='ANGLE', angle=math.pi / 2), {'FINISHED'})
        self.assertEqual(centres(), c0)
        sizes = sorted((round(b[2] - b[0], 5), round(b[3] - b[1], 5)) for b in boxes())
        self.assertEqual(sizes, sorted((h, w) for w, h in sizes0))

    def test_the_angle_is_counter_clockwise(self):
        # the island 0.4 x 0.1 at (0.2, 0.3): its lower-left corner is (-0.2, -0.05) from the
        # centre; a counter-clockwise quarter turn puts it at (0.05, -0.2)
        bm = bmesh.from_edit_mesh(bpy.context.object.data)
        uv = bm.loops.layers.uv.active
        corner = min((l for f in bm.faces for l in f.loops),
                     key=lambda l: (l[uv].uv.x, l[uv].uv.y))
        self.assertAlmostEqual(corner[uv].uv.x, 0.2, places=5)
        bpy.ops.uved.transform_islands(mode='ANGLE', angle=math.pi / 2)
        self.assertAlmostEqual(corner[uv].uv.x, 0.4 + 0.05, places=5)
        self.assertAlmostEqual(corner[uv].uv.y, 0.35 - 0.2, places=5)

    def test_flips_keep_the_box(self):
        before = boxes()
        for mode in ('FLIP_H', 'FLIP_V', 'ROT180'):
            with self.subTest(mode=mode):
                self.assertEqual(bpy.ops.uved.transform_islands(mode=mode), {'FINISHED'})
                self.assertEqual(boxes(), before)

    def test_scale_keeps_the_centre(self):
        c0 = centres()
        w0 = sorted(round(b[2] - b[0], 5) for b in boxes())
        self.assertEqual(bpy.ops.uved.scale_islands(scale_u=2.0, scale_v=0.5), {'FINISHED'})
        self.assertEqual(centres(), c0)
        self.assertEqual(sorted(round(b[2] - b[0], 5) for b in boxes()),
                         sorted(round(w * 2, 5) for w in w0))

if __name__ == "__main__":
    unittest.main()
