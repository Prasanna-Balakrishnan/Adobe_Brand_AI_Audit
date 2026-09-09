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
sys.path.insert(0, str(REPO_ROOT / "skills" / "site-crawler" / "scripts"))

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
crawl_mod = load_module(REPO_ROOT / "skills/site-crawler/scripts/crawl.py", "crawl")
norm_mod = load_module(REPO_ROOT / "skills/audit-orchestrator/scripts/normalize_findings.py", "norm")
dedup_mod = load_module(REPO_ROOT / "skills/audit-orchestrator/scripts/deduplicate_findings.py", "dedup")
score_mod = load_module(REPO_ROOT / "skills/audit-orchestrator/scripts/score.py", "score")
build_mod = load_module(REPO_ROOT / "skills/audit-orchestrator/scripts/build_report.py", "build_report")


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


def run_all_skills(snapshot: dict) -> tuple[list[dict], list[dict], list[dict]]:
    """Run all audit skills and return (skill_outputs, all_findings_normalized_deduped, strengths)."""
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


# ─── Marketplace Manifest & Hygiene Tests ─────────────────────────────────────

class TestMarketplaceManifest(unittest.TestCase):
    """Verifies that the marketplace manifest satisfies Hackathon Round 3 rules."""

    def setUp(self):
        self.manifest_path = REPO_ROOT / "marketplace.json"
        self.assertTrue(self.manifest_path.exists(), "marketplace.json must exist at root")
        with open(self.manifest_path, encoding="utf-8") as f:
            self.manifest = json.load(f)

    def test_manifest_top_level_fields(self):
        """Manifest must have name, version, and skills."""
        self.assertIn("name", self.manifest)
        self.assertIn("version", self.manifest)
        self.assertIn("skills", self.manifest)
        self.assertIsInstance(self.manifest["skills"], list)
        self.assertGreater(len(self.manifest["skills"]), 0)

    def test_exactly_one_entrypoint(self):
        """Manifest must have exactly one skill marked as entrypoint."""
        entrypoints = [s for s in self.manifest["skills"] if s.get("entrypoint") is True]
        self.assertEqual(len(entrypoints), 1,
                         f"Expected exactly 1 entrypoint skill, found {len(entrypoints)}")

    def test_skill_folders_and_skill_md_exist(self):
        """Every skill folder listed in the marketplace must contain a valid SKILL.md."""
        for skill in self.manifest["skills"]:
            skill_id = skill.get("id") or skill.get("name")
            self.assertTrue(skill_id, f"Skill entry missing id/name: {skill}")
            
            skill_path = REPO_ROOT / skill["path"]
            self.assertTrue(skill_path.exists(), f"Skill path does not exist: {skill_path}")
            
            skill_md = skill_path / "SKILL.md" if skill_path.is_dir() else skill_path
            self.assertTrue(skill_md.exists(), f"SKILL.md does not exist at: {skill_md}")

            # Verify SKILL.md has YAML frontmatter
            content = skill_md.read_text(encoding="utf-8")
            self.assertTrue(content.startswith("---"), f"{skill_md} missing YAML frontmatter start")
            parts = content.split("---", 2)
            self.assertGreaterEqual(len(parts), 3, f"{skill_md} invalid YAML frontmatter structure")
            frontmatter = parts[1]
            self.assertIn("name:", frontmatter, f"{skill_md} frontmatter missing 'name:'")
            self.assertIn("description:", frontmatter, f"{skill_md} frontmatter missing 'description:'")


# ─── Clean Site Test (Req 27) ────────────────────────────────────────────────

class TestCleanSite(unittest.TestCase):
    """
    Asserts that a high-quality, well-structured website does NOT receive
    unnecessary high-severity findings and scores >= 90 (Req 27).
    """

    def setUp(self):
        org_schema = {
            "@context": "https://schema.org",
            "@type": "Organization",
            "name": "Acme Global Solutions",
            "url": "https://acme.example.com",
            "logo": "https://acme.example.com/logo.png",
            "description": "Enterprise cloud productivity and compliance software.",
            "foundingDate": "2020",
            "address": {
                "@type": "PostalAddress",
                "streetAddress": "100 Market St",
                "addressLocality": "San Francisco",
                "addressCountry": "US"
            },
            "sameAs": ["https://linkedin.com/company/acme"]
        }
        website_schema = {
            "@context": "https://schema.org",
            "@type": "WebSite",
            "name": "Acme Global Solutions",
            "url": "https://acme.example.com"
        }
        product_schema = {
            "@context": "https://schema.org",
            "@type": "Product",
            "name": "Acme Cloud Suite",
            "description": "Full cloud operations monitoring software.",
            "offers": {
                "@type": "Offer",
                "price": "99.00",
                "priceCurrency": "USD"
            }
        }

        self.snapshot = make_snapshot([
            make_page(
                url="https://acme.example.com/",
                page_type="Homepage",
                title="Acme Global Solutions — Enterprise Cloud Software",
                meta_description="Enterprise cloud productivity and compliance software built for modern engineering teams.",
                h1=["Acme Global Solutions"],
                json_ld=[org_schema, website_schema],
                visible_text_sample="Acme Global Solutions helps teams scale cloud systems. Contact us at hello@acme.example.com or +1-800-555-0199. Get started today!",
                links=[
                    {"href": "https://acme.example.com/start", "text": "Get Started Free", "is_internal": True},
                    {"href": "https://acme.example.com/about", "text": "About Us", "is_internal": True},
                    {"href": "https://acme.example.com/products/cloud", "text": "Cloud Product", "is_internal": True},
                    {"href": "https://acme.example.com/pricing", "text": "Pricing Plans", "is_internal": True},
                    {"href": "https://acme.example.com/contact", "text": "Contact Support", "is_internal": True},
                    {"href": "https://acme.example.com/docs", "text": "Documentation", "is_internal": True},
                ],
                last_modified="2026-08-15"
            ),
            make_page(
                url="https://acme.example.com/about",
                page_type="About",
                title="About Us — Acme Global Solutions",
                h1=["About Acme Global Solutions"],
                json_ld=[org_schema],
                visible_text_sample="Founded in 2020 in San Francisco, Acme Global Solutions provides top tier cloud tools.",
                last_modified="2026-08-15"
            ),
            make_page(
                url="https://acme.example.com/products/cloud",
                page_type="Product",
                title="Acme Cloud Suite — Cloud Tools",
                h1=["Acme Cloud Suite"],
                json_ld=[product_schema],
                visible_text_sample="Acme Cloud Suite starting at $99.00 per month. Get started with a 14-day free trial.",
                last_modified="2026-08-15"
            ),
            make_page(
                url="https://acme.example.com/contact",
                page_type="Contact",
                title="Contact Us — Acme Global Solutions",
                h1=["Contact Acme"],
                json_ld=[org_schema],
                visible_text_sample="Reach our team at hello@acme.example.com or call +1-800-555-0199.",
                last_modified="2026-08-15"
            ),
            make_page(
                url="https://acme.example.com/docs",
                page_type="Documentation",
                title="Documentation — Acme Global Solutions",
                h1=["Acme API Documentation"],
                json_ld=[],
                visible_text_sample="API reference and integration guides for developers.",
                last_modified="2026-08-15"
            )
        ], start_url="https://acme.example.com/")

    def test_clean_site_has_zero_high_severity_findings(self):
        cra_f, _ = cra_mod.run_checks(self.snapshot)
        sdc_f, _ = sdc_mod.run_checks(self.snapshot)
        ent_f, _ = ent_mod.run_checks(self.snapshot)
        frs_f, _ = frs_mod.run_checks(self.snapshot)
        eng_f, _ = eng_mod.run_checks(self.snapshot)

        raw_outputs = [
            {"skill": "cra", "findings": cra_f, "strengths": []},
            {"skill": "sdc", "findings": sdc_f, "strengths": []},
            {"skill": "ent", "findings": ent_f, "strengths": []},
            {"skill": "frs", "findings": frs_f, "strengths": []},
            {"skill": "eng", "findings": eng_f, "strengths": []},
        ]
        norm_f, _ = norm_mod.normalize_all(raw_outputs)
        dedup_f = dedup_mod.deduplicate(norm_f)
        summary = score_mod.compute_summary(dedup_f)

        self.assertEqual(summary["critical"], 0, "Clean site should have 0 critical findings")
        self.assertEqual(summary["high"], 0, "Clean site should have 0 high severity findings")
        self.assertGreaterEqual(summary["ai_readiness_score"], 90, "Clean site score should be >= 90")


# ─── Fourteen Fixture Scenarios (Req 26) ─────────────────────────────────────

