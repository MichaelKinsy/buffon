# SPDX-License-Identifier: Apache-2.0
"""The repository documents (CONTRIBUTING.md, docs/*.md) as HTML for the dashboard's own pages: the subset of Markdown they use, converted to the site's own
components. Standard library only; every character of text is escaped.

Fenced code blocks become a code block with a Copy button, tables sit in a scrolling wrapper, headings carry an id so a link can point at one, and a link goes
through the caller's `href` function (a link to another carried document becomes a route of the site, a link to any other file becomes plain text)."""
import html
import re

FENCE = re.compile(r"^(\s*)(`{3,}|~{3,})\s*([\w+.#-]*)\s*$")
ITEM = re.compile(r"^(\s*)([-*+]|\d+[.)])\s+(.*)$")
BLOCK_START = re.compile(r"(#{1,6}\s|\||>|\s*([-*+]|\d+[.)])\s|\s*(`{3,}|~{3,})|---+\s*$|<!--)")


def slug(text):
    return re.sub(r"[^a-z0-9]+", "-", re.sub(r"[*`]", "", text.lower())).strip("-")


def inline(text, href):
    """Escape, then turn `code`, **bold**, *italic* and [text](url) into tags. `href(url)` gives the link's target, or None for plain text."""
    spans = []

    def keep(m):
        spans.append(f"<code>{html.escape(m.group(2).strip(), quote=False)}</code>")
        return f"\x00{len(spans) - 1}\x00"

    text = re.sub(r"(?<!`)(`+)(?!`)(.+?)(?<!`)\1(?!`)", keep, text)
    out = html.escape(text, quote=False)
    out = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", out)
    out = re.sub(r"(?<![\w*])\*([^*\s][^*]*)\*(?![\w*])", r"<em>\1</em>", out)

    def link(m):
        target = href(html.unescape(m.group(2)))
        return f'<a href="{html.escape(target, quote=True)}">{m.group(1)}</a>' if target else m.group(1)

    out = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", link, out)
    return re.sub(r"\x00(\d+)\x00", lambda m: spans[int(m.group(1))], out)


def cells_of(line):
    return [c.strip() for c in line.strip().strip("|").split("|")]


def is_rule(line):
    return bool(re.fullmatch(r"\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)*\|?", line.strip()))


def code_block(lang, lines):
    body = html.escape("\n".join(lines), quote=False)
    cls = f' class="lang-{html.escape(lang, quote=True)}"' if lang else ""
    return f'<div class="codeblock"><button type="button" class="btn small" data-copy-code>Copy</button><pre><code{cls}>{body}</code></pre></div>'


def list_html(lines, href):
    """Bullets and numbered items; an item indented deeper than its parent opens a nested list, and an indented line without a marker continues the item above."""
    items = []   # (indent, ordered, [text lines])
    for line in lines:
        m = ITEM.match(line)
        if m:
            items.append([len(m.group(1).expandtabs(4)), m.group(2)[0].isdigit(), [m.group(3)]])
        elif line.strip() and items:
            items[-1][2].append(line.strip())

    def build(i, indent):
        ordered = items[i][1]
        out, tag = [], "ol" if ordered else "ul"
        while i < len(items) and items[i][0] >= indent:
            if items[i][0] > indent:
                inner, i = build(i, items[i][0])
                out[-1] = out[-1][:-5] + inner + "</li>" if out else inner
                continue
            out.append(f"<li>{inline(' '.join(items[i][2]), href)}</li>")
            i += 1
        return f"<{tag}>" + "".join(out) + f"</{tag}>", i

    out, i = [], 0
    while i < len(items):
        part, i = build(i, items[i][0])
        out.append(part)
    return "".join(out)


def convert(text, href=lambda url: url):
    """Markdown -> HTML body."""
    return _convert(text.splitlines(), href)


def _convert(lines, href):
    out, i = [], 0
    while i < len(lines):
        line = lines[i]
        fence = FENCE.match(line)
        if not line.strip():
            i += 1
        elif line.lstrip().startswith("<!--"):
            while i < len(lines) and "-->" not in lines[i]:
                i += 1
            i += 1
        elif fence:
            mark, lang, body = fence.group(2), fence.group(3), []
            i += 1
            while i < len(lines) and not (lines[i].strip().startswith(mark[0] * len(mark)) and set(lines[i].strip()) == {mark[0]}):
                body.append(lines[i][len(fence.group(1)):] if lines[i].startswith(fence.group(1)) else lines[i])
                i += 1
            i += 1
            out.append(code_block(lang, body))
        elif m := re.match(r"(#{1,6})\s+(.*?)\s*#*\s*$", line):
            out.append(f'<h{len(m.group(1))} id="{slug(m.group(2))}">{inline(m.group(2), href)}</h{len(m.group(1))}>')
            i += 1
        elif line.startswith("|") and i + 1 < len(lines) and is_rule(lines[i + 1]):
            header, aligns = cells_of(line), [("right" if c.strip().endswith(":") else "") for c in cells_of(lines[i + 1])]
            i += 2
            rows = []
            while i < len(lines) and lines[i].startswith("|"):
                rows.append(cells_of(lines[i]))
                i += 1
            body = "".join("<tr>" + "".join(f'<td{" class=num" if aligns[k:k + 1] == ["right"] else ""}>{inline(c, href)}</td>' for k, c in enumerate(r)) + "</tr>" for r in rows)
            out.append('<div class="tablewrap"><table class="doc"><thead><tr>' + "".join(f"<th>{inline(c, href)}</th>" for c in header) + f"</tr></thead><tbody>{body}</tbody></table></div>")
        elif line.startswith(">"):
            block = []
            while i < len(lines) and lines[i].startswith(">"):
                block.append(lines[i][1:].strip())
                i += 1
            out.append("<blockquote>" + _convert(block, href) + "</blockquote>")
        elif ITEM.match(line):
            block = []
            while i < len(lines) and (ITEM.match(lines[i]) or (lines[i].strip() and lines[i][:1] in " \t" and not FENCE.match(lines[i])) or
                                      (not lines[i].strip() and i + 1 < len(lines) and (ITEM.match(lines[i + 1]) or lines[i + 1][:2] == "  ") and not FENCE.match(lines[i + 1]))):
                block.append(lines[i])
                i += 1
            out.append(list_html(block, href))
        elif re.match(r"(---+|\*\*\*+)\s*$", line):
            out.append("<hr>")
            i += 1
        else:
            para = []
            while i < len(lines) and lines[i].strip() and not (para and BLOCK_START.match(lines[i])):
                para.append(lines[i].strip())
                i += 1
            out.append(f"<p>{inline(' '.join(para), href)}</p>")
    return "\n".join(out)
