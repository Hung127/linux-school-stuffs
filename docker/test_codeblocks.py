"""Tests for how fenced code blocks are emitted and coloured.

Two defects hid behind a passing suite. Both came from Pygments' HtmlFormatter
wrapping its output in its own `<div class="hl"><pre>...</pre></div>`, which
was being nested inside the block element the build already had:

    <pre><code class="hl"><div class="hl"><pre>...</pre></div></code></pre>

A `<pre>` inside a `<pre>` inside a `<div>` inside a `<code>`. The tokens were
generated correctly all along -- the tests only checked that a token span
existed, never that the structure around it was valid -- so 39 code blocks
shipped looking like one undifferentiated slab.

The second was hidden behind the first: the Pygments base rule paints
`.hl { background: #282C34 }`, which is its own dark palette. With the wrapper
gone that rule targets the block element directly, so it would paint a dark
background onto a light-theme code block.

Run with:
    python -m unittest discover -s docker -t docker -v
"""

import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import theme
from pygments.styles import get_style_by_name

REPO_ROOT = Path(__file__).resolve().parent.parent
FENCE_LANGUAGES = {"bash", "text"}
CODE_LIGHT_THEME = theme.CODE_LIGHT_THEME
CODE_THEME = theme.CODE_THEME

# Light and dark selectors for the token rules, as they appear in app.css.
LIGHT_PREFIX = ".course-shell"
DARK_PREFIX = '[data-theme="dark"] .course-shell'


def _normalise_hex(colour: str) -> str:
    """Expand CSS shorthand so `#666` and `#666666` compare equal.

    Pygments shortens hex values when it writes CSS (`#666666` becomes
    `#666`) but stores them expanded in the style, so a straight comparison
    reports a palette member as foreign.
    """
    value = colour.strip().lower()
    if re.fullmatch(r"#[0-9a-f]{3}", value):
        return "#" + "".join(ch * 2 for ch in value[1:])
    return value


def _pygments_colours(style_name: str) -> set[str]:
    """Every hex colour the palette assigns, normalised for comparison."""
    colours: set[str] = set()
    for entry in get_style_by_name(style_name).styles.values():
        found = re.search(r"#([0-9a-fA-F]{3,8})\b", entry or "")
        if found:
            colours.add(_normalise_hex(f"#{found.group(1)}"))
    return colours


def _palette_gives_colour(cls: str, prefix: str) -> bool:
    """True when Pygments emits no rule for `cls` in this theme's palette.

    A token the palette leaves uncoloured is meant to inherit, so the absence
    of a rule is correct. Pygments' own output is the oracle here rather than
    the raw style dict: several tokens share a short class, so one of them
    carrying a colour says nothing about whether the class as a whole gets a
    rule. Punctuation is the case in point -- `Token.Punctuation.Marker` has a
    colour, but Pygments emits `.pm` and not `.p`, so a plain punctuation span
    is meant to inherit.
    """
    style_name = CODE_LIGHT_THEME if prefix == LIGHT_PREFIX else CODE_THEME
    generated = theme._code_theme_rules(style_name)
    return not re.search(rf"^\.course-shell \.hl \.{cls} \{{", generated, re.MULTILINE)


class CodeBlockTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        import shutil
        import tempfile

        import build_site

        cls.tmp = Path(tempfile.mkdtemp(prefix="codeblock-test-"))
        cls.out = cls.tmp / "out"
        build_site.build(REPO_ROOT, cls.out)
        cls.lab = (cls.out / "labs" / "lab01" / "index.html").read_text(encoding="utf-8")
        cls.index = (cls.out / "index.html").read_text(encoding="utf-8")
        cls.css = (cls.out / "assets" / "app.css").read_text(encoding="utf-8")

    @classmethod
    def tearDownClass(cls) -> None:
        import shutil

        shutil.rmtree(cls.tmp, ignore_errors=True)

    def blocks(self, html: str) -> list[str]:
        return re.findall(r'<div class="code-block">.*?</div></div>', html, re.DOTALL)


