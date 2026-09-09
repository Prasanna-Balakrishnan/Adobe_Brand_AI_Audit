"""
test_recommendations.py — Phase 6: Recommendation Quality & Prioritization Tests

Covers:
  - Part 10: Anti-overfitting across arbitrary domains
  - Part 11: Positive recommendation generation, contextual guidance, traceability,
             priority vs page importance, deterministic ordering, deduplication
  - Part 12: Negative tests (no mutations, no HTTP operations, no fabricated data)
  - Part 13: 9 generic website archetypes
  - Part 14: Score boundary validation (min/max, 0 findings, 50 findings, bounds)
  - Part 15: Determinism validation across repeated runs
"""

import copy
import math
import sys
import unittest
from pathlib import Path

# Add orchestrator to sys.path
THIS_DIR = Path(__file__).parent
MARKETPLACE_ROOT = THIS_DIR.parent
ORCHESTRATOR_SCRIPTS = MARKETPLACE_ROOT / "skills" / "audit-orchestrator" / "scripts"
sys.path.insert(0, str(ORCHESTRATOR_SCRIPTS))

import score as score_mod  # type: ignore[import-not-found]
import deduplicate_findings as dedup_mod  # type: ignore[import-not-found]


class TestRecommendationQualityAndTraceability(unittest.TestCase):
    """Part 11: Tests for recommendation quality, traceability, and advisory nature."""

    def test_recommendation_generated_for_real_finding(self):
        """Real finding has an advisory suggested_action with summary, priority, and effort."""
        finding = {
            "id": "F-001",
            "title": "Missing Schema.org Product structured data",
            "category": "discoverability",
            "severity": "high",
            "confidence": "high",
            "tags": ["json-ld", "structured-data"],
            "affected_urls": ["https://example-alpha.test/products/item-1"],
            "evidence": "No Product JSON-LD block found on product page.",
            "suggested_action": {
                "summary": "Consider providing Schema.org Product structured data for core catalog items.",
                "priority": "high",
                "effort": "low"
            }
        }
        res = score_mod.validate_recommendation_quality(finding)
        self.assertTrue(res["is_advisory_only"])
        self.assertTrue(res["has_advisory_language"])
        self.assertTrue(res["is_traceable"])
        self.assertTrue(res["no_fabricated_values"])
        self.assertEqual(res["issues"], [])

    def test_recommendation_contains_contextual_guidance(self):
        """Recommendation contains contextual guidance rather than vague text like 'Improve SEO'."""
        finding = {
            "id": "F-002",
            "title": "Missing meta description",
            "category": "discoverability",
            "severity": "medium",
            "confidence": "high",
            "tags": ["meta-description"],
            "affected_urls": ["https://demo-business.test/services"],
            "evidence": "Page lacks a meta description tag.",
            "suggested_action": {
                "summary": "Consider providing a unique title and meta description that clearly identifies the page's primary topic and service offerings.",
                "priority": "medium",
                "effort": "low"
            }
        }
        res = score_mod.validate_recommendation_quality(finding)
        self.assertTrue(res["has_advisory_language"])
        self.assertTrue(res["is_traceable"])
        self.assertGreater(len(finding["suggested_action"]["summary"]), 25)

    def test_recommendation_does_not_invent_facts(self):
        """Recommendation does not invent prices, dates, or contact info not in evidence."""
        finding_with_fake = {
            "id": "F-003",
            "title": "Unclear pricing",
            "category": "discoverability",
            "severity": "medium",
            "confidence": "low",
            "affected_urls": ["https://random-company.test/pricing"],
            "evidence": "No price was listed on the page.",
            "suggested_action": {
                "summary": "Change the price to $49.00 and publish the tier immediately.",
                "priority": "medium",
                "effort": "low"
            }
        }
        res = score_mod.validate_recommendation_quality(finding_with_fake)
        self.assertFalse(res["is_advisory_only"])
        self.assertFalse(res["no_fabricated_values"])
        self.assertTrue(any("fabricated/prescribed price" in issue for issue in res["issues"]))

    def test_recommendation_does_not_prescribe_unsupported_exact_values(self):
        """Advisory recommendation suggests synchronization rather than prescribing arbitrary values."""
        finding = {
            "id": "F-004",
            "title": "Conflicting price representation",
            "category": "discoverability",
            "severity": "high",
            "confidence": "high",
            "tags": ["price-conflict", "trust"],
            "affected_urls": ["https://example-alpha.test/plans"],
            "evidence": "Visible content states $29 while JSON-LD offer states $39.",
            "suggested_action": {
                "summary": "Consider ensuring the displayed price and structured-data offer remain synchronized across all page views.",
                "priority": "high",
                "effort": "low"
            }
        }
        res = score_mod.validate_recommendation_quality(finding)
        self.assertTrue(res["is_advisory_only"])
        self.assertTrue(res["no_fabricated_values"])
        self.assertEqual(res["issues"], [])

    def test_recommendation_references_relevant_issue(self):
        """Recommendation tokens overlap with finding evidence/title/tags (traceability)."""
        finding_unrelated = {
            "id": "F-005",
            "title": "Broken image links detected",
            "category": "discoverability",
            "severity": "low",
            "confidence": "high",
            "tags": ["broken-link"],
            "affected_urls": ["https://example-alpha.test/gallery"],
            "evidence": "Three image assets returned HTTP 404.",
            "suggested_action": {
                "summary": "Consider configuring SSL certificates and enforcing HTTPS redirection.",
                "priority": "low",
                "effort": "medium"
            }
        }
        res = score_mod.validate_recommendation_quality(finding_unrelated)
        self.assertFalse(res["is_traceable"])
        self.assertTrue(any("not share key concepts" in i for i in res["issues"]))

    def test_missing_evidence_does_not_produce_fabricated_recommendation(self):
        """Missing company information produces cautious 'Not found' advice, never fabricated facts."""
        snapshot = {
            "crawl_meta": {"start_url": "https://example-alpha.test/"},
            "pages": [
                {
                    "url": "https://example-alpha.test/",
                    "title": "Alpha Portal",
                    "visible_text_sample": "Welcome to our portal.",
                    "page_importance_score": 90
                }
            ]
        }
        answers = score_mod.evaluate_agent_answerability(snapshot)
        # Pricing question should be 'Not found' and recommendation must not invent a price
        q_price = next(q for q in answers if q["category"] == "pricing")
        self.assertEqual(q_price["status"], "Not found")
        self.assertNotIn("$", q_price["recommendation"])
        self.assertIn("transparent", q_price["recommendation"].lower())

    def test_conflicting_evidence_produces_cautious_recommendation(self):
        """Conflicting evidence triggers cautious reconciliation advice."""
        snapshot = {
            "crawl_meta": {"start_url": "https://example-alpha.test/"},
            "pages": [
                {
                    "url": "https://example-alpha.test/",
                    "title": "Alpha Portal",
                    "visible_text_sample": "Product price is $29/mo.",
                    "page_importance_score": 90
                }
            ]
        }
        findings = [
            {
                "id": "F-CONF",
                "title": "Pricing contradiction detected",
                "category": "discoverability",
                "severity": "high",
                "tags": ["price-conflict", "contradiction"],
                "evidence": "Conflicting price declarations between landing page and cart ($29 vs $49)."
            }
        ]
        answers = score_mod.evaluate_agent_answerability(snapshot, findings=findings)
        q_price = next(q for q in answers if q["category"] == "pricing")
        self.assertEqual(q_price["status"], "Conflicting")
        self.assertTrue(q_price["recommendation"].startswith("Consider"))
        self.assertIn("reconciling", q_price["recommendation"].lower())

    def test_clean_website_produces_no_unnecessary_recommendations(self):
        """A clean, well-structured website produces zero unnecessary recommendations."""
        clean_snapshot = {
            "crawl_meta": {"start_url": "https://clean-example.test/"},
            "pages": [
                {
                    "url": "https://clean-example.test/",
                    "title": "Clean Example Home",
                    "meta_description": "Clean Example provides reliable cloud management solutions.",
                    "h1": ["Clean Example Solutions"],
                    "json_ld": [
                        {
                            "@type": "Organization",
                            "name": "Clean Example Inc",
                            "description": "Clean Example provides reliable cloud management solutions.",
                            "contactPoint": {"telephone": "+1-800-555-0199", "email": "support@clean-example.test"},
                            "address": {"streetAddress": "123 Clean Way", "addressLocality": "Austin", "addressCountry": "US"}
                        }
                    ],
                    "page_importance_score": 95,
                    "page_type": "Homepage"
                },
                {
                    "url": "https://clean-example.test/pricing",
                    "title": "Transparent Pricing - Clean Example",
                    "meta_description": "Transparent pricing starting at $29 per month.",
                    "h1": ["Pricing Plans"],
                    "visible_text_sample": "Plans start at $29 per month with full support.",
                    "json_ld": [
                        {
                            "@type": "Product",
                            "name": "Cloud Manager",
                            "offers": {"@type": "Offer", "price": "29", "priceCurrency": "USD"}
                        }
                    ],
                    "page_importance_score": 80,
                    "page_type": "Pricing"
                }
            ]
        }
        answers = score_mod.evaluate_agent_answerability(clean_snapshot, findings=[])
        # On a clean site, all answerability questions are Supported
        unsupported = [q for q in answers if q["status"] != "Supported"]
        self.assertEqual(len(unsupported), 0, f"Clean site has unsupported questions: {unsupported}")
        # All recommendations for supported questions should be None
        for q in answers:
            self.assertIsNone(q["recommendation"])


