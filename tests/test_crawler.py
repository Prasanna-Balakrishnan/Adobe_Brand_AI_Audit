#!/usr/bin/env python3
"""
test_crawler.py — Dedicated unit tests for site crawler generalization,
page classification, and page importance scoring.
"""

import unittest
from bs4 import BeautifulSoup
from pathlib import Path
import sys

# Ensure site-crawler script can be loaded
REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT / "skills" / "site-crawler" / "scripts"))

import importlib.util
spec = importlib.util.spec_from_file_location("crawl", REPO_ROOT / "skills" / "site-crawler" / "scripts" / "crawl.py")
crawl_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(crawl_mod)


class TestPageTypeClassification(unittest.TestCase):
    """Tests for classify_page_type() and backward compatibility of detect_page_type()."""

    def test_homepage_detection(self):
        urls = [
            ("https://example.com", "https://example.com"),
            ("https://example.com/", "https://example.com/"),
            ("https://example.com/index.html", "https://example.com"),
            ("https://example.com/home", "https://example.com"),
            ("https://example.com/subpath", "https://example.com/subpath")  # start_url match
        ]
        for url, start_url in urls:
            ptype, conf = crawl_mod.classify_page_type(url=url, start_url=start_url)
            self.assertEqual(ptype, "Homepage", f"Expected Homepage for {url}")
            self.assertEqual(conf, "high")

    def test_schema_org_classification(self):
        test_cases = [
            ([{"@type": "JobPosting"}], "Careers"),
            ([{"@type": "Event"}], "Event"),
            ([{"@type": "BlogPosting"}], "Blog/article"),
            ([{"@type": "Article"}], "Blog/article"),
            ([{"@type": "NewsArticle"}], "Blog/article"),
            ([{"@type": "Product"}], "Product"),
            ([{"@type": "IndividualProduct"}], "Product"),
            ([{"@type": "Service"}], "Service"),
            ([{"@type": "AboutPage"}], "About"),
            ([{"@type": "ContactPage"}], "Contact"),
            ([{"@type": "TechArticle"}], "Documentation"),
            ([{"@type": "APIReference"}], "Documentation"),
            ([{"@graph": [{"@type": "JobPosting"}]}], "Careers"),
        ]
        for blocks, expected_type in test_cases:
            ptype, conf = crawl_mod.classify_page_type(
                url="https://example.com/generic-page",
                json_ld_blocks=blocks
            )
            self.assertEqual(ptype, expected_type, f"Failed for Schema.org {blocks}")
            self.assertEqual(conf, "high")

    def test_standard_url_and_title_classification(self):
        cases = [
            ("https://example.com/about", "About Us", ["Who We Are"], "About"),
            ("https://example.com/contact-us", "Contact Support", ["Get in Touch"], "Contact"),
            ("https://example.com/pricing", "Pricing & Plans", ["Simple Pricing"], "Pricing"),
            ("https://example.com/careers", "Careers", ["Open Positions"], "Careers"),
            ("https://example.com/docs/api", "API Documentation", ["Developer Guide"], "Documentation"),
            ("https://example.com/webinars", "Upcoming Webinars", ["Join Event"], "Event"),
            ("https://example.com/blog/ai-trends", "AI Trends", ["Latest News"], "Blog/article"),
        ]
        for url, title, h1s, expected in cases:
            ptype, conf = crawl_mod.classify_page_type(
                url=url,
                title=title,
                h1_list=h1s
            )
            self.assertEqual(ptype, expected, f"Failed for {url}")
            self.assertIn(conf, ("high", "medium"))

    def test_multilingual_non_english_content_signals(self):
        # Non-English path without English URL keywords, but rich content signals
        # 1. Czech/Polish About page: /o-nas
        about_text = "Společnost byla založena v roce 2015. Our mission and core values guide our leadership team and who we are."
        ptype, conf = crawl_mod.classify_page_type(
            url="https://example.com/o-nas",
            title="O nás",
            visible_text=about_text
        )
        self.assertEqual(ptype, "About")

        # 2. French Pricing page: /tarifs
        pricing_text = "Choisissez votre formule: $29 per month billed annually. Free trial available, cancel anytime."
        ptype, conf = crawl_mod.classify_page_type(
            url="https://example.com/tarifs",
            title="Nos Tarifs",
            visible_text=pricing_text
        )
        self.assertEqual(ptype, "Pricing")

        # 3. German Careers page: /karriere
        careers_text = "Offene Stellen: we're hiring! Check our open positions and benefits, competitive salary, apply now."
        ptype, conf = crawl_mod.classify_page_type(
            url="https://example.com/karriere",
            title="Karriere bei uns",
            visible_text=careers_text
        )
        self.assertEqual(ptype, "Careers")

    def test_fallback_to_other_unknown(self):
        ptype, conf = crawl_mod.classify_page_type(
            url="https://example.com/misc/random-page-12345",
            title="Random Page",
            h1_list=["Random Content"],
            visible_text="Lorem ipsum dolor sit amet, consectetur adipiscing elit."
        )
        self.assertEqual(ptype, "Other/unknown")
        self.assertEqual(conf, "low")

    def test_detect_page_type_backward_compatibility(self):
        soup = BeautifulSoup("<html><body><h1>Contact Us</h1><p>Send a message</p></body></html>", "html.parser")
        res = crawl_mod.detect_page_type(
            url="https://example.com/support",
            start_url="https://example.com",
            title="Support",
            h1_list=["Contact Us"],
            headings=[{"level": 1, "text": "Contact Us"}],
            json_ld_blocks=[],
            soup=soup
        )
        self.assertIsInstance(res, str)
        self.assertEqual(res, "Contact")


