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
from score import compute_summary

MARKETPLACE_VERSION = "1.0.0"

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
    p.add_argument("--url", required=True, help="Site URL to audit")
    p.add_argument("--max-pages", type=int, default=20)
    p.add_argument("--output", default="report.json")
    p.add_argument("--work-dir", default="./audit_work")
    p.add_argument("--use-js-render", action="store_true")
    p.add_argument("--stale-threshold-days", type=int, default=365)
    return p.parse_args()


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
    print(f"[INFO] Marketplace root: {marketplace_root}", file=sys.stderr)
    print(f"[INFO] Auditing: {args.url}", file=sys.stderr)
    print(f"[INFO] Work dir: {work_dir.resolve()}", file=sys.stderr)

    start_time = time.time()
    audited_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    # ── Step 1: site-crawler ────────────────────────────────────────────────
    snapshot_path = str(work_dir / "snapshot.json")
    crawler_script = str(marketplace_root / "skills" / "site-crawler" / "scripts" / "crawl.py")

    print(f"\n[STEP 1] Running site-crawler...", file=sys.stderr)
    crawl_start = time.time()

    crawler_cmd = [
        sys.executable, crawler_script,
        "--url", args.url,
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
            "url": args.url,
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
        # Add stale threshold for freshness skill
        if skill_name == "freshness-corroboration-audit":
            cmd += ["--stale-threshold-days", str(args.stale_threshold_days)]

        ok, _ = run_subprocess(cmd, skill_name)

        if ok:
            output = load_json_safe(skill_output_path, skill_name)
            if output:
                skill_outputs.append(output)
                skills_invoked.append(skill_name)
            else:
                skills_invoked.append(f"{skill_name}_SKIPPED")
        else:
            skills_invoked.append(f"{skill_name}_SKIPPED")

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

    # ── Step 5: Score ──────────────────────────────────────────────────────
    print(f"\n[STEP 5] Computing score...", file=sys.stderr)
    summary = compute_summary(deduped_findings)
    print(f"  AI Readiness Score: {summary['ai_readiness_score']}/100", file=sys.stderr)

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

    site = urlparse(args.url).netloc or args.url

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

    report = {
        "site": site,
        "audited_at": audited_at,
        "run_info": {
            "marketplace_version": MARKETPLACE_VERSION,
            "skills_invoked": skills_invoked,
            "pages_crawled": pages_crawled,
            "max_pages": args.max_pages,
            "crawl_duration_seconds": round(crawl_duration, 1),
            "robots_txt_respected": crawl_meta.get("robots_txt_respected", True)
        },
        "summary": summary,
        "findings": clean_findings,
        "proactive_recommendations": proactive_recommendations,
        "strengths": all_strengths
    }

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    total_time = time.time() - start_time
    print(f"\n[DONE] Audit completed in {total_time:.1f}s", file=sys.stderr)
    print(f"[DONE] Report written to: {args.output}", file=sys.stderr)
    print(f"[DONE] Score: {summary['ai_readiness_score']}/100 | "
          f"Findings: {summary['total_findings']} | "
          f"Recommendations: {len(proactive_recommendations)}", file=sys.stderr)
    print(args.output)


if __name__ == "__main__":
    main()
