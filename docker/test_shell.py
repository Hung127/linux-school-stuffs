"""Tests for the documentation shell: navigation, TOC, search, code blocks.

Split from test_build_site.py because these assert on the site shell rather
than on the build pipeline. Run everything with:

    python -m unittest discover -s docker -t docker -v
"""

import json
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import build_site  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent


class ShellTestCase(unittest.TestCase):
    """Builds the real repository once for the whole class."""

    @classmethod
    def setUpClass(cls) -> None:
        import shutil
        import tempfile

        cls.tmp = Path(tempfile.mkdtemp(prefix="shell-test-"))
        cls.out = cls.tmp / "out"
        build_site.build(REPO_ROOT, cls.out)
        cls.index = (cls.out / "index.html").read_text(encoding="utf-8")
        cls.lab = (cls.out / "labs" / "lab01" / "index.html").read_text(encoding="utf-8")
        cls.seminar = (cls.out / "seminar" / "index.html").read_text(encoding="utf-8")

    @classmethod
    def tearDownClass(cls) -> None:
        import shutil

        shutil.rmtree(cls.tmp, ignore_errors=True)


class TestDocumentShell(ShellTestCase):
    def test_pages_use_semantic_landmark_elements(self):
        for name, html in (("index", self.index), ("lab", self.lab), ("seminar", self.seminar)):
            with self.subTest(page=name):
                self.assertIn("<header", html)
                self.assertIn("<nav", html)
                self.assertIn("<main", html)

    def test_header_shows_the_course_path_as_branding(self):
        self.assertIn("~/linux-course", self.index)

    def test_stylesheet_is_a_separate_file_not_inlined(self):
        self.assertTrue((self.out / "assets" / "app.css").is_file())
        self.assertNotIn("<style>", self.index)

    def test_stylesheet_is_linked_from_every_page(self):
        for name, html in (("index", self.index), ("lab", self.lab), ("seminar", self.seminar)):
            with self.subTest(page=name):
                self.assertIn("app.css", html)

    def test_pages_carry_the_theme_toggle_and_search_controls(self):
        self.assertIn("id=\"theme-toggle\"", self.index)
        self.assertIn("id=\"search-toggle\"", self.index)
        self.assertIn("id=\"nav-toggle\"", self.index)

    def test_theme_toggle_has_an_accessible_name(self):
        button = re.search(r"<button[^>]*id=\"theme-toggle\"[^>]*>", self.index)
        self.assertIsNotNone(button)
        self.assertIn("aria-label=", button.group(0))

    def test_mobile_nav_toggle_has_an_accessible_name(self):
        button = re.search(r"<button[^>]*id=\"nav-toggle\"[^>]*>", self.index)
        self.assertIsNotNone(button)
        self.assertIn("aria-label=", button.group(0))

    def test_script_is_a_separate_deferred_file(self):
        self.assertTrue((self.out / "assets" / "app.js").is_file())
        self.assertIn("app.js", self.index)
        self.assertIn("defer", self.index)

    def test_theme_is_set_before_first_paint_to_avoid_a_flash(self):
        # The inline bootstrap must run before the stylesheet renders, or a
        # dark-mode user gets a white flash on every page load.
        css_at = self.index.index("app.css")
        bootstrap_at = self.index.index("data-theme")
        self.assertLess(bootstrap_at, css_at)


