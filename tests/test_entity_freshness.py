#!/usr/bin/env python3
"""
test_entity_freshness.py — Comprehensive tests for Phase 4: Entity Identity & Freshness / Corroboration.

Verifies:
- Entity Identity (consistent/inconsistent name, capitalization/punctuation normalization, consistent/conflicting location,
  consistent/conflicting contact info, schema agreeing/conflicting with visible content, multi-page corroboration, weak/missing identity)
- Entity Confidence (deterministic scoring, high/moderate/low confidence tiers, deduction penalties)
- Freshness & Corroboration (matching/conflicting publication dates, datePublished/dateModified, visible updated dates,
  stale time-sensitive vs evergreen documentation, current vs conflicting event dates, cross-page pricing corroboration/conflicts)
- Page Importance Prioritization (Phase 1 page importance boosting priority of identity/freshness findings)
- Real-World Generalization across 9 generic verticals (E-commerce, Service, Restaurant, Healthcare, Education, SaaS, Docs, Event, Informational)
- Anti-Overfitting with arbitrary domains and domain-invariance guarantees
- Determinism & Advisory Recommendation-Only guarantees
"""

import copy
import json
import unittest
from pathlib import Path
import importlib.util

REPO_ROOT = Path(__file__).parent.parent


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ent_mod = load_module(REPO_ROOT / "skills/entity-identity-audit/scripts/audit.py", "ent_mod_p4")
frs_mod = load_module(REPO_ROOT / "skills/freshness-corroboration-audit/scripts/audit.py", "frs_mod_p4")
score_mod = load_module(REPO_ROOT / "skills/audit-orchestrator/scripts/score.py", "score_mod_p4")


def make_snapshot(pages: list, start_url: str = "https://example.com/") -> dict:
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
            "disallowed_paths": [],
            "crawl_timeout_hit": False
        },
        "pages": pages
    }


def make_page(url: str = "https://example.com/", **overrides) -> dict:
    title = overrides.get("title", "Example Site")
    defaults = {
        "url": url,
        "status_code": 200,
        "final_url": url,
        "redirect_chain": [],
        "canonical": url,
        "meta_robots": "",
        "x_robots_tag": "",
        "title": title,
        "meta_description": "A comprehensive example organization site.",
        "h1": [title],
        "headings": [{"level": 1, "text": title},
                     {"level": 2, "text": "Overview"}],
        "json_ld": [],
        "open_graph": {},
        "twitter_card": {},
        "links": [
            {"href": f"{url}about", "text": "About", "is_internal": True},
            {"href": f"{url}contact", "text": "Contact", "is_internal": True}
        ],
        "images": [],
        "visible_text_length": 800,
        "visible_text_sample": "Welcome to official organization page. Contact us at info@example.com or +1-617-555-0100.",
        "last_modified": "2026-09-01",
        "crawled_with_js": False,
        "js_render_available": False,
        "raw_html_length": 5000,
        "page_type": "Other/unknown",
        "page_importance_score": 50
    }
    defaults.update(overrides)
    return defaults


