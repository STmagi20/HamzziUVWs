# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 StudyingHamzzi

"""HamzziUVWs - edit UVs that are already unwrapped.

Island tools : align, distribute, move to tile, texel density, scale,
               rotate / flip, auto-orient, orient to edge.
Element tools: align / distribute selected UV vertices (straighten edges).
Stitch       : Stitch Selected - join selected UV edges to their neighbour
               islands (bias / align / scale options, like 3ds Max Unwrap UVW).
Unstretch    : relax selected UVs (pinned re-solve) and toggle the stretch overlay.
Connected    : in the UV editor, shows where the selected UV edges / faces / vertices
               continue on other islands (like the blue edges in 3ds Max).

Works in the UV Editor and the 3D Viewport (Edit Mode), with UV sync on or off,
and on several objects in Edit Mode at once. If nothing is selected, every
visible island is used.
"""

if "bpy" in locals():
    # the add-on was reloaded in a running Blender: refresh the submodules too
    import importlib
    for _m in (info, icons, core, properties, islands, density, elements, stitch, relax, overlay, ui):
        importlib.reload(_m)

import bpy
from bpy.props import PointerProperty

from . import core, icons, info, overlay, properties, ui
from .operators import density, elements, islands, relax, stitch

classes = (
    properties.UVED_Settings,
    islands.UVED_OT_align_islands, islands.UVED_OT_distribute_islands, islands.UVED_OT_move_to_tile,
    islands.UVED_OT_pack_to_tile,
    islands.UVED_OT_scale_islands, islands.UVED_OT_transform_islands,
    islands.UVED_OT_auto_orient, islands.UVED_OT_orient_to_edge,
    density.UVED_OT_get_density, density.UVED_OT_set_density,
    elements.UVED_OT_align_elements, elements.UVED_OT_distribute_elements,
    stitch.UVED_OT_stitch_selected,
    relax.UVED_OT_relax, relax.UVED_OT_toggle_stretch,
) + ui.panel_classes


def register():
    for c in classes:
        bpy.utils.register_class(c)
    bpy.types.Scene.uved = PointerProperty(type=properties.UVED_Settings)
    icons.register()
    overlay.register()


def unregister():
    overlay.unregister()
    icons.unregister()
    del bpy.types.Scene.uved
    for c in reversed(classes):
        bpy.utils.unregister_class(c)
