# SPDX-License-Identifier: Apache-2.0
"""The checks on a project's picture (profiles/assets/): what the build verifies and what tools/profiles_refresh.py applies before it stores a file.

An SVG may draw, nothing else: no script, no foreignObject, no event attribute, no reference to anything outside the file. A PNG or a WebP is at most 250 KB and 960 px wide.
The sanitiser removes what the checker would refuse; the checker is the rule, and it runs again at every build."""
import re
import struct
import xml.etree.ElementTree as ET

SVG_NS, XLINK_NS = "http://www.w3.org/2000/svg", "http://www.w3.org/1999/xlink"
MAX_IMAGE_BYTES, MAX_IMAGE_WIDTH, MAX_MARK_SIDE, WIDE_ASPECT = 250 * 1024, 960, 256, 2
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
BRANCH_NAMES = {"main", "master", "head", "trunk", "develop", "dev", "latest", "stable", "next"}
IMAGE_DATA = r"data:image/(?:png|jpeg|gif|webp);base64,[A-Za-z0-9+/=\s]*"
DROP_ELEMENTS = {"script", "foreignobject", "iframe", "object", "embed", "audio", "video", "canvas", "metadata", "set", "handler", "listener"}
LINK_ATTRS = {"href", f"{{{XLINK_NS}}}href"}
for _prefix, _uri in (("", SVG_NS), ("xlink", XLINK_NS)):
    ET.register_namespace(_prefix, _uri)

_XMLNS = re.compile(r'\sxmlns(?::\w+)?\s*=\s*["\'](?:http://www\.w3\.org/2000/svg|http://www\.w3\.org/1999/xlink)["\']', re.I)
_EVENT = re.compile(r'[\s"\'/]on[a-z]+\s*=', re.I)
_LINK = re.compile(r'\b(?:xlink:)?href\s*=\s*(["\'])(.*?)\1', re.I | re.S)
_URL = re.compile(r'url\(\s*([\'"]?)\s*([^)\'"]*)', re.I)
_DATA = re.compile(r'data:\s*([^;,\s)"\']*)', re.I)


def branch_name(ref):
    """True for a ref that moves: main, master, HEAD and the like, or anything under refs/heads."""
    return ref.strip().lower() in BRANCH_NAMES or ref.startswith("refs/heads/") or ref.lower().startswith(("origin/", "heads/"))


def svg_problems(data):
    """The reasons an SVG (bytes) may not be shown, as plain phrases; empty when it is clean."""
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return ["not UTF-8 text"]
    bad = []
    try:
        root = ET.fromstring(data)
    except ET.ParseError as error:
        return [f"not well-formed XML ({error})"]
    if root.tag != f"{{{SVG_NS}}}svg":
        bad.append("the root element is not svg")
    elif not (root.get("viewBox") or (root.get("width") and root.get("height"))):
        bad.append("no viewBox and no width and height")
    if re.search(r"<!ENTITY|<!DOCTYPE", text, re.I):
        bad.append("a DOCTYPE or ENTITY declaration")
    for name in sorted({t.lower() for t in re.findall(r"<\s*([A-Za-z][\w:-]*)", text)} & DROP_ELEMENTS):
        bad.append(f"a {name} element")
    if _EVENT.search(text):
        bad.append("an on* event attribute")
    for _, target in _LINK.findall(text):
        if not (target.startswith("#") or re.fullmatch(IMAGE_DATA, target.strip(), re.I)):
            bad.append("an external or non-image href")
            break
    for _, target in _URL.findall(text):
        if not target.startswith("#"):
            bad.append("an external url() reference")
            break
    if re.search(r"@import", text, re.I):
        bad.append("an @import")
    if re.search(r"javascript:|expression\(", text, re.I):
        bad.append("a script URL")
    if re.search(r"https?://|//[\w-]+\.[\w.-]+/", _XMLNS.sub("", text), re.I):
        bad.append("an http(s) reference")
    for kind in _DATA.findall(text):
        if not re.fullmatch(r"image/(?:png|jpeg|gif|webp)", kind.lower()):
            bad.append("a data: URI that is not a raster image")
            break
    return bad


def _clean_style(css):
    """The CSS text without its @import rules, or None when it still points outside the file."""
    css = re.sub(r"@import[^;]*;?", "", css, flags=re.I)
    if any(not target.startswith("#") for _, target in _URL.findall(css)) or re.search(r"javascript:|expression\(", css, re.I):
        return None
    return css


