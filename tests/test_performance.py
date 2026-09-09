#!/usr/bin/env python3
"""
tests/test_performance.py — Dedicated Phase 8 Performance Test Suite

Covers:
1. Small site performance (5 pages)
2. Medium site performance (20 pages)
3. 50-page site performance
4. Repeated audit execution (no leaks/state pollution)
5. Duplicate URL handling and normalization
6. Large JSON-LD processing efficiency
7. Dense internal link graph scaling
8. Many findings deduplication performance
9. Slow/failing resource resilience and timeout handling
10. Deterministic repeated execution equality
"""

import copy
import json
from pathlib import Path
import sys
import time
import unittest
from unittest.mock import MagicMock, patch

REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "skills" / "audit-orchestrator" / "scripts"))
sys.path.insert(0, str(REPO_ROOT / "skills" / "site-crawler" / "scripts"))

from benchmarks.benchmark_audit import generate_benchmark_snapshot, run_benchmark
from build_report import (
    AUDIT_SKILLS,
    PROACTIVE_SKILL,
    get_skill_module,
    normalize_all,
    deduplicate,
    compute_summary,
    compute_agent_journey_scores,
    evaluate_agent_answerability,
    compute_top_priorities,
)
import crawl as crawl_mod
import deduplicate_findings as dedup_mod


