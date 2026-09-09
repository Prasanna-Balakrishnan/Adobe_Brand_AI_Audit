"""
Phase 10 Remediation Regression Tests:
1. Robots.txt fallback on HTTP 404/non-200.
2. Defensive URL handling on missing, None, empty URL page dictionaries.
3. Generic bare brand/domain input resolution without hardcoding.
4. Deterministic output ordering of affected_urls.
"""
import unittest
from unittest.mock import patch, MagicMock
import sys
from pathlib import Path

# Add script paths
sys.path.insert(0, str(Path(__file__).parent.parent / "skills" / "site-crawler" / "scripts"))
sys.path.insert(0, str(Path(__file__).parent.parent / "skills" / "audit-orchestrator" / "scripts"))
sys.path.insert(0, str(Path(__file__).parent.parent / "skills" / "agent-discoverability-audit" / "scripts"))

from robots_check import RobotsChecker
from build_report import extract_target_url
from score import evaluate_agent_answerability, compute_summary
from normalize_findings import normalize_finding
from deduplicate_findings import merge_findings


class TestRobotsFallback(unittest.TestCase):
    def test_robots_404_treated_as_allowed(self):
        checker = RobotsChecker("https://example.com/robots.txt")
        checker.robots_status = 404
        self.assertTrue(checker.is_allowed("https://example.com/"))
        self.assertTrue(checker.is_allowed("https://example.com/any-page"))

    def test_robots_403_treated_as_allowed(self):
        checker = RobotsChecker("https://example.com/robots.txt")
        checker.robots_status = 403
        self.assertTrue(checker.is_allowed("https://example.com/"))

    def test_robots_500_treated_as_allowed(self):
        checker = RobotsChecker("https://example.com/robots.txt")
        checker.robots_status = 500
        self.assertTrue(checker.is_allowed("https://example.com/"))

    def test_robots_0_treated_as_allowed(self):
        checker = RobotsChecker("https://example.com/robots.txt")
        checker.robots_status = 0
        self.assertTrue(checker.is_allowed("https://example.com/"))

    def test_robots_200_enforces_rules(self):
        checker = RobotsChecker("https://example.com/robots.txt")
        checker.robots_status = 200
        checker._parser.parse([
            "User-agent: *",
            "Disallow: /admin/",
            "Allow: /"
        ])
        self.assertTrue(checker.is_allowed("https://example.com/about"))
        self.assertFalse(checker.is_allowed("https://example.com/admin/settings"))


class TestDefensiveUrlHandling(unittest.TestCase):
    def test_missing_url_does_not_crash_answerability(self):
        snapshot = {
            "target_url": "https://example.com",
            "pages": [
                {},  # completely empty page dict
                {"title": "No URL page", "body_text": "Content here"},
                {"url": None, "final_url": None, "title": "Null page"},
                {"url": "", "title": "Empty URL page"}
            ]
        }
        res = evaluate_agent_answerability(snapshot, [])
        self.assertIsInstance(res, list)
        self.assertTrue(len(res) >= 5)

    def test_missing_url_does_not_crash_scoring(self):
        snapshot = {
            "target_url": "https://example.com",
            "pages": [
                {"status_code": 200, "title": "Page 1"},
                {"url": None, "status_code": 200},
                {}
            ]
        }
        summary = compute_summary([], snapshot)
        self.assertIn("ai_readiness_score", summary)
        self.assertIn("overall_score", summary)


class TestGenericSimpleNameResolution(unittest.TestCase):
    def test_bare_brands_resolve_generically(self):
        self.assertEqual(extract_target_url("amazon"), "https://www.amazon.com")
        self.assertEqual(extract_target_url("flipkart"), "https://www.flipkart.com")
        self.assertEqual(extract_target_url("microsoft"), "https://www.microsoft.com")
        self.assertEqual(extract_target_url("adobe"), "https://www.adobe.com")
        self.assertEqual(extract_target_url("python"), "https://www.python.com")
        self.assertEqual(extract_target_url("curl"), "https://www.curl.com")

    def test_domains_with_tld_preserved(self):
        self.assertEqual(extract_target_url("amazon.com"), "https://amazon.com")
        self.assertEqual(extract_target_url("flipkart.com"), "https://flipkart.com")
        self.assertEqual(extract_target_url("python.org"), "https://python.org")
        self.assertEqual(extract_target_url("w3.org"), "https://w3.org")
        self.assertEqual(extract_target_url("curl.se"), "https://curl.se")

    def test_natural_language_queries(self):
        self.assertEqual(extract_target_url("the amazon website"), "https://www.amazon.com")
        self.assertEqual(extract_target_url("check the flipkart website"), "https://www.flipkart.com")
        self.assertEqual(extract_target_url("the microsoft website"), "https://www.microsoft.com")


class TestDeterministicUrls(unittest.TestCase):
    def test_normalized_finding_urls_are_sorted(self):
        raw = {
            "check_id": "TEST-001",
            "title": "Test Title",
            "category": "discoverability",
            "severity": "medium",
            "confidence": "high",
            "affected_urls": ["https://example.com/z", "https://example.com/a", "https://example.com/m"],
            "evidence": "Evidence text",
            "suggested_action": {"summary": "Action"}
        }
        res = normalize_finding(raw, "test-skill")
        self.assertEqual(res["affected_urls"], ["https://example.com/a", "https://example.com/m", "https://example.com/z"])

    def test_merged_findings_urls_are_sorted(self):
        p = {
            "title": "A", "evidence": "Ev A", "category": "discoverability", "source_skill": "s1",
            "affected_urls": ["https://example.com/z", "https://example.com/b"]
        }
        s = {
            "title": "B", "evidence": "Ev B", "source_skill": "s2",
            "affected_urls": ["https://example.com/a", "https://example.com/m"]
        }
        merged = merge_findings(p, s)
        self.assertEqual(merged["affected_urls"], [
            "https://example.com/a", "https://example.com/b", "https://example.com/m", "https://example.com/z"
        ])


if __name__ == "__main__":
    unittest.main()