class TestEntityIdentity(unittest.TestCase):
    """Part 1 & 2 & 11: Entity Identity detection, normalization, and contradiction checks."""

    def test_consistent_organization_name(self):
        """Pages and JSON-LD agree on the organization name."""
        pages = [
            make_page(
                "https://acme-tools.test/",
                title="Acme Tools - Industrial Equipment",
                h1=["Acme Tools"],
                json_ld=[{"@type": "Organization", "name": "Acme Tools", "url": "https://acme-tools.test/"}]
            ),
            make_page(
                "https://acme-tools.test/about",
                title="About Us - Acme Tools",
                h1=["About Acme Tools"],
                page_type="About",
                json_ld=[{"@type": "Organization", "name": "Acme Tools"}]
            )
        ]
        snapshot = make_snapshot(pages, "https://acme-tools.test/")
        findings, strengths = ent_mod.run_checks(snapshot)
        finding_ids = [f.get("check_id") for f in findings]
        self.assertNotIn("ENT-001", finding_ids)
        self.assertNotIn("ENT-002", finding_ids)
        self.assertTrue(any("strongly corroborated" in s.get("title", "").lower() or "declared" in s.get("title", "").lower() for s in strengths))

    def test_inconsistent_organization_name(self):
        """Meaningful contradiction between homepage identity and internal page entity name."""
        pages = [
            make_page(
                "https://acme-tools.test/",
                title="Acme Tools Homepage",
                h1=["Acme Tools"],
                json_ld=[{"@type": "Organization", "name": "Acme Tools"}]
            ),
            make_page(
                "https://acme-tools.test/about",
                title="About Us",
                page_type="About",
                json_ld=[{"@type": "Organization", "name": "Apex Global Solutions"}]
            )
        ]
        snapshot = make_snapshot(pages, "https://acme-tools.test/")
        findings, _ = ent_mod.run_checks(snapshot)
        ent_002 = next((f for f in findings if f.get("check_id") == "ENT-002"), None)
        self.assertIsNotNone(ent_002, "Should report ENT-002 for divergent organization names")
        self.assertIn("https://acme-tools.test/about", ent_002["affected_urls"])
        self.assertIn("Apex Global Solutions", ent_002["evidence"])

    def test_capitalization_only_difference_normalized(self):
        """Differences solely in capitalization must NOT trigger an inconsistency finding."""
        pages = [
            make_page(
                "https://acme-tools.test/",
                title="ACME TOOLS",
                json_ld=[{"@type": "Organization", "name": "ACME TOOLS"}]
            ),
            make_page(
                "https://acme-tools.test/about",
                page_type="About",
                json_ld=[{"@type": "Organization", "name": "acme tools"}]
            )
        ]
        snapshot = make_snapshot(pages, "https://acme-tools.test/")
        findings, _ = ent_mod.run_checks(snapshot)
        finding_ids = [f.get("check_id") for f in findings]
        self.assertNotIn("ENT-002", finding_ids, "Capitalization differences alone must be normalized")

    def test_punctuation_only_difference_normalized(self):
        """Differences with legal suffixes and commas/dots must NOT trigger contradiction."""
        pages = [
            make_page(
                "https://acme-tools.test/",
                json_ld=[{"@type": "Organization", "name": "Example, Inc."}]
            ),
            make_page(
                "https://acme-tools.test/about",
                page_type="About",
                json_ld=[{"@type": "Organization", "name": "Example Inc"}]
            ),
            make_page(
                "https://acme-tools.test/contact",
                page_type="Contact",
                json_ld=[{"@type": "Organization", "name": "EXAMPLE INC."}]
            )
        ]
        snapshot = make_snapshot(pages, "https://acme-tools.test/")
        findings, _ = ent_mod.run_checks(snapshot)
        finding_ids = [f.get("check_id") for f in findings]
        self.assertNotIn("ENT-002", finding_ids, "Punctuation/legal suffix variants must be normalized")

    def test_consistent_location_corroborated(self):
        """Consistent headquarters address in copy and schema produces no location conflict."""
        pages = [
            make_page(
                "https://acme-tools.test/",
                visible_text_sample="Headquarters: Seattle, WA. Serving customers worldwide.",
                json_ld=[{"@type": "Organization", "name": "Acme", "address": {"addressLocality": "Seattle", "addressCountry": "US"}}]
            ),
            make_page(
                "https://acme-tools.test/contact",
                page_type="Contact",
                visible_text_sample="Based in Seattle, WA. Call our main desk."
            )
        ]
        snapshot = make_snapshot(pages, "https://acme-tools.test/")
        findings, _ = ent_mod.run_checks(snapshot)
        finding_ids = [f.get("check_id") for f in findings]
        self.assertNotIn("ENT-010", finding_ids)

    def test_conflicting_location_detected(self):
        """Contradicting locations across schema and copy emit ENT-010 with evidence."""
        pages = [
            make_page(
                "https://acme-tools.test/",
                visible_text_sample="Corporate headquarters: New York, NY.",
                json_ld=[{"@type": "Organization", "name": "Acme", "address": {"addressLocality": "New York", "addressCountry": "US"}}]
            ),
            make_page(
                "https://acme-tools.test/contact",
                page_type="Contact",
                visible_text_sample="Headquarters: Chicago, IL. Visit our corporate office.",
                json_ld=[{"@type": "Organization", "name": "Acme", "address": {"addressLocality": "Chicago", "addressCountry": "US"}}]
            )
        ]
        snapshot = make_snapshot(pages, "https://acme-tools.test/")
        findings, _ = ent_mod.run_checks(snapshot)
        ent_010 = next((f for f in findings if f.get("check_id") == "ENT-010"), None)
        self.assertIsNotNone(ent_010, "Should detect conflicting corporate locations")
        self.assertTrue(any("Chicago" in ent_010["evidence"] or "New York" in ent_010["evidence"] for _ in [1]))
        self.assertEqual(ent_010["suggested_action"]["priority"], "high")

    def test_consistent_contact_information(self):
        """Consistent support email and phone numbers across pages."""
        pages = [
            make_page(
                "https://acme-tools.test/",
                visible_text_sample="Customer service: support@acme-tools.test or +1-800-555-0199."
            ),
            make_page(
                "https://acme-tools.test/contact",
                page_type="Contact",
                visible_text_sample="Email our team at support@acme-tools.test or phone +1-800-555-0199."
            )
        ]
        snapshot = make_snapshot(pages, "https://acme-tools.test/")
        findings, strengths = ent_mod.run_checks(snapshot)
        finding_ids = [f.get("check_id") for f in findings]
        self.assertNotIn("ENT-011", finding_ids)
        self.assertTrue(any("contact" in s.get("title", "").lower() for s in strengths))

    def test_conflicting_contact_information(self):
        """Conflicting corporate email domains across pages emit ENT-011."""
        pages = [
            make_page(
                "https://acme-tools.test/",
                visible_text_sample="Reach us at press@alpha-holdings.corp for media inquiries."
            ),
            make_page(
                "https://acme-tools.test/contact",
                page_type="Contact",
                visible_text_sample="Official inquiries go to admin@beta-industries.net exclusively."
            )
        ]
        snapshot = make_snapshot(pages, "https://acme-tools.test/")
        findings, _ = ent_mod.run_checks(snapshot)
        ent_011 = next((f for f in findings if f.get("check_id") == "ENT-011"), None)
        self.assertIsNotNone(ent_011, "Should flag conflicting corporate email domains")

    def test_schema_conflicts_with_visible_h1(self):
        """Organization JSON-LD declares completely different entity than visible page H1."""
        pages = [
            make_page(
                "https://acme-tools.test/",
                title="Delta Dynamics - Robotics",
                h1=["Delta Dynamics"],
                json_ld=[{"@type": "Organization", "name": "Zeta Software Group"}]
            )
        ]
        snapshot = make_snapshot(pages, "https://acme-tools.test/")
        findings, _ = ent_mod.run_checks(snapshot)
        ent_008 = next((f for f in findings if f.get("check_id") == "ENT-008"), None)
        self.assertIsNotNone(ent_008, "Should detect schema name contradicting visible H1/Title")

    def test_weak_identity_evidence(self):
        """No schema, no About page, no contact channels yields low confidence score."""
        pages = [
            make_page(
                "https://minimal-site.test/",
                title="Generic Landing",
                h1=["Welcome"],
                visible_text_sample="Just a simple placeholder."
            )
        ]
        snapshot = make_snapshot(pages, "https://minimal-site.test/")
        score, level, signals = ent_mod.compute_entity_confidence(snapshot)
        self.assertLessEqual(score, 0.40)
        self.assertEqual(level, "Low")

    def test_missing_identity_information(self):
        """Total absence of brand name, schema, and identifiable headings triggers ENT-001."""
        pages = [
            make_page(
                "https://192.168.1.100/",
                title="",
                h1=[],
                visible_text_sample="Under construction. Check back soon."
            )
        ]
        snapshot = make_snapshot(pages, "https://192.168.1.100/")
        findings, _ = ent_mod.run_checks(snapshot)
        finding_ids = [f.get("check_id") for f in findings]
        self.assertIn("ENT-001", finding_ids)