def sanitize_svg(data):
    """The SVG (bytes) with every element and attribute the checker refuses taken out, as UTF-8 bytes; ValueError when what is left is not a valid logo.
    Only the SVG namespace and xlink stay: editor metadata (inkscape, sodipodi, rdf) goes."""
    if re.search(rb"<!ENTITY", data, re.I):
        raise ValueError("it declares entities")
    data = re.sub(rb"<!DOCTYPE[^>\[]*>", b"", data, flags=re.I)
    try:
        root = ET.fromstring(data)
    except ET.ParseError as error:
        raise ValueError(f"not well-formed XML ({error})") from None

    def local(tag):
        return tag.rsplit("}", 1)[-1].lower() if isinstance(tag, str) else ""

    def walk(el):
        for child in list(el):
            if not isinstance(child.tag, str) or not child.tag.startswith(f"{{{SVG_NS}}}") or local(child.tag) in DROP_ELEMENTS:
                el.remove(child)
                continue
            if local(child.tag) == "animate" and (child.get("attributeName") or "").lower().endswith("href"):
                el.remove(child)
                continue
            if local(child.tag) == "style":
                css = _clean_style(child.text or "")
                if css is None:
                    el.remove(child)
                    continue
                child.text = css
            for key in list(child.attrib):
                value = child.attrib[key]
                ns = key.startswith("{") and key[1:].split("}")[0]
                if (ns and ns not in (XLINK_NS,)) or key.lower().startswith("on"):
                    del child.attrib[key]
                elif key in LINK_ATTRS and not (value.startswith("#") or re.fullmatch(IMAGE_DATA, value.strip(), re.I)):
                    del child.attrib[key]
                elif key != "d" and (any(not t.startswith("#") for _, t in _URL.findall(value)) or re.search(r"javascript:|expression\(|@import", value, re.I)):
                    del child.attrib[key]
            walk(child)

    for key in list(root.attrib):
        if key.startswith("{") and not key.startswith(f"{{{XLINK_NS}}}") or key.lower().startswith("on"):
            del root.attrib[key]
    walk(root)
    out = (ET.tostring(root, encoding="unicode").strip() + "\n").encode("utf-8")
    problems = svg_problems(out)
    if problems:
        raise ValueError("it would not stay a clean SVG: " + ", ".join(problems))
    return out


def png_size(data):
    """(width, height) from a PNG's IHDR, or None when the bytes are not a PNG."""
    if len(data) < 24 or data[:8] != PNG_MAGIC or data[12:16] != b"IHDR":
        return None
    return struct.unpack(">II", data[16:24])


def webp_size(data):
    """(width, height) from a WebP's first chunk (lossy, lossless or extended), or None when the bytes are not a WebP."""
    if len(data) < 30 or data[:4] != b"RIFF" or data[8:12] != b"WEBP":
        return None
    kind = data[12:16]
    if kind == b"VP8 ":
        w, h = struct.unpack("<HH", data[26:30])
        return w & 0x3FFF, h & 0x3FFF
    if kind == b"VP8L":
        bits = int.from_bytes(data[21:25], "little")
        return (bits & 0x3FFF) + 1, ((bits >> 14) & 0x3FFF) + 1
    if kind == b"VP8X":
        return int.from_bytes(data[24:27], "little") + 1, int.from_bytes(data[27:30], "little") + 1
    return None


def raster_size(data):
    """(width, height) of a PNG or a WebP, or None."""
    return png_size(data) or webp_size(data)


def raster_problems(data):
    """The reasons a stored picture (a PNG or a WebP) may not be shown: not one of those, over 250 KB, or wider than 960 px; empty when it is within the caps."""
    size = raster_size(data)
    if size is None:
        return ["not a PNG or a WebP"]
    bad = []
    if len(data) > MAX_IMAGE_BYTES:
        bad.append(f"{len(data)} bytes, at most {MAX_IMAGE_BYTES}")
    if size[0] > MAX_IMAGE_WIDTH or min(size) < 1:
        bad.append(f"{size[0]}x{size[1]} px, at most {MAX_IMAGE_WIDTH} wide")
    return bad


def svg_size(data):
    """(width, height) of an SVG from its viewBox, else its width and height, or None."""
    try:
        root = ET.fromstring(data)
    except ET.ParseError:
        return None
    box = re.split(r"[\s,]+", (root.get("viewBox") or "").strip())
    try:
        if len(box) == 4:
            return float(box[2]), float(box[3])
        return float(re.match(r"[\d.]+", root.get("width", "")).group(0)), float(re.match(r"[\d.]+", root.get("height", "")).group(0))
    except (ValueError, AttributeError):
        return None


def image_kind(file, data):
    """"mark" for a logo shown beside the title, "strip" for a wide or large picture (a banner, a splash screen, a demo) shown across the top of a card, cropped to its middle.
    A vector drawing is always a mark, so that a wide wordmark is never cropped; a raster picture is a mark only when it is small (at most 256 px) and not wider than 2:1."""
    if file.endswith(".svg"):
        return "mark"
    size = raster_size(data)
    if size is None or min(size) <= 0:
        return "mark"
    return "mark" if max(size) <= MAX_MARK_SIDE and size[0] / size[1] <= WIDE_ASPECT else "strip"
