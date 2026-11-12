# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 StudyingHamzzi

"""Name, author and version shown in the sidebar."""

import os
import re

ADDON_NAME = "Hamzzi UV Toolkit"
ADDON_AUTHOR = "StudyingHamzzi"


def _read_version():
    """Version from blender_manifest.toml, so it is written in one place only."""
    try:
        path = os.path.join(os.path.dirname(__file__), "blender_manifest.toml")
        with open(path, encoding="utf-8") as fh:
            m = re.search(r'^version\s*=\s*"([^"]+)"', fh.read(), re.M)
        return m.group(1) if m else "?"
    except OSError:
        return "?"


ADDON_VERSION = _read_version()