class TestEntityConfidence(unittest.TestCase):
    """Part 3: Deterministic entity identity confidence calculation."""

    def test_high_confidence_with_all_authoritative_signals(self):
        """Brand name in JSON-LD, About page, Contact channels, and external sameAs yields high confidence >= 0.75."""
        pages = [
            make_page(
                "https://verified-firm.test/",
                title="Verified Firm",
                h1=["Verified Firm"],
                page_type="Homepage",
                json_ld=[{
                    "@type": "Organization",
                    "name": "Verified Firm",
                    "sameAs": ["https://www.wikidata.org/wiki/Q12345", "https://linkedin.com/company/verifiedfirm"]
                }]
            ),
            make_page(
                "https://verified-firm.test/about",
                title="About Verified Firm",
                page_type="About"
            ),
            make_page(
                "https://verified-firm.test/contact",
                title="Contact Us",
                page_type="Contact",
                visible_text_sample="Support: help@verified-firm.test"
            )
        ]
        snapshot = make_snapshot(pages, "https://verified-firm.test/")
        findings, strengths = ent_mod.run_checks(snapshot)
        score, level, signals = ent_mod.compute_entity_confidence(snapshot, findings)
        self.assertGreaterEqual(score, 0.75)
        self.assertEqual(level, "High")
        self.assertTrue(any("High confidence" in s.get("title", "") for s in strengths))

    def test_confidence_penalized_by_contradictions(self):
        """Identity contradictions substantially lower the confidence score."""
        pages = [
            make_page(
                "https://conflicted.test/",
                title="Brand A",
                h1=["Brand A"],
                json_ld=[{"@type": "Organization", "name": "Brand A"}]
            ),
            make_page(
                "https://conflicted.test/about",
                page_type="About",
                json_ld=[{"@type": "Organization", "name": "Brand Z"}]
            )
        ]
        snapshot = make_snapshot(pages, "https://conflicted.test/")
        findings, _ = ent_mod.run_checks(snapshot)
        score_with_findings, level, _ = ent_mod.compute_entity_confidence(snapshot, findings)
        score_clean, _, _ = ent_mod.compute_entity_confidence(snapshot, [])
        self.assertLess(score_with_findings, score_clean, "Contradiction findings must deduct from entity confidence")