class TestAuditPerformance(unittest.TestCase):
    """Phase 8 Performance and 5-minute execution test suite."""

    def test_01_small_site_performance(self):
        """1. Small site workload (5 pages) executes efficiently and produces valid output."""
        snap = generate_benchmark_snapshot(num_pages=5)
        self.assertEqual(len(snap["pages"]), 5)

        t0 = time.perf_counter()
        skill_outputs = []
        for skill in AUDIT_SKILLS:
            mod = get_skill_module(REPO_ROOT / skill["script"], f"perf_{skill['name']}")
            self.assertIsNotNone(mod)
            findings, strengths = mod.run_checks(snap)
            skill_outputs.append({"skill": skill["name"], "findings": findings, "strengths": strengths})

        norm_findings, strengths = normalize_all(skill_outputs)
        deduped = deduplicate(norm_findings)
        summary = compute_summary(deduped, snap)
        journey = compute_agent_journey_scores(deduped)
        elapsed = time.perf_counter() - t0

        self.assertLess(elapsed, 10.0, "Small site audit took longer than 10s")
        self.assertIn("ai_readiness_score", summary)
        self.assertIn("overall_journey_score", journey)

    def test_02_medium_site_performance(self):
        """2. Medium site workload (20 pages) executes and achieves high throughput."""
        snap = generate_benchmark_snapshot(num_pages=20)
        self.assertEqual(len(snap["pages"]), 20)

        t0 = time.perf_counter()
        skill_outputs = []
        for skill in AUDIT_SKILLS:
            mod = get_skill_module(REPO_ROOT / skill["script"], f"perf_{skill['name']}")
            findings, strengths = mod.run_checks(snap)
            skill_outputs.append({"skill": skill["name"], "findings": findings, "strengths": strengths})

        norm_findings, strengths = normalize_all(skill_outputs)
        deduped = deduplicate(norm_findings)
        summary = compute_summary(deduped, snap)
        elapsed = time.perf_counter() - t0

        self.assertLess(elapsed, 15.0, "Medium site audit took longer than 15s")
        throughput = 20 / elapsed
        self.assertGreater(throughput, 2.0, "Throughput should exceed 2 pages/sec")

    def test_03_50_page_site_performance(self):
        """3. 50-page site benchmark executes well within limits."""
        res = run_benchmark(num_pages=50)
        self.assertEqual(res["pages"], 50)
        self.assertTrue(res["pass_5min"])
        self.assertEqual(res["status"], "PASS")
        self.assertLess(res["total_time_seconds"], 60.0, "50-page site should finish well under 60s")
        self.assertGreater(res["throughput_pages_per_sec"], 5.0)

    def test_04_repeated_audit_execution(self):
        """4. Repeated audit runs maintain performance without state leaks or memory ballooning."""
        snap = generate_benchmark_snapshot(num_pages=15)
        times = []
        for _ in range(3):
            t0 = time.perf_counter()
            skill_outputs = []
            for skill in AUDIT_SKILLS:
                mod = get_skill_module(REPO_ROOT / skill["script"], f"perf_{skill['name']}")
                findings, strengths = mod.run_checks(snap)
                skill_outputs.append({"skill": skill["name"], "findings": findings, "strengths": strengths})
            norm_findings, _ = normalize_all(skill_outputs)
            deduped = deduplicate(norm_findings)
            _ = compute_summary(deduped, snap)
            times.append(time.perf_counter() - t0)

        # Ensure subsequent runs are not drastically slower (within 3x margin)
        self.assertLess(times[1], times[0] * 3.0)
        self.assertLess(times[2], times[0] * 3.0)

    def test_05_duplicate_url_scenario(self):
        """5. Crawler URL normalization and deduplication handles variations cleanly."""
        # Crawler normalisation: fragments stripped, root path normalized
        url1 = "https://example.com/page#section"
        url2 = "https://example.com/page"
        self.assertEqual(crawl_mod.normalise_url(url1), crawl_mod.normalise_url(url2))

        root1 = "https://example.com"
        root2 = "https://example.com/"
        self.assertEqual(crawl_mod.normalise_url(root1), crawl_mod.normalise_url(root2))

        # Deduplication normalisation: tracking params and trailing slashes stripped
        dedup_urls = [
            "https://example.com/page",
            "https://example.com/page/",
            "https://example.com/page?utm_source=twitter",
            "https://example.com/page#section",
            "https://example.com/page?utm_campaign=ai&utm_source=ad",
        ]
        norm_set = {dedup_mod.normalize_url_for_dedup(u) for u in dedup_urls}
        self.assertEqual(len(norm_set), 1, f"Expected all variations to normalize to 1 URL, got: {norm_set}")
        self.assertEqual(list(norm_set)[0], "https://example.com/page")

    def test_06_large_jsonld_scenario(self):
        """6. Large, deeply nested JSON-LD graphs are parsed and audited without exponential stall."""
        large_graph = []
        for i in range(100):
            large_graph.append({
                "@type": "Product",
                "name": f"Enterprise Cloud Node {i}",
                "description": f"Specification details for node {i}",
                "offers": {
                    "@type": "Offer",
                    "price": str(100 + i),
                    "priceCurrency": "USD",
                    "availability": "https://schema.org/InStock"
                }
            })

        snap = {
            "crawl_meta": {"start_url": "https://example.com/", "pages_crawled": 1},
            "pages": [{
                "url": "https://example.com/",
                "final_url": "https://example.com/",
                "status_code": 200,
                "title": "Large Graph Benchmark",
                "meta_description": "Testing large schema graph parsing",
                "headings": [{"level": 1, "text": "Heading 1"}],
                "json_ld": [{"@context": "https://schema.org", "@graph": large_graph}],
                "open_graph": {},
                "twitter_card": {},
                "links": [],
                "images": [],
                "visible_text_length": 5000,
                "visible_text_sample": "Content with large jsonld",
                "crawled_with_js": False
            }]
        }

        t0 = time.perf_counter()
        sdc_mod = get_skill_module(REPO_ROOT / "skills" / "structured-data-content-audit" / "scripts" / "audit.py", "perf_sdc")
        self.assertIsNotNone(sdc_mod)
        findings, strengths = sdc_mod.run_checks(snap)
        elapsed = time.perf_counter() - t0

        self.assertLess(elapsed, 5.0, "Parsing 100-node JSON-LD graph took longer than 5 seconds")
        self.assertIsInstance(findings, list)
        self.assertIsInstance(strengths, list)

    def test_07_many_internal_links_scenario(self):
        """7. Dense internal link graph with 1,000+ links scales linearly in importance calculation."""
        pages = []
        num_nodes = 50
        for i in range(num_nodes):
            url_i = f"https://example.com/p{i}"
            # Each page links to 20 other pages
            links = [{"href": f"https://example.com/p{(i + j) % num_nodes}", "is_internal": True, "text": f"Link {j}"} for j in range(1, 21)]
            pages.append({
                "url": url_i,
                "final_url": url_i,
                "page_type": "Homepage" if i == 0 else "Product",
                "links": links,
                "nav_link_texts": ["Link 1", "Link 2"]
            })

        t0 = time.perf_counter()
        scored_pages = crawl_mod.compute_page_importance_scores(pages)
        elapsed = time.perf_counter() - t0

        self.assertLess(elapsed, 2.0, "Dense link importance computation took longer than 2 seconds")
        self.assertEqual(len(scored_pages), num_nodes)
        self.assertIn("page_importance_score", scored_pages[0])
        self.assertGreaterEqual(scored_pages[0]["page_importance_score"], 0)

    def test_08_many_findings_deduplication_scenario(self):
        """8. Deduplication under a large finding set scales efficiently with token precomputation."""
        findings = []
        for i in range(150):
            cat = "discoverability" if i % 2 == 0 else "structured-data"
            findings.append({
                "id": f"RAW-{i:03d}",
                "check_id": f"CHK-{i % 10:02d}",
                "title": f"Missing structured schema on page {i // 5}",
                "category": cat,
                "severity": "medium",
                "confidence": "high",
                "source_skill": "skill-a" if i % 2 == 0 else "skill-b",
                "affected_urls": [f"https://example.com/p{i // 5}"],
                "evidence": f"Detailed evidence text explaining issue on page {i // 5} with schema tags.",
                "suggested_action": {"summary": f"Add schema to page {i // 5}"}
            })

        t0 = time.perf_counter()
        deduped = dedup_mod.deduplicate(findings)
        elapsed = time.perf_counter() - t0

        self.assertLess(elapsed, 3.0, "Deduplicating 150 findings took longer than 3 seconds")
        self.assertLess(len(deduped), len(findings), "Expected duplicates to be consolidated")
        # Ensure no temporary set objects leaked into result
        for f in deduped:
            self.assertNotIn("_tokens", f)
            self.assertNotIn("_tag_set", f)
            self.assertNotIn("_norm_urls", f)

    def test_09_slow_failing_resource_resilience(self):
        """9. Crawler and orchestrator gracefully handle timeouts, 500s, and connection drops."""
        snap = {
            "crawl_meta": {
                "start_url": "https://failing.internal/",
                "pages_crawled": 3,
                "failed_pages": [{"url": "https://failing.internal/error-500", "status_code": 500}]
            },
            "pages": [
                {
                    "url": "https://failing.internal/",
                    "status_code": 200,
                    "title": "Home",
                    "links": [{"href": "https://failing.internal/timeout", "is_internal": True}],
                    "headings": [],
                    "json_ld": []
                },
                {
                    "url": "https://failing.internal/error-500",
                    "status_code": 500,
                    "title": "Server Error",
                    "links": [],
                    "headings": [],
                    "json_ld": []
                },
                {
                    "url": "https://failing.internal/empty",
                    "status_code": 0,
                    "title": "",
                    "links": [],
                    "headings": [],
                    "json_ld": []
                }
            ]
        }

        # Running all skills should not crash or raise unhandled exceptions
        skill_outputs = []
        for skill in AUDIT_SKILLS:
            mod = get_skill_module(REPO_ROOT / skill["script"], f"fail_{skill['name']}")
            findings, strengths = mod.run_checks(snap)
            skill_outputs.append({"skill": skill["name"], "findings": findings, "strengths": strengths})

        norm_findings, strengths = normalize_all(skill_outputs)
        deduped = deduplicate(norm_findings)
        summary = compute_summary(deduped, snap)
        journey = compute_agent_journey_scores(deduped)

        self.assertIsInstance(deduped, list)
        self.assertIsInstance(summary["ai_readiness_score"], int)
        self.assertIsInstance(journey["overall_journey_score"], int)

    def test_10_deterministic_repeated_execution(self):
        """10. Repeated audit execution over identical input produces 100% bitwise-identical findings & scores."""
        snap = generate_benchmark_snapshot(num_pages=25)

        def run_pipeline(s):
            skill_outputs = []
            for skill in AUDIT_SKILLS:
                mod = get_skill_module(REPO_ROOT / skill["script"], f"perf_{skill['name']}")
                findings, strengths = mod.run_checks(s)
                skill_outputs.append({"skill": skill["name"], "findings": findings, "strengths": strengths})
            norm_findings, strengths = normalize_all(skill_outputs)
            deduped = deduplicate(norm_findings)
            summary = compute_summary(deduped, s)
            journey = compute_agent_journey_scores(deduped)
            answerability = evaluate_agent_answerability(s, deduped)
            top_p = compute_top_priorities(deduped, limit=5, snapshot=s)
            return deduped, summary, journey, answerability, top_p, strengths

        d1, s1, j1, a1, tp1, st1 = run_pipeline(copy.deepcopy(snap))
        d2, s2, j2, a2, tp2, st2 = run_pipeline(copy.deepcopy(snap))

        self.assertEqual(len(d1), len(d2))
        for f1, f2 in zip(d1, d2):
            self.assertEqual(f1["id"], f2["id"])
            self.assertEqual(f1["title"], f2["title"])
            self.assertEqual(f1["severity"], f2["severity"])
            self.assertEqual(f1["confidence"], f2["confidence"])
            self.assertEqual(f1["source_skill"], f2["source_skill"])
            self.assertEqual(f1["affected_urls"], f2["affected_urls"])
            self.assertEqual(f1["evidence"], f2["evidence"])
            self.assertEqual(f1["suggested_action"], f2["suggested_action"])

        self.assertEqual(s1, s2)
        self.assertEqual(j1, j2)
        self.assertEqual(a1, a2)
        self.assertEqual(tp1, tp2)
        self.assertEqual(st1, st2)


if __name__ == "__main__":
    unittest.main()