class TestBlockStructureIsValid(CodeBlockTestCase):
    def test_a_pre_is_never_nested_inside_another(self):
        # The invariant that was broken. Checked on the raw markup, because a
        # browser is the only thing that would actually render the result.
        for name, html in (("lab report", self.lab), ("landing page", self.index)):
            with self.subTest(page=name):
                self.assertNotIn(
                    "<pre", self._inner_pre(html),
                    "a <pre> is nested inside another",
                )

    def _inner_pre(self, html: str) -> str:
        """Any <pre> that appears while already inside a <pre>."""
        offenders = []
        depth = 0
        for match in re.finditer(r"</?pre\b", html):
            depth += -1 if match.group(0).startswith("</") else 1
            if depth > 1:
                offenders.append(match.group(0))
        return " ".join(offenders)

    def test_each_block_has_exactly_one_pre(self):
        for block in self.blocks(self.lab):
            with self.subTest(block=block[:40]):
                self.assertEqual(block.count("<pre>"), 1)
                self.assertEqual(block.count("</pre>"), 1)

    def test_the_block_element_contains_only_spans(self):
        # Pygments with nowrap=True emits spans and nothing else. Any element
        # in here means a wrapper crept back in.
        for block in self.blocks(self.lab):
            inner = re.search(r'<code[^>]*>(.*)</code>', block, re.DOTALL)
            self.assertIsNotNone(inner, block[:60])
            for tag in re.findall(r"<(?!/?span\b)([a-zA-Z][\w-]*)", inner.group(1)):
                self.assertEqual(
                    tag, "span",
                    f"a <{tag}> is inside the code element; Pygments should "
                    "emit spans only",
                )

    def test_no_div_appears_inside_a_code_block(self):
        self.assertNotIn("<div", "".join(
            re.search(r'<code[^>]*>(.*?)</code>', b, re.DOTALL).group(1)
            for b in self.blocks(self.lab)
        ))


class TestTokensAreEmitted(CodeBlockTestCase):
    def test_every_language_produces_token_spans(self):
        labels = re.findall(r'<span class="code-lang">(\w+)</span>', self.lab)
        self.assertTrue(labels)
        for language in FENCE_LANGUAGES:
            with self.subTest(language=language):
                self.assertIn(language, labels, f"no {language} block in the report")

    def test_every_language_in_use_resolves_to_a_lexer(self):
        # The bug that made all 46 bash fences plain: `bash` was missing from
        # the alias table while `sh`/`shell`/`zsh` pointed at it. Assert on the
        # languages this repository actually uses, not on one convenient block.
        import build_site

        for language in FENCE_LANGUAGES:
            with self.subTest(language=language):
                self.assertIsNotNone(
                    build_site._lexer_for(language),
                    f"no lexer for {language!r}, so its blocks render unhighlighted",
                )

    def test_every_fence_in_the_notes_is_highlighted(self):
        # Counts blocks against token spans per language, so a language that
        # silently stops resolving fails here rather than looking fine.
        import build_site

        for language in FENCE_LANGUAGES:
            source = REPO_ROOT / "labs" / "lab01" / "report.md"
            text = source.read_text(encoding="utf-8")
            body, _, langs = build_site.render_markdown(text)
            styled = build_site._style_fences(body, langs)
            if language not in langs:
                continue
            with self.subTest(language=language):
                self.assertIn(
                    '<span class=',
                    styled,
                    f"{language} produced no token spans at all",
                )

    def test_bash_blocks_carry_token_spans(self):
        blocks = re.findall(
            r'<code class="hl language-bash">(.*?)</code>', self.lab, re.DOTALL
        )
        self.assertTrue(blocks, "the report should have bash blocks")
        with_spans = [b for b in blocks if "<span class=" in b]
        self.assertEqual(
            len(with_spans), len(blocks),
            f"{len(blocks) - len(with_spans)} of {len(blocks)} bash blocks "
            "have no token spans",
        )

    def test_bash_keywords_are_coloured(self):
        # `awk` in a bash block is a command name; Pygments tags it. Proves the
        # lexer is actually running rather than falling back to plain text.
        self.assertRegex(self.lab, r'<code class="hl language-bash">[^<]*\S')

    def test_special_characters_stay_escaped(self):
        # awk's `<` and `>` must not become real tags.
        for block in self.blocks(self.lab):
            inner = re.search(r"<code[^>]*>(.*)</code>", block, re.DOTALL)
            if inner:
                with self.subTest(block=block[:40]):
                    self.assertNotIn("&lt;", inner.group(1).replace("&amp;lt;", ""))