class TestFreshnessAndCorroboration(unittest.TestCase):
    """Part 4 & 5 & 6 & 12: Freshness signals, dates, cross-page corroboration."""

    def test_matching_publication_dates(self):
        """Consistent dateModified and last_modified within normal tolerance."""
        pages = [
            make_page(
                "https://news-site.test/article-1",
                last_modified="2026-08-15",
                json_ld=[{
                    "@type": "Article",
                    "headline": "AI Developments",
                    "datePublished": "2026-08-10",
                    "dateModified": "2026-08-15"
                }]
            )
        ]
        snapshot = make_snapshot(pages, "https://news-site.test/")
        findings, strengths = frs_mod.run_checks(snapshot)
        finding_ids = [f.get("check_id") for f in findings]
        self.assertNotIn("FRS-005", finding_ids)
        self.assertTrue(any("datePublished" in s.get("title", "") for s in strengths))

    def test_conflicting_dates_detected(self):
        """Last-Modified header and JSON-LD dateModified differing by >30 days emit FRS-005."""
        pages = [
            make_page(
                "https://news-site.test/article-drift",
                last_modified="2026-08-01",
                json_ld=[{
                    "@type": "Article",
                    "headline": "Old Post",
                    "datePublished": "2024-01-01",
                    "dateModified": "2024-01-05"
                }]
            )
        ]
        snapshot = make_snapshot(pages, "https://news-site.test/")
        findings, _ = frs_mod.run_checks(snapshot)
        finding_ids = [f.get("check_id") for f in findings]
        self.assertIn("FRS-005", finding_ids)

    def test_visible_updated_date_extracted(self):
        """Pages without HTTP Last-Modified headers still extract visible 'Last updated:' dates."""
        pages = [
            make_page(
                "https://guide-site.test/manual",
                last_modified=None,
                visible_text_sample="Welcome to the operations manual. Last updated: August 20, 2026. Read below for details."
            )
        ]
        snapshot = make_snapshot(pages, "https://guide-site.test/")
        findings, strengths = frs_mod.run_checks(snapshot)
        finding_ids = [f.get("check_id") for f in findings]
        # Should not claim no date signals exist
        self.assertNotIn("FRS-001", finding_ids, "Visible date should prevent FRS-001 false positive")

    def test_stale_time_sensitive_vs_evergreen_documentation(self):
        """Time-sensitive pricing page from 2 years ago is flagged; 2-year-old documentation page is not labeled stale."""
        # 1. Stale pricing page (>365 days)
        pricing_pages = [
            make_page(
                "https://saas-company.test/pricing",
                page_type="Pricing",
                last_modified="2024-01-01",
                visible_text_sample="Plans start at $49/month."
            )
        ]
        snap_pricing = make_snapshot(pricing_pages, "https://saas-company.test/")
        findings_pricing, _ = frs_mod.run_checks(snap_pricing)
        self.assertTrue(any(f.get("check_id") == "FRS-002" and "time-sensitive" in f.get("title", "").lower() for f in findings_pricing))

        # 2. Evergreen docs page (2 years old, <3 years threshold)
        doc_pages = [
            make_page(
                "https://saas-company.test/docs/install",
                page_type="Documentation",
                last_modified="2024-06-01",
                visible_text_sample="Run npm install to configure dependencies."
            )
        ]
        snap_docs = make_snapshot(doc_pages, "https://saas-company.test/")
        findings_docs, _ = frs_mod.run_checks(snap_docs)
        self.assertFalse(any(f.get("check_id") == "FRS-002" for f in findings_docs), "2-year-old docs should not be labeled stale")

    def test_current_and_corroborated_event_dates(self):
        """Matching event dates across announcement page and structured data."""
        pages = [
            make_page(
                "https://events.test/summit",
                title="Global Tech Summit 2026",
                page_type="Event",
                visible_text_sample="Join us for Global Tech Summit on October 15, 2026 in Chicago.",
                json_ld=[{
                    "@type": "Event",
                    "name": "Global Tech Summit",
                    "startDate": "2026-10-15"
                }]
            )
        ]
        snapshot = make_snapshot(pages, "https://events.test/")
        findings, strengths = frs_mod.run_checks(snapshot)
        finding_ids = [f.get("check_id") for f in findings]
        self.assertNotIn("FRS-007", finding_ids)
        self.assertTrue(any("event schedule corroborated" in s.get("title", "").lower() for s in strengths))

    def test_conflicting_event_dates_detected(self):
        """Divergent event dates across pages trigger FRS-007 with affected URLs."""
        pages = [
            make_page(
                "https://events.test/conf-landing",
                page_type="Event",
                title="Future Tech Summit",
                visible_text_sample="Future Tech Summit kicks off on June 10, 2026 in Chicago."
            ),
            make_page(
                "https://events.test/conf-registration",
                page_type="Event",
                title="Future Tech Summit Registration",
                visible_text_sample="Registration opens for Future Tech Summit on July 20, 2026 in Chicago."
            )
        ]
        snapshot = make_snapshot(pages, "https://events.test/")
        findings, _ = frs_mod.run_checks(snapshot)
        frs_007 = next((f for f in findings if f.get("check_id") == "FRS-007"), None)
        self.assertIsNotNone(frs_007, "Should detect conflicting event schedule across pages")
        self.assertIn("https://events.test/conf-landing", frs_007["affected_urls"])
        self.assertIn("https://events.test/conf-registration", frs_007["affected_urls"])

    def test_cross_page_pricing_corroboration(self):
        """Pricing page and product schema declaring the same price are corroborated."""
        pages = [
            make_page(
                "https://store.test/products/smart-widget",
                title="Smart Widget - Buy Online",
                h1=["Smart Widget"],
                json_ld=[{"@type": "Product", "name": "Smart Widget", "offers": {"price": "99.00", "priceCurrency": "USD"}}]
            ),
            make_page(
                "https://store.test/pricing",
                title="Pricing Table",
                page_type="Pricing",
                visible_text_sample="Smart Widget is available for $99.00 today."
            )
        ]
        snapshot = make_snapshot(pages, "https://store.test/")
        findings, strengths = frs_mod.run_checks(snapshot)
        finding_ids = [f.get("check_id") for f in findings]
        self.assertNotIn("FRS-006", finding_ids)
        self.assertTrue(any("pricing information corroborated" in s.get("title", "").lower() for s in strengths))

    def test_conflicting_prices_detected(self):
        """Product page declaring $99 and pricing table declaring $149 for the same product emit FRS-006."""
        pages = [
            make_page(
                "https://store.test/products/smart-widget",
                title="Smart Widget",
                h1=["Smart Widget"],
                json_ld=[{"@type": "Product", "name": "Smart Widget", "offers": {"price": "99.00", "priceCurrency": "USD"}}]
            ),
            make_page(
                "https://store.test/pricing",
                title="Pricing Plans",
                page_type="Pricing",
                visible_text_sample="Smart Widget: $149.00 one-time fee."
            )
        ]
        snapshot = make_snapshot(pages, "https://store.test/")
        findings, _ = frs_mod.run_checks(snapshot)
        frs_006 = next((f for f in findings if f.get("check_id") == "FRS-006"), None)
        self.assertIsNotNone(frs_006, "Should detect cross-page price conflict")
        self.assertIn("$99.0", frs_006["evidence"])
        self.assertIn("$149.0", frs_006["evidence"])

    def test_missing_freshness_signals_when_unsupported(self):
        """Site completely lacking HTTP dates, JSON-LD dates, or visible timestamps reports FRS-001."""
        pages = [
            make_page(
                "https://static-firm.test/page1",
                last_modified=None,
                visible_text_sample="Welcome to our static site. Information provided as-is without timestamp."
            ),
            make_page(
                "https://static-firm.test/page2",
                last_modified=None,
                visible_text_sample="Learn more about our general capabilities."
            )
        ]
        snapshot = make_snapshot(pages, "https://static-firm.test/")
        findings, _ = frs_mod.run_checks(snapshot)
        finding_ids = [f.get("check_id") for f in findings]
        self.assertIn("FRS-001", finding_ids)