class TestPrioritizationHierarchy(unittest.TestCase):
    """Part 5 & 6: Tests for multi-factor priority calculation and ranking."""

    def test_high_severity_outranks_low_severity(self):
        """High-severity issue outranks low-severity issue on equivalent pages."""
        findings = [
            {
                "id": "F-LOW",
                "title": "Minor styling inconsistency",
                "severity": "low",
                "confidence": "high",
                "affected_urls": ["https://example-alpha.test/p1"],
                "suggested_action": {"summary": "Consider reviewing visual styling."}
            },
            {
                "id": "F-CRIT",
                "title": "Robots.txt blocks all crawlers",
                "severity": "critical",
                "confidence": "high",
                "affected_urls": ["https://example-alpha.test/p1"],
                "suggested_action": {"summary": "Consider removing disallow in robots.txt."}
            }
        ]
        priorities = score_mod.compute_top_priorities(findings, limit=5)
        self.assertEqual(priorities[0]["id"], "F-CRIT")
        self.assertGreater(priorities[0]["priority_score"], priorities[1]["priority_score"])

    def test_high_importance_page_outranks_low_importance_page(self):
        """Same-severity issue on a high-importance page outranks one on a low-importance page."""
        snapshot = {
            "pages": [
                {"url": "https://example-alpha.test/home", "page_importance_score": 95},
                {"url": "https://example-alpha.test/archived/old-post", "page_importance_score": 15}
            ]
        }
        findings = [
            {
                "id": "F-LOW-IMP",
                "title": "Missing title on archive",
                "severity": "high",
                "confidence": "high",
                "affected_urls": ["https://example-alpha.test/archived/old-post"],
                "suggested_action": {"summary": "Consider adding descriptive title."}
            },
            {
                "id": "F-HIGH-IMP",
                "title": "Missing title on homepage",
                "severity": "high",
                "confidence": "high",
                "affected_urls": ["https://example-alpha.test/home"],
                "suggested_action": {"summary": "Consider adding authoritative homepage title."}
            }
        ]
        priorities = score_mod.compute_top_priorities(findings, limit=5, snapshot=snapshot)
        self.assertEqual(priorities[0]["id"], "F-HIGH-IMP")
        self.assertGreater(priorities[0]["priority_score"], priorities[1]["priority_score"])

    def test_critical_on_high_importance_outranks_multiple_low_severity_on_low_importance(self):
        """1 critical issue on an important page outranks 5 minor issues on low-value pages."""
        snapshot = {
            "pages": [
                {"url": "https://example-alpha.test/primary", "page_importance_score": 90},
                {"url": "https://example-alpha.test/aux1", "page_importance_score": 20},
                {"url": "https://example-alpha.test/aux2", "page_importance_score": 20},
                {"url": "https://example-alpha.test/aux3", "page_importance_score": 20},
                {"url": "https://example-alpha.test/aux4", "page_importance_score": 20},
                {"url": "https://example-alpha.test/aux5", "page_importance_score": 20}
            ]
        }
        findings = [
            {
                "id": "F-MINOR-MANY",
                "title": "Minor link hygiene issues",
                "severity": "low",
                "confidence": "high",
                "affected_urls": [
                    "https://example-alpha.test/aux1",
                    "https://example-alpha.test/aux2",
                    "https://example-alpha.test/aux3",
                    "https://example-alpha.test/aux4",
                    "https://example-alpha.test/aux5"
                ],
                "suggested_action": {"summary": "Consider updating internal link anchors."}
            },
            {
                "id": "F-CRITICAL-KEY",
                "title": "Primary page HTTP 500 error",
                "severity": "critical",
                "confidence": "high",
                "affected_urls": ["https://example-alpha.test/primary"],
                "suggested_action": {"summary": "Consider resolving internal server error."}
            }
        ]
        priorities = score_mod.compute_top_priorities(findings, limit=5, snapshot=snapshot)
        self.assertEqual(priorities[0]["id"], "F-CRITICAL-KEY")


