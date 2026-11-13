# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 StudyingHamzzi

"""Select the faces that are mirrored (flipped) in UV space."""

import bmesh
from bpy.types import Operator

from ..core import EditOp, gather


def _select_in_mesh(o, faces):
    """UV sync on: the mesh selection is what the UV editor shows."""
    bm = o.bm
    for v in bm.verts:
        v.select_set(False)
    for e in bm.edges:
        e.select_set(False)
    for f in bm.faces:
        f.select_set(False)
    for f in faces:
        f.select_set(True)
    bm.select_mode = {'FACE'}
    bm.select_flush_mode()
    if hasattr(bm, "uv_select_sync_valid"):
        bm.uv_select_sync_valid = False      # let Blender rebuild the UV selection from the mesh


def _select_in_uv(o, faces):
    """UV sync off: leave the mesh selection alone and change only what is selected in UV space."""
    bm = o.bm
    shown = [f for f in bm.faces if o.visible(f)]
    chosen = set(faces)
    if hasattr(bmesh.types.BMLoop, "uv_select_vert"):          # Blender 5.x
        for f in shown:
            f.uv_select_set(f in chosen)
        for f in shown:
            for l in f.loops:
                l.uv_select_edge_set(f in chosen)
        for f in shown:
            for l in f.loops:
                l.uv_select_vert_set(f in chosen)
    else:                                                        # Blender 4.x
        uv = o.uv
        for f in shown:
            on = f in chosen
            for l in f.loops:
                l[uv].select = on
                l[uv].select_edge = on


class UVED_OT_select_flipped(EditOp, Operator):
    bl_idname = "uved.select_flipped"
    bl_label = "Select Flipped"
    bl_description = ("Select the faces that are mirrored in UV space (their UV outline runs "
                      "clockwise, like the back of a face). Everything else is deselected")

    def execute(self, context):
        found = []
        objs = gather(context)
        for o in objs:
            found.append((o, o.flipped_faces()))
        total = sum(len(f) for _, f in found)
        if not total:
            self.report({'INFO'}, "No flipped faces")
            return {'CANCELLED'}
        ts = context.tool_settings
        if ts.use_uv_select_sync:
            # In vertex or edge mode a face whose points are all selected through its
            # neighbours would be selected too. Face mode selects exactly these faces.
            ts.mesh_select_mode = (False, False, True)
        for o, faces in found:
            if o.sync:
                _select_in_mesh(o, faces)
            else:
                _select_in_uv(o, faces)
            o.update()
        self.report({'INFO'}, f"{total} flipped face{'s' if total != 1 else ''} selected")
        return {'FINISHED'}