class TestNavigation(ShellTestCase):
    def test_sidebar_lists_every_section_of_the_course(self):
        for group in ("Course", "Labs", "Slides", "Seminar"):
            with self.subTest(group=group):
                self.assertIn(f">{group}<", self.index)

    def test_sidebar_links_to_all_four_slide_decks(self):
        for deck in ("1_linux_architecture.html", "2_cli-text-processing.html",
                     "3_users-permissions.html", "4-software-storage-tasks.html"):
            with self.subTest(deck=deck):
                self.assertIn(deck, self.index)

    def test_nested_page_links_up_to_the_site_root(self):
        # labs/lab01/index.html needs ../../ to reach slides/ and the root.
        self.assertIn('href="../../slides/', self.lab)
        self.assertNotIn('href="slides/', self.lab)

    def page_dir(self, name: str) -> Path:
        if name == "index":
            return self.out
        return self.out / ("labs/lab01" if name == "lab" else "seminar")

    def test_every_navigation_link_resolves_to_a_real_file(self):
        for name, html in (("index", self.index), ("lab", self.lab), ("seminar", self.seminar)):
            for href in re.findall(r'<a[^>]+href="([^"#][^"]*)"', html):
                if href.startswith(("http://", "https://", "mailto:")):
                    continue
                target = (self.page_dir(name) / href.split("#")[0]).resolve()
                with self.subTest(page=name, href=href):
                    self.assertTrue(
                        target.exists(),
                        f"{name}: link {href!r} points at a missing file",
                    )

    def test_current_page_is_marked_for_assistive_tech(self):
        self.assertIn('aria-current="page"', self.lab)

    def test_current_page_is_marked_visually_not_by_colour_alone(self):
        # aria-current is on the element that also carries .is-current, so the
        # two never drift apart and the accent bar is not colour-only.
        self.assertRegex(self.lab, r'class="is-current"[^>]*aria-current="page"')

    def test_previous_and_next_navigation_exists_on_slides(self):
        deck = (self.out / "slides" / "2_cli-text-processing.html").read_text(encoding="utf-8")
        self.assertIn("1_linux_architecture.html", deck)
        self.assertIn("3_users-permissions.html", deck)

    def test_slide_shell_does_not_obscure_the_deck(self):
        # Each deck centres its own content in the viewport, so the shell stays
        # in normal flow and the pager sits below the deck, not above it.
        deck = (self.out / "slides" / "1_linux_architecture.html").read_text(encoding="utf-8")
        self.assertLess(deck.index("slide-shell-top"), deck.index("pager"))
        self.assertLess(deck.index("pager"), deck.rindex("</body>"))
        self.assertIn("slide-shell-top", deck)
        self.assertIn("slide-shell-bottom", deck)

    def test_slide_links_resolve_from_inside_the_slides_directory(self):
        # A deck sits in slides/, so a bare `index.html` there would resolve to
        # slides/index.html, which does not exist. Every link must go up first.
        for deck in sorted((self.out / "slides").glob("*.html")):
            html = deck.read_text(encoding="utf-8")
            for href in re.findall(r'<a[^>]+href="([^"#][^"]*)"', html):
                if href.startswith(("http://", "https://")):
                    continue
                target = (deck.parent / href.split("#")[0]).resolve()
                with self.subTest(deck=deck.name, href=href):
                    self.assertTrue(
                        target.exists(),
                        f"{deck.name}: {href!r} resolves to a missing file",
                    )

    def test_slide_keeps_its_own_stylesheet_and_content(self):
        original = (REPO_ROOT / "slides" / "1_linux_architecture.html").read_text(encoding="utf-8")
        built = (self.out / "slides" / "1_linux_architecture.html").read_text(encoding="utf-8")
        self.assertIn("<style", built, "the deck's own stylesheet must survive")
        # Only the shell is added; the deck's own body markup is untouched.
        for probe in ("<body>", "</body>", "session", "Linux"):
            with self.subTest(probe=probe):
                self.assertIn(probe, built)
        self.assertGreater(len(built), len(original))

    def test_slide_sequence_follows_filename_order(self):
        first = (self.out / "slides" / "1_linux_architecture.html").read_text(encoding="utf-8")
        last = (self.out / "slides" / "4-software-storage-tasks.html").read_text(encoding="utf-8")
        # The first deck has no previous, the last has no next.
        self.assertNotIn("pager-prev", first)
        self.assertNotIn("pager-next", last)

    def test_no_previous_next_invented_where_no_order_exists(self):
        # One lab and one seminar topic list: claiming a sequence is fiction.
        self.assertNotIn("pager-prev", self.lab)
        self.assertNotIn("pager-next", self.seminar)


