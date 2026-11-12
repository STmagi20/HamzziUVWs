# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 StudyingHamzzi

"""Pictures shown in the sidebar.

images/logo.png   small face, drawn in front of the add-on name at the top
images/mascot.png full-body picture, drawn in the About panel

Both are optional (square works best); without them the text is shown alone."""

import os

import bpy.utils.previews

_DIR = os.path.join(os.path.dirname(__file__), "images")
LOGO_FILE = os.path.join(_DIR, "logo.png")
MASCOT_FILE = os.path.join(_DIR, "mascot.png")
# size of the About picture, in multiples of a normal button height
MASCOT_SCALE = 2.4

_previews = None


def _icon(name):
    if _previews is None or name not in _previews:
        return 0
    return _previews[name].icon_id


def logo_id():
    """Icon id of the face logo, or 0 when there is no image file."""
    return _icon("logo")


def mascot_id():
    """Icon id of the full-body picture, or 0 when there is no image file."""
    return _icon("mascot")


def register():
    global _previews
    if _previews is None:
        _previews = bpy.utils.previews.new()
        for name, path in (("logo", LOGO_FILE), ("mascot", MASCOT_FILE)):
            if os.path.isfile(path):
                _previews.load(name, path, 'IMAGE')


def unregister():
    global _previews
    if _previews is not None:
        bpy.utils.previews.remove(_previews)
        _previews = None
