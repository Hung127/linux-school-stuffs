"""Tests for build_site.py — the build step that assembles the course-notes site.

Run with:
    python -m unittest discover -s docker -v

Requires: markdown-it-py, mdit-py-plugins
"""

import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import build_site  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent

README_SOURCE = """\
# Course Notes

Some intro text.

## Contents

- [Log analysis](#log-analysis)

## Log analysis

| Path | What it is |
|---|---|
| `slides/` | decks |

```bash
awk '{print $1}' access.log | sort | uniq -c
```

See the [decks](slides/1_linux_architecture.html) and the
[lab folder](labs/lab01/).
"""

REPORT_SOURCE = """\
# Lab01

## Environment

![A screenshot](screenshots/lab1_1.png)
"""


def make_fixture_repo(root: Path) -> None:
    """Build a small synthetic repo that mirrors the real one's shape."""
    (root / "slides").mkdir(parents=True)
    (root / "labs" / "lab01" / "screenshots").mkdir(parents=True)
    (root / "seminar").mkdir()
    (root / "books").mkdir()
    (root / ".git").mkdir()
    (root / "docker").mkdir()
    (root / "notes").mkdir()

    (root / "README.md").write_text(README_SOURCE, encoding="utf-8")
    (root / "syllabus.html").write_text("<h1>syllabus</h1>", encoding="utf-8")
    (root / "slides" / "1_linux_architecture.html").write_text(
        "<h1>deck</h1>", encoding="utf-8"
    )
    (root / "labs" / "lab01" / "report.md").write_text(REPORT_SOURCE, encoding="utf-8")
    (root / "labs" / "lab01" / "report.pdf").write_bytes(b"%PDF-1.4 fake")
    (root / "labs" / "lab01" / "access.log").write_text("203.0.113.88 - -\n", encoding="utf-8")
    (root / "labs" / "lab01" / "screenshots" / "lab1_1.png").write_bytes(b"\x89PNG fake")
    (root / "seminar" / "de_tai_seminar.md").write_text("# Topics\n", encoding="utf-8")
    (root / "notes" / "extra.md").write_text("# Stray\n", encoding="utf-8")
    (root / "books" / "textbook.pdf").write_bytes(b"%PDF-1.4 copyrighted")
    (root / ".git" / "config").write_text("[core]\n", encoding="utf-8")
    (root / "docker" / "Dockerfile").write_text("FROM alpine\n", encoding="utf-8")
    (root / ".gitignore").write_text("books/\n", encoding="utf-8")
    (root / ".dockerignore").write_text("books/\n.git/\n", encoding="utf-8")
    (root / ".env").write_text("SECRET=hunter2\n", encoding="utf-8")
    (root / "Dockerfile").write_text("FROM python:3-alpine\n", encoding="utf-8")

    # A virtualenv, the shape of leak that motivated the exclusion rules.
    (root / ".venv" / "lib" / "python3.12").mkdir(parents=True)
    (root / ".venv" / "lib" / "python3.12" / "thing.py").write_text("# venv\n", encoding="utf-8")

    # Bytecode caches appear at any depth, not just the top level.
    (root / "labs" / "lab01" / "__pycache__").mkdir()
    (root / "labs" / "lab01" / "__pycache__" / "report.cpython.pyc").write_bytes(b"\x00")


class BuildSiteTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="build-site-test-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.src = self.tmp / "src"
        self.out = self.tmp / "out"
        self.src.mkdir()
        make_fixture_repo(self.src)

    def read(self, relative: str) -> str:
        return (self.out / relative).read_text(encoding="utf-8")


