"""Tests for the back link added to the hand-written pages.

These pages ship standalone rather than inside the shell, because each defines
its own palette on :root and several of those token names collide with the
shell's. Wrapping them put the shell's dark background behind content asking
for its own near-black text, which made them unreadable in dark mode.

The link is the minimum needed to avoid a dead end, and it is deliberately
inert: bare markup, no injected CSS, appended in normal flow. It must not be
able to reflow or cover the page's own content -- the failure mode that made
the deck navigation bar unacceptably intrusive.

Run with:
    python -m unittest discover -s docker -t docker -v
"""

import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from build_site import (  # noqa: E402
    BACK_LINK_CLASS,
    DECK_LINK_CLASS,
    DECK_OVERRIDE_CSS,
    STANDALONE_PAGES,
    back_link_for,
)

REPO_ROOT = Path(__file__).resolve().parent.parent


class BackLinkTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        import shutil
        import tempfile

        import build_site

        cls.tmp = Path(tempfile.mkdtemp(prefix="backlink-test-"))
        cls.out = cls.tmp / "out"
        build_site.build(REPO_ROOT, cls.out)

    @classmethod
    def tearDownClass(cls) -> None:
        import shutil

        shutil.rmtree(cls.tmp, ignore_errors=True)

    def built(self, relative: str) -> str:
        return (self.out / relative).read_text(encoding="utf-8")


class TestEveryStandalonePageHasOne(BackLinkTestCase):
    def test_the_list_covers_every_hand_written_document(self):
        # The decks are excluded on purpose: they are presentations, not
        # documents, and they carry their own prev/next controls. This asserts
        # the list itself, so adding a new lab sheet without a back link fails
        # here rather than silently shipping a dead end.
        for relative in STANDALONE_PAGES:
            with self.subTest(page=relative):
                self.assertTrue((REPO_ROOT / relative).is_file())
                self.assertTrue((self.out / relative).is_file())
        self.assertIn("syllabus.html", STANDALONE_PAGES)
        self.assertIn("labs/lab01/linux_lab_1.html", STANDALONE_PAGES)

    def test_each_standalone_page_has_exactly_one_back_link(self):
        for relative in STANDALONE_PAGES:
            with self.subTest(page=relative):
                self.assertEqual(
                    self.built(relative).count(BACK_LINK_CLASS), 1,
                    f"{relative} should have exactly one back link",
                )

    def test_the_link_resolves(self):
        for relative in STANDALONE_PAGES:
            match = re.search(
                rf'href="([^"]+)">&larr; Back to the course',
                self.built(relative),
            )
            self.assertIsNotNone(match, f"{relative} has no back link")
            target = (self.out / relative).parent / match.group(1)
            with self.subTest(page=relative):
                self.assertTrue(
                    target.resolve().is_file(),
                    f"{relative} back link {match.group(1)!r} points nowhere",
                )

    def test_nested_pages_step_up_enough_levels(self):
        # labs/labNN/ is two directories deep, so `index.html` would resolve to
        # labs/labNN/index.html -- a file that does not exist.
        self.assertEqual(back_link_for("syllabus.html"), '<p class="%s"><a href="index.html">&larr; Back to the course</a></p>' % BACK_LINK_CLASS)
        self.assertIn("../../index.html", back_link_for("labs/lab01/linux_lab_1.html"))

    def test_the_back_link_text_is_readable(self):
        for relative in STANDALONE_PAGES:
            with self.subTest(page=relative):
                self.assertIn("Back to the course", self.built(relative))


