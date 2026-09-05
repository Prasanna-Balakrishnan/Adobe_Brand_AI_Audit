#!/usr/bin/env python3
"""
audit.py — crawlability-render-audit skill

Reads snapshot.json, runs crawlability checks, writes standardised findings JSON.

Usage:
    python audit.py --snapshot snapshot.json --output crawlability_findings.json
"""

import argparse
import json
import sys
from urllib.parse import urlparse


SKILL_NAME = "crawlability-render-audit"

SPA_MARKERS = [
    '<div id="root">',
    "<div id='root'>",
    '<div id="app">',
    "<div id='app'>",
    "data-reactroot",
    "__NEXT_DATA__",
    "__nuxt",
    "ng-version=",
]


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--snapshot", default="snapshot.json")
    p.add_argument("--output", default="crawlability_findings.json")
    return p.parse_args()


def load_snapshot(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def has_noindex(page: dict) -> bool:
    mr = (page.get("meta_robots") or "").lower()
    xr = (page.get("x_robots_tag") or "").lower()
    return "noindex" in mr or "noindex" in xr


def is_spa_page(page: dict) -> bool:
    """Heuristic: low text + SPA markers in raw HTML."""
    # We don't have raw HTML in snapshot, use visible_text_length as proxy
    # and check page title / heading count as proxy for SPA
    vt = page.get("visible_text_length", 9999)
    if vt >= 300:
        return False
    # Check for SPA markers via visible_text_sample (limited, but best we have)
    sample = page.get("visible_text_sample", "")
    # Also check JSON-LD absence and heading absence as SPA indicators
    has_no_headings = len(page.get("headings", [])) == 0
    has_no_jsonld = len(page.get("json_ld", [])) == 0
    crawled_with_js = page.get("crawled_with_js", False)
    return vt < 300 and has_no_headings and not crawled_with_js


def run_checks(snapshot: dict) -> tuple[list[dict], list[dict]]:
    """Return (findings, strengths)."""
    meta = snapshot.get("crawl_meta", {})
    pages = snapshot.get("pages", [])
    findings = []
    strengths = []

    total = len(pages)
    if total == 0:
        findings.append({
            "check_id": "CRA-003",
            "title": "Homepage failed to load — no pages crawled",
            "category": "discoverability",
            "severity": "critical",
            "confidence": "high",
            "affected_urls": [meta.get("start_url", "unknown")],
            "evidence": "The crawler returned 0 pages. The start URL may be unreachable.",
            "tags": ["crawlability"],
            "suggested_action": {
                "summary": "Verify the site is accessible and the URL is correct.",
                "priority": "critical",
                "effort": "low"
            }
        })
        return findings, strengths

    # --- CRA-001: robots.txt blocks all crawling ---
    disallowed = meta.get("disallowed_paths", [])
    if "/" in disallowed and total <= 1:
        findings.append({
            "check_id": "CRA-001",
            "title": "robots.txt disallows all crawling (Disallow: /)",
            "category": "discoverability",
            "severity": "critical",
            "confidence": "high",
            "affected_urls": [meta.get("robots_txt_url", meta.get("start_url"))],
            "evidence": (
                f"robots.txt at {meta.get('robots_txt_url')} contains 'Disallow: /'. "
                f"Only {total} page(s) were successfully crawled."
            ),
            "tags": ["robots-txt", "crawlability"],
            "suggested_action": {
                "summary": (
                    "Remove the global 'Disallow: /' directive from robots.txt. "
                    "Use targeted Disallow rules for private paths only."
                ),
                "priority": "critical",
                "effort": "low"
            }
        })

    # --- CRA-002: noindex on ALL pages ---
    noindex_pages = [p for p in pages if has_noindex(p)]
    noindex_count = len(noindex_pages)
    noindex_ratio = noindex_count / total

    if noindex_ratio == 1.0:
        findings.append({
            "check_id": "CRA-002",
            "title": "noindex directive present on every crawled page",
            "category": "discoverability",
            "severity": "critical",
            "confidence": "high",
            "affected_urls": [p["url"] for p in noindex_pages[:5]],
            "evidence": (
                f"All {noindex_count}/{total} crawled pages have 'noindex' in "
                "meta_robots or X-Robots-Tag. AI assistants and search engines "
                "will not index this site."
            ),
            "tags": ["noindex", "crawlability"],
            "suggested_action": {
                "summary": "Remove noindex from all public-facing pages immediately.",
                "priority": "critical",
                "effort": "low"
            }
        })
    elif noindex_ratio > 0.5:
        # --- CRA-005: noindex on majority ---
        findings.append({
            "check_id": "CRA-005",
            "title": f"noindex on {noindex_count}/{total} crawled pages (majority)",
            "category": "discoverability",
            "severity": "high",
            "confidence": "high",
            "affected_urls": [p["url"] for p in noindex_pages[:5]],
            "evidence": (
                f"{noindex_count} of {total} pages ({noindex_ratio*100:.0f}%) have "
                "noindex directives. These pages are invisible to AI assistants."
            ),
            "tags": ["noindex", "crawlability"],
            "suggested_action": {
                "summary": "Audit noindex usage; remove from content pages that should be indexed.",
                "priority": "high",
                "effort": "medium"
            }
        })
    elif noindex_count == 0:
        strengths.append({
            "title": "No noindex directives on any crawled page",
            "category": "discoverability"
        })

    # --- CRA-003: Homepage HTTP error ---
    start_url = meta.get("start_url", "")
    homepage = next((p for p in pages if p["url"] == start_url or
                     p["final_url"] == start_url), pages[0] if pages else None)
    if homepage and homepage.get("status_code", 200) >= 400:
        findings.append({
            "check_id": "CRA-003",
            "title": f"Homepage returns HTTP {homepage['status_code']}",
            "category": "discoverability",
            "severity": "critical",
            "confidence": "high",
            "affected_urls": [homepage["url"]],
            "evidence": (
                f"The homepage at {homepage['url']} returned HTTP {homepage['status_code']}. "
                "Crawlers and AI agents cannot retrieve any content."
            ),
            "tags": ["crawlability"],
            "suggested_action": {
                "summary": "Fix the server error on the homepage immediately.",
                "priority": "critical",
                "effort": "high"
            }
        })
    elif homepage and homepage.get("status_code", 0) == 200:
        strengths.append({
            "title": "Homepage returns HTTP 200",
            "category": "discoverability"
        })

    # --- CRA-004: Redirect loops ---
    loop_pages = [
        p for p in pages
        if p.get("status_code") == 310 or len(p.get("redirect_chain", [])) > 5
    ]
    if loop_pages:
        findings.append({
            "check_id": "CRA-004",
            "title": f"Redirect loop or excessive redirects on {len(loop_pages)} page(s)",
            "category": "discoverability",
            "severity": "high",
            "confidence": "high",
            "affected_urls": [p["url"] for p in loop_pages[:5]],
            "evidence": (
                f"{len(loop_pages)} page(s) triggered redirect loops or chains longer "
                f"than 5 hops. Examples: {', '.join(p['url'] for p in loop_pages[:3])}."
            ),
            "tags": ["redirect", "crawlability"],
            "suggested_action": {
                "summary": "Audit redirect rules; ensure each URL has a single final destination.",
                "priority": "high",
                "effort": "medium"
            }
        })

    # --- CRA-006: Missing canonical on ALL pages ---
    pages_without_canonical = [
        p for p in pages if not p.get("canonical")
    ]
    canonical_ratio_missing = len(pages_without_canonical) / total

    if canonical_ratio_missing == 1.0:
        findings.append({
            "check_id": "CRA-006",
            "title": "No canonical tags on any crawled page",
            "category": "discoverability",
            "severity": "high",
            "confidence": "high",
            "affected_urls": [p["url"] for p in pages[:5]],
            "evidence": (
                f"0 of {total} crawled pages contain a <link rel='canonical'> tag. "
                "Without canonicals, duplicate content dilutes AI citation quality."
            ),
            "tags": ["canonical", "crawlability"],
            "suggested_action": {
                "summary": "Add <link rel='canonical'> to every page pointing to its preferred URL.",
                "priority": "high",
                "effort": "medium"
            }
        })
    elif canonical_ratio_missing >= 0.25:
        # --- CRA-009: Missing canonical on some pages ---
        findings.append({
            "check_id": "CRA-009",
            "title": (
                f"Canonical tags missing on {len(pages_without_canonical)}/{total} pages"
            ),
            "category": "discoverability",
            "severity": "medium",
            "confidence": "high",
            "affected_urls": [p["url"] for p in pages_without_canonical[:5]],
            "evidence": (
                f"{len(pages_without_canonical)} of {total} pages "
                f"({canonical_ratio_missing*100:.0f}%) lack canonical tags."
            ),
            "tags": ["canonical", "crawlability"],
            "suggested_action": {
                "summary": "Systematically add canonical tags; prioritise high-traffic pages.",
                "priority": "medium",
                "effort": "medium"
            }
        })
    else:
        strengths.append({
            "title": "Consistent canonical tags across all crawled pages",
            "category": "discoverability"
        })

    # --- CRA-007: Broken internal links ---
    error_pages = [p for p in pages if p.get("status_code", 200) >= 400]
    error_ratio = len(error_pages) / total
    if error_ratio > 0.30:
        findings.append({
            "check_id": "CRA-007",
            "title": f"High rate of broken internal links ({len(error_pages)}/{total} pages)",
            "category": "discoverability",
            "severity": "high",
            "confidence": "high",
            "affected_urls": [p["url"] for p in error_pages[:10]],
            "evidence": (
                f"{len(error_pages)} of {total} crawled pages returned HTTP 4xx/5xx errors "
                f"({error_ratio*100:.0f}%)."
            ),
            "tags": ["broken-link", "crawlability"],
            "suggested_action": {
                "summary": "Fix or redirect broken URLs. Audit internal links site-wide.",
                "priority": "high",
                "effort": "medium"
            }
        })
    elif 0.10 < error_ratio <= 0.30:
        findings.append({
            "check_id": "CRA-007",
            "title": f"Broken internal links detected ({len(error_pages)}/{total} pages)",
            "category": "discoverability",
            "severity": "medium",
            "confidence": "high",
            "affected_urls": [p["url"] for p in error_pages[:10]],
            "evidence": (
                f"{len(error_pages)} of {total} pages returned 4xx/5xx errors "
                f"({error_ratio*100:.0f}%)."
            ),
            "tags": ["broken-link", "crawlability"],
            "suggested_action": {
                "summary": "Fix broken URLs; set up 301 redirects for moved content.",
                "priority": "medium",
                "effort": "medium"
            }
        })
    elif len(error_pages) > 0:
        findings.append({
            "check_id": "CRA-007",
            "title": f"Minor broken internal links ({len(error_pages)} pages)",
            "category": "discoverability",
            "severity": "low",
            "confidence": "high",
            "affected_urls": [p["url"] for p in error_pages[:5]],
            "evidence": (
                f"{len(error_pages)} of {total} pages returned 4xx/5xx errors "
                f"({error_ratio*100:.0f}%)."
            ),
            "tags": ["broken-link", "crawlability"],
            "suggested_action": {
                "summary": "Fix or redirect the broken URLs listed.",
                "priority": "low",
                "effort": "low"
            }
        })
    else:
        strengths.append({
            "title": "All crawled pages return HTTP 200",
            "category": "discoverability"
        })

    # --- CRA-008: JS-only content ---
    js_only_pages = [
        p for p in pages
        if (not p.get("crawled_with_js", False) and
            p.get("visible_text_length", 9999) < 300 and
            len(p.get("headings", [])) == 0 and
            p.get("status_code", 200) == 200)
    ]
    if js_only_pages:
        findings.append({
            "check_id": "CRA-008",
            "title": f"Suspected JS-only content on {len(js_only_pages)} page(s)",
            "category": "discoverability",
            "severity": "high",
            "confidence": "medium",
            "affected_urls": [p["url"] for p in js_only_pages[:5]],
            "evidence": (
                f"{len(js_only_pages)} page(s) have fewer than 300 visible characters "
                "and no headings when crawled without JavaScript. These pages may be "
                "invisible to AI assistants that do not execute JS."
            ),
            "tags": ["js-render", "crawlability"],
            "suggested_action": {
                "summary": (
                    "Implement server-side rendering (SSR) or static site generation (SSG) "
                    "so crawlers receive fully-rendered HTML."
                ),
                "priority": "high",
                "effort": "high"
            }
        })
    else:
        strengths.append({
            "title": "All crawled pages have content without JS rendering",
            "category": "discoverability"
        })

    # --- CRA-010: Conflicting canonical ---
    conflicting = []
    crawled_urls = {p["url"].rstrip("/") for p in pages} | {p.get("final_url", "").rstrip("/") for p in pages}
    for p in pages:
        c = p.get("canonical")
        fu = p.get("final_url", p["url"])
        if c:
            c_norm = c.rstrip("/")
            fu_norm = fu.rstrip("/")
            if c_norm != fu_norm and c_norm not in crawled_urls:
                conflicting.append(p)
    if conflicting:
        findings.append({
            "check_id": "CRA-010",
            "title": f"Conflicting or off-site canonical tags on {len(conflicting)} page(s)",
            "category": "discoverability",
            "severity": "medium",
            "confidence": "high",
            "affected_urls": [p["url"] for p in conflicting[:5]],
            "evidence": (
                f"{len(conflicting)} page(s) have canonical URLs that differ from their "
                "final URL and point to uncrawled locations. "
                f"Example: {conflicting[0]['url']} → canonical: {conflicting[0].get('canonical')}."
            ),
            "tags": ["canonical", "crawlability"],
            "suggested_action": {
                "summary": "Verify each page's canonical tag points to its correct preferred URL.",
                "priority": "medium",
                "effort": "medium"
            }
        })

    # --- CRA-011: Missing title or meta description ---
    missing_meta_pages = [
        p for p in pages
        if not p.get("title") or not p.get("meta_description")
    ]
    meta_missing_ratio = len(missing_meta_pages) / total
    if meta_missing_ratio > 0.25:
        findings.append({
            "check_id": "CRA-011",
            "title": (
                f"Missing title or meta description on {len(missing_meta_pages)}/{total} pages"
            ),
            "category": "discoverability",
            "severity": "medium",
            "confidence": "high",
            "affected_urls": [p["url"] for p in missing_meta_pages[:5]],
            "evidence": (
                f"{len(missing_meta_pages)} of {total} pages "
                f"({meta_missing_ratio*100:.0f}%) are missing a <title> and/or "
                "<meta name='description'>."
            ),
            "tags": ["page-title", "meta-description", "crawlability"],
            "suggested_action": {
                "summary": "Add unique, descriptive title tags and meta descriptions to every page.",
                "priority": "medium",
                "effort": "medium"
            }
        })

    # --- CRA-012: Thin content ---
    thin_pages = [p for p in pages if p.get("visible_text_length", 9999) < 200]
    thin_ratio = len(thin_pages) / total
    if thin_ratio > 0.25:
        findings.append({
            "check_id": "CRA-012",
            "title": f"Thin content on {len(thin_pages)}/{total} pages (<200 characters)",
            "category": "discoverability",
            "severity": "medium",
            "confidence": "high",
            "affected_urls": [p["url"] for p in thin_pages[:5]],
            "evidence": (
                f"{len(thin_pages)} of {total} pages ({thin_ratio*100:.0f}%) have fewer "
                "than 200 visible characters. AI assistants have little content to cite."
            ),
            "tags": ["thin-content", "crawlability"],
            "suggested_action": {
                "summary": "Expand thin pages with substantive content or consolidate them.",
                "priority": "medium",
                "effort": "high"
            }
        })

    # robots.txt strength
    if meta.get("robots_txt_status", 0) == 200 and "/" not in disallowed:
        strengths.append({
            "title": "robots.txt present and permits crawling",
            "category": "discoverability"
        })

    return findings, strengths


def main():
    args = parse_args()

    try:
        snapshot = load_snapshot(args.snapshot)
    except FileNotFoundError:
        print(f"[ERROR] Snapshot file not found: {args.snapshot}", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"[ERROR] Invalid snapshot JSON: {e}", file=sys.stderr)
        sys.exit(1)

    findings, strengths = run_checks(snapshot)

    output = {
        "skill": SKILL_NAME,
        "findings": findings,
        "strengths": strengths
    }

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(
        f"[OK] {SKILL_NAME}: {len(findings)} finding(s), {len(strengths)} strength(s) → {args.output}",
        file=sys.stderr
    )
    print(args.output)


if __name__ == "__main__":
    main()