class TestTableOfContents(ShellTestCase):
    def test_long_pages_get_an_on_this_page_toc(self):
        self.assertIn("On this page", self.lab)
        self.assertIn("On this page", self.index)

    def test_toc_links_use_real_generated_heading_ids(self):
        heading_ids = set(re.findall(r'<h[1-6] id="([^"]+)"', self.lab))
        toc_links = set(re.findall(r'class="toc-link[^"]*"[^>]*href="#([^"]+)"', self.lab))
        self.assertTrue(toc_links, "the lab page should have a populated TOC")
        for anchor in toc_links:
            with self.subTest(anchor=anchor):
                self.assertIn(anchor, heading_ids)

    def test_toc_includes_third_level_headings(self):
        # The seminar page has no H2 at all; an H2-only TOC would leave it bare.
        anchors = re.findall(r'class="toc-link[^"]*"[^>]*href="#([^"]+)"', self.seminar)
        self.assertTrue(anchors, "the seminar page has 13 H3s and needs a TOC")
        h3s = set(re.findall(r'<h3 id="([^"]+)"', self.seminar))
        self.assertTrue(set(anchors) & h3s)

    def test_toc_entries_are_marked_by_level_for_indentation(self):
        self.assertRegex(self.lab, r'class="toc-link toc-h3"')

    def test_short_pages_do_not_get_a_cluttered_toc(self):
        # Below the threshold, the TOC is omitted entirely.
        self.assertNotIn("On this page", (self.out / "syllabus.html").read_text(encoding="utf-8"))


class TestPdfPresentation(ShellTestCase):
    def test_bare_pdf_link_becomes_a_card(self):
        body = '<p><a href="report.pdf">Lab 01 Report</a></p>'
        html = build_site._pdf_cards(body)
        self.assertIn('class="pdf-card"', html)
        self.assertIn("PDF", html)
        self.assertIn("report.pdf", html)

    def test_pdf_link_inside_a_table_cell_becomes_a_card(self):
        # The lab's file inventory is a table, so a paragraph-only match would
        # leave the most obvious PDF link in the notes unstyled.
        body = "<table><tr><td><code>x</code></td><td><a href=\"report.pdf\">PDF</a></td></tr></table>"
        html = build_site._pdf_cards(body)
        self.assertIn('class="pdf-card"', html)

    def test_non_pdf_links_are_untouched(self):
        body = '<p><a href="screenshots/lab1_1.png">shot</a></p>'
        self.assertEqual(build_site._pdf_cards(body), body)


class TestCodeBlocks(ShellTestCase):
    def test_code_blocks_carry_a_language_label(self):
        self.assertIn("code-lang", self.index)
        self.assertIn("bash", self.index)

    def test_code_blocks_have_a_copy_button(self):
        self.assertIn("data-copy", self.index)

    def test_syntax_highlighting_is_applied_at_build_time(self):
        # Pygments wraps tokens in <span class="nt"> (name) / .k (keyword) etc.
        # Highlighting happens during the build, so the browser downloads no
        # highlighter and does no highlighting work.
        self.assertRegex(self.index, r'<span class="[a-z]{1,2}">')

    def test_plain_fences_render_without_a_language_label(self):
        # A fence with no info string is labelled "text", never "plain".
        for html in (self.index, self.lab, self.seminar):
            with self.subTest(page=html[:40]):
                self.assertNotIn(">plain<", html)

    def test_code_escaping_survives_highlighting(self):
        self.assertIn("&lt;", self.lab)  # awk '<', not a raw tag


