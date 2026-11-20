"""Move to Tile: every island lands in the given UDIM tile and keeps its place inside it."""
import math
import unittest

import bpy

import helpers

# three islands in different tiles, each at a known place inside its tile
RECTS = [((0, 0, 0), (0.1, 0.2, 0.3, 0.1)),
         ((2, 0, 0), (1.5, 0.4, 0.2, 0.2)),
         ((4, 0, 0), (-0.8, 2.3, 0.1, 0.3))]


def offsets():
    """(centre x, centre y) of each island, folded into its own tile."""
    out = []
    for i in helpers.islands():
        cx, cy = i.center()
        out.append((round(cx - math.floor(cx), 5), round(cy - math.floor(cy), 5)))
    return sorted(out)


class MoveToTile(unittest.TestCase):
    def setUp(self):
        helpers.fresh()
        helpers.enter_edit([helpers.quads_object(RECTS)])

    def tearDown(self):
        helpers.leave_edit()

    def test_every_island_lands_in_the_tile(self):
        self.assertEqual(bpy.ops.uved.move_to_tile(tile_u=3, tile_v=2), {'FINISHED'})
        for i in helpers.islands():
            cx, cy = i.center()
            self.assertEqual((math.floor(cx), math.floor(cy)), (3, 2))

    def test_positions_inside_the_tile_are_kept(self):
        before = offsets()
        self.assertEqual(bpy.ops.uved.move_to_tile(tile_u=-1, tile_v=4), {'FINISHED'})
        self.assertEqual(offsets(), before)

    def test_default_is_the_first_tile(self):
        self.assertEqual(bpy.ops.uved.move_to_tile(), {'FINISHED'})
        for i in helpers.islands():
            cx, cy = i.center()
            self.assertEqual((math.floor(cx), math.floor(cy)), (0, 0))

if __name__ == "__main__":
    unittest.main()
