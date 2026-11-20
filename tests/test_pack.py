"""Pack into Tile: with Scale to Fit the islands always end up inside the tile margins."""
import random
import unittest

import bpy

import helpers


def random_rects(n, seed=1):
    rng = random.Random(seed)
    return [((i * 2, 0, 0), (rng.uniform(0, 3), rng.uniform(0, 3),
                             rng.uniform(0.05, 0.3), rng.uniform(0.05, 0.3))) for i in range(n)]


class PackIntoTile(unittest.TestCase):
    def setUp(self):
        helpers.fresh()

    def tearDown(self):
        helpers.leave_edit()

    def pack(self, rects, margin, fit):
        helpers.enter_edit([helpers.quads_object(rects)])
        return bpy.ops.uved.pack_to_tile(margin=margin, fit=fit)

    def test_scale_to_fit_stays_inside_the_margins(self):
        for n, margin in ((6, 0.05), (25, 0.02), (25, 0.05), (25, 0.1), (40, 0.05), (3, 0.25)):
            with self.subTest(islands=n, margin=margin):
                helpers.fresh()
                self.assertEqual(self.pack(random_rects(n), margin, True), {'FINISHED'})
                for x0, y0, x1, y1 in (i.bounds() for i in helpers.islands()):
                    self.assertGreaterEqual(x0, margin - 1e-6)
                    self.assertGreaterEqual(y0, margin - 1e-6)
                    self.assertLessEqual(x1, 1 - margin + 1e-6)
                    self.assertLessEqual(y1, 1 - margin + 1e-6)
                helpers.leave_edit()

    def test_islands_keep_their_proportions(self):
        helpers.enter_edit([helpers.quads_object(random_rects(8))])
        before = sorted((b[2] - b[0]) / (b[3] - b[1]) for b in (i.bounds() for i in helpers.islands()))
        self.assertEqual(bpy.ops.uved.pack_to_tile(margin=0.02), {'FINISHED'})
        after = sorted((b[2] - b[0]) / (b[3] - b[1]) for b in (i.bounds() for i in helpers.islands()))
        for a, b in zip(before, after):
            self.assertAlmostEqual(a, b, places=5)

    def test_a_margin_that_leaves_no_room_is_refused(self):
        # room is 0.5 and the gaps alone are 0.25: three rows of three fit, ten islands cannot
        self.assertEqual(self.pack(random_rects(10), 0.25, True), {'CANCELLED'})

    def test_without_scale_to_fit_oversized_islands_are_refused(self):
        rects = [((n * 2, 0, 0), (n * 2.0, 0, 0.6, 0.6)) for n in range(3)]
        self.assertEqual(self.pack(rects, 0.0, False), {'CANCELLED'})

    def test_tile_option_packs_into_that_tile(self):
        helpers.enter_edit([helpers.quads_object(random_rects(6))])
        self.assertEqual(bpy.ops.uved.pack_to_tile(margin=0.05, tile_u=2, tile_v=1), {'FINISHED'})
        for x0, y0, x1, y1 in (i.bounds() for i in helpers.islands()):
            self.assertGreaterEqual(x0, 2.05 - 1e-6)
            self.assertLessEqual(x1, 2.95 + 1e-6)
            self.assertGreaterEqual(y0, 1.05 - 1e-6)
            self.assertLessEqual(y1, 1.95 + 1e-6)


if __name__ == "__main__":
    unittest.main()
