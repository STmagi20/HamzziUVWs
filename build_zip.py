"""Build the installable uv_edit_toolkit.zip (attach it to a GitHub release).

    python build_zip.py
"""
import pathlib
import zipfile

root = pathlib.Path(__file__).parent
src = root / "uv_edit_toolkit"
out = root / "uv_edit_toolkit.zip"

with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
    for name in ("__init__.py", "blender_manifest.toml"):
        z.write(src / name, name)
print(f"wrote {out}")