class TestBackLinkCannotReflow(BackLinkTestCase):
    def test_no_css_is_injected_into_a_standalone_page(self):
        # The link inherits the page's own styling. Injecting CSS would mean
        # restyling pages that were committed to shipping as authored, and is
        # the thing most likely to reintroduce a layout difference.
        for relative in STANDALONE_PAGES:
            with self.subTest(page=relative):
                self.assertNotIn("<style>#dots", self.built(relative))
                self.assertNotIn("app.css", self.built(relative))
                self.assertNotIn("course-shell", self.built(relative))

    def test_the_link_is_not_positioned_out_of_flow(self):
        # A fixed or absolute link would sit over the page's own content, which
        # is exactly the deck-bar failure. Plain markup in normal flow cannot.
        for relative in STANDALONE_PAGES:
            body = self.built(relative)
            link_at = body.index(BACK_LINK_CLASS)
            tail = body[link_at:]
            with self.subTest(page=relative):
                for forbidden in ("position:fixed", "position: fixed",
                                  "position:absolute", "position: absolute",
                                  "position:sticky", "position: sticky"):
                    self.assertNotIn(forbidden, tail)

    def test_the_link_is_the_last_element_in_the_body(self):
        for relative in STANDALONE_PAGES:
            body = self.built(relative)
            with self.subTest(page=relative):
                self.assertLess(
                    body.index(BACK_LINK_CLASS),
                    body.index("</body>"),
                    "the link should be the last thing in the body",
                )

    def test_each_page_differs_from_source_by_the_link_only(self):
        for relative in STANDALONE_PAGES:
            original = (REPO_ROOT / relative).read_text(encoding="utf-8")
            link = back_link_for(relative)
            with self.subTest(page=relative):
                self.assertEqual(
                    self.built(relative).replace(link, ""),
                    original,
                    f"{relative} differs from source by more than the back link",
                )


class TestStandalonePagesKeepTheirOwnStyles(BackLinkTestCase):
    def root_tokens(self, relative: str) -> set[str]:
        text = self.built(relative)
        css = " ".join(re.findall(r"<style[^>]*>(.*?)</style>", text, re.DOTALL))
        names: set[str] = set()
        for block in re.findall(r":root\s*\{(.*?)\}", css, re.DOTALL):
            names |= set(re.findall(r"(--[\w-]+)\s*:", block))
        return names

    def test_every_page_still_declares_its_own_palette(self):
        # These pages collide with the shell on --bg, --text, --border and
        # more, which is the reason they ship standalone. Their tokens must
        # survive intact or the page stops rendering as its author intended.
        for relative in STANDALONE_PAGES:
            with self.subTest(page=relative):
                self.assertTrue(
                    self.root_tokens(relative),
                    f"{relative} should still declare its own :root palette",
                )

    def test_page_content_survives(self):
        for relative, marker in (
            ("syllabus.html", "capstone"),
            ("labs/lab01/linux_lab_1.html", "Homework"),
            ("labs/lab02/linux_lab_2.html", "<html"),
        ):
            with self.subTest(page=relative):
                self.assertIn(marker, self.built(relative))


