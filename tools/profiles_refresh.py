# SPDX-License-Identifier: Apache-2.0
"""Stores what a project's own README says about it, for the site: the title, the first paragraphs, its first wide picture and the project's square mark, read at a pinned ref.

    python3 tools/profiles_refresh.py <project> [--ref TAG_OR_COMMIT] [--readme-url URL] [--date YYYY-MM-DD]

<project> is the file name of profiles/<project>.toml. The README comes from raw.githubusercontent.com at the ref (a tag or a commit; a branch name is refused, because it moves)
or from --readme-url (a raw or a github.com blob URL). The tool writes readme_url, readme_ref, readme_title, readme_head and retrieved into the profile, and the README's first
picture before its first section (a banner, a splash screen or a demo, never a badge) to profiles/assets/<project>.<png|webp> with logo, logo_source, logo_sha256 and logo_alt: the harness page shows it as
"From its README". A first picture that is itself a mark (a vector drawing, or a small square raster) is the project's mark instead, unless the profile already names one.
The mark is the one square tile on a card (profiles/assets/<project>-mark.<svg|png|webp>, with mark, mark_source, mark_ref, mark_sha256). Its source is the profile's mark_source: an SVG is sanitised and a
raster that fits is kept; with mark_crop = [x, y, side, side], in pixels of the source (the first frame of a GIF), the square is cut with ffmpeg and scaled to 128 px with nearest-neighbour, so pixel art stays sharp.
A mark_source that is not an https URL names a file the owner supplied (a private repository, say): nothing is fetched, the file in profiles/assets must match mark_sha256, and mark_note says whose it is.
An SVG is sanitised. A PNG or WebP within 250 KB and 960 px is kept; any other picture (a GIF's first frame, a JPEG, a large PNG) is scaled to at most 960 px wide and re-encoded, which
needs ffmpeg. The site build fetches nothing: it checks the stored files.
The same fetched bytes give the same files."""
import argparse
import datetime
import hashlib
import html
import io
import json
import os
import re
import shutil
import subprocess
import tempfile
import sys
import tomllib
import urllib.request
from html.parser import HTMLParser
from urllib.parse import quote, urlsplit

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from buffon.dashboard import profiles_check   # noqa: E402

PROFILES = os.path.join(ROOT, "profiles")
RAW = "https://raw.githubusercontent.com"
README_NAMES = ("README.md", "readme.md", "Readme.md")
MAX_PARAGRAPHS = 2
# (no kind of picture is refused for what it shows: a logo, a banner, a splash screen and a demo are all the project's own; only badges and shields are not)
BADGE = re.compile(r"shields\.io|badgen\.net|badge|codecov|coveralls|travis-ci|reuse\.software|scorecard\.dev|/actions/workflows/|sonarcloud|bestpractices\.dev|libraries\.io", re.I)
KEY_ORDER = ("project", "harnesses", "maker", "maker_url", "tagline", "tagline_source", "readme_url", "readme_ref", "readme_title", "readme_head",
             "logo", "logo_source", "logo_sha256", "logo_alt", "mark", "mark_source", "mark_ref", "mark_sha256", "mark_crop", "mark_bg", "mark_alt", "mark_note", "monogram",
             "retrieved", "licence", "licence_note")
MARK_PX = 128


class RefreshError(Exception):
    pass


# fetching

def fetch(url):
    """The bytes at url, redirects followed. urllib first, then curl: a failure of both names both."""
    request = urllib.request.Request(url, headers={"User-Agent": "buffon-profiles-refresh"})
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return response.read()
    except Exception as first:
        try:
            return subprocess.run(["curl", "-sSL", "--fail", "--max-time", "90", url], stdin=subprocess.DEVNULL, capture_output=True, check=True).stdout
        except Exception as second:
            raise RefreshError(f"could not fetch {url}: urllib said {first}; curl said {getattr(second, 'stderr', b'').decode(errors='replace').strip() or second}") from None


# the README

