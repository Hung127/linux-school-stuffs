"""Tests for hand-written pages: they ship as authored, not as shell pages.

Two gaps and one mistake shaped this contract:

  * syllabus.html received no shell at all -- it is hand-written HTML that
    MARKDOWN_PAGES never touched, so it had no header, no sidebar and did not
    even link the stylesheet;
  * a nav bar was then injected into every slide deck, which is wrong twice
    over. The decks fill the viewport (a 100vh body, or a fixed 1600x900 box
    scaled with `fit()` to innerWidth/innerHeight), so a bar has nowhere to
    sit without covering content. Injected in flow it was unreachable below a
    clipped viewport; made `position: fixed` it overlaid the slide. The decks
    are presentations with their own navigation, so they now ship untouched.

The syllabus keeps its own light palette and no dark variant, so wrapping it
in a two-theme shell rendered it unreadable in dark mode. It ships standalone
with a single link back to the shell, so it is not a dead end.

Run with:
    python -m unittest discover -s docker -t docker -v
"""

import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from build_site import DECK_OVERRIDE_CSS  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
SLIDES = sorted((REPO_ROOT / "slides").glob("*.html"))


class ShipAsAuthoredTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        import shutil
        import tempfile

        import build_site

        cls.tmp = Path(tempfile.mkdtemp(prefix="authored-test-"))
        cls.out = cls.tmp / "out"
        build_site.build(REPO_ROOT, cls.out)
        cls.css = (cls.out / "assets" / "app.css").read_text(encoding="utf-8")

    @classmethod
    def tearDownClass(cls) -> None:
        import shutil

        shutil.rmtree(cls.tmp, ignore_errors=True)


from build_site import DECK_OVERRIDE_CSS  # noqa: E402


class TestDecksAreUntouched(ShipAsAuthoredTestCase):
    def test_every_deck_differs_from_its_source_by_the_injection_only(self):
        # The guarantee that matters is that nothing *restyles* a deck: no class
        # on <body>, no app.css, no colour, type or size injection into the
        # deck's own rules. The only permitted differences are the build-time
        # rule hiding the progress rail and the back link, both appended. The
        # exact-match assertion lives in test_backlinks.
        for source in SLIDES:
            after = (self.out / "slides" / source.name).read_text(encoding="utf-8")
            with self.subTest(deck=source.name):
                self.assertIn(DECK_OVERRIDE_CSS.strip(), after)
                self.assertNotIn("app.css", after)
                self.assertNotIn("course-shell", after)

    def test_the_rail_rule_is_injected_into_every_deck(self):
        for source in SLIDES:
            text = (self.out / "slides" / source.name).read_text(encoding="utf-8")
            with self.subTest(deck=source.name):
                self.assertIn(
                    DECK_OVERRIDE_CSS.strip(), text,
                    "the progress dot rail should be hidden in the built deck",
                )

    def test_the_rail_rule_hides_dots_without_removing_them(self):
        # Each deck does `getElementById('dots').appendChild(...)` with no null
        # guard, so deleting the element would throw and kill the deck's own
        # navigation. `display: none` keeps the node in the DOM and its script
        # working, which is why this is a CSS rule and not a markup edit.
        self.assertRegex(DECK_OVERRIDE_CSS, r"display:\s*none")
        for source in SLIDES:
            text = source.read_text(encoding="utf-8")
            with self.subTest(deck=source.name):
                self.assertIn('id="dots"', text, "the rail node must still exist")
                self.assertIn("getElementById('dots')", text)

    def test_the_rail_rule_targets_the_rail_by_id(self):
        # `#dots` rather than `.dots` / `.dot-nav`: the class differs per deck
        # and could mean something else, but the id is `dots` in all four.
        self.assertIn("#dots", DECK_OVERRIDE_CSS)

    def test_the_rail_rule_preserves_the_counter_and_buttons(self):
        # Deck 4 calls its buttons `.nbtn` rather than `.nav-btn`, and its
        # counter `id="cnt"` rather than `id="counter"`.
        for source in SLIDES:
            text = (self.out / "slides" / source.name).read_text(encoding="utf-8")
            with self.subTest(deck=source.name):
                self.assertRegex(text, r'class="nav-btn"|class="nbtn"')
                self.assertRegex(text, r'id="counter"|id="cnt"')

    def test_decks_reference_no_shell_assets(self):
        for source in SLIDES:
            text = (self.out / "slides" / source.name).read_text(encoding="utf-8")
            for marker in ("app.css", "app.js", "deck-bar", "deck-shell", "course-shell"):
                with self.subTest(deck=source.name, marker=marker):
                    self.assertNotIn(
                        marker, text,
                        f"{source.name} must not reference {marker}",
                    )

    def test_no_nav_bar_markup_remains_anywhere(self):
        for source in SLIDES:
            text = (self.out / "slides" / source.name).read_text(encoding="utf-8")
            self.assertNotIn('class="nav-list"', text)
            self.assertNotIn("pager-prev", text)
            self.assertNotIn("pager-next", text)

    def test_decks_are_still_served_at_their_original_urls(self):
        for source in SLIDES:
            with self.subTest(deck=source.name):
                self.assertTrue((self.out / "slides" / source.name).is_file())


