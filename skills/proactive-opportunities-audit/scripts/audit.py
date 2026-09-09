#!/usr/bin/env python3
"""
audit.py — proactive-opportunities-audit skill

Runs LAST after deduplicated findings are available. Suggests improvements
beyond defects without duplicating existing findings.

Usage:
    python audit.py --snapshot snapshot.json \
                    --findings deduplicated_findings.json \
                    --output proactive_findings.json
"""

import argparse
import json
import re
import sys
from urllib.parse import urlparse

SKILL_NAME = "proactive-opportunities-audit"

PRODUCT_URL_PATTERNS = ["/product", "/item", "/shop", "/store", "/buy", "/pricing", "/plan"]
BLOG_URL_PATTERNS = ["/blog", "/article", "/news", "/post", "/insight"]
FAQ_URL_PATTERNS = ["/faq", "/help", "/questions", "/q-and-a", "/support"]
EVENT_KEYWORDS = ["event", "conference", "webinar", "summit", "meetup", "workshop"]
VIDEO_KEYWORDS = ["video", "watch", "demo", "tutorial", "webinar", "recording"]
HOW_TO_KEYWORDS = ["how to", "steps", "guide", "tutorial", "walkthrough"]
REVIEW_KEYWORDS = ["review", "rating", "testimonial", "case study", "customer story"]
MULTILINGUAL_PATTERNS = ["/en/", "/fr/", "/de/", "/es/", "/pt/", "/ja/", "/zh/",
                          "/it/", "/nl/", "/ar/"]


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--snapshot", default="snapshot.json")
    p.add_argument("--findings", default="deduplicated_findings.json")
    p.add_argument("--output", default="proactive_findings.json")
    return p.parse_args()


def load_json(path: str) -> dict | list:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def get_finding_topics(findings: list) -> set:
    """Build a set of (category, topic_keywords) from existing findings."""
    topics = set()
    for f in findings:
        tags = f.get("tags", [])
        cat = f.get("category", "")
        for tag in tags:
            topics.add((cat, tag))
        # Also extract key terms from title
        title = f.get("title", "").lower()
        for kw in ["faq", "video", "event", "review", "hreflang", "breadcrumb",
                   "search", "opengraph", "og:", "howto", "how-to"]:
            if kw in title:
                topics.add((cat, kw))
    return topics


def get_all_schema_types(pages: list) -> set:
    types = set()
    for p in pages:
        for block in p.get("json_ld", []):
            if isinstance(block, dict):
                t = block.get("@type")
                if isinstance(t, str):
                    types.add(t)
                elif isinstance(t, list):
                    types.update(t)
                for node in block.get("@graph", []):
                    if isinstance(node, dict):
                        nt = node.get("@type")
                        if isinstance(nt, str):
                            types.add(nt)
                        elif isinstance(nt, list):
                            types.update(nt)
    return types


def text_contains_any(text: str, keywords: list) -> bool:
    text_lower = text.lower()
    return any(kw in text_lower for kw in keywords)


def url_matches_any(url: str, patterns: list) -> bool:
    url_lower = url.lower()
    return any(p in url_lower for p in patterns)