class TestPageImportancePrioritization(unittest.TestCase):
    """Part 7: Verifies page importance scores boost finding priority for important pages."""

    def test_important_page_receives_higher_priority(self):
        """Issue on homepage (importance 95) receives higher priority than identical issue on leaf page (importance 30)."""
        finding_important = {
            "id": "test-finding-high",
            "title": "Conflicting location on key hub",
            "category": "discoverability",
            "severity": "medium",
            "confidence": "high",
            "affected_urls": ["https://corp.test/"]
        }
        finding_minor = {
            "id": "test-finding-low",
            "title": "Conflicting location on obscure leaf",
            "category": "discoverability",
            "severity": "medium",
            "confidence": "high",
            "affected_urls": ["https://corp.test/deep/leaf/note"]
        }

        snapshot = make_snapshot([
            make_page("https://corp.test/", page_importance_score=95),
            make_page("https://corp.test/deep/leaf/note", page_importance_score=30)
        ], "https://corp.test/")

        priorities = score_mod.compute_top_priorities([finding_minor, finding_important], limit=2, snapshot=snapshot)
        self.assertEqual(priorities[0]["id"], "test-finding-high", "High importance page finding must rank first")
        self.assertGreater(priorities[0]["priority_score"], priorities[1]["priority_score"])


