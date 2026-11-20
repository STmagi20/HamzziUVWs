"""UV editor displays: connected edges, the redraw cache and where the notice goes.

Drawing itself needs a UV editor, which a background Blender does not have; these check
the geometry, the cache key and the layout maths."""
import types
import unittest

import bmesh
import bpy

import helpers
from HamzziUVToolkit import overlay


def cube():
    """The default cube (its UVs are split along seams), in Edit Mode, nothing selected."""
    helpers.fresh()
    bpy.ops.mesh.primitive_cube_add()
    ob = bpy.context.object
    helpers.enter_edit([ob], sync=True)
    bpy.ops.mesh.select_all(action='DESELECT')
    return ob


def edges_split_from(face, uv):
    """How many edges of `face` continue at another UV position on the other side."""
    n = 0
    for l in face.loops:
        o = next(x for x in l.edge.link_loops if x.face is not face)
        a, b = o[uv].uv, o.link_loop_next[uv].uv
        if o.vert is not l.vert:
            a, b = b, a
        if (a - l[uv].uv).length > 1e-5 or (b - l.link_loop_next[uv].uv).length > 1e-5:
            n += 1
    return n


def uv_selected(l, uv):
    return l.uv_select_vert if hasattr(l, "uv_select_vert_set") else l[uv].select


def set_uv_select(l, uv, state):
    if hasattr(l, "uv_select_vert_set"):        # Blender 5.x
        l.uv_select_vert_set(state)
    else:
        l[uv].select = state