class TestDuplicateRecommendationHandling(unittest.TestCase):
    """Part 7: Deduplication of duplicate recommendations while keeping distinct ones separate."""

    def test_multiple_identical_recommendations_are_appropriately_deduplicated(self):
        """Identical recommendations across findings are merged into a single priority item with combined reach."""
        items = [
            {
                "id": "F-001",
                "title": "Missing JSON-LD on product 1",
                "category": "discoverability",
                "severity": "high",
                "priority_score": 35.0,
                "affected_urls": ["https://example-alpha.test/p1"],
                "evidence": "Product 1 missing schema.",
                "suggested_action": {"summary": "Consider providing Schema.org Product structured data."}
            },
            {
                "id": "F-002",
                "title": "Missing JSON-LD on product 2",
                "category": "discoverability",
                "severity": "high",
                "priority_score": 35.0,
                "affected_urls": ["https://example-alpha.test/p2"],
                "evidence": "Product 2 missing schema.",
                "suggested_action": {"summary": "Consider providing Schema.org Product structured data."}
            }
        ]
        deduped = score_mod.deduplicate_recommendations(items)
        self.assertEqual(len(deduped), 1)
        self.assertEqual(len(deduped[0]["affected_urls"]), 2)
        self.assertIn("https://example-alpha.test/p1", deduped[0]["affected_urls"])
        self.assertIn("https://example-alpha.test/p2", deduped[0]["affected_urls"])
        self.assertIn("Product 1", deduped[0]["evidence"])
        self.assertIn("Product 2", deduped[0]["evidence"])

    def test_distinct_recommendations_remain_distinct(self):
        """Distinct recommendations addressing different problems are not merged."""
        items = [
            {
                "id": "F-001",
                "title": "Missing JSON-LD",
                "category": "discoverability",
                "severity": "high",
                "affected_urls": ["https://example-alpha.test/p1"],
                "evidence": "No structured data.",
                "suggested_action": {"summary": "Consider providing Schema.org Product structured data."}
            },
            {
                "id": "F-002",
                "title": "Broken canonical tag",
                "category": "discoverability",
                "severity": "high",
                "affected_urls": ["https://example-alpha.test/p1"],
                "evidence": "Canonical points to 404.",
                "suggested_action": {"summary": "Consider updating canonical URL to an active HTTP 200 endpoint."}
            }
        ]
        deduped = score_mod.deduplicate_recommendations(items)
        self.assertEqual(len(deduped), 2)
        self.assertEqual(deduped[0]["id"], "F-001")
        self.assertEqual(deduped[1]["id"], "F-002")


