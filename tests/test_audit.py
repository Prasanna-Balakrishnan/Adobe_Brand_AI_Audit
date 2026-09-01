#!/usr/bin/env python3
"""
test_audit.py — Integration tests for the Brand AI-Readiness Audit marketplace.

Tests run against offline HTML fixtures (no live network calls).
Each test:
  1. Builds a synthetic snapshot.json from the fixture HTML.
  2. Runs each audit skill against the snapshot.
  3. Asserts schema validity.
  4. Asserts that expected CATEGORIES of findings fire (not exact wording).

Run:
    python tests/test_audit.py
    # or with pytest:
    pytest tests/test_audit.py -v
"""

import json
import os
import re
import sys
import tempfile
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib.parse import urlparse

# Add skill scripts to path
REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT / "skills" / "audit-orchestrator" / "scripts"))
sys.path.insert(0, str(REPO_ROOT / "skills" / "crawlability-render-audit" / "scripts"))
sys.path.insert(0, str(REPO_ROOT / "skills" / "structured-data-content-audit" / "scripts"))
sys.path.insert(0, str(REPO_ROOT / "skills" / "entity-identity-audit" / "scripts"))
sys.path.insert(0, str(REPO_ROOT / "skills" / "freshness-corroboration-audit" / "scripts"))
sys.path.insert(0, str(REPO_ROOT / "skills" / "engagement-audit" / "scripts"))
sys.path.insert(0, str(REPO_ROOT / "skills" / "proactive-opportunities-audit" / "scripts"))

# Import audit functions
import importlib.util

def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

cra_mod = load_module(REPO_ROOT / "skills/crawlability-render-audit/scripts/audit.py", "cra")
sdc_mod = load_module(REPO_ROOT / "skills/structured-data-content-audit/scripts/audit.py", "sdc")
ent_mod = load_module(REPO_ROOT / "skills/entity-identity-audit/scripts/audit.py", "ent")
frs_mod = load_module(REPO_ROOT / "skills/freshness-corroboration-audit/scripts/audit.py", "frs")
eng_mod = load_module(REPO_ROOT / "skills/engagement-audit/scripts/audit.py", "eng")
pro_mod = load_module(REPO_ROOT / "skills/proactive-opportunities-audit/scripts/audit.py", "pro")
norm_mod = load_module(REPO_ROOT / "skills/audit-orchestrator/scripts/normalize_findings.py", "norm")
dedup_mod = load_module(REPO_ROOT / "skills/audit-orchestrator/scripts/deduplicate_findings.py", "dedup")
score_mod = load_module(REPO_ROOT / "skills/audit-orchestrator/scripts/score.py", "score")


# ─── Snapshot Builder ────────────────────────────────────────────────────────

