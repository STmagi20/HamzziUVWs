# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 StudyingHamzzi

"""Unstretch: relax the selected UVs and toggle the stretch overlay."""

import traceback

import bmesh
import bpy
import numpy as np
from bpy.props import BoolProperty, EnumProperty, FloatProperty
from bpy.types import Operator

from ..core import EditOp, face_winding, gather


def _fit_back(old, new):
    """Similarity transform (rotation, uniform scale, shift) that maps `new` onto `old`."""
    mx, my = old.mean(axis=0), new.mean(axis=0)
    X, Y = old - mx, new - my
    denom = (Y ** 2).sum()
    if denom < 1e-18:
        return new
    U, S, Vt = np.linalg.svd(X.T @ Y)
    d = 1.0 if np.linalg.det(U @ Vt) >= 0 else -1.0
    D = np.diag([1.0, d])
    R = U @ D @ Vt
    k = (S * np.diag(D)).sum() / denom
    # Y is already centred on `my`, so only the old centre has to be added back
    return (k * (R @ Y.T)).T + mx


def _save_mesh_state(o):
    bm = o.bm
    bm.faces.ensure_lookup_table()
    bm.edges.ensure_lookup_table()
    bm.faces.index_update()
    bm.edges.index_update()
    st = {
        "v": [v.select for v in bm.verts],
        "e": [e.select for e in bm.edges],
        "f": [f.select for f in bm.faces],
        "seam": [e.seam for e in bm.edges],
        "pin": [[l[o.uv].pin_uv for l in f.loops] for f in bm.faces],
        "active": bm.faces.active.index if bm.faces.active else -1,
        "uvsel": None,
        "uv_sync": o.uv_sync,
        "mode": set(bm.select_mode),
    }
    if (not o.sync or o.uv_sync) and hasattr(bmesh.types.BMLoop, "uv_select_vert"):
        st["uvsel"] = [(f.uv_select, [(l.uv_select_vert, l.uv_select_edge) for l in f.loops])
                       for f in bm.faces]
    return st


def _restore_mesh_state(o, st):
    bm = bmesh.from_edit_mesh(o.ob.data)
    o.bm = bm
    uv = bm.loops.layers.uv.active
    bm.faces.ensure_lookup_table()
    bm.edges.ensure_lookup_table()
    bm.verts.ensure_lookup_table()
    bm.select_mode = st["mode"]
    for v in bm.verts:
        v.select_set(False)
    for e in bm.edges:
        e.select_set(False)
    for f in bm.faces:
        f.select_set(False)
    for v, s in zip(bm.verts, st["v"]):
        if s:
            v.select_set(True)
    for e, s in zip(bm.edges, st["e"]):
        if s:
            e.select_set(True)
    for f, s in zip(bm.faces, st["f"]):
        if s:
            f.select_set(True)
    for e, s in zip(bm.edges, st["seam"]):
        e.seam = s
    for f, pins in zip(bm.faces, st["pin"]):
        for l, p in zip(f.loops, pins):
            l[uv].pin_uv = p
    if st["active"] >= 0:
        bm.faces.active = bm.faces[st["active"]]
    bm.select_flush_mode()
    if st["uvsel"] is not None:
        # clearing an edge or face flag also clears its vertex flags, so the
        # vertex flags go last, in a pass of their own
        for f, (fs, ls) in zip(bm.faces, st["uvsel"]):
            f.uv_select_set(fs)
        for f, (fs, ls) in zip(bm.faces, st["uvsel"]):
            for l, (sv, se) in zip(f.loops, ls):
                l.uv_select_edge_set(se)
        for f, (fs, ls) in zip(bm.faces, st["uvsel"]):
            for l, (sv, se) in zip(f.loops, ls):
                l.uv_select_vert_set(sv)
        if st["uv_sync"]:
            bm.uv_select_sync_valid = True
    bmesh.update_edit_mesh(o.ob.data, loop_triangles=False, destructive=False)


def _run_unwrap(context, method):
    """Run uv.unwrap as if from a 3D viewport.

    Called from inside the UV editor, Blender's unwrap works from the UV selection and
    the existing UVs and returns a different, distorted result (a square face came back
    as a kite). From any other editor it solves from the 3D shape, which is what Relax
    needs. The buttons sit in the UV editor sidebar, so step out of that area here."""
    win = context.window
    areas = list(win.screen.areas) if win else []
    area = (next((a for a in areas if a.type == 'VIEW_3D'), None)
            or next((a for a in areas if a.type != 'IMAGE_EDITOR'), None))
    if area is None:
        return bpy.ops.uv.unwrap(method=method, fill_holes=True, margin=0.0)
    with context.temp_override(window=win, area=area):
        return bpy.ops.uv.unwrap(method=method, fill_holes=True, margin=0.0)