class TestGenericWebsiteVerticals(unittest.TestCase):
    """Part 10: Synthetic test fixtures for 9 generic website verticals."""

    def test_vertical_ecommerce(self):
        """1. E-commerce / product website."""
        pages = [
            make_page("https://shop-hub.test/", title="ShopHub Online", h1=["ShopHub"], json_ld=[{"@type": "Organization", "name": "ShopHub"}]),
            make_page("https://shop-hub.test/p/laptop", title="Pro Laptop", json_ld=[{"@type": "Product", "name": "Pro Laptop", "offers": {"price": "999.00"}}]),
            make_page("https://shop-hub.test/about", page_type="About"),
            make_page("https://shop-hub.test/contact", page_type="Contact")
        ]
        findings, strengths = ent_mod.run_checks(make_snapshot(pages, "https://shop-hub.test/"))
        self.assertNotIn("ENT-001", [f["check_id"] for f in findings])
        self.assertNotIn("ENT-002", [f["check_id"] for f in findings])

    def test_vertical_service_business(self):
        """2. Service business website."""
        pages = [
            make_page("https://plumb-pro.test/", title="PlumbPro Services", h1=["PlumbPro"], json_ld=[{"@type": "LocalBusiness", "name": "PlumbPro"}]),
            make_page("https://plumb-pro.test/services", title="Residential Plumbing"),
            make_page("https://plumb-pro.test/about", page_type="About"),
            make_page("https://plumb-pro.test/contact", page_type="Contact", visible_text_sample="Emergency desk: contact@plumb-pro.test")
        ]
        findings, strengths = ent_mod.run_checks(make_snapshot(pages, "https://plumb-pro.test/"))
        self.assertNotIn("ENT-002", [f["check_id"] for f in findings])

    def test_vertical_restaurant(self):
        """3. Restaurant website."""
        pages = [
            make_page("https://bistro-paris.test/", title="Bistro Paris", h1=["Bistro Paris"], json_ld=[{"@type": "Restaurant", "name": "Bistro Paris"}]),
            make_page("https://bistro-paris.test/menu", title="Dinner Menu"),
            make_page("https://bistro-paris.test/about", page_type="About"),
            make_page("https://bistro-paris.test/contact", page_type="Contact")
        ]
        findings, strengths = ent_mod.run_checks(make_snapshot(pages, "https://bistro-paris.test/"))
        self.assertNotIn("ENT-002", [f["check_id"] for f in findings])

    def test_vertical_healthcare(self):
        """4. Healthcare / clinic website."""
        pages = [
            make_page("https://metro-health.test/", title="Metro Health Clinic", h1=["Metro Health Clinic"], json_ld=[{"@type": "MedicalClinic", "name": "Metro Health Clinic"}]),
            make_page("https://metro-health.test/doctors", title="Physicians"),
            make_page("https://metro-health.test/about", page_type="About"),
            make_page("https://metro-health.test/contact", page_type="Contact")
        ]
        findings, _ = ent_mod.run_checks(make_snapshot(pages, "https://metro-health.test/"))
        self.assertNotIn("ENT-002", [f["check_id"] for f in findings])

    def test_vertical_university(self):
        """5. University / education website."""
        pages = [
            make_page("https://coastal-univ.test/", title="Coastal University", h1=["Coastal University"], json_ld=[{"@type": "CollegeOrUniversity", "name": "Coastal University"}]),
            make_page("https://coastal-univ.test/admissions", title="Admissions"),
            make_page("https://coastal-univ.test/about", page_type="About"),
            make_page("https://coastal-univ.test/contact", page_type="Contact")
        ]
        findings, _ = ent_mod.run_checks(make_snapshot(pages, "https://coastal-univ.test/"))
        self.assertNotIn("ENT-002", [f["check_id"] for f in findings])

    def test_vertical_saas(self):
        """6. SaaS / software website."""
        pages = [
            make_page("https://cloud-task.test/", title="CloudTask SaaS", h1=["CloudTask"], json_ld=[{"@type": "Organization", "name": "CloudTask"}]),
            make_page("https://cloud-task.test/pricing", title="Pricing", page_type="Pricing", last_modified="2026-08-01"),
            make_page("https://cloud-task.test/about", page_type="About"),
            make_page("https://cloud-task.test/contact", page_type="Contact")
        ]
        findings, _ = ent_mod.run_checks(make_snapshot(pages, "https://cloud-task.test/"))
        self.assertNotIn("ENT-002", [f["check_id"] for f in findings])

    def test_vertical_documentation(self):
        """7. Documentation / developer portal website."""
        pages = [
            make_page("https://docs.api-gateway.test/", title="API Docs", page_type="Documentation"),
            make_page("https://docs.api-gateway.test/auth", title="Authentication", page_type="Documentation", last_modified="2025-01-01")
        ]
        # Docs site should not be penalized for missing about page or aged docs under 3 years
        findings_ent, _ = ent_mod.run_checks(make_snapshot(pages, "https://docs.api-gateway.test/"))
        findings_frs, _ = frs_mod.run_checks(make_snapshot(pages, "https://docs.api-gateway.test/"))
        self.assertNotIn("ENT-003", [f["check_id"] for f in findings_ent])
        self.assertNotIn("FRS-002", [f["check_id"] for f in findings_frs])

    def test_vertical_event(self):
        """8. Event website."""
        pages = [
            make_page("https://annual-expo.test/", title="Annual Expo 2026", h1=["Annual Expo 2026"], json_ld=[{"@type": "Event", "name": "Annual Expo 2026", "startDate": "2026-11-10"}]),
            make_page("https://annual-expo.test/about", page_type="About"),
            make_page("https://annual-expo.test/contact", page_type="Contact")
        ]
        findings, strengths = frs_mod.run_checks(make_snapshot(pages, "https://annual-expo.test/"))
        self.assertNotIn("FRS-007", [f["check_id"] for f in findings])

    def test_vertical_informational(self):
        """9. Informational / research organization website."""
        pages = [
            make_page("https://climate-watch.test/", title="Climate Watch Institute", h1=["Climate Watch Institute"], json_ld=[{"@type": "NGO", "name": "Climate Watch Institute"}]),
            make_page("https://climate-watch.test/reports", title="Annual Reports", last_modified="2026-07-01"),
            make_page("https://climate-watch.test/about", page_type="About"),
            make_page("https://climate-watch.test/contact", page_type="Contact")
        ]
        findings, _ = ent_mod.run_checks(make_snapshot(pages, "https://climate-watch.test/"))
        self.assertNotIn("ENT-002", [f["check_id"] for f in findings])


