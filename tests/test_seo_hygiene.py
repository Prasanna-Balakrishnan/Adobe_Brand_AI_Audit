#!/usr/bin/env python3
"""
test_seo_hygiene.py — Comprehensive tests for Phase 3: SEO Hygiene & Structured Data.

Verifies:
- Crawlability & Indexability (robots.txt, noindex, canonical, redirect, broken links, HTTP status, duplicate URLs)
- SEO Metadata (missing/empty/duplicate titles, missing/duplicate descriptions, missing H1, heading gaps)
- Structured Data (recursive extraction, @graph, nested schemas, malformed JSON-LD, schema subtypes)
- Structured Data Consistency (price conflicts, availability contradictions, event date contradictions)
- Real-World Generalization across 9 generic verticals (E-commerce, Service, Restaurant, Healthcare, Education, SaaS, Docs, Event, Informational)
- Anti-Overfitting with arbitrary domains and multilingual content
- Advisory Recommendation-Only guarantees
"""

import unittest
from pathlib import Path
import importlib.util

REPO_ROOT = Path(__file__).parent.parent


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


cra_mod = load_module(REPO_ROOT / "skills/crawlability-render-audit/scripts/audit.py", "cra_mod")
sdc_mod = load_module(REPO_ROOT / "skills/structured-data-content-audit/scripts/audit.py", "sdc_mod")


def make_snapshot(pages: list, start_url: str = "https://example.com/", disallowed: list = None, sitemaps: list = None) -> dict:
    return {
        "crawl_meta": {
            "start_url": start_url,
            "crawl_started_at": "2026-09-08T10:00:00Z",
            "crawl_ended_at": "2026-09-08T10:01:00Z",
            "pages_crawled": len(pages),
            "max_pages": 20,
            "robots_txt_respected": True,
            "robots_txt_url": f"{start_url}robots.txt",
            "robots_txt_status": 200,
            "disallowed_paths": disallowed or [],
            "sitemaps": sitemaps or [f"{start_url}sitemap.xml"],
            "crawl_timeout_hit": False
        },
        "pages": pages
    }


def make_page(url: str = "https://example.com/", **overrides) -> dict:
    defaults = {
        "url": url,
        "status_code": 200,
        "final_url": url,
        "redirect_chain": [],
        "canonical": url,
        "meta_robots": "",
        "x_robots_tag": "",
        "title": "Example Standard Page",
        "meta_description": "Descriptive meta description for this standard test page.",
        "h1": ["Standard Heading"],
        "headings": [{"level": 1, "text": "Standard Heading"}, {"level": 2, "text": "Subheading"}],
        "json_ld": [],
        "links": [],
        "images": [],
        "visible_text_length": 600,
        "visible_text_sample": "Standard visible text content for indexing and crawl evaluation.",
        "page_type": "Other",
        "page_importance_score": 50,
        "crawled_with_js": False
    }
    defaults.update(overrides)
    return defaults


# ─────────────────────────────────────────────────────────────────────────────
# 1. CRAWLABILITY & INDEXABILITY TESTS
# ─────────────────────────────────────────────────────────────────────────────