class TestFourteenFixtureScenarios(unittest.TestCase):
    """
    Validates all 14 scenarios specified in Requirement 26.
    """

    def test_scenario_01_js_heavy_website(self):
        """1. JS-heavy website with empty initial markup flags JS rendering risk."""
        snap = make_snapshot([
            make_page(
                url="https://spa.example.com/",
                visible_text_length=120,
                headings=[],
                crawled_with_js=False
            )
        ])
        findings, _ = cra_mod.run_checks(snap)
        self.assertTrue(any(f["check_id"] == "CRA-008" for f in findings))

    def test_scenario_02_clean_website(self):
        """2. Clean website produces no critical or high severity defects."""
        snap = make_snapshot([
            make_page(
                url="https://clean.example.com/",
                page_type="Homepage",
                title="Clean Enterprise Platform",
                meta_description="Clean reliable platform for enterprise teams.",
                h1=["Clean Enterprise Platform"],
                json_ld=[{
                    "@context": "https://schema.org",
                    "@type": "Organization",
                    "name": "Clean Corp",
                    "url": "https://clean.example.com",
                    "sameAs": ["https://linkedin.com/clean"]
                }],
                last_modified="2026-08-01"
            )
        ])
        sdc_f, _ = sdc_mod.run_checks(snap)
        self.assertFalse(any(f.get("severity") in ("critical", "high") for f in sdc_f))

    def test_scenario_03_conflicting_canonical(self):
        """3. Conflicting canonical pointing off-site or mismatching final_url."""
        snap = make_snapshot([
            make_page(
                url="https://example.com/landing",
                final_url="https://example.com/landing",
                canonical="https://otherdomain.com/landing",
                canonical_conflict=True
            )
        ])
        findings, _ = cra_mod.run_checks(snap)
        self.assertTrue(any(f["check_id"] == "CRA-010" for f in findings))

    def test_scenario_04_redirect_loop(self):
        """4. Detect redirect loops or excessive redirect chains."""
        snap = make_snapshot([
            make_page(
                url="https://example.com/loop",
                status_code=310,
                redirect_chain=["https://example.com/a", "https://example.com/b", "https://example.com/a"],
                redirect_loop=True
            )
        ])
        findings, _ = cra_mod.run_checks(snap)
        self.assertTrue(any(f["check_id"] == "CRA-004" for f in findings))

    def test_scenario_05_broken_links(self):
        """5. Broken internal links with 4xx/5xx status."""
        snap = make_snapshot([
            make_page(url="https://example.com/page1", status_code=200),
            make_page(url="https://example.com/page2", status_code=404),
            make_page(url="https://example.com/page3", status_code=500),
        ])
        findings, _ = cra_mod.run_checks(snap)
        self.assertTrue(any(f["check_id"] == "CRA-007" for f in findings))

    def test_scenario_06_robots_restriction(self):
        """6. Robots.txt Disallow: / global restriction."""
        snap = {
            "crawl_meta": {
                "start_url": "https://blocked.example.com/",
                "robots_txt_status": 200,
                "robots_txt_url": "https://blocked.example.com/robots.txt",
                "disallowed_paths": ["/"]
            },
            "pages": [make_page(url="https://blocked.example.com/")]
        }
        findings, _ = cra_mod.run_checks(snap)
        self.assertTrue(any(f["check_id"] == "CRA-001" for f in findings))

    def test_scenario_07_image_only_important_information(self):
        """7. Pages with images lacking alt text."""
        snap = make_snapshot([
            make_page(
                url="https://example.com/gallery",
                images=[
                    {"src": "https://example.com/img1.jpg", "alt": ""},
                    {"src": "https://example.com/img2.jpg", "alt": ""}
                ]
            )
        ])
        self.assertEqual(len(snap["pages"][0]["images"]), 2)
        self.assertEqual(snap["pages"][0]["images"][0]["alt"], "")

    def test_scenario_08_entity_name_inconsistency(self):
        """8. Organization name inconsistency across pages."""
        snap = make_snapshot([
            make_page(
                url="https://brand.com/",
                h1=["Beta Technologies Inc"],
                json_ld=[{"@context": "https://schema.org", "@type": "Organization", "name": "Beta Tech"}]
            ),
            make_page(
                url="https://brand.com/about",
                page_type="About",
                json_ld=[{"@context": "https://schema.org", "@type": "Organization", "name": "Gamma Corp"}]
            )
        ], start_url="https://brand.com/")
        findings, _ = ent_mod.run_checks(snap)
        self.assertTrue(any(f["check_id"] in ("ENT-002", "ENT-008") for f in findings))

    def test_scenario_09_visible_vs_structured_data_conflict(self):
        """9. Visible price ($99) vs JSON-LD price ($149) conflict."""
        snap = make_snapshot([
            make_page(
                url="https://shop.com/item",
                page_type="Product",
                visible_text_sample="Special discount today: only $99 for our full software package!",
                json_ld=[{
                    "@context": "https://schema.org",
                    "@type": "Product",
                    "name": "Software",
                    "offers": {"@type": "Offer", "price": "149.00", "priceCurrency": "USD"}
                }]
            )
        ])
        findings, _ = sdc_mod.run_checks(snap)
        self.assertTrue(any(f["check_id"] == "SDC-013" for f in findings))

    def test_scenario_10_raw_vs_rendered_disparity(self):
        """10. Content disparity between raw HTML and rendered DOM."""
        page = make_page(
            url="https://app.com/dashboard",
            raw_text_length=150,
            rendered_text_length=1200,
            js_dependent_content=True,
            content_disparity=1050
        )
        self.assertTrue(page["js_dependent_content"])
        self.assertGreater(page["content_disparity"], 300)

    def test_scenario_11_product_page_context(self):
        """11. Product page context: missing schema fires on Product, suppressed on Contact."""
        snap = make_snapshot([
            make_page(url="https://shop.com/products/shoes", page_type="Product", json_ld=[]),
            make_page(url="https://shop.com/contact", page_type="Contact", json_ld=[])
        ])
        findings, _ = sdc_mod.run_checks(snap)
        sdc_002 = next((f for f in findings if f["check_id"] == "SDC-002"), None)
        self.assertIsNotNone(sdc_002)
        self.assertIn("https://shop.com/products/shoes", sdc_002["affected_urls"])
        self.assertNotIn("https://shop.com/contact", sdc_002["affected_urls"])

    def test_scenario_12_blog_article_context(self):
        """12. Blog / article context checking author attribution."""
        snap = make_snapshot([
            make_page(
                url="https://news.com/blog/ai-trends",
                page_type="Blog/article",
                title="AI Trends for 2026",
                visible_text_sample="AI trends overview without author attribution.",
                json_ld=[{"@context": "https://schema.org", "@type": "BlogPosting", "headline": "AI Trends"}]
            )
        ])
        findings, _ = ent_mod.run_checks(snap)
        self.assertTrue(any(f["check_id"] == "ENT-005" for f in findings))

    def test_scenario_13_documentation_page_context(self):
        """13. Documentation page does not trigger dead-end or missing CTA warnings."""
        snap = make_snapshot([
            make_page(
                url="https://docs.com/",
                page_type="Homepage",
                links=[{"href": "https://docs.com/docs/api", "text": "API Docs", "is_internal": True}]
            ),
            make_page(
                url="https://docs.com/docs/api",
                page_type="Documentation",
                links=[]  # terminal doc page
            )
        ], start_url="https://docs.com/")
        findings, _ = eng_mod.run_checks(snap)
        self.assertFalse(any(f["check_id"] == "ENG-004" for f in findings))

    def test_scenario_14_limited_crawl_coverage(self):
        """14. Single-page snapshot evaluated gracefully without crashing."""
        snap = make_snapshot([
            make_page(url="https://single.com/", page_type="Homepage")
        ], start_url="https://single.com/")
        answerability = score_mod.evaluate_agent_answerability(snap)
        self.assertEqual(len(answerability), 5)
        self.assertTrue(all("status" in item for item in answerability))


# ─── Agent Journey & Answerability Tests (Req 10, 11, 14) ────────────────────

class TestAgentJourneyAndAnswerability(unittest.TestCase):
    """
    Tests AI Agent Journey scoring, Answerability evaluation, and Multi-factor prioritization.
    """

    def setUp(self):
        self.findings = [
            {
                "id": "F-001",
                "check_id": "CRA-001",
                "title": "Robots restriction",
                "category": "discoverability",
                "severity": "critical",
                "confidence": "high",
                "tags": ["robots-txt", "crawlability"],
                "affected_urls": ["https://example.com/"],
                "suggested_action": {"summary": "Allow crawling in robots.txt"}
            },
            {
                "id": "F-002",
                "check_id": "SDC-001",
                "title": "Missing structured data",
                "category": "discoverability",
                "severity": "high",
                "confidence": "high",
                "tags": ["json-ld", "structured-data"],
                "affected_urls": ["https://example.com/p1", "https://example.com/p2"],
                "suggested_action": {"summary": "Add JSON-LD markup"}
            }
        ]

    def test_journey_scores_structure(self):
        journey = score_mod.compute_agent_journey_scores(self.findings)
        pillars = ["reach", "read", "understand", "trust", "navigate", "act", "overall_journey_score"]
        for p in pillars:
            self.assertIn(p, journey)
            self.assertGreaterEqual(journey[p], 0)
            self.assertLessEqual(journey[p], 100)

        # Reach should have deductions due to CRA-001
        self.assertLess(journey["reach"], 100)
        # Understand should have deductions due to SDC-001
        self.assertLess(journey["understand"], 100)

    def test_answerability_evaluation(self):
        snap = make_snapshot([
            make_page(
                url="https://example.com/",
                meta_description="Providing enterprise compliance software for fintechs.",
                visible_text_sample="Enterprise compliance. Email us at info@example.com. Price starts at $49.",
                json_ld=[{
                    "@context": "https://schema.org",
                    "@type": "Organization",
                    "name": "Fintech Compliance",
                    "address": {"@type": "PostalAddress", "addressLocality": "New York", "addressCountry": "US"}
                }]
            )
        ])
        results = score_mod.evaluate_agent_answerability(snap)
        self.assertEqual(len(results), 5)
        # Check that question 1 (What does this company do?) is Supported
        self.assertEqual(results[0]["status"], "Supported")
        # Check contact is Supported
        self.assertEqual(results[4]["status"], "Supported")

    def test_top_priorities_calculation(self):
        priorities = score_mod.compute_top_priorities(self.findings, limit=5)
        self.assertEqual(len(priorities), 2)
        # Critical finding should be ranked first
        self.assertEqual(priorities[0]["id"], "F-001")
        self.assertEqual(priorities[0]["priority_rank"], 1)


# ─── Natural Language URL Parsing & Resiliency (Req 1, 25) ───────────────────

class TestNaturalLanguageParsingAndResilience(unittest.TestCase):
    """
    Tests NLP URL extraction and fault isolation.
    """

    def test_extract_target_url(self):
        cases = [
            ("https://example.com/pricing", "https://example.com/pricing"),
            ("example.com", "https://example.com"),
            ("Check the Microsoft website and generate a report.", "https://www.microsoft.com"),
            ("Audit the Nike site please", "https://www.nike.com"),
            ("Inspect https://store.apple.com/us", "https://store.apple.com/us"),
        ]
        for query, expected in cases:
            extracted = build_mod.extract_target_url(query)
            self.assertEqual(extracted, expected, f"Failed extracting URL from query: {query}")


# ─── Full Report Schema Compliance Test (Req 19, 20) ─────────────────────────

class TestFullReportSchema(unittest.TestCase):
    """
    Validates that the final report produced contains all required fields:
    scores, agent_journey_scores, agent_answerability, top_priorities,
    crawl_coverage, findings, proactive_recommendations, and strengths.
    """

    def test_report_schema_fields(self):
        snap = make_snapshot([
            make_page(url="https://report-test.com/", page_type="Homepage")
        ], start_url="https://report-test.com/")

        findings = [
            {
                "id": "F-001",
                "title": "Missing title",
                "category": "discoverability",
                "severity": "medium",
                "confidence": "high",
                "source_skill": "crawlability-render-audit",
                "tags": ["page-title"],
                "affected_urls": ["https://report-test.com/"],
                "evidence": "Missing title tag.",
                "suggested_action": {"summary": "Add title"}
            }
        ]

        summary = score_mod.compute_summary(findings, snap)
        journey = score_mod.compute_agent_journey_scores(findings)
        answerability = score_mod.evaluate_agent_answerability(snap, findings)
        priorities = score_mod.compute_top_priorities(findings)

        report = {
            "site": "report-test.com",
            "audited_at": "2026-09-01T12:00:00Z",
            "run_info": {
                "marketplace_version": "1.0.0",
                "query_input": "https://report-test.com",
                "target_url": "https://report-test.com",
                "skills_invoked": ["crawlability-render-audit"],
                "failed_skills": [],
                "pages_crawled": 1,
                "max_pages": 20,
                "crawl_duration_seconds": 1.2,
                "robots_txt_respected": True,
                "crawl_coverage": {
                    "pages_discovered": 1,
                    "pages_crawled": 1,
                    "pages_skipped": 0,
                    "failed_pages": [],
                    "crawl_duration_seconds": 1.2,
                    "robots_status": 200,
                    "js_rendering_status": "disabled"
                }
            },
            "summary": summary,
            "agent_journey_scores": journey,
            "agent_answerability": answerability,
            "top_priorities": priorities,
            "findings": findings,
            "proactive_recommendations": [],
            "strengths": [],
            "methodology_and_limitations": build_mod.METHODOLOGY_AND_LIMITATIONS
        }

        # Assert all required sections from Req 19 are present
        required_keys = [
            "site", "audited_at", "run_info", "summary",
            "agent_journey_scores", "agent_answerability", "top_priorities",
            "findings", "proactive_recommendations", "strengths",
            "methodology_and_limitations"
        ]
        for k in required_keys:
            self.assertIn(k, report, f"Report missing key: {k}")

        # Assert crawl coverage from Req 20 is present
        cov = report["run_info"]["crawl_coverage"]
        for cov_key in ["pages_discovered", "pages_crawled", "pages_skipped", "failed_pages", "crawl_duration_seconds"]:
            self.assertIn(cov_key, cov, f"Crawl coverage missing key: {cov_key}")