class TestAntiOverfittingAndGeneralization(unittest.TestCase):
    """Part 13: Arbitrary domains, multilingual content, and domain-invariance verification."""

    def test_arbitrary_test_domains_evaluated_identically(self):
        """Explicitly tests specified arbitrary domains with identical structure."""
        domains = [
            "https://example-alpha.test/",
            "https://random-company.test/",
            "https://demo-business.test/",
            "https://company-123.test/"
        ]

        def build_domain_snapshot(domain):
            return make_snapshot([
                make_page(f"{domain}", title="Alpha Tech", h1=["Alpha Tech"], json_ld=[{"@type": "Organization", "name": "Alpha Tech"}]),
                make_page(f"{domain}about", page_type="About", json_ld=[{"@type": "Organization", "name": "Beta Corp"}]),
                make_page(f"{domain}contact", page_type="Contact")
            ], domain)

        reference_findings = None
        for d in domains:
            snap = build_domain_snapshot(d)
            findings, _ = ent_mod.run_checks(snap)
            finding_ids = sorted([f["check_id"] for f in findings])
            if reference_findings is None:
                reference_findings = finding_ids
            else:
                self.assertEqual(finding_ids, reference_findings, f"Domain {d} must produce identical check IDs based on semantics")

    def test_domain_change_only_produces_identical_findings(self):
        """Changing ONLY domain name leaves finding categories, severities, and check_ids identical."""
        def make_test_snap(base):
            return make_snapshot([
                make_page(f"{base}", title="Org", h1=["Org"], json_ld=[{"@type": "Organization", "name": "Org"}]),
                make_page(f"{base}pricing", page_type="Pricing", last_modified="2024-01-01")
            ], base)

        snap1 = make_test_snap("https://domain-aaa.test/")
        snap2 = make_test_snap("https://domain-bbb.test/")

        f1_ent, _ = ent_mod.run_checks(snap1)
        f2_ent, _ = ent_mod.run_checks(snap2)
        self.assertEqual([f["check_id"] for f in f1_ent], [f["check_id"] for f in f2_ent])

        f1_frs, _ = frs_mod.run_checks(snap1)
        f2_frs, _ = frs_mod.run_checks(snap2)
        self.assertEqual([f["check_id"] for f in f1_frs], [f["check_id"] for f in f2_frs])

    def test_multilingual_entity_signals(self):
        """Non-English terms (GmbH, S.A., Société) are normalized without spurious contradiction."""
        pages = [
            make_page(
                "https://global-corp.test/",
                title="Müller & Schmidt GmbH",
                h1=["Müller & Schmidt"],
                json_ld=[{"@type": "Organization", "name": "Müller & Schmidt GmbH"}]
            ),
            make_page(
                "https://global-corp.test/de/ueber-uns",
                title="Über uns - Müller & Schmidt",
                page_type="About",
                json_ld=[{"@type": "Organization", "name": "Müller & Schmidt"}]
            )
        ]
        snapshot = make_snapshot(pages, "https://global-corp.test/")
        findings, _ = ent_mod.run_checks(snapshot)
        finding_ids = [f["check_id"] for f in findings]
        self.assertNotIn("ENT-002", finding_ids, "Multilingual legal suffixes must be cleanly normalized")


