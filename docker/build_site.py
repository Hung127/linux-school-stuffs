#!/usr/bin/env python3
"""Assemble the course-notes site from the repository.

This is the build step. It produces a finished site directory that the final
Docker image copies verbatim, so the image never carries the toolchain that
built it.

    python build_site.py [SOURCE_DIR] [OUT_DIR]

Defaults match the container layout: the builder stage copies the repository to
/build/src and expects a finished site in /build/out.

What it does:

  1. copies the static tree (slides, syllabus, lab screenshots, the access.log
     dataset and report.pdf) -- this keeps every relative link in the README
     working, because generated pages land at the same paths as their sources;
  2. renders the Markdown notes to HTML, wrapped in a documentation shell with
     navigation, an on-this-page table of contents, highlighted code blocks and
     a search index, so the README is the landing page rather than a raw file;
  3. drops the rendered .md sources, so a page is served as one file, not two.
"""

from __future__ import annotations

import argparse
import html
import json
import os
import re
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path

from markdown_it import MarkdownIt
from markdown_it.token import Token
from mdit_py_plugins.anchors import anchors_plugin
from pygments import highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import get_lexer_by_name
from pygments.util import ClassNotFound

from theme import stylesheet

# Markdown source -> where its rendered page belongs. The destinations are
# chosen so that the README's own relative links resolve to real pages:
# `labs/lab01/` finds the report's index.html, and `seminar/de_tai_seminar.md`
# is backed by `seminar/index.html` beside it.
MARKDOWN_PAGES = [
    ("README.md", "index.html"),
    ("labs/lab01/report.md", "labs/lab01/index.html"),
    ("seminar/de_tai_seminar.md", "seminar/index.html"),
]

# Never part of the published site, at any depth. `books/` is deliberately
# excluded twice -- here and in .dockerignore -- because it holds copyrighted
# PDFs that are gitignored, and forgetting .dockerignore would otherwise bake
# 22 MB of them into an image layer. `Dockerfile` is a build input, not course
# notes, and the site is public.
EXCLUDED_NAMES = {"books", "docker", "node_modules", "__pycache__", "Dockerfile"}

BRAND = "~/linux-course"
SITE_TITLE = "Linux Operating System &amp; Applications"

# Below this many headings a page gets no table of contents, so short pages
# are not cluttered with navigation they do not need.
TOC_MIN_ENTRIES = 3

# Fence languages that can be mapped to a Pygments lexer. Anything outside
# this set is rendered as plain text rather than guessed at, because a wrong
# guess is worse than no colour.
LEXER_ALIASES = {
    "": "text",
    "sh": "bash",
    "shell": "bash",
    "zsh": "bash",
    "console": "bash",
    "py": "python",
    "js": "javascript",
    "ts": "typescript",
    "html": "html",
    "htm": "html",
    "xml": "html",
    "css": "css",
    "json": "json",
    "yml": "yaml",
    "md": "markdown",
    "sql": "sql",
    "dockerfile": "docker",
    "docker": "docker",
    "text": "text",
    "txt": "text",
    "plain": "text",
    "plaintext": "text",
    "": "text",
}

LABELS = {
    "": "plain",
    "text": "text",
    "bash": "bash",
    "python": "python",
    "docker": "dockerfile",
    "json": "json",
    "yaml": "yaml",
    "sql": "sql",
    "html": "html",
    "css": "css",
    "javascript": "javascript",
    "markdown": "markdown",
    "typescript": "typescript",
}

_HIGHLIGHTER = HtmlFormatter(cssclass="hl")
_H1 = re.compile(r"<h1[^>]*>(.*?)</h1>", re.DOTALL)
_TAG = re.compile(r"<[^>]+>")
_HEADING = re.compile(r'<h([2-3]) id="([^"]+)"[^>]*>(.*?)</h\1>', re.DOTALL)
_WS = re.compile(r"\s+")


@dataclass
class Doc:
    """One page in the site shell."""

    path: str          # URL path relative to the output root
    title: str         # plain-text title
    group: str         # sidebar section heading
    order: int         # position within its group
    url_label: str     # short path shown under the nav entry
    body: str = ""     # rendered HTML
    headings: list[tuple[int, str, str]] = field(default_factory=list)

    @property
    def depth(self) -> int:
        """Directory depth, so links from nested pages can be prefixed."""
        return self.path.count("/")