def run_opportunities(snapshot: dict, findings: list) -> list[dict]:
    pages = snapshot.get("pages", [])
    meta = snapshot.get("crawl_meta", {})
    total = len(pages)

    if total == 0:
        return []

    existing_topics = get_finding_topics(findings)
    all_types = get_all_schema_types(pages)
    existing_severities = {f.get("severity") for f in findings}

    # Helper: check if a topic is already covered
    def already_covered(*topic_keys) -> bool:
        for key in topic_keys:
            if any(key in t for _, t in existing_topics):
                return True
        return False

    recs = []
    pro_counter = 1

    def make_rec(title: str, category: str, rationale: str, priority: str) -> dict:
        nonlocal pro_counter
        r = {
            "id": f"PRO-{pro_counter:03d}",
            "title": title,
            "category": category,
            "rationale": rationale,
            "priority": priority
        }
        pro_counter += 1
        return r

    # --- PRO-001: FAQ/Q&A Content ---
    has_faq_page = any(url_matches_any(p.get("url") or p.get("final_url") or "", FAQ_URL_PATTERNS) for p in pages)
    has_faq_schema = "FAQPage" in all_types
    has_product_pages = any(url_matches_any(p.get("url") or p.get("final_url") or "", PRODUCT_URL_PATTERNS) for p in pages)
    if not has_faq_page and not has_faq_schema and has_product_pages:
        if not already_covered("faq"):
            recs.append(make_rec(
                "Add FAQ-style Q&A content to top landing pages",
                "discoverability",
                (
                    "The site has product/service pages but no FAQ content or FAQPage schema. "
                    "AI assistants frequently quote FAQ content verbatim in responses, making "
                    "this a high-ROI opportunity to increase citation frequency."
                ),
                "medium"
            ))

    # --- PRO-002: BreadcrumbList ---
    has_breadcrumb = "BreadcrumbList" in all_types
    deep_pages = [p for p in pages if len(urlparse(p.get("url") or p.get("final_url") or "").path.rstrip("/").split("/")) > 3]
    if not has_breadcrumb and deep_pages:
        if not already_covered("breadcrumb"):
            recs.append(make_rec(
                "Add BreadcrumbList structured data to reflect site hierarchy",
                "discoverability",
                (
                    f"{len(deep_pages)} crawled pages are at depth > 2, suggesting a hierarchical "
                    "structure, but no BreadcrumbList JSON-LD was found. Breadcrumbs help AI agents "
                    "understand content context and navigation paths."
                ),
                "low"
            ))

    # --- PRO-003: SearchAction / SiteLinksSearchBox ---
    has_search_action = any(
        isinstance(b, dict) and (b.get("@type") == "SearchAction" or
                                  "SearchAction" in str(b.get("potentialAction", "")))
        for p in pages for b in p.get("json_ld", [])
    )
    high_severity_jsonld_missing = any(
        "json-ld" in f.get("tags", []) and f.get("severity") in ("critical", "high")
        for f in findings
    )
    if total > 5 and not has_search_action and not high_severity_jsonld_missing:
        if not already_covered("search", "searchaction"):
            recs.append(make_rec(
                "Add SearchAction to WebSite schema for sitelinks search box",
                "discoverability",
                (
                    f"The site has {total} crawled pages but no SearchAction in WebSite JSON-LD. "
                    "This enables AI assistants and search engines to offer direct site search "
                    "from result panels."
                ),
                "low"
            ))

    # --- PRO-004: VideoObject ---
    video_pages = [
        p for p in pages
        if (text_contains_any(p.get("visible_text_sample", ""), VIDEO_KEYWORDS) or
            text_contains_any(p.get("title", ""), VIDEO_KEYWORDS))
    ]
    has_video_schema = "VideoObject" in all_types
    if video_pages and not has_video_schema:
        if not already_covered("video"):
            recs.append(make_rec(
                "Add VideoObject JSON-LD to pages featuring video content",
                "discoverability",
                (
                    f"{len(video_pages)} page(s) appear to feature video content based on text signals, "
                    "but no VideoObject schema was detected. VideoObject markup with transcript or "
                    "description dramatically increases AI discoverability of multimedia content."
                ),
                "medium"
            ))

    # --- PRO-005: HowTo ---
    how_to_pages = [
        p for p in pages
        if any(
            text_contains_any(h.get("text", ""), HOW_TO_KEYWORDS)
            for h in p.get("headings", [])
        )
    ]
    has_howto_schema = "HowTo" in all_types
    if how_to_pages and not has_howto_schema:
        if not already_covered("howto", "how-to"):
            recs.append(make_rec(
                "Add HowTo structured data to guide and tutorial pages",
                "discoverability",
                (
                    f"{len(how_to_pages)} page(s) have headings suggesting step-by-step guides, "
                    "but no HowTo JSON-LD was found. HowTo schema is among the highest-ROI types "
                    "for 'how do I' AI assistant queries."
                ),
                "medium"
            ))

    # --- PRO-006: Review/AggregateRating ---
    review_pages = [
        p for p in pages
        if (text_contains_any(p.get("visible_text_sample", ""), REVIEW_KEYWORDS) or
            url_matches_any(p.get("url") or p.get("final_url") or "", ["/review", "/testimonial", "/case-study"]))
    ]
    has_review_schema = bool({"Review", "AggregateRating"}.intersection(all_types))
    if review_pages and not has_review_schema and not high_severity_jsonld_missing:
        if not already_covered("review", "rating"):
            recs.append(make_rec(
                "Mark up reviews and testimonials with Review/AggregateRating schema",
                "discoverability",
                (
                    f"{len(review_pages)} page(s) appear to contain review or testimonial content, "
                    "but no Review or AggregateRating JSON-LD was found. Social proof in structured "
                    "form is a powerful AI trust signal."
                ),
                "medium"
            ))

    # --- PRO-007: Author expertise (E-E-A-T) ---
    blog_pages = [p for p in pages if url_matches_any(p.get("url") or p.get("final_url") or "", BLOG_URL_PATTERNS)]
    ent005_fired = any(f.get("check_id") == "ENT-005" for f in findings)
    if blog_pages and not ent005_fired:
        has_person_with_expertise = any(
            isinstance(b, dict) and b.get("@type") in ("Person",) and
            any(b.get(field) for field in ["jobTitle", "knowsAbout", "alumniOf"])
            for p in pages for b in p.get("json_ld", [])
        )
        if not has_person_with_expertise:
            if not already_covered("author"):
                recs.append(make_rec(
                    "Add expertise fields to author Person JSON-LD (jobTitle, knowsAbout)",
                    "discoverability",
                    (
                        f"The site has {len(blog_pages)} article/blog page(s) with author attribution, "
                        "but no Person JSON-LD includes expertise fields (jobTitle, knowsAbout, alumniOf). "
                        "AI agents use these to assess content authority and E-E-A-T signals."
                    ),
                    "medium"
                ))

    # --- PRO-008: hreflang / multilingual ---
    multilingual_pages = [
        p for p in pages if url_matches_any(p.get("url") or p.get("final_url") or "", MULTILINGUAL_PATTERNS)
    ]
    has_hreflang = any(
        any("hreflang" in str(lnk) for lnk in p.get("links", []))
        for p in pages
    )
    if len(multilingual_pages) > 3 and not has_hreflang:
        if not already_covered("hreflang"):
            recs.append(make_rec(
                "Add hreflang alternate links for multilingual content",
                "discoverability",
                (
                    f"{len(multilingual_pages)} pages appear to serve content in multiple languages, "
                    "but no hreflang attributes were detected. Without hreflang, AI assistants may "
                    "cite the wrong language version of content."
                ),
                "low"
            ))

    # --- PRO-009: Event schema ---
    event_pages = [
        p for p in pages
        if (p.get("page_type") == "Event" or
            text_contains_any(p.get("visible_text_sample", ""), EVENT_KEYWORDS) or
            url_matches_any(p.get("url") or p.get("final_url") or "", ["/event", "/conference", "/webinar", "/summit"]))
    ]
    has_event_schema = "Event" in all_types
    if event_pages and not has_event_schema:
        if not already_covered("event"):
            recs.append(make_rec(
                "Add Event structured data to event and webinar pages",
                "discoverability",
                (
                    f"{len(event_pages)} page(s) appear to feature events or webinars, but no Event "
                    "JSON-LD was found. Event schema is one of the highest-ROI structured data types — "
                    "AI assistants specifically surface upcoming events for brand queries."
                ),
                "high"
            ))

    # --- PRO-010: OpenGraph completeness ---
    og_incomplete_pages = [
        p for p in pages
        if not (p.get("open_graph", {}).get("og:title") and
                p.get("open_graph", {}).get("og:description") and
                p.get("open_graph", {}).get("og:image"))
    ]
    og_incomplete_ratio = len(og_incomplete_pages) / total
    if og_incomplete_ratio > 0.25 and not already_covered("og:", "opengraph"):
        recs.append(make_rec(
            "Complete OpenGraph tags for richer social sharing previews",
            "engagement",
            (
                f"{len(og_incomplete_pages)} of {total} pages ({og_incomplete_ratio*100:.0f}%) "
                "are missing og:title, og:description, or og:image. Complete OpenGraph tags "
                "improve how content appears when shared on social media and in AI-powered "
                "link previews, driving referral traffic."
            ),
            "low"
        ))

    return recs


def main():
    args = parse_args()

    try:
        snapshot = load_json(args.snapshot)
    except FileNotFoundError:
        print(f"[ERROR] Snapshot not found: {args.snapshot}", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"[ERROR] Invalid snapshot JSON: {e}", file=sys.stderr)
        sys.exit(1)

    try:
        findings_data = load_json(args.findings)
        if isinstance(findings_data, list):
            findings = findings_data
        elif isinstance(findings_data, dict):
            findings = findings_data.get("findings", [])
        else:
            findings = []
    except FileNotFoundError:
        print(f"[WARN] Findings file not found: {args.findings}; running with no prior findings.",
              file=sys.stderr)
        findings = []
    except json.JSONDecodeError as e:
        print(f"[WARN] Invalid findings JSON: {e}; running with no prior findings.", file=sys.stderr)
        findings = []

    recommendations = run_opportunities(snapshot, findings)

    output = {
        "skill": SKILL_NAME,
        "recommendations": recommendations
    }

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(
        f"[OK] {SKILL_NAME}: {len(recommendations)} recommendation(s) → {args.output}",
        file=sys.stderr
    )
    print(args.output)


if __name__ == "__main__":
    main()
