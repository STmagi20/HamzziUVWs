"""Distribute Islands: islands keep their outer limits and get equal or fixed gaps."""
import unittest

import bpy

import helpers

# three islands with uneven spacing along both axes
RECTS = [((0, 0, 0), (0.0, 0.0, 0.2, 0.2)),
         ((2, 0, 0), (0.3, 0.5, 0.1, 0.1)),
         ((4, 0, 0), (0.9, 0.9, 0.1, 0.1))]


def spans(k):
    return sorted((i.bounds()[k], i.bounds()[k + 2]) for i in helpers.islands())


class Distribute(unittest.TestCase):
    def setUp(self):
        helpers.fresh()
        helpers.enter_edit([helpers.quads_object(RECTS)])

    def tearDown(self):
        helpers.leave_edit()

    def gaps(self, k):
        s = spans(k)
        return [round(float(s[n + 1][0] - s[n][1]), 5) for n in range(len(s) - 1)]

    def test_equal_gaps_keep_the_outer_limits(self):
        for axis, k in (('U', 0), ('V', 1)):
            with self.subTest(axis=axis):
                helpers.fresh()
                helpers.enter_edit([helpers.quads_object(RECTS)])
                lo, hi = spans(k)[0][0], spans(k)[-1][1]
                self.assertEqual(bpy.ops.uved.distribute_islands(axis=axis, gap_mode='EQUAL'),
                                 {'FINISHED'})
                self.assertAlmostEqual(spans(k)[0][0], lo, places=5)
                self.assertAlmostEqual(spans(k)[-1][1], hi, places=5)
                g = self.gaps(k)
                self.assertAlmostEqual(g[0], g[1], places=5)
                helpers.leave_edit()

    def test_fixed_gap(self):
        self.assertEqual(bpy.ops.uved.distribute_islands(axis='U', gap_mode='FIXED', gap=0.05),
                         {'FINISHED'})
        self.assertEqual(self.gaps(0), [0.05, 0.05])

    def test_islands_do_not_move_across_the_other_axis(self):
        before = sorted((i.bounds()[1], i.bounds()[3]) for i in helpers.islands())
        bpy.ops.uved.distribute_islands(axis='U')
        self.assertEqual(sorted((i.bounds()[1], i.bounds()[3]) for i in helpers.islands()), before)

    def test_needs_two_islands(self):
        helpers.leave_edit()
        helpers.fresh()
        helpers.enter_edit([helpers.quads_object(RECTS[:1])])
        self.assertEqual(bpy.ops.uved.distribute_islands(axis='U'), {'CANCELLED'})

if __name__ == "__main__":
    unittest.main()