@dataclass
class Site:
    """The course outline, derived from the repository rather than hardcoded."""

    docs: list[Doc]

    def by_path(self, path: str) -> Doc:
        for doc in self.docs:
            if doc.path == path:
                return doc
        raise KeyError(path)

    def groups(self) -> list[tuple[str, list[Doc]]]:
        """Sidebar groups, in order, each with its documents in order."""
        seen: list[tuple[str, list[Doc]]] = []
        for doc in self.docs:
            for name, items in seen:
                if name == doc.group:
                    items.append(doc)
                    break
            else:
                seen.append((doc.group, [doc]))
        return seen


# --------------------------------------------------------------- outline

def _slide_order(name: str) -> int:
    """Sort slides by their leading session number, not alphabetically."""
    match = re.match(r"(\d+)", name)
    return int(match.group(1)) if match else 999


def build_outline(source: Path) -> Site:
    """Discover the site from what is actually in the repository.

    Slides are found by globbing and ordered by their session number, so a new
    deck appears in the navigation without a code change.
    """
    docs: list[Doc] = [
        Doc("index.html", "Overview", "Course", 0, "README.md"),
        Doc("syllabus.html", "Syllabus", "Course", 1, "syllabus.html"),
        Doc("labs/lab01/index.html", "Lab 01", "Labs", 0, "~/labs/lab01"),
        Doc("seminar/index.html", "Seminar topics", "Seminar", 0, "~/seminar"),
    ]

    slides = sorted(
        (p for p in (source / "slides").glob("*.html")),
        key=lambda p: _slide_order(p.stem),
    )
    titles = {}
    for order, slide in enumerate(slides, start=1):
        titles[slide.name] = (
            f"Session {order:02d}",
            f"Session {order:02d} — {_slide_title(slide)}",
            f"slides/{slide.name}",
        )

    for order, slide in enumerate(slides):
        _, title, url = titles[slide.name]
        docs.append(Doc(url, title, "Slides", order, f"~/slides/{_short(slide.stem)}"))

    return Site(docs)


def _slide_title(path: Path) -> str:
    """Pull the deck name out of its <title>, dropping the session prefix."""
    match = re.search(r"<title>(.*?)</title>", path.read_text(encoding="utf-8"), re.DOTALL)
    if not match:
        return path.stem.replace("_", " ").replace("-", " ").title()
    text = _WS.sub(" ", match.group(1)).strip()
    text = re.sub(r"^Session\s+\d+\s*[—–-]\s*", "", text)
    text = re.sub(r"\s*[—–-]\s*Module\s+\d+(\s*·\s*Session\s*\d+)?$", "", text)
    return text.strip() or path.stem


def _short(stem: str) -> str:
    """Trim a slide filename down to its readable core."""
    stem = re.sub(r"^\d+[_-]?", "", stem)
    return stem.replace("_", "-")


# --------------------------------------------------------- link helpers

def rel_prefix(doc: Doc) -> str:
    """Relative path from a page back to the output root.

    A page at `labs/lab01/index.html` needs `../../` to reach `slides/`, and
    getting this wrong breaks every navigation link on nested pages.
    """
    return "../" * doc.depth


def url_for(doc: Doc, target: Doc) -> str:
    """A URL from `doc` to `target`, both relative to the output root."""
    return rel_prefix(doc) + target.path


def _text_of(fragment: str) -> str:
    """Strip tags and unescape entities, for titles and search text.

    Escaped angle brackets are dropped too: markdown-it turns a literal `&` in
    prose into `&amp;`, and code containing `<` into `&lt;`, so a naive strip
    would leave those in the search text and make it look like markup.
    """
    text = _TAG.sub("", fragment)
    text = html.unescape(text)
    return text.replace("<", " ").replace(">", " ").strip()


# -------------------------------------------------------- markdown step