class TestSearch(ShellTestCase):
    def index_data(self, html: str) -> list[dict]:
        raw = re.search(
            r'<script type="application/json" id="search-index">(.*?)</script>', html, re.DOTALL
        )
        self.assertIsNotNone(raw, "pages should inline the search index")
        return json.loads(raw.group(1))

    def test_search_index_is_embedded_and_parses(self):
        entries = self.index_data(self.index)
        self.assertTrue(entries)

    def test_index_covers_every_markdown_page(self):
        for html in (self.index, self.lab, self.seminar):
            with self.subTest(page=html[:40]):
                self.assertEqual(len(self.index_data(html)), 3)

    def test_index_entries_carry_title_url_and_text(self):
        entry = self.index_data(self.index)[0]
        for key in ("title", "url", "text"):
            self.assertIn(key, entry)

    def test_index_urls_are_root_relative_and_page_depth_is_recorded(self):
        # Index entries store output-root-relative URLs; app.js prefixes them
        # with the including page's depth, read from <body data-depth>.
        for entry in self.index_data(self.lab):
            self.assertFalse(entry["url"].startswith(("../", "/")), entry["url"])
        self.assertRegex(self.lab, r'<body data-depth="2">')
        self.assertRegex(self.index, r'<body data-depth="0">')

    def test_search_navigation_uses_the_recorded_depth(self):
        js = (self.out / "assets" / "app.js").read_text(encoding="utf-8")
        self.assertIn('data-depth', js)
        self.assertIn("prefix + entry.url", js)

    def test_index_text_is_plain_text_without_markup(self):
        # The index is built from the rendered body, so it must be stripped of
        # tags: otherwise a search for "div" matches every page.
        for entry in self.index_data(self.index):
            with self.subTest(url=entry["url"]):
                self.assertNotIn("<", entry["text"])
                self.assertNotIn(">", entry["text"])
                self.assertNotIn("|---", entry["text"])

    def test_index_contains_no_excluded_file_contents(self):
        # The string "books/" appears in the README prose -- the layout table
        # and the published/not-published table both name it -- and that is
        # course content, meant to be searchable. What must not be indexed is
        # the *files* themselves, so assert on their actual names and on any
        # real PDF content rather than on the word.
        raw = json.dumps(self.index_data(self.index))
        for banned in (
            "How-Linux-Works-What-Every-Superuser-Should-Know.pdf",
            "Shell Scripting Bible 3rd Edition {PRG }.pdf",
        ):
            with self.subTest(banned=banned):
                self.assertNotIn(banned, raw)
        self.assertNotIn("%PDF", raw)

    def test_index_is_derived_only_from_rendered_pages(self):
        # Three Markdown sources produce exactly three entries; nothing from
        # the copied static tree leaks into the index.
        self.assertEqual(len(self.index_data(self.index)), len(build_site.MARKDOWN_PAGES))

    def test_index_stays_small(self):
        raw = json.dumps(self.index_data(self.index))
        self.assertLess(len(raw), 200_000, "search index should stay under ~200 KB")

    def test_search_script_ships_no_highlighter_or_network_client(self):
        # The index is inlined, so there is no fetch(), and highlighting is
        # done at build time, so there is no highlighter bundle either.
        js = (self.out / "assets" / "app.js").read_text(encoding="utf-8")
        self.assertIn("search-index", js)
        for banned in ("XMLHttpRequest", "cdn.", "highlight.js", "hljs"):
            with self.subTest(banned=banned):
                self.assertNotIn(banned, js, f"search must not use {banned}")

    def test_search_never_refetches_the_index(self):
        # A local file:// page cannot fetch a sibling JSON file, so the index
        # is inlined and read from the DOM instead.
        js = (self.out / "assets" / "app.js").read_text(encoding="utf-8")
        for match in re.findall(r".*fetch.*", js):
            with self.subTest(line=match.strip()[:60]):
                self.assertIn("file://", match)

    def test_no_third_party_runtime_dependencies(self):
        # The whole point of the static architecture: no CDN, no framework.
        for name in ("index.html", "labs/lab01/index.html", "seminar/index.html"):
            html = (self.out / name).read_text(encoding="utf-8")
            for pattern in (r'src="https?://', r'href="https?://(?!localhost)'):
                with self.subTest(page=name, pattern=pattern):
                    self.assertIsNone(
                        re.search(pattern, html),
                        f"{name} loads a remote asset",
                    )


class TestPaletteContrast(ShellTestCase):
    """WCAG checks on the palette actually shipped, not on the source."""

    def luminance(self, colour: str) -> float:
        c = colour.lstrip("#")
        channels = [int(c[i:i + 2], 16) / 255 for i in (0, 2, 4)]
        linear = [
            v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
            for v in channels
        ]
        return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]

    def ratio(self, a: str, b: str) -> float:
        la, lb = self.luminance(a), self.luminance(b)
        hi, lo = max(la, lb), min(la, lb)
        return (hi + 0.05) / (lo + 0.05)

    def tokens(self, css: str, theme: str) -> dict[str, str]:
        block = re.search(rf'\[data-theme="{theme}"\]\s*\{{(.*?)\n\}}', css, re.DOTALL)
        self.assertIsNotNone(block, f"no {theme} token block in the stylesheet")
        return dict(re.findall(r"--([\w-]+):\s*(#[0-9a-fA-F]{6})", block.group(1)))

    def test_text_contrast_meets_wcag_aa(self):
        css = (self.out / "assets" / "app.css").read_text(encoding="utf-8")
        for theme in ("light", "dark"):
            t = self.tokens(css, theme)
            for token in ("text", "text-muted", "accent"):
                with self.subTest(theme=theme, token=token):
                    self.assertGreaterEqual(
                        self.ratio(t[token], t["bg"]), 4.5,
                        f"{theme} ${token} on background is below 4.5:1",
                    )

    def test_focus_and_input_borders_meet_wcag_aa_non_text(self):
        css = (self.out / "assets" / "app.css").read_text(encoding="utf-8")
        for theme in ("light", "dark"):
            t = self.tokens(css, theme)
            with self.subTest(theme=theme):
                self.assertGreaterEqual(
                    self.ratio(t["border-strong"], t["bg"]), 3.0,
                    f"{theme} --border-strong on background is below 3:1",
                )
                self.assertGreaterEqual(
                    self.ratio(t["text-faint"], t["bg"]), 3.0,
                    f"{theme} --text-faint on background is below 3:1",
                )

    def test_focus_ring_uses_a_token_that_passes(self):
        css = (self.out / "assets" / "app.css").read_text(encoding="utf-8")
        self.assertIn("outline: 2px solid var(--accent)", css)


