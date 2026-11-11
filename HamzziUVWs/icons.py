# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 StudyingHamzzi

"""Logo image shown above the add-on name in the sidebar.

Put the picture at images/logo.png (square works best). The add-on works
without it - the title is then shown alone."""

import os

import bpy.utils.previews

LOGO_FILE = os.path.join(os.path.dirname(__file__), "images", "logo.png")
# size of the picture in the panel, in multiples of a normal button height
LOGO_SCALE = 6.0

_previews = None


def logo_id():
    """Icon id of the logo, or 0 when there is no image file."""
    if _previews is None or "logo" not in _previews:
        return 0
    return _previews["logo"].icon_id


def register():
    global _previews
    if _previews is None:
        _previews = bpy.utils.previews.new()
        if os.path.isfile(LOGO_FILE):
            _previews.load("logo", LOGO_FILE, 'IMAGE')


def unregister():
    global _previews
    if _previews is not None:
        bpy.utils.previews.remove(_previews)
        _previews = None