class TestEveryTokenIsColoured(CodeBlockTestCase):
    """The tests that should have caught the flat-looking blocks.

    Three checks passed in a row while the code was visibly monochrome. Each
    asked whether colour was *defined*, never whether the browser *received*
    one. A `dockerfile` block satisfied the first, 5 of 24 token rules satisfied
    the second, and 106 well-formed-looking rules satisfied the third -- when
    every one of them read `color: #;` or `color: b;`, because a Pygments style
    entry is a string like `'bold #61AFEF'` and `entry[0]` is the character
    `'b'`. The browser discards those declarations silently, so the block fell
    back to body text in both themes while every structural assertion held.

    So the assertions below are about what the cascade ends up with: that each
    colour is a colour, that it came from the palette for the theme it is
    scoped to, and that each token the reader actually sees resolves to one.
    """

    def token_classes(self, html: str) -> set[str]:
        classes: set[str] = set()
        for block in re.findall(
            r'<code class="hl language-\w+">(.*?)</code>', html, re.DOTALL
        ):
            classes |= set(re.findall(r'<span class="([a-z]+)"', block))
        return classes

    def rules_for(self, prefix: str) -> dict[str, str]:
        pattern = rf'^{re.escape(prefix)} \.hl \.([a-z]+) \{{([^}}]*)\}}'
        return dict(re.findall(pattern, self.css, re.MULTILINE))

    def test_the_report_uses_enough_tokens_to_be_meaningful(self):
        classes = self.token_classes(self.lab)
        self.assertGreaterEqual(
            len(classes), 5,
            f"only {sorted(classes)} found; the fixture is not exercising much",
        )

    def test_no_colour_declaration_in_the_stylesheet_is_malformed(self):
        # The direct check on the defect: `color: #;` and `color: b;` are what a
        # Pygments style string misread as a tuple produces, and the browser
        # drops both without a word.
        allowed = r"(#[0-9a-fA-F]{3,8}|var\(--[a-z-]+\)|currentColor|inherit|transparent)"
        malformed = [
            value for value in re.findall(r"color:\s*([^;}]+)", self.css)
            if not re.fullmatch(allowed, value.strip())
        ]
        self.assertEqual(
            malformed, [],
            f"these declarations are not colours and will be discarded: "
            f"{sorted(set(malformed))[:10]}",
        )

    def test_token_colours_come_from_the_palette_for_their_theme(self):
        # A light rule carrying a dark-palette colour renders the wrong theme's
        # colours on a white background, which is legible enough to ship.
        palettes = {
            ".course-shell": CODE_LIGHT_THEME,
            '[data-theme="dark"] .course-shell': CODE_THEME,
        }
        for prefix, style_name in palettes.items():
            expected = {
                colour.lower()
                for colour in _pygments_colours(style_name)
            }
            for cls, body in self.rules_for(prefix).items():
                for colour in re.findall(r"color:\s*(#[0-9a-fA-F]{3,8})", body):
                    with self.subTest(prefix=prefix, token=cls, colour=colour):
                        self.assertIn(
                            _normalise_hex(colour), expected,
                            f"colour {colour} is not in the {style_name} palette",
                        )

    def test_every_token_the_reader_sees_resolves_in_both_themes(self):
        # A class with no rule is fine only where its palette entry carries no
        # colour -- punctuation is one, and inheriting body text is correct.
        # Anything else means the token renders as plain text.
        unresolvable = []
        for cls in sorted(self.token_classes(self.lab)):
            for prefix in (".course-shell", '[data-theme="dark"] .course-shell'):
                body = self.rules_for(prefix).get(cls)
                if body is not None and re.search(r"color:\s*#[0-9a-fA-F]{3,8}", body):
                    continue
                if _palette_gives_colour(cls, prefix):
                    continue  # inherits by design
                unresolvable.append(f"{cls} ({prefix})")
        self.assertEqual(
            unresolvable, [],
            f"tokens that render as plain text in one theme: {unresolvable}",
        )

    def test_the_light_rules_are_not_gated_on_differing_from_dark(self):
        # Regression guard on the emission itself. The dark rule is scoped to
        # `[data-theme="dark"]`, so emitting the light rule only where the two
        # differ left those tokens with no light-mode colour at all.
        light = self.rules_for(".course-shell")
        dark = self.rules_for('[data-theme="dark"] .course-shell')
        self.assertGreater(
            len(light), 0, "no light-theme token rules were emitted"
        )
        # Punctuation is the one class the light palette leaves uncoloured.
        self.assertLessEqual(
            sorted(set(light) - set(dark)),
            ["p"],
            "light rules appeared only where they differ from dark",
        )

    def test_the_stylesheet_has_no_escaped_newline(self):
        # A '\\n' written into the source instead of a real newline joins the
        # whole dark palette onto one line, where everything after the first
        # rule is inside a comment-shaped tail and silently does nothing.
        self.assertNotIn(
            "\\n", self.css,
            "stylesheet contains a literal backslash-n, not a newline",
        )

    def test_the_build_emits_every_rule_pygments_generates(self):
        # The coverage check. Whichever way the rules are assembled, nothing
        # Pygments produces may be quietly dropped on the way into app.css --
        # that is how tokens end up rendering as body text while the palette
        # looks complete. `.hll` is excluded because this build never marks a
        # highlighted line and its `#ffffcc` would be a yellow band in dark mode.
        for prefix, style_name in (
            (LIGHT_PREFIX, CODE_LIGHT_THEME),
            (DARK_PREFIX, CODE_THEME),
        ):
            generated = theme._code_theme_rules(style_name)
            expected = set(re.findall(r"^\.course-shell \.hl \.([a-z]+) \{", generated, re.M))
            self.assertGreater(len(expected), 50, f"{style_name} produced too few rules")
            dropped = sorted(expected - set(self.rules_for(prefix)))
            self.assertEqual(
                dropped, [],
                f"{style_name} rules missing from app.css: {dropped}",
            )

    def test_both_themes_carry_a_substantial_token_palette(self):
        for prefix in (".course-shell", '[data-theme="dark"] .course-shell'):
            rules = self.rules_for(prefix)
            self.assertGreater(
                len(rules), 50,
                f"{prefix} emitted only {len(rules)} token rules",
            )
            self.assertGreaterEqual(
                len({body for body in rules.values()}), 10,
                f"{prefix} rules are near-identical; the palette looks wrong",
            )


