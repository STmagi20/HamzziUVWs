"""Sort Islands: UV order follows the 3D order; islands keep their size and never overlap."""
import random
import unittest

import bpy

import helpers


def rand_items(rng, n, spread=3.0):
    items = []
    for _ in range(n):
        pos = tuple(rng.uniform(-spread, spread) for _ in range(3))
        uvr = (rng.uniform(0, 3), rng.uniform(0, 3), rng.uniform(0.05, 0.3), rng.uniform(0.05, 0.3))
        items.append((pos, uvr))
    return items


def snapshot():
    return [(i.center3d(), i.bounds()) for i in helpers.islands()]


class SortIslands(unittest.TestCase):
    def setUp(self):
        helpers.fresh()
        self.rng = random.Random(4)

    def tearDown(self):
        helpers.leave_edit()

    def check(self, objects, axis_3d, direction, reverse=False, gap_mode='EQUAL', gap=0.01):
        obs = [helpers.quads_object(items, f"o{n}", location=off)
               for n, (off, items) in enumerate(objects)]
        helpers.enter_edit(obs)
        s = helpers.settings()
        s.sort_axis, s.sort_reverse, s.gap_mode, s.gap = axis_3d, reverse, gap_mode, gap
        before = snapshot()
        self.assertEqual(bpy.ops.uved.sort_islands(axis=direction), {'FINISHED'})
        after = snapshot()

        k = 0 if direction == 'U' else 1
        ax = {'X': 0, 'Y': 1, 'Z': 2}[axis_3d]
        after.sort(key=lambda t: t[1][k])
        centres = [t[0][ax] for t in after]
        self.assertEqual(centres, sorted(centres, reverse=reverse), "UV order does not follow 3D order")

        def sizes(shots, d):
            return sorted(round(b[d + 2] - b[d], 5) for _, b in shots)
        self.assertEqual(sizes(before, 0), sizes(after, 0))
        self.assertEqual(sizes(before, 1), sizes(after, 1))

        self.assertEqual(len({round(t[1][1 - k], 5) for t in after}), 1, "islands share no common edge")
        gaps = [round(after[i + 1][1][k] - after[i][1][k + 2], 5) for i in range(len(after) - 1)]
        self.assertFalse(any(g < -1e-6 for g in gaps), f"islands overlap, gaps {gaps}")
        if gap_mode == 'FIXED':
            for g in gaps:
                self.assertAlmostEqual(g, gap, places=4)

    def one(self, n=6):
        return [((0, 0, 0), rand_items(self.rng, n))]

    def test_row_by_x(self):
        self.check(self.one(), 'X', 'U')

    def test_column_by_z(self):
        self.check(self.one(), 'Z', 'V')

    def test_row_by_y_reversed(self):
        self.check(self.one(), 'Y', 'U', reverse=True)

    def test_fixed_gap(self):
        self.check(self.one(), 'X', 'U', gap_mode='FIXED', gap=0.02)

    def test_many_islands(self):
        self.check(self.one(12), 'X', 'U')

    def test_two_objects_use_world_positions(self):
        two = [((5, 0, 0), rand_items(self.rng, 3)), ((-4, 2, 1), rand_items(self.rng, 4))]
        self.check(two, 'X', 'U')

    def test_two_objects_column_by_z(self):
        two = [((5, 0, 0), rand_items(self.rng, 3)), ((-4, 2, 1), rand_items(self.rng, 4))]
        self.check(two, 'Z', 'V')

    def test_a_single_island_is_refused(self):
        ob = helpers.quads_object(rand_items(self.rng, 1))
        helpers.enter_edit([ob])
        self.assertEqual(bpy.ops.uved.sort_islands(axis='U'), {'CANCELLED'})


if __name__ == "__main__":
    unittest.main()
