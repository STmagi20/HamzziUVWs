"""Buttons start an operator from the panel values (EditOp.panel_values).

A background Blender has no window, so it never calls invoke. invoke only runs
copy_panel_values, which is checked here for every operator that has a table."""
import types
import unittest

import bpy

import helpers
from HamzziUVToolkit import core


def table_operators():
    return [c for c in core.EditOp.__subclasses__() if c.panel_values]


def rna(cls):
    group, name = cls.bl_idname.split(".")
    return getattr(getattr(bpy.ops, group), name).get_rna_type().properties


def other_value(prop):
    """A valid value of the panel property that is not its default."""
    if prop.type == 'BOOLEAN':
        return not prop.default
    if prop.type == 'ENUM':
        return next(i.identifier for i in prop.enum_items if i.identifier != prop.default)
    step = 1 if prop.type == 'INT' else 0.25
    up = prop.default + step
    return up if up <= prop.hard_max else prop.default - step


class PanelValues(unittest.TestCase):
    def setUp(self):
        helpers.fresh()

    def test_every_operator_with_panel_options_has_a_table(self):
        self.assertEqual(sorted(c.bl_idname for c in table_operators()), sorted((
            "uved.distribute_islands", "uved.sort_islands", "uved.move_to_tile",
            "uved.pack_to_tile", "uved.scale_islands", "uved.transform_islands",
            "uved.set_density", "uved.relax", "uved.stitch_selected")))

    def test_both_sides_have_the_same_type_and_default(self):
        panel = helpers.settings().bl_rna.properties
        for cls in table_operators():
            op = rna(cls)
            for mine, theirs in cls.panel_values:
                with self.subTest(op=cls.bl_idname, option=mine):
                    a, b = op[mine], panel[theirs]
                    self.assertEqual(a.type, b.type)
                    if a.type == 'FLOAT':
                        self.assertAlmostEqual(a.default, b.default, places=6)
                    else:
                        self.assertEqual(a.default, b.default)
                    if a.type == 'ENUM':
                        self.assertEqual([i.identifier for i in a.enum_items],
                                         [i.identifier for i in b.enum_items])

    def test_the_button_copies_every_panel_value(self):
        s = helpers.settings()
        panel = s.bl_rna.properties
        for cls in table_operators():
            op = rna(cls)
            for _, theirs in cls.panel_values:
                setattr(s, theirs, other_value(panel[theirs]))
            stand_in = types.SimpleNamespace(panel_values=cls.panel_values)
            core.EditOp.copy_panel_values(stand_in, s)
            for mine, theirs in cls.panel_values:
                with self.subTest(op=cls.bl_idname, option=mine):
                    value = getattr(stand_in, mine)
                    self.assertEqual(value, getattr(s, theirs))
                    self.assertNotEqual(value, op[mine].default)
                    if op[mine].type in {'INT', 'FLOAT'}:
                        self.assertTrue(op[mine].hard_min <= value <= op[mine].hard_max)


if __name__ == "__main__":
    unittest.main()