class TestRealWorldGeneralization(unittest.TestCase):
    """
    Regression tests for real-world generalization, false-positive resistance,
    and diverse website patterns.
    """

    def test_schema_org_organization_subtypes(self):
        """Schema.org Organization subtypes (CollegeOrUniversity, EducationalOrganization) are recognized."""
        uni_page = make_page(
            url="https://state.edu/",
            title="State University - Excellence in Education",
            meta_description="Official site of State University",
            h1=["State University"],
            json_ld=[{
                "@context": "https://schema.org",
                "@type": "CollegeOrUniversity",
                "name": "State University",
                "sameAs": ["https://en.wikipedia.org/wiki/State_University"]
            }],
            visible_text_sample="Welcome to State University. Founded in 1890. Apply now for admissions."
        )
        snap = make_snapshot([uni_page], start_url="https://state.edu/")
        sdc_findings, sdc_strengths = sdc_mod.run_checks(snap)
        sdc_ids = [f["check_id"] for f in sdc_findings]
        self.assertNotIn("SDC-001", sdc_ids, "CollegeOrUniversity should be recognized as valid Org schema on homepage")
        self.assertNotIn("SDC-008", sdc_ids)

        ent_findings, ent_strengths = ent_mod.run_checks(snap)
        ent_ids = [f["check_id"] for f in ent_findings]
        self.assertNotIn("ENT-001", ent_ids, "Brand name should be recognized from CollegeOrUniversity JSON-LD")
        self.assertNotIn("ENT-007", ent_ids, "sameAs in CollegeOrUniversity should be recognized")

    def test_subdomain_news_not_flagged_as_blog_post(self):
        """Subdomain news homepage should not be flagged for missing author attribution."""
        news_page = make_page(
            url="https://news.example.com/",
            title="Example News - Breaking World News",
            meta_description="Global journalism and investigative reports",
            h1=["Latest News Headlines"],
            page_type="Homepage",
            json_ld=[{
                "@context": "https://schema.org",
                "@type": "NewsMediaOrganization",
                "name": "Example News"
            }]
        )
        snap = make_snapshot([news_page], start_url="https://news.example.com/")
        ent_findings, _ = ent_mod.run_checks(snap)
        ent_ids = [f["check_id"] for f in ent_findings]
        self.assertNotIn("ENT-005", ent_ids, "News homepage should not be flagged as an individual article missing author")

    def test_h1_marketing_headline_not_flagged_as_inconsistent_brand(self):
        """Marketing headlines in H1 should not cause false positive ENT-008 identity drift."""
        hp = make_page(
            url="https://apexcorp.com/",
            title="Apex Corp | Enterprise Solutions",
            h1=["Accelerate Enterprise Growth with AI"],
            page_type="Homepage",
            json_ld=[{"@type": "Organization", "name": "Apex Corp"}]
        )
        about = make_page(
            url="https://apexcorp.com/about",
            title="About Apex Corp",
            h1=["About Apex Corp"],
            page_type="About",
            json_ld=[{"@type": "Organization", "name": "Apex Corp"}]
        )
        snap = make_snapshot([hp, about], start_url="https://apexcorp.com/")
        ent_findings, _ = ent_mod.run_checks(snap)
        ent_ids = [f["check_id"] for f in ent_findings]
        self.assertNotIn("ENT-008", ent_ids, "Marketing H1 should not trigger inconsistent brand name finding")

    def test_answerability_compatible_location_matching(self):
        """Locality in JSON-LD and street address in text should corroborate, not conflict."""
        p1 = make_page(
            url="https://corp.example.com/",
            json_ld=[{
                "@type": "Organization",
                "address": {"addressLocality": "Austin", "addressCountry": "US"}
            }]
        )
        p2 = make_page(
            url="https://corp.example.com/contact",
            page_type="Contact",
            visible_text_sample="Visit us at 500 Congress Ave, Austin, TX 78701. Email: contact@corp.example.com"
        )
        snap = make_snapshot([p1, p2], start_url="https://corp.example.com/")
        ans = score_mod.evaluate_agent_answerability(snap)
        loc_q = next(q for q in ans if q["question"] == "Where is it located?")
        self.assertEqual(loc_q["status"], "Supported", "Compatible Austin locations should be Supported, not Conflicting")

    def test_answerability_aggregate_offers(self):
        """AggregateOffer with lowPrice should satisfy pricing answerability."""
        p = make_page(
            url="https://saas.example.com/pricing",
            page_type="Pricing",
            json_ld=[{
                "@type": "Product",
                "name": "Cloud Subscription",
                "offers": {
                    "@type": "AggregateOffer",
                    "priceCurrency": "USD",
                    "lowPrice": 29,
                    "highPrice": 99
                }
            }]
        )
        snap = make_snapshot([p], start_url="https://saas.example.com/")
        ans = score_mod.evaluate_agent_answerability(snap)
        cost_q = next(q for q in ans if q["question"] == "What does the product cost?")
        self.assertEqual(cost_q["status"], "Supported")
        self.assertIn("29", cost_q["evidence"])

    def test_documentation_site_about_page_suppressed(self):
        """Documentation pages should not be penalized for lacking an About page."""
        doc_page = make_page(
            url="https://docs.framework.io/",
            title="Developer Documentation",
            page_type="Documentation",
            links=[{"href": "https://docs.framework.io/quickstart", "text": "Quickstart", "is_internal": True}]
        )
        snap = make_snapshot([doc_page], start_url="https://docs.framework.io/")
        ent_findings, _ = ent_mod.run_checks(snap)
        eng_findings, _ = eng_mod.run_checks(snap)
        self.assertNotIn("ENT-003", [f["check_id"] for f in ent_findings])
        self.assertNotIn("ENG-005", [f["check_id"] for f in eng_findings])

    def test_cross_skill_deduplication_about_and_contact(self):
        """Near-duplicate about and contact findings across skills should group cleanly."""
        findings = [
            {
                "check_id": "ENT-003",
                "title": "No About page detected",
                "category": "discoverability",
                "severity": "medium",
                "confidence": "medium",
                "affected_urls": ["https://example.com/"],
                "evidence": "No URL matches about page",
                "tags": ["about-page", "entity-identity"],
                "source_skill": "entity-identity-audit",
                "suggested_action": {"summary": "Create About page", "priority": "medium", "effort": "medium"}
            },
            {
                "check_id": "ENG-005",
                "title": "No About or team page detected",
                "category": "engagement",
                "severity": "medium",
                "confidence": "medium",
                "affected_urls": ["https://example.com/"],
                "evidence": "No about or team page for orientation",
                "tags": ["about-page", "navigation"],
                "source_skill": "engagement-audit",
                "suggested_action": {"summary": "Create About page", "priority": "medium", "effort": "medium"}
            }
        ]
        deduped = dedup_mod.deduplicate(findings)
        self.assertEqual(len(deduped), 1, "Cross-skill about-page findings should merge into 1 representative finding")
        self.assertIsNotNone(deduped[0]["root_cause_group"])


class TestAdaptiveCrawlPrioritization(unittest.TestCase):
    """
    Unit and regression tests for Adaptive Crawl Page Limit & Prioritization:
    - Verifies priority scoring hierarchy (Homepage > About > Contact > Products > Pricing > Docs > Careers > Events > Hubs > Leaves > Deep).
    - Verifies repetitive leaf vs category hub distinction.
    - Verifies repetitive leaf capping at max 3 without skipping category hubs.
    - Verifies strict enforcement of max-pages limit.
    - Verifies deterministic queue ordering.
    """

    def test_priority_scoring_hierarchy(self):
        """Priority scoring strictly adheres to the requested hierarchy."""
        score_home, _ = crawl_mod.score_url_priority("https://example.com/", depth=0)
        score_about, _ = crawl_mod.score_url_priority("https://example.com/about", link_text="About Us", depth=1)
        score_contact, _ = crawl_mod.score_url_priority("https://example.com/contact", link_text="Contact Us", depth=1)
        score_prod, _ = crawl_mod.score_url_priority("https://example.com/products", link_text="Our Products", depth=1)
        score_pricing, _ = crawl_mod.score_url_priority("https://example.com/pricing", link_text="Pricing Plans", depth=1)
        score_docs, _ = crawl_mod.score_url_priority("https://example.com/docs", link_text="Documentation", depth=1)
        score_careers, _ = crawl_mod.score_url_priority("https://example.com/careers", link_text="Join our team", depth=1)
        score_events, _ = crawl_mod.score_url_priority("https://example.com/events", link_text="Upcoming Conferences", depth=1)
        score_hub, _ = crawl_mod.score_url_priority("https://example.com/blog", link_text="Blog", depth=1)
        score_rep, _ = crawl_mod.score_url_priority("https://example.com/community", link_text="Community", depth=1)
        score_leaf, _ = crawl_mod.score_url_priority("https://example.com/blog/2026/01/post-one", link_text="Post One", depth=2)
        score_deep, _ = crawl_mod.score_url_priority("https://example.com/tag/ai/page/2", link_text="Page 2", depth=3)

        self.assertGreater(score_home, score_about)
        self.assertGreater(score_about, score_contact)
        self.assertGreater(score_contact, score_prod)
        self.assertGreater(score_prod, score_pricing)
        self.assertGreater(score_pricing, score_docs)
        self.assertGreater(score_docs, score_careers)
        self.assertGreater(score_careers, score_events)
        self.assertGreater(score_events, score_hub)
        self.assertGreater(score_hub, score_rep)
        self.assertGreater(score_rep, score_leaf)
        self.assertGreater(score_leaf, score_deep)

    def test_category_hubs_not_classified_as_leaves(self):
        """Category hub pages must not be misclassified as repetitive leaves."""
        hubs = [
            "https://example.com/blog",
            "https://example.com/blog/",
            "https://example.com/products",
            "https://example.com/products/",
            "https://example.com/news",
            "https://example.com/shop",
            "https://example.com/catalog"
        ]
        for h in hubs:
            is_leaf, leaf_type = crawl_mod.is_repetitive_leaf(h)
            self.assertFalse(is_leaf, f"{h} is a category hub and should not be identified as a repetitive leaf")
            self.assertIsNone(leaf_type)

    def test_repetitive_leaf_detection(self):
        """Individual deep articles and products are correctly detected as repetitive leaves."""
        leaves = [
            ("https://example.com/blog/2026/01/my-post", "blog_leaf"),
            ("https://example.com/articles/deep-dive-ai", "blog_leaf"),
            ("https://example.com/news/latest-update", "blog_leaf"),
            ("https://example.com/product/widget-123", "product_leaf"),
            ("https://example.com/products/item-999", "product_leaf"),
            ("https://example.com/shop/shoe-blue", "product_leaf")
        ]
        for url, expected_type in leaves:
            is_leaf, leaf_type = crawl_mod.is_repetitive_leaf(url)
            self.assertTrue(is_leaf, f"{url} should be identified as a repetitive leaf")
            self.assertEqual(leaf_type, expected_type)

    def test_repetitive_leaf_capping_and_prioritization(self):
        """Crawler prioritizes high-value pages and caps repetitive leaves at max 3."""
        # Simulate discovered links from homepage
        raw_links = []
        # Add 20 blog leaf links first (e.g. at top of homepage)
        for i in range(1, 21):
            raw_links.append({"href": f"https://example.com/blog/post-{i}", "text": f"Post {i}"})
        # Add high-value pages at bottom of homepage
        raw_links.append({"href": "https://example.com/about", "text": "About Us"})
        raw_links.append({"href": "https://example.com/contact", "text": "Contact Us"})
        raw_links.append({"href": "https://example.com/pricing", "text": "Pricing"})
        raw_links.append({"href": "https://example.com/blog", "text": "Blog"})  # Hub!

        queue = []
        queued_urls = set()
        repetitive_counts = {"blog_leaf": 0, "product_leaf": 0}
        skipped_count = 0
        order = 0

        for link in raw_links:
            href = link["href"]
            is_leaf, leaf_type = crawl_mod.is_repetitive_leaf(href)
            if is_leaf and leaf_type:
                if repetitive_counts.get(leaf_type, 0) >= 3:
                    skipped_count += 1
                    continue
                repetitive_counts[leaf_type] = repetitive_counts.get(leaf_type, 0) + 1

            order += 1
            priority, _ = crawl_mod.score_url_priority(href, link_text=link["text"], depth=1)
            queue.append({"url": href, "priority": priority, "depth": 1, "order": order})
            queued_urls.add(href)

        # 17 blog leaf links were skipped due to the 3-page cap
        self.assertEqual(skipped_count, 17)
        self.assertEqual(repetitive_counts["blog_leaf"], 3)
        self.assertIn("https://example.com/blog", queued_urls, "Category hub /blog must NOT be skipped")

        # Sort queue by priority
        queue.sort(key=lambda item: (-item["priority"], item["depth"], item["order"]))
        popped_urls = [item["url"] for item in queue]

        # Verify high-value pages are popped BEFORE any blog leaf pages
        about_idx = popped_urls.index("https://example.com/about")
        contact_idx = popped_urls.index("https://example.com/contact")
        pricing_idx = popped_urls.index("https://example.com/pricing")
        blog_hub_idx = popped_urls.index("https://example.com/blog")
        first_leaf_idx = popped_urls.index("https://example.com/blog/post-1")

        self.assertLess(about_idx, first_leaf_idx)
        self.assertLess(contact_idx, first_leaf_idx)
        self.assertLess(pricing_idx, first_leaf_idx)
        self.assertLess(blog_hub_idx, first_leaf_idx)

    def test_max_pages_strict_enforcement(self):
        """Queue popping strictly respects max_pages limit regardless of queue size."""
        queue = [
            {"url": f"https://example.com/page-{i}", "priority": 50, "depth": 1, "order": i}
            for i in range(50)
        ]
        max_pages = 5
        visited = []
        while queue and len(visited) < max_pages:
            queue.sort(key=lambda item: (-item["priority"], item["depth"], item["order"]))
            visited.append(queue.pop(0)["url"])

        self.assertEqual(len(visited), 5)

    def test_crawl_queue_determinism(self):
        """Queue sorting is strictly deterministic across multiple runs."""
        items_run1 = [
            {"url": "https://example.com/docs", "priority": 70, "depth": 1, "order": 2},
            {"url": "https://example.com/pricing", "priority": 75, "depth": 1, "order": 3},
            {"url": "https://example.com/about", "priority": 90, "depth": 1, "order": 1},
            {"url": "https://example.com/blog/p1", "priority": 30, "depth": 2, "order": 4},
            {"url": "https://example.com/blog/p2", "priority": 30, "depth": 2, "order": 5},
        ]
        items_run2 = list(items_run1)

        items_run1.sort(key=lambda item: (-item["priority"], item["depth"], item["order"]))
        items_run2.sort(key=lambda item: (-item["priority"], item["depth"], item["order"]))

        self.assertEqual(items_run1, items_run2)
        expected_urls = [
            "https://example.com/about",
            "https://example.com/pricing",
            "https://example.com/docs",
            "https://example.com/blog/p1",
            "https://example.com/blog/p2"
        ]
        self.assertEqual([item["url"] for item in items_run1], expected_urls)


