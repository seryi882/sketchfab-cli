#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Pure-Python Sketchfab OSGJS → OBJ (+ MTL) converter.

Decode path mirrors the Sketchfab web viewer:
  varint (+ zigzag) → triangle_mode → prediction → dequant → normals(nphi)
"""

from __future__ import annotations

import json
import math
import re
import struct
from pathlib import Path
from typing import Any, Optional

# Attribute flags in UserData "attributes"
ATTR = {
    "Vertex": 1,
    "Normal": 2,
    "TexCoord": 4,
    "Color": 8,
    "Triangle": 16,
    "Tangent": 32,
}

MODE_QUANT = 1  # dequant via bbl/h
MODE_PARALLELOGRAM = 2

TRI_DELTA = 1
TRI_HIGHWATER = 2
TRI_IMPLICIT = 4

IMPLICIT_HEADER_PRIMITIVE_LENGTH = 0
IMPLICIT_HEADER_MASK_LENGTH = 1
IMPLICIT_HEADER_EXPECTED_INDEX = 2
IMPLICIT_HEADER_LENGTH = 3


def _zigzag_decode(n: int) -> int:
    return (n >> 1) ^ (-(n & 1))


def _to_i32(n: int) -> int:
    """Match JS ToInt32."""
    n &= 0xFFFFFFFF
    if n >= 0x80000000:
        n -= 0x100000000
    return n


def _to_u32(n: int) -> int:
    return n & 0xFFFFFFFF


def decode_varint(buf: bytes | memoryview, count: int, type_name: str) -> list[int]:
    """JS-compatible varint reader (H+3W). Bit ops are 32-bit like JS."""
    out = [0] * count
    o = 0
    signed = not type_name.startswith("U")
    for a in range(count):
        s = 0
        shift = 0
        while True:
            if o >= len(buf):
                raise ValueError(f"varint overflow at element {a}/{count}")
            b = buf[o]
            o += 1
            s |= (b & 127) << shift
            # JS bitwise is 32-bit
            s = _to_u32(s)
            shift += 7
            if (b & 128) == 0:
                break
            if shift > 35:
                raise ValueError("varint too long")
        if signed:
            # zigzag with 32-bit arithmetic shift semantics
            c = _to_i32(s)
            out[a] = (c >> 1) ^ (-(c & 1))
        else:
            out[a] = s
    return out


def delta_decode(values: list[int], start: int = 0) -> list[int]:
    """JS function a: prefix-sum of zigzag deltas (32-bit)."""
    if start >= len(values):
        return values
    r = _to_i32(int(values[start]))
    values[start] = r
    for i in range(start + 1, len(values)):
        o = _to_i32(int(values[i]))
        # o>>1 ^ -(o&1) with JS 32-bit shifts
        delta = (o >> 1) ^ (-(o & 1))
        r = _to_i32(r + delta)
        values[i] = r
    return values


def highwater_decode(values: list[int], state: list[int]) -> list[int]:
    """JS function h."""
    n = int(state[0])
    out = [0] * len(values)
    for a, e in enumerate(values):
        o = n - int(e)
        out[a] = o
        if n <= o:
            n = o + 1
    state[0] = n
    return out


def implicit_strip_decode(
    src: list[int], prim_len: int, data_index: int, use_watermark_seed: bool
) -> list[int]:
    """
    Expand implicit triangle-strip indices (viewer function o/s).

    Critical JS loop semantics:
      for (c=s[u], h=32*u, d=(last?leftover:0); d<32; ++d, ++h)
        t[h] = (c & (-2147483648 >>> d)) ? e[i++] : (n ? r : r++);

    h starts at 32*u even when d starts at leftover (bits below leftover are skipped).
    """
    expected = int(src[IMPLICIT_HEADER_EXPECTED_INDEX])
    mask_len = int(src[IMPLICIT_HEADER_MASK_LENGTH])
    masks = [
        _to_u32(int(x))
        for x in src[IMPLICIT_HEADER_LENGTH : IMPLICIT_HEADER_LENGTH + mask_len]
    ]
    leftover = 32 * mask_len - prim_len
    dest = [0] * prim_len
    i = data_index
    r = expected
    for u in range(mask_len):
        c = masks[u]
        d_start = leftover if u == mask_len - 1 else 0
        h = 32 * u
        for d in range(d_start, 32):
            if h >= prim_len:
                break
            # JS: c & ((-2147483648) >>> d)
            bit_sel = _to_u32(0x80000000 >> d) if d < 32 else 0
            # In Python >> on 0x80000000 works as unsigned for d>0 if we mask:
            bit_sel = (0x80000000 >> d) & 0xFFFFFFFF
            if c & bit_sel:
                dest[h] = int(src[i])
                i += 1
            else:
                dest[h] = r
                if not use_watermark_seed:
                    r += 1
            h += 1
    return dest


def parallelogram_predict(values: list[int], item_size: int, indices: list[int]) -> list[int]:
    n_verts = len(values) // item_size
    if n_verts <= 0 or len(indices) < 3:
        return values
    seen = [0] * n_verts
    for k in range(3):
        if 0 <= indices[k] < n_verts:
            seen[indices[k]] = 1
    a = len(indices) - 1
    for o in range(2, a):
        s = o - 2
        l_i, u_i, c_i, h_i = indices[s], indices[s + 1], indices[s + 2], indices[s + 3]
        if not (0 <= h_i < n_verts):
            continue
        if seen[h_i] == 1:
            continue
        if not (0 <= l_i < n_verts and 0 <= u_i < n_verts and 0 <= c_i < n_verts):
            continue
        seen[h_i] = 1
        bl, bu, bc, bh = l_i * item_size, u_i * item_size, c_i * item_size, h_i * item_size
        for d in range(item_size):
            values[bh + d] = values[bh + d] + values[bu + d] + values[bc + d] - values[bl + d]
    return values


def dequant(values: list[int], bbl: list[float], step: list[float], item_size: int) -> list[float]:
    out = [0.0] * len(values)
    n = len(values) // item_size
    for o in range(n):
        s = o * item_size
        for l in range(item_size):
            out[s + l] = bbl[l] + float(values[s + l]) * step[l]
    return out


def decode_normals(
    packed: list[int],
    item_size_out: int,
    epsilon: float = 0.25,
    nphi: int = 720,
    is_tangent: bool = False,
) -> list[float]:
    pi = math.pi
    u = math.cos(math.radians(epsilon))
    d = pi / max(nphi - 1, 1)
    g = (math.pi / 2) / max(nphi - 1, 1)
    f = 3 if is_tangent else 2
    p = len(packed) // f
    out = [0.0] * (p * item_size_out)
    for c in range(p):
        v = c * item_size_out
        base = c * f
        S = int(packed[base])
        x = int(packed[base + 1])
        if item_size_out == 4 and not is_tangent:
            out[v + 3] = -1.0 if (S & 1024) else 1.0
            S &= ~1024
        A = S * d
        R = math.cos(A)
        w = math.sin(A)
        A2 = A + g
        denom = max(1e-5, w * math.sin(A2))
        E = (u - R * math.cos(A2)) / denom
        E = max(-1.0, min(1.0, E))
        P = (2 * math.pi) * x / max(1.0, math.ceil(pi / max(1e-5, math.acos(E))))
        C = w * math.cos(P)
        T = w * math.sin(P)
        M = R
        if is_tangent and f >= 3:
            N = 4.7938362584151635e-5 * float(packed[base + 2])
            O = math.sin(N)
            out[v] = O * C
            out[v + 1] = O * T
            out[v + 2] = O * M
            out[v + 3] = math.cos(N)
        else:
            out[v] = C
            out[v + 1] = T
            out[v + 2] = M
    return out


def parse_user_data(udc: Optional[dict]) -> dict[str, Any]:
    if not udc:
        return {}
    out: dict[str, Any] = {}
    special = {
        "wireframe", "epsilon", "nphi", "attributes", "vertex_mode", "triangle_mode",
        "rigIndex", "framerate", "bx", "by", "bz", "hx", "hy", "hz",
        "ox", "oy", "oz", "ow", "ot", "channel_mode",
    }
    for item in udc.get("Values") or []:
        name = item.get("Name")
        val = item.get("Value")
        if name is None:
            continue
        if (
            name in special
            or "_bbl_" in name
            or "_h_" in name
            or name.endswith("_mode")
            or name.endswith("_bits")
        ):
            try:
                out[name] = json.loads(val)
            except Exception:
                try:
                    out[name] = float(val)
                except Exception:
                    out[name] = val
        else:
            out[name] = val
    return out


def _attr_flag(name: str) -> int:
    if "TexCoord" in name:
        return ATTR["TexCoord"]
    return ATTR.get(name, 0)


def _get_array_desc(node: dict) -> tuple[str, dict]:
    arr = node.get("Array") or {}
    if not arr:
        raise ValueError("empty Array descriptor")
    type_name = next(iter(arr.keys()))
    return type_name, arr[type_name]


def read_buffer_array(
    bin_files: dict[str, bytes],
    node: dict,
    *,
    element_count_mode: str = "components",
) -> tuple[list, str, int]:
    """
    Read a BufferArray-like node.

    Viewer uses count = ItemSize * Size for attribute streams.
    In Sketchfab JSON, Size is typically the vertex/element count for attributes,
    so total scalars = ItemSize * Size.
    For indices ItemSize is 1 → Size values.
    """
    item_size = int(node.get("ItemSize") or 1)
    tname, meta = _get_array_desc(node)
    offset = int(meta.get("Offset") or 0)
    size = int(meta.get("Size") or 0)
    fname = meta.get("File") or "model_file.bin"
    encoding = meta.get("Encoding")
    # Resolve decrypted buffers even if osgjs still says .binz / .bin.gz
    data = bin_files.get(fname) or bin_files.get(Path(fname).name)
    if data is None:
        alt = Path(fname).name
        for cand in (
            alt,
            alt.replace(".binz", ".bin"),
            alt.replace(".bin.gz", ".bin"),
            alt.replace(".gz", ""),
            re.sub(r"\.binz$", ".bin", alt),
            re.sub(r"\.bin\.gz$", ".bin", alt),
        ):
            if cand in bin_files:
                data = bin_files[cand]
                break
    if data is None:
        for k, v in bin_files.items():
            if Path(k).name.split(".")[0] == Path(fname).name.split(".")[0] and "wireframe" not in k:
                # model_file* match
                if Path(k).stem.startswith(Path(fname).stem.split(".")[0][:10]):
                    data = v
                    break
    if data is None:
        raise FileNotFoundError(f"Binary buffer not found: {fname}")

    # Match viewer: count = itemSize * Size
    count = size * item_size if element_count_mode == "viewer" else size
    if count <= 0:
        return [], tname, item_size

    if encoding == "varint":
        values = decode_varint(memoryview(data)[offset:], count, tname)
        return values, tname, item_size

    nbytes = {
        "Uint8Array": 1, "Int8Array": 1,
        "Uint16Array": 2, "Int16Array": 2,
        "Uint32Array": 4, "Int32Array": 4,
        "Float32Array": 4,
    }.get(tname)
    if nbytes is None:
        raise ValueError(f"Unsupported array type {tname}")
    raw = data[offset : offset + count * nbytes]
    if len(raw) < count * nbytes:
        # fallback: Size already means total components
        count = size
        raw = data[offset : offset + count * nbytes]
    fmt = {
        "Uint8Array": "B", "Int8Array": "b",
        "Uint16Array": "H", "Int16Array": "h",
        "Uint32Array": "I", "Int32Array": "i",
        "Float32Array": "f",
    }[tname]
    values = list(struct.unpack("<" + fmt * (len(raw) // nbytes), raw[: (len(raw) // nbytes) * nbytes]))
    return values, tname, item_size


def decode_indices(
    prim: dict,
    user: dict,
    bin_files: dict[str, bytes],
) -> tuple[list[int], str]:
    key = next(k for k in prim if k.startswith("DrawElements") or k.startswith("DrawArrays"))
    pe = prim[key]
    mode = pe.get("Mode") or "TRIANGLES"

    if key.startswith("DrawArrays"):
        first = int(pe.get("First") or 0)
        count = int(pe.get("Count") or 0)
        return list(range(first, first + count)), mode

    indices_node = pe.get("Indices") or {}
    # indices: ItemSize usually 1, Size = stream length
    values, tname, item_size = read_buffer_array(
        bin_files, indices_node, element_count_mode="viewer"
    )
    values = [int(v) for v in values]

    attrs = int(user.get("attributes") or 0)
    tri_mode = int(user.get("triangle_mode") or 0)
    is_strip = mode == "TRIANGLE_STRIP"

    if (attrs & ATTR["Triangle"]) == 0 or (not is_strip and mode != "TRIANGLES"):
        return values, mode

    b = 0
    if (tri_mode & TRI_IMPLICIT) and is_strip:
        b = IMPLICIT_HEADER_LENGTH + int(values[IMPLICIT_HEADER_MASK_LENGTH])
        prim_len = int(values[IMPLICIT_HEADER_PRIMITIVE_LENGTH])
    else:
        prim_len = len(values)

    if tri_mode & TRI_DELTA:
        delta_decode(values, b)

    if (tri_mode & TRI_IMPLICIT) and is_strip:
        values = implicit_strip_decode(
            values, prim_len, b, use_watermark_seed=bool(tri_mode & TRI_HIGHWATER)
        )

    if tri_mode & TRI_HIGHWATER:
        values = highwater_decode(values, [0])

    return [int(v) for v in values], mode


def strip_to_triangles(indices: list[int]) -> list[int]:
    """
    Expand GL TRIANGLE_STRIP to TRIANGLES.
    Winding flips every index (including over degenerates), matching GPU behaviour.
    """
    tris: list[int] = []
    n = len(indices)
    for i in range(n - 2):
        a, b, c = indices[i], indices[i + 1], indices[i + 2]
        if a == b or b == c or a == c:
            continue
        if (i & 1) == 0:
            tris.extend((a, b, c))
        else:
            tris.extend((a, c, b))
    return tris


def recalc_vertex_normals(positions: list[float], indices: list[int]) -> list[float]:
    """Area-weighted smooth normals from triangle soup (fixes bad packed normals)."""
    n_verts = len(positions) // 3
    acc = [0.0] * (n_verts * 3)
    for i in range(0, len(indices) - 2, 3):
        ia, ib, ic = indices[i], indices[i + 1], indices[i + 2]
        if min(ia, ib, ic) < 0 or max(ia, ib, ic) >= n_verts:
            continue
        ax, ay, az = positions[ia * 3 : ia * 3 + 3]
        bx, by, bz = positions[ib * 3 : ib * 3 + 3]
        cx, cy, cz = positions[ic * 3 : ic * 3 + 3]
        abx, aby, abz = bx - ax, by - ay, bz - az
        acx, acy, acz = cx - ax, cy - ay, cz - az
        nx = aby * acz - abz * acy
        ny = abz * acx - abx * acz
        nz = abx * acy - aby * acx
        for vi in (ia, ib, ic):
            acc[vi * 3] += nx
            acc[vi * 3 + 1] += ny
            acc[vi * 3 + 2] += nz
    for vi in range(n_verts):
        x, y, z = acc[vi * 3], acc[vi * 3 + 1], acc[vi * 3 + 2]
        ln = math.sqrt(x * x + y * y + z * z)
        if ln > 1e-12:
            acc[vi * 3] = x / ln
            acc[vi * 3 + 1] = y / ln
            acc[vi * 3 + 2] = z / ln
        else:
            acc[vi * 3 : vi * 3 + 3] = [0.0, 1.0, 0.0]
    return acc


def filter_spike_tris(
    positions: list[float], indices: list[int], *, max_edge_factor: float = 12.0
) -> list[int]:
    """
    Drop triangles with an edge much longer than the mesh median edge.
    Removes rare decode spikes without harming normal topology.
    """
    if len(indices) < 3 or len(positions) < 9:
        return indices
    # sample edges for median
    samples: list[float] = []
    step = max(3, (len(indices) // 3) // 2000 * 3)  # limit work
    for i in range(0, len(indices) - 2, step):
        for a, b in (
            (indices[i], indices[i + 1]),
            (indices[i + 1], indices[i + 2]),
            (indices[i + 2], indices[i]),
        ):
            ax, ay, az = positions[a * 3 : a * 3 + 3]
            bx, by, bz = positions[b * 3 : b * 3 + 3]
            dx, dy, dz = ax - bx, ay - by, az - bz
            samples.append(math.sqrt(dx * dx + dy * dy + dz * dz))
    if not samples:
        return indices
    samples.sort()
    med = samples[len(samples) // 2] or 1e-6
    limit = med * max_edge_factor
    out: list[int] = []
    for i in range(0, len(indices) - 2, 3):
        tri = indices[i : i + 3]
        ok = True
        for a, b in ((tri[0], tri[1]), (tri[1], tri[2]), (tri[2], tri[0])):
            ax, ay, az = positions[a * 3 : a * 3 + 3]
            bx, by, bz = positions[b * 3 : b * 3 + 3]
            dx, dy, dz = ax - bx, ay - by, az - bz
            if math.sqrt(dx * dx + dy * dy + dz * dz) > limit:
                ok = False
                break
        if ok:
            out.extend(tri)
    return out if len(out) >= 3 else indices


def weld_mesh_by_position(
    positions: list[float],
    indices: list[int],
    uvs: Optional[list[float]] = None,
    *,
    eps: float = 1e-5,
) -> tuple[list[float], list[int], Optional[list[float]]]:
    """
    Merge vertices that share the same position (UV islands).

    Sketchfab meshes are heavily UV-split: same XYZ appears many times with
    different UVs. Exporting without welding leaves false boundary edges and
    can look like a 'sieve' in some DCC tools. We keep one UV per welded vertex
    (first seen) — good enough for solid shading; textures may soft-seam.
    """
    n_verts = len(positions) // 3
    if n_verts == 0:
        return positions, indices, uvs

    key_to_new: dict[tuple[int, int, int], int] = {}
    remap = [0] * n_verts
    new_pos: list[float] = []
    new_uv: Optional[list[float]] = [] if uvs is not None else None

    inv = 1.0 / eps
    for i in range(n_verts):
        x, y, z = positions[i * 3], positions[i * 3 + 1], positions[i * 3 + 2]
        key = (int(round(x * inv)), int(round(y * inv)), int(round(z * inv)))
        if key not in key_to_new:
            key_to_new[key] = len(new_pos) // 3
            new_pos.extend((x, y, z))
            if new_uv is not None and uvs is not None and len(uvs) >= (i + 1) * 2:
                new_uv.extend((uvs[i * 2], uvs[i * 2 + 1]))
            elif new_uv is not None:
                new_uv.extend((0.0, 0.0))
        remap[i] = key_to_new[key]

    new_idx: list[int] = []
    for i in range(0, len(indices) - 2, 3):
        a, b, c = remap[indices[i]], remap[indices[i + 1]], remap[indices[i + 2]]
        if a == b or b == c or a == c:
            continue
        new_idx.extend((a, b, c))
    if len(new_idx) < 3:
        return positions, indices, uvs
    return new_pos, new_idx, new_uv


def is_transparent_geom(geom: dict) -> bool:
    ss = geom.get("StateSet") or {}
    if "osg.StateSet" in ss:
        ss = ss["osg.StateSet"]
    hint = str(ss.get("RenderingHint") or "")
    if "TRANSPARENT" in hint.upper():
        return True
    for entry in ss.get("AttributeList") or []:
        if isinstance(entry, dict) and "osg.BlendFunc" in entry:
            return True
    return False


def make_double_sided(indices: list[int]) -> list[int]:
    """Append flipped winding of every triangle (for cards/transparent shells)."""
    out = list(indices)
    for i in range(0, len(indices) - 2, 3):
        a, b, c = indices[i], indices[i + 1], indices[i + 2]
        out.extend((a, c, b))
    return out


def decode_vertex_attr(
    name: str,
    node: dict,
    user: dict,
    bin_files: dict[str, bytes],
    indices_for_predict: Optional[list[int]] = None,
) -> tuple[list[float], int]:
    attrs = int(user.get("attributes") or 0)
    flag = _attr_flag(name)
    values, tname, item_size = read_buffer_array(
        bin_files, node, element_count_mode="viewer"
    )
    values_list = list(values)

    if name == "Normal" and (attrs & ATTR["Normal"]):
        epsilon = float(user.get("epsilon") or 0.25)
        nphi = int(user.get("nphi") or 720)
        out = decode_normals([int(x) for x in values_list], 3, epsilon, nphi, False)
        return out, 3

    if name == "Tangent" and (attrs & ATTR["Tangent"]):
        epsilon = float(user.get("epsilon") or 0.25)
        nphi = int(user.get("nphi") or 720)
        out = decode_normals([int(x) for x in values_list], 4, epsilon, nphi, True)
        return out, 4

    if name == "Color":
        # often uint8 0..255
        if tname == "Uint8Array":
            return [float(x) / 255.0 for x in values_list], item_size
        return [float(x) for x in values_list], item_size

    if name == "Vertex":
        mode = int(user.get("vertex_mode") or 0)
        prefix = "vtx_"
    elif name.startswith("TexCoord"):
        idx = name.replace("TexCoord", "")
        mode_key = f"uv_{idx}_mode"
        mode = int(
            user[mode_key]
            if mode_key in user and user[mode_key] is not None
            else user.get("vertex_mode") or 0
        )
        prefix = f"uv_{idx}_"
    else:
        return [float(x) for x in values_list], item_size

    if (attrs & flag) == 0:
        return [float(x) for x in values_list], item_size

    ints = [int(x) for x in values_list]
    if (mode & MODE_PARALLELOGRAM) and indices_for_predict:
        parallelogram_predict(ints, item_size, indices_for_predict)

    if mode & MODE_QUANT:
        bbl_key = prefix + "bbl_x"
        if bbl_key in user:
            bbl = [float(user.get(prefix + "bbl_x") or 0.0), float(user.get(prefix + "bbl_y") or 0.0)]
            step = [float(user.get(prefix + "h_x") or 1.0), float(user.get(prefix + "h_y") or 1.0)]
            if item_size >= 3:
                bbl.append(float(user.get(prefix + "bbl_z") or 0.0))
                step.append(float(user.get(prefix + "h_z") or 1.0))
            while len(bbl) < item_size:
                bbl.append(0.0)
                step.append(1.0)
            return dequant(ints, bbl, step, item_size), item_size

    return [float(x) for x in ints], item_size


def _load_bins(work_dir: Path) -> dict[str, bytes]:
    """Load .bin buffers and alias .binz / .bin.gz names to decrypted .bin."""
    bins: dict[str, bytes] = {}
    for p in work_dir.iterdir():
        if p.suffix.lower() == ".bin" and p.is_file():
            data = p.read_bytes()
            bins[p.name] = data
            # aliases used inside file.osgjs before/after rename
            bins[p.name + "z"] = data  # model_file.binz
            bins[p.stem + ".binz"] = data
            bins[p.name + ".gz"] = data
            bins[p.stem + ".bin.gz"] = data
    return bins


def _is_wireframe_geom(g: dict) -> bool:
    """Skip wireframe helper meshes (lines as triangles = 'sieve' artifacts)."""
    # File refs
    blob = json.dumps(g, ensure_ascii=False)
    if "wireframe" in blob.lower():
        return True
    valist = g.get("VertexAttributeList") or {}
    for node in valist.values():
        if not isinstance(node, dict):
            continue
        arr = node.get("Array") or {}
        for meta in arr.values():
            if isinstance(meta, dict):
                f = str(meta.get("File") or "").lower()
                if "wireframe" in f:
                    return True
    return False


def _walk_geometries(node: Any, out: list[dict], *, _seen: Optional[set] = None) -> None:
    """Collect unique renderable geometries; prefer RigGeometry.SourceGeometry once."""
    if _seen is None:
        _seen = set()

    if isinstance(node, dict):
        if "osg.RigGeometry" in node:
            rg = node["osg.RigGeometry"]
            src = rg.get("SourceGeometry")
            geom = None
            if isinstance(src, dict) and "osg.Geometry" in src:
                geom = src["osg.Geometry"]
            elif isinstance(src, dict):
                for k, v in src.items():
                    if k.startswith("osg.") and isinstance(v, dict) and v.get("VertexAttributeList"):
                        geom = v
                        break
            if geom is not None:
                gid = id(geom)
                if gid not in _seen and not _is_wireframe_geom(geom):
                    _seen.add(gid)
                    out.append(geom)
            # still walk non-source children of rig (animations etc.) but skip re-adding source
            for k, v in rg.items():
                if k == "SourceGeometry":
                    continue
                _walk_geometries(v, out, _seen=_seen)
            for k, v in node.items():
                if k != "osg.RigGeometry":
                    _walk_geometries(v, out, _seen=_seen)
            return

        if "osg.Geometry" in node:
            geom = node["osg.Geometry"]
            gid = id(geom)
            if gid not in _seen and geom.get("VertexAttributeList") and not _is_wireframe_geom(geom):
                _seen.add(gid)
                out.append(geom)

        for v in node.values():
            _walk_geometries(v, out, _seen=_seen)
    elif isinstance(node, list):
        for v in node:
            _walk_geometries(v, out, _seen=_seen)


def _extract_diffuse_texture(geom: dict) -> Optional[str]:
    """Return texture File path from StateSet if present."""
    ss = geom.get("StateSet") or {}
    if "osg.StateSet" in ss:
        ss = ss["osg.StateSet"]
    tal = ss.get("TextureAttributeList") or []
    for unit in tal:
        if not isinstance(unit, list):
            unit = [unit]
        for entry in unit:
            if not isinstance(entry, dict):
                continue
            tex = entry.get("osg.Texture") or entry.get("osg.Texture2D")
            if isinstance(tex, dict) and tex.get("File"):
                return str(tex["File"])
    # AttributeList material name only — no file
    return None


def _extract_material_name(geom: dict, fallback: str) -> str:
    ss = geom.get("StateSet") or {}
    if "osg.StateSet" in ss:
        ss = ss["osg.StateSet"]
    for entry in ss.get("AttributeList") or []:
        if isinstance(entry, dict) and "osg.Material" in entry:
            mat = entry["osg.Material"]
            if mat.get("Name"):
                return str(mat["Name"])
    return fallback


def _rel_tex(path: Path, work_dir: Path) -> str:
    try:
        return str(path.relative_to(work_dir)).replace("\\", "/")
    except ValueError:
        return path.name


def _resolve_texture_file(
    tex_ref: str,
    work_dir: Path,
    tex_map: Optional[dict[str, Path]],
    *,
    material_name: str = "",
) -> Optional[str]:
    """Return path relative to work_dir for MTL map_Kd, or None."""
    candidates: list[Path] = []
    uid_m = re.search(r"([a-f0-9]{32})", (tex_ref or "").replace("\\", "/"))

    if tex_map:
        if uid_m and uid_m.group(1) in tex_map:
            candidates.append(Path(tex_map[uid_m.group(1)]))
        base = Path(tex_ref).name if tex_ref else ""
        if base and base in tex_map:
            candidates.append(Path(tex_map[base]))
        if uid_m:
            for k, p in tex_map.items():
                if uid_m.group(1) in k:
                    candidates.append(Path(p))

    if tex_ref:
        direct = work_dir / tex_ref
        if direct.is_file():
            candidates.append(direct)

    tex_dir = work_dir / "textures"
    if tex_dir.is_dir():
        if uid_m:
            for p in tex_dir.glob(f"{uid_m.group(1)}*"):
                candidates.append(p)
        # Heuristic: material name → diffuse map (*_D*, *Diffuse*, *Albedo*, *BaseColor*)
        mat = re.sub(r"[^a-z0-9]+", "", (material_name or "").lower())
        if mat:
            for p in tex_dir.iterdir():
                if not p.is_file():
                    continue
                n = p.name.lower()
                if mat[:8] and mat[:8] in re.sub(r"[^a-z0-9]+", "", n):
                    if any(tag in n for tag in ("_d.", "_d_", "diffuse", "albedo", "basecolor", "_a.")):
                        candidates.insert(0, p)
                    else:
                        candidates.append(p)

    for p in candidates:
        if p.is_file():
            return _rel_tex(p, work_dir)
    return None


def _filter_tris(indices: list[int], n_verts: int) -> list[int]:
    """Drop triangles with out-of-range indices (prevents Blender IndexError)."""
    out: list[int] = []
    for i in range(0, len(indices) - 2, 3):
        a, b, c = indices[i], indices[i + 1], indices[i + 2]
        if min(a, b, c) < 0 or max(a, b, c) >= n_verts:
            continue
        if a == b or b == c or a == c:
            continue
        out.extend([a, b, c])
    return out


def convert_osgjs(
    work_dir: Path,
    model_name: str = "model",
    *,
    prefer: str = "gltf",
    texture_map: Optional[dict[str, Path]] = None,
    weld: bool = False,
    double_sided: bool = False,
) -> Path:
    """
    Convert file.osgjs + *.bin in work_dir.
    prefer: 'gltf' (default) or 'obj'
    weld/double_sided: off by default (safer mesh; enable only if needed)
    texture_map: optional uid/name → local file paths
    """
    work_dir = Path(work_dir)
    osgjs_path = work_dir / "file.osgjs"
    if not osgjs_path.is_file():
        raise FileNotFoundError(f"No file.osgjs in {work_dir}")

    scene = json.loads(osgjs_path.read_text(encoding="utf-8"))
    bins = _load_bins(work_dir)
    if not bins:
        raise FileNotFoundError("No .bin buffers next to file.osgjs")

    geoms: list[dict] = []
    _walk_geometries(scene, geoms)
    if not geoms:
        raise RuntimeError("No osg.Geometry found in file.osgjs")

    meshes: list[dict] = []
    for gi, g in enumerate(geoms):
        try:
            user = parse_user_data(g.get("UserDataContainer"))
            valist = g.get("VertexAttributeList") or {}
            if "Vertex" not in valist or not valist["Vertex"].get("Array"):
                continue

            prims = g.get("PrimitiveSetList") or []
            all_tri: list[int] = []
            predict_idx: Optional[list[int]] = None
            for pi, prim in enumerate(prims):
                try:
                    idx, mode = decode_indices(prim, user, bins)
                except Exception:
                    continue
                if predict_idx is None:
                    predict_idx = list(idx)
                if mode == "TRIANGLE_STRIP":
                    tris = strip_to_triangles(idx)
                elif mode == "TRIANGLES":
                    tris = idx
                else:
                    continue
                all_tri.extend(tris)
            if not all_tri:
                continue

            positions, _ = decode_vertex_attr(
                "Vertex", valist["Vertex"], user, bins, predict_idx
            )
            n_verts = len(positions) // 3
            if n_verts <= 0:
                continue
            all_tri = _filter_tris(all_tri, n_verts)
            if not all_tri:
                continue
            # Drop only extreme decode spikes (keep long thin real geometry like weapons/hair)
            all_tri = filter_spike_tris(positions, all_tri, max_edge_factor=80.0)
            if not all_tri:
                continue

            uvs = None
            if "TexCoord0" in valist and valist["TexCoord0"].get("Array"):
                try:
                    uvs, uv_size = decode_vertex_attr(
                        "TexCoord0", valist["TexCoord0"], user, bins, predict_idx
                    )
                    if not uvs or len(uvs) < n_verts * 2:
                        uvs = None
                    else:
                        uvs = uvs[: n_verts * 2]
                except Exception:
                    uvs = None

            if weld:
                positions, all_tri, uvs = weld_mesh_by_position(
                    positions, all_tri, uvs, eps=1e-5
                )
                if not all_tri:
                    continue

            if double_sided:
                all_tri = make_double_sided(all_tri)

            # Prefer decoded normals; fall back to computed
            normals = None
            if "Normal" in valist and valist["Normal"].get("Array"):
                try:
                    normals, _ = decode_vertex_attr(
                        "Normal", valist["Normal"], user, bins
                    )
                    if not normals or len(normals) // 3 != len(positions) // 3:
                        normals = None
                except Exception:
                    normals = None
            if normals is None:
                normals = recalc_vertex_normals(positions, all_tri)

            mat_name = _extract_material_name(g, f"mat_{gi}")
            tex_ref = _extract_diffuse_texture(g)
            tex_rel = _resolve_texture_file(
                tex_ref or "",
                work_dir,
                texture_map,
                material_name=mat_name,
            )

            meshes.append(
                {
                    "name": str(g.get("Name") or f"mesh_{gi}"),
                    "positions": positions,
                    "normals": normals,
                    "uvs": uvs,
                    "indices": all_tri,
                    "material": re.sub(r"[^\w\-]+", "_", mat_name)[:64] or f"mat_{gi}",
                    "texture": tex_rel,
                }
            )
        except Exception:
            continue

    if not meshes:
        raise RuntimeError("No mesh data could be decoded from osgjs")

    if prefer == "gltf":
        return _write_gltf(work_dir, model_name, meshes)
    return _write_obj(work_dir, model_name, meshes)


def _write_obj(work_dir: Path, model_name: str, meshes: list[dict]) -> Path:
    obj_path = work_dir / f"{model_name}.obj"
    mtl_path = work_dir / f"{model_name}.mtl"

    # materials
    mats: dict[str, Optional[str]] = {}
    for m in meshes:
        mats.setdefault(m["material"], m.get("texture"))

    mtl_lines = [f"# MTL for {model_name}", f"# materials: {len(mats)}"]
    for mat, tex in mats.items():
        mtl_lines.append(f"newmtl {mat}")
        mtl_lines.append("Ka 1.000 1.000 1.000")
        mtl_lines.append("Kd 1.000 1.000 1.000")
        mtl_lines.append("Ks 0.000 0.000 0.000")
        mtl_lines.append("d 1.0")
        mtl_lines.append("illum 1")
        if tex:
            mtl_lines.append(f"map_Kd {tex}")
        mtl_lines.append("")
    mtl_path.write_text("\n".join(mtl_lines), encoding="utf-8")

    lines: list[str] = [
        f"# Sketchfab pure-python OBJ export: {model_name}",
        f"mtllib {mtl_path.name}",
        f"o {model_name}",
    ]

    # Global vertex pools (Blender-safe): write unique v/vt/vn per mesh with running offsets
    v_off = 0
    vt_off = 0
    vn_off = 0

    for mi, m in enumerate(meshes):
        pos = m["positions"]
        nrm = m["normals"]
        uvs = m["uvs"]
        n_verts = len(pos) // 3
        lines.append(f"g {m['name'] or f'mesh_{mi}'}")
        lines.append(f"usemtl {m['material']}")

        for i in range(0, len(pos), 3):
            lines.append(f"v {pos[i]:.8g} {pos[i+1]:.8g} {pos[i+2]:.8g}")

        has_vn = bool(nrm) and len(nrm) // 3 == n_verts
        has_vt = bool(uvs) and len(uvs) // 2 == n_verts

        if has_vn:
            for i in range(0, len(nrm), 3):
                lines.append(f"vn {nrm[i]:.8g} {nrm[i+1]:.8g} {nrm[i+2]:.8g}")
        if has_vt:
            for i in range(0, len(uvs), 2):
                # Sketchfab UVs often need V flip for Blender
                lines.append(f"vt {uvs[i]:.8g} {1.0 - uvs[i+1]:.8g}")

        idx = m["indices"]
        for i in range(0, len(idx), 3):
            a0, b0, c0 = idx[i], idx[i + 1], idx[i + 2]
            # OBJ is 1-based
            a, b, c = a0 + 1 + v_off, b0 + 1 + v_off, c0 + 1 + v_off
            if has_vt and has_vn:
                at, bt, ct = a0 + 1 + vt_off, b0 + 1 + vt_off, c0 + 1 + vt_off
                an, bn, cn = a0 + 1 + vn_off, b0 + 1 + vn_off, c0 + 1 + vn_off
                lines.append(f"f {a}/{at}/{an} {b}/{bt}/{bn} {c}/{ct}/{cn}")
            elif has_vt:
                at, bt, ct = a0 + 1 + vt_off, b0 + 1 + vt_off, c0 + 1 + vt_off
                lines.append(f"f {a}/{at} {b}/{bt} {c}/{ct}")
            elif has_vn:
                an, bn, cn = a0 + 1 + vn_off, b0 + 1 + vn_off, c0 + 1 + vn_off
                lines.append(f"f {a}//{an} {b}//{bn} {c}//{cn}")
            else:
                lines.append(f"f {a} {b} {c}")

        v_off += n_verts
        if has_vt:
            vt_off += n_verts
        if has_vn:
            vn_off += n_verts

    obj_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return obj_path


def _write_gltf(work_dir: Path, model_name: str, meshes: list[dict]) -> Path:
    """Minimal embedded glTF (no textures) — kept as secondary option."""
    import array
    import base64

    blob = bytearray()
    accessors: list[dict] = []
    buffer_views: list[dict] = []
    gl_meshes: list[dict] = []
    nodes: list[dict] = []

    def add_f32(data: list[float], item_size: int) -> int:
        while len(blob) % 4:
            blob.append(0)
        offset = len(blob)
        raw = array.array("f", data).tobytes()
        blob.extend(raw)
        bv = len(buffer_views)
        buffer_views.append({"buffer": 0, "byteOffset": offset, "byteLength": len(raw), "target": 34962})
        mins = [min(data[i::item_size]) for i in range(item_size)]
        maxs = [max(data[i::item_size]) for i in range(item_size)]
        ai = len(accessors)
        accessors.append({
            "bufferView": bv, "componentType": 5126,
            "count": len(data) // item_size,
            "type": {1: "SCALAR", 2: "VEC2", 3: "VEC3", 4: "VEC4"}[item_size],
            "min": mins, "max": maxs,
        })
        return ai

    def add_u32(data: list[int]) -> int:
        while len(blob) % 4:
            blob.append(0)
        offset = len(blob)
        raw = array.array("I", data).tobytes()
        blob.extend(raw)
        bv = len(buffer_views)
        buffer_views.append({"buffer": 0, "byteOffset": offset, "byteLength": len(raw), "target": 34963})
        ai = len(accessors)
        accessors.append({"bufferView": bv, "componentType": 5125, "count": len(data), "type": "SCALAR"})
        return ai

    for mi, m in enumerate(meshes):
        attrs = {"POSITION": add_f32(m["positions"], 3)}
        if m["normals"]:
            attrs["NORMAL"] = add_f32(m["normals"], 3)
        if m["uvs"]:
            attrs["TEXCOORD_0"] = add_f32(m["uvs"], 2)
        gl_meshes.append({
            "name": m["name"],
            "primitives": [{"attributes": attrs, "indices": add_u32(m["indices"]), "mode": 4}],
        })
        nodes.append({"mesh": mi, "name": m["name"]})

    b64 = base64.b64encode(bytes(blob)).decode("ascii")
    gltf = {
        "asset": {"version": "2.0", "generator": "sketchfab-dl-pure-python"},
        "buffers": [{"byteLength": len(blob), "uri": f"data:application/octet-stream;base64,{b64}"}],
        "bufferViews": buffer_views,
        "accessors": accessors,
        "meshes": gl_meshes,
        "nodes": nodes,
        "scenes": [{"nodes": list(range(len(nodes)))}],
        "scene": 0,
    }
    out = work_dir / f"{model_name}.gltf"
    out.write_text(json.dumps(gltf), encoding="utf-8")
    return out


if __name__ == "__main__":
    import sys
    d = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
    p = convert_osgjs(d, "model", prefer="obj")
    print("wrote", p, p.stat().st_size)