class TestStaticCopy(BuildSiteTest):
    def test_copies_static_files_into_out(self):
        build_site.build(self.src, self.out)

        self.assertTrue((self.out / "syllabus.html").is_file())
        self.assertTrue((self.out / "slides" / "1_linux_architecture.html").is_file())
        self.assertTrue((self.out / "labs" / "lab01" / "report.pdf").is_file())
        self.assertTrue((self.out / "labs" / "lab01" / "screenshots" / "lab1_1.png").is_file())

    def test_copies_the_lab_dataset_so_report_commands_still_run(self):
        build_site.build(self.src, self.out)

        self.assertTrue((self.out / "labs" / "lab01" / "access.log").is_file())

    def test_excludes_books_directory(self):
        build_site.build(self.src, self.out)

        self.assertFalse((self.out / "books").exists())

    def test_excludes_git_directory(self):
        build_site.build(self.src, self.out)

        self.assertFalse((self.out / ".git").exists())

    def test_excludes_docker_build_inputs(self):
        build_site.build(self.src, self.out)

        self.assertFalse((self.out / "docker").exists())

    def test_excludes_repo_plumbing_files(self):
        build_site.build(self.src, self.out)

        self.assertFalse((self.out / ".gitignore").exists())
        self.assertFalse((self.out / ".dockerignore").exists())

    def test_excludes_hidden_directories_at_the_top_level(self):
        build_site.build(self.src, self.out)

        self.assertFalse((self.out / ".venv").exists())

    def test_excludes_hidden_entries_the_code_has_never_heard_of(self):
        # The point of a rule over a list: .env is not on any exclusion list,
        # so this only passes if the rule matches the pattern itself.
        build_site.build(self.src, self.out)

        self.assertFalse((self.out / ".env").exists())

    def test_excludes_the_dockerfile_from_the_published_site(self):
        build_site.build(self.src, self.out)

        self.assertFalse((self.out / "Dockerfile").exists())

    def test_excludes_bytecode_caches_below_the_top_level(self):
        # __pycache__ does not start with a dot, so the hidden-entry rule does
        # not cover it -- the named exclusions have to apply at any depth.
        build_site.build(self.src, self.out)

        self.assertFalse((self.out / "labs" / "lab01" / "__pycache__").exists())

    def test_excluding_a_cache_does_not_drop_its_sibling(self):
        build_site.build(self.src, self.out)

        self.assertTrue((self.out / "labs" / "lab01" / "access.log").is_file())


class TestMarkdownRendering(BuildSiteTest):
    def test_renders_readme_as_root_index(self):
        build_site.build(self.src, self.out)

        self.assertIn("<h1", self.read("index.html"))

    def test_renders_report_beside_its_screenshots(self):
        build_site.build(self.src, self.out)

        self.assertIn('src="screenshots/lab1_1.png"', self.read("labs/lab01/index.html"))

    def test_renders_seminar_topics_as_a_page(self):
        build_site.build(self.src, self.out)

        self.assertIn("<h1", self.read("seminar/index.html"))

    def test_renders_gfm_tables(self):
        build_site.build(self.src, self.out)

        self.assertIn("<table>", self.read("index.html"))

    def test_adds_heading_anchors_for_the_hand_written_toc(self):
        build_site.build(self.src, self.out)

        self.assertIn('id="log-analysis"', self.read("index.html"))

    def test_omits_markdown_sources_that_were_rendered(self):
        build_site.build(self.src, self.out)

        self.assertFalse((self.out / "README.md").exists())
        self.assertFalse((self.out / "labs" / "lab01" / "report.md").exists())
        self.assertFalse((self.out / "seminar" / "de_tai_seminar.md").exists())

    def test_keeps_markdown_files_that_were_not_rendered(self):
        build_site.build(self.src, self.out)

        self.assertTrue((self.out / "notes" / "extra.md").is_file())


class TestHtmlShell(BuildSiteTest):
    def test_wraps_pages_in_a_full_html_document(self):
        build_site.build(self.src, self.out)

        page = self.read("index.html")
        self.assertTrue(page.startswith("<!DOCTYPE html>"))
        self.assertIn('<meta charset="utf-8">', page)
        self.assertIn("</html>", page)

    def test_gives_each_page_its_own_title(self):
        build_site.build(self.src, self.out)

        self.assertIn("<title>", self.read("index.html"))
        self.assertIn("<title>", self.read("labs/lab01/index.html"))