def make_renderer() -> MarkdownIt:
    """CommonMark + GFM tables, with heading ids for the hand-written TOC.

    `max_level=6` matters: the anchors plugin defaults to 2, which would leave
    the README's `###` table-of-contents links dangling. Raw HTML is allowed
    because the notes are the repository's own content.
    """
    return (
        MarkdownIt("commonmark", {"html": True, "linkify": False})
        .enable("table")
        .use(anchors_plugin, max_level=6)
    )


def _lexer_for(language: str):
    """Resolve a fence language to a Pygments lexer, or None."""
    name = LEXER_ALIASES.get((language or "").strip().lower())
    if not name:
        return None
    try:
        return get_lexer_by_name(name)
    except ClassNotFound:
        return None


def highlight_code(code: str, language: str) -> str:
    """Highlight a fenced block at build time, so the browser does nothing."""
    lexer = _lexer_for(language)
    if lexer is None:
        return html.escape(code)
    return highlight(code, lexer, _HIGHLIGHTER)


def render_markdown(source: str) -> tuple[str, list[tuple[int, str, str]], list[str]]:
    """Render Markdown, collecting the headings and fence languages."""
    renderer = make_renderer()
    tokens = renderer.parse(source)

    # The info strings are read from the same token stream the renderer uses,
    # so they stay aligned with the emitted <pre> blocks.
    fence_langs = [
        (token.info.strip().split() or [""])[0]
        for token in tokens
        if token.type == "fence"
    ]

    body = renderer.renderer.render(tokens, renderer.options, {})
    return body, _collect_headings(body), fence_langs


def _collect_headings(body: str) -> list[tuple[int, str, str]]:
    """(level, id, text) for every H2/H3, which is what the TOC shows.

    H3 is included deliberately: the seminar page has no H2 at all, so an
    H2-only table of contents would leave that page with nothing.
    """
    return [
        (int(level), anchor, _text_of(inner))
        for level, anchor, inner in _HEADING.findall(body)
    ]


def _code_block(lang: str, highlighted: str) -> str:
    """Wrap highlighted code in a titled block with a copy button."""
    label = LABELS.get(lang, lang or "plain")
    return (
        '<div class="code-block">'
        f'<div class="code-head"><span class="code-lang">{html.escape(label)}</span>'
        '<button class="copy-btn" type="button" data-copy aria-label="Copy code">Copy</button>'
        "</div>"
        f"<pre><code class=\"hl language-{html.escape(label)}\">{highlighted}</code></pre>"
        "</div>"
    )


def _wrap_tables(body: str) -> str:
    """Give tables a scroll container so wide ones do not break the layout."""
    def repl(match: re.Match) -> str:
        return f'<div class="table-wrap">{match.group(0)}</div>'

    return re.sub(r"<table>.*?</table>", repl, body, flags=re.DOTALL)


def _style_fences(body: str, fence_langs: list[str]) -> str:
    """Replace bare <pre><code> fences with highlighted, copyable blocks.

    markdown-it has already escaped the fence contents, so the text is unescaped
    before highlighting and re-escaped by the Pygments formatter. The two lists
    -- fences in the body, info strings in the source -- are in the same order,
    which is what lines the language label up with the right block.
    """
    parts: list[str] = []
    cursor = 0
    position = 0
    for match in re.finditer(r"<pre><code[^>]*>(.*?)</code></pre>", body, re.DOTALL):
        parts.append(body[cursor:match.start()])
        raw = html.unescape(match.group(1))
        language = fence_langs[position] if position < len(fence_langs) else ""
        parts.append(_code_block(language.strip().lower(), highlight_code(raw, language)))
        cursor = match.end()
        position += 1
    parts.append(body[cursor:])
    return "".join(parts)


def _figure_figures(body: str) -> str:
    """Give each image a caption derived from its alt text."""

    def repl(match: re.Match) -> str:
        tag = match.group(0)
        alt = re.search(r'alt="([^"]*)"', tag)
        text = alt.group(1).strip() if alt else ""
        if not text:
            return tag
        return tag + f'<p class="figure-caption">{html.escape(text)}</p>'

    return re.sub(r"<img [^>]*>", repl, body)