def _make_plans(objs, pin_boundary):
    """One plan per island that holds selected UV vertices.

    Returns (plans, closed, outline_only): `closed` counts islands that cannot be
    solved, `outline_only` is True when only outline vertices were selected."""
    plans = []
    outline_only = False
    closed = 0
    for o in objs:
        for isl in o.islands():
            inner = set(isl.joined)

            def on_outline(l):
                # a corner touches the island outline when either of its two edges
                # is not joined to a neighbour face inside the same island
                return l.edge not in inner or l.link_loop_prev.edge not in inner

            selected = {(f.index, k) for f in isl.faces for k, l in enumerate(f.loops)
                        if o.selected(l)}
            if selected and not any(on_outline(l) for f in isl.faces for l in f.loops):
                # every edge is joined in UV space (a folded, closed island): the
                # unwrap has no boundary to solve from and would fail
                closed += 1
                continue
            free = ({(f.index, k) for f in isl.faces for k, l in enumerate(f.loops)
                     if (f.index, k) in selected and not on_outline(l)}
                    if pin_boundary else selected)
            if not free:
                outline_only = outline_only or bool(selected)
                continue
            pts = np.array([tuple(l[o.uv].uv) for f in isl.faces for l in f.loops])
            fixed = sum(1 for f in isl.faces for k, l in enumerate(f.loops)
                        if (f.index, k) not in free or l[o.uv].pin_uv)
            plans.append({
                "o": o, "faces": [f.index for f in isl.faces],
                "edges": [e.index for e in isl.joined], "free": free,
                "old": pts, "fixed": fixed,
                "wind": sum(face_winding(f, o.uv) for f in isl.faces),
            })
    return plans, closed, outline_only


def _prepare_unwrap(objs, plans):
    """Set up selection, pins and seams so the unwrap solves only the planned islands."""
    for o in objs:
        # Face mode, so that selecting the faces of the islands being relaxed
        # cannot pull in a neighbouring face whose corners are all selected
        # (vertex mode would): that face would be solved without any pins.
        o.bm.select_mode = {'FACE'}
        if o.uv_sync:
            # the unwrap below must follow the mesh selection we set up
            o.bm.uv_select_sync_valid = False
        for v in o.bm.verts:
            v.select_set(False)
        for e in o.bm.edges:
            e.select_set(False)
        for f in o.bm.faces:
            f.select_set(False)
    for p in plans:
        bm, uv = p["o"].bm, p["o"].uv
        for fi in p["faces"]:
            f = bm.faces[fi]
            f.select_set(True)
            for k, l in enumerate(f.loops):
                if (fi, k) not in p["free"]:
                    l[uv].pin_uv = True      # must not move
        for ei in p["edges"]:
            bm.edges[ei].seam = False        # keep the island in one piece
    for o in objs:
        # Edges that are cut in UV space must be seams for the unwrap, even when
        # the mesh has no seam there (a default UV sphere, for example). Without
        # them a closed mesh has no boundary and the solve fails. Seams are put
        # back from the saved state afterwards.
        sel = {fi for p in plans if p["o"] is o for fi in p["faces"]}
        joined = {ei for p in plans if p["o"] is o for ei in p["edges"]}
        for e in o.bm.edges:
            if e.index in joined:
                continue
            if sum(1 for f in e.link_faces if f.index in sel) >= 2:
                e.seam = True
    for o in objs:
        o.bm.select_flush_mode()
        o.update()


def _apply_result(objs, plans, amount):
    """Blend the solved UVs of the free vertices in. Returns the number of islands
    whose solve failed (those keep their old UVs)."""
    for o in objs:
        o.bm = bmesh.from_edit_mesh(o.ob.data)
        o.uv = o.bm.loops.layers.uv.active
        o.bm.faces.ensure_lookup_table()
    failed = 0
    for p in plans:
        bm, uv = p["o"].bm, p["o"].uv
        loops = [(fi, k, l) for fi in p["faces"] for k, l in enumerate(bm.faces[fi].loops)]
        new = np.array([tuple(l[uv].uv) for _, _, l in loops])
        spread = new.max(axis=0) - new.min(axis=0)
        if not np.isfinite(new).all() or spread.max() < 1e-9:
            new = p["old"]      # the solve failed: keep the UVs as they were
            failed += 1
        elif p["fixed"] < 2:
            # nothing was pinned: put the island back where it was
            if sum(face_winding(bm.faces[fi], uv) for fi in p["faces"]) * p["wind"] < 0:
                new = new * (-1.0, 1.0)
            new = _fit_back(p["old"], new)
        for (fi, k, l), a, b in zip(loops, p["old"], new):
            if (fi, k) in p["free"]:
                l[uv].uv = tuple(a + (b - a) * amount)
    return failed


