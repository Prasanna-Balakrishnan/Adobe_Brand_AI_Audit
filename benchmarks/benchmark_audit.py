#!/usr/bin/env python3
"""
benchmarks/benchmark_audit.py — Master Benchmark Suite for Brand AI-Readiness Audit

Executes the COMPLETE audit pipeline over realistic workloads (50, 100, 250 pages),
profiling per-phase execution times, memory, findings, and throughput.

Execution Limit:
    <= 5 minutes (300 seconds) for complete audit workload.

Usage:
    python benchmarks/benchmark_audit.py
    python benchmarks/benchmark_audit.py --pages 50
    python benchmarks/benchmark_audit.py --all
"""

import argparse
import copy
import json
import os
from pathlib import Path
import sys
import time
import tracemalloc

# Setup paths
REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "skills" / "audit-orchestrator" / "scripts"))

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
    generate_markdown_report,
    METHODOLOGY_AND_LIMITATIONS,
    MARKETPLACE_VERSION,
)


def generate_benchmark_snapshot(num_pages: int = 50, domain: str = "benchmark-acme.internal") -> dict:
    """
    Generate a realistic synthetic website snapshot with rich metadata,
    diverse page types, JSON-LD, navigation graphs, and entity information.
    """
    base_url = f"https://{domain}"
    pages = []
    
    # 1. Homepage
    pages.append({
        "url": f"{base_url}/",
        "status_code": 200,
        "final_url": f"{base_url}/",
        "redirect_chain": [],
        "redirect_loop": False,
        "canonical": f"{base_url}/",
        "canonical_conflict": False,
        "meta_robots": "index, follow",
        "x_robots_tag": "",
        "page_type": "Homepage",
        "classification_confidence": "high",
        "title": "Acme Global — Enterprise AI Cloud Platform",
        "meta_description": "Acme Global provides autonomous AI agent orchestration and enterprise intelligence infrastructure.",
        "h1": ["Next-Generation Autonomous AI Cloud Platform"],
        "headings": [
            {"level": 1, "text": "Next-Generation Autonomous AI Cloud Platform"},
            {"level": 2, "text": "Platform Capabilities"},
            {"level": 2, "text": "Trusted by 5,000+ Enterprises"},
            {"level": 3, "text": "Request a Demo"}
        ],
        "json_ld": [
            {
                "@context": "https://schema.org",
                "@type": "Organization",
                "name": "Acme Global Inc.",
                "url": f"{base_url}/",
                "logo": f"{base_url}/assets/logo.png",
                "description": "Acme Global provides enterprise AI intelligence infrastructure.",
                "sameAs": ["https://twitter.com/acmeglobal", "https://linkedin.com/company/acmeglobal"]
            },
            {
                "@context": "https://schema.org",
                "@type": "WebSite",
                "name": "Acme Global",
                "url": f"{base_url}/"
            }
        ],
        "open_graph": {
            "og:title": "Acme Global — Enterprise AI Cloud Platform",
            "og:description": "Acme Global enterprise AI platform.",
            "og:image": f"{base_url}/assets/og-home.png"
        },
        "twitter_card": {"twitter:card": "summary_large_image"},
        "links": [
            {"href": f"{base_url}/about", "text": "About Us", "is_internal": True},
            {"href": f"{base_url}/pricing", "text": "Pricing & Plans", "is_internal": True},
            {"href": f"{base_url}/docs", "text": "Documentation", "is_internal": True},
            {"href": f"{base_url}/contact", "text": "Contact Sales", "is_internal": True},
            {"href": f"{base_url}/blog", "text": "Insights Blog", "is_internal": True},
            {"href": f"{base_url}/careers", "text": "Careers", "is_internal": True},
        ],
        "nav_link_texts": ["About Us", "Pricing & Plans", "Documentation", "Contact Sales", "Insights Blog", "Careers"],
        "images": [{"src": f"{base_url}/assets/logo.png", "alt": "Acme Global Logo", "width": 200, "height": 60}],
        "visible_text_length": 2800,
        "visible_text_sample": "Acme Global enterprise AI cloud platform empowers organizations to deploy autonomous agents...",
        "last_modified": "2026-03-01T10:00:00Z",
        "crawled_with_js": False,
        "js_render_available": True,
        "raw_html_length": 14500,
        "raw_text_length": 2800,
        "rendered_text_length": 2800,
        "js_dependent_content": False,
        "content_disparity": 0
    })

    # Standard pages: About, Contact, Pricing, Docs, FAQ, Careers
    standard_defs = [
        ("about", "About", "About Acme Global — Our Leadership & Vision", [
            {"@context": "https://schema.org", "@type": "AboutPage", "name": "About Acme Global"}
        ]),
        ("contact", "Contact", "Contact Acme Global — Support & Sales", [
            {"@context": "https://schema.org", "@type": "ContactPage", "name": "Contact Acme Global"}
        ]),
        ("pricing", "Pricing", "Transparent Enterprise Pricing & Subscription Plans", [
            {"@context": "https://schema.org", "@type": "Product", "name": "Acme Cloud Enterprise",
             "offers": {"@type": "AggregateOffer", "lowPrice": "49", "highPrice": "499", "priceCurrency": "USD"}}
        ]),
        ("docs", "Documentation", "Developer API Reference & Integration Guides", [
            {"@context": "https://schema.org", "@type": "TechArticle", "headline": "Developer API Reference"}
        ]),
        ("faq", "FAQ", "Frequently Asked Questions — Knowledge Base", [
            {"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [
                {"@type": "Question", "name": "What is Acme Global?", "acceptedAnswer": {"@type": "Answer", "text": "Acme Global is an AI cloud."}}
            ]}
        ]),
        ("careers", "Careers", "Careers at Acme Global — Join Our Team", [
            {"@context": "https://schema.org", "@type": "JobPosting", "title": "Staff AI Engineer"}
        ]),
    ]

    for slug, ptype, title, jsonld in standard_defs:
        if len(pages) >= num_pages:
            break
        pages.append({
            "url": f"{base_url}/{slug}",
            "status_code": 200,
            "final_url": f"{base_url}/{slug}",
            "redirect_chain": [],
            "redirect_loop": False,
            "canonical": f"{base_url}/{slug}",
            "canonical_conflict": False,
            "meta_robots": "index, follow",
            "x_robots_tag": "",
            "page_type": ptype,
            "classification_confidence": "high",
            "title": f"{title} | Acme Global",
            "meta_description": f"Learn more about {title} at Acme Global.",
            "h1": [title],
            "headings": [{"level": 1, "text": title}, {"level": 2, "text": "Details"}, {"level": 3, "text": "More info"}],
            "json_ld": jsonld,
            "open_graph": {"og:title": title, "og:description": title, "og:image": f"{base_url}/assets/{slug}.png"},
            "twitter_card": {"twitter:card": "summary"},
            "links": [
                {"href": f"{base_url}/", "text": "Home", "is_internal": True},
                {"href": f"{base_url}/pricing", "text": "Pricing", "is_internal": True},
                {"href": f"{base_url}/docs", "text": "Docs", "is_internal": True},
            ],
            "nav_link_texts": ["Home", "About Us", "Pricing & Plans", "Documentation"],
            "images": [{"src": f"{base_url}/assets/{slug}.png", "alt": title}],
            "visible_text_length": 1800,
            "visible_text_sample": f"{title} content overview and information for enterprise customers.",
            "last_modified": "2026-02-15T12:00:00Z",
            "crawled_with_js": False,
            "js_render_available": True,
            "raw_html_length": 9200,
            "raw_text_length": 1800,
            "rendered_text_length": 1800,
            "js_dependent_content": False,
            "content_disparity": 0
        })

    # Fill remaining pages with Products, Blog Posts, Solutions, and Case Studies
    idx = 1
    while len(pages) < num_pages:
        category = "product" if idx % 3 == 0 else ("blog" if idx % 3 == 1 else "solution")
        if category == "product":
            p_type = "Product"
            slug = f"products/product-suite-{idx}"
            title = f"Acme Product Suite {idx}"
            jld = [
                {
                    "@context": "https://schema.org",
                    "@type": "Product",
                    "name": title,
                    "description": f"High performance AI capability module {idx}.",
                    "offers": {"@type": "Offer", "price": str(99 + idx * 10), "priceCurrency": "USD", "availability": "https://schema.org/InStock"}
                }
            ] if idx % 4 != 0 else []  # 25% missing schema to generate realistic audit findings
        elif category == "blog":
            p_type = "Blog/article"
            slug = f"blog/ai-trends-article-{idx}"
            title = f"AI Trends and Best Practices Part {idx}"
            jld = [
                {
                    "@context": "https://schema.org",
                    "@type": "BlogPosting",
                    "headline": title,
                    "datePublished": "2025-11-20T08:00:00Z",
                    "dateModified": "2026-01-10T11:00:00Z",
                    "author": {"@type": "Person", "name": "Jane Doe"}
                }
            ]
        else:
            p_type = "Service"
            slug = f"solutions/enterprise-solution-{idx}"
            title = f"Enterprise Solution {idx}"
            jld = [
                {
                    "@context": "https://schema.org",
                    "@type": "Service",
                    "name": title,
                    "serviceType": "Cloud AI Solution"
                }
            ]

        pages.append({
            "url": f"{base_url}/{slug}",
            "status_code": 200,
            "final_url": f"{base_url}/{slug}",
            "redirect_chain": [],
            "redirect_loop": False,
            "canonical": f"{base_url}/{slug}",
            "canonical_conflict": False,
            "meta_robots": "index, follow",
            "x_robots_tag": "",
            "page_type": p_type,
            "classification_confidence": "high",
            "title": f"{title} | Acme Global",
            "meta_description": f"Explore {title} designed for modern autonomous enterprise workflows.",
            "h1": [title],
            "headings": [{"level": 1, "text": title}, {"level": 2, "text": "Feature Overview"}, {"level": 3, "text": "Specifications"}],
            "json_ld": jld,
            "open_graph": {"og:title": title, "og:description": title, "og:image": f"{base_url}/assets/prod-{idx}.png"},
            "twitter_card": {"twitter:card": "summary_large_image"},
            "links": [
                {"href": f"{base_url}/", "text": "Home", "is_internal": True},
                {"href": f"{base_url}/pricing", "text": "Pricing", "is_internal": True},
                {"href": f"{base_url}/contact", "text": "Get Started", "is_internal": True},
                {"href": f"{base_url}/docs", "text": "Documentation", "is_internal": True}
            ],
            "nav_link_texts": ["Home", "Pricing & Plans", "Documentation", "Contact Sales"],
            "images": [{"src": f"{base_url}/assets/prod-{idx}.png", "alt": title}],
            "visible_text_length": 1400 + (idx * 17) % 800,
            "visible_text_sample": f"{title} provides end-to-end automation with guaranteed uptime and compliance.",
            "last_modified": "2026-01-15T09:00:00Z",
            "crawled_with_js": False,
            "js_render_available": True,
            "raw_html_length": 8500 + (idx * 31) % 1500,
            "raw_text_length": 1400 + (idx * 17) % 800,
            "rendered_text_length": 1400 + (idx * 17) % 800,
            "js_dependent_content": False,
            "content_disparity": 0
        })
        idx += 1

    snapshot = {
        "crawl_meta": {
            "start_url": f"{base_url}/",
            "crawl_started_at": "2026-09-08T12:00:00Z",
            "crawl_ended_at": "2026-09-08T12:00:05Z",
            "crawl_duration_seconds": 5.0,
            "pages_discovered": len(pages),
            "pages_crawled": len(pages),
            "pages_skipped": 0,
            "robots_txt_status": 200,
            "robots_txt_respected": True,
            "js_rendering_status": "disabled",
            "failed_pages": []
        },
        "pages": pages
    }
    return snapshot