class TestNegativeConstraints(unittest.TestCase):
    """Part 12: Negative tests verifying that recommendations NEVER perform or suggest mutations."""

    def test_no_http_mutation_operations(self):
        """Validator rejects suggestions with HTTP mutation operations."""
        bad_action = {
            "id": "F-BAD-1",
            "title": "Database sync needed",
            "evidence": "Outdated data.",
            "suggested_action": {"summary": "Issue an HTTP POST request to update catalog records."}
        }
        res = score_mod.validate_recommendation_quality(bad_action)
        self.assertFalse(res["is_advisory_only"])
        self.assertTrue(any("Mutation phrase" in i for i in res["issues"]))

    def test_no_claim_that_fix_was_applied(self):
        """Validator rejects suggestions claiming that a fix was already applied."""
        bad_action = {
            "id": "F-BAD-2",
            "title": "Robots error",
            "evidence": "Disallow rule.",
            "suggested_action": {"summary": "We updated the robots.txt file and fix has been applied."}
        }
        res = score_mod.validate_recommendation_quality(bad_action)
        self.assertFalse(res["is_advisory_only"])

    def test_no_direct_html_or_file_mutations(self):
        """Validator rejects suggestions directing immediate file mutation or upload."""
        bad_actions = [
            "Modify the HTML file directly on the production server.",
            "Upload new sitemap.xml to root directory immediately.",
            "Edit the robots.txt to unblock crawlers right now."
        ]
        for act in bad_actions:
            res = score_mod.validate_recommendation_quality({
                "id": "F-TEST",
                "title": "Test",
                "evidence": "Issue.",
                "suggested_action": {"summary": act}
            })
            self.assertFalse(res["is_advisory_only"], f"Failed to catch mutation: {act}")

    def test_no_fabricated_dates_or_prices(self):
        """Validator rejects fabricated specific dates or prices not found in evidence."""
        bad_finding = {
            "id": "F-DATE-FAKE",
            "title": "Event date missing",
            "evidence": "No event date was declared anywhere.",
            "suggested_action": {"summary": "Consider setting the event date to December 25, 2026."}
        }
        res = score_mod.validate_recommendation_quality(bad_finding)
        self.assertFalse(res["no_fabricated_values"])
        self.assertTrue(any("fabricated date" in i for i in res["issues"]))

    def test_no_fabricated_contact_details(self):
        """Validator rejects fabricated specific email addresses or telephone numbers."""
        bad_finding = {
            "id": "F-CONTACT-FAKE",
            "title": "Contact info missing",
            "evidence": "No contact channels found on website.",
            "suggested_action": {"summary": "Consider contacting support@fictional-domain.test or calling +1-800-999-0000."}
        }
        res = score_mod.validate_recommendation_quality(bad_finding)
        self.assertFalse(res["no_fabricated_values"])
        self.assertTrue(any("fabricated email" in i for i in res["issues"]))

    def test_no_fabricated_structured_data_values(self):
        """Recommendations advise exposing observed facts rather than fabricating structured data properties."""
        finding = {
            "id": "F-SD-ADVISORY",
            "title": "Product lacks structured data",
            "category": "discoverability",
            "severity": "high",
            "tags": ["json-ld", "structured-data"],
            "affected_urls": ["https://example-alpha.test/item"],
            "evidence": "Product name 'Widget Alpha' and price '$15.00' visible in content, but no Schema.org markup.",
            "suggested_action": {
                "summary": "Consider exposing the available product information and visible pricing through Schema.org Product structured data.",
                "priority": "high",
                "effort": "low"
            }
        }
        res = score_mod.validate_recommendation_quality(finding)
        self.assertTrue(res["is_advisory_only"])
        self.assertTrue(res["no_fabricated_values"])
        self.assertEqual(res["issues"], [])