def blocks(text):
    """[(kind, text)] for the blocks of a README, in order. Kinds: heading1, heading, para, html, quote, list, table, fence, hr, refdef."""
    text = re.sub(r"<!--.*?-->", "", text.replace("\r\n", "\n"), flags=re.S)
    out, cur, fence = [], [], None

    def flush():
        if cur:
            out.append(classify("\n".join(cur)))
            cur.clear()

    for line in text.split("\n"):
        if fence:
            cur.append(line)
            if line.strip().startswith(fence):
                fence = None
                flush()
            continue
        m = re.match(r"\s{0,3}(```+|~~~+)", line)
        if m:
            flush()
            fence = m.group(1)
            cur.append(line)
        elif not line.strip():
            flush()
        elif re.match(r"\s{0,3}#{1,6}\s", line):
            flush()
            cur.append(line)
            flush()
        else:
            cur.append(line)
    flush()
    return out


def classify(block):
    lines = block.split("\n")
    first = lines[0].lstrip()
    if first.startswith(("```", "~~~")):
        return "fence", block
    m = re.match(r"(#{1,6})\s+(.*?)\s*#*\s*$", first)
    if m and len(lines) == 1:
        return ("heading1" if len(m.group(1)) == 1 else "heading"), m.group(2)
    if len(lines) == 2 and re.fullmatch(r"=+\s*", lines[1]):
        return "heading1", lines[0].strip()
    if len(lines) == 2 and re.fullmatch(r"-+\s*", lines[1]):
        return "heading", lines[0].strip()
    if re.fullmatch(r"([-*_]\s*){3,}", block.strip()):
        return "hr", block
    if all(re.match(r"\s*\[[^\]]+\]:\s*\S", l) for l in lines):
        return "refdef", block
    if first.startswith(">"):
        return "quote", block
    if re.match(r"([-*+]|\d+[.)])\s", first):
        return "list", block
    if first.startswith("|"):
        return "table", block
    if first.startswith("<") and not first.startswith(("<http", "<mailto")):
        return "html", block
    return "para", block


class _Html(HTMLParser):
    """Text of HTML in paragraphs: block tags and <br> end a paragraph, images and scripts add nothing; the h1 text and a leading bold are kept apart."""
    BLOCK = {"p", "div", "br", "h1", "h2", "h3", "h4", "h5", "h6", "li", "ul", "ol", "tr", "table", "blockquote", "section", "center", "hr", "details", "summary"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.paras, self.h1, self.lead, self._h1, self._lead, self._skip, self.images = [""], None, None, None, None, 0, []

    def _break(self):
        if self.paras[-1].strip():
            self.paras.append("")

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self._skip += 1
        if tag in self.BLOCK:
            self._break()
        if tag == "img":
            self.images.append(len(self.paras) - 1)
        if tag == "h1":
            self._h1 = ""
        if tag in ("strong", "b") and not self.paras[-1].strip() and self.lead is None and self._lead is None:
            self._lead = ""

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self._skip = max(0, self._skip - 1)
        if tag == "h1" and self._h1 is not None:
            self.h1 = self.h1 or clean(self._h1)
            self._h1 = None
        elif tag in ("strong", "b") and self._lead is not None:
            self.lead = clean(self._lead)
            self._lead = None
        if tag in self.BLOCK:
            self._break()

    def handle_data(self, data):
        if self._skip:
            return
        if self._h1 is not None:
            self._h1 += data
            return
        if self._lead is not None:
            self._lead += data
        self.paras[-1] += data


def clean(text):
    return re.sub(r"\s+", " ", text).strip()


def plain(text):
    """Text without Markdown marks: entities decoded, escapes undone, emphasis, strike-through and code marks removed, spaces collapsed."""
    text = html.unescape(text)
    text = re.sub(r"\\([\\`*_{}\[\]()#+\-.!|<>])", r"\1", text)
    text = re.sub(r"`([^`]*)`", r"\1", text)
    text = re.sub(r"(\*\*|__)(.+?)\1", r"\2", text)
    text = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?!\w)", r"\1", text)
    text = re.sub(r"(?<![\w])_(?!\s)(.+?)(?<!\s)_(?![\w])", r"\1", text)
    return clean(re.sub(r"~~(.+?)~~", r"\1", text))