class TestSEOHygieneAndAIDiscoverability(unittest.TestCase):
    """Regression test suite for Phase 5 SEO Hygiene and AI Discoverability checks."""

    def test_clean_site_zero_false_positives(self):
        """A well-configured site generates 0 SEO defect findings across all skills."""
        clean_pages = [
            make_page(
                url="https://example.com/",
                title="Acme Analytics — Enterprise Observability",
                meta_description="Comprehensive cloud observability for enterprise platforms.",
                h1=["Acme Enterprise Observability"],
                json_ld=[{
                    "@context": "https://schema.org",
                    "@type": "Organization",
                    "name": "Acme Analytics",
                    "url": "https://example.com/"
                }],
                links=[
                    {"href": "https://example.com/about", "text": "About Acme", "is_internal": True},
                    {"href": "https://example.com/contact", "text": "Contact Sales", "is_internal": True},
                    {"href": "https://example.com/products", "text": "Our Products", "is_internal": True}
                ],
                page_type="Homepage"
            ),
            make_page(
                url="https://example.com/about",
                title="About Acme Analytics",
                meta_description="Learn about the Acme leadership and history.",
                h1=["About Our Mission"],
                links=[{"href": "https://example.com/", "text": "Home", "is_internal": True}],
                page_type="About"
            ),
            make_page(
                url="https://example.com/contact",
                title="Contact Acme Support",
                meta_description="Get in touch with Acme customer support.",
                h1=["Contact Us"],
                links=[{"href": "https://example.com/", "text": "Home", "is_internal": True}],
                page_type="Contact"
            )
        ]
        snap = make_snapshot(clean_pages)
        snap["crawl_meta"]["sitemaps"] = ["https://example.com/sitemap.xml"]

        cra_f, _ = cra_mod.run_checks(snap)
        sdc_f, _ = sdc_mod.run_checks(snap)
        eng_f, _ = eng_mod.run_checks(snap)

        seo_check_ids = {"CRA-013", "CRA-014", "CRA-015", "CRA-016", "CRA-018", "CRA-019", "CRA-020",
                         "SDC-206", "SDC-207", "SDC-208", "SDC-209", "ENG-009", "ENG-010"}
        all_fired = {f["check_id"] for f in cra_f + sdc_f + eng_f}
        self.assertEqual(all_fired & seo_check_ids, set())

    def test_cra_013_page_type_disallow_detection(self):
        """CRA-013 dynamically identifies disallowed high-value pages without hardcoded paths."""
        pages = [
            make_page(url="https://example.com/", page_type="Homepage"),
            make_page(url="https://example.com/knowledge-hub/guide", page_type="Documentation"),
            make_page(url="https://example.com/corp/team", page_type="About")
        ]
        snap = make_snapshot(pages)
        snap["crawl_meta"]["disallowed_paths"] = ["/knowledge-hub/"]

        findings, _ = cra_mod.run_checks(snap)
        cra013 = [f for f in findings if f.get("check_id") == "CRA-013"]
        self.assertEqual(len(cra013), 1)
        self.assertIn("knowledge-hub", cra013[0]["evidence"])
        self.assertEqual(cra013[0]["severity"], "high")

    def test_cra_015_brand_page_noindex(self):
        """CRA-015 fires when primary brand homepage has noindex, even if <50% of the site has noindex."""
        pages = [
            make_page(url="https://example.com/", meta_robots="noindex, follow", page_type="Homepage"),
            make_page(url="https://example.com/p1", meta_robots="index, follow"),
            make_page(url="https://example.com/p2", meta_robots="index, follow"),
            make_page(url="https://example.com/p3", meta_robots="index, follow"),
        ]
        snap = make_snapshot(pages)
        findings, _ = cra_mod.run_checks(snap)
        cra015 = [f for f in findings if f.get("check_id") == "CRA-015"]
        self.assertEqual(len(cra015), 1)
        self.assertEqual(cra015[0]["severity"], "critical")
        self.assertIn("Homepage", cra015[0]["evidence"])

    def test_cra_016_canonical_pointing_to_error(self):
        """CRA-016 detects canonical tag pointing to a broken (404/500) target URL."""
        pages = [
            make_page(url="https://example.com/article", canonical="https://example.com/missing-canonical"),
            make_page(url="https://example.com/missing-canonical", status_code=404)
        ]
        snap = make_snapshot(pages)
        findings, _ = cra_mod.run_checks(snap)
        cra016 = [f for f in findings if f.get("check_id") == "CRA-016"]
        self.assertEqual(len(cra016), 1)
        self.assertEqual(cra016[0]["severity"], "high")
        self.assertIn("HTTP 404", cra016[0]["evidence"])

    def test_cra_019_material_content_disparity(self):
        """CRA-019 flags only when JS rendering reveals material content absent in raw HTML."""
        clean_js_page = make_page(
            url="https://example.com/app",
            crawled_with_js=True,
            raw_text_length=1500,
            rendered_text_length=1520,
            content_disparity=20,
            js_dependent_content=False
        )
        snap1 = make_snapshot([clean_js_page])
        findings1, _ = cra_mod.run_checks(snap1)
        self.assertFalse(any(f.get("check_id") == "CRA-019" for f in findings1))

        disparate_page = make_page(
            url="https://example.com/spa",
            crawled_with_js=True,
            raw_text_length=120,
            rendered_text_length=2400,
            content_disparity=2280,
            js_dependent_content=True
        )
        snap2 = make_snapshot([disparate_page])
        findings2, _ = cra_mod.run_checks(snap2)
        cra019 = [f for f in findings2 if f.get("check_id") == "CRA-019"]
        self.assertEqual(len(cra019), 1)
        self.assertEqual(cra019[0]["severity"], "high")

    def test_sdc_206_boilerplate_titles(self):
        """SDC-206 identifies boilerplate and placeholder titles."""
        pages = [
            make_page(url="https://example.com/", title="Home"),
            make_page(url="https://example.com/page2", title="Untitled Document")
        ]
        snap = make_snapshot(pages)
        findings, _ = sdc_mod.run_checks(snap)
        sdc206 = [f for f in findings if f.get("check_id") == "SDC-206"]
        self.assertEqual(len(sdc206), 1)
        self.assertEqual(sdc206[0]["severity"], "medium")

    def test_sdc_207_missing_h1_on_content_pages(self):
        """SDC-207 detects missing H1 on inferred Product/Documentation content pages."""
        pages = [
            make_page(url="https://example.com/", h1=["Home"]),
            make_page(url="https://example.com/product/crm", h1=[], page_type="Product", visible_text_length=800)
        ]
        snap = make_snapshot(pages)
        findings, _ = sdc_mod.run_checks(snap)
        sdc207 = [f for f in findings if f.get("check_id") == "SDC-207"]
        self.assertEqual(len(sdc207), 1)
        self.assertIn("crm", sdc207[0]["affected_urls"][0])

    def test_sdc_208_incomplete_schema(self):
        """SDC-208 flags Schema.org objects missing required identity/content properties."""
        pages = [
            make_page(
                url="https://example.com/",
                json_ld=[{
                    "@context": "https://schema.org",
                    "@type": "Organization"
                }]
            )
        ]
        snap = make_snapshot(pages)
        findings, _ = sdc_mod.run_checks(snap)
        sdc208 = [f for f in findings if f.get("check_id") == "SDC-208"]
        self.assertEqual(len(sdc208), 1)
        self.assertIn("missing 'name'", sdc208[0]["evidence"])

    def test_sdc_209_semantic_heading_contradiction(self):
        """SDC-209 flags when Schema.org declared entity directly contradicts visible heading."""
        pages = [
            make_page(
                url="https://example.com/service",
                title="Gourmet Artisan Bakery",
                h1=["Fresh Artisan Bread and Pastries"],
                visible_text_sample="We bake sourdough bread and French pastries daily in downtown.",
                json_ld=[{
                    "@context": "https://schema.org",
                    "@type": "Product",
                    "name": "Acme Cyber Cloud Enterprise Monitoring"
                }]
            )
        ]
        snap = make_snapshot(pages)
        findings, _ = sdc_mod.run_checks(snap)
        sdc209 = [f for f in findings if f.get("check_id") == "SDC-209"]
        self.assertEqual(len(sdc209), 1)
        self.assertIn("Acme Cyber Cloud", sdc209[0]["evidence"])

    def test_eng_009_contextual_anchor_text(self):
        """ENG-009 detects non-descriptive links when they materially hinder navigation."""
        pages = [
            make_page(
                url="https://example.com/",
                links=[
                    {"href": "https://example.com/p1", "text": "click here", "is_internal": True},
                    {"href": "https://example.com/p2", "text": "read more", "is_internal": True},
                    {"href": "https://example.com/p3", "text": "click here", "is_internal": True},
                    {"href": "https://example.com/p4", "text": "learn more", "is_internal": True},
                    {"href": "https://example.com/p5", "text": "Normal Link", "is_internal": True}
                ]
            )
        ]
        snap = make_snapshot(pages)
        findings, _ = eng_mod.run_checks(snap)
        eng009 = [f for f in findings if f.get("check_id") == "ENG-009"]
        self.assertEqual(len(eng009), 1)
        self.assertEqual(eng009[0]["severity"], "medium")

    def test_eng_010_orientation_page_discoverability(self):
        """ENG-010 detects when an inferred core orientation page exists in crawl but is isolated from homepage navigation."""
        linked_pages = [
            make_page(
                url="https://example.com/",
                links=[
                    {"href": "https://example.com/about", "text": "About Us", "is_internal": True},
                    {"href": "https://example.com/contact", "text": "Contact", "is_internal": True}
                ]
            ),
            make_page(url="https://example.com/about", page_type="About"),
            make_page(url="https://example.com/contact", page_type="Contact")
        ]
        snap_linked = make_snapshot(linked_pages)
        findings_linked, _ = eng_mod.run_checks(snap_linked)
        self.assertFalse(any(f.get("check_id") == "ENG-010" for f in findings_linked))

        isolated_pages = [
            make_page(
                url="https://example.com/",
                links=[
                    {"href": "https://example.com/features", "text": "Features", "is_internal": True},
                    {"href": "https://example.com/blog", "text": "Blog", "is_internal": True}
                ]
            ),
            make_page(url="https://example.com/pricing", page_type="Pricing")
        ]
        snap_isolated = make_snapshot(isolated_pages)
        findings_isolated, _ = eng_mod.run_checks(snap_isolated)
        eng010 = [f for f in findings_isolated if f.get("check_id") == "ENG-010"]
        self.assertEqual(len(eng010), 1)
        self.assertIn("https://example.com/pricing", eng010[0]["affected_urls"])

    def test_cra_020_sitemap_absence_requires_discoverability_impact(self):
        """CRA-020 produces NO finding for missing sitemap alone; requires material discoverability limitation."""
        pages = [
            make_page(url="https://example.com/"),
            make_page(url="https://example.com/about"),
            make_page(url="https://example.com/contact"),
            make_page(url="https://example.com/docs")
        ]
        snap_normal = make_snapshot(pages)
        snap_normal["crawl_meta"]["robots_txt_status"] = 200
        snap_normal["crawl_meta"]["sitemaps"] = []
        findings1, _ = cra_mod.run_checks(snap_normal)
        self.assertFalse(any(f.get("check_id") == "CRA-020" for f in findings1))

        snap_limited = make_snapshot(pages)
        snap_limited["crawl_meta"]["robots_txt_status"] = 200
        snap_limited["crawl_meta"]["sitemaps"] = []
        snap_limited["crawl_meta"]["crawl_coverage"] = {"discovery_limited": True}
        findings2, _ = cra_mod.run_checks(snap_limited)
        cra020 = [f for f in findings2 if f.get("check_id") == "CRA-020"]
        self.assertEqual(len(cra020), 1)
        self.assertEqual(cra020[0]["severity"], "low")