class TestGenericWebsiteArchetypes(unittest.TestCase):
    """Part 10 & 13: Recommendation quality across 9 generic website archetypes on arbitrary domains."""

    def _build_snapshot(self, domain: str, ptype: str, headings: list[str], json_ld: list[dict]):
        return {
            "crawl_meta": {"start_url": f"https://{domain}/"},
            "pages": [
                {
                    "url": f"https://{domain}/",
                    "title": f"{domain} Home",
                    "h1": headings,
                    "headings": [{"level": 1, "text": h} for h in headings],
                    "json_ld": json_ld,
                    "page_importance_score": 90,
                    "page_type": "Homepage"
                },
                {
                    "url": f"https://{domain}/detail",
                    "title": f"{domain} {ptype}",
                    "h1": [f"Our {ptype}"],
                    "headings": [{"level": 1, "text": f"Our {ptype}"}],
                    "json_ld": json_ld,
                    "page_importance_score": 75,
                    "page_type": ptype
                }
            ]
        }

    def test_01_ecommerce_archetype(self):
        """E-commerce: Evaluates product structured data and pricing answerability."""
        snap = self._build_snapshot("shop-alpha.test", "Product", ["Buy Widgets"], [
            {"@type": "Product", "name": "Alpha Widget", "offers": {"@type": "Offer", "price": "19.99", "priceCurrency": "USD"}}
        ])
        answers = score_mod.evaluate_agent_answerability(snap)
        q_prod = next(q for q in answers if q["category"] == "offerings")
        q_price = next(q for q in answers if q["category"] == "pricing")
        self.assertEqual(q_prod["status"], "Supported")
        self.assertEqual(q_price["status"], "Supported")

    def test_02_service_business_archetype(self):
        """Service business: Professional services discovery."""
        snap = self._build_snapshot("consulting-beta.test", "Service", ["Strategic Advisory"], [
            {"@type": "Service", "name": "Enterprise AI Audit"}
        ])
        answers = score_mod.evaluate_agent_answerability(snap)
        q_prod = next(q for q in answers if q["category"] == "offerings")
        self.assertEqual(q_prod["status"], "Supported")

    def test_03_restaurant_archetype(self):
        """Restaurant: Local business with opening hours."""
        snap = self._build_snapshot("bistro-gamma.test", "Other", ["Neighborhood Dining"], [
            {"@type": "Restaurant", "name": "Gamma Bistro", "openingHours": "Mo-Su 11:00-22:00"}
        ])
        answers = score_mod.evaluate_agent_answerability(snap, dynamic=True)
        q_hours = next((q for q in answers if q["category"] == "hours"), None)
        self.assertIsNotNone(q_hours)
        self.assertEqual(q_hours["status"], "Supported")

    def test_04_healthcare_archetype(self):
        """Healthcare: Medical clinic services."""
        snap = self._build_snapshot("health-clinic.test", "Service", ["Family Medicine"], [
            {"@type": "MedicalClinic", "name": "Community Health"}
        ])
        answers = score_mod.evaluate_agent_answerability(snap, dynamic=True)
        q_off = next(q for q in answers if q["category"] == "offerings")
        self.assertEqual(q_off["status"], "Supported")

    def test_05_university_archetype(self):
        """University: Educational programs and degrees."""
        snap = self._build_snapshot("state-university.test", "Other", ["Undergraduate Programs"], [
            {"@type": "EducationalOccupationalProgram", "name": "B.S. Computer Science"}
        ])
        answers = score_mod.evaluate_agent_answerability(snap)
        q_off = next(q for q in answers if q["category"] == "offerings")
        self.assertEqual(q_off["status"], "Supported")

    def test_06_saas_software_archetype(self):
        """SaaS / Software: Application and software offers."""
        snap = self._build_snapshot("cloud-saas.test", "Product", ["Cloud Automation Platform"], [
            {"@type": "SoftwareApplication", "name": "SyncCloud"}
        ])
        answers = score_mod.evaluate_agent_answerability(snap)
        q_off = next(q for q in answers if q["category"] == "offerings")
        self.assertEqual(q_off["status"], "Supported")

    def test_07_documentation_archetype(self):
        """Documentation: API docs and developer guides."""
        snap = self._build_snapshot("developer-docs.test", "Documentation", ["Developer API Reference"], [])
        answers = score_mod.evaluate_agent_answerability(snap, dynamic=True)
        q_docs = next((q for q in answers if q["category"] == "documentation"), None)
        self.assertIsNotNone(q_docs)
        self.assertEqual(q_docs["status"], "Supported")

    def test_08_event_archetype(self):
        """Event: Scheduled conference or webinar."""
        snap = self._build_snapshot("global-summit.test", "Event", ["Annual Tech Summit"], [
            {"@type": "Event", "name": "Tech Summit 2026", "startDate": "2026-11-15"}
        ])
        answers = score_mod.evaluate_agent_answerability(snap, dynamic=True)
        q_event = next((q for q in answers if q["category"] == "events"), None)
        self.assertIsNotNone(q_event)
        self.assertEqual(q_event["status"], "Supported")

    def test_09_informational_archetype(self):
        """Informational / Publisher: Clean article attribution and purpose."""
        snap = self._build_snapshot("news-journal.test", "Article", ["World Reports"], [
            {"@type": "NewsArticle", "headline": "Scientific Breakthrough"}
        ])
        answers = score_mod.evaluate_agent_answerability(snap)
        self.assertTrue(len(answers) >= 5)