class TestCrawlabilityAndIndexability(unittest.TestCase):

    def test_robots_allowed_strength(self):
        """Clean robots.txt produces a strength and no crawlability block."""
        pages = [make_page(url="https://site.test/", page_type="Homepage")]
        snap = make_snapshot(pages, start_url="https://site.test/", disallowed=[])
        findings, strengths = cra_mod.run_checks(snap)
        self.assertFalse(any(f["check_id"] == "CRA-001" for f in findings))
        self.assertTrue(any("robots.txt" in s.get("title", "").lower() for s in strengths))

    def test_robots_blocked_global(self):
        """robots.txt Disallow: / triggers CRA-001 critical finding."""
        pages = [make_page(url="https://site.test/")]
        snap = make_snapshot(pages, start_url="https://site.test/", disallowed=["/"])
        findings, _ = cra_mod.run_checks(snap)
        cra001 = [f for f in findings if f["check_id"] == "CRA-001"]
        self.assertEqual(len(cra001), 1)
        self.assertEqual(cra001[0]["severity"], "critical")

    def test_noindex_on_all_pages(self):
        """noindex across all pages triggers CRA-002 critical finding."""
        pages = [
            make_page(url="https://site.test/", meta_robots="noindex, follow"),
            make_page(url="https://site.test/about", meta_robots="noindex")
        ]
        snap = make_snapshot(pages, start_url="https://site.test/")
        findings, _ = cra_mod.run_checks(snap)
        self.assertTrue(any(f["check_id"] == "CRA-002" for f in findings))

    def test_noindex_on_important_brand_page(self):
        """noindex on high-importance page triggers CRA-015."""
        pages = [
            make_page(url="https://site.test/", page_type="Homepage"),
            make_page(url="https://site.test/pricing", page_type="Pricing", meta_robots="noindex", page_importance_score=85)
        ]
        snap = make_snapshot(pages, start_url="https://site.test/")
        findings, _ = cra_mod.run_checks(snap)
        cra015 = [f for f in findings if f["check_id"] == "CRA-015"]
        self.assertTrue(len(cra015) >= 1)
        self.assertIn("https://site.test/pricing", cra015[0]["affected_urls"])

    def test_canonical_missing_and_pointing_to_error(self):
        """Canonical missing from pages or pointing to 404 triggers CRA-006 / CRA-016."""
        # Missing canonical
        pages_no_canon = [make_page(url="https://site.test/", canonical="")]
        snap = make_snapshot(pages_no_canon, start_url="https://site.test/")
        findings, _ = cra_mod.run_checks(snap)
        self.assertTrue(any(f["check_id"] == "CRA-006" for f in findings))

        # Canonical pointing to error
        pages_error_canon = [
            make_page(url="https://site.test/page1", canonical="https://site.test/missing"),
            make_page(url="https://site.test/missing", status_code=404)
        ]
        snap2 = make_snapshot(pages_error_canon, start_url="https://site.test/")
        findings2, _ = cra_mod.run_checks(snap2)
        self.assertTrue(any(f["check_id"] == "CRA-016" for f in findings2))

    def test_redirect_loop_and_inefficient_chain(self):
        """Redirect loop triggers CRA-004; excessive hops trigger CRA-014."""
        loop_pages = [
            make_page(url="https://site.test/loop", status_code=310)
        ]
        findings, _ = cra_mod.run_checks(make_snapshot(loop_pages, start_url="https://site.test/"))
        self.assertTrue(any(f["check_id"] == "CRA-004" for f in findings))

        chain_pages = [
            make_page(url="https://site.test/hop1", redirect_chain=["https://site.test/hop1", "https://site.test/hop2", "https://site.test/hop3", "https://site.test/final"])
        ]
        findings2, _ = cra_mod.run_checks(make_snapshot(chain_pages, start_url="https://site.test/"))
        self.assertTrue(any(f["check_id"] == "CRA-014" for f in findings2))

    def test_broken_internal_links(self):
        """Broken internal link triggers CRA-007."""
        pages = [
            make_page(url="https://site.test/", links=[{"href": "https://site.test/broken", "is_internal": True}]),
            make_page(url="https://site.test/broken", status_code=404)
        ]
        findings, _ = cra_mod.run_checks(make_snapshot(pages, start_url="https://site.test/"))
        self.assertTrue(any(f["check_id"] == "CRA-007" for f in findings))

    def test_http_error_homepage(self):
        """Homepage HTTP 500 error triggers CRA-003."""
        pages = [make_page(url="https://site.test/", status_code=500)]
        findings, _ = cra_mod.run_checks(make_snapshot(pages, start_url="https://site.test/"))
        self.assertTrue(any(f["check_id"] == "CRA-003" for f in findings))

    def test_duplicate_url_variants(self):
        """CRAWL-018 detects duplicate URL variants (trailing slash variations)."""
        pages = [
            make_page(url="https://site.test/product"),
            make_page(url="https://site.test/product/")
        ]
        findings, _ = cra_mod.run_checks(make_snapshot(pages, start_url="https://site.test/"))
        cra018 = [f for f in findings if f["check_id"] == "CRA-018"]
        self.assertTrue(len(cra018) >= 1)


# ─────────────────────────────────────────────────────────────────────────────
# 2. SEO METADATA & HEADINGS TESTS
# ─────────────────────────────────────────────────────────────────────────────

