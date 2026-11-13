"""Auto Orient finds the exact minimum-area box (not a sampled angle)."""
import math
import unittest

import bpy
import numpy as np

import helpers
from HamzziUVToolkit.operators.islands import min_box_rotation


def _box_area(points, angle):
    c, s = math.cos(angle), math.sin(angle)
    x = points[:, 0] * c - points[:, 1] * s
    y = points[:, 0] * s + points[:, 1] * c
    return (x.max() - x.min()) * (y.max() - y.min())


def _rotated_rectangle(degrees, w=3.0, h=1.0, extra=40, seed=1):
    rng = np.random.default_rng(seed)
    pts = np.array([(x, y) for x in (0, w) for y in (0, h)] +
                   [(rng.uniform(0, w), rng.uniform(0, h)) for _ in range(extra)])
    a = math.radians(degrees)
    c, s = math.cos(a), math.sin(a)
    return np.stack([pts[:, 0] * c - pts[:, 1] * s, pts[:, 0] * s + pts[:, 1] * c], 1)


class MinBoxRotation(unittest.TestCase):
    def test_recovers_the_exact_area_at_any_angle(self):
        for deg in (0.0, 10.0, 17.3, 33.33, -41.7, 44.0, 89.0, 123.456):
            with self.subTest(angle=deg):
                pts = _rotated_rectangle(deg)
                area = _box_area(pts, min_box_rotation(pts))
                self.assertAlmostEqual(area, 3.0, places=9)

    def test_rotation_is_at_most_45_degrees(self):
        for deg in (10.0, 80.0, 123.456, -170.0):
            with self.subTest(angle=deg):
                r = min_box_rotation(_rotated_rectangle(deg))
                self.assertLessEqual(abs(math.degrees(r)), 45.0 + 1e-9)

    def test_island_already_square_to_the_axes_is_left_alone(self):
        pts = np.array([(0, 0), (2, 0), (2, 1), (0, 1)], float)
        self.assertAlmostEqual(min_box_rotation(pts), 0.0, places=12)

    def test_degenerate_input(self):
        self.assertEqual(min_box_rotation(np.array([(1.0, 1.0)])), 0.0)
        line = min_box_rotation(np.array([(0, 0), (1, 1)], float))
        self.assertAlmostEqual(abs(math.degrees(line)), 45.0, places=6)


class AutoOrientOperator(unittest.TestCase):
    def setUp(self):
        helpers.fresh()

    def tearDown(self):
        helpers.leave_edit()

    def _island_size(self, target):
        a = math.radians(30.0)
        c, s = math.cos(a), math.sin(a)
        pts = [(x * c - y * s, x * s + y * c) for x, y in ((0, 0), (3, 0), (3, 1), (0, 1))]
        ob = helpers.polygon_object(pts)
        helpers.enter_edit([ob])
        self.assertEqual(bpy.ops.uved.auto_orient(target=target), {'FINISHED'})
        x0, y0, x1, y1 = helpers.islands()[0].bounds()
        return x1 - x0, y1 - y0

    def test_horizontal(self):
        w, h = self._island_size('HORIZONTAL')
        self.assertAlmostEqual(w, 3.0, places=6)
        self.assertAlmostEqual(h, 1.0, places=6)

    def test_vertical(self):
        w, h = self._island_size('VERTICAL')
        self.assertAlmostEqual(w, 1.0, places=6)
        self.assertAlmostEqual(h, 3.0, places=6)


if __name__ == "__main__":
    unittest.main()
