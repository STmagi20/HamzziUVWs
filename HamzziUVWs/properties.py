# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 StudyingHamzzi

"""Scene settings shown in the panels."""

import math

from bpy.props import (
    BoolProperty, EnumProperty, FloatProperty, FloatVectorProperty, IntProperty,
    StringProperty,
)
from bpy.types import PropertyGroup


def _redraw_uv_editors(self, context):
    for w in context.window_manager.windows:
        for a in w.screen.areas:
            if a.type == 'IMAGE_EDITOR':
                a.tag_redraw()


class UVED_Settings(PropertyGroup):
    show_links: BoolProperty(
        name="Show Connected Edges", default=True, update=_redraw_uv_editors,
        description="In the UV editor, highlight where the selected UV edges, faces or "
                    "vertices continue on another island (the other side of a seam)")
    link_color: FloatVectorProperty(
        name="Color", subtype='COLOR', size=4, min=0.0, max=1.0,
        default=(0.1, 0.45, 1.0, 1.0), update=_redraw_uv_editors)
    link_width: FloatProperty(
        name="Line Width", default=3.0, min=1.0, max=10.0, update=_redraw_uv_editors)
    link_limit: IntProperty(
        name="Face Limit", default=10000, min=100, soft_max=500000,
        description="Skip the display when more faces than this are in Edit Mode, "
                    "to keep the UV editor responsive")
    align_relative: EnumProperty(
        name="Align To", default='SELECTION',
        items=[('SELECTION', "Selection", "Bounds of the selected islands"),
               ('TILE', "UV Tile", "The 0-1 tile under the selection")])
    gap_mode: EnumProperty(
        name="Spacing", default='EQUAL',
        items=[('EQUAL', "Equal Gaps", "Even gaps between the outermost islands"),
               ('FIXED', "Fixed Gap", "Use the gap value below")])
    gap: FloatProperty(name="Gap", default=0.01, min=-1.0, max=1.0, precision=4)
    sort_axis: EnumProperty(
        name="Order By", default='X',
        items=[('X', "X", "Order the islands by their X position in 3D space"),
               ('Y', "Y", "Order the islands by their Y position in 3D space"),
               ('Z', "Z", "Order the islands by their Z position in 3D space")])
    sort_reverse: BoolProperty(
        name="Reverse", default=False,
        description="Reverse the order (highest 3D position first)")
    tile_u: IntProperty(name="U", default=0)
    tile_v: IntProperty(name="V", default=0)
    pack_margin: FloatProperty(
        name="Margin", default=0.0, min=0.0, max=0.25, precision=4,
        description="Space left between the islands and along the tile border, in UV units")
    pack_fit: BoolProperty(
        name="Scale to Fit", default=True,
        description="Resize all islands by the same factor so they fill the tile. "
                    "When off, islands keep their size and are only moved")
    texture_size: IntProperty(
        name="Texture Size", default=1024, min=1, max=65536,
        description="Texture width in pixels. Only used to express density as px/m; "
                    "changing it does not move any UVs")
    target_density: FloatProperty(
        name="Target (px/m)", default=512.0, min=0.0, soft_max=8192.0,
        description="Texture pixels per metre of 3D surface. Measure fills this in")
    scale_u: FloatProperty(name="U", default=1.0, min=0.001, soft_max=10.0,
                           description="Multiply island width by this factor")
    scale_v: FloatProperty(name="V", default=1.0, min=0.001, soft_max=10.0,
                           description="Multiply island height by this factor")
    rot_angle: FloatProperty(name="Angle", default=math.radians(15.0), subtype='ANGLE')
    readout: StringProperty(name="Readout", default="")
    stretch_type: EnumProperty(
        name="Stretch", default='AREA',
        items=[('AREA', "Area", ""), ('ANGLE', "Angle", "")])
    relax_method: EnumProperty(
        name="Method", default='ANGLE_BASED',
        items=[('ANGLE_BASED', "Angle Based", "Preserves angles, good general choice"),
               ('CONFORMAL', "Conformal", "Preserves shape, may change scale")])
    relax_pin_boundary: BoolProperty(
        name="Pin Boundary", default=True,
        description="Keep the outline of each island where it is and relax only the inner "
                    "vertices, so islands do not change shape or overlap. When off, the whole "
                    "selection is re-solved from the 3D shape and put back by best fit")
    relax_blend: FloatProperty(
        name="Amount", default=1.0, min=0.0, max=1.0,
        description="How far to move toward the relaxed result (1 = fully relaxed)")
    stitch_bias: FloatProperty(
        name="Bias", default=0.0, min=0.0, max=1.0,
        description="0 = the selected island stays and the neighbour moves, "
                    "1 = the neighbour stays and the selected island moves, "
                    "0.5 = both meet in the middle")
    stitch_align: BoolProperty(
        name="Align Clusters", default=True,
        description="Rotate the moving island so the edges line up")
    stitch_scale: BoolProperty(
        name="Scale Clusters", default=True,
        description="Scale the moving island so the edges have the same length")