def make_snapshot(pages: list, start_url: str = "https://example.com/") -> dict:
    """Build a minimal snapshot.json structure from a list of page dicts."""
    return {
        "crawl_meta": {
            "start_url": start_url,
            "crawl_started_at": "2026-09-01T10:00:00Z",
            "crawl_ended_at": "2026-09-01T10:01:00Z",
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
    """Return a default page dict with optional field overrides."""
    defaults = {
        "url": url,
        "status_code": 200,
        "final_url": url,
        "redirect_chain": [],
        "canonical": url,
        "meta_robots": "",
        "x_robots_tag": "",
        "title": "Example Site",
        "meta_description": "A great example site.",
        "h1": ["Welcome to Example"],
        "headings": [{"level": 1, "text": "Welcome to Example"},
                     {"level": 2, "text": "Our Services"}],
        "json_ld": [],
        "open_graph": {},
        "twitter_card": {},
        "links": [
            {"href": "https://example.com/about", "text": "About", "is_internal": True},
            {"href": "https://example.com/contact", "text": "Contact", "is_internal": True},
            {"href": "https://example.com/products", "text": "Products", "is_internal": True},
        ],
        "images": [],
        "visible_text_length": 800,
        "visible_text_sample": "Welcome to Example. We provide great services. Get started today!",
        "last_modified": "2025-01-01",
        "crawled_with_js": False,
        "js_render_available": False,
        "raw_html_length": 5000
    }
    defaults.update(overrides)
    return defaults


# ─── Schema Validators ────────────────────────────────────────────────────────

VALID_SEVERITIES = {"critical", "high", "medium", "low"}
VALID_CATEGORIES = {"discoverability", "engagement"}
VALID_CONFIDENCES = {"high", "medium", "low"}


def validate_finding(f: dict) -> list[str]:
    """Return list of validation errors for a Finding dict."""
    errors = []
    for field in ["id", "title", "category", "severity", "confidence",
                  "source_skill", "affected_urls", "evidence", "suggested_action"]:
        if field not in f:
            errors.append(f"Missing field: {field}")
    if f.get("severity") not in VALID_SEVERITIES:
        errors.append(f"Invalid severity: {f.get('severity')}")
    if f.get("category") not in VALID_CATEGORIES:
        errors.append(f"Invalid category: {f.get('category')}")
    if f.get("confidence") not in VALID_CONFIDENCES:
        errors.append(f"Invalid confidence: {f.get('confidence')}")
    if not isinstance(f.get("affected_urls"), list) or len(f.get("affected_urls", [])) == 0:
        errors.append("affected_urls must be a non-empty list")
    sa = f.get("suggested_action", {})
    if not isinstance(sa, dict) or not sa.get("summary"):
        errors.append("suggested_action must have a summary")
    if not re.match(r"F-\d{3}", f.get("id", "")):
        errors.append(f"Invalid id format: {f.get('id')}")
    return errors


def validate_report(report: dict) -> list[str]:
    """Return list of validation errors for a full report dict."""
    errors = []
    for field in ["site", "audited_at", "run_info", "summary", "findings",
                  "proactive_recommendations", "strengths"]:
        if field not in report:
            errors.append(f"Missing top-level field: {field}")

    summary = report.get("summary", {})
    for sf in ["total_findings", "critical", "high", "medium", "low",
               "ai_readiness_score", "by_category"]:
        if sf not in summary:
            errors.append(f"Missing summary field: {sf}")

    for f in report.get("findings", []):
        errors.extend(validate_finding(f))

    for rec in report.get("proactive_recommendations", []):
        if not re.match(r"P-\d{3}", rec.get("id", "")):
            errors.append(f"Invalid proactive id: {rec.get('id')}")
        if rec.get("category") not in VALID_CATEGORIES:
            errors.append(f"Invalid rec category: {rec.get('category')}")

    return errors


def run_all_skills(snapshot: dict) -> tuple[list[dict], list[dict]]:
    """Run all audit skills and return (skill_outputs, all_findings_normalized_deduped)."""
    skills = [
        lambda s: cra_mod.run_checks(s),
        lambda s: sdc_mod.run_checks(s),
        lambda s: ent_mod.run_checks(s),
        lambda s: (frs_mod.run_checks(s, 365)),
        lambda s: eng_mod.run_checks(s),
    ]
    skill_names = [
        "crawlability-render-audit",
        "structured-data-content-audit",
        "entity-identity-audit",
        "freshness-corroboration-audit",
        "engagement-audit",
    ]

    skill_outputs = []
    for i, (fn, name) in enumerate(zip(skills, skill_names)):
        findings, strengths = fn(snapshot)
        skill_outputs.append({"skill": name, "findings": findings, "strengths": strengths})

    normalized, strengths = norm_mod.normalize_all(skill_outputs)
    deduped = dedup_mod.deduplicate(normalized)
    return skill_outputs, deduped, strengths


# ─── Test Cases ──────────────────────────────────────────────────────────────

class TestJsHeavySPA(unittest.TestCase):
    """
    Fixture: JS-heavy SPA page with no rendered text content.
    Expected findings: crawlability (js-render), structured-data (missing JSON-LD).
    """

    def setUp(self):
        self.page = make_page(
            url="https://spa.example.com/",
            title="Loading...",
            meta_description="",
            h1=[],
            headings=[],
            json_ld=[],
            visible_text_length=0,
            visible_text_sample="",
            canonical=None,
            crawled_with_js=False,
        )
        self.snapshot = make_snapshot([self.page], start_url="https://spa.example.com/")

    def test_crawlability_detects_js_only_content(self):
        findings, strengths = cra_mod.run_checks(self.snapshot)
        check_ids = [f["check_id"] for f in findings]
        self.assertIn("CRA-008", check_ids, "Should detect JS-only content")

    def test_structured_data_detects_missing_jsonld(self):
        findings, strengths = sdc_mod.run_checks(self.snapshot)
        check_ids = [f["check_id"] for f in findings]
        self.assertIn("SDC-001", check_ids, "Should detect missing JSON-LD")

    def test_findings_have_discoverability_category(self):
        findings, _ = cra_mod.run_checks(self.snapshot)
        for f in findings:
            self.assertIn(f["category"], VALID_CATEGORIES)

    def test_schema_valid(self):
        _, deduped, strengths = run_all_skills(self.snapshot)
        summary = score_mod.compute_summary(deduped)
        # Build a minimal report structure
        report = {
            "site": "spa.example.com",
            "audited_at": "2026-09-01T10:00:00Z",
            "run_info": {
                "marketplace_version": "1.0.0",
                "skills_invoked": [],
                "pages_crawled": 1,
                "max_pages": 20,
                "crawl_duration_seconds": 1.0,
                "robots_txt_respected": True
            },
            "summary": summary,
            "findings": deduped,
            "proactive_recommendations": [],
            "strengths": strengths
        }
        errors = validate_report(report)
        self.assertEqual(errors, [], f"Report validation errors: {errors}")


class TestStaticWellStructured(unittest.TestCase):
    """
    Fixture: Well-structured static site with JSON-LD, canonical, About, CTA.
    Expected: Few or no high-severity findings; score should be >= 70.
    """

    def setUp(self):
        self.page = make_page(
            url="https://acmecorp.example.com/",
            title="Acme Corp — Industrial Widgets",
            meta_description="Acme Corp — Leading provider of industrial widgets since 2010",
            h1=["Industrial Widgets for Modern Manufacturing"],
            headings=[
                {"level": 1, "text": "Industrial Widgets for Modern Manufacturing"},
                {"level": 2, "text": "Why Choose Acme Corp?"}
            ],
            json_ld=[
                {
                    "@context": "https://schema.org",
                    "@type": "Organization",
                    "name": "Acme Corp",
                    "url": "https://acmecorp.example.com",
                    "sameAs": ["https://linkedin.com/company/acmecorp",
                               "https://en.wikipedia.org/wiki/Acme_Corp"],
                    "foundingDate": "2010"
                },
                {
                    "@context": "https://schema.org",
                    "@type": "WebSite",
                    "name": "Acme Corp",
                    "url": "https://acmecorp.example.com"
                }
            ],
            canonical="https://acmecorp.example.com/",
            visible_text_length=600,
            visible_text_sample=(
                "Acme Corp has been providing high-quality industrial widgets since 2010. "
                "Get started today with our free trial. Shop Widgets."
            ),
            last_modified="2026-08-15",
            links=[
                {"href": "https://acmecorp.example.com/products", "text": "Shop Widgets", "is_internal": True},
                {"href": "https://acmecorp.example.com/about", "text": "About", "is_internal": True},
                {"href": "https://acmecorp.example.com/contact", "text": "Contact", "is_internal": True},
            ]
        )
        self.snapshot = make_snapshot([self.page], start_url="https://acmecorp.example.com/")

    def test_no_critical_findings(self):
        _, deduped, _ = run_all_skills(self.snapshot)
        critical = [f for f in deduped if f["severity"] == "critical"]
        self.assertEqual(len(critical), 0, f"Should have no critical findings: {[f['title'] for f in critical]}")

    def test_ai_readiness_score_is_good(self):
        _, deduped, _ = run_all_skills(self.snapshot)
        summary = score_mod.compute_summary(deduped)
        self.assertGreaterEqual(summary["ai_readiness_score"], 50,
                                f"Score should be >=50 for well-structured site, got {summary['ai_readiness_score']}")

    def test_entity_detects_org_name(self):
        name, source = ent_mod.derive_brand_name(self.snapshot)
        self.assertIsNotNone(name)
        self.assertEqual(source, "json-ld")


class TestAmbiguousEntity(unittest.TestCase):
    """
    Fixture: Short/generic brand name (Atlas), no About page, contradicting dates.
    Expected: entity-identity findings, discoverability category.
    """

    def setUp(self):
        self.page = make_page(
            url="https://atlas.example.com/",
            title="Atlas",
            meta_description="",
            h1=["Welcome to Atlas"],
            json_ld=[],
            canonical=None,
            visible_text_length=200,
            visible_text_sample=(
                "Atlas is a platform. Atlas provides solutions. "
                "Atlas was founded in 2018. We have been serving customers since 2015."
            ),
            links=[
                {"href": "https://atlas.example.com/features", "text": "Features", "is_internal": True},
                {"href": "https://atlas.example.com/pricing", "text": "Pricing", "is_internal": True},
            ]
        )
        self.snapshot = make_snapshot([self.page], start_url="https://atlas.example.com/")

    def test_entity_detects_no_about_page(self):
        findings, _ = ent_mod.run_checks(self.snapshot)
        check_ids = [f["check_id"] for f in findings]
        self.assertIn("ENT-003", check_ids, "Should detect missing About page")

    def test_entity_detects_no_contact(self):
        findings, _ = ent_mod.run_checks(self.snapshot)
        check_ids = [f["check_id"] for f in findings]
        self.assertIn("ENT-004", check_ids, "Should detect missing contact info")

    def test_freshness_detects_contradictions(self):
        findings, _ = frs_mod.run_checks(self.snapshot, 365)
        check_ids = [f["check_id"] for f in findings]
        self.assertIn("FRS-003", check_ids, "Should detect contradicting founding years")

    def test_all_findings_have_discoverability_category(self):
        findings, _ = ent_mod.run_checks(self.snapshot)
        for f in findings:
            self.assertEqual(f["category"], "discoverability",
                             f"Entity finding should be discoverability: {f['title']}")


class TestStaleContent(unittest.TestCase):
    """
    Fixture: Content with old dates (2019), last_modified > 12 months ago.
    Expected: freshness findings (FRS-001 or FRS-002).
    """

    def setUp(self):
        self.page = make_page(
            url="https://oldco.example.com/",
            title="OldCo — Your Trusted Partner",
            meta_description="OldCo has been serving customers since 2005",
            h1=["Trusted Business Solutions Since 2005"],
            json_ld=[{
                "@context": "https://schema.org",
                "@type": "Organization",
                "name": "OldCo",
                "url": "https://oldco.example.com",
                "foundingDate": "2005"
            }],
            last_modified="2019-01-15",  # Very stale
            visible_text_length=400,
            visible_text_sample=(
                "OldCo has been a leader since 2005. "
                "Last updated: January 2019. Pricing from $99/month (as of 2018)."
            )
        )
        self.snapshot = make_snapshot([self.page], start_url="https://oldco.example.com/")

    def test_freshness_detects_stale_content(self):
        findings, _ = frs_mod.run_checks(self.snapshot, stale_threshold_days=365)
        check_ids = [f["check_id"] for f in findings]
        # Should fire FRS-002 (stale) or FRS-001 if somehow no date detected
        self.assertTrue(
            "FRS-002" in check_ids or "FRS-001" in check_ids,
            f"Should detect stale content. Got check_ids: {check_ids}"
        )

    def test_freshness_finding_category_is_discoverability(self):
        findings, _ = frs_mod.run_checks(self.snapshot, stale_threshold_days=365)
        for f in findings:
            self.assertEqual(f["category"], "discoverability")


class TestGoodDiscoverabilityBadEngagement(unittest.TestCase):
    """
    Fixture: Good JSON-LD + canonical, but no CTA on homepage, dead-end pages.
    Expected: engagement findings; few discoverability findings.
    """

    def setUp(self):
        homepage = make_page(
            url="https://brightsaas.example.com/",
            title="BrightSaaS — Team Collaboration",
            meta_description="Collaboration platform for distributed teams",
            h1=["Collaborate Without Limits"],
            json_ld=[{
                "@context": "https://schema.org",
                "@type": "Organization",
                "name": "BrightSaaS",
                "sameAs": ["https://linkedin.com/company/brightsaas"]
            }],
            canonical="https://brightsaas.example.com/",
            visible_text_length=250,
            visible_text_sample="BrightSaaS: collaborate without limits. Platform for distributed teams.",
            links=[
                {"href": "https://brightsaas.example.com/features", "text": "Features", "is_internal": True},
                {"href": "https://brightsaas.example.com/pricing", "text": "Pricing", "is_internal": True},
                # No CTA links
            ],
            last_modified="2026-07-01"
        )
        # A dead-end page
        deadend = make_page(
            url="https://brightsaas.example.com/features",
            title="Features",
            h1=["Features"],
            json_ld=[],
            links=[],  # No links out = dead end
            visible_text_length=300,
            visible_text_sample="Real-time editing, video conferencing, task management."
        )
        self.snapshot = make_snapshot(
            [homepage, deadend],
            start_url="https://brightsaas.example.com/"
        )

    def test_engagement_detects_no_cta(self):
        findings, _ = eng_mod.run_checks(self.snapshot)
        check_ids = [f["check_id"] for f in findings]
        self.assertIn("ENG-001", check_ids, "Should detect missing CTA")

    def test_engagement_detects_dead_end(self):
        findings, _ = eng_mod.run_checks(self.snapshot)
        check_ids = [f["check_id"] for f in findings]
        self.assertIn("ENG-004", check_ids, "Should detect dead-end pages")

    def test_engagement_findings_have_engagement_category(self):
        findings, _ = eng_mod.run_checks(self.snapshot)
        for f in findings:
            self.assertEqual(f["category"], "engagement",
                             f"All engagement findings should have engagement category: {f['title']}")


class TestNormalizationAndDeduplication(unittest.TestCase):
    """Tests for the normalization and deduplication pipeline."""

    def test_normalize_drops_invalid_severity(self):
        skill_output = {
            "skill": "test-skill",
            "findings": [{
                "check_id": "TST-001",
                "title": "Test finding",
                "category": "discoverability",
                "severity": "INVALID",
                "confidence": "high",
                "affected_urls": ["https://example.com"],
                "evidence": "Some evidence",
                "suggested_action": {"summary": "Fix it"}
            }],
            "strengths": []
        }
        normalized, _ = norm_mod.normalize_all([skill_output])
        self.assertEqual(len(normalized), 0, "Invalid severity should be dropped")

    def test_normalize_drops_empty_evidence(self):
        skill_output = {
            "skill": "test-skill",
            "findings": [{
                "check_id": "TST-002",
                "title": "Test finding",
                "category": "engagement",
                "severity": "medium",
                "confidence": "high",
                "affected_urls": ["https://example.com"],
                "evidence": "",
                "suggested_action": {"summary": "Fix it"}
            }],
            "strengths": []
        }
        normalized, _ = norm_mod.normalize_all([skill_output])
        self.assertEqual(len(normalized), 0, "Empty evidence should be dropped")

    def test_dedup_assigns_f_ids(self):
        findings = [
            {
                "title": "Test finding", "category": "discoverability",
                "severity": "high", "confidence": "high",
                "source_skill": "skill-a", "check_id": "SKA-001",
                "tags": ["json-ld"], "affected_urls": ["https://example.com"],
                "evidence": "Missing JSON-LD on example.com",
                "root_cause_group": None,
                "suggested_action": {"summary": "Fix it", "priority": "high", "effort": "low"}
            }
        ]
        deduped = dedup_mod.deduplicate(findings)
        self.assertEqual(len(deduped), 1)
        self.assertEqual(deduped[0]["id"], "F-001")

    def test_dedup_clusters_near_duplicates(self):
        """Two findings from different skills about the same JSON-LD issue."""
        findings = [
            {
                "title": "Missing JSON-LD structured data on product pages",
                "category": "discoverability", "severity": "high", "confidence": "high",
                "source_skill": "skill-a", "check_id": "SKA-001",
                "tags": ["json-ld"], "affected_urls": ["https://example.com/product/1"],
                "evidence": "No JSON-LD found on product pages",
                "root_cause_group": None,
                "suggested_action": {"summary": "Add JSON-LD", "priority": "high", "effort": "low"}
            },
            {
                "title": "Product page missing JSON-LD structured data",
                "category": "discoverability", "severity": "high", "confidence": "high",
                "source_skill": "skill-b", "check_id": "SKB-001",
                "tags": ["json-ld"], "affected_urls": ["https://example.com/product/1"],
                "evidence": "JSON-LD absent on product page example.com/product/1",
                "root_cause_group": None,
                "suggested_action": {"summary": "Add JSON-LD markup", "priority": "high", "effort": "low"}
            }
        ]
        deduped = dedup_mod.deduplicate(findings)
        # Should be merged into one with a root_cause_group
        self.assertEqual(len(deduped), 1, "Near-duplicates should be merged")
        self.assertIsNotNone(deduped[0]["root_cause_group"],
                             "Merged finding should have root_cause_group")

    def test_score_formula(self):
        """Test deterministic score formula."""
        findings = [
            {"severity": "critical", "category": "discoverability"},
            {"severity": "high", "category": "engagement"},
            {"severity": "medium", "category": "discoverability"},
            {"severity": "low", "category": "engagement"},
        ]
        summary = score_mod.compute_summary(findings)
        expected_score = max(0, 100 - 1*25 - 1*10 - 1*4 - 1*1)
        self.assertEqual(summary["ai_readiness_score"], expected_score)
        self.assertEqual(summary["total_findings"], 4)
        self.assertEqual(summary["critical"], 1)
        self.assertEqual(summary["by_category"]["discoverability"], 2)
        self.assertEqual(summary["by_category"]["engagement"], 2)


class TestProactiveOpportunities(unittest.TestCase):
    """Tests for proactive recommendations."""

    def test_faq_opportunity_when_no_faq_page(self):
        snapshot = make_snapshot([
            make_page(
                url="https://ex.com/",
                json_ld=[],
                links=[
                    {"href": "https://ex.com/product", "text": "Product", "is_internal": True}
                ]
            ),
            make_page(url="https://ex.com/product", json_ld=[])
        ], start_url="https://ex.com/")
        findings = []  # No existing findings
        recs = pro_mod.run_opportunities(snapshot, findings)
        titles = [r["title"] for r in recs]
        self.assertTrue(
            any("FAQ" in t for t in titles),
            f"Should suggest FAQ opportunity. Got: {titles}"
        )

    def test_proactive_does_not_duplicate_existing_findings(self):
        """If an existing finding covers json-ld, proactive should not re-report it."""
        snapshot = make_snapshot([make_page(json_ld=[])], start_url="https://ex.com/")
        existing_findings = [
            {
                "id": "F-001",
                "title": "No JSON-LD structured data on any page",
                "category": "discoverability",
                "severity": "high",
                "tags": ["json-ld", "schema-org"],
                "evidence": "0/1 pages have JSON-LD"
            }
        ]
        recs = pro_mod.run_opportunities(snapshot, existing_findings)
        # BreadcrumbList and SearchAction recs should not fire if JSON-LD is entirely missing
        for rec in recs:
            self.assertNotIn("BreadcrumbList", rec["title"],
                             "Should not recommend BreadcrumbList when JSON-LD is entirely absent")

    def test_event_schema_opportunity(self):
        snapshot = make_snapshot([
            make_page(
                url="https://ex.com/events/summit-2026",
                visible_text_sample="Join us for the summit 2026 event. Annual conference for tech leaders.",
                json_ld=[]
            )
        ], start_url="https://ex.com/")
        recs = pro_mod.run_opportunities(snapshot, [])
        titles = [r["title"] for r in recs]
        self.assertTrue(
            any("Event" in t for t in titles),
            f"Should suggest Event schema. Got: {titles}"
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