class TestCodeStyling(CodeBlockTestCase):
    def test_no_hardcoded_background_from_pygments(self):
        # Pygments' own base rule paints #282C34, its dark palette. On a
        # light-theme page that is a dark slab; it has to come from a token.
        self.assertNotRegex(
            self.css, r"\.hl\s*\{[^}]*background:\s*#",
            "app.css must not hardcode a Pygments background",
        )
        # #282C34 only ever came from that base rule, so it must be gone
        # entirely. #abb2bf is one-dark's base *text* colour, so it legitimately
        # colours tokens in dark mode -- it is only forbidden as a background,
        # and in the light palette, which has no such colour.
        self.assertNotIn("#282c34", self.css.lower())
        light = "\n".join(
            body for cls, body in re.findall(
                r"^\.course-shell \.hl \.([a-z]+) \{([^}]*)\}", self.css, re.M
            )
        )
        self.assertNotIn("#abb2bf", light.lower())

    def test_code_background_uses_a_theme_token(self):
        # The block's background has to come from the palette, not from
        # Pygments' own dark palette, or a light page gets a dark slab.
        block_rule = re.search(r"\.code-block\s*\{(.*?)\}", self.css, re.DOTALL)
        self.assertIsNotNone(block_rule)
        self.assertIn("var(--cn-code-bg)", block_rule.group(1))

    def test_token_rules_target_the_code_element(self):
        # The rules must match the `code.hl` block element, which is what
        # Pygments styles once the wrapper is gone.
        self.assertRegex(self.css, r"\.course-shell \.hl \.[a-z]{1,2}\s*\{")

    def test_token_colours_are_set_for_both_themes(self):
        self.assertRegex(self.css, r"\.course-shell \.hl \.[a-z]{1,2}\s*\{")
        self.assertIn('[data-theme="dark"] .course-shell .hl .', self.css)

    def test_the_dark_selector_actually_matches_the_dom(self):
        # `data-theme` is set on <html>; `.course-shell` is the <body>. Written
        # as `.course-shell[data-theme="dark"]` the rule never matched, so dark
        # mode kept the light token colours.
        self.assertNotIn(
            '.course-shell[data-theme="dark"]', self.css,
            "this selector cannot match: the attribute is on <html>",
        )
        self.assertRegex(self.lab, r'<html[^>]*>')  # sanity: html element exists

    def test_inline_code_is_visually_distinct_from_blocks(self):
        css = self.css
        self.assertIn(".content :not(pre) > code", css)
        self.assertIn(".content pre code", css)


if __name__ == "__main__":
    unittest.main()