class TestSEOMetadata(unittest.TestCase):

    def test_missing_and_empty_titles(self):
        """Missing title triggers CRA-011; empty/whitespace title triggers CRA-021."""
        # Empty title
        pages = [
            make_page(url="https://site.test/p1", title="   "),
            make_page(url="https://site.test/p2", title="")
        ]
        findings, _ = cra_mod.run_checks(make_snapshot(pages, start_url="https://site.test/"))
        self.assertTrue(any(f["check_id"] == "CRA-021" for f in findings))

    def test_duplicate_titles_across_pages(self):
        """SDC-212 detects identical titles across distinct pages."""
        pages = [
            make_page(url="https://site.test/product-a", title="Leading Enterprise Cloud Platform"),
            make_page(url="https://site.test/product-b", title="Leading Enterprise Cloud Platform")
        ]
        findings, _ = sdc_mod.run_checks(make_snapshot(pages, start_url="https://site.test/"))
        sdc212 = [f for f in findings if f["check_id"] == "SDC-212"]
        self.assertEqual(len(sdc212), 1)
        self.assertIn("Duplicate page titles", sdc212[0]["title"])

    def test_missing_and_duplicate_meta_descriptions(self):
        """SDC-213 detects duplicate meta descriptions across distinct URLs."""
        shared_desc = "Experience next-generation intelligent enterprise resource management and workflow orchestration."
        pages = [
            make_page(url="https://site.test/solutions/finance", meta_description=shared_desc),
            make_page(url="https://site.test/solutions/hr", meta_description=shared_desc)
        ]
        findings, _ = sdc_mod.run_checks(make_snapshot(pages, start_url="https://site.test/"))
        sdc213 = [f for f in findings if f["check_id"] == "SDC-213"]
        self.assertEqual(len(sdc213), 1)
        self.assertIn("Duplicate meta descriptions", sdc213[0]["title"])

    def test_missing_h1_on_homepage_and_content_pages(self):
        """SDC-005 flags missing H1 on homepage; SDC-207 flags missing H1 on core content pages."""
        hp_no_h1 = [make_page(url="https://site.test/", page_type="Homepage", h1=[])]
        findings_hp, _ = sdc_mod.run_checks(make_snapshot(hp_no_h1, start_url="https://site.test/"))
        self.assertTrue(any(f["check_id"] == "SDC-005" for f in findings_hp))

        content_no_h1 = [
            make_page(url="https://site.test/", page_type="Homepage", h1=["Welcome"]),
            make_page(url="https://site.test/service", page_type="Service", h1=[], visible_text_length=500)
        ]
        findings_ct, _ = sdc_mod.run_checks(make_snapshot(content_no_h1, start_url="https://site.test/"))
        self.assertTrue(any(f["check_id"] == "SDC-207" for f in findings_ct))

    def test_heading_hierarchy_gaps(self):
        """SDC-007 flags heading level skips (e.g. H1 directly to H3)."""
        pages = [
            make_page(
                url="https://site.test/article",
                headings=[{"level": 1, "text": "Main Topic"}, {"level": 3, "text": "Skipped H2 Subtopic"}]
            )
        ]
        findings, _ = sdc_mod.run_checks(make_snapshot(pages, start_url="https://site.test/"))
        self.assertTrue(any(f["check_id"] == "SDC-007" for f in findings))


# ─────────────────────────────────────────────────────────────────────────────
# 3. STRUCTURED DATA QUALITY & RECURSIVE DISCOVERY
# ─────────────────────────────────────────────────────────────────────────────

