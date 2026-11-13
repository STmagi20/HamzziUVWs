"""Flipped Faces: finding faces mirrored in UV space, selecting them, and the fill geometry."""
import unittest

import bmesh
import bpy

import helpers
from HamzziUVToolkit import overlay
from HamzziUVToolkit.core import gather


def unwrapped_object(kind="cube"):
    bm = bmesh.new()
    if kind == "cube":
        bmesh.ops.create_cube(bm, size=2.0)
    else:                                   # one 8-sided face
        bmesh.ops.create_circle(bm, cap_ends=True, radius=1.0, segments=8)
    me = bpy.data.meshes.new(kind)
    bm.to_mesh(me)
    bm.free()
    ob = helpers.link(bpy.data.objects.new(kind, me))
    return ob


def mirror_faces(ob, indices):
    bm = bmesh.from_edit_mesh(ob.data)
    uv = bm.loops.layers.uv.active
    bm.faces.ensure_lookup_table()
    for i in indices:
        for l in bm.faces[i].loops:
            l[uv].uv.x = 10.0 - l[uv].uv.x
    bmesh.update_edit_mesh(ob.data)


def flipped_indices():
    return sorted(f.index for o in gather(bpy.context) for f in o.flipped_faces())


class FlippedFaces(unittest.TestCase):
    def setUp(self):
        helpers.fresh()

    def tearDown(self):
        helpers.leave_edit()

    def _edit(self, kind="cube", sync=True):
        ob = unwrapped_object(kind)
        helpers.enter_edit([ob], sync=sync)
        bpy.ops.uv.smart_project()
        return ob

    def test_nothing_is_flipped_after_unwrapping(self):
        self._edit()
        self.assertEqual(flipped_indices(), [])

    def test_mirrored_faces_are_found(self):
        for sync in (True, False):
            with self.subTest(sync=sync):
                helpers.fresh()
                ob = self._edit(sync=sync)
                mirror_faces(ob, [1, 4])
                self.assertEqual(flipped_indices(), [1, 4])
                helpers.leave_edit()

    def test_hidden_faces_are_not_reported(self):
        ob = self._edit()
        mirror_faces(ob, [1, 4])
        bpy.ops.mesh.select_all(action='DESELECT')
        bm = bmesh.from_edit_mesh(ob.data)
        bm.faces.ensure_lookup_table()
        bm.faces[1].hide_set(True)
        bmesh.update_edit_mesh(ob.data)
        self.assertEqual(flipped_indices(), [4])

    def test_select_with_uv_sync_selects_exactly_those_faces(self):
        ob = self._edit(sync=True)
        mirror_faces(ob, [1, 4])
        self.assertEqual(bpy.ops.uved.select_flipped(), {'FINISHED'})
        self.assertEqual(helpers.face_indices(ob), [1, 4])
        self.assertEqual(tuple(helpers.tool_settings().mesh_select_mode), (False, False, True))

    def test_select_without_uv_sync_changes_only_the_uv_selection(self):
        ob = self._edit(sync=False)
        mirror_faces(ob, [1, 4])
        self.assertEqual(bpy.ops.uved.select_flipped(), {'FINISHED'})
        self.assertEqual(helpers.face_indices(ob), [0, 1, 2, 3, 4, 5])      # mesh selection kept
        if hasattr(bmesh.types.BMFace, "uv_select"):                         # Blender 5.x
            self.assertEqual(helpers.face_indices(ob, "uv_select"), [1, 4])

    def test_neighbours_are_not_selected_along_in_vertex_mode(self):
        # a 4x4 grid: faces whose points are all selected through their neighbours
        bm = bmesh.new()
        bmesh.ops.create_grid(bm, x_segments=4, y_segments=4, size=1.0)
        me = bpy.data.meshes.new("grid")
        bm.to_mesh(me)
        bm.free()
        ob = helpers.link(bpy.data.objects.new("grid", me))
        helpers.enter_edit([ob], sync=True, select_mode='VERT')
        bpy.ops.uv.unwrap(method='ANGLE_BASED', margin=0.0)
        mirror_faces(ob, [2, 3, 9, 10, 13])
        self.assertEqual(bpy.ops.uved.select_flipped(), {'FINISHED'})
        self.assertEqual(helpers.face_indices(ob), [2, 3, 9, 10, 13])

    def test_cancelled_when_nothing_is_flipped(self):
        self._edit()
        self.assertEqual(bpy.ops.uved.select_flipped(), {'CANCELLED'})


class FlippedGeometry(unittest.TestCase):
    def setUp(self):
        helpers.fresh()

    def tearDown(self):
        helpers.leave_edit()

    def _edit(self, kind):
        ob = unwrapped_object(kind)
        helpers.enter_edit([ob], sync=True)
        bpy.ops.uv.smart_project()
        return ob

    def test_quads_make_two_triangles_each(self):
        ob = self._edit("cube")
        mirror_faces(ob, [0, 2])
        tris = overlay.flipped_geometry(bpy.context, 1000)
        self.assertEqual(len(tris) // 3, 4)

    def test_an_ngon_is_split_into_n_minus_2_triangles(self):
        ob = self._edit("ngon")
        self.assertEqual(overlay.flipped_geometry(bpy.context, 1000), [])
        mirror_faces(ob, [0])
        self.assertEqual(len(overlay.flipped_geometry(bpy.context, 1000)) // 3, 6)

    def test_over_the_face_limit_returns_none(self):
        self._edit("cube")
        self.assertIsNone(overlay.flipped_geometry(bpy.context, 0))


if __name__ == "__main__":
    unittest.main()