class TestSyllabusIsStandalone(ShipAsAuthoredTestCase):
    def syllabus(self) -> str:
        return (self.out / "syllabus.html").read_text(encoding="utf-8")

    def test_syllabus_keeps_its_own_stylesheet_and_fonts(self):
        text = self.syllabus()
        for marker in ("<style", "Lora", "IBM Plex Mono"):
            with self.subTest(marker=marker):
                self.assertIn(marker, text)

    def test_syllabus_keeps_its_own_light_palette(self):
        # A regression: the shell's dark background under the syllabus's
        # near-black --text made the page unreadable in dark mode.
        text = self.syllabus()
        root = re.search(r":root\s*\{(.*?)\}", text, re.DOTALL)
        self.assertIsNotNone(root, "the syllabus should still declare :root tokens")
        tokens = dict(re.findall(r"(--[\w-]+)\s*:\s*([^;]+)", root.group(1)))
        self.assertIn("--text", tokens)
        self.assertIn("--white", tokens)

    def test_syllabus_does_not_inherit_the_shell(self):
        text = self.syllabus()
        for marker in ("app.css", "app.js", "course-shell", "data-theme", "deck-shell"):
            with self.subTest(marker=marker):
                self.assertNotIn(marker, text)

    def test_syllabus_keeps_its_course_content(self):
        text = self.syllabus().lower()
        for marker in ("module", "capstone", "quiz"):
            with self.subTest(marker=marker):
                self.assertIn(marker, text)

    def test_syllabus_is_not_a_dead_end(self):
        # It leaves the shell, so it needs exactly one way back.
        text = self.syllabus()
        back = re.findall(r'<a[^>]+href="(\.\./)?index\.html"[^>]*>', text)
        self.assertEqual(
            len(back), 1,
            "the standalone syllabus should link back to the course exactly once",
        )

    def test_syllabus_back_link_resolves(self):
        back = re.search(r'href="(\.\./)?index\.html"', self.syllabus())
        self.assertIsNotNone(back)
        target = (self.out / "syllabus.html").parent / (back.group(1) or "") / "index.html"
        self.assertTrue(target.resolve().is_file(), "the back link points nowhere")

    def test_syllabus_is_still_reachable_from_the_shell(self):
        index = (self.out / "index.html").read_text(encoding="utf-8")
        self.assertIn("syllabus.html", index)
        self.assertRegex(index, r'nav-label">Syllabus')


class TestStylesheetIsScoped(ShipAsAuthoredTestCase):
    def selectors(self) -> list[str]:
        css = re.sub(r"/\*.*?\*/", "", self.css, flags=re.S)
        found: list[str] = []
        for match in re.finditer(r"(?:^|\})\s*([^{}@]+)\{", css, re.MULTILINE):
            for part in match.group(1).split(","):
                part = part.strip()
                if part:
                    found.append(part)
        return found

    def test_no_unscoped_element_selectors_remain(self):
        # A bare `pre` or `*` rule leaks onto any page that is not the shell.
        bare = sorted({s for s in self.selectors() if not re.search(r"[.#\[:]", s)})
        self.assertEqual(
            bare, [],
            f"these selectors are not scoped to the shell and would leak: {bare}",
        )

    def test_pygments_base_rule_is_scoped(self):
        # Pygments emits `.hl { background: #282C34 }`, which would paint a
        # near-black block on the light-only syllabus.
        self.assertRegex(self.css, r"\.course-shell \.hl\s*\{")
        self.assertNotRegex(self.css, r"(?m)^\.hl\s*\{")

    def test_no_selector_is_defined_twice_with_the_same_declarations(self):
        # Two `.deck-bar {}` blocks once existed because a rule was appended
        # instead of edited. Catch a genuinely duplicated rule -- the same
        # selector carrying the same body twice -- rather than the normal case
        # of several distinct rules for one element (`.sidebar`, then
        # `.sidebar a`).
        css = re.sub(r"/\*.*?\*/", "", self.css, flags=re.DOTALL)
        # The same rule declared twice verbatim -- which is what happens when a
        # block is appended rather than edited. Several distinct rules for one
        # element (`.sidebar`, then `.sidebar a`) are normal and allowed.
        seen: dict[tuple[str, str], int] = {}
        for selector, body in re.findall(r"(?m)^(\.[\w-]+)\s*\{([^}]*)\}", css):
            key = (selector, " ".join(body.split()))
            seen[key] = seen.get(key, 0) + 1
        repeated = sorted(
            f"{selector} {{{body[:30]}}}" for (selector, body), n in seen.items() if n > 1
        )
        self.assertEqual(
            repeated, [],
            f"these rules are declared more than once verbatim: {repeated}",
        )

    def test_no_deck_navigation_css_remains(self):
        for marker in (".deck-bar", ".deck-shell", ".deck-nav"):
            with self.subTest(marker=marker):
                self.assertNotIn(marker, self.css)


class TestShellPagesStillWork(ShipAsAuthoredTestCase):
    def test_markdown_pages_keep_the_full_shell(self):
        for page in ("index.html", "labs/lab01/index.html", "seminar/index.html"):
            text = (self.out / page).read_text(encoding="utf-8")
            with self.subTest(page=page):
                for marker in ('class="site-header"', 'class="sidebar"', "app.css", "app.js"):
                    self.assertIn(marker, text)

    def test_decks_are_linked_from_the_sidebar(self):
        index = (self.out / "index.html").read_text(encoding="utf-8")
        for source in SLIDES:
            with self.subTest(deck=source.name):
                self.assertIn(source.name, index)

    def test_theme_toggle_never_appears_on_a_light_only_page(self):
        # The syllabus has no dark variant, so offering the toggle there would
        # be a broken promise.
        self.assertNotIn("theme-toggle", (self.out / "syllabus.html").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
