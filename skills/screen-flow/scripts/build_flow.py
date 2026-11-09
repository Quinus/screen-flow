#!/usr/bin/env python3
"""Build a standalone, zoomable screen-flow HTML page from a flow.json and screenshots.

Usage:
    python3 build_flow.py path/to/flow.json [-o screen-flow.html] [--max-width 1000] [--check]

Only the Python standard library is required. When Pillow is installed (or `sips` on macOS),
screenshots wider than --max-width are downscaled before they are embedded, which keeps the
HTML file small. Every image is inlined as a data URI, so the result is a single file that
works offline and can be mailed, attached or committed.

See ../references/flow-schema.md for the flow.json format.
"""
from __future__ import annotations

import argparse
import base64
import datetime as dt
import io
import json
import re
import shutil
import struct
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
TEMPLATE = HERE.parent / "assets" / "viewer.html"
PLACEHOLDER = "/*__FLOW_DATA__*/null"
MIME = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp", ".gif": "image/gif"}
KINDS = {"nav", "action", "back", "modal", "redirect"}
GROUP_KINDS = {"nav", "feature"}
LAYOUTS = {"row", "flow", "grid"}
HEX = re.compile(r"^#[0-9a-fA-F]{6}$")


class FlowError(Exception):
    pass


# ---------------------------------------------------------------- image helpers
def image_size(data: bytes) -> tuple[int, int] | None:
    """Read width/height from PNG, JPEG, WebP or GIF bytes without third-party libraries."""
    try:
        if data[:8] == b"\x89PNG\r\n\x1a\n":
            return struct.unpack(">II", data[16:24])
        if data[:6] in (b"GIF87a", b"GIF89a"):
            return struct.unpack("<HH", data[6:10])
        if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
            chunk = data[12:16]
            if chunk == b"VP8X":
                w = int.from_bytes(data[24:27], "little") + 1
                h = int.from_bytes(data[27:30], "little") + 1
                return w, h
            if chunk == b"VP8L":
                b = data[21:25]
                w = 1 + (((b[1] & 0x3F) << 8) | b[0])
                h = 1 + (((b[3] & 0xF) << 10) | (b[2] << 2) | ((b[1] & 0xC0) >> 6))
                return w, h
            if chunk == b"VP8 ":
                w, h = struct.unpack("<HH", data[26:30])
                return w & 0x3FFF, h & 0x3FFF
        if data[:2] == b"\xff\xd8":
            i = 2
            while i < len(data) - 9:
                if data[i] != 0xFF:
                    i += 1
                    continue
                marker = data[i + 1]
                if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
                    h, w = struct.unpack(">HH", data[i + 5 : i + 9])
                    return w, h
                if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7:
                    i += 2
                    continue
                i += 2 + struct.unpack(">H", data[i + 2 : i + 4])[0]
    except (struct.error, IndexError):
        return None
    return None


def downscale(path: Path, data: bytes, size: tuple[int, int], max_width: int) -> tuple[bytes, tuple[int, int]]:
    """Shrink an image to max_width using Pillow or macOS sips; return the original on failure."""
    w, h = size
    if max_width <= 0 or w <= max_width:
        return data, size
    new = (max_width, round(h * max_width / w))
    try:
        from PIL import Image  # type: ignore

        with Image.open(io.BytesIO(data)) as im:
            fmt = im.format or "PNG"
            im = im.resize(new, Image.LANCZOS)
            buf = io.BytesIO()
            im.save(buf, format=fmt, **({"optimize": True} if fmt == "PNG" else {"quality": 85}))
            return buf.getvalue(), new
    except ImportError:
        pass
    except Exception as exc:  # noqa: BLE001 - keep the original image
        print(f"  ! could not resize {path.name} with Pillow: {exc}", file=sys.stderr)
        return data, size
    if shutil.which("sips"):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / path.name
            res = subprocess.run(
                ["sips", "--resampleWidth", str(max_width), str(path), "--out", str(out)],
                capture_output=True,
            )
            if res.returncode == 0 and out.exists():
                small = out.read_bytes()
                return small, image_size(small) or new
    return data, size


