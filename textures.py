#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Download Sketchfab model textures (public API, no login)."""

from __future__ import annotations

import json
import re
import tempfile
from pathlib import Path
from typing import Callable, Optional
from PIL import Image

Progress = Optional[Callable[[str], None]]


def _log(progress: Progress, msg: str) -> None:
    if progress:
        try:
            progress(msg)
        except Exception:
            pass


def fetch_texture_manifest(uid: str, http_get_json) -> list[dict]:
    data = http_get_json(f"https://sketchfab.com/i/models/{uid}/textures")
    return list(data.get("results") or [])


def _texture_variants(images: list[dict]) -> list[dict]:
    usable = []
    for image in images:
        url = image.get("url")
        if not url:
            continue
        width, height = int(image.get("width") or 0), int(image.get("height") or 0)
        key, version = image.get("pk"), image.get("pv")
        if key is not None or version is not None:
            if key is None or version != 1 or width <= 0 or height <= 0 or width % 8 or height % 8:
                continue
        usable.append(image)
    return sorted(usable, key=lambda image: (
        int(image.get("width") or 0) * int(image.get("height") or 0),
        int(image.get("size") or 0),
    ), reverse=True)


def _decode_viewer_image(image: Image.Image, key: int) -> Image.Image:
    """Restore v1 viewer tiles using the layout documented by Sketchfab Local."""
    mode = "RGBA" if "A" in image.getbands() or "transparency" in image.info else "RGB"
    source = image.convert(mode)
    result = Image.new(mode, source.size)
    columns, rows = source.width // 8, source.height // 8
    positions = []
    for diagonal in range(columns + rows - 1):
        columns_on_diagonal = range(max(0, diagonal - rows + 1), min(columns, diagonal + 1))
        if diagonal % 2:
            columns_on_diagonal = reversed(columns_on_diagonal)
        positions.extend((8 * x, 8 * (diagonal - x)) for x in columns_on_diagonal)

    forward = (None, Image.Transpose.FLIP_LEFT_RIGHT, Image.Transpose.TRANSPOSE, Image.Transpose.ROTATE_270)
    inverse = (None, Image.Transpose.FLIP_LEFT_RIGHT, Image.Transpose.TRANSPOSE, Image.Transpose.ROTATE_90)
    for output_index, position in enumerate(positions):
        input_index = (output_index - key) % len(positions)
        x, y = positions[input_index]
        tile = source.crop((x, y, x + 8, y + 8))
        if (operation := forward[input_index % 4]) is not None:
            tile = tile.transpose(operation)
        if (operation := inverse[output_index % 4]) is not None:
            tile = tile.transpose(operation)
        result.paste(tile, position)
    return result


def _safe_name(name: str) -> str:
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name or "tex")
    name = name.strip(" .") or "tex"
    return name


def download_textures(
    uid: str,
    out_dir: Path,
    *,
    http_get_json,
    download_file,
    progress: Progress = None,
) -> dict[str, Path]:
    """
    Download all textures for a model.

    Returns mapping:
      texture_uid -> local path
      and also basename / relative path keys for MTL lookup.

    Progress tokens (for i18n): step:tex_count|N , step:tex_item|i|N|name
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    results = fetch_texture_manifest(uid, http_get_json)
    mapping: dict[str, Path] = {}
    _log(progress, f"step:tex_count|{len(results)}")

    for i, tex in enumerate(results, start=1):
        tuid = str(tex.get("uid") or "")
        name = _safe_name(str(tex.get("name") or tuid or f"tex_{i}"))
        variants = _texture_variants(list(tex.get("images") or []))
        if not variants:
            _log(progress, f"step:tex_skip|{name}")
            continue

        _log(progress, f"step:tex_item|{i}|{len(results)}|{name}")
        for variant in variants:
            url = variant["url"]
            try:
                with tempfile.TemporaryDirectory(dir=out_dir) as temporary:
                    raw = Path(temporary) / "download"
                    download_file(url, raw)
                    with Image.open(raw) as image:
                        image.load()
                        expected = (variant.get("width"), variant.get("height"))
                        if all(expected) and image.size != tuple(map(int, expected)):
                            raise ValueError(f"Expected {expected}, received {image.size}")
                        key = variant.get("pk")
                        if key is not None:
                            decoded = _decode_viewer_image(image, int(key))
                            prepared = Path(temporary) / "decoded.png"
                            decoded.save(prepared)
                            extension = ".png"
                        else:
                            actual_suffix = {"JPEG": ".jpeg", "PNG": ".png", "WEBP": ".webp", "GIF": ".gif"}
                            extension = actual_suffix.get(image.format, "")
                            if not extension:
                                prepared = Path(temporary) / "decoded.png"
                                image.convert("RGBA").save(prepared)
                                extension = ".png"
                            else:
                                prepared = raw
                    filename = Path(name).stem + extension
                    dest = out_dir / (f"{tuid}_{filename}" if tuid else filename)
                    prepared.replace(dest)
            except (OSError, RuntimeError, ValueError) as error:
                _log(progress, f"step:tex_fail|{name}|{error}")
                continue
            if tuid:
                mapping[tuid] = dest
            mapping[name] = dest
            mapping[filename] = dest
            mapping[dest.name] = dest
            break

    # also write manifest
    (out_dir / "textures_manifest.json").write_text(
        json.dumps(
            {
                "uid": uid,
                "count": len(results),
                "files": sorted({path.name for path in mapping.values()}),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return mapping
