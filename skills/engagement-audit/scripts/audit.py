#!/usr/bin/env python3
"""
audit.py — engagement-audit skill

Checks visitor orientation, navigation clarity, CTA presence, and dead-end pages
from snapshot.json.

Usage:
    python audit.py --snapshot snapshot.json --output engagement_findings.json
"""

import argparse
import json
import re
import sys
from urllib.parse import urlparse

SKILL_NAME = "engagement-audit"

CTA_KEYWORDS = [
    "get started", "try", "sign up", "register", "buy", "shop", "contact us",
    "book", "request a demo", "request demo", "learn more", "start free",
    "free trial", "demo", "download", "subscribe", "join", "explore",
    "get access", "start now", "order now", "get quote", "schedule"
]
VALUE_PROP_KEYWORDS = [
    "help", "solution", "platform", "service", "product", "tool",
    "enables", "makes", "provides", "lets you", "for teams", "for business",
    "for companies", "we build", "we create", "we provide", "we help"
]
CONTACT_LINK_KEYWORDS = ["contact", "support", "help", "chat", "reach us", "get help"]
ABOUT_URL_PATTERNS = ["/about", "/who", "/story", "/team", "/company"]
ABOUT_TITLE_PATTERNS = ["about", "who we are", "our team"]
NAVIGATION_STOP_WORDS = {"home", "back", "next", "previous", "menu", "close", "open", "", "#"}


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--snapshot", default="snapshot.json")
    p.add_argument("--output", default="engagement_findings.json")
    return p.parse_args()