class TestIdempotence(BuildSiteTest):
    def test_removes_stale_output_from_a_previous_build(self):
        self.out.mkdir()
        (self.out / "stale.html").write_text("old", encoding="utf-8")

        build_site.build(self.src, self.out)

        self.assertFalse((self.out / "stale.html").exists())


class TestOutputInsideSource(BuildSiteTest):
    def test_does_not_recurse_when_output_nests_inside_source(self):
        # `build_site.py . out` is the natural thing to type locally, and it
        # would otherwise copy the output directory into itself.
        nested = self.src / "out"

        build_site.build(self.src, nested)

        self.assertTrue((nested / "index.html").is_file())
        self.assertFalse((nested / "out").exists())


class TestRealRepo(unittest.TestCase):
    """Contract checks against the actual repository content."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.tmp = Path(tempfile.mkdtemp(prefix="build-site-real-"))
        cls.out = cls.tmp / "out"
        build_site.build(REPO_ROOT, cls.out)

    @classmethod
    def tearDownClass(cls) -> None:
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_readme_becomes_the_landing_page(self):
        page = (self.out / "index.html").read_text(encoding="utf-8")
        self.assertIn("Linux Operating System", page)

    def test_every_readme_toc_anchor_resolves(self):
        page = (self.out / "index.html").read_text(encoding="utf-8")
        for anchor in ("whats-in-here", "repository-layout", "log-analysis",
                       "finding-and-inspecting-files", "command-cheat-sheet",
                       "links-and-inodes", "the-web-version", "contributing"):
            with self.subTest(anchor=anchor):
                self.assertIn(f'id="{anchor}"', page)

    def test_readme_renders_its_tables(self):
        page = (self.out / "index.html").read_text(encoding="utf-8")
        self.assertIn("<table>", page)

    def test_all_four_slide_decks_are_served(self):
        for name in ("1_linux_architecture", "2_cli-text-processing",
                     "3_users-permissions", "4-software-storage-tasks"):
            with self.subTest(deck=name):
                self.assertTrue((self.out / "slides" / f"{name}.html").is_file())

    def test_lab_report_renders_with_all_twenty_screenshots(self):
        page = (self.out / "labs" / "lab01" / "index.html").read_text(encoding="utf-8")
        self.assertEqual(page.count("<img"), 20)

    def test_books_are_not_published(self):
        self.assertFalse((self.out / "books").exists())

    def test_readme_test_count_is_accurate(self):
        # The README quotes a test count; it must not drift from reality.
        readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        match = re.search(r"(\d+) tests, run against", readme)
        self.assertIsNotNone(match, "README should state a test count")

        # Counting by walking the loaded suite rather than by grepping for
        # `def test_`, so subTest variants and inherited cases are counted too.
        suite = unittest.TestLoader().discover(
            str(REPO_ROOT / "docker"),
            pattern="test_*.py",
            top_level_dir=str(REPO_ROOT / "docker"),
        )
        self.assertEqual(
            int(match.group(1)),
            suite.countTestCases(),
            "the README's test count is out of date",
        )

    def test_readme_documents_the_real_dockerfile(self):
        # The web-version section quotes the Dockerfile to explain layer order.
        # A paraphrased copy drifts from the real file and quietly documents a
        # Dockerfile nobody builds.
        readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        block = re.search(r"```dockerfile\n(.*?)```", readme, re.DOTALL)
        self.assertIsNotNone(block, "README has no ```dockerfile block")
        actual = (REPO_ROOT / "Dockerfile").read_text(encoding="utf-8")
        self.assertEqual(
            block.group(1).strip(),
            actual.strip(),
            "the README's Dockerfile block no longer matches the real Dockerfile",
        )


if __name__ == "__main__":
    unittest.main()
