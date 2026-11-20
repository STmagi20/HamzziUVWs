"""The UV menu entry and the empty keymap slots for Stitch and Detach."""
import unittest

import bpy

import helpers
from HamzziUVToolkit import menus


class Menus(unittest.TestCase):
    def test_the_menu_is_registered_and_draws_every_operator_it_names(self):
        helpers.fresh()
        self.assertTrue(hasattr(bpy.types, "UVED_MT_menu"))
        # every operator the menu uses has to exist, or drawing the menu raises
        ids = set()
        for name in dir(bpy.ops.uved):
            ids.add("uved." + name)
        import inspect
        src = inspect.getsource(menus.UVED_MT_menu.draw)
        import re
        for idname in set(re.findall(r'"(uved\.[a-z_]+)"', src)):
            with self.subTest(op=idname):
                self.assertIn(idname, ids)

    def test_keymap_slots_have_no_key(self):
        helpers.fresh()
        kc = bpy.context.window_manager.keyconfigs.addon
        if kc is None:
            self.skipTest("no add-on key configuration in this Blender")
        found = [(km.name, kmi.idname, kmi.type) for km in kc.keymaps for kmi in km.keymap_items
                 if kmi.idname.startswith("uved.")]
        self.assertEqual(sorted((n, i) for n, i, _ in found), sorted(
            (name, idname) for idname, name in menus.KEYMAP_SLOTS))
        self.assertTrue(all(t == 'NONE' for _, _, t in found))


if __name__ == "__main__":
    unittest.main()