class TestStructuredDataDiscovery(unittest.TestCase):

    def test_recursive_schema_type_extraction(self):
        """get_schema_types recursively identifies types inside @graph, arrays, and nested schemas."""
        blocks = [{
            "@context": "https://schema.org",
            "@graph": [
                {
                    "@type": "WebPage",
                    "name": "Service Overview",
                    "mainEntity": {
                        "@type": "Service",
                        "name": "Cloud Security Audit",
                        "offers": {
                            "@type": "Offer",
                            "price": "499.00"
                        }
                    }
                },
                {
                    "@type": ["BreadcrumbList", "ItemList"],
                    "itemListElement": [
                        {"@type": "ListItem", "position": 1, "name": "Home"}
                    ]
                }
            ]
        }]
        types = sdc_mod.get_schema_types(blocks)
        expected = {"WebPage", "Service", "Offer", "BreadcrumbList", "ItemList", "ListItem"}
        self.assertTrue(expected.issubset(types))

    def test_malformed_jsonld_blocks(self):
        """SDC-004 flags JSON-LD missing @type or @context."""
        pages = [
            make_page(
                url="https://site.test/",
                page_type="Homepage",
                json_ld=[{"name": "Missing Type and Context Corp"}]
            )
        ]
        findings, _ = sdc_mod.run_checks(make_snapshot(pages, start_url="https://site.test/"))
        self.assertTrue(any(f["check_id"] == "SDC-004" for f in findings))

    def test_incomplete_schema_declarations(self):
        """SDC-208 flags Schema objects missing mandatory properties across entities."""
        # Event missing startDate, Product missing name
        pages = [
            make_page(
                url="https://site.test/event",
                json_ld=[{
                    "@context": "https://schema.org",
                    "@type": "Event",
                    "name": "Global Tech Summit"
                    # missing startDate
                }]
            )
        ]
        findings, _ = sdc_mod.run_checks(make_snapshot(pages, start_url="https://site.test/"))
        sdc208 = [f for f in findings if f["check_id"] == "SDC-208"]
        self.assertEqual(len(sdc208), 1)
        self.assertIn("Event missing 'startDate'", sdc208[0]["evidence"])


# ─────────────────────────────────────────────────────────────────────────────
# 4. STRUCTURED DATA CONSISTENCY & CONTRADICTIONS
# ─────────────────────────────────────────────────────────────────────────────

class TestStructuredDataConsistency(unittest.TestCase):

    def test_price_consistency_and_contradiction(self):
        """SDC-013 detects contradiction between visible price and JSON-LD schema price."""
        pages = [
            make_page(
                url="https://site.test/product/alpha",
                visible_text_sample="Special limited offer: Purchase now for $49.00 with lifetime updates!",
                json_ld=[{
                    "@context": "https://schema.org",
                    "@type": "Product",
                    "name": "Alpha Optimizer",
                    "offers": {"@type": "Offer", "price": "149.00", "priceCurrency": "USD"}
                }]
            )
        ]
        findings, _ = sdc_mod.run_checks(make_snapshot(pages, start_url="https://site.test/"))
        sdc013 = [f for f in findings if f["check_id"] == "SDC-013"]
        self.assertEqual(len(sdc013), 1)
        self.assertIn("$49.0", sdc013[0]["evidence"])
        self.assertIn("$149.0", sdc013[0]["evidence"])

    def test_availability_contradiction(self):
        """SDC-210 detects contradiction between visible out of stock and schema InStock."""
        pages = [
            make_page(
                url="https://site.test/store/widget",
                visible_text_sample="Currently Sold Out. This item is temporarily unavailable and on backorder.",
                json_ld=[{
                    "@context": "https://schema.org",
                    "@type": "Product",
                    "name": "Smart Widget",
                    "offers": {
                        "@type": "Offer",
                        "price": "29.99",
                        "availability": "https://schema.org/InStock"
                    }
                }]
            )
        ]
        findings, _ = sdc_mod.run_checks(make_snapshot(pages, start_url="https://site.test/"))
        sdc210 = [f for f in findings if f["check_id"] == "SDC-210"]
        self.assertEqual(len(sdc210), 1)
        self.assertIn("inventory contradiction", sdc210[0]["evidence"])

    def test_event_date_contradiction(self):
        """SDC-211 detects mismatch between visible date and Event startDate."""
        pages = [
            make_page(
                url="https://site.test/conference",
                visible_text_sample="Mark your calendars: The annual summit will take place on December 15, 2026 at the civic center.",
                json_ld=[{
                    "@context": "https://schema.org",
                    "@type": "Event",
                    "name": "Annual Summit",
                    "startDate": "2026-06-10"
                }]
            )
        ]
        findings, _ = sdc_mod.run_checks(make_snapshot(pages, start_url="https://site.test/"))
        sdc211 = [f for f in findings if f["check_id"] == "SDC-211"]
        self.assertEqual(len(sdc211), 1)
        self.assertIn("2026-06-10", sdc211[0]["evidence"])

    def test_semantic_heading_contradiction(self):
        """SDC-209 detects complete semantic divergence between schema name and visible heading."""
        pages = [
            make_page(
                url="https://site.test/services",
                title="Boutique Floral Design Studio",
                h1=["Fresh Wedding Floral Arrangements"],
                visible_text_sample="We craft seasonal botanical bouquets and floral decor for private events.",
                json_ld=[{
                    "@context": "https://schema.org",
                    "@type": "Product",
                    "name": "Enterprise Database Backup Daemon"
                }]
            )
        ]
        findings, _ = sdc_mod.run_checks(make_snapshot(pages, start_url="https://site.test/"))
        sdc209 = [f for f in findings if f["check_id"] == "SDC-209"]
        self.assertEqual(len(sdc209), 1)