def _retarget_markdown_links(body: str, page_dir: str) -> str:
    """Point `.md` links at the rendered page instead of the missing source.

    The notes link to their own neighbours by their source paths, e.g.
    `seminar/de_tai_seminar.md`. Those sources are deliberately not published,
    so the link has to become `seminar/` -- the page that replaced it.
    """
    def repl(match: re.Match) -> str:
        href = match.group(1)
        if not href.endswith(".md"):
            return match.group(0)
        target = os.path.normpath(os.path.join(page_dir, href))
        directory = os.path.dirname(target)
        new_href = f"{directory}/" if directory else ""
        return f'href="{html.escape(new_href, quote=True)}"'

    return re.sub(r'href="([^"]+\.md(?:#[^"]*)?)"', repl, body)


def _pdf_cards(body: str) -> str:
    """Make links to a PDF look like a document, not a bare filename.

    Matches both a paragraph-wrapped link and one inside a table cell, because
    the lab's file inventory is a table and a table-only match would leave the
    most obvious PDF link in the notes unstyled.
    """

    def repl(match: re.Match) -> str:
        href, label = match.group(1), match.group(2)
        return (
            '<a class="pdf-card" href="{href}">'
            '<span class="pdf-badge">PDF</span>'
            '<span class="pdf-text"><span class="pdf-title">{label}</span>'
            '<span class="pdf-meta">Open the generated document</span></span>'
            '<span class="pdf-arrow" aria-hidden="true">&rarr;</span>'
            "</a>"
        ).format(href=href, label=html.escape(label))

    # Inside a table cell the surrounding <p> does not exist.
    return re.sub(
        r'<a href="([^"]+\.pdf(?:#[^"]*)?)">([^<]+)</a>', repl, body
    )


def _heading_anchors(body: str) -> str:
    """Add a hover-revealed link icon to each H2-H4."""

    def repl(match: re.Match) -> str:
        open_tag, inner, close_tag = match.group(1), match.group(2), match.group(3)
        if "<a" in open_tag:
            return match.group(0)
        anchor = re.search(r'id="([^"]+)"', open_tag)
        if not anchor:
            return match.group(0)
        link = f'<a href="#{anchor.group(1)}" aria-label="Link to this section">#</a>'
        return f"{open_tag}{inner}{link}{close_tag}"

    return re.sub(
        r"(<h[2-4][^>]*>)(.*?)(</h[2-4]>)",
        repl,
        body,
        flags=re.DOTALL,
    )


# ------------------------------------------------------------ shell HTML

ICONS = {
    "sun": '<circle cx="12" cy="12" r="4"/><path d="M12 2v2m0 16v2M2 12h2m16 0h2'
           'M4.9 4.9l1.4 1.4m11.4 11.4 1.4 1.4M19.1 4.9l-1.4 1.4M6.3 17.7l-1.4 1.4"/>',
    "moon": '<path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/>',
    "search": '<circle cx="11" cy="11" r="7"/><path d="M20 20l-3.5-3.5"/>',
    "menu": '<path d="M3 6h18M3 12h18M3 18h18"/>',
    "close": '<path d="M6 6l12 12M18 6L6 18"/>',
}


def _icon(name: str, extra: str = "") -> str:
    return (
        f'<svg viewBox="0 0 24 24" aria-hidden="true"{extra}>'
        f"{ICONS[name]}</svg>"
    )


def theme_bootstrap() -> str:
    """Inline script that sets the theme before the stylesheet paints.

    Without this a dark-mode reader gets a white flash on every navigation.
    """
    return (
        "<script>"
        "(function(){var t;try{t=localStorage.getItem('course-notes-theme')}catch(e){}"
        "if(t!=='light'&&t!=='dark'){t=matchMedia('(prefers-color-scheme: dark)').matches"
        "?'dark':'light'}"
        "document.documentElement.setAttribute('data-theme',t)})();"
        "</script>"
    )


def header(prefix: str = "") -> str:
    """The compact top bar: brand, spacer, search, theme, nav toggle.

    `prefix` is the including page's path back to the output root, so a deck
    in `slides/` links to `../index.html` rather than a `slides/index.html`
    that does not exist.
    """
    return (
        '<header class="site-header">'
        f'<a class="brand" href="{prefix}index.html">{BRAND}</a>'
        '<span class="header-spacer"></span>'
        '<button class="icon-btn" id="search-toggle" type="button" '
        'aria-label="Search course notes">' + _icon("search") + "</button>"
        '<button class="icon-btn" id="theme-toggle" type="button" '
        'aria-label="Switch theme">' + _icon("moon") + "</button>"
        '<button class="icon-btn" id="nav-toggle" type="button" '
        'aria-label="Open navigation" aria-expanded="false" '
        'aria-controls="course-nav">' + _icon("menu") + "</button>"
        "</header>"
    )


