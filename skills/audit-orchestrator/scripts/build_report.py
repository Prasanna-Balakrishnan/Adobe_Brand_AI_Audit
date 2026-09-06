#!/usr/bin/env python3
"""
build_report.py — Master orchestrator script.

Invokes site-crawler, fans out to all audit skills, normalizes, deduplicates,
scores, runs proactive audit, and assembles the final JSON report.

Usage:
    python skills/audit-orchestrator/scripts/build_report.py \
        --url https://example.com \
        --max-pages 20 \
        --output report.json \
        [--work-dir ./audit_work] \
        [--use-js-render]
"""

import argparse
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

# Allow importing sibling orchestrator scripts
THIS_DIR = Path(__file__).parent
sys.path.insert(0, str(THIS_DIR))
from normalize_findings import normalize_all
from deduplicate_findings import deduplicate
from score import (
    compute_summary,
    compute_agent_journey_scores,
    evaluate_agent_answerability,
    compute_top_priorities,
    get_journey_pillar_explanations
)

MARKETPLACE_VERSION = "1.0.0"

METHODOLOGY_AND_LIMITATIONS = {
    "audit_scope": "Evaluates technical AI discoverability, content extractability, structured data completeness, and citation readiness based on an observable crawl snapshot.",
    "deterministic_scoring": "All scoring formulas and journey deductions are 100% deterministic and rule-grounded, measuring concrete technical readiness rather than subjective or volatile LLM search rankings.",
    "read_only_guarantee": "This audit operates purely in read-only analysis mode without modifying site infrastructure, publishing changes, or executing non-idempotent operations.",
    "limitations": [
        "Crawl depth is capped at 20 pages per run under standard execution parameters.",
        "Dynamic Single-Page Application (SPA) content requires headless rendering with Playwright fallback when JavaScript rendering is enabled.",
        "Content behind authentication, paywalls, or strict CAPTCHA barriers is outside audit scope."
    ]
}


def extract_target_url(query: str) -> str:
    """
    Accept direct URLs or natural-language audit requests (Req 1).
    Examples:
      - 'https://example.com' -> 'https://example.com'
      - 'example.com' -> 'https://example.com'
      - 'Check the Microsoft website and generate a report' -> 'https://www.microsoft.com'
      - 'Audit https://store.nike.com/us' -> 'https://store.nike.com/us'
    """
    q = query.strip()
    # 1. Check for explicit http(s) URL in string
    url_match = re.search(r'https?://[^\s\'"<>]+', q)
    if url_match:
        return url_match.group(0).rstrip(".,;")

    # 2. Check for domain pattern like example.com or sub.example.co.uk
    domain_match = re.search(r'\b([a-zA-Z0-9][-a-zA-Z0-9]*\.)+[a-zA-Z]{2,}\b', q)
    if domain_match:
        domain = domain_match.group(0).rstrip(".,;")
        return f"https://{domain}"

    # 3. Check for 'the <Brand> website' or 'check <Brand>'
    brand_match = re.search(r'(?:check|audit|analyze|inspect|test|report on)?\s*(?:the\s+)?([a-zA-Z0-9-]+)\s+(?:website|site|portal|web page)', q, re.IGNORECASE)
    if brand_match:
        brand = brand_match.group(1).lower().strip()
        if brand and brand not in ("a", "the", "this", "our"):
            return f"https://www.{brand}.com"

    # Fallback
    if not q.startswith("http://") and not q.startswith("https://"):
        return f"https://{q}"
    return q


AUDIT_SKILLS = [
    {
        "name": "crawlability-render-audit",
        "script": "skills/crawlability-render-audit/scripts/audit.py",
        "output_name": "crawlability_findings.json",
    },
    {
        "name": "structured-data-content-audit",
        "script": "skills/structured-data-content-audit/scripts/audit.py",
        "output_name": "structured_data_findings.json",
    },
    {
        "name": "entity-identity-audit",
        "script": "skills/entity-identity-audit/scripts/audit.py",
        "output_name": "entity_findings.json",
    },
    {
        "name": "freshness-corroboration-audit",
        "script": "skills/freshness-corroboration-audit/scripts/audit.py",
        "output_name": "freshness_findings.json",
    },
    {
        "name": "engagement-audit",
        "script": "skills/engagement-audit/scripts/audit.py",
        "output_name": "engagement_findings.json",
    },
]