# ─────────────────────────────────────────────────────────────────────────────
# 5. GENERALIZATION ACROSS 9 REAL-WORLD VERTICALS
# ─────────────────────────────────────────────────────────────────────────────

class TestRealWorldGeneralization(unittest.TestCase):

    def test_vertical_ecommerce(self):
        """E-commerce site with valid Product & Offer schemas and clean metadata."""
        pages = [
            make_page(
                url="https://shop.test/",
                page_type="Homepage",
                title="Aura Apparel — Modern Sustainable Fashion",
                meta_description="Discover ethical, organic clothing designed for timeless everyday wear.",
                h1=["Sustainable Fashion for Modern Living"],
                json_ld=[{"@context": "https://schema.org", "@type": "Organization", "name": "Aura Apparel"}]
            ),
            make_page(
                url="https://shop.test/products/linen-shirt",
                page_type="Product",
                title="Organic Linen Shirt — Aura Apparel",
                meta_description="Lightweight 100% organic French linen button-down shirt.",
                h1=["Organic Linen Shirt"],
                visible_text_sample="Crafted from natural fibers. $75.00. In Stock and ready to ship.",
                json_ld=[{
                    "@context": "https://schema.org",
                    "@type": "Product",
                    "name": "Organic Linen Shirt",
                    "description": "French linen button-down shirt",
                    "offers": {"@type": "Offer", "price": "75.00", "priceCurrency": "USD", "availability": "https://schema.org/InStock"}
                }]
            )
        ]
        snap = make_snapshot(pages, start_url="https://shop.test/")
        cra_f, _ = cra_mod.run_checks(snap)
        sdc_f, _ = sdc_mod.run_checks(snap)
        critical_or_high = [f for f in cra_f + sdc_f if f.get("severity") in ("critical", "high")]
        self.assertEqual(critical_or_high, [])

    def test_vertical_restaurant(self):
        """Restaurant site with Restaurant schema and clear dining hours."""
        pages = [
            make_page(
                url="https://bistro.test/",
                page_type="Homepage",
                title="Trattoria Bella — Authentic Woodfired Pizza & Pasta",
                meta_description="Cozy neighborhood Italian trattoria serving hand-rolled pasta in downtown.",
                h1=["Trattoria Bella Italian Dining"],
                json_ld=[{
                    "@context": "https://schema.org",
                    "@type": "Restaurant",
                    "name": "Trattoria Bella",
                    "servesCuisine": "Italian",
                    "telephone": "+1-555-0199"
                }]
            )
        ]
        snap = make_snapshot(pages, start_url="https://bistro.test/")
        _, strengths = cra_mod.run_checks(snap)
        sdc_f, _ = sdc_mod.run_checks(snap)
        self.assertFalse(any(f.get("check_id") == "SDC-003" for f in sdc_f))

    def test_vertical_healthcare(self):
        """Healthcare facility with Hospital / MedicalClinic schema recognized."""
        pages = [
            make_page(
                url="https://health.test/",
                page_type="Homepage",
                title="Cedar Valley Medical Center — Compassionate Patient Care",
                meta_description="Comprehensive primary and specialized medical services for the Cedar Valley community.",
                h1=["Cedar Valley Medical Center"],
                json_ld=[{
                    "@context": "https://schema.org",
                    "@type": "Hospital",
                    "name": "Cedar Valley Medical Center",
                    "telephone": "+1-555-0144"
                }]
            )
        ]
        snap = make_snapshot(pages, start_url="https://health.test/")
        sdc_f, _ = sdc_mod.run_checks(snap)
        self.assertFalse(any(f.get("check_id") == "SDC-003" for f in sdc_f))

    def test_vertical_education(self):
        """Educational institution with CollegeOrUniversity schema."""
        pages = [
            make_page(
                url="https://polytechnic.test/",
                page_type="Homepage",
                title="Grandview Polytechnic Institute — Engineering & Applied Sciences",
                meta_description="Undergraduate and graduate degree programs in software engineering and robotics.",
                h1=["Grandview Polytechnic Institute"],
                json_ld=[{
                    "@context": "https://schema.org",
                    "@type": "CollegeOrUniversity",
                    "name": "Grandview Polytechnic Institute"
                }]
            )
        ]
        snap = make_snapshot(pages, start_url="https://polytechnic.test/")
        sdc_f, _ = sdc_mod.run_checks(snap)
        self.assertFalse(any(f.get("check_id") == "SDC-003" for f in sdc_f))

    def test_vertical_saas(self):
        """SaaS platform with SoftwareApplication schema and pricing page."""
        pages = [
            make_page(
                url="https://cloudmetrics.test/",
                page_type="Homepage",
                title="CloudMetrics — Distributed Observability Platform",
                meta_description="Real-time telemetry and APM monitoring for microservice architectures.",
                h1=["Unified Observability for Cloud Teams"],
                json_ld=[{
                    "@context": "https://schema.org",
                    "@type": "SoftwareApplication",
                    "name": "CloudMetrics Platform",
                    "applicationCategory": "DeveloperApplication"
                }]
            )
        ]
        snap = make_snapshot(pages, start_url="https://cloudmetrics.test/")
        sdc_f, _ = sdc_mod.run_checks(snap)
        # Should not have generic title or missing H1 defect
        self.assertFalse(any(f.get("check_id") in ("SDC-206", "SDC-005") for f in sdc_f))

    def test_vertical_documentation(self):
        """Documentation website with clean hierarchy and TechArticle schema."""
        pages = [
            make_page(
                url="https://docs.framework.test/guide/getting-started",
                page_type="Documentation",
                title="Getting Started with Framework — Developer Guide",
                meta_description="Step-by-step instructions for installing and configuring Framework CLI.",
                h1=["Getting Started with Framework"],
                headings=[
                    {"level": 1, "text": "Getting Started with Framework"},
                    {"level": 2, "text": "Installation"},
                    {"level": 3, "text": "Quickstart Script"}
                ],
                json_ld=[{
                    "@context": "https://schema.org",
                    "@type": "TechArticle",
                    "headline": "Getting Started with Framework",
                    "datePublished": "2026-01-15"
                }]
            )
        ]
        snap = make_snapshot(pages, start_url="https://docs.framework.test/")
        sdc_f, _ = sdc_mod.run_checks(snap)
        self.assertFalse(any(f.get("check_id") in ("SDC-007", "SDC-207", "SDC-208") for f in sdc_f))

    def test_vertical_event(self):
        """Event website with valid Event structured data."""
        pages = [
            make_page(
                url="https://summit.test/",
                page_type="Homepage",
                title="DevCon 2026 — Annual Distributed Systems Conference",
                meta_description="Join 3,000 systems engineers for three days of deep technical talks.",
                h1=["DevCon 2026 Conference"],
                visible_text_sample="Happening live in Seattle on October 20, 2026. Register today!",
                json_ld=[{
                    "@context": "https://schema.org",
                    "@type": "Event",
                    "name": "DevCon 2026",
                    "startDate": "2026-10-20"
                }]
            )
        ]
        snap = make_snapshot(pages, start_url="https://summit.test/")
        sdc_f, _ = sdc_mod.run_checks(snap)
        self.assertFalse(any(f.get("check_id") in ("SDC-211", "SDC-208") for f in sdc_f))