def sidebar(site: Site, current: Doc) -> str:
    """The course navigation, marked up with filesystem hints."""
    parts = ['<nav class="sidebar" id="course-nav" aria-label="Course">']
    for name, docs in site.groups():
        parts.append('<div class="nav-group">')
        parts.append(f'<h2 class="nav-group-title">{html.escape(name)}</h2>')
        parts.append('<ul class="nav-list">')
        for doc in docs:
            is_current = doc.path == current.path
            classes = ' class="is-current"' if is_current else ""
            current_attr = ' aria-current="page"' if is_current else ""
            parts.append(
                f'<li><a href="{url_for(current, doc)}"{classes}{current_attr}>'
                f'<span class="nav-label">{html.escape(doc.title)}</span>'
                f'<span class="nav-path">{html.escape(doc.url_label)}</span></a></li>'
            )
        parts.append("</ul></div>")
    parts.append("</nav>")
    return "".join(parts)


def toc_block(headings: list[tuple[int, str, str]], ident: str, mobile: bool) -> str:
    """An on-this-page list, or nothing when the page is too short."""
    if len(headings) < TOC_MIN_ENTRIES:
        return ""
    items = "".join(
        f'<li><a class="toc-link toc-h{level}" href="#{anchor}">{html.escape(text)}</a></li>'
        for level, anchor, text in headings
    )
    if mobile:
        return (
            '<details class="toc-mobile"><summary>On this page</summary>'
            f'<ul class="toc-list">{items}</ul></details>'
        )
    return (
        f'<nav class="toc" id="{ident}" aria-label="On this page">'
        '<p class="toc-title">On this page</p>'
        f'<ul class="toc-list">{items}</ul></nav>'
    )


def pager(site: Site, current: Doc) -> str:
    """Previous/next links, only where a real order exists.

    Slides are sequential; there is one lab and one seminar list, so inventing
    a sequence there would be a lie.
    """
    group = [doc for _, docs in site.groups() for doc in docs if doc.group == current.group]
    try:
        position = [doc.path for doc in group].index(current.path)
    except ValueError:
        return ""
    previous = group[position - 1] if position > 0 else None
    following = group[position + 1] if position + 1 < len(group) else None
    if previous is None and following is None:
        return ""

    def link(doc: Doc | None, kind: str) -> str:
        if doc is None:
            return '<div class="pager-empty"></div>'
        label = "Previous" if kind == "prev" else "Next"
        return (
            f'<a class="pager-link pager-{kind}" href="{url_for(current, doc)}">'
            f'<span class="pager-label">{label}</span>'
            f'<span class="pager-title">{html.escape(doc.title)}</span></a>'
        )

    return f'<nav class="pager" aria-label="Document navigation">{link(previous, "prev")}{link(following, "next")}</nav>'


def breadcrumb(site: Site, current: Doc) -> str:
    """A shell-like trail so the reader knows where they are."""
    prefix = rel_prefix(current)
    return (
        '<p class="breadcrumb">'
        f'<a href="{prefix}index.html">{BRAND}</a> / '
        f'<a href="{prefix}syllabus.html">Course</a> / '
        f"<span>{html.escape(current.title)}</span>"
        "</p>"
    )