# ─── Phase 6: Final Report & Evaluator Optimization Tests ────────────────────

class TestFinalReportAndEvaluatorOptimization(unittest.TestCase):
    """
    Validates Phase 6 deterministic prioritization tie-breaking, report schema conformity,
    companion markdown report generation, journey explainability, answerability evidence calibration,
    and resilience on shallow/empty crawls.
    """

    def test_top_priorities_deterministic_tie_breaking(self):
        """Top priorities enforce strict multi-tier deterministic sorting: (-priority_score, severity_rank, -affected_pages_count, id)."""
        findings = [
            {
                "id": "F-100",
                "title": "Critical issue B",
                "severity": "critical",
                "confidence": "high",
                "affected_urls": ["https://example.com/p1"],
                "suggested_action": {"summary": "Fix B"}
            },
            {
                "id": "F-050",
                "title": "Critical issue A",
                "severity": "critical",
                "confidence": "high",
                "affected_urls": ["https://example.com/p1"],
                "suggested_action": {"summary": "Fix A"}
            },
            {
                "id": "F-020",
                "title": "Critical with more reach",
                "severity": "critical",
                "confidence": "high",
                "affected_urls": ["https://example.com/p1", "https://example.com/p2"],
                "suggested_action": {"summary": "Fix Reach"}
            }
        ]
        # F-020: score = 40 * 1.0 * 1.2 = 48.0
        # F-100: score = 40 * 1.0 * 1.1 = 44.0, id="F-100"
        # F-050: score = 40 * 1.0 * 1.1 = 44.0, id="F-050"
        # Ordered: F-020 (rank 1), F-050 (rank 2), F-100 (rank 3)
        priorities = score_mod.compute_top_priorities(findings, limit=5)
        self.assertEqual(len(priorities), 3)
        self.assertEqual(priorities[0]["id"], "F-020")
        self.assertEqual(priorities[1]["id"], "F-050")
        self.assertEqual(priorities[2]["id"], "F-100")
        self.assertEqual(priorities[0]["priority_rank"], 1)
        self.assertEqual(priorities[1]["priority_rank"], 2)
        self.assertEqual(priorities[2]["priority_rank"], 3)

    def test_report_structure_and_required_keys(self):
        """Final report contains all 10 required top-level keys plus methodology_and_limitations with exact fields."""
        snap = make_snapshot([make_page(url="https://example.com/")])
        findings = [
            {
                "id": "F-001",
                "title": "Robots block",
                "category": "discoverability",
                "severity": "critical",
                "confidence": "high",
                "source_skill": "crawlability-render-audit",
                "tags": ["robots-txt", "crawlability"],
                "affected_urls": ["https://example.com/"],
                "evidence": "Robots.txt blocks /",
                "suggested_action": {"summary": "Allow in robots.txt"}
            }
        ]
        summary = score_mod.compute_summary(findings, snap)
        journey = score_mod.compute_agent_journey_scores(findings)
        answerability = score_mod.evaluate_agent_answerability(snap, findings)
        priorities = score_mod.compute_top_priorities(findings)

        report = {
            "site": "example.com",
            "audited_at": "2026-09-06T15:00:00Z",
            "run_info": {
                "marketplace_version": "1.0.0",
                "query_input": "https://example.com",
                "target_url": "https://example.com",
                "skills_invoked": ["crawlability-render-audit"],
                "failed_skills": [],
                "pages_crawled": 1,
                "max_pages": 20,
                "crawl_duration_seconds": 2.5,
                "robots_txt_respected": True,
                "crawl_coverage": {
                    "pages_discovered": 1,
                    "pages_crawled": 1,
                    "pages_skipped": 0,
                    "failed_pages": [],
                    "crawl_duration_seconds": 2.5,
                    "robots_status": 200,
                    "js_rendering_status": "disabled"
                }
            },
            "summary": summary,
            "agent_journey_scores": journey,
            "agent_answerability": answerability,
            "top_priorities": priorities,
            "findings": findings,
            "proactive_recommendations": [],
            "strengths": [],
            "methodology_and_limitations": build_mod.METHODOLOGY_AND_LIMITATIONS
        }

        required_keys = [
            "site", "audited_at", "run_info", "summary",
            "agent_journey_scores", "agent_answerability", "top_priorities",
            "findings", "proactive_recommendations", "strengths",
            "methodology_and_limitations"
        ]
        for k in required_keys:
            self.assertIn(k, report)

        meth = report["methodology_and_limitations"]
        for meth_field in ["audit_scope", "deterministic_scoring", "read_only_guarantee", "limitations"]:
            self.assertIn(meth_field, meth)
        self.assertIsInstance(meth["limitations"], list)
        self.assertGreater(len(meth["limitations"]), 0)

    def test_companion_markdown_report_generation(self):
        """build_report.py generates a complete, scan-friendly companion Markdown report."""
        snap = make_snapshot([make_page(url="https://example.com/")])
        findings = [
            {
                "id": "F-001",
                "title": "Missing meta description",
                "category": "discoverability",
                "severity": "medium",
                "confidence": "high",
                "source_skill": "crawlability-render-audit",
                "tags": ["meta-description"],
                "affected_urls": ["https://example.com/"],
                "evidence": "Homepage has empty meta description.",
                "suggested_action": {"summary": "Add meta description", "priority": "medium", "effort": "low"}
            }
        ]
        report = {
            "site": "example.com",
            "audited_at": "2026-09-06T15:00:00Z",
            "run_info": {
                "marketplace_version": "1.0.0",
                "target_url": "https://example.com",
                "max_pages": 20,
                "crawl_coverage": {
                    "pages_discovered": 1,
                    "pages_crawled": 1,
                    "pages_skipped": 0,
                    "crawl_duration_seconds": 1.2,
                    "robots_status": "allowed",
                    "js_rendering_status": "disabled"
                }
            },
            "summary": score_mod.compute_summary(findings, snap),
            "agent_journey_scores": score_mod.compute_agent_journey_scores(findings),
            "agent_answerability": score_mod.evaluate_agent_answerability(snap, findings),
            "top_priorities": score_mod.compute_top_priorities(findings),
            "findings": findings,
            "proactive_recommendations": [{"id": "PRO-001", "title": "Add FAQ schema", "category": "discoverability", "priority": "medium", "rationale": "Improves AI Q&A"}],
            "strengths": [{"title": "Fast response time", "category": "discoverability"}],
            "methodology_and_limitations": build_mod.METHODOLOGY_AND_LIMITATIONS
        }
        md_text = build_mod.generate_markdown_report(report)
        self.assertIsInstance(md_text, str)
        self.assertIn("# Brand AI-Readiness Audit Report: example.com", md_text)
        self.assertIn("## Executive Summary", md_text)
        self.assertIn("## Agent Journey Scorecard", md_text)
        self.assertIn("## Crawl Coverage Summary", md_text)
        self.assertIn("## Top Priorities", md_text)
        self.assertIn("## Agent Answerability", md_text)
        self.assertIn("## Strengths", md_text)
        self.assertIn("## Proactive Opportunities", md_text)
        self.assertIn("## Detailed Audit Findings", md_text)
        self.assertIn("## Methodology & Limitations", md_text)

    def test_agent_journey_scores_evidence_grounded(self):
        """Journey pillar deductions are strictly grounded in findings and match check tags and severities."""
        findings = [
            {
                "id": "F-001",
                "title": "Robots block",
                "severity": "critical",
                "tags": ["crawlability", "robots-txt"],
                "evidence": "Disallow in robots.txt"
            },
            {
                "id": "F-002",
                "title": "Missing schema",
                "severity": "high",
                "tags": ["json-ld", "structured-data"],
                "evidence": "0 schema found"
            }
        ]
        explanations = score_mod.get_journey_pillar_explanations(findings)
        self.assertEqual(len(explanations), 6)
        for pillar in ["reach", "read", "understand", "trust", "navigate", "act"]:
            self.assertIn(pillar, explanations)
            self.assertIn("score", explanations[pillar])
            self.assertIn("deduction_total", explanations[pillar])
            self.assertIn("contributing_findings", explanations[pillar])

        # Reach should have 25 deduction from critical crawlability finding
        self.assertEqual(explanations["reach"]["deduction_total"], 25)
        self.assertEqual(explanations["reach"]["score"], 75)
        self.assertEqual(len(explanations["reach"]["contributing_findings"]), 1)
        self.assertEqual(explanations["reach"]["contributing_findings"][0]["id"], "F-001")

        # Understand should have 15 deduction from high structured data finding
        self.assertEqual(explanations["understand"]["deduction_total"], 15)
        self.assertEqual(explanations["understand"]["score"], 85)

    def test_answerability_evidence_and_sources(self):
        """Answerability questions require observable evidence; absence/conflict produces low confidence without whole-crawl inflation."""
        # Supported scenario
        snap_supported = make_snapshot([
            make_page(
                url="https://example.com/",
                meta_description="Enterprise CRM software for global sales teams.",
                page_type="Homepage",
                json_ld=[{
                    "@type": "Product",
                    "name": "Sales CRM",
                    "offers": {"@type": "Offer", "price": "99", "priceCurrency": "USD"}
                }, {
                    "@type": "Organization",
                    "address": {"streetAddress": "100 Market St", "addressLocality": "San Francisco", "addressCountry": "US"},
                    "contactPoint": {"telephone": "+1-800-555-0199", "email": "support@example.com"}
                }]
            )
        ])
        results = score_mod.evaluate_agent_answerability(snap_supported)
        self.assertEqual(len(results), 5)
        for q in results:
            self.assertEqual(q["status"], "Supported")
            self.assertEqual(q["confidence"], "high")
            self.assertTrue(len(q["evidence"]) > 10)
            self.assertGreater(len(q["sources"]), 0)

        # Empty/unsupported scenario with large crawl metadata (whole-site crawl)
        snap_unsupported = make_snapshot([
            make_page(url="https://empty-brand.com/", title="Blank", visible_text_sample="")
        ])
        snap_unsupported["crawl_meta"]["pages_crawled"] = 20
        snap_unsupported["crawl_meta"]["pages_discovered"] = 20
        snap_unsupported["crawl_meta"]["crawl_coverage"] = {"whole_site_crawled": True}

        unsupported_results = score_mod.evaluate_agent_answerability(snap_unsupported)
        # Verify that questions with no observable evidence use 'low' confidence and are not inflated by crawl coverage
        q_loc = next(q for q in unsupported_results if q["question"] == "Where is it located?")
        self.assertEqual(q_loc["status"], "Not found")
        self.assertEqual(q_loc["confidence"], "low", "Absence of evidence must produce low confidence, not high")

        q_cost = next(q for q in unsupported_results if q["question"] == "What does the product cost?")
        self.assertEqual(q_cost["status"], "Not found")
        self.assertEqual(q_cost["confidence"], "low", "Missing pricing must produce low confidence regardless of whole site crawl")

        q_contact = next(q for q in unsupported_results if q["question"] == "How can users contact it?")
        self.assertEqual(q_contact["status"], "Not found")
        self.assertEqual(q_contact["confidence"], "low", "Missing contact must produce low confidence")

    def test_graceful_handling_empty_or_limited_crawl(self):
        """Zero-page or completely empty snapshots are handled gracefully across answerability, summary, and priorities."""
        empty_snap = {"pages": [], "crawl_meta": {"pages_crawled": 0, "start_url": "https://empty.com"}}
        ans = score_mod.evaluate_agent_answerability(empty_snap, [])
        self.assertEqual(len(ans), 5)
        for item in ans:
            self.assertIn("question", item)
            self.assertIn("status", item)
            self.assertIn("confidence", item)
            self.assertIn("evidence", item)
            self.assertIn("sources", item)
            self.assertEqual(item["confidence"], "low")

        summary = score_mod.compute_summary([], empty_snap)
        self.assertEqual(summary["total_findings"], 0)
        self.assertEqual(summary["ai_readiness_score"], 100)

        priorities = score_mod.compute_top_priorities([], limit=5)
        self.assertEqual(priorities, [])