def load_snapshot(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def url_depth(url: str) -> int:
    """Return path depth (number of segments, ignoring trailing slash)."""
    path = urlparse(url).path.rstrip("/")
    if not path:
        return 0
    return len(path.split("/")) - 1


def has_cta(link_texts: list) -> bool:
    combined = " ".join(t.lower().strip() for t in link_texts)
    return any(kw in combined for kw in CTA_KEYWORDS)


def run_checks(snapshot: dict) -> tuple[list[dict], list[dict]]:
    meta = snapshot.get("crawl_meta", {})
    pages = snapshot.get("pages", [])
    findings = []
    strengths = []
    total = len(pages)

    if total == 0:
        return findings, strengths

    start_url = meta.get("start_url", "")
    homepage = next(
        (p for p in pages if p["url"] == start_url or p.get("final_url") == start_url),
        pages[0] if pages else None
    )

    # --- ENG-001: No primary CTA on homepage ---
    if homepage:
        hp_link_texts = [lnk.get("text", "") for lnk in homepage.get("links", [])
                         if lnk.get("is_internal")]
        hp_all_texts = [lnk.get("text", "") for lnk in homepage.get("links", [])]
        all_texts_sample = [t for t in hp_all_texts if t.strip()][:20]

        if not has_cta(hp_all_texts):
            findings.append({
                "check_id": "ENG-001",
                "title": "No primary call-to-action found on homepage",
                "category": "engagement",
                "severity": "high",
                "confidence": "medium",
                "affected_urls": [homepage["url"]],
                "evidence": (
                    f"Homepage ({homepage['url']}) has no link text matching CTA patterns. "
                    f"Actual link texts found: {all_texts_sample[:10]}."
                ),
                "tags": ["cta", "value-proposition"],
                "suggested_action": {
                    "summary": "Add a prominent primary CTA button above the fold (e.g. 'Get Started', 'Try Free').",
                    "priority": "high",
                    "effort": "low"
                }
            })
        else:
            strengths.append({
                "title": "Homepage has a clear primary call-to-action",
                "category": "engagement"
            })

    # --- ENG-002: Homepage lacks value proposition ---
    if homepage:
        hp_sample = homepage.get("visible_text_sample", "") or ""
        hp_h1_h2_texts = " ".join(
            h["text"] for h in homepage.get("headings", [])
            if h["level"] <= 2
        )
        has_value_prop = (
            len(hp_h1_h2_texts) >= 50 or
            any(kw in hp_sample.lower() for kw in VALUE_PROP_KEYWORDS)
        )
        if not has_value_prop and homepage.get("visible_text_length", 0) < 200:
            findings.append({
                "check_id": "ENG-002",
                "title": "Homepage lacks a clear value proposition",
                "category": "engagement",
                "severity": "high",
                "confidence": "medium",
                "affected_urls": [homepage["url"]],
                "evidence": (
                    f"Homepage heading text: '{hp_h1_h2_texts[:200] or 'none'}'. "
                    f"Visible text sample: '{hp_sample[:200] or 'empty'}'. "
                    "No clear statement of who the product/service is for or what it does."
                ),
                "tags": ["value-proposition"],
                "suggested_action": {
                    "summary": "Add an H1 stating who you help and how; add a sub-headline with one key benefit.",
                    "priority": "high",
                    "effort": "low"
                }
            })

    # --- ENG-003: Navigation has no visible labels ---
    if homepage:
        internal_link_texts = [
            lnk.get("text", "").strip()
            for lnk in homepage.get("links", [])
            if lnk.get("is_internal") and lnk.get("text", "").strip()
        ]
        meaningful_nav_texts = [
            t for t in internal_link_texts
            if len(t) > 2 and t.lower() not in NAVIGATION_STOP_WORDS
        ]
        if len(meaningful_nav_texts) < 3:
            findings.append({
                "check_id": "ENG-003",
                "title": "Navigation has fewer than 3 meaningful text labels",
                "category": "engagement",
                "severity": "high",
                "confidence": "medium",
                "affected_urls": [homepage["url"]],
                "evidence": (
                    f"Homepage has only {len(meaningful_nav_texts)} meaningful internal link "
                    f"text(s): {meaningful_nav_texts}. Navigation may be icon-only or unlabelled."
                ),
                "tags": ["navigation"],
                "suggested_action": {
                    "summary": "Add visible text labels to all navigation items; avoid icon-only navigation.",
                    "priority": "high",
                    "effort": "medium"
                }
            })
        else:
            strengths.append({
                "title": "Site navigation has descriptive text labels",
                "category": "engagement"
            })

    # --- ENG-004: Dead-end pages (Req 9, 23) ---
    # Terminal pages (docs, careers, policies) or pages with breadcrumbs should not be flagged blindly as dead ends.
    terminal_types = {"Documentation", "Careers", "Contact"}
    ok_pages = [p for p in pages if p.get("status_code", 200) == 200]
    dead_end_pages = [
        p for p in ok_pages
        if not any(lnk.get("is_internal") for lnk in p.get("links", []))
        and p.get("page_type") not in terminal_types
        and not any(term in p.get("url", "").lower() for term in ("/docs", "/careers", "/privacy", "/terms", "/support"))
    ]
    dead_end_ratio = len(dead_end_pages) / max(len(ok_pages), 1)
    if dead_end_ratio > 0.15:
        findings.append({
            "check_id": "ENG-004",
            "title": f"Dead-end pages with no internal links on {len(dead_end_pages)}/{len(ok_pages)} pages",
            "category": "engagement",
            "severity": "medium",
            "confidence": "high",
            "affected_urls": [p["url"] for p in dead_end_pages[:5]],
            "evidence": (
                f"{len(dead_end_pages)} of {len(ok_pages)} non-terminal pages ({dead_end_ratio*100:.0f}%) "
                "have no outbound internal links. Visitors arriving at these pages have no "
                "clear next step."
            ),
            "tags": ["dead-end", "navigation"],
            "suggested_action": {
                "summary": "Add navigation links, related content, or a footer to all dead-end pages.",
                "priority": "medium",
                "effort": "medium"
            }
        })
    elif len(dead_end_pages) == 0:
        strengths.append({
            "title": "No dead-end pages found — all pages have onward navigation",
            "category": "engagement"
        })

    # --- ENG-005: No About/orientation page ---
    all_urls_lower = [p["url"].lower() for p in pages]
    all_titles_lower = [p.get("title", "").lower() for p in pages]
    has_about = (
        any(p.get("page_type") == "About" for p in pages) or
        any(any(pat in u for pat in ABOUT_URL_PATTERNS) for u in all_urls_lower) or
        any(any(pat in t for pat in ABOUT_TITLE_PATTERNS) for t in all_titles_lower)
    )
    if not has_about:
        findings.append({
            "check_id": "ENG-005",
            "title": "No About or team page detected",
            "category": "engagement",
            "severity": "medium",
            "confidence": "medium",
            "affected_urls": [start_url],
            "evidence": (
                f"None of {total} crawled URLs match about/team page patterns, and no title "
                "contains 'About' or 'Our Team'. First-time visitors cannot learn who is "
                "behind the site."
            ),
            "tags": ["navigation", "value-proposition"],
            "suggested_action": {
                "summary": "Create an About page introducing the team/company and mission.",
                "priority": "medium",
                "effort": "medium"
            }
        })

    # --- ENG-006: Navigation depth > 4 ---
    deep_pages = [p for p in pages if url_depth(p["url"]) > 4]
    deep_ratio = len(deep_pages) / total
    if deep_ratio > 0.25:
        findings.append({
            "check_id": "ENG-006",
            "title": f"Deep URL structure on {len(deep_pages)}/{total} pages (depth > 4)",
            "category": "engagement",
            "severity": "medium",
            "confidence": "medium",
            "affected_urls": [p["url"] for p in deep_pages[:5]],
            "evidence": (
                f"{len(deep_pages)} pages ({deep_ratio*100:.0f}%) have URL path depth > 4 "
                f"(e.g. {deep_pages[0]['url'] if deep_pages else 'N/A'}). "
                "Deep structures make content hard to discover."
            ),
            "tags": ["navigation"],
            "suggested_action": {
                "summary": "Flatten site architecture; important content should be reachable within 3 clicks.",
                "priority": "medium",
                "effort": "high"
            }
        })

    # --- ENG-007: Thin pages with no engagement signals ---
    stub_pages = [
        p for p in pages
        if (p.get("visible_text_length", 9999) < 150 and
            not any(lnk.get("is_internal") for lnk in p.get("links", [])) and
            not p.get("images") and
            p.get("status_code", 200) == 200)
    ]
    if stub_pages:
        findings.append({
            "check_id": "ENG-007",
            "title": f"Stub/placeholder pages with no content or navigation ({len(stub_pages)} pages)",
            "category": "engagement",
            "severity": "medium",
            "confidence": "medium",
            "affected_urls": [p["url"] for p in stub_pages[:5]],
            "evidence": (
                f"{len(stub_pages)} page(s) have <150 visible characters, zero internal links, "
                "and zero images. These appear to be placeholders served to live users."
            ),
            "tags": ["dead-end", "thin-content"],
            "suggested_action": {
                "summary": "Remove or consolidate stub pages; ensure every published page has meaningful content.",
                "priority": "medium",
                "effort": "medium"
            }
        })

    # --- ENG-008: No contact/support link ---
    all_link_texts = []
    for p in pages:
        for lnk in p.get("links", []):
            all_link_texts.append(lnk.get("text", "").lower())
    has_contact_link = any(
        any(kw in t for kw in CONTACT_LINK_KEYWORDS)
        for t in all_link_texts
    )
    if not has_contact_link:
        findings.append({
            "check_id": "ENG-008",
            "title": "No contact or support link found across any crawled page",
            "category": "engagement",
            "severity": "low",
            "confidence": "medium",
            "affected_urls": [start_url],
            "evidence": (
                f"No link text across {total} crawled pages matches contact/support patterns "
                f"({', '.join(CONTACT_LINK_KEYWORDS[:4])}, ...)."
            ),
            "tags": ["navigation", "cta"],
            "suggested_action": {
                "summary": "Add a 'Contact' or 'Support' link to the site header or footer.",
                "priority": "low",
                "effort": "low"
            }
        })

    return findings, strengths


def main():
    args = parse_args()
    try:
        snapshot = load_snapshot(args.snapshot)
    except FileNotFoundError:
        print(f"[ERROR] Snapshot not found: {args.snapshot}", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"[ERROR] Invalid JSON: {e}", file=sys.stderr)
        sys.exit(1)

    findings, strengths = run_checks(snapshot)
    output = {"skill": SKILL_NAME, "findings": findings, "strengths": strengths}

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"[OK] {SKILL_NAME}: {len(findings)} finding(s), {len(strengths)} strength(s) → {args.output}",
          file=sys.stderr)
    print(args.output)


if __name__ == "__main__":
    main()