class ConnectedEdges(unittest.TestCase):
    def tearDown(self):
        helpers.leave_edit()

    def test_one_face_shows_the_edges_that_continue_elsewhere(self):
        ob = cube()
        bpy.ops.mesh.select_mode(type='FACE')
        bm = bmesh.from_edit_mesh(ob.data)
        uv = bm.loops.layers.uv.active
        face = max(bm.faces, key=lambda f: edges_split_from(f, uv))
        expected = edges_split_from(face, uv)
        self.assertGreater(expected, 0)
        face.select_set(True)
        bmesh.update_edit_mesh(ob.data)
        lines, points = overlay.link_geometry(bpy.context, 1000)
        self.assertEqual((len(lines) // 2, points), (expected, []))

    def test_everything_selected_shows_nothing(self):
        cube()
        bpy.ops.mesh.select_all(action='SELECT')
        self.assertEqual(overlay.link_geometry(bpy.context, 1000), ([], []))

    def test_one_uv_vertex_shows_the_other_uv_positions_of_its_vertex(self):
        ob = cube()
        bpy.ops.mesh.select_all(action='SELECT')
        ts = bpy.context.tool_settings
        ts.use_uv_select_sync = False
        ts.uv_select_mode = 'VERTEX'
        bm = bmesh.from_edit_mesh(ob.data)
        uv = bm.loops.layers.uv.active
        for f in bm.faces:
            for l in f.loops:
                set_uv_select(l, uv, False)
        bm.verts.ensure_lookup_table()
        v = bm.verts[0]
        picked = v.link_loops[0]
        set_uv_select(picked, uv, True)
        spot = lambda p: tuple(round(c, 5) for c in p)      # noqa: E731
        others = {spot(l[uv].uv) for l in v.link_loops} - {spot(picked[uv].uv)}
        self.assertGreater(len(others), 0)
        lines, points = overlay.link_geometry(bpy.context, 1000)
        self.assertEqual(lines, [])
        self.assertEqual({spot(p) for p in points}, others)

    def test_over_the_face_limit_returns_none(self):
        cube()
        self.assertIsNone(overlay.link_geometry(bpy.context, 5))


class Cache(unittest.TestCase):
    def setUp(self):
        self.ob = cube()
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.context.tool_settings.use_uv_select_sync = False
        self.bm = bmesh.from_edit_mesh(self.ob.data)
        self.bm.verts.ensure_lookup_table()
        self.bm.faces.ensure_lookup_table()
        self.uv = self.bm.loops.layers.uv.active

    def tearDown(self):
        overlay.clear_cache()
        helpers.leave_edit()

    def key(self):
        return overlay.state_key(bpy.context, overlay.uv_objects(bpy.context, 1000))

    def test_key_stays_the_same_while_nothing_changes(self):
        self.assertEqual(self.key(), self.key())

    def test_key_follows_a_uv_move_and_comes_back(self):
        k0 = self.key()
        l = self.bm.faces[0].loops[0]
        old = l[self.uv].uv.copy()
        l[self.uv].uv = (old.x + 0.01, old.y)
        self.assertNotEqual(self.key(), k0)
        l[self.uv].uv = old
        self.assertEqual(self.key(), k0)

    def test_key_follows_a_uv_only_selection(self):
        k0 = self.key()
        l = self.bm.faces[0].loops[0]
        set_uv_select(l, self.uv, not uv_selected(l, self.uv))
        self.assertNotEqual(self.key(), k0)

    def test_key_follows_mesh_selection_hiding_and_vertex_moves(self):
        for change in (lambda: self.bm.verts[0].select_set(False),
                       lambda: setattr(self.bm.faces[1], "hide", True),
                       lambda: setattr(self.bm.verts[2], "co", (5.0, 5.0, 5.0))):
            with self.subTest(change=change):
                k0 = self.key()
                change()
                self.assertNotEqual(self.key(), k0)

    def test_key_follows_the_select_mode_settings(self):
        k0 = self.key()
        bpy.context.tool_settings.use_uv_select_sync = True
        self.assertNotEqual(self.key(), k0)

    def test_result_is_worked_out_once_per_key(self):
        calls = []

        def compute():
            calls.append(1)
            return len(calls)
        self.assertEqual(overlay.cached("x", "k1", compute), 1)
        self.assertEqual(overlay.cached("x", "k1", compute), 1)
        self.assertEqual(overlay.cached("x", "k2", compute), 2)
        self.assertEqual(len(calls), 2)


def region(type_, x, y, w, h):
    return types.SimpleNamespace(type=type_, x=x, y=y, width=w, height=h)


class Layout(unittest.TestCase):
    def test_uv_units_to_pixels(self):
        # 100 px per UV unit, UV (0.5, 0.25) at the bottom left corner
        view2d = types.SimpleNamespace(region_to_view=lambda x, y: (x / 100 + 0.5, y / 100 + 0.25))
        (ox, oy), (sx, sy) = overlay.uv_to_pixels(view2d, 800, 600)
        self.assertAlmostEqual(sx, 100.0)
        self.assertAlmostEqual(sy, 100.0)
        self.assertAlmostEqual(ox + 0.5 * sx, 0.0)
        self.assertAlmostEqual(oy + 0.25 * sy, 0.0)
        self.assertAlmostEqual(ox + 2.5 * sx, 200.0)

    def test_notice_clears_a_tool_shelf_and_header_drawn_over_the_editor(self):
        win = region('WINDOW', 0, 0, 800, 600)
        regions = [win, region('TOOLS', 0, 0, 60, 600), region('HEADER', 0, 574, 800, 26)]
        x, y = overlay.notice_origin(regions, win, 1.0)
        self.assertEqual((x, y), (72.0, 600 - 26 - 20.0))

    def test_notice_ignores_a_tool_shelf_beside_the_editor(self):
        win = region('WINDOW', 60, 0, 740, 574)
        regions = [win, region('TOOLS', 0, 0, 60, 574), region('HEADER', 0, 574, 800, 26)]
        x, y = overlay.notice_origin(regions, win, 1.0)
        self.assertEqual((x, y), (12.0, 574 - 20.0))

    def test_notice_follows_the_ui_scale(self):
        win = region('WINDOW', 0, 0, 800, 600)
        self.assertEqual(overlay.notice_origin([win], win, 2.0), (24.0, 560.0))


if __name__ == "__main__":
    unittest.main()
