"""Tests that the shell's design tokens cannot collide with a page's own.

Regression: the palette used `--bg`, `--text`, `--border`, `--surface`,
`--accent`, `--sans` and `--mono`, and every hand-written page in this
repository defines several of those same names on its own `:root`. Because the
shell's tokens were declared on <body> -- a descendant of the <html> that
carries `:root` -- the more specific rule won and silently replaced the page's
palette. On the slide decks that also swapped the typeface, which reflowed
their text and produced visible overflow.

The fix is a private `--cn-*` prefix, so the two namespaces cannot overlap.
These tests assert that, rather than asserting today's specific four names.

Run with:
    python -m unittest discover -s docker -t docker -v
"""

import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

REPO_ROOT = Path(__file__).resolve().parent.parent

# Hand-written pages whose own palettes must survive the build untouched.
HAND_WRITTEN_PAGES = [REPO_ROOT / "syllabus.html"] + sorted((REPO_ROOT / "slides").glob("*.html"))


def custom_properties(css: str) -> set[str]:
    """Every custom property name declared anywhere in a stylesheet."""
    return set(re.findall(r"(--[\w-]+)\s*:", css))


def root_properties(page: Path) -> set[str]:
    """The custom properties a page declares on its own :root."""
    text = page.read_text(encoding="utf-8")
    blocks = re.findall(r":root\s*\{(.*?)\}", text, re.DOTALL)
    names: set[str] = set()
    for block in blocks:
        names |= set(re.findall(r"(--[\w-]+)\s*:", block))
    return names


class ShellTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        import shutil
        import tempfile

        cls.tmp = Path(tempfile.mkdtemp(prefix="tokens-test-"))
        cls.out = cls.tmp / "out"
        import build_site

        build_site.build(REPO_ROOT, cls.out)
        cls.css = (cls.out / "assets" / "app.css").read_text(encoding="utf-8")

    @classmethod
    def tearDownClass(cls) -> None:
        import shutil

        shutil.rmtree(cls.tmp, ignore_errors=True)


class TestNoTokenCollision(ShellTestCase):
    def test_shell_tokens_never_collide_with_a_hand_written_page(self):
        mine = custom_properties(self.css)
        self.assertTrue(mine, "app.css should declare custom properties")
        for page in HAND_WRITTEN_PAGES:
            theirs = root_properties(page)
            self.assertTrue(theirs, f"{page.name} declares no :root properties?")
            clash = sorted(theirs & mine)
            with self.subTest(page=page.name):
                self.assertEqual(
                    clash, [],
                    f"{page.name} defines {clash}, which the shell also defines; "
                    "one will silently override the other",
                )

    def test_every_shell_token_is_privately_prefixed(self):
        # A single naming convention is what makes the collision impossible
        # rather than merely absent today.
        mine = custom_properties(self.css)
        unprefixed = sorted(
            name for name in mine if not name.startswith("--cn-")
        )
        self.assertEqual(
            unprefixed, [],
            "shell tokens must all be --cn-* so they cannot collide",
        )

    def test_pygments_token_names_are_not_mistaken_for_shell_tokens(self):
        # Pygments emits .hl .k / .hl .nb etc. as class names, not custom
        # properties, so the check above must not pick them up as collisions.
        for token in ("--cn-bg", "--cn-text", "--cn-accent"):
            self.assertIn(token, self.css)

    def test_shell_declares_no_bare_root_token_block(self):
        # A bare :root block has equal specificity to [data-theme] and would
        # win or lose purely on stylesheet order.
        self.assertNotRegex(
            self.css, r"(?m)^:root\s*\{[^}]*--cn-",
            "shell tokens must not be declared on a bare :root",
        )


class TestHandWrittenPagesKeepTheirPalette(ShellTestCase):
    def test_every_page_still_declares_its_own_root_tokens(self):
        for page in HAND_WRITTEN_PAGES:
            built = self.out / page.relative_to(REPO_ROOT)
            with self.subTest(page=page.name):
                self.assertTrue(built.is_file(), f"{page.name} missing from the build")
                self.assertEqual(
                    root_properties(page),
                    root_properties(built),
                    f"{page.name}'s own :root palette changed during the build",
                )

    def test_deck_palette_values_are_unchanged(self):
        # The concrete symptom: deck 1 is dark by design (#0a0d12). If the
        # shell replaced --bg, the deck would render light and its own text
        # colours would be unreadable.
        deck = self.out / "slides" / "1_linux_architecture.html"
        text = deck.read_text(encoding="utf-8")
        self.assertIn("#0a0d12", text, "deck 1's background token is gone")

    def test_deck_body_never_matches_the_colour_bearing_shell_rule(self):
        # The shell's `.course-shell` rule sets background, colour, font-family,
        # font-size, line-height and min-height. A class selector outranks the
        # decks' own `body` / `html, body` element rules, so a deck body
        # carrying `course-shell` silently loses its own palette -- which is
        # what made the deployed decks reflow and overflow. Decks now ship
        # byte-identical, so no deck can carry that class at all.
        for deck in sorted((self.out / "slides").glob("*.html")):
            text = deck.read_text(encoding="utf-8")
            with self.subTest(deck=deck.name):
                self.assertNotIn(
                    "course-shell", text,
                    "a deck must not match .course-shell, which would override "
                    "the deck's own background, colour and type",
                )
                self.assertNotIn("deck-shell", text)
                self.assertNotIn("app.css", text)

    def test_shell_metrics_block_carries_no_visuals(self):
        # The first `.course-shell {` block holds custom properties only; the
        # visual rules follow. Keeping them apart means the metrics can be
        # inherited without dragging colours and type along.
        blocks = re.findall(r"\.course-shell\s*\{(.*?)\n?\}\s*\n", self.css, re.DOTALL)
        self.assertGreaterEqual(len(blocks), 2, "expected a metrics block and a visual block")
        metrics = blocks[0]
        self.assertIn("--cn-sans:", metrics, "the metrics block should hold the type stacks")
        for prop in ("background", "color:", "font-family", "font-size", "line-height"):
            with self.subTest(prop=prop):
                self.assertNotIn(
                    prop, metrics,
                    "the metrics block must stay visual-free, or a deck would "
                    "inherit it if it also carried .course-shell",
                )

    def test_shell_visual_block_is_scoped_to_the_shell(self):
        for prop in ("background", "color", "font-family", "font-size"):
            with self.subTest(prop=prop):
                self.assertRegex(
                    self.css, rf"\.course-shell\s*\{{[^}}]*{prop}:",
                    f".course-shell should carry {prop}",
                )


class TestNoDeadTokenReferences(ShellTestCase):
    """Every var() in the stylesheet must resolve to a declared token.

    The deck bar was removed when the decks stopped taking injected
    navigation, which left its `--cn-bar-*` tokens behind once. An unresolved
    var() is silent -- the property just falls back to its initial value -- so
    leftovers are easy to miss and are caught here instead.
    """

    def test_every_referenced_token_is_declared(self):
        declared = set(custom_properties(self.css))
        used = set(re.findall(r"var\((--[\w-]+)\)", self.css))
        missing = sorted(used - declared)
        self.assertEqual(
            missing, [],
            f"these tokens are used but never declared: {missing}",
        )

    def test_no_dead_bar_tokens_remain(self):
        for token in ("--cn-bar-bg", "--cn-bar-text", "--cn-bar-border", "--cn-bar-accent"):
            with self.subTest(token=token):
                self.assertNotIn(
                    token, self.css,
                    "the deck bar was removed; its tokens should be gone too",
                )


if __name__ == "__main__":
    unittest.main()