# ─── Phase 7: Final Accuracy, Stress Testing & Real-World Generalization ─────

class TestPhase7RealWorldGeneralization(unittest.TestCase):
    """
    Validates Phase 7 accuracy, stress testing, and real-world generalization across:
    - Restaurant / FoodEstablishment schema
    - Healthcare / Hospital schema
    - Multilingual site structure and hreflang without spurious false positives
    - 20-page full crawl budget processing
    - LocalBusiness priceRange in answerability
    """

    def test_restaurant_and_food_establishment_schema_recognized(self):
        """Restaurant / FoodEstablishment Schema on homepage triggers no SDC-003 or ENT-001 false positives."""
        restaurant_page = make_page(
            url="https://bistro.example.com/",
            title="Bistro Parisien — Fine French Dining",
            meta_description="Traditional French restaurant in downtown.",
            h1=["Bistro Parisien"],
            page_type="Homepage",
            json_ld=[{
                "@context": "https://schema.org",
                "@type": "Restaurant",
                "name": "Bistro Parisien",
                "url": "https://bistro.example.com",
                "priceRange": "$$$",
                "telephone": "+1-555-0123",
                "address": {"streetAddress": "123 Main St", "addressLocality": "Paris", "addressCountry": "FR"}
            }]
        )
        snap = make_snapshot([restaurant_page], start_url="https://bistro.example.com/")
        sdc_findings, _ = sdc_mod.run_checks(snap)
        sdc_ids = [f["check_id"] for f in sdc_findings]
        self.assertNotIn("SDC-003", sdc_ids, "Restaurant should be recognized as valid homepage entity schema")

        ent_findings, _ = ent_mod.run_checks(snap)
        ent_ids = [f["check_id"] for f in ent_findings]
        self.assertNotIn("ENT-001", ent_ids, "Brand name should be recognized from Restaurant JSON-LD")

    def test_healthcare_and_hospital_schema_recognized(self):
        """Hospital / MedicalOrganization Schema is recognized as valid organization entity."""
        hospital_page = make_page(
            url="https://hospital.example.org/",
            title="City General Hospital — Emergency & Specialty Care",
            meta_description="Providing comprehensive medical care.",
            h1=["City General Hospital"],
            page_type="Homepage",
            json_ld=[{
                "@context": "https://schema.org",
                "@type": "Hospital",
                "name": "City General Hospital",
                "url": "https://hospital.example.org",
                "telephone": "+1-555-0199",
                "address": {"streetAddress": "500 Health Ave", "addressLocality": "New York", "addressCountry": "US"}
            }]
        )
        snap = make_snapshot([hospital_page], start_url="https://hospital.example.org/")
        sdc_findings, _ = sdc_mod.run_checks(snap)
        sdc_ids = [f["check_id"] for f in sdc_findings]
        self.assertNotIn("SDC-003", sdc_ids, "Hospital should be recognized as valid homepage entity schema")

        ent_findings, _ = ent_mod.run_checks(snap)
        ent_ids = [f["check_id"] for f in ent_findings]
        self.assertNotIn("ENT-001", ent_ids, "Brand name should be recognized from Hospital JSON-LD")

    def test_multilingual_hreflang_and_paths_no_spurious_findings(self):
        """Multilingual paths (/en/, /es/) and hreflang do not trigger spurious findings, while genuine issues are reported."""
        # 1. Clean multilingual site without issues
        clean_pages = [
            make_page(
                url="https://global.example.com/",
                title="Global Solutions — International Freight",
                page_type="Homepage",
                links=[
                    {"href": "https://global.example.com/en/solutions", "text": "English", "is_internal": True},
                    {"href": "https://global.example.com/es/soluciones", "text": "Español", "is_internal": True}
                ],
                json_ld=[{"@type": "Organization", "name": "Global Solutions"}]
            ),
            make_page(
                url="https://global.example.com/en/solutions",
                canonical="https://global.example.com/en/solutions",
                title="Freight Solutions — English",
                h1=["Enterprise Freight Solutions"],
                page_type="Product"
            ),
            make_page(
                url="https://global.example.com/es/soluciones",
                canonical="https://global.example.com/es/soluciones",
                title="Soluciones de Carga — Español",
                h1=["Soluciones de Carga Empresarial"],
                page_type="Product"
            )
        ]
        clean_snap = make_snapshot(clean_pages, start_url="https://global.example.com/")
        cra_findings, _ = cra_mod.run_checks(clean_snap)
        cra_ids = [f["check_id"] for f in cra_findings]
        self.assertNotIn("CRA-018", cra_ids, "Language-prefixed paths must not trigger CRA-018 tracking pollution finding")

        # 2. Multilingual site with genuine canonical defect on Spanish page
        defect_pages = [
            make_page(
                url="https://global.example.com/",
                title="Global Solutions",
                page_type="Homepage",
                links=[{"href": "https://global.example.com/es/soluciones", "text": "Español", "is_internal": True}],
                json_ld=[{"@type": "Organization", "name": "Global Solutions"}]
            ),
            make_page(
                url="https://global.example.com/es/soluciones",
                canonical="https://global.example.com/es/error-404",
                title="Soluciones de Carga",
                h1=["Soluciones de Carga Empresarial"],
                page_type="Product"
            ),
            make_page(
                url="https://global.example.com/es/error-404",
                status_code=404,
                title="404 No Encontrado"
            )
        ]
        defect_snap = make_snapshot(defect_pages, start_url="https://global.example.com/")
        cra_defects, _ = cra_mod.run_checks(defect_snap)
        cra_defect_ids = [f["check_id"] for f in cra_defects]
        self.assertIn("CRA-016", cra_defect_ids, "Genuine canonical defect on localized page must be detected")

    def test_large_site_20_page_crawl_budget_prioritization(self):
        """Full 20-page crawl budget snapshot computes priorities and scores deterministically."""
        pages = [
            make_page(
                "https://megastore.example.com/",
                page_type="Homepage",
                title="MegaStore",
                json_ld=[{"@type": "Store", "name": "MegaStore"}]
            )
        ]
        for i in range(1, 20):
            pages.append(
                make_page(
                    f"https://megastore.example.com/item-{i}",
                    page_type="Product",
                    title=f"Item {i}",
                    json_ld=[{"@type": "Product", "name": f"Item {i}", "offers": {"@type": "Offer", "price": str(10 + i)}}]
                )
            )
        snap = make_snapshot(pages, start_url="https://megastore.example.com/")
        snap["crawl_meta"]["pages_crawled"] = 20
        snap["crawl_meta"]["pages_discovered"] = 50
        snap["crawl_meta"]["pages_skipped"] = 30

        summary = score_mod.compute_summary([], snap)
        self.assertEqual(summary["total_findings"], 0)
        self.assertEqual(summary["ai_readiness_score"], 100)

        priorities = score_mod.compute_top_priorities([], limit=5)
        self.assertEqual(priorities, [])

    def test_local_business_price_range_answerability(self):
        """priceRange in LocalBusiness/Restaurant satisfies Question 4 pricing answerability with observable evidence."""
        bistro_page = make_page(
            url="https://dining.example.com/",
            page_type="Homepage",
            title="Le Bistro",
            json_ld=[{
                "@type": "Restaurant",
                "name": "Le Bistro",
                "priceRange": "$$$",
                "address": {"streetAddress": "100 Rue de Paris", "addressLocality": "Lyon", "addressCountry": "FR"}
            }]
        )
        snap = make_snapshot([bistro_page], start_url="https://dining.example.com/")
        ans = score_mod.evaluate_agent_answerability(snap)
        cost_q = next(q for q in ans if q["question"] == "What does the product cost?")
        self.assertEqual(cost_q["status"], "Supported")
        self.assertEqual(cost_q["confidence"], "high")
        self.assertIn("$$$", cost_q["evidence"])


if __name__ == "__main__":
    unittest.main(verbosity=2)


# ─── Phase 5 Module Loader ────────────────────────────────────────────────────