PROACTIVE_SKILL = {
    "name": "proactive-opportunities-audit",
    "script": "skills/proactive-opportunities-audit/scripts/audit.py",
    "output_name": "proactive_findings.json",
}


def parse_args():
    p = argparse.ArgumentParser(
        description="Brand AI-Readiness Audit — Master Orchestrator"
    )
    p.add_argument("--url", default=None, help="Site URL to audit")
    p.add_argument("--snapshot", default=None, help="Path to pre-existing snapshot.json (replaces crawler/network step for offline execution)")
    p.add_argument("--max-pages", type=int, default=20)
    p.add_argument("--output", default="report.json")
    p.add_argument("--work-dir", default="./audit_work")
    p.add_argument("--use-js-render", action="store_true")
    p.add_argument("--stale-threshold-days", type=int, default=365)
    args = p.parse_args()
    if not args.url and not args.snapshot:
        p.error("Either --url or --snapshot must be provided.")
    return args


def find_marketplace_root() -> Path:
    """Walk up from this script's location to find marketplace.json."""
    here = THIS_DIR
    for _ in range(5):
        if (here / "marketplace.json").exists():
            return here
        here = here.parent
    # Fallback: current working directory
    return Path.cwd()


def run_subprocess(cmd: list, label: str) -> tuple[bool, str]:
    """Run a subprocess command; return (success, stderr_output)."""
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300  # 5-minute safety timeout per skill
        )
        if result.stderr:
            for line in result.stderr.strip().splitlines():
                print(f"  [{label}] {line}", file=sys.stderr)
        if result.returncode != 0:
            print(f"[WARN] {label} exited with code {result.returncode}", file=sys.stderr)
            return False, result.stderr
        return True, result.stderr
    except subprocess.TimeoutExpired:
        print(f"[WARN] {label} timed out after 300s", file=sys.stderr)
        return False, "timeout"
    except Exception as e:
        print(f"[WARN] {label} failed: {e}", file=sys.stderr)
        return False, str(e)


def load_json_safe(path: str, label: str) -> dict | None:
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"[WARN] Output file not found for {label}: {path}", file=sys.stderr)
        return None
    except json.JSONDecodeError as e:
        print(f"[WARN] Invalid JSON from {label}: {e}", file=sys.stderr)
        return None