class TestDecksCarryTheLinkInAClearCorner(BackLinkTestCase):
    """The decks fill the viewport, so a link has to be positioned.

    Every deck centres its content and puts its own chrome at bottom-centre
    (.nav) and, in decks 3 and 4, bottom-right (.kbd-hint / .kbhint). Top-left
    is the one corner nothing occupies, which is why the link goes there.

    Only two of the four decks have an `.idle` hook that hides their chrome, so
    an idle-only link could not be uniform. The link is therefore always
    visible, and no JavaScript is added to any deck.
    """

    def deck(self, name: str) -> str:
        return (self.out / "slides" / name).read_text(encoding="utf-8")

    def deck_rule(self) -> str:
        """The CSS rule body for the deck link.

        Matched on the class rather than a substring count, because the class
        also appears in the <nav> element and in the :hover rule.
        """
        match = re.search(rf"\.{DECK_LINK_CLASS}\s*\{{(.*?)\}}", DECK_OVERRIDE_CSS)
        self.assertIsNotNone(match, "no rule for the deck link")
        return match.group(1)

    def test_every_deck_has_exactly_one_link(self):
        for source in sorted((REPO_ROOT / "slides").glob("*.html")):
            with self.subTest(deck=source.name):
                self.assertEqual(
                    self.deck(source.name).count(f'<nav class="{DECK_LINK_CLASS}"'), 1,
                    f"{source.name} should carry exactly one back link",
                )

    def test_the_deck_link_resolves(self):
        for source in sorted((REPO_ROOT / "slides").glob("*.html")):
            match = re.search(
                rf'href="([^"]+)">&larr; Back to the course',
                self.deck(source.name),
            )
            self.assertIsNotNone(match, f"{source.name} has no back link")
            target = (self.out / "slides" / match.group(1)).resolve()
            with self.subTest(deck=source.name):
                self.assertTrue(
                    target.is_file(),
                    f"{source.name} link {match.group(1)!r} points nowhere",
                )

    def test_the_link_is_pinned_to_the_top_left(self):
        # The rule that positions it, asserted rather than trusted: a link that
        # ended up centred or full-width would be the overflow we already hit.
        for source in sorted((REPO_ROOT / "slides").glob("*.html")):
            with self.subTest(deck=source.name):
                self.assertIn("position: fixed", DECK_OVERRIDE_CSS)
                self.assertRegex(DECK_OVERRIDE_CSS, r"top\s*:\s*[\d.]+rem")
                self.assertRegex(DECK_OVERRIDE_CSS, r"left\s*:\s*[\d.]+rem")

    def test_the_link_rule_sets_no_width_or_height(self):
        # No width, height, inset or padding that could grow: a fixed element
        # given a size is what covers content. This is text, so it needs none.
        # Matched on a property boundary, so `line-height` is not read as
        # `height`.
        rule = self.deck_rule()
        for forbidden in ("width", "height", "inset", "padding", "margin", "min-width"):
            with self.subTest(prop=forbidden):
                self.assertIsNone(
                    re.search(rf"(?<![-\w]){re.escape(forbidden)}\s*:", rule),
                    f"the deck link rule must not set {forbidden}",
                )

    def test_the_link_never_blocks_the_deck(self):
        # It must not be a full-viewport overlay, or it would intercept clicks
        # meant for the slide. Fixed to a corner with no size, it cannot be.
        rule = self.deck_rule()
        for forbidden in ("inset", "100vw", "100vh", "100%"):
            with self.subTest(prop=forbidden):
                self.assertNotIn(forbidden, rule)

    def test_no_javascript_is_added_to_a_deck(self):
        # Two of the four decks have no idle hook, and matching the other two
        # would mean injecting script. The link is CSS and markup only.
        for source in sorted((REPO_ROOT / "slides").glob("*.html")):
            after = self.deck(source.name)
            with self.subTest(deck=source.name):
                self.assertEqual(
                    after.count("<script"),
                    source.read_text(encoding="utf-8").count("<script"),
                    "a deck gained a script",
                )

    def test_decks_differ_from_source_by_the_injection_only(self):
        import build_site

        for source in sorted((REPO_ROOT / "slides").glob("*.html")):
            after = self.deck(source.name)
            with self.subTest(deck=source.name):
                self.assertEqual(
                    after.replace(DECK_OVERRIDE_CSS.strip(), "").replace(
                        build_site.deck_link("slides/" + source.name), ""
                    ),
                    source.read_text(encoding="utf-8"),
                    f"{source.name} differs by more than the injected rule and link",
                )

    def test_a_deck_still_carries_no_shell_assets(self):
        for source in sorted((REPO_ROOT / "slides").glob("*.html")):
            after = self.deck(source.name)
            with self.subTest(deck=source.name):
                for marker in ("app.css", "app.js", "course-shell", "deck-shell"):
                    self.assertNotIn(marker, after)


class TestLabSheetsAreReachable(BackLinkTestCase):
    def test_lab02_is_in_the_sidebar(self):
        # It is published but has no report, so without this it would be an
        # unreachable file in the build.
        self.assertIn("Lab 02", self.built("index.html"))

    def test_lab_entries_point_at_real_files(self):
        # A trailing-slash href is served from that directory's index.html, so
        # check the file the server would actually read. Anything else -- a
        # page, a PDF, a sheet -- is a plain file path.
        index = self.built("index.html")
        for href in re.findall(r'<a[^>]+href="([^"]*labs/[^"]*)"', index):
            path = href.split("#")[0]
            target = self.out / (f"{path}index.html" if path.endswith("/") else path)
            with self.subTest(href=href):
                self.assertTrue(
                    target.is_file(),
                    f"lab entry {href!r} points at a missing file",
                )


if __name__ == "__main__":
    unittest.main()
