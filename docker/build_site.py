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
  2. renders the Markdown notes to HTML, so the README's hand-written table of
     contents is the landing page rather than a raw file download;
  3. drops the rendered .md sources, so a page is served as one file, not two.
"""

from __future__ import annotations

import argparse
import re
import shutil
import sys
from pathlib import Path

from markdown_it import MarkdownIt
from mdit_py_plugins.anchors import anchors_plugin

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

CSS = """
:root { color-scheme: light dark; }
* { box-sizing: border-box; }
body {
  margin: 0 auto; padding: 2.5rem 1.25rem 6rem; max-width: 52rem;
  font: 16px/1.7 system-ui, -apple-system, "Segoe UI", sans-serif;
  color: #1c1c1e; background: #fdfdfc;
}
h1, h2, h3, h4 { line-height: 1.25; margin: 2.2rem 0 0.7rem; }
h1 { font-size: 1.9rem; margin-top: 0; }
h2 { font-size: 1.45rem; padding-bottom: 0.3rem; border-bottom: 1px solid #e2e0da; }
h3 { font-size: 1.15rem; }
a { color: #0b5fa5; }
a:hover { color: #08406f; }
code, pre, kbd { font-family: ui-monospace, "SFMono-Regular", Menlo, monospace; }
code { background: #f0efeb; padding: 0.12em 0.34em; border-radius: 4px; font-size: 0.9em; }
pre { background: #f6f5f1; border: 1px solid #e2e0da; border-radius: 8px;
      padding: 0.9rem 1.1rem; overflow-x: auto; }
pre code { background: none; padding: 0; font-size: 0.88rem; line-height: 1.55; }
table { border-collapse: collapse; width: 100%; margin: 1.2rem 0; display: block;
        overflow-x: auto; }
th, td { border: 1px solid #dddad2; padding: 0.5rem 0.7rem; text-align: left; }
th { background: #f3f2ed; font-weight: 600; }
tr:nth-child(even) td { background: #faf9f6; }
img { max-width: 100%; height: auto; border: 1px solid #e2e0da; border-radius: 6px; }
blockquote { margin: 1.2rem 0; padding: 0.3rem 1.1rem; border-left: 4px solid #d8d5cc;
             color: #55534d; }
hr { border: 0; border-top: 1px solid #e2e0da; margin: 2.5rem 0; }
ul, ol { padding-left: 1.5rem; }
@media (prefers-color-scheme: dark) {
  body { color: #e8e6e1; background: #17181a; }
  h2 { border-bottom-color: #33353a; }
  a { color: #6cb2f0; }
  a:hover { color: #9acdf7; }
  code { background: #26282c; }
  pre { background: #1d1f22; border-color: #33353a; }
  th { background: #222428; }
  th, td { border-color: #33353a; }
  tr:nth-child(even) td { background: #1b1d1f; }
  img, blockquote { border-color: #33353a; }
  blockquote { color: #a5a29b; }
  hr { border-top-color: #33353a; }
}
"""

_FIRST_H1 = re.compile(r"<h1[^>]*>(.*?)</h1>", re.DOTALL)


def make_renderer() -> MarkdownIt:
    """CommonMark + GFM tables, with heading ids for the hand-written TOC.

    `max_level=6` matters: the anchors plugin defaults to 2, which would leave
    the README's `###` table-of-contents links dangling. Raw HTML is allowed
    because the notes are the repository's own content.
    """
    return (
        MarkdownIt("commonmark", {"html": True})
        .enable("table")
        .use(anchors_plugin, max_level=6)
    )


def page(body: str, title: str) -> str:
    """Wrap rendered markdown in a minimal, self-contained HTML document."""
    return (
        "<!DOCTYPE html>\n"
        '<html lang="en">\n'
        "<head>\n"
        '<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"<title>{title}</title>\n"
        f"<style>{CSS}</style>\n"
        "</head>\n"
        "<body>\n"
        f"{body}\n"
        "</body>\n"
        "</html>\n"
    )


def title_from(body: str, fallback: str) -> str:
    """Use the document's own H1 as the page title, entities and all."""
    match = _FIRST_H1.search(body)
    return match.group(1).strip() if match else fallback


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

    renderer = make_renderer()
    for source_name, dest_name in MARKDOWN_PAGES:
        markdown_path = source / source_name
        if not markdown_path.is_file():
            raise SystemExit(f"build_site: missing Markdown source: {markdown_path}")
        body = renderer.render(markdown_path.read_text(encoding="utf-8"))
        destination = out / dest_name
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            page(body, title_from(body, markdown_path.stem)), encoding="utf-8"
        )


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