class TestPageImportanceScore(unittest.TestCase):
    """Tests for compute_page_importance_scores() graph calculations."""

    def test_link_frequency_scoring(self):
        # 4-page site:
        # Home links to About, Pricing, and Blog
        # About links to Home
        # Blog links to Home and Pricing
        # Pricing has 2 incoming links, About has 1, Home has 2
        pages = [
            {
                "url": "https://example.com/",
                "page_type": "Homepage",
                "nav_link_texts": ["About", "Pricing", "Blog"],
                "links": [
                    {"href": "https://example.com/about", "is_internal": True, "text": "About"},
                    {"href": "https://example.com/pricing", "is_internal": True, "text": "Pricing"},
                    {"href": "https://example.com/blog", "is_internal": True, "text": "Blog"},
                ]
            },
            {
                "url": "https://example.com/about",
                "page_type": "About",
                "nav_link_texts": [],
                "links": [
                    {"href": "https://example.com/", "is_internal": True, "text": "Home"}
                ]
            },
            {
                "url": "https://example.com/pricing",
                "page_type": "Pricing",
                "nav_link_texts": [],
                "links": []
            },
            {
                "url": "https://example.com/blog",
                "page_type": "Blog/article",
                "nav_link_texts": [],
                "links": [
                    {"href": "https://example.com/", "is_internal": True, "text": "Home"},
                    {"href": "https://example.com/pricing", "is_internal": True, "text": "Pricing Plans"}
                ]
            },
            {
                "url": "https://example.com/isolated-orphan",
                "page_type": "Other/unknown",
                "nav_link_texts": [],
                "links": []
            }
        ]

        scored = crawl_mod.compute_page_importance_scores(pages)
        self.assertEqual(len(scored), 5)

        by_url = {p["url"]: p for p in scored}

        # Pricing was linked from 2 pages (Home and Blog), and linked from nav -> high score
        self.assertEqual(by_url["https://example.com/pricing"]["incoming_link_count"], 2)
        # Isolated page has 0 incoming links -> low score
        self.assertEqual(by_url["https://example.com/isolated-orphan"]["incoming_link_count"], 0)

        # All scores normalized between 0 and 100
        for p in scored:
            self.assertGreaterEqual(p["page_importance_score"], 0)
            self.assertLessEqual(p["page_importance_score"], 100)

        # Homepage and high-incoming nav pages score higher than orphan page
        self.assertGreater(by_url["https://example.com/"]["page_importance_score"],
                           by_url["https://example.com/isolated-orphan"]["page_importance_score"])
        self.assertGreater(by_url["https://example.com/pricing"]["page_importance_score"],
                           by_url["https://example.com/isolated-orphan"]["page_importance_score"])


class TestUrlPriority(unittest.TestCase):
    """Tests for score_url_priority() with generalized PAGE_TYPE_SIGNALS."""

    def test_hierarchy_preservation(self):
        s_home, _ = crawl_mod.score_url_priority("https://example.com/", depth=0)
        s_about, _ = crawl_mod.score_url_priority("https://example.com/about", link_text="About Us", depth=1)
        s_contact, _ = crawl_mod.score_url_priority("https://example.com/contact", link_text="Contact Us", depth=1)
        s_prod, _ = crawl_mod.score_url_priority("https://example.com/products", link_text="Our Products", depth=1)
        s_pricing, _ = crawl_mod.score_url_priority("https://example.com/pricing", link_text="Pricing Plans", depth=1)
        s_docs, _ = crawl_mod.score_url_priority("https://example.com/docs", link_text="Documentation", depth=1)
        s_careers, _ = crawl_mod.score_url_priority("https://example.com/careers", link_text="Join our team", depth=1)
        s_events, _ = crawl_mod.score_url_priority("https://example.com/events", link_text="Upcoming Conferences", depth=1)
        s_hub, _ = crawl_mod.score_url_priority("https://example.com/blog", link_text="Blog", depth=1)
        s_rep, _ = crawl_mod.score_url_priority("https://example.com/community", link_text="Community", depth=1)
        s_leaf, _ = crawl_mod.score_url_priority("https://example.com/blog/2026/01/post-one", link_text="Post One", depth=2)
        s_deep, _ = crawl_mod.score_url_priority("https://example.com/tag/ai/page/2", link_text="Page 2", depth=3)

        self.assertGreater(s_home, s_about)
        self.assertGreater(s_about, s_contact)
        self.assertGreater(s_contact, s_prod)
        self.assertGreater(s_prod, s_pricing)
        self.assertGreater(s_pricing, s_docs)
        self.assertGreater(s_docs, s_careers)
        self.assertGreater(s_careers, s_events)
        self.assertGreater(s_events, s_hub)
        self.assertGreater(s_hub, s_rep)
        self.assertGreater(s_rep, s_leaf)
        self.assertGreater(s_leaf, s_deep)

    def test_anchor_text_prioritization_for_unknown_path(self):
        # Even if path is non-descriptive, strong nav anchor text boosts priority
        score, cat = crawl_mod.score_url_priority("https://example.com/x123", link_text="Pricing & Plans", depth=1)
        self.assertEqual(score, 75)
        self.assertEqual(cat, "Pricing")

        score_c, cat_c = crawl_mod.score_url_priority("https://example.com/info-hub", link_text="Contact Us", depth=1)
        self.assertEqual(score_c, 85)
        self.assertEqual(cat_c, "Contact")


if __name__ == "__main__":
    unittest.main()