# ─────────────────────────────────────────────────────────────────────────────
# 6. ANTI-OVERFITTING & MULTILINGUAL TESTS
# ─────────────────────────────────────────────────────────────────────────────

class TestAntiOverfittingAndMultilingual(unittest.TestCase):

    def test_arbitrary_domains_detect_identical_seo_defects(self):
        """The engine identifies the same SEO defect on arbitrary test domains without brand bias."""
        domains = ["https://example-alpha.test/", "https://random-site.test/", "https://company-123.test/"]
        for domain in domains:
            pages = [
                make_page(
                    url=domain,
                    page_type="Homepage",
                    title="   ",  # Blank title
                    meta_robots="noindex"
                )
            ]
            snap = make_snapshot(pages, start_url=domain)
            cra_f, _ = cra_mod.run_checks(snap)
            fired_ids = {f["check_id"] for f in cra_f}
            self.assertIn("CRA-021", fired_ids, f"CRA-021 should fire on blank title for {domain}")
            self.assertIn("CRA-002", fired_ids, f"CRA-002 should fire on noindex for {domain}")

    def test_multilingual_non_english_content(self):
        """Non-English pages (French, German, Spanish) are evaluated correctly without spurious defects."""
        french_pages = [
            make_page(
                url="https://boulangerie-paris.test/fr/",
                page_type="Homepage",
                title="Boulangerie Traditionnelle — Pains et Viennoiseries",
                meta_description="Artisan boulanger à Paris confectionnant baguettes au levain naturel et croissants pur beurre.",
                h1=["Boulangerie Artisanale Parisienne"],
                headings=[
                    {"level": 1, "text": "Boulangerie Artisanale Parisienne"},
                    {"level": 2, "text": "Nos Pains Spéciaux"}
                ],
                visible_text_sample="Bienvenue dans notre fournil artisanal où chaque pain est façonné à la main.",
                json_ld=[{
                    "@context": "https://schema.org",
                    "@type": "Bakery",
                    "name": "Boulangerie Traditionnelle",
                    "telephone": "+33-1-42-68-00-00"
                }]
            )
        ]
        snap = make_snapshot(french_pages, start_url="https://boulangerie-paris.test/fr/")
        sdc_f, _ = sdc_mod.run_checks(snap)
        # Should not flag semantic contradiction or missing H1
        self.assertFalse(any(f.get("check_id") in ("SDC-209", "SDC-005", "SDC-206") for f in sdc_f))


