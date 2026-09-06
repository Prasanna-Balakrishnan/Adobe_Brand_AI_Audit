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

    # --- CRA-013: Disallowed rules block inferred high-value discoverability pages ---
    # Zero hardcoding: Uses page-type inference and link targets dynamically.
    high_value_types = {"About", "Contact", "Product", "Service", "Pricing", "Documentation"}
    blocked_high_value = []
    for p in pages:
        pt = p.get("page_type")
        if pt in high_value_types:
            p_path = urlparse(p.get("url", "")).path
            for dis in disallowed:
                if dis and dis != "/" and p_path.startswith(dis):
                    blocked_high_value.append((p.get("url"), pt, dis))
                    break
    if not blocked_high_value:
        high_value_link_keywords = {"about", "contact", "pricing", "product", "docs", "documentation", "support"}
        for p in pages:
            for l in p.get("links", []):
                if l.get("is_internal"):
                    l_path = urlparse(l.get("href", "")).path
                    l_text = l.get("text", "").lower()
                    if any(kw in l_text for kw in high_value_link_keywords):
                        for dis in disallowed:
                            if dis and dis != "/" and l_path.startswith(dis):
                                blocked_high_value.append((l.get("href"), f"Link ({l.get('text')})", dis))
                                break
    if blocked_high_value and "/" not in disallowed:
        distinct_blocked = list({url: (pt, dis) for url, pt, dis in blocked_high_value}.items())
        findings.append({
            "check_id": "CRA-013",
            "title": f"robots.txt disallow rules block {len(distinct_blocked)} inferred high-value discoverability page(s)",
            "category": "discoverability",
            "severity": "high",
            "confidence": "high",
            "affected_urls": [url for url, _ in distinct_blocked[:5]],
            "evidence": (
                f"robots.txt disallows path(s) that match high-importance site pages: "
                f"{', '.join(f'{url} (type: {info[0]}, rule: Disallow: {info[1]})' for url, info in distinct_blocked[:3])}. "
                "AI search agents and crawlers cannot access core brand, orientation, or product knowledge."
            ),
            "tags": ["robots-txt", "crawlability", "discoverability"],
            "suggested_action": {
                "summary": "Revise robots.txt to allow crawling of core brand, product, and orientation pages.",
                "priority": "high",
                "effort": "low"
            }
        })

    # --- CRA-014: Inefficient or insecure redirect chains ---
    inefficient_redirects = []
    for p in pages:
        chain = p.get("redirect_chain", [])
        if len(chain) >= 3 and not p.get("redirect_loop", False) and p.get("status_code", 200) != 310:
            inefficient_redirects.append(p)
        elif len(chain) >= 2:
            schemes = [urlparse(u).scheme for u in chain if u]
            if len(schemes) >= 3 and schemes != sorted(schemes):
                inefficient_redirects.append(p)

    if inefficient_redirects and not loop_pages:
        findings.append({
            "check_id": "CRA-014",
            "title": f"Excessive redirect hops on {len(inefficient_redirects)} page(s) (>= 3 hops)",
            "category": "discoverability",
            "severity": "medium",
            "confidence": "high",
            "affected_urls": [p["url"] for p in inefficient_redirects[:5]],
            "evidence": (
                f"{len(inefficient_redirects)} page(s) require 3 or more redirect hops to reach their destination. "
                f"Example: {inefficient_redirects[0]['url']} → {len(inefficient_redirects[0].get('redirect_chain', []))} hops. "
                "Long chains deplete crawler budget and increase request latency for AI agents."
            ),
            "tags": ["redirect", "crawlability"],
            "suggested_action": {
                "summary": "Point internal links directly to final destination URLs and collapse intermediate 301 redirects.",
                "priority": "medium",
                "effort": "low"
            }
        })

    # --- CRA-015: Indexing block on primary brand or orientation pages ---
    if noindex_ratio < 1.0:
        blocked_brand_pages = []
        for p in pages:
            if has_noindex(p):
                is_home = (p["url"] == start_url or p.get("final_url") == start_url or p == homepage)
                is_core = p.get("page_type") in ("About", "Contact", "Product", "Pricing")
                if is_home:
                    blocked_brand_pages.append((p, "Homepage", "critical"))
                elif is_core:
                    blocked_brand_pages.append((p, p.get("page_type"), "high"))

        if blocked_brand_pages:
            top_severity = "critical" if any(sev == "critical" for _, _, sev in blocked_brand_pages) else "high"
            sample_pages = [f"{p.get('url')} ({role})" for p, role, _ in blocked_brand_pages[:3]]
            findings.append({
                "check_id": "CRA-015",
                "title": f"noindex directive on primary brand/orientation page ({blocked_brand_pages[0][1]})",
                "category": "discoverability",
                "severity": top_severity,
                "confidence": "high",
                "affected_urls": [p["url"] for p, _, _ in blocked_brand_pages[:5]],
                "evidence": (
                    f"{len(blocked_brand_pages)} key orientation page(s) specify 'noindex' in meta_robots or X-Robots-Tag: "
                    f"{', '.join(sample_pages)}. "
                    "AI search engines will exclude these foundational brand pages from search indexes."
                ),
                "tags": ["noindex", "indexability", "crawlability"],
                "suggested_action": {
                    "summary": "Remove noindex headers and meta tags from primary brand and orientation pages.",
                    "priority": top_severity,
                    "effort": "low"
                }
            })

    # --- CRA-016: Canonical URL points to error, redirect, or invalid destination ---
    status_map = {p["url"].rstrip("/"): p.get("status_code", 200) for p in pages}
    for p in pages:
        fu = p.get("final_url")
        if fu:
            status_map[fu.rstrip("/")] = p.get("status_code", 200)

    broken_canonicals = []
    redirect_canonicals = []
    invalid_canonicals = []
    for p in pages:
        c = p.get("canonical")
        if not c:
            continue
        c_clean = c.strip()
        if "#" in c_clean or c_clean.startswith("javascript:") or c_clean.startswith("mailto:"):
            invalid_canonicals.append((p, c_clean, "contains fragment or invalid scheme"))
            continue
        c_norm = c_clean.rstrip("/")
        sc = status_map.get(c_norm)
        if sc is not None:
            if sc >= 400:
                broken_canonicals.append((p, c_clean, f"returns HTTP {sc}"))
            elif sc in (301, 302, 307, 308):
                redirect_canonicals.append((p, c_clean, f"is a redirect (HTTP {sc})"))

    if broken_canonicals:
        findings.append({
            "check_id": "CRA-016",
            "title": f"Canonical URL points to broken error page on {len(broken_canonicals)} page(s)",
            "category": "discoverability",
            "severity": "high",
            "confidence": "high",
            "affected_urls": [p["url"] for p, _, _ in broken_canonicals[:5]],
            "evidence": (
                f"{len(broken_canonicals)} page(s) have <link rel='canonical'> pointing to 4xx/5xx error URLs. "
                f"Example: {broken_canonicals[0][0]['url']} → canonical {broken_canonicals[0][1]} ({broken_canonicals[0][2]}). "
                "AI search engines cannot index the canonical destination."
            ),
            "tags": ["canonical", "indexability", "canonical-conflict"],
            "suggested_action": {
                "summary": "Fix canonical URLs to reference existing, valid HTTP 200 URLs.",
                "priority": "high",
                "effort": "low"
            }
        })
    elif redirect_canonicals or invalid_canonicals:
        items = redirect_canonicals + invalid_canonicals
        findings.append({
            "check_id": "CRA-016",
            "title": f"Canonical URL points to redirect or invalid target on {len(items)} page(s)",
            "category": "discoverability",
            "severity": "medium",
            "confidence": "high",
            "affected_urls": [p["url"] for p, _, _ in items[:5]],
            "evidence": (
                f"{len(items)} page(s) declare canonical URLs that redirect or contain fragment/syntax issues. "
                f"Example: {items[0][0]['url']} → canonical {items[0][1]} ({items[0][2]})."
            ),
            "tags": ["canonical", "indexability", "canonical-conflict"],
            "suggested_action": {
                "summary": "Update canonical tags to point directly to the definitive HTTP 200 URL without redirects or fragments.",
                "priority": "medium",
                "effort": "low"
            }
        })

    # --- CRA-018: Duplicate URL variants and query parameter pollution ---
    tracking_params = {"utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
                       "gclid", "fbclid", "msclkid", "sessionid", "phpsessid", "jsessionid"}
    pages_with_tracking = []
    for p in pages:
        parsed_url = urlparse(p.get("url", ""))
        if parsed_url.query:
            query_keys = {q.split("=")[0].lower() for q in parsed_url.query.split("&") if q}
            if query_keys & tracking_params:
                pages_with_tracking.append(p["url"])

    if not pages_with_tracking:
        for p in pages:
            for l in p.get("links", []):
                if l.get("is_internal"):
                    parsed_link = urlparse(l.get("href", ""))
                    if parsed_link.query:
                        query_keys = {q.split("=")[0].lower() for q in parsed_link.query.split("&") if q}
                        if query_keys & tracking_params:
                            pages_with_tracking.append(l["href"])
                            break
            if pages_with_tracking:
                break

    if pages_with_tracking:
        distinct_tracking = list(dict.fromkeys(pages_with_tracking))
        findings.append({
            "check_id": "CRA-018",
            "title": f"Tracking/session parameters pollute internal URLs on {len(distinct_tracking)} page(s)",
            "category": "discoverability",
            "severity": "medium",
            "confidence": "high",
            "affected_urls": distinct_tracking[:5],
            "evidence": (
                f"Internal links or crawled URLs include tracking/session parameters (e.g. {distinct_tracking[0]}). "
                "Tracking parameters split crawl budget and create duplicate URL indexing issues for AI agents."
            ),
            "tags": ["url-hygiene", "canonical", "crawlability"],
            "suggested_action": {
                "summary": "Strip marketing tracking and session tokens from internal site links.",
                "priority": "medium",
                "effort": "low"
            }
        })

    # --- CRA-019: Material raw-vs-rendered content disparity ---
    # Guardrail: Never penalize JS usage by itself. Only flag when meaningful disparity exists
    # and important content is unavailable without rendering.
    disparity_pages = [
        p for p in pages
        if p.get("crawled_with_js", False) and (
            p.get("js_dependent_content", False) or
            p.get("content_disparity", 0) > 500 or
            (p.get("raw_text_length", 9999) < 200 and p.get("rendered_text_length", 0) > 600)
        )
    ]
    if disparity_pages:
        findings.append({
            "check_id": "CRA-019",
            "title": f"Material raw-vs-rendered content disparity on {len(disparity_pages)} page(s)",
            "category": "discoverability",
            "severity": "high" if any(p.get("raw_text_length", 9999) < 200 for p in disparity_pages) else "medium",
            "confidence": "high",
            "affected_urls": [p["url"] for p in disparity_pages[:5]],
            "evidence": (
                f"{len(disparity_pages)} page(s) require JavaScript rendering to expose their primary content. "
                f"Example: {disparity_pages[0]['url']} has raw HTML text of {disparity_pages[0].get('raw_text_length', 0)} chars "
                f"vs {disparity_pages[0].get('rendered_text_length', 0)} rendered chars. "
                "AI agents without client-side JS rendering engines cannot extract this information."
            ),
            "tags": ["js-render", "machine-readable", "content-disparity"],
            "suggested_action": {
                "summary": "Provide server-side rendered (SSR) or pre-rendered HTML for critical content and headings.",
                "priority": "high",
                "effort": "medium"
            }
        })

    # --- CRA-020: Discoverability hindered by absence of sitemap reference ---
    # Guardrail: Missing Sitemap alone produces NO finding. Only report when discoverability is materially limited.
    sitemaps = meta.get("sitemaps", [])
    if meta.get("robots_txt_status") == 200 and not sitemaps:
        coverage = meta.get("crawl_coverage", {})
        discovery_limited = (
            coverage.get("discovery_limited") is True or
            meta.get("discovery_limited") is True or
            (meta.get("crawl_timeout_hit") and meta.get("pages_discovered", 0) > total)
        )
        if discovery_limited:
            findings.append({
                "check_id": "CRA-020",
                "title": "Crawl discoverability limited and no XML sitemap declared in robots.txt",
                "category": "discoverability",
                "severity": "low",
                "confidence": "medium",
                "affected_urls": [meta.get("robots_txt_url", start_url)],
                "evidence": (
                    f"robots.txt does not declare a Sitemap directive and crawl discovery was materially constrained. "
                    "Declaring an XML sitemap helps AI discovery agents find all authoritative site URLs."
                ),
                "tags": ["robots-txt", "discoverability"],
                "suggested_action": {
                    "summary": "Add 'Sitemap: <url>' to robots.txt to aid search and AI indexers in discovering all content.",
                    "priority": "low",
                    "effort": "low"
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