def document(
    site: Site,
    doc: Doc,
    body: str,
    search_index: str,
) -> str:
    """Assemble one complete HTML page."""
    prefix = rel_prefix(doc)
    title = html.escape(doc.title)
    return (
        "<!DOCTYPE html>\n"
        '<html lang="en">\n'
        "<head>\n"
        '<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f'<meta name="description" content="Course notes for {title}.">\n'
        f"<title>{title} — {SITE_TITLE}</title>\n"
        + theme_bootstrap()
        + f'<link rel="stylesheet" href="{prefix}assets/app.css">\n'
        + f'<script type="application/json" id="search-index">{search_index}</script>\n'
        f'<script src="{prefix}assets/app.js" defer></script>\n'
        "</head>\n"
        f'<body data-depth="{doc.depth}">\n'
        '<a class="skip-link" href="#main">Skip to content</a>\n'
        + header(prefix)
        + '<div class="nav-scrim"></div>\n'
        + '<div class="layout">\n'
        + sidebar(site, doc)
        + '<div class="content">\n'
        + breadcrumb(site, doc)
        + toc_block(doc.headings, "toc", mobile=True)
        + f'<main id="main" tabindex="-1">\n{body}\n</main>\n'
        + pager(site, doc)
        + "</div>\n"
        + toc_block(doc.headings, "toc", mobile=False)
        + "</div>\n"
        + search_dialog()
        + "</body>\n</html>\n"
    )


def search_dialog() -> str:
    return (
        '<dialog class="search-dialog" id="search-dialog" aria-label="Search course notes">'
        '<div class="search-head">'
        '<svg viewBox="0 0 24 24" aria-hidden="true">'
        '<circle cx="11" cy="11" r="7"/><path d="M20 20l-3.5-3.5"/></svg>'
        '<input class="search-input" id="search-input" type="search" '
        'placeholder="Search course notes…" role="combobox" '
        'aria-expanded="true" aria-controls="search-results" '
        'aria-autocomplete="list" autocomplete="off">'
        '<kbd class="search-hint" id="search-hint">esc</kbd>'
        "</div>"
        '<ul class="search-results" id="search-results" role="listbox" '
        'aria-label="Search results"></ul>'
        "</dialog>"
    )


# ----------------------------------------------------------- search index

def build_search_index(docs: list[Doc]) -> str:
    """A small JSON index of every rendered page's text.

    The URLs are stored root-relative to the output directory, and app.js
    prefixes them with the including page's own depth. Storing them relative to
    the homepage would break search on every nested page, and a separate JSON
    file would stop it working at all over file:// where fetch is blocked.
    """
    entries = [
        {
            "title": doc.title,
            "url": doc.path,
            "headings": " ".join(text for _, _, text in doc.headings),
            "text": _WS.sub(" ", _text_of(doc.body)),
        }
        for doc in docs
    ]
    return json.dumps(entries, ensure_ascii=False)


# -------------------------------------------------------- slide injection

def inject_shell_into_slide(path: Path, doc: Doc, site: Site) -> None:
    """Give a standalone deck a header and pager without touching its CSS.

    The decks are already self-contained and work offline, so their own styling
    is left entirely alone. The header sits in normal flow rather than fixed,
    because each deck centres its own content in the viewport and a fixed bar
    would overlap the first slide. The pager goes just before `</body>` so it
    appears below the deck, not above it.

    Every link is written from the *output root* and then prefixed with
    `rel_prefix`, because a deck lives in `slides/` and a bare `index.html`
    there would resolve to `slides/index.html`, which does not exist.
    """
    original = path.read_text(encoding="utf-8")
    if "site-header" in original:
        return

    prefix = rel_prefix(doc)
    top = (
        '<div class="slide-shell-top">'
        + header(prefix=prefix)
        + '<div class="nav-scrim"></div>'
        + f'<p class="breadcrumb"><a href="{prefix}index.html">{BRAND}</a> / '
        f'<a href="{prefix}index.html#slides">Slides</a> / '
        f"<span>{html.escape(doc.title)}</span></p>"
        + "</div>"
    )
    bottom = f'<div class="slide-shell-bottom">{pager(site, doc)}</div>'

    result = original
    if "<body>" in result:
        result = result.replace("<body>", "<body>" + top, 1)
    else:
        result = top + result

    if "</body>" in result:
        result = result.replace("</body>", bottom + "</body>", 1)
    else:
        result += bottom

    head_extra = (
        f'<link rel="stylesheet" href="{prefix}assets/app.css">\n'
        f'<script src="{prefix}assets/app.js" defer></script>\n'
    )
    if "</head>" in result:
        result = result.replace("</head>", head_extra + "</head>", 1)

    path.write_text(result, encoding="utf-8")