def links_as_text(text):
    """Autolinks as their address, images dropped, links reduced to their text."""
    text = re.sub(r"<((?:https?|mailto):[^>\s]+)>", r"\1", text)
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)|!\[[^\]]*\]\[[^\]]*\]|!\[[^\]]*\](?![(\[])", "", text)
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
    return re.sub(r"\[([^\]]+)\]\[[^\]]*\]", r"\1", text)


def inline(text):
    """Plain text of one line of Markdown or HTML: no images, links as their text, no marks."""
    text = links_as_text(text)
    return plain(re.sub(r"<[^>]+>", "", text)) if re.search(r"</?[A-Za-z][^>]*>", text) else plain(text)


def paragraphs(block):
    """(paragraphs, h1, lead, ended) of a para or html block: plain text, no markup. h1 is the text of an <h1>, lead a bold phrase that opens the block, ended says an image-only
    line (a badge row) follows the text inside the block, so the head stops there."""
    text = links_as_text(block)
    h1 = lead = None
    ended = False
    if re.search(r"</?[A-Za-z][^>]*>", text):
        parser = _Html()
        parser.feed(text)
        parser.close()
        paras, h1, lead = parser.paras, parser.h1 and plain(parser.h1), parser.lead and plain(parser.lead)
        for at in parser.images:
            if at < len(paras) and not paras[at].strip() and any(p.strip() for p in paras[:at]):
                paras, ended = paras[:at], True
                break
    else:
        paras = [text]
    plains = [plain(p) for p in paras]
    return [p for p in plains if p and not mostly_links(p)], h1, lead, ended


def mostly_links(para):
    """A line of "Website: <url> · Docs: <url>" is navigation, not a sentence."""
    if not re.search(r"https?://", para):
        return False
    return len([w for w in re.sub(r"https?://\S+", " ", para).split() if re.search(r"\w", w)]) <= 3


def images(block):
    """[(src, alt)] of the images of a block, in order: Markdown images and <img> tags."""
    found = []
    for m in re.finditer(r"!\[([^\]]*)\]\(\s*<?([^)\s>]+)>?(?:\s+\"[^\"]*\")?\s*\)", block):
        found.append((m.start(), m.group(2), m.group(1)))
    for m in re.finditer(r"<img\b[^>]*>", block, re.I):
        src = re.search(r"\bsrc\s*=\s*([\"'])(.*?)\1", m.group(0), re.I | re.S)
        alt = re.search(r"\balt\s*=\s*([\"'])(.*?)\1", m.group(0), re.I | re.S)
        if src:
            found.append((m.start(), html.unescape(src.group(2).strip()), html.unescape(alt.group(2)) if alt else ""))
    return [(s, a) for _, s, a in sorted(found)]


def logo_candidates(items):
    """The pictures at the top of the README, in order: every image before its first section heading (the title line is not one), less badges and shields. The first is the project's picture:
    a logo, a banner, a splash screen or a demo."""
    out, titled = [], False
    for kind, text in items:
        if kind == "heading1" and not titled:
            titled = True
            continue
        if kind in ("heading", "heading1", "fence"):
            break
        if kind in ("para", "html"):
            out += [(src, alt) for src, alt in images(text) if not BADGE.search(src + " " + alt)]
    return out


def parse_readme(text, project):
    """{title, head, logos}: the title line, 1 to 2 paragraphs of plain text, and the logo candidates [(src, alt)] of a README."""
    items = blocks(text)
    title, lead, head = None, None, []
    for kind, block in items:
        if kind == "heading1" and title is None and not head:
            title = inline(block) or None
            continue
        if kind in ("heading", "heading1", "fence", "list", "table", "hr") or (kind == "quote" and head):
            if head:
                break
            continue
        if kind in ("para", "html"):
            paras, h1, bold, ended = paragraphs(block)
            if h1 and title is None and not head:
                title = h1
            if bold and lead is None and not head:
                lead = bold
            if not paras:
                if head and not h1:
                    break
                continue
            head += paras
            if ended:
                break
            if len(head) >= MAX_PARAGRAPHS:
                break
    logos = logo_candidates(items)
    if title is None:
        alt = re.sub(r"\s*\b(logo|icon|mark)\b\s*$", "", logos[0][1], flags=re.I).strip() if logos and logos[0][1] else ""
        title = lead or alt or project
    return {"title": title, "head": head[:MAX_PARAGRAPHS], "logos": logos}


# the logo

def resolve(src, owner, repo, ref, directory=""):
    """The https URL of an image the README names: relative paths against raw.githubusercontent.com at the ref, GitHub blob links as raw links."""
    src = src.strip()
    if src.startswith("//"):
        src = "https:" + src
    if src.startswith("http://"):
        src = "https://" + src[len("http://"):]
    if src.startswith("https://"):
        m = re.match(r"https://github\.com/([^/]+)/([^/]+)/(?:blob|raw)/([^/]+)/(.+?)(?:\?.*)?$", src)
        return f"{RAW}/{m.group(1)}/{m.group(2)}/{m.group(3)}/{m.group(4)}" if m else src
    path = src.split("#")[0].split("?")[0]
    path = path.lstrip("/") if path.startswith("/") else os.path.normpath(os.path.join(directory, path))
    return f"{RAW}/{owner}/{repo}/{ref}/{quote(path, safe='/%')}"


def sniff(data):
    head = data[:16]
    if head.startswith(profiles_check.PNG_MAGIC):
        return "png"
    if head.startswith(b"\xff\xd8\xff"):
        return "jpg"
    if head.startswith((b"GIF87a", b"GIF89a")):
        return "gif"
    if head[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    if b"<svg" in data[:4096].lower() and not data.lstrip()[:15].lower().startswith((b"<!doctype html", b"<html")):
        return "svg"
    return None


def to_raster(data):
    """(extension, bytes) of the first frame of any raster picture (PNG, JPEG, GIF, WebP), at most 960 px wide and 250 KB, made with ffmpeg: a PNG when it fits, else a WebP, then a narrower one.
    None when ffmpeg is missing or nothing fits. The same bytes in give the same bytes out for one ffmpeg."""
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return None
    with tempfile.TemporaryDirectory() as tmp:
        src = os.path.join(tmp, "in")
        with open(src, "wb") as f:
            f.write(data)
        for width in (profiles_check.MAX_IMAGE_WIDTH, 800, 640, 480, 320):
            for ext, codec in (("png", ["-c:v", "png"]), ("webp", ["-c:v", "libwebp", "-quality", "80"]), ("webp", ["-c:v", "libwebp", "-quality", "60"])):
                out = os.path.join(tmp, "out." + ext)
                run = subprocess.run([ffmpeg, "-v", "error", "-y", "-i", src, "-frames:v", "1", "-vf", f"scale='min({width},iw)':-2:flags=lanczos", *codec, out],
                                     stdin=subprocess.DEVNULL, capture_output=True)
                if run.returncode == 0 and os.path.exists(out):
                    with open(out, "rb") as f:
                        result = f.read()
                    if len(result) <= profiles_check.MAX_IMAGE_BYTES:
                        return ext, result
    return None


def make_logo(url, data):
    """(extension, bytes, note) of the picture to store from the fetched bytes, or raises RefreshError saying why there is none."""
    kind = sniff(data)
    if kind is None:
        raise RefreshError("what it names is not an image")
    if kind == "svg":
        try:
            return "svg", profiles_check.sanitize_svg(data), "sanitised"
        except ValueError as error:
            raise RefreshError(str(error)) from None
    if kind in ("png", "webp") and not profiles_check.raster_problems(data):
        return kind, data, "as published"
    converted = to_raster(data)
    if converted is None:
        raise RefreshError(f"it is a {kind.upper()} that does not fit in 250 KB and 960 px, and ffmpeg is not installed or could not convert it")
    ext, raster = converted
    return ext, raster, f"first frame of the {kind.upper()}, scaled to at most {profiles_check.MAX_IMAGE_WIDTH} px wide" if kind == "gif" else f"converted from {kind.upper()}, at most {profiles_check.MAX_IMAGE_WIDTH} px wide"


def crop_mark(data, crop, size=MARK_PX):
    """The PNG (bytes) of the square crop = [x, y, side, side] of the first frame of a raster picture, scaled to size px with nearest-neighbour (pixel art stays sharp). The same bytes in give the same bytes out for one ffmpeg."""
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RefreshError("ffmpeg is not installed: a mark_crop needs it")
    x, y, w, h = crop
    with tempfile.TemporaryDirectory() as tmp:
        src, out = os.path.join(tmp, "in"), os.path.join(tmp, "out.png")
        with open(src, "wb") as f:
            f.write(data)
        run = subprocess.run([ffmpeg, "-v", "error", "-y", "-i", src, "-frames:v", "1", "-vf", f"crop={w}:{h}:{x}:{y},scale={size}:{size}:flags=neighbor", "-c:v", "png", out], stdin=subprocess.DEVNULL, capture_output=True)
        if run.returncode != 0 or not os.path.exists(out):
            raise RefreshError("ffmpeg could not crop it: " + run.stderr.decode(errors="replace").strip())
        with open(out, "rb") as f:
            return f.read()


def make_mark(data, crop=None):
    """(extension, bytes, note) of the mark to store from the fetched bytes: a cropped square PNG, a sanitised SVG or a raster within the caps."""
    kind = sniff(data)
    if kind is None:
        raise RefreshError("what it names is not an image")
    if crop:
        if kind == "svg":
            raise RefreshError("a vector mark is not cropped: drop mark_crop")
        return "png", crop_mark(data, crop), f"crop {crop}, {MARK_PX} px"
    if kind == "svg":
        try:
            return "svg", profiles_check.sanitize_svg(data), "sanitised"
        except ValueError as error:
            raise RefreshError(str(error)) from None
    if kind in ("png", "webp") and not profiles_check.raster_problems(data) and profiles_check.raster_size(data)[0] == profiles_check.raster_size(data)[1]:
        return kind, data, "as published"
    raise RefreshError(f"it is a {kind.upper()} that is not a square within the caps: give a mark_crop")


def pick_logo(candidates, owner, repo, ref, directory, get):
    """(url, ext, bytes, note, notes, alt): the README's first picture, stored; the reasons of the ones passed over; the picture's alt text."""
    notes = []
    for src, alt in candidates[:1]:
        url = resolve(src, owner, repo, ref, directory)
        alt = re.sub(r"\s+", " ", alt or "").strip()[:160]
        try:
            ext, data, note = make_logo(url, get(url))
            return url, ext, data, note, notes, alt
        except RefreshError as error:
            notes.append(f"{url}: {error}")
            if url.lower().endswith(".png"):   # a PNG that will not fit: the same name as an SVG, if the repository has one
                alt_url = url[:-4] + ".svg"
                try:
                    ext, data, note = make_logo(alt_url, get(alt_url))
                    return alt_url, ext, data, "SVG alternative, " + note, notes, alt
                except RefreshError as second:
                    notes.append(f"{alt_url}: {second}")
    return None, None, None, None, notes, ""


# the profile

def toml_string(value):
    return json.dumps(value, ensure_ascii=False).replace("\x7f", "\\u007f")


def toml_text(data):
    """The profile as TOML in the layout the files already have: keys in a fixed order, [links], then one [[quotes]] table per quote."""
    lines = []
    for key in sorted((k for k in data if k not in ("links", "quotes")), key=lambda k: KEY_ORDER.index(k) if k in KEY_ORDER else len(KEY_ORDER)):
        value = data[key]
        if key == "readme_head":
            lines.append(f"{key} = [")
            lines += [f"    {toml_string(v)}," for v in value]
            lines.append("]")
        elif isinstance(value, list):
            lines.append(f"{key} = [{', '.join(toml_string(v) for v in value)}]")
        else:
            lines.append(f"{key} = {toml_string(value)}")
    if data.get("links"):
        lines += ["", "[links]"] + [f"{k} = {toml_string(v)}" for k, v in data["links"].items()]
    for q in data.get("quotes") or []:
        lines += ["", "[[quotes]]"] + [f"{k} = {toml_string(q[k])}" for k in ("text", "source", "about") if k in q]
    return "\n".join(lines) + "\n"


def parse_url(url):
    """(owner, repo, ref, path) of a raw.githubusercontent.com URL or a github.com blob URL."""
    parts = urlsplit(url)
    segs = parts.path.strip("/").split("/")
    if parts.netloc == "raw.githubusercontent.com" and len(segs) >= 4:
        return segs[0], segs[1], segs[2], "/".join(segs[3:])
    if parts.netloc == "github.com" and len(segs) >= 5 and segs[2] in ("blob", "raw"):
        return segs[0], segs[1], segs[3], "/".join(segs[4:])
    raise RefreshError(f"{url} is not a raw.githubusercontent.com or github.com blob URL")


def place_mark(out, project, first_mark, readme_ref, get, assets=None):
    """(lines, bytes or None): the mark of the profile `out`, and updates out. The profile's mark_source wins: an https URL is fetched (cropped when mark_crop is set) and the ref is the one in a GitHub URL;
    a source that is not an https URL is an owner-supplied file, checked against mark_sha256 and never fetched. With no mark_source, the README's first picture is the mark when it is one. Nothing is written here."""
    source = out.get("mark_source")
    if source and not source.startswith("https://"):
        path = os.path.join(assets or os.path.join(PROFILES, "assets"), str(out.get("mark", "")))
        if not out.get("mark_note"):
            raise RefreshError("mark_source is not an https URL, so mark_note must say who supplied the file")
        try:
            with open(path, "rb") as f:
                raw = f.read()
        except OSError:
            raise RefreshError(f"the owner-supplied mark {out.get('mark')} is not in profiles/assets") from None
        if hashlib.sha256(raw).hexdigest() != out.get("mark_sha256"):
            raise RefreshError(f"the owner-supplied mark {out.get('mark')} does not match its mark_sha256")
        found = profiles_check.svg_problems(raw) if path.endswith(".svg") else profiles_check.raster_problems(raw)
        if found:
            raise RefreshError(f"the owner-supplied mark {out.get('mark')}: " + ", ".join(found))
        return [f"  mark: {out['mark']}, {len(raw)} bytes, supplied by the owner ({source}), not fetched; sha256 checked"], None
    if source:
        url = resolve(source, "", "", "")
        ext, data, note = make_mark(get(url), out.get("mark_crop"))
        ref = out.get("mark_ref")
    elif first_mark:
        url, ext, data, note = first_mark
        ref = readme_ref
        out["mark_source"] = url
    else:
        return ["  mark: none"], None
    m = re.match(RAW + r"/[^/]+/[^/]+/([^/]+)/", url)
    if m:
        ref = m.group(1)
    if not ref:
        raise RefreshError("mark_ref is needed: a mark that is not at a GitHub ref has no ref to read from the URL")
    if profiles_check.branch_name(ref):
        raise RefreshError(f"mark ref {ref} is a branch, and a branch moves: pin a tag or a commit")
    out.update(mark=f"{project}-mark.{ext}", mark_sha256=hashlib.sha256(data).hexdigest(), mark_ref=ref)
    return [f"  mark: {project}-mark.{ext}, {len(data)} bytes, from {url} at {ref} ({note})"], data


def refresh(project, ref=None, readme_url=None, today=None, profiles=PROFILES, get=fetch):
    """Fetch, parse and store; the lines to print. Nothing is written when anything before the writing fails."""
    path = os.path.join(profiles, project + ".toml")
    with open(path, "rb") as f:
        data = tomllib.load(f)
    links_repo = urlsplit((data.get("links") or {}).get("repo", "")).path.strip("/").split("/")
    if len(links_repo) < 2:
        raise RefreshError(f"{project}: links.repo is not a GitHub repository URL")
    owner, repo = links_repo[0], re.sub(r"\.git$", "", links_repo[1])
    names = README_NAMES
    if readme_url:
        owner, repo, url_ref, name = parse_url(readme_url)
        ref, names = ref or url_ref, (name,)
        if url_ref != ref:
            raise RefreshError(f"--ref {ref} is not the ref in the URL ({url_ref})")
    ref = ref or data.get("readme_ref")
    if not ref:
        raise RefreshError("give --ref: a tag or a commit")
    if profiles_check.branch_name(ref):
        raise RefreshError(f"{ref} is a branch, and a branch moves: pin a tag or a commit")
    text, used, errors = None, None, []
    for name in names:
        try:
            raw = get(f"{RAW}/{owner}/{repo}/{ref}/{name}")
            text, used = raw.decode("utf-8-sig"), name
            break
        except (RefreshError, UnicodeDecodeError) as error:
            errors.append(str(error))
    if text is None:
        raise RefreshError("; ".join(errors))
    parsed = parse_readme(text, data["project"])
    if not parsed["head"]:
        raise RefreshError("the README has no paragraph before its first heading")
    directory = os.path.dirname(used)
    out = {k: v for k, v in data.items() if k not in ("readme_url", "readme_ref", "readme_title", "readme_head", "logo", "logo_source", "logo_sha256", "logo_alt")}
    out.update(readme_url=f"https://github.com/{owner}/{repo}/blob/{ref}/{used}", readme_ref=ref, readme_title=parsed["title"], readme_head=parsed["head"],
               retrieved=today or datetime.date.today().isoformat())
    url, ext, logo, note, notes, alt = pick_logo(parsed["logos"], owner, repo, ref, directory, get)
    first_mark = None
    if logo and profiles_check.image_kind(f"x.{ext}", logo) == "mark":   # the README's first picture is a mark: it is not a "From its README" figure
        first_mark, logo = (url, ext, logo, note), None
    said_mark, mark_file = place_mark(out, project, first_mark, ref, get, os.path.join(profiles, "assets"))
    said = [f"{project}: {owner}/{repo}@{ref}", f"  title: {parsed['title']}", f"  head: {len(parsed['head'])} paragraphs, {sum(len(p.split()) for p in parsed['head'])} words"]
    assets = os.path.join(profiles, "assets")
    for stale in (".svg", ".png", ".webp"):
        if os.path.exists(os.path.join(assets, project + stale)):
            os.remove(os.path.join(assets, project + stale))
    if mark_file:
        os.makedirs(assets, exist_ok=True)
        for stale in (".svg", ".png", ".webp"):
            if os.path.exists(os.path.join(assets, project + "-mark" + stale)):
                os.remove(os.path.join(assets, project + "-mark" + stale))
        with open(os.path.join(assets, out["mark"]), "wb") as f:
            f.write(mark_file)
    if logo:
        os.makedirs(assets, exist_ok=True)
        with open(os.path.join(assets, f"{project}.{ext}"), "wb") as f:
            f.write(logo)
        out.update(logo=f"{project}.{ext}", logo_source=url, logo_sha256=hashlib.sha256(logo).hexdigest())
        if alt:
            out["logo_alt"] = alt
        said.append(f"  picture: {project}.{ext}, {len(logo)} bytes, from {url} ({note})")
    else:
        said.append("  picture: none" + ("" if parsed["logos"] else " (the README shows none before its first section)"))
    said += said_mark + [f"  passed over: {n}" for n in notes]
    with open(path, "w", encoding="utf-8") as f:
        f.write(toml_text(out))
    return said


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("project")
    parser.add_argument("--ref")
    parser.add_argument("--readme-url")
    parser.add_argument("--date", help="the retrieved date (default today)")
    args = parser.parse_args(argv)
    try:
        print("\n".join(refresh(args.project, args.ref, args.readme_url, args.date)))
    except (RefreshError, OSError) as error:
        print(f"{args.project}: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