def main():
    args = parse_args()

    # Setup
    work_dir = Path(args.work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)

    marketplace_root = find_marketplace_root()
    snapshot_path = str(work_dir / "snapshot.json")

    start_time = time.time()
    audited_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    if args.snapshot:
        # ── Snapshot Mode: replace ONLY the crawler/network step ───────────────
        snap_in = Path(args.snapshot)
        if not snap_in.exists():
            print(f"[ERROR] Specified snapshot not found: {snap_in}", file=sys.stderr)
            sys.exit(1)
        snapshot = load_json_safe(str(snap_in), "snapshot-input")
        if not snapshot:
            print(f"[ERROR] Cannot read snapshot from: {snap_in}", file=sys.stderr)
            sys.exit(1)
        with open(snapshot_path, "w", encoding="utf-8") as f:
            json.dump(snapshot, f, indent=2)
        crawl_meta = snapshot.get("crawl_meta", {})
        target_url = crawl_meta.get("start_url") or "https://example.com"
        query_input = args.url or target_url
        crawl_duration = 0.0
        pages_crawled = crawl_meta.get("pages_crawled", len(snapshot.get("pages", [])))
        print(f"[INFO] Marketplace root: {marketplace_root}", file=sys.stderr)
        print(f"[INFO] Auditing via snapshot: {snap_in} for {target_url}", file=sys.stderr)
        print(f"[INFO] Work dir: {work_dir.resolve()}", file=sys.stderr)
        print(f"\n[STEP 1] Reusing provided snapshot ({pages_crawled} pages) — skipping live crawl.", file=sys.stderr)
    else:
        # ── Standard Mode: invoke site-crawler ─────────────────────────────────
        target_url = extract_target_url(args.url)
        query_input = args.url
        print(f"[INFO] Marketplace root: {marketplace_root}", file=sys.stderr)
        print(f"[INFO] Auditing: {target_url} (input query: '{args.url}')", file=sys.stderr)
        print(f"[INFO] Work dir: {work_dir.resolve()}", file=sys.stderr)

        crawler_script = str(marketplace_root / "skills" / "site-crawler" / "scripts" / "crawl.py")
        print(f"\n[STEP 1] Running site-crawler...", file=sys.stderr)
        crawl_start = time.time()

        crawler_cmd = [
            sys.executable, crawler_script,
            "--url", target_url,
            "--max-pages", str(args.max_pages),
            "--output", snapshot_path,
        ]
        if args.use_js_render:
            crawler_cmd.append("--use-js-render")

        crawl_ok, _ = run_subprocess(crawler_cmd, "site-crawler")
        crawl_duration = time.time() - crawl_start

        if not crawl_ok or not Path(snapshot_path).exists():
            print("[ERROR] Crawl failed — aborting audit.", file=sys.stderr)
            error_report = {
                "error": "crawl_failed",
                "reason": "site-crawler did not produce a snapshot.json",
                "url": target_url,
                "query_input": args.url,
                "audited_at": audited_at
            }
            with open(args.output, "w", encoding="utf-8") as f:
                json.dump(error_report, f, indent=2)
            sys.exit(1)

        snapshot = load_json_safe(snapshot_path, "site-crawler")
        if not snapshot:
            print("[ERROR] Cannot read snapshot.json — aborting.", file=sys.stderr)
            sys.exit(1)

        crawl_meta = snapshot.get("crawl_meta", {})
        pages_crawled = crawl_meta.get("pages_crawled", 0)
        print(f"[INFO] Crawled {pages_crawled} pages in {crawl_duration:.1f}s", file=sys.stderr)

    # ── Step 2: Fan-out to audit skills ────────────────────────────────────
    print(f"\n[STEP 2] Running {len(AUDIT_SKILLS)} audit skills...", file=sys.stderr)

    skill_outputs = []
    skills_invoked = []
    failed_skills = []

    for skill in AUDIT_SKILLS:
        skill_name = skill["name"]
        skill_output_path = str(work_dir / skill["output_name"])
        skill_script = str(marketplace_root / skill["script"])

        print(f"  → {skill_name}", file=sys.stderr)

        # Build command
        cmd = [
            sys.executable, skill_script,
            "--snapshot", snapshot_path,
            "--output", skill_output_path,
        ]
        if skill_name == "freshness-corroboration-audit":
            cmd += ["--stale-threshold-days", str(args.stale_threshold_days)]

        # Fault-tolerant execution (Req 25)
        try:
            ok, stderr_output = run_subprocess(cmd, skill_name)
            if ok:
                output = load_json_safe(skill_output_path, skill_name)
                if output:
                    skill_outputs.append(output)
                    skills_invoked.append(skill_name)
                else:
                    skills_invoked.append(f"{skill_name}_SKIPPED")
                    failed_skills.append({"skill": skill_name, "error": "Output file missing or invalid"})
            else:
                skills_invoked.append(f"{skill_name}_FAILED")
                failed_skills.append({"skill": skill_name, "error": stderr_output or "Non-zero exit code"})
        except Exception as exc:
            skills_invoked.append(f"{skill_name}_ERROR")
            failed_skills.append({"skill": skill_name, "error": str(exc)})

    # ── Step 3: Normalize ──────────────────────────────────────────────────
    print(f"\n[STEP 3] Normalizing findings...", file=sys.stderr)
    normalized_findings, all_strengths = normalize_all(skill_outputs)
    print(f"  {len(normalized_findings)} findings after normalization", file=sys.stderr)

    # ── Step 4: Deduplicate ────────────────────────────────────────────────
    print(f"\n[STEP 4] Deduplicating findings...", file=sys.stderr)
    deduped_findings = deduplicate(normalized_findings)
    print(f"  {len(deduped_findings)} findings after deduplication", file=sys.stderr)

    # Save deduplicated findings for proactive skill
    dedup_path = str(work_dir / "deduplicated_findings.json")
    with open(dedup_path, "w", encoding="utf-8") as f:
        json.dump({"findings": deduped_findings}, f, indent=2, ensure_ascii=False)

    # ── Step 5: Score, Journey & Answerability ─────────────────────────────
    print(f"\n[STEP 5] Computing score, AI Agent Journey & Answerability...", file=sys.stderr)
    summary = compute_summary(deduped_findings, snapshot)
    journey_scores = compute_agent_journey_scores(deduped_findings)
    answerability = evaluate_agent_answerability(snapshot, deduped_findings)
    top_priorities = compute_top_priorities(deduped_findings, limit=5)
    print(f"  AI Readiness Score: {summary['ai_readiness_score']}/100", file=sys.stderr)
    print(f"  Agent Journey Overall: {journey_scores['overall_journey_score']}/100", file=sys.stderr)

    # ── Step 6: Proactive opportunities ───────────────────────────────────
    print(f"\n[STEP 6] Running proactive-opportunities-audit...", file=sys.stderr)
    proactive_output_path = str(work_dir / PROACTIVE_SKILL["output_name"])
    proactive_script = str(marketplace_root / PROACTIVE_SKILL["script"])

    proactive_cmd = [
        sys.executable, proactive_script,
        "--snapshot", snapshot_path,
        "--findings", dedup_path,
        "--output", proactive_output_path,
    ]
    pro_ok, _ = run_subprocess(proactive_cmd, PROACTIVE_SKILL["name"])

    proactive_recommendations = []
    if pro_ok:
        pro_data = load_json_safe(proactive_output_path, PROACTIVE_SKILL["name"])
        if pro_data:
            proactive_recommendations = pro_data.get("recommendations", [])
            skills_invoked.append(PROACTIVE_SKILL["name"])
        else:
            skills_invoked.append(f"{PROACTIVE_SKILL['name']}_SKIPPED")
    else:
        skills_invoked.append(f"{PROACTIVE_SKILL['name']}_SKIPPED")

    print(f"  {len(proactive_recommendations)} proactive recommendation(s)", file=sys.stderr)

    # ── Step 7: Build final report ─────────────────────────────────────────
    print(f"\n[STEP 7] Building final report...", file=sys.stderr)

    site = urlparse(target_url).netloc or target_url

    # Build clean findings (remove internal fields)
    clean_findings = []
    for f in deduped_findings:
        clean_f = {
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
        # Include merged_from_skills if present
        if "merged_from_skills" in f:
            clean_f["merged_from_skills"] = f["merged_from_skills"]
        clean_findings.append(clean_f)

    # Crawl coverage info (Req 20)
    crawl_coverage = {
        "pages_discovered": crawl_meta.get("pages_discovered", pages_crawled),
        "pages_crawled": pages_crawled,
        "pages_skipped": crawl_meta.get("pages_skipped", 0),
        "failed_pages": crawl_meta.get("failed_pages", []),
        "crawl_duration_seconds": round(crawl_duration, 1),
        "robots_status": crawl_meta.get("robots_txt_status", "allowed"),
        "js_rendering_status": crawl_meta.get("js_rendering_status", "disabled")
    }

    report = {
        "site": site,
        "audited_at": audited_at,
        "run_info": {
            "marketplace_version": MARKETPLACE_VERSION,
            "query_input": args.url or target_url,
            "target_url": target_url,
            "skills_invoked": skills_invoked,
            "failed_skills": failed_skills,
            "pages_crawled": pages_crawled,
            "max_pages": args.max_pages,
            "crawl_duration_seconds": round(crawl_duration, 1),
            "robots_txt_respected": crawl_meta.get("robots_txt_respected", True),
            "crawl_coverage": crawl_coverage
        },
        "summary": summary,
        "agent_journey_scores": journey_scores,
        "agent_answerability": answerability,
        "top_priorities": top_priorities,
        "findings": clean_findings,
        "proactive_recommendations": proactive_recommendations,
        "strengths": all_strengths,
        "methodology_and_limitations": METHODOLOGY_AND_LIMITATIONS
    }

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    out_p = Path(args.output)
    md_output_path = out_p.with_suffix(".md") if out_p.suffix == ".json" else out_p.parent / f"{out_p.name}.md"
    md_content = generate_markdown_report(report)
    with open(md_output_path, "w", encoding="utf-8") as f:
        f.write(md_content)

    print_terminal_summary(report)

    total_time = time.time() - start_time
    print(f"[DONE] Audit completed in {total_time:.1f}s", file=sys.stderr)
    print(f"[DONE] Report written to: {args.output}", file=sys.stderr)
    print(f"[DONE] Companion Markdown written to: {md_output_path}", file=sys.stderr)
    print(args.output)


def generate_markdown_report(report: dict) -> str:
    site = report.get("site", "Unknown Site")
    audited_at = report.get("audited_at", "")
    run_info = report.get("run_info", {}) if isinstance(report.get("run_info"), dict) else {}
    summary = report.get("summary", {})
    if not isinstance(summary, dict):
        score_val = summary if isinstance(summary, (int, float)) else 0
        summary = {"ai_readiness_score": score_val, "total_findings": len(findings), "critical": 0, "high": 0, "medium": 0, "low": 0}

    journey = report.get("agent_journey_scores", {})
    if not isinstance(journey, dict):
        ovr_val = journey if isinstance(journey, (int, float)) else 100
        journey = {
            "reach": ovr_val, "read": ovr_val, "understand": ovr_val,
            "trust": ovr_val, "navigate": ovr_val, "act": ovr_val,
            "overall_journey_score": ovr_val
        }

    answerability = report.get("agent_answerability", []) if isinstance(report.get("agent_answerability"), list) else []
    top_priorities = report.get("top_priorities", []) if isinstance(report.get("top_priorities"), list) else []
    findings = report.get("findings", []) if isinstance(report.get("findings"), list) else []
    proactive = report.get("proactive_recommendations", []) if isinstance(report.get("proactive_recommendations"), list) else []
    strengths = report.get("strengths", []) if isinstance(report.get("strengths"), list) else []
    methodology = report.get("methodology_and_limitations", {}) if isinstance(report.get("methodology_and_limitations"), dict) else {}

    lines = []
    lines.append(f"# Brand AI-Readiness Audit Report: {site}\n")

    # Executive Summary
    lines.append("## Executive Summary\n")
    lines.append(f"- **Target URL**: {run_info.get('target_url', site)}")
    lines.append(f"- **Audited At**: {audited_at}")
    lines.append(f"- **AI Readiness Score**: `{summary.get('ai_readiness_score', 0)}/100`")
    lines.append(f"- **Overall Journey Score**: `{journey.get('overall_journey_score', 0)}/100`")
    crit = summary.get("critical", 0)
    high = summary.get("high", 0)
    med = summary.get("medium", 0)
    low = summary.get("low", 0)
    tot = summary.get("total_findings", 0)
    lines.append(f"- **Findings Summary**: {tot} total ({crit} critical, {high} high, {med} medium, {low} low)\n")

    # 6-Pillar Agent Journey Scorecard
    lines.append("## Agent Journey Scorecard\n")
    lines.append("| Pillar | Score | Status | Description |")
    lines.append("|---|:---:|:---:|---|")
    pillar_desc = {
        "reach": "Crawlability, robots compliance, and indexability without barriers",
        "read": "Clean text and heading extractability without JavaScript traps",
        "understand": "Rich, valid Schema.org structured data and entity identity",
        "trust": "Freshness, provenance, and factual consistency across pages",
        "navigate": "Traversable internal link architecture without dead ends",
        "act": "Clear calls-to-action and machine-discoverable contact channels"
    }
    for p, desc in pillar_desc.items():
        score = journey.get(p, 100)
        status = "Optimal" if score >= 90 else ("Attention Needed" if score >= 70 else "At Risk")
        lines.append(f"| **{p.capitalize()}** | `{score}/100` | {status} | {desc} |")
    ovr = journey.get("overall_journey_score", 100)
    lines.append(f"| **Overall Journey** | `{ovr}/100` | - | Unweighted average across all 6 pillars |\n")

    # Crawl Coverage Summary
    cov = run_info.get("crawl_coverage", {})
    lines.append("## Crawl Coverage Summary\n")
    lines.append(f"- **Pages Discovered**: {cov.get('pages_discovered', 0)}")
    lines.append(f"- **Pages Crawled**: {cov.get('pages_crawled', 0)} / {run_info.get('max_pages', 20)} cap")
    lines.append(f"- **Pages Skipped**: {cov.get('pages_skipped', 0)}")
    lines.append(f"- **Crawl Duration**: {cov.get('crawl_duration_seconds', 0)}s")
    lines.append(f"- **Robots.txt Status**: `{cov.get('robots_status', 'allowed')}`")
    lines.append(f"- **JS Rendering**: `{cov.get('js_rendering_status', 'disabled')}`\n")

    # Top Priorities
    lines.append("## Top Priorities\n")
    if top_priorities:
        lines.append("| Rank | Finding ID | Title | Severity | Confidence | Affected Pages | Priority Score | Suggested Action |")
        lines.append("|:---:|:---:|---|:---:|:---:|:---:|:---:|---|")
        for tp in top_priorities:
            lines.append(
                f"| {tp.get('priority_rank', '-')} | `{tp.get('id', '')}` | {tp.get('title', '')} | "
                f"`{tp.get('severity', '')}` | `{tp.get('confidence', '')}` | {tp.get('affected_pages_count', 0)} | "
                f"`{tp.get('priority_score', 0)}` | {tp.get('suggested_action', '')} |"
            )
        lines.append("")
    else:
        lines.append("No priority remediation actions required.\n")

    # Agent Answerability Matrix
    lines.append("## Agent Answerability\n")
    if answerability:
        lines.append("| Question | Status | Confidence | Evidence & Citation |")
        lines.append("|---|:---:|:---:|---|")
        for qa in answerability:
            q = qa.get("question", "")
            st = qa.get("status", "Not found")
            conf = qa.get("confidence", "low")
            ev = qa.get("evidence", "")
            srcs = qa.get("sources", [])
            src_str = f"<br>*Sources: {', '.join(srcs)}*" if srcs else ""
            lines.append(f"| **{q}** | `{st}` | `{conf}` | {ev}{src_str} |")
        lines.append("")
    else:
        lines.append("No answerability data available.\n")

    # Strengths
    lines.append("## Strengths\n")
    if strengths:
        for s in strengths:
            lines.append(f"- **[{s.get('category', 'general').capitalize()}]** {s.get('title', '')}")
        lines.append("")
    else:
        lines.append("No explicit strength signals detected.\n")

    # Proactive Recommendations
    lines.append("## Proactive Opportunities\n")
    if proactive:
        lines.append("| ID | Title | Category | Priority | Rationale |")
        lines.append("|:---:|---|:---:|:---:|---|")
        for pr in proactive:
            lines.append(
                f"| `{pr.get('id', '')}` | {pr.get('title', '')} | `{pr.get('category', '')}` | "
                f"`{pr.get('priority', 'medium')}` | {pr.get('rationale', '')} |"
            )
        lines.append("")
    else:
        lines.append("No proactive recommendations recorded.\n")

    # Detailed Findings
    lines.append("## Detailed Audit Findings\n")
    if findings:
        for f in findings:
            fid = f.get("id", "F-???")
            title = f.get("title", "")
            sev = f.get("severity", "low")
            conf = f.get("confidence", "medium")
            cat = f.get("category", "")
            tags = ", ".join(f.get("tags", []))
            urls = f.get("affected_urls", [])
            ev = f.get("evidence", "")
            action = f.get("suggested_action", {})
            action_summary = action.get("summary", "") if isinstance(action, dict) else str(action)
            action_priority = action.get("priority", sev) if isinstance(action, dict) else sev
            action_effort = action.get("effort", "medium") if isinstance(action, dict) else "medium"

            lines.append(f"### `{fid}`: {title}\n")
            lines.append(f"- **Severity**: `{sev.upper()}` | **Confidence**: `{conf}` | **Category**: `{cat}`")
            if tags:
                lines.append(f"- **Tags**: `{tags}`")
            lines.append(f"- **Evidence**: {ev}")
            if urls:
                sample_urls = urls[:5]
                more = f" *(and {len(urls) - 5} more)*" if len(urls) > 5 else ""
                lines.append(f"- **Affected URLs** ({len(urls)}): {', '.join(sample_urls)}{more}")
            lines.append(f"- **Suggested Action**: {action_summary} *(Priority: {action_priority}, Effort: {action_effort})*\n")
    else:
        lines.append("No defect findings detected.\n")

    # Methodology & Limitations
    lines.append("## Methodology & Limitations\n")
    lines.append(f"- **Scope**: {methodology.get('audit_scope', 'Deterministic AI discoverability audit.')}")
    lines.append(f"- **Scoring Principles**: {methodology.get('deterministic_scoring', 'Rule-based readiness scoring.')}")
    lines.append(f"- **Execution Guarantee**: {methodology.get('read_only_guarantee', 'Non-destructive read-only audit.')}")
    limits = methodology.get("limitations", [])
    if limits:
        lines.append("- **Known Boundaries & Constraints**:")
        for lm in limits:
            lines.append(f"  - {lm}")
    lines.append("")

    return "\n".join(lines)


def print_terminal_summary(report: dict):
    site = report.get("site", "Site")
    summary = report.get("summary", {})
    journey = report.get("agent_journey_scores", {})
    cov = report.get("run_info", {}).get("crawl_coverage", {}) if isinstance(report.get("run_info"), dict) else {}
    if not isinstance(cov, dict):
        cov = {}
    priorities = report.get("top_priorities", []) if isinstance(report.get("top_priorities"), list) else []

    if isinstance(journey, dict):
        overall_j = journey.get("overall_journey_score", 0)
        reach_s = journey.get("reach", 100)
        read_s = journey.get("read", 100)
        und_s = journey.get("understand", 100)
        tru_s = journey.get("trust", 100)
        nav_s = journey.get("navigate", 100)
        act_s = journey.get("act", 100)
    else:
        overall_j = journey if isinstance(journey, (int, float)) else 0
        reach_s = read_s = und_s = tru_s = nav_s = act_s = overall_j

    ai_score = summary.get("ai_readiness_score", 0) if isinstance(summary, dict) else (summary if isinstance(summary, (int, float)) else 0)

    print("\n" + "=" * 62, file=sys.stderr)
    print("           BRAND AI-READINESS AUDIT SUMMARY", file=sys.stderr)
    print("=" * 62, file=sys.stderr)
    print(f" Target Site:    {site}", file=sys.stderr)
    print(f" Audited At:     {report.get('audited_at', '')}", file=sys.stderr)
    print(f" AI Readiness:   {ai_score}/100", file=sys.stderr)
    print(f" Journey Score:  {overall_j}/100", file=sys.stderr)
    c_pages = cov.get("pages_crawled", 0)
    c_dur = cov.get("crawl_duration_seconds", 0)
    c_disc = cov.get("pages_discovered", 0)
    c_skip = cov.get("pages_skipped", 0)
    print(f" Crawl Coverage: {c_pages} pages crawled in {c_dur}s ({c_disc} discovered, {c_skip} skipped)", file=sys.stderr)
    print("-" * 62, file=sys.stderr)
    print(" AGENT JOURNEY PILLARS:", file=sys.stderr)
    print(f"   Reach:     {reach_s:>3}/100  | Read:    {read_s:>3}/100", file=sys.stderr)
    print(f"   Understand:{und_s:>3}/100  | Trust:   {tru_s:>3}/100", file=sys.stderr)
    print(f"   Navigate:  {nav_s:>3}/100  | Act:     {act_s:>3}/100", file=sys.stderr)
    print("-" * 62, file=sys.stderr)
    tot_f = summary.get("total_findings", 0) if isinstance(summary, dict) else 0
    cr_f = summary.get("critical", 0) if isinstance(summary, dict) else 0
    hi_f = summary.get("high", 0) if isinstance(summary, dict) else 0
    me_f = summary.get("medium", 0) if isinstance(summary, dict) else 0
    lo_f = summary.get("low", 0) if isinstance(summary, dict) else 0
    print(f" FINDINGS: {tot_f} Total (Critical: {cr_f}, High: {hi_f}, Medium: {me_f}, Low: {lo_f})", file=sys.stderr)
    if priorities:
        print(" TOP PRIORITIES:", file=sys.stderr)
        for p in priorities[:3]:
            pr_rank = p.get("priority_rank", "-")
            pr_id = p.get("id", "")
            pr_title = p.get("title", "")
            pr_sev = p.get("severity", "")
            pr_score = p.get("priority_score", 0)
            print(f"   {pr_rank}. [{pr_id}] {pr_title} (Severity: {pr_sev}, Score: {pr_score})", file=sys.stderr)
    print("=" * 62 + "\n", file=sys.stderr)


if __name__ == "__main__":
    main()