class TestScoreBoundaries(unittest.TestCase):
    """Part 14: Score boundary conditions, empty/large sets, finite values."""

    def test_zero_findings_score_bounds(self):
        """Zero findings returns empty top_priorities and perfect 100 readiness score."""
        summary = score_mod.compute_summary([])
        self.assertEqual(summary["ai_readiness_score"], 100)
        self.assertEqual(summary["total_findings"], 0)

        priorities = score_mod.compute_top_priorities([])
        self.assertEqual(priorities, [])

    def test_one_finding_score_bounds(self):
        """Single finding yields bounded priority score between 0.0 and 100.0."""
        finding = {
            "id": "F-001",
            "title": "Critical server crash",
            "severity": "critical",
            "confidence": "high",
            "affected_urls": ["https://example-alpha.test/"],
            "suggested_action": {"summary": "Consider resolving internal server crash."}
        }
        priorities = score_mod.compute_top_priorities([finding])
        self.assertEqual(len(priorities), 1)
        score = priorities[0]["priority_score"]
        self.assertGreaterEqual(score, 0.0)
        self.assertLessEqual(score, 100.0)
        self.assertFalse(math.isnan(score))
        self.assertFalse(math.isinf(score))

    def test_many_findings_scores_remain_bounded(self):
        """50 findings all produce finite, non-negative scores clamped to [0.0, 100.0]."""
        findings = []
        for i in range(50):
            findings.append({
                "id": f"F-{i:03d}",
                "title": f"Issue {i}",
                "severity": ["critical", "high", "medium", "low"][i % 4],
                "confidence": ["high", "medium", "low"][i % 3],
                "affected_urls": [f"https://example.test/page-{j}" for j in range(i % 5 + 1)],
                "suggested_action": {"summary": f"Consider fixing issue {i}."}
            })
        priorities = score_mod.compute_top_priorities(findings, limit=10)
        self.assertEqual(len(priorities), 10)
        for p in priorities:
            score = p["priority_score"]
            self.assertGreaterEqual(score, 0.0)
            self.assertLessEqual(score, 100.0)
            self.assertFalse(math.isnan(score))

    def test_extreme_importance_scores(self):
        """Importance scores of 0 and 100 do not produce negative or unbounded values."""
        snapshot = {
            "pages": [
                {"url": "https://example.test/zero", "page_importance_score": 0},
                {"url": "https://example.test/max", "page_importance_score": 100}
            ]
        }
        findings = [
            {
                "id": "F-ZERO",
                "title": "Issue on zero importance",
                "severity": "low",
                "confidence": "low",
                "affected_urls": ["https://example.test/zero"],
                "suggested_action": {"summary": "Consider checking zero page."}
            },
            {
                "id": "F-MAX",
                "title": "Issue on max importance",
                "severity": "critical",
                "confidence": "high",
                "affected_urls": ["https://example.test/max"],
                "suggested_action": {"summary": "Consider checking max page."}
            }
        ]
        priorities = score_mod.compute_top_priorities(findings, limit=5, snapshot=snapshot)
        for p in priorities:
            self.assertGreaterEqual(p["priority_score"], 0.0)
            self.assertLessEqual(p["priority_score"], 100.0)