# ---------------------------------------------------------------- flow loading
def parse_hotspot(raw, size: tuple[int, int] | None) -> dict | None:
    """Return {x, y, w, h} as fractions of the screenshot. Accepts fractions or screenshot pixels."""
    if isinstance(raw, (list, tuple)) and len(raw) == 4:
        raw = dict(zip("xywh", raw))
    if not isinstance(raw, dict):
        return None
    try:
        x, y, w, h = (float(raw[k]) for k in ("x", "y", "w", "h"))
    except (KeyError, TypeError, ValueError):
        return None
    if max(x, y, w, h) > 1.0:          # pixels of the original screenshot
        if not size:
            return None
        x, w = x / size[0], w / size[0]
        y, h = y / size[1], h / size[1]
    x, y = max(0.0, min(1.0, x)), max(0.0, min(1.0, y))
    w, h = max(0.0, min(1.0 - x, w)), max(0.0, min(1.0 - y, h))
    if w <= 0 or h <= 0:
        return None
    return {k: round(v, 5) for k, v in (("x", x), ("y", y), ("w", w), ("h", h))}


def load_flow(flow_path: Path, max_width: int, embed: bool = True, hotspots_path: Path | None = None) -> tuple[dict, list[str]]:
    try:
        flow = json.loads(flow_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise FlowError(f"{flow_path}: invalid JSON: {exc}") from exc
    base = flow_path.parent
    warnings: list[str] = []
    errors: list[str] = []

    groups = flow.get("groups") or []
    screens = flow.get("screens") or []
    edges = flow.get("edges") or []
    if not screens:
        errors.append("flow has no screens")

    group_ids: set[str] = set()
    out_groups = []
    for g in groups:
        gid = g.get("id")
        if not gid:
            errors.append(f"group without id: {g}")
            continue
        if gid in group_ids:
            errors.append(f"duplicate group id '{gid}'")
        group_ids.add(gid)
        kind = g.get("kind", "feature")
        if kind not in GROUP_KINDS:
            warnings.append(f"group '{gid}': unknown kind '{kind}', using 'feature'")
            kind = "feature"
        layout = g.get("layout")
        if layout is not None and layout not in LAYOUTS:
            warnings.append(f"group '{gid}': unknown layout '{layout}', using the default")
            layout = None
        color = g.get("color")
        if color is not None and not HEX.match(str(color)):
            warnings.append(f"group '{gid}': color must look like #1a2b3c, ignoring '{color}'")
            color = None
        item = {"id": gid, "label": g.get("label") or gid, "kind": kind}
        for key, val in (("layout", layout), ("color", color), ("description", g.get("description")), ("parent", g.get("parent"))):
            if val:
                item[key] = val
        out_groups.append(item)

    screen_ids: set[str] = set()
    orig_size: dict[str, tuple[int, int]] = {}
    out_screens = []
    for s in screens:
        sid = s.get("id")
        if not sid:
            errors.append(f"screen without id: {s}")
            continue
        if sid in screen_ids:
            errors.append(f"duplicate screen id '{sid}'")
        screen_ids.add(sid)
        gid = s.get("group")
        if not gid:
            errors.append(f"screen '{sid}' has no group")
        elif gid not in group_ids:
            warnings.append(f"screen '{sid}': group '{gid}' is not declared, creating it")
            group_ids.add(gid)
            out_groups.append({"id": gid, "label": gid, "kind": "feature"})
        item = {k: s[k] for k in ("id", "title", "group", "route", "notes", "state", "entry", "column") if s.get(k) not in (None, "")}
        item.setdefault("title", sid)
        img = s.get("image")
        if not img:
            warnings.append(f"screen '{sid}': no image")
        else:
            p = (base / img).resolve()
            if not p.is_file():
                warnings.append(f"screen '{sid}': image not found: {img}")
            else:
                data = p.read_bytes()
                size = image_size(data)
                if not size:
                    warnings.append(f"screen '{sid}': unsupported image format: {img}")
                else:
                    orig_size[sid] = size
                    if embed:
                        data, size = downscale(p, data, size, max_width)
                        mime = MIME.get(p.suffix.lower(), "image/png")
                        item["src"] = f"data:{mime};base64," + base64.b64encode(data).decode("ascii")
                    item["w"], item["h"] = size
        out_screens.append(item)

    hotspots: dict = {}
    hp = hotspots_path or base / "hotspots.json"
    if hp.is_file():
        try:
            hotspots = json.loads(hp.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            warnings.append(f"{hp.name}: invalid JSON, ignored ({exc})")
    elif hotspots_path:
        warnings.append(f"hotspots file not found: {hotspots_path}")

    out_edges = []
    seen = set()
    for e in edges:
        src, dst = e.get("from"), e.get("to")
        if src not in screen_ids or dst not in screen_ids:
            errors.append(f"edge {src} -> {dst}: unknown screen id")
            continue
        if src == dst:
            warnings.append(f"edge {src} -> {dst}: self-links are not drawn")
            continue
        kind = e.get("kind", "nav")
        if kind not in KINDS:
            warnings.append(f"edge {src} -> {dst}: unknown kind '{kind}', using 'nav'")
            kind = "nav"
        key = (src, dst, e.get("label", ""))
        if key in seen:
            warnings.append(f"edge {src} -> {dst}: duplicate, skipped")
            continue
        seen.add(key)
        item = {"from": src, "to": dst, "kind": kind}
        if e.get("label"):
            item["label"] = e["label"]
        raw = e.get("hotspot") or hotspots.get(f"{src}>{dst}#{e.get('label', '')}") or hotspots.get(f"{src}>{dst}")
        if raw is not None:
            hs = parse_hotspot(raw, orig_size.get(src))
            if hs:
                item["hotspot"] = hs
            else:
                warnings.append(f"edge {src} -> {dst}: invalid hotspot {raw!r}, ignored")
        out_edges.append(item)

    for g in out_groups:
        if g.get("parent") and g["parent"] not in group_ids:
            warnings.append(f"group '{g['id']}': parent '{g['parent']}' does not exist")
            g.pop("parent")

    if errors:
        raise FlowError("\n".join(errors))

    data = {
        "title": flow.get("title") or "Screen flow",
        "description": flow.get("description") or "",
        "scope": flow.get("scope") or "",
        "platform": flow.get("platform") or "",
        "generatedAt": dt.datetime.now().isoformat(timespec="seconds"),
        "groups": out_groups,
        "screens": out_screens,
        "edges": out_edges,
    }
    return data, warnings


def render(data: dict) -> str:
    template = TEMPLATE.read_text(encoding="utf-8")
    if PLACEHOLDER not in template:
        raise FlowError(f"template {TEMPLATE} is missing the {PLACEHOLDER} marker")
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    payload = payload.replace("</", "<\\/").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
    title = (data["title"] or "Screen flow").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return template.replace("__TITLE__", title, 1).replace(PLACEHOLDER, payload, 1)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("flow", type=Path, help="path to flow.json")
    ap.add_argument("-o", "--out", type=Path, help="output HTML (default: screen-flow.html next to flow.json)")
    ap.add_argument("--max-width", type=int, default=1000, help="downscale wider screenshots (0 = keep size)")
    ap.add_argument("--hotspots", type=Path, help="hotspots JSON (default: hotspots.json next to flow.json, if present)")
    ap.add_argument("--check", action="store_true", help="validate flow.json and images only")
    args = ap.parse_args()

    try:
        data, warnings = load_flow(args.flow, args.max_width, embed=not args.check, hotspots_path=args.hotspots)
    except (FlowError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    for w in warnings:
        print(f"warning: {w}", file=sys.stderr)

    n_img = sum(1 for s in data["screens"] if "w" in s)
    n_hs = sum(1 for e in data["edges"] if "hotspot" in e)
    summary = (f"{len(data['groups'])} groups, {len(data['screens'])} screens ({n_img} with screenshots), "
               f"{len(data['edges'])} links ({n_hs} with hotspots)")
    if args.check:
        print(f"ok: {summary}")
        return 0

    out = args.out or args.flow.parent / "screen-flow.html"
    html = render(data)
    out.write_text(html, encoding="utf-8")
    print(f"wrote {out} ({len(html.encode('utf-8')) / 1_048_576:.1f} MB): {summary}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