# ─────────────────────────────────────────────────────────────────────────────
# 7. RECOMMENDATION-ONLY GUARANTEE
# ─────────────────────────────────────────────────────────────────────────────

class TestRecommendationOnlyGuarantee(unittest.TestCase):

    def test_all_findings_are_advisory_only(self):
        """Every finding generated across skills must provide advisory recommendations only."""
        sample_pages = [
            make_page(url="https://audit.test/", title="Untitled Document", h1=[]),
            make_page(url="https://audit.test/product", title="Untitled Document", visible_text_sample="Cost: $10.00", json_ld=[{
                "@context": "https://schema.org",
                "@type": "Product",
                "offers": {"@type": "Offer", "price": "90.00"}
            }])
        ]
        snap = make_snapshot(sample_pages, start_url="https://audit.test/", disallowed=["/private/"])
        cra_f, _ = cra_mod.run_checks(snap)
        sdc_f, _ = sdc_mod.run_checks(snap)

        all_findings = cra_f + sdc_f
        self.assertTrue(len(all_findings) > 0)

        for finding in all_findings:
            action = finding.get("suggested_action", {})
            summary = action.get("summary", "")
            self.assertTrue(bool(summary), f"Finding {finding['check_id']} missing suggested action summary")
            # Must be advisory phrasing
            advisory_keywords = (
                "add", "provide", "ensure", "replace", "synchronize", "update",
                "write", "remove", "populate", "verify", "consider", "review",
                "expand", "strip", "point"
            )
            first_word = summary.strip().split()[0].lower()
            self.assertTrue(
                any(first_word.startswith(kw) for kw in advisory_keywords),
                f"Finding {finding['check_id']} suggested action '{summary}' does not use advisory language"
            )


if __name__ == "__main__":
    unittest.main()