class TestDeterminism(unittest.TestCase):
    """Part 15: Determinism validation across repeated runs."""

    def test_top_priorities_strictly_deterministic(self):
        """Repeatedly computing top priorities on identical input produces identical output."""
        findings = [
            {
                "id": "F-003",
                "title": "Medium severity B",
                "severity": "medium",
                "confidence": "high",
                "affected_urls": ["https://example.test/p2"],
                "suggested_action": {"summary": "Consider reviewing medium B."}
            },
            {
                "id": "F-001",
                "title": "Critical severity A",
                "severity": "critical",
                "confidence": "high",
                "affected_urls": ["https://example.test/p1"],
                "suggested_action": {"summary": "Consider fixing critical A."}
            },
            {
                "id": "F-002",
                "title": "High severity C",
                "severity": "high",
                "confidence": "medium",
                "affected_urls": ["https://example.test/p3", "https://example.test/p4"],
                "suggested_action": {"summary": "Consider addressing high C."}
            }
        ]

        baseline = score_mod.compute_top_priorities(copy.deepcopy(findings), limit=3)

        for _ in range(25):
            run = score_mod.compute_top_priorities(copy.deepcopy(findings), limit=3)
            self.assertEqual(len(run), len(baseline))
            for b_item, r_item in zip(baseline, run):
                self.assertEqual(b_item["id"], r_item["id"])
                self.assertEqual(b_item["priority_rank"], r_item["priority_rank"])
                self.assertEqual(b_item["priority_score"], r_item["priority_score"])
                self.assertEqual(b_item["suggested_action"], r_item["suggested_action"])


if __name__ == "__main__":
    unittest.main()