class TestAccessibility(ShellTestCase):
    def test_search_dialog_is_a_labelled_dialog(self):
        self.assertRegex(self.index, r'<dialog[^>]*id="search-dialog"')
        self.assertIn('aria-label="Search course notes"', self.index)

    def test_sidebar_navigation_has_an_accessible_label(self):
        self.assertRegex(self.index, r'<nav[^>]*aria-label="Course"')

    def test_html_has_a_language_and_viewport(self):
        self.assertIn('<html lang="en"', self.index)
        self.assertIn('name="viewport"', self.index)

    def test_skip_link_is_the_first_focusable_element(self):
        skip = re.search(r'<a[^>]*class="skip-link"[^>]*href="#main"', self.index)
        self.assertIsNotNone(skip)
        self.assertLess(skip.start(), self.index.index("<main"))

    def test_reduced_motion_is_respected(self):
        css = (self.out / "assets" / "app.css").read_text(encoding="utf-8")
        self.assertIn("prefers-reduced-motion", css)

    def test_responsive_breakpoints_exist(self):
        css = (self.out / "assets" / "app.css").read_text(encoding="utf-8")
        self.assertIn("@media", css)
        self.assertIn("max-width: 900px", css.replace(" ", " ").replace("max-width:900px", "max-width: 900px"))

    def test_heading_anchor_links_point_at_real_headings(self):
        # A regression: a broken replacement once emitted the literal text
        # `match.group(4)` into every heading, so each got a dead `href="#2"`.
        for name, html in (("index", self.index), ("lab", self.lab), ("seminar", self.seminar)):
            ids = set(re.findall(r'<h[1-6] id="([^"]+)"', html))
            anchors = re.findall(
                r'<a href="#([^"]+)" aria-label="Link to this section">', html
            )
            self.assertTrue(anchors, f"{name} should have heading anchor links")
            for target in anchors:
                with self.subTest(page=name, target=target):
                    self.assertIn(target, ids)
            with self.subTest(page=name):
                self.assertNotIn("match.group", html)
                self.assertNotRegex(html, r'href="#\d+"')

    def test_images_carry_alt_text(self):
        for img in re.findall(r"<img [^>]*>", self.lab)[:5]:
            with self.subTest(img=img[:60]):
                self.assertIn("alt=", img)

    def test_no_horizontal_overflow_risk_from_fixed_widths(self):
        css = (self.out / "assets" / "app.css").read_text(encoding="utf-8")
        self.assertIn("max-width: 100%", css)
        self.assertNotIn("width: 100vw", css)


class TestExclusionsStillHold(ShellTestCase):
    def test_development_only_paths_are_not_published(self):
        for name in ("books", "docker", ".git", "Dockerfile", ".gitignore", ".dockerignore", ".venv"):
            with self.subTest(name=name):
                self.assertFalse((self.out / name).exists())

    def test_markdown_sources_are_not_published(self):
        for name in ("README.md", "labs/lab01/report.md", "seminar/de_tai_seminar.md"):
            with self.subTest(name=name):
                self.assertFalse((self.out / name).exists())

    def test_urls_are_unchanged(self):
        for url in ("index.html", "labs/lab01/index.html", "seminar/index.html"):
            with self.subTest(url=url):
                self.assertTrue((self.out / url).is_file())

    def test_assets_directory_contains_only_shipped_assets(self):
        shipped = {p.name for p in (self.out / "assets").iterdir()}
        self.assertEqual(shipped, {"app.css", "app.js"})


if __name__ == "__main__":
    unittest.main()
