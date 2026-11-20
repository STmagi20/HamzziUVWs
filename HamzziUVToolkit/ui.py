# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 StudyingHamzzi

"""Sidebar panels - one collapsible panel per tool group."""

from bpy.types import Panel

from . import icons
from .info import ADDON_AUTHOR, ADDON_NAME, ADDON_VERSION


def _op(layout, idname, text, icon='NONE', **props):
    o = layout.operator(idname, text=text, icon=icon)
    for k, v in props.items():
        setattr(o, k, v)
    return o


def _icon_grid(layout, columns=6):
    """One evenly spread row of icon-only buttons."""
    return layout.grid_flow(row_major=True, columns=columns, even_columns=True,
                            even_rows=True, align=True)


def _ui_align(layout, s):
    layout.prop(s, "align_relative", expand=True)
    g = _icon_grid(layout)
    for icon, mode in (('ALIGN_LEFT', 'LEFT'), ('ALIGN_CENTER', 'CENTER_H'), ('ALIGN_RIGHT', 'RIGHT'),
                       ('ALIGN_BOTTOM', 'BOTTOM'), ('ALIGN_MIDDLE', 'CENTER_V'), ('ALIGN_TOP', 'TOP')):
        _op(g, "uved.align_islands", "", icon, mode=mode)


def _ui_distribute(layout, s):
    layout.prop(s, "gap_mode", expand=True)
    if s.gap_mode == 'FIXED':
        layout.prop(s, "gap")
    r = layout.row(align=True)
    _op(r, "uved.distribute_islands", "Distribute U", axis='U')
    _op(r, "uved.distribute_islands", "Distribute V", axis='V')
    layout.separator()
    r = layout.row(align=True)
    r.prop(s, "sort_axis", expand=True)
    r.prop(s, "sort_reverse", text="", icon='ARROW_LEFTRIGHT', toggle=True)
    r = layout.row(align=True)
    _op(r, "uved.sort_islands", "Sort U", axis='U')
    _op(r, "uved.sort_islands", "Sort V", axis='V')


def _ui_tile(layout, s):
    r = layout.row(align=True)
    r.prop(s, "tile_u")
    r.prop(s, "tile_v")
    layout.operator("uved.move_to_tile", text="Move to Tile")
    layout.separator()
    r = layout.row(align=True)
    r.prop(s, "pack_margin")
    r.prop(s, "pack_fit", toggle=True)
    layout.operator("uved.pack_to_tile", text="Pack into Tile", icon='MOD_ARRAY')


def _ui_rotate(layout, s):
    c = layout.column(align=True)
    r = c.row(align=True)
    _op(r, "uved.transform_islands", "90°", 'LOOP_BACK', mode='CCW90')
    _op(r, "uved.transform_islands", "90°", 'LOOP_FORWARDS', mode='CW90')
    _op(r, "uved.transform_islands", "180°", mode='ROT180')
    r = c.row(align=True)
    _op(r, "uved.transform_islands", "Flip H", mode='FLIP_H')
    _op(r, "uved.transform_islands", "Flip V", mode='FLIP_V')
    _ui_flipped(layout, s)
    r = layout.row(align=True)
    r.prop(s, "rot_angle", text="")
    _op(r, "uved.transform_islands", "Rotate", mode='ANGLE')
    r = layout.row(align=True)
    _op(r, "uved.auto_orient", "Auto H", target='HORIZONTAL')
    _op(r, "uved.auto_orient", "Auto V", target='VERTICAL')
    r.operator("uved.orient_to_edge", text="To Edge")
    layout.separator()
    _ui_scale(layout, s)


def _ui_density(layout, s):
    layout.prop(s, "texture_size")
    r = layout.row(align=True)
    r.prop(s, "target_density")
    r.operator("uved.get_density", text="", icon='EYEDROPPER')
    if s.readout:
        layout.label(text=s.readout, icon='INFO')
    r = layout.row(align=True)
    _op(r, "uved.set_density", "Apply", source='VALUE')
    _op(r, "uved.set_density", "Equalize", source='AVERAGE')
    _op(r, "uved.set_density", "Active", source='ACTIVE')


def _ui_scale(layout, s):
    r = layout.row(align=True)
    r.prop(s, "scale_u")
    r.prop(s, "scale_v")
    r = layout.row()
    r.enabled = abs(s.scale_u - 1.0) > 1e-6 or abs(s.scale_v - 1.0) > 1e-6
    r.operator("uved.scale_islands", text="Scale")


