#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Download Sketchfab model textures (public API, no login)."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Callable, Optional

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


def _best_image(images: list[dict]) -> Optional[dict]:
    if not images:
        return None

    def score(img: dict) -> int:
        w = int(img.get("width") or 0)
        h = int(img.get("height") or 0)
        size = int(img.get("size") or 0)
        return size or (w * h)

    # Prefer power-of-two full maps (skip tiny thumbs)
    usable = [
        i
        for i in images
        if int(i.get("width") or 0) >= 64 and int(i.get("height") or 0) >= 64
    ]
    pool = usable or images
    return max(pool, key=score)


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
        img = _best_image(list(tex.get("images") or []))
        if not img or not img.get("url"):
            _log(progress, f"step:tex_skip|{name}")
            continue
        url = img["url"]
        # keep extension from url or name
        ext = Path(name).suffix.lower()
        if ext not in {".png", ".jpg", ".jpeg", ".webp", ".gif"}:
            url_ext = Path(url.split("?", 1)[0]).suffix.lower()
            ext = url_ext if url_ext in {".png", ".jpg", ".jpeg", ".webp"} else ".png"
            if not name.lower().endswith(ext):
                name = f"{name}{ext}"
        # Sketchfab-like filename used by some pipelines
        fname = f"{tuid}_{name}" if tuid else name
        dest = out_dir / fname
        try:
            _log(progress, f"step:tex_item|{i}|{len(results)}|{name}")
            download_file(url, dest)
            if tuid:
                mapping[tuid] = dest
            mapping[name] = dest
            mapping[fname] = dest
            mapping[dest.name] = dest
        except Exception as e:
            _log(progress, f"step:tex_fail|{name}|{e}")

    # also write manifest
    (out_dir / "textures_manifest.json").write_text(
        json.dumps(
            {
                "uid": uid,
                "count": len(results),
                "files": [p.name for p in out_dir.glob("*") if p.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return mapping