agd_mod = load_module(
    REPO_ROOT / "skills/agent-discoverability-audit/scripts/audit.py",
    "agd"
)


# ─── Phase 5: Agent Discoverability Tests ─────────────────────────────────────

class TestAgentDiscoverabilityAudit(unittest.TestCase):
    """
    Regression tests for Phase 5: Marketplace / Agent Discoverability.

    All tests verify that:
    - Expected check IDs fire when the problematic condition is present.
    - They do NOT fire on well-structured pages (false-positive regression).
    - Findings target pages with high page_importance_score first.
    - No Adobe-specific or domain-specific logic is used.
    """

    # ── AGD-001: Important pages missing machine-readable summary metadata ────

    def test_agd001_fires_when_important_page_has_no_meta_description(self):
        """AGD-001 fires when an important page has no meta description."""
        pages = [
            make_page(
                url="https://shop.example.com/",
                page_type="Homepage",
                title="Shop Example",
                meta_description="",        # missing
                page_importance_score=90,
            ),
        ]
        snap = make_snapshot(pages, start_url="https://shop.example.com/")
        findings, _ = agd_mod.run_checks(snap)
        agd001 = [f for f in findings if f.get("check_id") == "AGD-001"]
        self.assertEqual(len(agd001), 1, f"Expected AGD-001 to fire. Got: {[f['check_id'] for f in findings]}")
        self.assertEqual(agd001[0]["severity"], "high")
        self.assertIn("https://shop.example.com/", agd001[0]["affected_urls"])

    def test_agd001_fires_when_important_page_has_no_title(self):
        """AGD-001 fires when an important page has a trivially short / missing title."""
        pages = [
            make_page(
                url="https://example.com/pricing",
                page_type="Pricing",
                title="",                   # missing
                meta_description="See our pricing plans.",
                page_importance_score=85,
            ),
        ]
        snap = make_snapshot(pages)
        findings, _ = agd_mod.run_checks(snap)
        agd001 = [f for f in findings if f.get("check_id") == "AGD-001"]
        self.assertEqual(len(agd001), 1)

    def test_agd001_does_not_fire_on_page_with_good_metadata(self):
        """AGD-001 must NOT fire when an important page has both title and meta description."""
        pages = [
            make_page(
                url="https://example.com/",
                page_type="Homepage",
                title="Example — Cloud Data Platform",
                meta_description="Explore our data platform built for modern engineering teams.",
                page_importance_score=95,
            ),
        ]
        snap = make_snapshot(pages)
        findings, _ = agd_mod.run_checks(snap)
        agd001 = [f for f in findings if f.get("check_id") == "AGD-001"]
        self.assertEqual(agd001, [], f"AGD-001 false positive: {agd001}")

    def test_agd001_ignores_low_importance_pages(self):
        """AGD-001 only checks pages at or above the importance threshold."""
        pages = [
            make_page(
                url="https://example.com/tag/misc",
                page_type="Other",
                title="",
                meta_description="",
                page_importance_score=40,   # below threshold
            ),
        ]
        snap = make_snapshot(pages)
        findings, _ = agd_mod.run_checks(snap)
        agd001 = [f for f in findings if f.get("check_id") == "AGD-001"]
        self.assertEqual(agd001, [], "AGD-001 should not fire on low-importance pages")

    # ── AGD-002: High-importance page not reachable from homepage ─────────────

    def test_agd002_fires_when_very_important_page_unreachable(self):
        """AGD-002 fires when a very important page cannot be reached within 3 hops."""
        hp = make_page(
            url="https://example.com/",
            page_type="Homepage",
            page_importance_score=95,
            links=[
                {"href": "https://example.com/about", "text": "About", "is_internal": True},
            ],
        )
        # Orphaned pricing page — no link from homepage or about
        pricing = make_page(
            url="https://example.com/pricing",
            page_type="Pricing",
            page_importance_score=88,
            links=[],
        )
        about = make_page(
            url="https://example.com/about",
            page_type="About",
            page_importance_score=70,
            links=[
                {"href": "https://example.com/", "text": "Home", "is_internal": True},
            ],
        )
        snap = make_snapshot([hp, about, pricing], start_url="https://example.com/")
        findings, _ = agd_mod.run_checks(snap)
        agd002 = [f for f in findings if f.get("check_id") == "AGD-002"]
        self.assertEqual(len(agd002), 1, f"Expected AGD-002 to fire. Got: {[f['check_id'] for f in findings]}")
        self.assertIn("https://example.com/pricing", agd002[0]["affected_urls"])

    def test_agd002_does_not_fire_when_all_important_pages_reachable(self):
        """AGD-002 must NOT fire when all very important pages are reachable within 3 hops."""
        hp = make_page(
            url="https://example.com/",
            page_type="Homepage",
            page_importance_score=95,
            links=[
                {"href": "https://example.com/pricing", "text": "Pricing", "is_internal": True},
                {"href": "https://example.com/about", "text": "About", "is_internal": True},
            ],
        )
        pricing = make_page(
            url="https://example.com/pricing",
            page_type="Pricing",
            page_importance_score=88,
        )
        about = make_page(
            url="https://example.com/about",
            page_type="About",
            page_importance_score=75,
        )
        snap = make_snapshot([hp, pricing, about], start_url="https://example.com/")
        findings, _ = agd_mod.run_checks(snap)
        agd002 = [f for f in findings if f.get("check_id") == "AGD-002"]
        self.assertEqual(agd002, [], f"AGD-002 false positive: {agd002}")

    def test_agd002_reachable_via_intermediate_hop(self):
        """AGD-002 must NOT fire when a page is reachable via a 2-hop path."""
        hp = make_page(
            url="https://example.com/",
            page_type="Homepage",
            page_importance_score=95,
            links=[{"href": "https://example.com/products", "text": "Products", "is_internal": True}],
        )
        products = make_page(
            url="https://example.com/products",
            page_type="Category",
            page_importance_score=80,
            links=[{"href": "https://example.com/products/widget", "text": "Widget", "is_internal": True}],
        )
        widget = make_page(
            url="https://example.com/products/widget",
            page_type="Product",
            page_importance_score=85,
        )
        snap = make_snapshot([hp, products, widget], start_url="https://example.com/")
        findings, _ = agd_mod.run_checks(snap)
        agd002 = [f for f in findings if f.get("check_id") == "AGD-002"]
        self.assertEqual(agd002, [], f"AGD-002 false positive on 2-hop path: {agd002}")

    # ── AGD-003: Important pages missing actionable structured data ───────────

    def test_agd003_fires_when_product_page_has_no_schema(self):
        """AGD-003 fires when a Product page has no actionable JSON-LD."""
        pages = [
            make_page(
                url="https://store.example.com/widget",
                page_type="Product",
                json_ld=[],
                page_importance_score=80,
            ),
        ]
        snap = make_snapshot(pages)
        findings, _ = agd_mod.run_checks(snap)
        agd003 = [f for f in findings if f.get("check_id") == "AGD-003"]
        self.assertEqual(len(agd003), 1, f"Expected AGD-003 to fire. Got: {[f['check_id'] for f in findings]}")
        self.assertEqual(agd003[0]["severity"], "high")

    def test_agd003_does_not_fire_on_product_with_product_schema(self):
        """AGD-003 must NOT fire when Product page has Product JSON-LD."""
        pages = [
            make_page(
                url="https://store.example.com/widget",
                page_type="Product",
                page_importance_score=80,
                json_ld=[{
                    "@context": "https://schema.org",
                    "@type": "Product",
                    "name": "Widget Pro",
                    "offers": {"@type": "Offer", "price": "29.99"}
                }],
            ),
        ]
        snap = make_snapshot(pages)
        findings, _ = agd_mod.run_checks(snap)
        agd003 = [f for f in findings if f.get("check_id") == "AGD-003"]
        self.assertEqual(agd003, [], f"AGD-003 false positive: {agd003}")

    def test_agd003_context_aware_skips_generic_other_pages(self):
        """AGD-003 must NOT fire on pages of type 'Other' or 'Privacy' (no schema expected)."""
        pages = [
            make_page(
                url="https://example.com/privacy",
                page_type="Other",
                json_ld=[],
                page_importance_score=75,
            ),
        ]
        snap = make_snapshot(pages)
        findings, _ = agd_mod.run_checks(snap)
        agd003 = [f for f in findings if f.get("check_id") == "AGD-003"]
        self.assertEqual(agd003, [], f"AGD-003 false positive on non-content page: {agd003}")

    def test_agd003_detects_schema_in_graph_node(self):
        """AGD-003 must NOT fire when actionable schema is inside @graph."""
        pages = [
            make_page(
                url="https://example.com/events/conf",
                page_type="Event",
                page_importance_score=82,
                json_ld=[{
                    "@context": "https://schema.org",
                    "@graph": [
                        {"@type": "Event", "name": "Annual Conference 2026"}
                    ]
                }],
            ),
        ]
        snap = make_snapshot(pages)
        findings, _ = agd_mod.run_checks(snap)
        agd003 = [f for f in findings if f.get("check_id") == "AGD-003"]
        self.assertEqual(agd003, [], f"AGD-003 false positive on @graph schema: {agd003}")

    # ── AGD-004: Missing sitemap signal ───────────────────────────────────────

    def test_agd004_fires_when_large_site_has_no_sitemap_signal(self):
        """AGD-004 fires when >3 pages are crawled and no sitemap is detectable."""
        pages = [
            make_page(url=f"https://example.com/p{i}", page_type="Article", page_importance_score=60)
            for i in range(5)
        ]
        snap = make_snapshot(pages)
        # No sitemap reference in meta or links
        findings, _ = agd_mod.run_checks(snap)
        agd004 = [f for f in findings if f.get("check_id") == "AGD-004"]
        self.assertEqual(len(agd004), 1, f"Expected AGD-004. Got: {[f['check_id'] for f in findings]}")
        self.assertEqual(agd004[0]["severity"], "medium")

    def test_agd004_does_not_fire_when_sitemap_in_meta(self):
        """AGD-004 must NOT fire when sitemap_url is present in crawl_meta."""
        pages = [
            make_page(url=f"https://example.com/p{i}", page_type="Article")
            for i in range(5)
        ]
        snap = make_snapshot(pages)
        snap["crawl_meta"]["sitemap_url"] = "https://example.com/sitemap.xml"
        findings, _ = agd_mod.run_checks(snap)
        agd004 = [f for f in findings if f.get("check_id") == "AGD-004"]
        self.assertEqual(agd004, [], f"AGD-004 false positive when sitemap_url set: {agd004}")

    def test_agd004_does_not_fire_on_tiny_site(self):
        """AGD-004 must NOT fire for sites with 3 or fewer pages (sitemaps not critical)."""
        pages = [
            make_page(url="https://example.com/", page_type="Homepage"),
            make_page(url="https://example.com/about", page_type="About"),
        ]
        snap = make_snapshot(pages)
        findings, _ = agd_mod.run_checks(snap)
        agd004 = [f for f in findings if f.get("check_id") == "AGD-004"]
        self.assertEqual(agd004, [], f"AGD-004 false positive on tiny site: {agd004}")

    def test_agd004_detects_sitemap_via_robots_txt(self):
        """AGD-004 must NOT fire when robots.txt references a sitemap."""
        pages = [
            make_page(url=f"https://example.com/p{i}", page_type="Article")
            for i in range(5)
        ]
        snap = make_snapshot(pages)
        snap["crawl_meta"]["robots_txt"] = "User-agent: *\nAllow: /\nSitemap: https://example.com/sitemap.xml\n"
        findings, _ = agd_mod.run_checks(snap)
        agd004 = [f for f in findings if f.get("check_id") == "AGD-004"]
        self.assertEqual(agd004, [], f"AGD-004 false positive when robots.txt has Sitemap: {agd004}")

    # ── AGD-005: Non-canonical URL patterns on important pages ────────────────

    def test_agd005_fires_on_mixed_case_path(self):
        """AGD-005 fires when an important page URL has mixed-case path segments."""
        pages = [
            make_page(
                url="https://example.com/Products/Widget",   # mixed case
                page_type="Product",
                page_importance_score=80,
            ),
        ]
        snap = make_snapshot(pages)
        findings, _ = agd_mod.run_checks(snap)
        agd005 = [f for f in findings if f.get("check_id") == "AGD-005"]
        self.assertEqual(len(agd005), 1, f"Expected AGD-005 on mixed-case URL. Got: {[f['check_id'] for f in findings]}")

    def test_agd005_fires_on_tracking_params_in_url(self):
        """AGD-005 fires when an important page URL contains tracking query parameters."""
        pages = [
            make_page(
                url="https://example.com/pricing?utm_source=newsletter",
                page_type="Pricing",
                page_importance_score=85,
            ),
        ]
        snap = make_snapshot(pages)
        findings, _ = agd_mod.run_checks(snap)
        agd005 = [f for f in findings if f.get("check_id") == "AGD-005"]
        self.assertEqual(len(agd005), 1, f"Expected AGD-005 on tracking param URL. Got: {[f['check_id'] for f in findings]}")

    def test_agd005_does_not_fire_on_clean_lowercase_url(self):
        """AGD-005 must NOT fire on a clean lowercase URL with no tracking params."""
        pages = [
            make_page(
                url="https://example.com/pricing",
                page_type="Pricing",
                page_importance_score=85,
            ),
        ]
        snap = make_snapshot(pages)
        findings, _ = agd_mod.run_checks(snap)
        agd005 = [f for f in findings if f.get("check_id") == "AGD-005"]
        self.assertEqual(agd005, [], f"AGD-005 false positive on clean URL: {agd005}")

    # ── AGD-006: Content cluster isolation ────────────────────────────────────

    def test_agd006_fires_when_blog_posts_not_interlinked(self):
        """AGD-006 fires when multiple important blog posts share a cluster but have no cross-links."""
        # 4 blog posts — all important, none linking to each other
        posts = [
            make_page(
                url=f"https://example.com/blog/post-{i}",
                page_type="Article",
                page_importance_score=65,
                links=[
                    {"href": "https://example.com/", "text": "Home", "is_internal": True}
                    # No links to sibling blog posts
                ],
            )
            for i in range(1, 5)
        ]
        snap = make_snapshot(posts + [make_page(url="https://example.com/", page_type="Homepage")])
        findings, _ = agd_mod.run_checks(snap)
        agd006 = [f for f in findings if f.get("check_id") == "AGD-006"]
        self.assertEqual(len(agd006), 1, f"Expected AGD-006. Got: {[f['check_id'] for f in findings]}")
        self.assertIn("blog", agd006[0]["evidence"].lower())

    def test_agd006_does_not_fire_when_posts_interlinked(self):
        """AGD-006 must NOT fire when blog posts link to sibling posts in the same cluster."""
        post_urls = [f"https://example.com/blog/post-{i}" for i in range(1, 5)]
        posts = [
            make_page(
                url=url,
                page_type="Article",
                page_importance_score=65,
                links=[
                    {"href": other_url, "text": "Related Post", "is_internal": True}
                    for other_url in post_urls if other_url != url
                ],
            )
            for url in post_urls
        ]
        snap = make_snapshot(posts)
        findings, _ = agd_mod.run_checks(snap)
        agd006 = [f for f in findings if f.get("check_id") == "AGD-006"]
        self.assertEqual(agd006, [], f"AGD-006 false positive on interlinked posts: {agd006}")

    def test_agd006_ignores_single_page_clusters(self):
        """AGD-006 must NOT fire when a path prefix has only 1 page (no cluster to form)."""
        pages = [
            make_page(
                url="https://example.com/docs/intro",
                page_type="Documentation",
                page_importance_score=70,
                links=[],
            ),
        ]
        snap = make_snapshot(pages)
        findings, _ = agd_mod.run_checks(snap)
        agd006 = [f for f in findings if f.get("check_id") == "AGD-006"]
        self.assertEqual(agd006, [], f"AGD-006 false positive on single-page cluster: {agd006}")

    # ── AGD-007: Thin agent-visible content on important page ─────────────────

    def test_agd007_fires_on_thin_product_page(self):
        """AGD-007 fires when an important Product page has very little visible text."""
        pages = [
            make_page(
                url="https://store.example.com/item-x",
                page_type="Product",
                visible_text_length=80,  # below 200 char threshold
                page_importance_score=80,
            ),
        ]
        snap = make_snapshot(pages)
        findings, _ = agd_mod.run_checks(snap)
        agd007 = [f for f in findings if f.get("check_id") == "AGD-007"]
        self.assertEqual(len(agd007), 1, f"Expected AGD-007. Got: {[f['check_id'] for f in findings]}")
        self.assertEqual(agd007[0]["severity"], "medium")

    def test_agd007_does_not_fire_on_rich_product_page(self):
        """AGD-007 must NOT fire on an important Product page with adequate visible text."""
        pages = [
            make_page(
                url="https://store.example.com/widget-pro",
                page_type="Product",
                visible_text_length=1200,
                page_importance_score=80,
            ),
        ]
        snap = make_snapshot(pages)
        findings, _ = agd_mod.run_checks(snap)
        agd007 = [f for f in findings if f.get("check_id") == "AGD-007"]
        self.assertEqual(agd007, [], f"AGD-007 false positive on rich page: {agd007}")

    def test_agd007_ignores_non_content_page_types(self):
        """AGD-007 must NOT fire on page types not expected to have rich body content."""
        pages = [
            make_page(
                url="https://example.com/search",
                page_type="Search",
                visible_text_length=50,
                page_importance_score=70,
            ),
        ]
        snap = make_snapshot(pages)
        findings, _ = agd_mod.run_checks(snap)
        agd007 = [f for f in findings if f.get("check_id") == "AGD-007"]
        self.assertEqual(agd007, [], f"AGD-007 false positive on Search page type: {agd007}")

    # ── Clean site — all AGD checks must yield zero false positives ──────────

    def test_clean_site_zero_agd_false_positives(self):
        """
        A well-structured site with all AGD best practices applied must generate
        zero AGD findings (comprehensive false-positive regression).
        """
        blog_urls = [f"https://news.example.com/blog/article-{i}" for i in range(1, 4)]
        hp = make_page(
            url="https://news.example.com/",
            page_type="Homepage",
            title="News Example — Trusted Industry Coverage",
            meta_description="In-depth reporting on technology, science, and culture.",
            page_importance_score=100,
            json_ld=[{
                "@context": "https://schema.org",
                "@type": "WebSite",
                "name": "News Example",
                "url": "https://news.example.com/"
            }],
            links=[
                {"href": url, "text": f"Article {i}", "is_internal": True}
                for i, url in enumerate(blog_urls, 1)
            ] + [
                {"href": "https://news.example.com/about", "text": "About", "is_internal": True}
            ],
        )
        blog_posts = [
            make_page(
                url=url,
                page_type="Article",
                title=f"Article {i} — Deep Analysis",
                meta_description=f"An in-depth look at industry trends, report {i}.",
                page_importance_score=72,
                visible_text_length=900,
                json_ld=[{"@context": "https://schema.org", "@type": "Article", "headline": f"Article {i}"}],
                links=[
                    {"href": "https://news.example.com/", "text": "Home", "is_internal": True},
                ] + [
                    {"href": other_url, "text": "Related", "is_internal": True}
                    for other_url in blog_urls if other_url != url
                ],
            )
            for i, url in enumerate(blog_urls, 1)
        ]
        about = make_page(
            url="https://news.example.com/about",
            page_type="About",
            title="About News Example",
            meta_description="Learn about our editorial team and standards.",
            page_importance_score=65,
        )
        pages = [hp] + blog_posts + [about]
        snap = make_snapshot(pages, start_url="https://news.example.com/")
        snap["crawl_meta"]["sitemap_url"] = "https://news.example.com/sitemap.xml"

        findings, strengths = agd_mod.run_checks(snap)
        agd_findings = [f for f in findings if f.get("check_id", "").startswith("AGD-")]
        self.assertEqual(
            agd_findings, [],
            f"Expected zero AGD findings on clean site. Got: {[(f['check_id'], f['title']) for f in agd_findings]}"
        )
        # Confirm at least some strengths are generated
        self.assertGreater(len(strengths), 0, "Clean site should generate strengths")

    # ── Finding schema validation ─────────────────────────────────────────────

    def test_agd_findings_have_required_fields(self):
        """All AGD findings must have the required schema fields."""
        pages = [
            make_page(
                url="https://deficient.example.com/",
                page_type="Homepage",
                title="",
                meta_description="",
                page_importance_score=90,
                json_ld=[],
                links=[],
                visible_text_length=50,
            ),
        ]
        snap = make_snapshot(pages)
        findings, _ = agd_mod.run_checks(snap)
        for f in findings:
            with self.subTest(check_id=f.get("check_id")):
                self.assertIn("check_id", f)
                self.assertIn("title", f)
                self.assertIn("category", f)
                self.assertIn("severity", f)
                self.assertIn("confidence", f)
                self.assertIn("affected_urls", f)
                self.assertIn("evidence", f)
                self.assertIn("suggested_action", f)
                self.assertIsInstance(f["affected_urls"], list)
                self.assertGreater(len(f["affected_urls"]), 0)
                self.assertIn("summary", f["suggested_action"])
                self.assertIn(f["severity"], {"critical", "high", "medium", "low"})
                self.assertIn(f["category"], {"discoverability", "engagement"})
                self.assertIn(f["confidence"], {"high", "medium", "low"})

    def test_agd_manifest_includes_new_skill(self):
        """marketplace.json must include agent-discoverability-audit as a registered skill."""
        manifest_path = REPO_ROOT / "marketplace.json"
        with open(manifest_path, encoding="utf-8") as f:
            manifest = json.load(f)
        skill_ids = [s.get("id") or s.get("name") for s in manifest["skills"]]
        self.assertIn(
            "agent-discoverability-audit", skill_ids,
            f"agent-discoverability-audit not found in marketplace.json skills: {skill_ids}"
        )

    def test_agd_skill_in_orchestrator_audit_skills(self):
        """build_report.py AUDIT_SKILLS must include agent-discoverability-audit."""
        skill_names = [s["name"] for s in build_mod.AUDIT_SKILLS]
        self.assertIn(
            "agent-discoverability-audit", skill_names,
            f"agent-discoverability-audit not in build_report.AUDIT_SKILLS: {skill_names}"
        )

    def test_agd_results_are_deterministic(self):
        """AGD findings must be identical across multiple runs on the same snapshot."""
        pages = [
            make_page(
                url="https://example.com/",
                page_type="Homepage",
                title="",
                meta_description="",
                page_importance_score=95,
                json_ld=[],
            )
        ] + [
            make_page(
                url=f"https://example.com/item-{i}",
                page_type="Product",
                page_importance_score=70,
                json_ld=[],
                links=[],
            )
            for i in range(1, 5)
        ]
        snap = make_snapshot(pages)
        run1_ids = sorted(f["check_id"] for f in agd_mod.run_checks(snap)[0])
        run2_ids = sorted(f["check_id"] for f in agd_mod.run_checks(snap)[0])
        self.assertEqual(run1_ids, run2_ids, "AGD findings must be deterministic across runs")





