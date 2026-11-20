# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 StudyingHamzzi

"""Texel density: measure and set."""

from bpy.props import EnumProperty, FloatProperty, IntProperty
from bpy.types import Operator

from ..core import EditOp, finish, targets


class UVED_OT_get_density(EditOp, Operator):
    bl_idname = "uved.get_density"
    bl_label = "Measure Density"
    bl_description = ("Measure the texel density of the selected islands and put the "
                      "average into Target (px/m). Does not change any UVs")

    def execute(self, context):
        s = context.scene.uved
        objs, isl = targets(context)
        d = [i.density(s.texture_size) for i in isl]
        d = [x for x in d if x > 0]
        if not d:
            self.report({'WARNING'}, "No measurable islands")
            return {'CANCELLED'}
        avg = sum(d) / len(d)
        s.target_density = avg
        if max(d) - min(d) < 0.05:
            s.readout = f"Measured: {avg:.1f} px/m ({len(d)} islands, uniform)"
        else:
            s.readout = f"Measured: {min(d):.1f} - {max(d):.1f} px/m ({len(d)} islands)"
        self.report({'INFO'}, s.readout)
        return {'FINISHED'}


class UVED_OT_set_density(EditOp, Operator):
    bl_idname = "uved.set_density"
    bl_label = "Set Texel Density"
    bl_description = ("Resize each selected island around its own center so its texel "
                      "density matches. Islands are not moved, so they may overlap")

    source: EnumProperty(
        name="Match To", default='VALUE',
        items=[('VALUE', "Target Value", "Use the Target (px/m) value"),
               ('AVERAGE', "Selection Average",
                "Make all selected islands the same density, keeping their overall size"),
               ('ACTIVE', "Active Face Island", "Copy the density of the active face's island")])

    @classmethod
    def description(cls, context, properties):
        return {
            'VALUE': "Resize each selected island so its density equals Target (px/m)",
            'AVERAGE': "Make all selected islands the same density (their average), "
                       "so the overall size stays about the same",
            'ACTIVE': "Resize the selected islands to the density of the island "
                      "that holds the active face",
        }[properties.source] + ". Islands are resized around their own center and may overlap"

    # Own copies of the panel values, so they can be changed in the Adjust Last Operation
    # panel after the run. Pressing the button starts them from the panel (panel_values).
    # Equalize and Active copy a density measured from the UVs, so only Target Value
    # offers anything to adjust.
    texture_size: IntProperty(
        name="Texture Size", default=1024, min=1, max=65536,
        description="Texture width in pixels. Only used to express density as px/m")
    target_density: FloatProperty(
        name="Target (px/m)", default=512.0, min=0.0, soft_max=8192.0,
        description="Texture pixels per metre of 3D surface")

    panel_values = (("texture_size", "texture_size"), ("target_density", "target_density"))

    def draw(self, context):
        if self.source == 'VALUE':
            self.layout.prop(self, "texture_size")
            self.layout.prop(self, "target_density")
        else:
            self.layout.label(text="Nothing to adjust: the density is measured from the UVs")

    def execute(self, context):
        objs, isl = targets(context)
        dens = [(i, i.density(self.texture_size)) for i in isl]
        dens = [(i, d) for i, d in dens if d > 0]
        if not dens:
            self.report({'WARNING'}, "No measurable islands")
            return {'CANCELLED'}
        if self.source == 'VALUE':
            target = self.target_density
            if target <= 0:
                self.report({'WARNING'}, "Target (px/m) must be above zero")
                return {'CANCELLED'}
        elif self.source == 'AVERAGE':
            target = sum(d for _, d in dens) / len(dens)
        else:
            target = 0.0
            for o in objs:
                af = o.bm.faces.active
                if af is not None:
                    for i in o.islands():
                        if af in i.faces:
                            target = i.density(self.texture_size)
            if target <= 0:
                self.report({'WARNING'}, "No active face - select a face first")
                return {'CANCELLED'}
        for i, d in dens:
            k = target / d
            cx, cy = i.center()
            i.scale(k, k, cx, cy)
        context.scene.uved.readout = ""      # the last measurement no longer describes these UVs
        finish(objs)
        self.report({'INFO'}, f"Set {len(dens)} island(s) to {target:.1f} px/m")
        return {'FINISHED'}
