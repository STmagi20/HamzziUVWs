# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 StudyingHamzzi

"""UV menu entry and keymap slots.

The tools are listed under UV > Hamzzi UV Toolkit in the UV editor. Stitch Selected and
Detach Selected also get a keymap entry with no key assigned, so they show up under
Preferences > Keymap (search "Hamzzi") and the user picks the key. No default key is
taken, so nothing in an existing keymap can clash."""

import bpy
from bpy.types import Menu

from .info import ADDON_NAME

# (operator, keymap name) pairs that get an empty keymap slot
KEYMAP_SLOTS = (
    ("uved.stitch_selected", "UV Editor"), ("uved.detach_selected", "UV Editor"),
    ("uved.stitch_selected", "Mesh"), ("uved.detach_selected", "Mesh"),
)

_slots = []


def _op(layout, idname, text, icon='NONE', **props):
    o = layout.operator(idname, text=text, icon=icon)
    for k, v in props.items():
        setattr(o, k, v)
    return o


class UVED_MT_menu(Menu):
    bl_idname = "UVED_MT_menu"
    bl_label = ADDON_NAME

    def draw(self, context):
        lay = self.layout
        lay.label(text="Islands")
        for mode, text in (('LEFT', "Align Left"), ('CENTER_H', "Align Center"), ('RIGHT', "Align Right"),
                           ('BOTTOM', "Align Bottom"), ('CENTER_V', "Align Middle"), ('TOP', "Align Top")):
            _op(lay, "uved.align_islands", text, mode=mode)
        lay.separator()
        _op(lay, "uved.distribute_islands", "Distribute U", axis='U')
        _op(lay, "uved.distribute_islands", "Distribute V", axis='V')
        _op(lay, "uved.sort_islands", "Sort U", axis='U')
        _op(lay, "uved.sort_islands", "Sort V", axis='V')
        lay.separator()
        lay.operator("uved.move_to_tile", text="Move to Tile")
        lay.operator("uved.pack_to_tile", text="Pack into Tile", icon='MOD_ARRAY')
        lay.separator()
        lay.label(text="Transform")
        _op(lay, "uved.transform_islands", "Rotate 90° CCW", mode='CCW90')
        _op(lay, "uved.transform_islands", "Rotate 90° CW", mode='CW90')
        _op(lay, "uved.transform_islands", "Rotate 180°", mode='ROT180')
        _op(lay, "uved.transform_islands", "Flip H", mode='FLIP_H')
        _op(lay, "uved.transform_islands", "Flip V", mode='FLIP_V')
        _op(lay, "uved.auto_orient", "Auto H", target='HORIZONTAL')
        _op(lay, "uved.auto_orient", "Auto V", target='VERTICAL')
        lay.operator("uved.orient_to_edge", text="Orient to Edge")
        lay.separator()
        lay.label(text="Texel Density")
        _op(lay, "uved.set_density", "Apply Target", source='VALUE')
        _op(lay, "uved.set_density", "Equalize", source='AVERAGE')
        _op(lay, "uved.set_density", "Match Active", source='ACTIVE')
        lay.separator()
        lay.label(text="UV Vertices")
        lay.operator("uved.straighten_edges", text="Straighten", icon='IPO_LINEAR')
        lay.separator()
        lay.label(text="Seams")
        lay.operator("uved.stitch_selected", icon='AUTOMERGE_ON')
        lay.operator("uved.detach_selected", icon='AUTOMERGE_OFF')
        lay.separator()
        lay.operator("uved.relax", icon='MOD_SMOOTH')


def _draw_in_uv_menu(self, context):
    self.layout.separator()
    self.layout.menu(UVED_MT_menu.bl_idname, text=ADDON_NAME)


def _add_keymap_slots():
    kc = bpy.context.window_manager.keyconfigs.addon
    if kc is None:                  # a background Blender has no add-on key configuration
        return
    for idname, name in KEYMAP_SLOTS:
        km = kc.keymaps.get(name) or kc.keymaps.new(name=name, space_type='EMPTY')
        _slots.append((km, km.keymap_items.new(idname, 'NONE', 'PRESS')))


def register():
    bpy.types.IMAGE_MT_uvs.append(_draw_in_uv_menu)
    _add_keymap_slots()


def unregister():
    for km, kmi in _slots:
        try:
            km.keymap_items.remove(kmi)
        except (RuntimeError, ReferenceError):
            pass
    _slots.clear()
    bpy.types.IMAGE_MT_uvs.remove(_draw_in_uv_menu)