def run_benchmark(num_pages: int = 50, output_dir: Path = None) -> dict:
    """
    Execute the complete audit pipeline against a synthetic benchmark workload.
    Measures per-phase timings, throughput, memory, and checks against 5-minute requirement.
    """
    if output_dir is None:
        output_dir = REPO_ROOT / "benchmark_work"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    tracemalloc.start()
    total_start = time.perf_counter()

    # 1. Snapshot / Crawl phase
    crawl_start = time.perf_counter()
    snapshot = generate_benchmark_snapshot(num_pages=num_pages)
    snapshot_path = output_dir / f"snapshot_{num_pages}.json"
    with open(snapshot_path, "w", encoding="utf-8") as f:
        json.dump(snapshot, f, indent=2)
    crawl_time = time.perf_counter() - crawl_start

    # 2. Audit Skills Fan-Out
    audit_start = time.perf_counter()
    skill_outputs = []
    skills_invoked = []
    failed_skills = []

    for skill in AUDIT_SKILLS:
        s_name = skill["name"]
        script_path = REPO_ROOT / skill["script"]
        out_path = output_dir / f"{s_name}_{num_pages}.json"
        
        mod_name = f"skill_{s_name.replace('-', '_')}"
        mod = get_skill_module(script_path, mod_name)
        if mod and hasattr(mod, "run_checks"):
            findings, strengths = mod.run_checks(snapshot)
            output = {"skill": s_name, "findings": findings, "strengths": strengths}
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(output, f, indent=2, ensure_ascii=False)
            skill_outputs.append(output)
            skills_invoked.append(s_name)
        else:
            failed_skills.append({"skill": s_name, "error": "Module failed to load in-process"})

    # 3. Normalization & Deduplication
    norm_start = time.perf_counter()
    normalized_findings, all_strengths = normalize_all(skill_outputs)
    deduped_findings = deduplicate(normalized_findings)
    norm_dedup_time = time.perf_counter() - norm_start

    # 4. Scoring, Agent Journey, Answerability
    score_start = time.perf_counter()
    summary = compute_summary(deduped_findings, snapshot)
    journey_scores = compute_agent_journey_scores(deduped_findings)
    answerability = evaluate_agent_answerability(snapshot, deduped_findings)
    top_priorities = compute_top_priorities(deduped_findings, limit=5, snapshot=snapshot)
    scoring_time = time.perf_counter() - score_start

    # 5. Proactive Opportunities
    proactive_start = time.perf_counter()
    pro_mod = get_skill_module(REPO_ROOT / PROACTIVE_SKILL["script"], "skill_proactive_opportunities_audit")
    proactive_recs = []
    if pro_mod and hasattr(pro_mod, "run_opportunities"):
        proactive_recs = pro_mod.run_opportunities(snapshot, deduped_findings)
        pro_out_path = output_dir / f"proactive_{num_pages}.json"
        with open(pro_out_path, "w", encoding="utf-8") as f:
            json.dump({"skill": PROACTIVE_SKILL["name"], "recommendations": proactive_recs}, f, indent=2, ensure_ascii=False)
        skills_invoked.append(PROACTIVE_SKILL["name"])
    proactive_time = time.perf_counter() - proactive_start

    audit_time = (time.perf_counter() - audit_start) - scoring_time

    # 6. Report Generation
    report_start = time.perf_counter()
    clean_findings = []
    for f in deduped_findings:
        cf = {
            "id": f["id"],
            "title": f["title"],
            "category": f["category"],
            "severity": f["severity"],
            "confidence": f["confidence"],
            "source_skill": f["source_skill"],
            "tags": f.get("tags", []),
            "affected_urls": f["affected_urls"],
            "evidence": f["evidence"],
            "root_cause_group": f.get("root_cause_group"),
            "suggested_action": f["suggested_action"]
        }
        if "merged_from_skills" in f:
            cf["merged_from_skills"] = f["merged_from_skills"]
        clean_findings.append(cf)

    report = {
        "site": "benchmark-acme.internal",
        "audited_at": "2026-09-08T12:00:00Z",
        "run_info": {
            "marketplace_version": MARKETPLACE_VERSION,
            "target_url": f"https://benchmark-acme.internal/",
            "skills_invoked": skills_invoked,
            "failed_skills": failed_skills,
            "pages_crawled": num_pages,
            "crawl_duration_seconds": round(crawl_time, 2)
        },
        "summary": summary,
        "agent_journey_scores": journey_scores,
        "agent_answerability": answerability,
        "top_priorities": top_priorities,
        "findings": clean_findings,
        "proactive_recommendations": proactive_recs,
        "strengths": all_strengths,
        "methodology_and_limitations": METHODOLOGY_AND_LIMITATIONS
    }

    report_json_path = output_dir / f"benchmark_report_{num_pages}.json"
    with open(report_json_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    md_content = generate_markdown_report(report)
    report_md_path = output_dir / f"benchmark_report_{num_pages}.md"
    with open(report_md_path, "w", encoding="utf-8") as f:
        f.write(md_content)

    report_time = time.perf_counter() - report_start
    total_time = time.perf_counter() - total_start
    
    current_mem, peak_mem = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    throughput = round(num_pages / total_time, 1) if total_time > 0 else 0.0
    passed_5min = total_time <= 300.0

    return {
        "pages": num_pages,
        "total_time_seconds": round(total_time, 3),
        "crawl_time_seconds": round(crawl_time, 3),
        "audit_time_seconds": round(audit_time, 3),
        "norm_dedup_time_seconds": round(norm_dedup_time, 3),
        "scoring_time_seconds": round(scoring_time, 3),
        "proactive_time_seconds": round(proactive_time, 3),
        "report_time_seconds": round(report_time, 3),
        "findings_count": len(clean_findings),
        "recommendations_count": len(proactive_recs),
        "strengths_count": len(all_strengths),
        "ai_readiness_score": summary.get("ai_readiness_score", 0),
        "journey_score": journey_scores.get("overall_journey_score", 0),
        "throughput_pages_per_sec": throughput,
        "peak_memory_mb": round(peak_mem / (1024 * 1024), 2),
        "pass_5min": passed_5min,
        "status": "PASS" if passed_5min else "FAIL"
    }


def print_benchmark_results(res: dict):
    print("=" * 68)
    print(f"        BRAND AI-READINESS AUDIT -- BENCHMARK RESULTS ({res['pages']} PAGES)")
    print("=" * 68)
    print(f" Workload Size:          {res['pages']} pages")
    print(f" Total Wall-Clock Time:  {res['total_time_seconds']}s")
    print(f"   |-- Crawl/Snapshot:    {res['crawl_time_seconds']}s")
    print(f"   |-- Audit Skills:      {res['audit_time_seconds']}s")
    print(f"   |-- Norm & Dedup:      {res['norm_dedup_time_seconds']}s")
    print(f"   |-- Scoring & Journey: {res['scoring_time_seconds']}s")
    print(f"   |-- Proactive Audit:   {res['proactive_time_seconds']}s")
    print(f"   +-- Report Generation: {res['report_time_seconds']}s")
    print("-" * 68)
    print(f" Findings Generated:     {res['findings_count']}")
    print(f" Proactive Recs:         {res['recommendations_count']}")
    print(f" Strengths Identified:   {res['strengths_count']}")
    print(f" AI Readiness Score:     {res['ai_readiness_score']}/100")
    print(f" Overall Journey Score:  {res['journey_score']}/100")
    print(f" Peak Memory Usage:      {res['peak_memory_mb']} MB")
    print(f" Throughput:             {res['throughput_pages_per_sec']} pages/sec")
    print("-" * 68)
    status_label = "PASS (<= 5 minutes)" if res['pass_5min'] else "FAIL (> 5 minutes)"
    print(f" 5-MINUTE TARGET STATUS: {status_label}")
    print("=" * 68)
    print()


def main():
    p = argparse.ArgumentParser(description="Brand AI-Readiness Audit Performance Benchmark")
    p.add_argument("--pages", type=int, default=50, help="Number of pages in synthetic workload (default: 50)")
    p.add_argument("--all", action="store_true", help="Run scalability suite across 50, 100, and 250 pages")
    p.add_argument("--output", default=None, help="Optional output JSON path for benchmark metrics")
    args = p.parse_args()

    page_counts = [50, 100, 250] if args.all else [args.pages]
    all_results = []
    overall_pass = True

    for count in page_counts:
        print(f"[BENCHMARK] Executing {count}-page audit workload...", file=sys.stderr)
        res = run_benchmark(num_pages=count)
        all_results.append(res)
        print_benchmark_results(res)
        if not res["pass_5min"]:
            overall_pass = False

    if args.output:
        out_data = all_results[0] if len(all_results) == 1 else {"benchmarks": all_results}
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(out_data, f, indent=2)
        print(f"[BENCHMARK] Saved metrics to {args.output}", file=sys.stderr)

    sys.exit(0 if overall_pass else 1)


if __name__ == "__main__":
    main()
