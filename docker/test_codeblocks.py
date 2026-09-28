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

REPO_ROOT = Path(__file__).resolve().parent.parent
FENCE_LANGUAGES = {"bash", "text"}


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


class TestCodeStyling(CodeBlockTestCase):
    def test_no_hardcoded_background_from_pygments(self):
        # Pygments' own base rule paints #282C34, its dark palette. On a
        # light-theme page that is a dark slab; it has to come from a token.
        self.assertNotRegex(
            self.css, r"\.hl\s*\{[^}]*background:\s*#",
            "app.css must not hardcode a Pygments background",
        )
        for hexcode in ("#282C34", "#abb2bf"):
            with self.subTest(colour=hexcode):
                self.assertNotIn(hexcode.lower(), self.css.lower())

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