def _restore_all(objs, saved):
    """Put every object's selection, seams and pins back. An error on one object
    does not stop the others; returns the names of objects that failed."""
    failed = []
    for o in objs:
        try:
            _restore_mesh_state(o, saved[o.ob.name])
        except Exception:
            traceback.print_exc()
            failed.append(o.ob.name)
    return failed


class UVED_OT_relax(EditOp, Operator):
    bl_idname = "uved.relax"
    bl_label = "Relax / Unstretch"
    bl_description = ("Re-solve the selected UV vertices from the 3D shape so they are no "
                      "longer stretched. Unselected and pinned UVs stay where they are")

    # Own copies of the panel values, so they can be changed in the Adjust Last Operation
    # panel after the run. Pressing the button starts them from the panel (see invoke).
    method: EnumProperty(
        name="Method", default='ANGLE_BASED',
        items=[('ANGLE_BASED', "Angle Based", "Preserves angles, good general choice"),
               ('CONFORMAL', "Conformal", "Preserves shape, may change scale")])
    pin_boundary: BoolProperty(
        name="Pin Boundary", default=True,
        description="Keep the outline of each island where it is and relax only the inner "
                    "vertices, so islands do not change shape or overlap. When off, the whole "
                    "selection is re-solved from the 3D shape and put back by best fit")
    blend: FloatProperty(
        name="Amount", default=1.0, min=0.0, max=1.0, subtype='FACTOR',
        description="How far to move toward the relaxed result (1 = fully relaxed)")

    def invoke(self, context, event):
        s = context.scene.uved
        self.method, self.pin_boundary, self.blend = s.relax_method, s.relax_pin_boundary, s.relax_blend
        return self.execute(context)

    def execute(self, context):
        ts = context.tool_settings
        objs = gather(context)
        saved = {o.ob.name: _save_mesh_state(o) for o in objs}

        plans, closed, outline_only = _make_plans(objs, self.pin_boundary)
        if not plans:
            if closed:
                self.report({'WARNING'}, f"Relax could not solve {closed} island(s): they have no "
                                         "open UV border; they were left unchanged")
            elif outline_only:
                self.report({'WARNING'}, "Only outline vertices are selected - select inner vertices "
                                         "or turn off Pin Boundary")
            else:
                self.report({'WARNING'}, "Select the UV vertices you want to relax")
            return {'CANCELLED'}

        sync0 = ts.use_uv_select_sync
        ok = False
        try:
            _prepare_unwrap(objs, plans)
            ts.use_uv_select_sync = True
            res = _run_unwrap(context, self.method)
            if 'FINISHED' not in res:
                self.report({'WARNING'}, "Relax failed")
                return {'CANCELLED'}
            failed = _apply_result(objs, plans, self.blend)
            ok = failed < len(plans)
            if failed or closed:
                self.report({'WARNING'}, f"Relax could not solve {failed + closed} island(s); "
                                         "they were left unchanged")
        finally:
            ts.use_uv_select_sync = sync0
            broken = _restore_all(objs, saved)
            if broken:
                self.report({'ERROR'}, "Could not restore selection / seams / pins on "
                                       f"{', '.join(broken)} - press Ctrl+Z")
        return {'FINISHED'} if ok else {'CANCELLED'}


class UVED_OT_toggle_stretch(Operator):
    bl_idname = "uved.toggle_stretch"
    bl_label = "Show Stretch"
    bl_description = "Toggle the stretch overlay in the UV editors"

    @classmethod
    def poll(cls, context):
        return context.mode == 'EDIT_MESH'

    def execute(self, context):
        spaces = [sp.uv_editor for w in context.window_manager.windows
                  for a in w.screen.areas if a.type == 'IMAGE_EDITOR'
                  for sp in a.spaces if sp.type == 'IMAGE_EDITOR']
        if not spaces:
            self.report({'WARNING'}, "No UV editor is open")
            return {'CANCELLED'}
        state = not spaces[0].show_stretch
        for ue in spaces:
            ue.show_stretch = state
            ue.display_stretch_type = context.scene.uved.stretch_type
        return {'FINISHED'}
