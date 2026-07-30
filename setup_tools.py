#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Verify (and optionally re-download) Windows conversion tools.

The repository already ships tools under tools/ so most users can skip this.
Run only if files are missing or you want to refresh them:

  python setup_tools.py

On Linux/macOS you need Wine to execute the .exe binaries:
  sudo apt install wine64
"""

from __future__ import annotations

import os
import sys
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.abspath(__file__))

# Primary: files expected in this repo after clone
# Optional mirrors (tried only if a file is missing)
MIRRORS = [
    # Historical source (may 404 if upstream removed)
    "https://raw.githubusercontent.com/Grav1tyBoi/Sketchfab-Ripper/main",
    "https://cdn.jsdelivr.net/gh/Grav1tyBoi/Sketchfab-Ripper@main",
]

FILES = [
    "tools/binz/binzDecrypt.exe",
    "tools/OsgConv/osgconv.exe",
    "tools/OsgConv/libpng16.dll",
    "tools/OsgConv/osg202-osg.dll",
    "tools/OsgConv/osg202-osgAnimation.dll",
    "tools/OsgConv/osg202-osgDB.dll",
    "tools/OsgConv/osg202-osgFX.dll",
    "tools/OsgConv/osg202-osgGA.dll",
    "tools/OsgConv/osg202-osgManipulator.dll",
    "tools/OsgConv/osg202-osgParticle.dll",
    "tools/OsgConv/osg202-osgPresentation.dll",
    "tools/OsgConv/osg202-osgShadow.dll",
    "tools/OsgConv/osg202-osgSim.dll",
    "tools/OsgConv/osg202-osgTerrain.dll",
    "tools/OsgConv/osg202-osgText.dll",
    "tools/OsgConv/osg202-osgUI.dll",
    "tools/OsgConv/osg202-osgUtil.dll",
    "tools/OsgConv/osg202-osgViewer.dll",
    "tools/OsgConv/osg202-osgVolume.dll",
    "tools/OsgConv/osg202-osgWidget.dll",
    "tools/OsgConv/ot21-OpenThreads.dll",
    "tools/OsgConv/tiff.dll",
    "tools/OsgConv/zlib.dll",
    "tools/OsgConv/osgPlugins-3.7.0/osgdb_cfg.dll",
    "tools/OsgConv/osgPlugins-3.7.0/osgdb_dds.dll",
    "tools/OsgConv/osgPlugins-3.7.0/osgdb_fbx.dll",
    "tools/OsgConv/osgPlugins-3.7.0/osgdb_gif.dll",
    "tools/OsgConv/osgPlugins-3.7.0/osgdb_gltf.dll",
    "tools/OsgConv/osgPlugins-3.7.0/osgdb_gz.dll",
    "tools/OsgConv/osgPlugins-3.7.0/osgdb_jpeg.dll",
    "tools/OsgConv/osgPlugins-3.7.0/osgdb_obj.dll",
    "tools/OsgConv/osgPlugins-3.7.0/osgdb_osg.dll",
    "tools/OsgConv/osgPlugins-3.7.0/osgdb_osga.dll",
    "tools/OsgConv/osgPlugins-3.7.0/osgdb_osgjs.dll",
    "tools/OsgConv/osgPlugins-3.7.0/osgdb_png.dll",
    "tools/OsgConv/osgPlugins-3.7.0/osgdb_pnm.dll",
    "tools/OsgConv/osgPlugins-3.7.0/osgdb_revisions.dll",
    "tools/OsgConv/osgPlugins-3.7.0/osgdb_rgb.dll",
    "tools/OsgConv/osgPlugins-3.7.0/osgdb_tga.dll",
    "tools/OsgConv/osgPlugins-3.7.0/osgdb_tgz.dll",
    "tools/OsgConv/osgPlugins-3.7.0/osgdb_tiff.dll",
    "tools/OsgConv/osgPlugins-3.7.0/osgdb_zip.dll",
]


def _exists(rel: str) -> bool:
    dest = os.path.join(ROOT, rel.replace("/", os.sep))
    return os.path.isfile(dest) and os.path.getsize(dest) > 0


def download(rel: str) -> bool:
    dest = os.path.join(ROOT, rel.replace("/", os.sep))
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    if _exists(rel):
        print(f"ok    {rel} (already present)")
        return True

    last_err: Exception | None = None
    for base in MIRRORS:
        url = f"{base}/{rel}"
        print(f"get   {rel}  <- {base}")
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=300) as resp:
                data = resp.read()
            if not data:
                raise RuntimeError("empty response")
            with open(dest, "wb") as f:
                f.write(data)
            print(f"ok    {rel} ({len(data)} bytes)")
            return True
        except Exception as e:
            last_err = e
            print(f"      failed: {e}")

    print(f"FAIL  {rel}: {last_err}", file=sys.stderr)
    return False


def main() -> int:
    print("Checking tools in:", ROOT)
    print()

    missing = [rel for rel in FILES if not _exists(rel)]
    present = len(FILES) - len(missing)
    print(f"Present: {present}/{len(FILES)}")
    if not missing:
        print("All tools are already installed.")
        if not sys.platform.startswith("win"):
            print()
            print("Linux/macOS: ensure Wine is installed to run .exe tools:")
            print("  sudo apt install wine64")
        print()
        print("Next:  python main.py --check-tools")
        return 0

    print(f"Missing: {len(missing)} — trying mirrors…")
    print()
    failed = 0
    for rel in missing:
        if not download(rel):
            failed += 1

    print()
    if failed:
        print(f"Could not fetch {failed} file(s).", file=sys.stderr)
        print(
            "Re-clone the full repository (tools/ folder must be included),\n"
            "or copy tools/binz and tools/OsgConv from a complete checkout.",
            file=sys.stderr,
        )
        return 1

    print("Done. Tools are ready.")
    print("Next:  python main.py --check-tools")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
