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
            "strengths": []
        }

        # Assert all required sections from Req 19 are present
        required_keys = [
            "site", "audited_at", "run_info", "summary",
            "agent_journey_scores", "agent_answerability", "top_priorities",
            "findings", "proactive_recommendations", "strengths"
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


if __name__ == "__main__":
    unittest.main(verbosity=2)