# ----------------------------------------------------------------- build

def copy_static(source: Path, out: Path, rendered: set[str]) -> None:
    """Copy everything that is not a rendered Markdown source."""
    out_resolved = out.resolve()

    def ignore(directory: str, names: list[str]) -> set[str]:
        skip = set()
        for name in names:
            full = Path(directory) / name
            # A leading dot marks tooling and metadata, never course notes:
            # .git, .venv, .gitignore, .dockerignore, .env, .vscode, .DS_Store.
            # Matching the pattern rather than enumerating names means the next
            # hidden entry someone creates is already covered.
            if name.startswith("."):
                skip.add(name)
                continue
            if name in EXCLUDED_NAMES:
                skip.add(name)
                continue
            if full.resolve() == out_resolved:
                skip.add(name)
                continue
            if full.is_file() and full.relative_to(source).as_posix() in rendered:
                skip.add(name)
        return skip

    shutil.copytree(source, out, ignore=ignore, dirs_exist_ok=True)


def render_page(
    source: Path, source_name: str, dest_name: str
) -> tuple[str, str, list[tuple[int, str, str]]]:
    """Render one Markdown source, returning its body, title and headings."""
    markdown_path = source / source_name
    if not markdown_path.is_file():
        raise SystemExit(f"build_site: missing Markdown source: {markdown_path}")

    text = markdown_path.read_text(encoding="utf-8")
    body, headings, fence_langs = render_markdown(text)
    body = _wrap_tables(body)
    body = _style_fences(body, fence_langs)
    body = _figure_figures(body)
    body = _pdf_cards(body)
    body = _retarget_markdown_links(body, os.path.dirname(dest_name))
    body = _heading_anchors(body)

    title_match = _H1.search(body)
    title = _text_of(title_match.group(1)) if title_match else Path(source_name).stem
    return body, title, headings


def _fence_languages(renderer: MarkdownIt, source: str) -> list[str]:
    """Every fenced block's info string, in document order.

    Read from the parsed token stream rather than by regex over the raw text,
    so the list lines up exactly with the `<pre>` elements the renderer emits.
    A regex would miscount whenever a fence appears inside a list item or the
    text contains a literal ``` sequence.
    """
    return [
        (token.info.strip().split() or [""])[0]
        for token in renderer.parse(source)
        if token.type == "fence"
    ]


def build(source: Path, out: Path) -> None:
    """Build the site at `out` from the repository at `source`."""
    source = Path(source)
    out = Path(out)
    if not source.is_dir():
        raise SystemExit(f"build_site: source directory not found: {source}")

    rendered = {source_name for source_name, _ in MARKDOWN_PAGES}

    # Start from a clean slate so a renamed or deleted note cannot survive as a
    # stale page from a previous build.
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)

    copy_static(source, out, rendered)

    # Assets are shared by every page, so they are written once.
    assets = out / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    (assets / "app.css").write_text(stylesheet(), encoding="utf-8")
    (assets / "app.js").write_text(
        (Path(__file__).resolve().parent / "app.js").read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    site = build_outline(source)
    generated: list[Doc] = []

    for source_name, dest_name in MARKDOWN_PAGES:
        body, title, headings = render_page(source, source_name, dest_name)
        doc = site.by_path(dest_name)
        doc.body = body
        doc.headings = headings
        if source_name == "README.md":
            doc.title = title
        generated.append(doc)

    # The search index needs every page's text, so it is built after the
    # bodies exist and then written into each page.
    index = build_search_index(generated)

    for source_name, dest_name in MARKDOWN_PAGES:
        doc = site.by_path(dest_name)
        (out / dest_name).write_text(
            document(site, doc, doc.body, index), encoding="utf-8"
        )

    # The standalone decks get the shell around them, not a restyle.
    for doc in site.docs:
        if doc.group == "Slides":
            slide_path = out / doc.path
            if slide_path.is_file():
                inject_shell_into_slide(slide_path, doc, site)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("source", nargs="?", default="/build/src", type=Path)
    parser.add_argument("out", nargs="?", default="/build/out", type=Path)
    args = parser.parse_args(argv)

    build(args.source, args.out)
    print(f"build_site: wrote site to {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