def _ui_vertices(layout, s):
    g = _icon_grid(layout)
    for icon, mode in (('ALIGN_LEFT', 'U_MIN'), ('ALIGN_CENTER', 'U_AVG'), ('ALIGN_RIGHT', 'U_MAX'),
                       ('ALIGN_BOTTOM', 'V_MIN'), ('ALIGN_MIDDLE', 'V_AVG'), ('ALIGN_TOP', 'V_MAX')):
        _op(g, "uved.align_elements", "", icon, mode=mode)
    r = layout.row(align=True)
    _op(r, "uved.distribute_elements", "Distribute U", axis='U')
    _op(r, "uved.distribute_elements", "Distribute V", axis='V')
    layout.operator("uved.straighten_edges", text="Straighten", icon='IPO_LINEAR')


def _ui_stitch(layout, s):
    layout.prop(s, "stitch_bias", slider=True)
    r = layout.row(align=True)
    r.prop(s, "stitch_align", text="Align", toggle=True)
    r.prop(s, "stitch_scale", text="Scale", toggle=True)
    layout.operator("uved.stitch_selected", icon='AUTOMERGE_ON')
    layout.operator("uved.detach_selected", icon='AUTOMERGE_OFF')


def _ui_unstretch(layout, s):
    layout.prop(s, "relax_method", expand=True)
    layout.prop(s, "relax_blend", slider=True)
    layout.prop(s, "relax_pin_boundary")
    layout.operator("uved.relax", icon='MOD_SMOOTH')
    r = layout.row(align=True)
    r.prop(s, "stretch_type", text="")
    r.operator("uved.toggle_stretch")


def _ui_flipped(layout, s):
    r = layout.row(align=True)
    r.prop(s, "show_flipped", text="Show Flipped")
    sub = r.row(align=True)
    sub.enabled = s.show_flipped
    sub.prop(s, "flipped_color", text="")


def _ui_display(layout, s):
    r = layout.row(align=True)
    r.prop(s, "show_links", text="Show")
    sub = r.row(align=True)
    sub.enabled = s.show_links
    sub.prop(s, "link_color", text="")
    if s.show_links:
        layout.prop(s, "link_width")
        layout.prop(s, "link_limit")


def _ui_title(layout, s):
    """The title panel is only its header; nothing to draw in the body."""


def _title_header(layout):
    # Blender draws the panel label (bl_label) right after the header icon.
    logo = icons.logo_id()
    if logo:
        layout.label(text="", icon_value=logo)
    else:
        layout.label(text="", icon='UV')


def _ui_about(layout, s):
    mascot = icons.mascot_id()
    if mascot:
        split = layout.split(factor=0.74)
        c = split.column(align=True)
    else:
        c = layout.column(align=True)
    c.label(text=f"버전: v{ADDON_VERSION}", icon='INFO')
    logo = icons.logo_id()
    if logo:
        c.label(text=f"제작: {ADDON_AUTHOR}", icon_value=logo)
    else:
        c.label(text=f"제작: {ADDON_AUTHOR}", icon='USER')
    if mascot:
        split.template_icon(icon_value=mascot, scale=icons.MASCOT_SCALE)


# (key, panel title, draw function, panel options)
_SECTIONS = (
    ("title", ADDON_NAME, _ui_title),
    ("align", "Align Islands", _ui_align),
    ("distribute", "Distribute / Sort", _ui_distribute),
    ("tile", "Tile / Pack", _ui_tile),
    ("rotate", "Transform", _ui_rotate),
    ("density", "Texel Density", _ui_density),
    ("vertices", "UV Vertices", _ui_vertices),
    ("stitch", "Stitch", _ui_stitch),
    ("unstretch", "Unstretch", _ui_unstretch),
    ("display", "Connected Edges", _ui_display, {'DEFAULT_CLOSED'}),
    ("about", "About", _ui_about, {'DEFAULT_CLOSED'}),
)


class _SectionPanel:
    bl_region_type = 'UI'
    bl_category = ADDON_NAME

    @classmethod
    def poll(cls, context):
        return context.mode == 'EDIT_MESH'

    def draw(self, context):
        type(self).section(self.layout, context.scene.uved)

    def draw_header(self, context):
        if type(self).section is _ui_title:
            _title_header(self.layout)


def _make_panels():
    out = []
    for order, (key, label, fn, *opts) in enumerate(_SECTIONS):
        for space, tag in (('VIEW_3D', "view3d"), ('IMAGE_EDITOR', "image")):
            name = f"UVED_PT_{tag}_{key}"
            out.append(type(name, (_SectionPanel, Panel), {
                "bl_idname": name, "bl_label": label, "bl_space_type": space,
                "bl_order": order, "section": staticmethod(fn),
                "bl_options": set(opts[0]) if opts else set(),
            }))
    return tuple(out)


panel_classes = _make_panels()
