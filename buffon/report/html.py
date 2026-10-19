# SPDX-License-Identifier: Apache-2.0
"""report.html from the same lines as report.md: a converter for the subset of Markdown the report writes (headings, tables, quotes, lists, rules, paragraphs, bold, code, links),
so the HTML and the Markdown cannot say different things. Standard library only; every character of text is escaped."""
import html
import re

from . import theme


def inline(text):
    """Escape, then turn `code`, **bold**, *italic* and [text](url) into tags."""
    out = html.escape(text, quote=False)
    out = re.sub(r"`([^`]+)`", lambda m: f"<code>{m.group(1)}</code>", out)
    out = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", out)
    out = re.sub(r"(?<![\w*])\*([^*\s][^*]*)\*(?![\w*])", r"<em>\1</em>", out)
    out = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", lambda m: f'<a href="{html.escape(html.unescape(m.group(2)), quote=True)}">{m.group(1)}</a>', out)
    return out


def cells_of(line):
    return [c.strip() for c in line.strip().strip("|").split("|")]


def is_rule(line):
    return bool(re.fullmatch(r"\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)*\|?", line.strip()))


def convert(lines):
    """Markdown lines -> HTML body."""
    out, i = [], 0
    while i < len(lines):
        line = lines[i]
        if not line.strip():
            i += 1
        elif m := re.match(r"(#{1,4}) (.*)", line):
            level = len(m.group(1))
            text = m.group(2)
            anchor = re.sub(r"[^a-z0-9]+", "-", re.sub(r"[*`]", "", text.lower())).strip("-")
            out.append(f'<h{level} id="{anchor}">{inline(text)}</h{level}>')
            i += 1
        elif line.startswith("|") and i + 1 < len(lines) and is_rule(lines[i + 1]):
            header, aligns = cells_of(line), [("right" if c.strip().endswith(":") else "") for c in cells_of(lines[i + 1])]
            i += 2
            rows = []
            while i < len(lines) and lines[i].startswith("|"):
                rows.append(cells_of(lines[i]))
                i += 1
            out.append("<table><thead><tr>" + "".join(f"<th>{inline(c)}</th>" for c in header) + "</tr></thead><tbody>")
            for r in rows:
                out.append("<tr>" + "".join(f'<td{" class=num" if aligns[k:k + 1] == ["right"] else ""}>{inline(c)}</td>' for k, c in enumerate(r)) + "</tr>")
            out.append("</tbody></table>")
        elif line.startswith(">"):
            block = []
            while i < len(lines) and lines[i].startswith(">"):
                block.append(lines[i][1:].strip())
                i += 1
            out.append("<blockquote>" + convert(block) + "</blockquote>")
        elif re.match(r"[-*] ", line):
            out.append("<ul>")
            while i < len(lines) and re.match(r"[-*] ", lines[i]):
                out.append(f"<li>{inline(lines[i][2:])}</li>")
                i += 1
            out.append("</ul>")
        elif line.strip() == "---":
            out.append("<hr>")
            i += 1
        else:
            para = []
            while i < len(lines) and lines[i].strip() and not re.match(r"(#{1,4} |\||>|[-*] |---$)", lines[i]):
                para.append(lines[i])
                i += 1
            out.append(f"<p>{inline(' '.join(para))}</p>")
    return "\n".join(out)


def convert_doc(lines):
    """A repository document embedded in a report: converted like the report, and a link to another file of the repository (which the report is not next to) becomes plain text."""
    out = re.sub(r'<a href="(?!https?:|#)[^"]*">(.*?)</a>', r'<span class="doclink">\1</span>', convert(lines))
    return out.replace("<table>", '<table class="doc">')   # the tables of the report are plain <table>: a test counts them against report.md


def page(title, md_lines, extra_html=""):
    """A complete HTML document in Buffon's theme: the converted Markdown, then `extra_html` (the plots). One static file; nothing is fetched when it is viewed."""
    return (f'<!doctype html>\n<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{html.escape(title)}</title>'
            f'<style>{theme.CSS}</style></head><body><div class="wrap"><div class="top"><a class="brand" href="#">{theme.brand_mark(26)}<span>Buffon</span></a></div>'
            f'<main class="md">\n{convert(md_lines)}\n{extra_html}\n</main></div></body></html>\n')