class TestDeterminismAndRecommendationOnly(unittest.TestCase):
    """Part 14 & 15: Verification of deterministic execution and advisory-only recommendations."""

    def test_determinism_across_multiple_runs(self):
        """Repeated runs of the same fixture produce bit-for-bit identical results (excluding timestamps)."""
        pages = [
            make_page(
                "https://deterministic.test/",
                title="Determinism Test",
                h1=["Determinism Test"],
                visible_text_sample="Headquarters in Boston, MA. Plan is $99/mo.",
                json_ld=[{"@type": "Organization", "name": "Determinism Test"}]
            ),
            make_page(
                "https://deterministic.test/pricing",
                page_type="Pricing",
                visible_text_sample="Plan is $149/mo."
            ),
            make_page(
                "https://deterministic.test/about",
                page_type="About"
            )
        ]
        snap = make_snapshot(pages, "https://deterministic.test/")

        run1_ent, run1_ent_str = ent_mod.run_checks(snap)
        run2_ent, run2_ent_str = ent_mod.run_checks(snap)
        self.assertEqual(run1_ent, run2_ent)
        self.assertEqual(run1_ent_str, run2_ent_str)

        run1_frs, run1_frs_str = frs_mod.run_checks(snap)
        run2_frs, run2_frs_str = frs_mod.run_checks(snap)
        self.assertEqual(run1_frs, run2_frs)
        self.assertEqual(run1_frs_str, run2_frs_str)

    def test_recommendations_are_strictly_advisory(self):
        """All suggested actions must use advisory guidance ('Consider', 'Ensure', 'Reconcile') and not mandate specific mutations."""
        pages = [
            make_page(
                "https://advisory.test/",
                title="Conflict Hub",
                h1=["Conflict Hub"],
                visible_text_sample="Headquarters: New York, NY. Contact: user@domain-a.org",
                json_ld=[{"@type": "Organization", "name": "Conflict Hub"}]
            ),
            make_page(
                "https://advisory.test/contact",
                page_type="Contact",
                visible_text_sample="Headquarters: Chicago, IL. Contact: admin@domain-b.net"
            ),
            make_page(
                "https://advisory.test/pricing",
                page_type="Pricing",
                visible_text_sample="Service plan: $100/mo."
            ),
            make_page(
                "https://advisory.test/cart",
                visible_text_sample="Service plan: $200/mo."
            )
        ]
        snap = make_snapshot(pages, "https://advisory.test/")
        findings_ent, _ = ent_mod.run_checks(snap)
        findings_frs, _ = frs_mod.run_checks(snap)
        all_findings = findings_ent + findings_frs

        advisory_prefixes = (
            "consider", "ensure", "reconcile", "standardise", "standardize",
            "align", "verify", "review", "add", "provide", "implement", "update", "create"
        )
        for f in all_findings:
            action = f.get("suggested_action", {})
            summary = action.get("summary", "") if isinstance(action, dict) else str(action)
            self.assertTrue(
                any(summary.lower().startswith(p) for p in advisory_prefixes),
                f"Finding {f.get('check_id')} suggested action must be advisory, got: '{summary}'"
            )

    def test_no_snapshot_mutation(self):
        """Audit skills must treat the input snapshot as immutable and never modify it."""
        pages = [
            make_page(
                "https://immutable.test/",
                title="Immutable Test",
                h1=["Immutable Test"],
                json_ld=[{"@type": "Organization", "name": "Immutable Test"}]
            )
        ]
        snap = make_snapshot(pages, "https://immutable.test/")
        snap_copy = copy.deepcopy(snap)

        ent_mod.run_checks(snap)
        frs_mod.run_checks(snap)

        self.assertEqual(snap, snap_copy, "Snapshot content must not be mutated during audit execution")


if __name__ == "__main__":
    unittest.main()
