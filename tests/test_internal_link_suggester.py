"""Tests for internal-link-suggester. Run with:

    python -m unittest discover -s tests -v
"""

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from internal_link_suggester.extract import extract_page, parse_sitemap
from internal_link_suggester.suggest import (
    Page,
    build_suggestions,
    find_orphans,
    render_json,
    render_markdown,
)
from internal_link_suggester.text import normalize_persian, tokenize
from internal_link_suggester.tfidf import cosine_similarity, tfidf_vectors

DEMO = Path(__file__).resolve().parents[1] / "examples" / "demo-site"


def make_page(url: str, title: str, text: str) -> Page:
    return Page(url=url, title=title, text=text, tokens=tokenize(f"{title} {text}"))


class TestTokenize(unittest.TestCase):
    def test_english_stopwords_dropped(self):
        tokens = tokenize("The quick brown fox jumps over the lazy dog")
        self.assertNotIn("the", tokens)
        self.assertIn("quick", tokens)
        self.assertIn("fox", tokens)

    def test_persian_normalization(self):
        # Arabic Yeh/Kaf map to Persian forms, so both spellings match.
        self.assertEqual(tokenize("كتابخانه"), tokenize("کتابخانه"))

    def test_persian_stopwords_dropped(self):
        tokens = tokenize("این کتاب درباره سئو و لینک سازی است")
        self.assertNotIn("این", tokens)
        self.assertNotIn("و", tokens)
        self.assertIn("سئو", tokens)

    def test_digits_dropped(self):
        self.assertNotIn("2026", tokenize("guide 2026 edition"))


class TestTfidf(unittest.TestCase):
    def test_identical_docs_similarity_one(self):
        docs = [["coffee", "brewing", "guide"], ["coffee", "brewing", "guide"]]
        a, b = tfidf_vectors(docs)
        self.assertAlmostEqual(cosine_similarity(a, b), 1.0, places=6)

    def test_unrelated_docs_similarity_zero(self):
        docs = [["coffee", "brewing"], ["quantum", "entanglement"]]
        a, b = tfidf_vectors(docs)
        self.assertAlmostEqual(cosine_similarity(a, b), 0.0, places=6)

    def test_shared_rare_term_beats_shared_common_term(self):
        docs = [
            ["coffee", "espresso", "machine"],
            ["coffee", "espresso", "grinder"],
            ["coffee", "morning", "routine"],
        ]
        a, b, c = tfidf_vectors(docs)
        self.assertGreater(cosine_similarity(a, b), cosine_similarity(a, c))


class TestExtract(unittest.TestCase):
    def test_extract_skips_script_and_nav(self):
        html = """<html><head><title>Pour Over Guide</title>
        <style>.x{color:red}</style></head><body>
        <nav>Home About</nav><h1>Pour Over Coffee</h1>
        <p>Grind beans medium-fine and bloom the grounds.</p>
        <script>var x = 1;</script></body></html>"""
        page = extract_page("https://example.com/pour-over", html)
        self.assertEqual(page.title, "Pour Over Guide")
        self.assertIn("Pour Over Coffee", page.headings)
        self.assertIn("Grind beans", page.text)
        self.assertNotIn("Home About", page.text)
        self.assertNotIn("var x", page.text)

    def test_parse_sitemap(self):
        xml = """<?xml version="1.0" encoding="UTF-8"?>
        <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
        <url><loc>https://example.com/a</loc></url>
        <url><loc>https://example.com/b</loc></url></urlset>"""
        self.assertEqual(parse_sitemap(xml), ["https://example.com/a", "https://example.com/b"])


class TestSuggest(unittest.TestCase):
    def setUp(self):
        self.pages = [
            make_page("https://example.com/pour-over", "Pour Over Guide",
                      "Pour over coffee brewing with a dripper, paper filter and gooseneck kettle. Grind medium fine."),
            make_page("https://example.com/french-press", "French Press Guide",
                      "French press coffee brewing with immersion, coarse grind and a metal filter plunger."),
            make_page("https://example.com/grinder", "Coffee Grinder Guide",
                      "A burr grinder gives consistent grind size for pour over and french press brewing."),
            make_page("https://example.com/astronomy", "Stargazing Basics",
                      "Telescope astronomy guide to constellations and planets in the night sky."),
        ]

    def test_coffee_pages_link_each_other_not_astronomy(self):
        suggestions = build_suggestions(self.pages, top_n=2, min_score=0.05)
        by_source = {}
        for s in suggestions:
            by_source.setdefault(s.source_url, []).append(s.target_url)
        pour_over = by_source["https://example.com/pour-over"]
        self.assertIn("https://example.com/french-press", pour_over)
        self.assertIn("https://example.com/grinder", pour_over)
        self.assertNotIn("https://example.com/astronomy", pour_over)

    def test_astronomy_page_is_orphan(self):
        suggestions = build_suggestions(self.pages, top_n=2, min_score=0.05)
        orphans = find_orphans(self.pages, suggestions)
        self.assertEqual([p.url for p in orphans], ["https://example.com/astronomy"])

    def test_anchors_come_from_source_text(self):
        suggestions = build_suggestions(self.pages, top_n=1, min_score=0.05)
        for s in suggestions:
            source = next(p for p in self.pages if p.url == s.source_url)
            for anchor in s.anchors:
                self.assertIn(anchor, source.tokens)

    def test_near_duplicates_are_not_suggested(self):
        dupes = [
            make_page("https://example.com/a", "Guide", "coffee brewing pour over grinder beans"),
            make_page("https://example.com/b", "Guide", "coffee brewing pour over grinder beans"),
            make_page("https://example.com/c", "Other", "coffee brewing french press kettle"),
        ]
        suggestions = build_suggestions(dupes, top_n=2, min_score=0.01)
        pairs = {(s.source_url, s.target_url) for s in suggestions}
        self.assertNotIn(("https://example.com/a", "https://example.com/b"), pairs)

    def test_single_page_yields_nothing(self):
        self.assertEqual(build_suggestions(self.pages[:1]), [])


class TestDemoSiteEndToEnd(unittest.TestCase):
    def test_demo_site_produces_real_suggestions(self):
        from internal_link_suggester.extract import extract_page as ep

        pages = []
        for path in sorted(DEMO.glob("*.html")):
            pages.append(Page.from_extracted(ep(f"https://demo.example/{path.name}", path.read_text())))
        suggestions = build_suggestions(pages, top_n=3, min_score=0.05)
        orphans = find_orphans(pages, suggestions)
        # Every coffee page links out; two pages receive no inbound
        # suggestion: astronomy (off-topic) and beans (under-linked --
        # it ranks 4th for every other page, so top-3 never picks it).
        # That is a real finding, not a bug: the beans page needs
        # stronger topical overlap to earn internal links.
        self.assertEqual(len(suggestions), 21)
        self.assertEqual(
            sorted(p.url for p in orphans),
            ["https://demo.example/astronomy.html", "https://demo.example/beans.html"],
        )
        md = render_markdown(pages, suggestions, orphans)
        self.assertIn("Internal-link suggestions", md)
        data = json.loads(render_json(pages, suggestions, orphans))
        self.assertEqual(data["pages"], len(pages))
        self.assertEqual(data["suggestions"], len(suggestions))


if __name__ == "__main__":
    unittest.main()
