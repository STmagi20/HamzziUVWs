"""Relax (Unstretch) on controlled cases.

These run in a background Blender, which has no UV editor. Blender's unwrap gives a
different result when it is called from inside a UV editor, so this only checks what
does not depend on that: pinned points stay, the stretch goes down, nothing is left
changed afterwards. Check the real behaviour in a GUI session with a UV editor open."""
import random
import unittest

import bmesh
import bpy
import numpy as np

import helpers


def stats(ob):
    """UV points, plus the largest deviation of the UV-to-3D area ratio from its mean."""
    bm = bmesh.from_edit_mesh(ob.data)
    uv = bm.loops.layers.uv.active
    pts = np.array([tuple(l[uv].uv) for f in bm.faces for l in f.loops])
    ratios = []
    for f in bm.faces:
        p = [l[uv].uv for l in f.loops]
        a = abs(sum(p[i].x * p[(i + 1) % len(p)].y - p[(i + 1) % len(p)].x * p[i].y
                    for i in range(len(p)))) / 2
        ratios.append(a / max(f.calc_area(), 1e-12))
    r = np.array(ratios)
    r = r / r.mean()
    return pts, float(np.abs(r - 1).max())


class RelaxGrid(unittest.TestCase):
    OFFSET = (3.3, 2.1)

    def setUp(self):
        helpers.fresh()

    def tearDown(self):
        helpers.leave_edit()

    def jittered_grid(self, interior_only, sync=True):
        bpy.ops.mesh.primitive_grid_add(x_subdivisions=10, y_subdivisions=10, size=2)
        ob = bpy.context.object
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.context.tool_settings.use_uv_select_sync = sync
        bm = bmesh.from_edit_mesh(ob.data)
        uv = bm.loops.layers.uv.active
        rng = random.Random(5)
        jit = {}
        for f in bm.faces:
            for l in f.loops:
                v = l.vert
                if v.index not in jit:
                    edge = abs(v.co.x) > 0.999 or abs(v.co.y) > 0.999
                    jit[v.index] = (0, 0) if edge else (rng.uniform(-.045, .045), rng.uniform(-.045, .045))
                l[uv].uv = ((v.co.x + 1) / 2 + self.OFFSET[0] + jit[v.index][0],
                            (v.co.y + 1) / 2 + self.OFFSET[1] + jit[v.index][1])
        for v in bm.verts:
            v.select_set(not interior_only or (abs(v.co.x) < 0.999 and abs(v.co.y) < 0.999))
        bm.select_flush_mode()
        if not sync:
            self.select_all_uvs(bm, uv)
        bmesh.update_edit_mesh(ob.data)
        return ob

    @staticmethod
    def select_all_uvs(bm, uv):
        # without UV sync the UV editor keeps its own selection, which starts out empty
        for f in bm.faces:
            for l in f.loops:
                if hasattr(l, "uv_select_vert_set"):            # Blender 5.x
                    l.uv_select_vert_set(True)
                    l.uv_select_edge_set(True)
                else:                                          # Blender 4.x
                    l[uv].select = True
                    l[uv].select_edge = True

    def border_indices(self, pts):
        o = np.array(self.OFFSET)
        # UV values are stored as float32, so compare with a tolerance above its rounding
        return [i for i, p in enumerate(pts)
                if min(abs(p - o).min(), abs(p - o - 1).min()) < 1e-6]

    def test_everything_selected_reduces_the_stretch_and_stays_in_place(self):
        ob = self.jittered_grid(False)
        before, worst0 = stats(ob)
        self.assertEqual(bpy.ops.uved.relax(), {'FINISHED'})
        after, worst1 = stats(ob)
        self.assertLess(worst1, worst0)
        self.assertLess(np.abs(after.mean(axis=0) - before.mean(axis=0)).max(), 0.05)

    def test_pinned_border_does_not_move(self):
        ob = self.jittered_grid(True)
        before, worst0 = stats(ob)
        self.assertEqual(bpy.ops.uved.relax(), {'FINISHED'})
        after, worst1 = stats(ob)
        border = self.border_indices(before)
        self.assertTrue(border)
        self.assertLess(float(np.abs(after[border] - before[border]).max()), 1e-6)
        self.assertLess(worst1, worst0)

    def test_without_uv_sync(self):
        ob = self.jittered_grid(False, sync=False)
        before, worst0 = stats(ob)
        self.assertEqual(bpy.ops.uved.relax(), {'FINISHED'})
        self.assertLess(stats(ob)[1], worst0)

    def test_selection_and_seams_are_restored(self):
        ob = self.jittered_grid(True)
        bm = bmesh.from_edit_mesh(ob.data)
        selected = sorted(v.index for v in bm.verts if v.select)
        seams = sorted(e.index for e in bm.edges if e.seam)
        self.assertEqual(bpy.ops.uved.relax(), {'FINISHED'})
        bm = bmesh.from_edit_mesh(ob.data)
        self.assertEqual(sorted(v.index for v in bm.verts if v.select), selected)
        self.assertEqual(sorted(e.index for e in bm.edges if e.seam), seams)
        self.assertFalse(any(l[bm.loops.layers.uv.active].pin_uv for f in bm.faces for l in f.loops))

    def test_amount_option_moves_less_than_a_full_relax(self):
        moved = {}
        for amount in (0.5, 1.0):
            helpers.leave_edit()
            ob = self.jittered_grid(True)
            before, _ = stats(ob)
            self.assertEqual(bpy.ops.uved.relax(blend=amount), {'FINISHED'})
            after, _ = stats(ob)
            moved[amount] = float(np.abs(after - before).sum())
        self.assertGreater(moved[1.0], 0.0)
        self.assertLess(moved[0.5], moved[1.0])

    def test_pin_boundary_option(self):
        ob = self.jittered_grid(False)
        before, _ = stats(ob)
        self.assertEqual(bpy.ops.uved.relax(pin_boundary=False, method='CONFORMAL'), {'FINISHED'})
        after, worst1 = stats(ob)
        self.assertTrue(np.isfinite(after).all())


class RelaxOptions(unittest.TestCase):
    """The button copies the panel values into the operator (invoke). A background Blender
    has no window, so it never calls invoke: that part has to be checked in a GUI session."""

    def test_operator_defaults_match_the_panel_defaults(self):
        helpers.fresh()
        panel = helpers.settings().bl_rna.properties
        op = bpy.ops.uved.relax.get_rna_type().properties
        for mine, theirs in (("method", "relax_method"), ("pin_boundary", "relax_pin_boundary"),
                             ("blend", "relax_blend")):
            with self.subTest(option=mine):
                self.assertEqual(op[mine].default, panel[theirs].default)


class RelaxSphere(unittest.TestCase):
    def tearDown(self):
        helpers.leave_edit()

    def test_middle_band_of_a_default_uv_sphere(self):
        helpers.fresh()
        bpy.ops.mesh.primitive_uv_sphere_add()
        ob = bpy.context.object
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.context.tool_settings.use_uv_select_sync = True
        bm = bmesh.from_edit_mesh(ob.data)
        for v in bm.verts:
            v.select_set(abs(v.co.z) < 0.55)
        bm.select_flush_mode()
        bmesh.update_edit_mesh(ob.data)
        before, worst0 = stats(ob)
        self.assertEqual(bpy.ops.uved.relax(), {'FINISHED'})
        after, worst1 = stats(ob)
        self.assertLessEqual(worst1, worst0 + 1e-9)


if __name__ == "__main__":
    unittest.main()
