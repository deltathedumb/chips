"""The .mpkg format.

An .mpkg is an uncompressed zip holding one importable Python package, so a
mod can be a single file and still be an ordinary module with imports of its
own. Nothing in here loads anything: it reads and writes the container.
"""

import os
import zipfile

from pclengine import paths

#: Where a built .mpkg lands when no output path is given.
MODS_DIR = paths.MODS_DIR


def inspect_package(path):
    """(package name, source of its __init__, warning) for a .mpkg."""
    try:
        with zipfile.ZipFile(path) as bundle:
            names = bundle.namelist()
            stored = all(info.compress_type == zipfile.ZIP_STORED
                         for info in bundle.infolist())
            packages = sorted({n.split("/")[0] for n in names
                               if n.count("/") >= 1
                               and n.split("/", 1)[1] == "__init__.py"})
            if packages:
                name = packages[0]
                source = bundle.read(name + "/__init__.py").decode(
                    "utf-8", "replace")
            else:
                singles = [n for n in names
                           if n.endswith(".py") and "/" not in n]
                if not singles:
                    return None, "", "no package or module at the archive root"
                name = singles[0][:-3]
                source = bundle.read(singles[0]).decode("utf-8", "replace")
    except (OSError, zipfile.BadZipFile) as exc:
        return None, "", "not a readable zip: " + str(exc)
    warning = "" if stored else "archive is compressed; .mpkg should be stored"
    return name, source, warning


def build_package(package_dir, out_path=None):
    """Zip a package directory into an uncompressed .mpkg."""
    package_dir = os.path.abspath(package_dir.rstrip("/\\"))
    name = os.path.basename(package_dir)
    if not os.path.isfile(os.path.join(package_dir, "__init__.py")):
        raise ValueError(package_dir + " has no __init__.py")
    out_path = out_path or os.path.join(MODS_DIR, name + ".mpkg")
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_STORED) as bundle:
        for root, _dirs, files in os.walk(package_dir):
            if "__pycache__" in root:
                continue
            for filename in sorted(files):
                if filename.endswith((".pyc", ".pyo")):
                    continue
                full = os.path.join(root, filename)
                rel = os.path.relpath(full, os.path.dirname(package_dir))
                bundle.write(full, rel.replace(os.sep, "/"))
    return out_path
