#!/usr/bin/env python3
"""
audit.py — structured-data-content-audit skill

Checks JSON-LD structured data quality and content extractability from snapshot.json.

Usage:
    python audit.py --snapshot snapshot.json --output structured_data_findings.json
"""

import argparse
import json
import sys
import re

from urllib.parse import urlparse

SKILL_NAME = "structured-data-content-audit"

PRODUCT_URL_PATTERNS = ["/product", "/item", "/shop", "/store", "/buy", "/pricing", "/plan"]
BLOG_URL_PATTERNS = ["/blog", "/article", "/news", "/post", "/insight"]
GENERIC_SCHEMA_TYPES = {"Thing", "CreativeWork", "Intangible"}
ORG_HOMEPAGE_TYPES = {
    "Organization", "WebSite", "LocalBusiness", "Corporation",
    "EducationalOrganization", "CollegeOrUniversity", "School",
    "HighSchool", "NewsMediaOrganization", "GovernmentOrganization",
    "NGO", "MedicalOrganization", "Event", "Project",
    "Restaurant", "FoodEstablishment", "CafeOrCoffeeShop", "Bakery", "BarOrPub",
    "Hospital", "MedicalClinic", "MedicalBusiness", "Physician",
    "Hotel", "LodgingBusiness", "Store", "FinancialService", "AutomotiveBusiness"
}


def is_org_homepage_type(t: str) -> bool:
    """Return True if type is Organization, WebSite, or any standard Organization/Entity subtype."""
    if not isinstance(t, str):
        return False
    return (
        t.endswith("Organization") or
        t.endswith("Business") or
        t.endswith("Establishment") or
        t in ORG_HOMEPAGE_TYPES
    )


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--snapshot", default="snapshot.json")
    p.add_argument("--output", default="structured_data_findings.json")
    return p.parse_args()


def load_snapshot(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def url_matches(url: str, patterns: list) -> bool:
    """Match pattern against URL path to avoid false positives on subdomains."""
    path = urlparse(url).path.lower()
    return any(p in path for p in patterns)


def get_schema_types(json_ld_blocks: list) -> set:
    """Extract all @type values from JSON-LD blocks (handles arrays and nested)."""
    types = set()
    for block in json_ld_blocks:
        if isinstance(block, dict):
            t = block.get("@type")
            if isinstance(t, str):
                types.add(t)
            elif isinstance(t, list):
                types.update(t)
            # Check @graph
            graph = block.get("@graph", [])
            if isinstance(graph, list):
                for node in graph:
                    if isinstance(node, dict):
                        nt = node.get("@type")
                        if isinstance(nt, str):
                            types.add(nt)
                        elif isinstance(nt, list):
                            types.update(nt)
    return types


def has_valid_jsonld(block: dict) -> bool:
    return bool(block.get("@type")) and bool(block.get("@context"))


def heading_has_gaps(headings: list) -> bool:
    """Return True if heading levels skip (e.g. H1 → H3)."""
    if not headings:
        return False
    prev = headings[0]["level"]
    for h in headings[1:]:
        if h["level"] > prev + 1:
            return True
        prev = h["level"]
    return False


def run_checks(snapshot: dict) -> tuple[list[dict], list[dict]]:
    meta = snapshot.get("crawl_meta", {})
    pages = snapshot.get("pages", [])
    findings = []
    strengths = []

    total = len(pages)
    if total == 0:
        return findings, strengths

    start_url = meta.get("start_url", "")

    # --- SDC-001: No JSON-LD on ANY page ---
    pages_with_jsonld = [p for p in pages if p.get("json_ld")]
    if not pages_with_jsonld:
        findings.append({
            "check_id": "SDC-001",
            "title": "No JSON-LD structured data on any crawled page",
            "category": "discoverability",
            "severity": "high",
            "confidence": "high",
            "affected_urls": [p["url"] for p in pages[:5]],
            "evidence": (
                f"Crawled {total} pages; 0/{total} contain JSON-LD structured data. "
                "AI assistants cannot extract machine-readable facts about this site."
            ),
            "tags": ["json-ld", "schema-org", "structured-data"],
            "suggested_action": {
                "summary": (
                    "Add schema.org JSON-LD to all pages, starting with Organization "
                    "and WebSite on the homepage, and Product/Article on content pages."
                ),
                "priority": "high",
                "effort": "medium"
            }
        })
    else:
        jsonld_ratio = len(pages_with_jsonld) / total
        if jsonld_ratio == 1.0:
            strengths.append({
                "title": "JSON-LD structured data present on all crawled pages",
                "category": "discoverability"
            })

    # --- SDC-002: No JSON-LD on product pages (Req 6, 23) ---
    product_pages = [
        p for p in pages
        if p.get("page_type") in ("Product", "Service", "Pricing") or
           (url_matches(p["url"], PRODUCT_URL_PATTERNS) and p.get("page_type") not in ("About", "Contact", "Careers", "Documentation", "Blog/article", "Homepage"))
    ]
    if product_pages:
        product_pages_no_jsonld = [p for p in product_pages if not p.get("json_ld")]
        if product_pages_no_jsonld:
            findings.append({
                "check_id": "SDC-002",
                "title": (
                    f"No structured data on {len(product_pages_no_jsonld)}/{len(product_pages)} "
                    "product/service pages"
                ),
                "category": "discoverability",
                "severity": "high",
                "confidence": "high",
                "affected_urls": [p["url"] for p in product_pages_no_jsonld[:5]],
                "evidence": (
                    f"{len(product_pages_no_jsonld)} of {len(product_pages)} product/service "
                    "pages contain no JSON-LD. AI cannot extract product details, prices, or specs."
                ),
                "tags": ["json-ld", "schema-org", "structured-data"],
                "suggested_action": {
                    "summary": "Add Product/Offer/Service JSON-LD to every product and service page.",
                    "priority": "high",
                    "effort": "medium"
                }
            })

    # --- SDC-003: Missing Organization or WebSite schema on homepage ---
    homepage = next(
        (p for p in pages if p["url"] == start_url or p.get("final_url") == start_url),
        pages[0] if pages else None
    )
    if homepage:
        hp_types = get_schema_types(homepage.get("json_ld", []))
        matched_org_types = [t for t in hp_types if is_org_homepage_type(t)]
        if not matched_org_types:
            findings.append({
                "check_id": "SDC-003",
                "title": "Missing Organization or WebSite schema on homepage",
                "category": "discoverability",
                "severity": "high",
                "confidence": "high",
                "affected_urls": [homepage["url"]],
                "evidence": (
                    f"Homepage ({homepage['url']}) has no JSON-LD with an Organization, "
                    f"WebSite, or brand entity type. Found types: {hp_types or 'none'}. "
                    "AI assistants cannot reliably identify and describe this brand."
                ),
                "tags": ["json-ld", "schema-org", "entity-identity"],
                "suggested_action": {
                    "summary": (
                        "Add Organization and WebSite JSON-LD to the homepage with name, "
                        "url, logo, description, and sameAs properties."
                    ),
                    "priority": "high",
                    "effort": "low"
                }
            })
        else:
            strengths.append({
                "title": f"Homepage has Organization/WebSite schema ({', '.join(matched_org_types)})",
                "category": "discoverability"
            })

    # --- SDC-004: Invalid JSON-LD blocks ---
    invalid_jsonld_pages = []
    for p in pages:
        for block in p.get("json_ld", []):
            if isinstance(block, dict) and not has_valid_jsonld(block):
                invalid_jsonld_pages.append(p)
                break
    if invalid_jsonld_pages:
        findings.append({
            "check_id": "SDC-004",
            "title": f"Invalid JSON-LD (missing @type or @context) on {len(invalid_jsonld_pages)} page(s)",
            "category": "discoverability",
            "severity": "medium",
            "confidence": "high",
            "affected_urls": [p["url"] for p in invalid_jsonld_pages[:5]],
            "evidence": (
                f"{len(invalid_jsonld_pages)} page(s) contain JSON-LD blocks missing @type "
                "or @context. These blocks are invalid and will be ignored by search engines."
            ),
            "tags": ["json-ld", "schema-org"],
            "suggested_action": {
                "summary": (
                    'Ensure every JSON-LD block includes both @context: "https://schema.org" '
                    "and a valid @type."
                ),
                "priority": "medium",
                "effort": "low"
            }
        })

    # --- SDC-005: Missing H1 on homepage ---
    if homepage and not homepage.get("h1"):
        findings.append({
            "check_id": "SDC-005",
            "title": "Homepage has no H1 heading",
            "category": "discoverability",
            "severity": "high",
            "confidence": "high",
            "affected_urls": [homepage["url"]],
            "evidence": f"Homepage ({homepage['url']}) has h1: []. No primary topic signal for crawlers.",
            "tags": ["heading-structure"],
            "suggested_action": {
                "summary": "Add a single, descriptive H1 to the homepage stating the brand name and value proposition.",
                "priority": "high",
                "effort": "low"
            }
        })

    # --- SDC-006: Multiple H1 on pages ---
    multi_h1_pages = [p for p in pages if len(p.get("h1", [])) > 1]
    multi_h1_ratio = len(multi_h1_pages) / total
    if multi_h1_ratio > 0.25:
        findings.append({
            "check_id": "SDC-006",
            "title": f"Multiple H1 tags on {len(multi_h1_pages)}/{total} pages",
            "category": "discoverability",
            "severity": "medium",
            "confidence": "high",
            "affected_urls": [p["url"] for p in multi_h1_pages[:5]],
            "evidence": (
                f"{len(multi_h1_pages)} of {total} pages have more than one H1 tag. "
                "Example: " + (
                    f"{multi_h1_pages[0]['url']} has H1s: {multi_h1_pages[0]['h1'][:3]}"
                    if multi_h1_pages else ""
                )
            ),
            "tags": ["heading-structure"],
            "suggested_action": {
                "summary": "Reduce each page to exactly one H1 as the primary topic identifier.",
                "priority": "medium",
                "effort": "low"
            }
        })

    # --- SDC-007: Heading hierarchy gaps ---
    gap_pages = [p for p in pages if heading_has_gaps(p.get("headings", []))]
    if gap_pages:
        findings.append({
            "check_id": "SDC-007",
            "title": f"Heading hierarchy gaps on {len(gap_pages)} page(s)",
            "category": "discoverability",
            "severity": "low",
            "confidence": "medium",
            "affected_urls": [p["url"] for p in gap_pages[:5]],
            "evidence": (
                f"{len(gap_pages)} page(s) skip heading levels (e.g. H1 → H3 without H2). "
                "Example: " + (
                    f"{gap_pages[0]['url']} headings: "
                    f"{['H' + str(h.get('level')) for h in gap_pages[0].get('headings', [])[:5]]}"
                    if gap_pages else ""
                )
            ),
            "tags": ["heading-structure"],
            "suggested_action": {
                "summary": "Maintain a logical H1 → H2 → H3 hierarchy on all pages.",
                "priority": "low",
                "effort": "low"
            }
        })

    # --- SDC-008: No JSON-LD on blog/article pages ---
    blog_pages = [p for p in pages if url_matches(p["url"], BLOG_URL_PATTERNS)]
    if blog_pages:
        blog_no_article_schema = []
        for p in blog_pages:
            types = get_schema_types(p.get("json_ld", []))
            if not types.intersection({"Article", "BlogPosting", "NewsArticle"}):
                blog_no_article_schema.append(p)
        if blog_no_article_schema:
            findings.append({
                "check_id": "SDC-008",
                "title": (
                    f"Missing Article schema on {len(blog_no_article_schema)}/{len(blog_pages)} "
                    "blog/article pages"
                ),
                "category": "discoverability",
                "severity": "medium",
                "confidence": "high",
                "affected_urls": [p["url"] for p in blog_no_article_schema[:5]],
                "evidence": (
                    f"{len(blog_no_article_schema)} blog/article pages lack Article or "
                    "BlogPosting JSON-LD. Authors and publication dates are not machine-readable."
                ),
                "tags": ["json-ld", "schema-org"],
                "suggested_action": {
                    "summary": "Add Article JSON-LD with headline, author, datePublished, dateModified.",
                    "priority": "medium",
                    "effort": "medium"
                }
            })

    # --- SDC-009: Sub-optimal schema types ---
    generic_type_pages = []
    for p in pages:
        types = get_schema_types(p.get("json_ld", []))
        generic_found = types.intersection(GENERIC_SCHEMA_TYPES)
        if generic_found:
            generic_type_pages.append((p, generic_found))
    if generic_type_pages:
        findings.append({
            "check_id": "SDC-009",
            "title": f"Over-generic schema.org types on {len(generic_type_pages)} page(s)",
            "category": "discoverability",
            "severity": "low",
            "confidence": "medium",
            "affected_urls": [p["url"] for p, _ in generic_type_pages[:5]],
            "evidence": (
                f"{len(generic_type_pages)} page(s) use generic types "
                f"({', '.join(set(t for _, ts in generic_type_pages for t in ts))}). "
                "These provide less semantic value than specific types."
            ),
            "tags": ["schema-org", "json-ld"],
            "suggested_action": {
                "summary": "Replace generic types (Thing, CreativeWork) with the most specific applicable schema.org type.",
                "priority": "low",
                "effort": "low"
            }
        })

    # --- SDC-201: Key facts locked in images ---
    all_images = [(img, p) for p in pages for img in p.get("images", [])]
    images_no_alt = [(img, p) for img, p in all_images if not img.get("alt")]
    problematic_pages = []
    for p in pages:
        imgs = p.get("images", [])
        imgs_no_alt = [i for i in imgs if not i.get("alt")]
        vt = p.get("visible_text_length", 9999)
        if len(imgs) > 5 and len(imgs_no_alt) > len(imgs) * 0.5 and vt < 500:
            problematic_pages.append(p)
    if problematic_pages:
        findings.append({
            "check_id": "SDC-201",
            "title": f"Key facts may be locked in images on {len(problematic_pages)} page(s)",
            "category": "discoverability",
            "severity": "high",
            "confidence": "medium",
            "affected_urls": [p["url"] for p in problematic_pages[:5]],
            "evidence": (
                f"{len(problematic_pages)} page(s) have >5 images with >50% missing alt text "
                "AND visible text < 500 characters, suggesting content is image-locked."
            ),
            "tags": ["alt-text", "extractability"],
            "suggested_action": {
                "summary": "Add alt text to all images; duplicate key facts as visible plain text.",
                "priority": "high",
                "effort": "medium"
            }
        })

    # --- SDC-202: Thin text on non-homepage content pages ---
    content_pages = [
        p for p in pages
        if p["url"] != start_url and p.get("visible_text_length", 9999) < 300
        and p.get("status_code", 200) == 200
    ]
    if content_pages and len(content_pages) / max(total - 1, 1) > 0.25:
        findings.append({
            "check_id": "SDC-202",
            "title": f"Thin content on {len(content_pages)} content page(s) (<300 characters)",
            "category": "discoverability",
            "severity": "medium",
            "confidence": "high",
            "affected_urls": [p["url"] for p in content_pages[:5]],
            "evidence": (
                f"{len(content_pages)} non-homepage pages have fewer than 300 visible "
                "characters. AI assistants have little extractable text to cite."
            ),
            "tags": ["thin-content", "extractability"],
            "suggested_action": {
                "summary": "Expand content pages with substantive plain text (aim for 300+ characters per page).",
                "priority": "medium",
                "effort": "high"
            }
        })

    # --- SDC-203: Missing alt text on images ---
    total_images = len(all_images)
    if total_images > 0:
        alt_missing_ratio = len(images_no_alt) / total_images
        if alt_missing_ratio > 0.5:
            pages_with_alt_issues = list({p["url"] for _, p in images_no_alt})
            findings.append({
                "check_id": "SDC-203",
                "title": f"Alt text missing on {len(images_no_alt)}/{total_images} images ({alt_missing_ratio*100:.0f}%)",
                "category": "discoverability",
                "severity": "medium",
                "confidence": "high",
                "affected_urls": pages_with_alt_issues[:5],
                "evidence": (
                    f"{len(images_no_alt)} of {total_images} images across {len(pages_with_alt_issues)} "
                    "page(s) have empty alt attributes. Image content is invisible to AI crawlers."
                ),
                "tags": ["alt-text"],
                "suggested_action": {
                    "summary": "Add descriptive alt text to all meaningful images.",
                    "priority": "medium",
                    "effort": "medium"
                }
            })
        elif alt_missing_ratio == 0:
            strengths.append({
                "title": "All images have alt text across crawled pages",
                "category": "discoverability"
            })

    # --- SDC-204: No text AND no JSON-LD on product pages ---
    no_content_product_pages = [
        p for p in product_pages
        if not p.get("json_ld") and p.get("visible_text_length", 9999) < 300
    ]
    if no_content_product_pages:
        findings.append({
            "check_id": "SDC-204",
            "title": (
                f"Product pages have neither structured data nor text content "
                f"({len(no_content_product_pages)} pages)"
            ),
            "category": "discoverability",
            "severity": "high",
            "confidence": "medium",
            "affected_urls": [p["url"] for p in no_content_product_pages[:5]],
            "evidence": (
                f"{len(no_content_product_pages)} product/service pages have <300 visible "
                "characters AND no JSON-LD. Both content extraction channels are absent."
            ),
            "tags": ["extractability", "json-ld", "thin-content"],
            "suggested_action": {
                "summary": "Add Product JSON-LD AND expand visible text on all product pages.",
                "priority": "high",
                "effort": "high"
            }
        })

    # --- SDC-205: No descriptive page titles ---
    short_title_pages = [p for p in pages if not p.get("title") or len(p.get("title", "")) < 10]
    short_title_ratio = len(short_title_pages) / total
    if short_title_ratio > 0.25:
        findings.append({
            "check_id": "SDC-205",
            "title": f"Short or missing page titles on {len(short_title_pages)}/{total} pages",
            "category": "discoverability",
            "severity": "medium",
            "confidence": "high",
            "affected_urls": [p["url"] for p in short_title_pages[:5]],
            "evidence": (
                f"{len(short_title_pages)} pages have titles shorter than 10 characters or empty. "
                f"Examples: {[p.get('title', '') for p in short_title_pages[:3]]}."
            ),
            "tags": ["page-title"],
            "suggested_action": {
                "summary": "Write unique, descriptive titles (40–60 characters) for every page.",
                "priority": "medium",
                "effort": "medium"
            }
        })

    # --- SDC-013: Conflict between visible price and structured data price (Req 6, 12) ---
    price_conflict_pages = []
    price_pattern = re.compile(r'[\$€£]\s*(\d+(?:\.\d{2})?)|\b(\d+(?:\.\d{2})?)\s*(?:USD|EUR|GBP)\b', re.IGNORECASE)
    for p in pages:
        # Extract structured data price
        ld_prices = []
        for block in p.get("json_ld", []):
            if isinstance(block, dict):
                offers = block.get("offers")
                if isinstance(offers, dict) and "price" in offers:
                    try:
                        ld_prices.append(float(str(offers["price"]).replace(",", "")))
                    except ValueError:
                        pass
                elif isinstance(offers, list):
                    for off in offers:
                        if isinstance(off, dict) and "price" in off:
                            try:
                                ld_prices.append(float(str(off["price"]).replace(",", "")))
                            except ValueError:
                                pass
        if not ld_prices:
            continue

        # Extract visible prices
        visible_text = p.get("visible_text_sample", "")
        matches = price_pattern.findall(visible_text)
        visible_prices = []
        for m in matches:
            val_str = m[0] or m[1]
            try:
                visible_prices.append(float(val_str))
            except ValueError:
                pass

        if visible_prices and ld_prices:
            if not any(abs(vp - lp) < 0.01 for vp in visible_prices for lp in ld_prices):
                price_conflict_pages.append((p, visible_prices[0], ld_prices[0]))

    if price_conflict_pages:
        findings.append({
            "check_id": "SDC-013",
            "title": f"Visible price conflicts with structured data price on {len(price_conflict_pages)} page(s)",
            "category": "discoverability",
            "severity": "high",
            "confidence": "high",
            "affected_urls": [p[0]["url"] for p in price_conflict_pages[:5]],
            "evidence": (
                f"Page {price_conflict_pages[0][0]['url']} displays visible price ${price_conflict_pages[0][1]} "
                f"but JSON-LD schema declares ${price_conflict_pages[0][2]}. "
                "Conflicting facts cause AI agents to hallucinate or distrust pricing data."
            ),
            "tags": ["json-ld", "price-conflict", "contradiction", "structured-data"],
            "suggested_action": {
                "summary": "Synchronize visible pricing numbers with JSON-LD schema offers.",
                "priority": "high",
                "effort": "low"
            }
        })

    # --- SDC-206: Boilerplate or placeholder page titles ---
    boilerplate_names = {"home", "untitled", "default title", "new page", "website", "index", "page 1", "document", "coming soon"}
    boilerplate_pages = []
    for p in pages:
        t = (p.get("title") or "").strip().lower()
        if t in boilerplate_names or t.startswith("untitled") or t.startswith("default title"):
            boilerplate_pages.append(p)
    if boilerplate_pages:
        sample_bp = [f"{p['url']} (title: \"{p.get('title')}\")" for p in boilerplate_pages[:3]]
        findings.append({
            "check_id": "SDC-206",
            "title": f"Boilerplate or generic page title on {len(boilerplate_pages)} page(s)",
            "category": "discoverability",
            "severity": "medium",
            "confidence": "high",
            "affected_urls": [p["url"] for p in boilerplate_pages[:5]],
            "evidence": (
                f"{len(boilerplate_pages)} page(s) use placeholder or boilerplate titles: "
                f"{', '.join(sample_bp)}. "
                "Generic titles prevent AI assistants from indexing distinct page topics."
            ),
            "tags": ["page-title", "heading-structure"],
            "suggested_action": {
                "summary": "Replace generic titles with distinct, descriptive titles containing brand and topic keywords.",
                "priority": "medium",
                "effort": "low"
            }
        })

    # --- SDC-207: Missing H1 on core inferred content pages ---
    core_content_types = {"Product", "Service", "Documentation", "Article", "About"}
    content_pages_no_h1 = [
        p for p in pages
        if p.get("page_type") in core_content_types and
        p["url"] != start_url and
        len(p.get("h1", [])) == 0 and
        p.get("visible_text_length", 0) >= 200
    ]
    if content_pages_no_h1:
        sample_h1 = [f"{p['url']} (type: {p.get('page_type')})" for p in content_pages_no_h1[:3]]
        findings.append({
            "check_id": "SDC-207",
            "title": f"Missing H1 heading on {len(content_pages_no_h1)} core content page(s)",
            "category": "discoverability",
            "severity": "medium",
            "confidence": "high",
            "affected_urls": [p["url"] for p in content_pages_no_h1[:5]],
            "evidence": (
                f"{len(content_pages_no_h1)} content page(s) lack an <h1> heading: "
                f"{', '.join(sample_h1)}. "
                "The H1 heading is the primary topic signal for AI content extraction."
            ),
            "tags": ["heading-structure", "h1-tag"],
            "suggested_action": {
                "summary": "Add a descriptive <h1> heading identifying the core topic or entity on each content page.",
                "priority": "medium",
                "effort": "low"
            }
        })

    # --- SDC-208: Incomplete core Schema.org entity declarations ---
    incomplete_schema_pages = []
    for p in pages:
        for block in p.get("json_ld", []):
            if not isinstance(block, dict):
                continue
            nodes = [block] + (block.get("@graph", []) if isinstance(block.get("@graph"), list) else [])
            for node in nodes:
                if not isinstance(node, dict):
                    continue
                nt = node.get("@type", "")
                nt_types = [nt] if isinstance(nt, str) else (nt if isinstance(nt, list) else [])
                # Organization
                if any(is_org_homepage_type(t) for t in nt_types):
                    if not node.get("name") and not node.get("legalName"):
                        incomplete_schema_pages.append((p, "Organization missing 'name'", node))
                        break
                # Product
                elif any("Product" in t for t in nt_types):
                    if not node.get("name"):
                        incomplete_schema_pages.append((p, "Product missing 'name'", node))
                        break
                    elif not node.get("offers") and not node.get("description"):
                        incomplete_schema_pages.append((p, "Product missing 'offers' or 'description'", node))
                        break
                # Article / BlogPosting
                elif any(t in ("Article", "BlogPosting", "NewsArticle") for t in nt_types):
                    if not node.get("headline"):
                        incomplete_schema_pages.append((p, "Article missing 'headline'", node))
                        break
                    elif not node.get("datePublished") and not node.get("dateModified"):
                        incomplete_schema_pages.append((p, "Article missing 'datePublished'", node))
                        break

    if incomplete_schema_pages:
        distinct_incomplete = list({item[0]["url"]: item for item in incomplete_schema_pages}.values())
        sample_incomplete = [f"{item[0]['url']} ({item[1]})" for item in distinct_incomplete[:3]]
        findings.append({
            "check_id": "SDC-208",
            "title": f"Incomplete Schema.org entity declarations on {len(distinct_incomplete)} page(s)",
            "category": "discoverability",
            "severity": "medium",
            "confidence": "high",
            "affected_urls": [item[0]["url"] for item in distinct_incomplete[:5]],
            "evidence": (
                f"{len(distinct_incomplete)} page(s) define Schema.org objects missing required properties: "
                f"{', '.join(sample_incomplete)}. "
                "Incomplete schema blocks prevent AI agents from fully structuring brand entities."
            ),
            "tags": ["json-ld", "schema-org", "structured-data"],
            "suggested_action": {
                "summary": "Populate essential schema properties (name, headline, offers, datePublished) for all declared types.",
                "priority": "medium",
                "effort": "low"
            }
        })

    # --- SDC-209: Semantic contradiction between Schema and visible heading ---
    # Guardrail: No rigid '0 word overlap' rule. Tokenize and normalize semantic entities.
    def extract_semantic_tokens(text: str) -> set[str]:
        stopwords = {"the", "and", "for", "with", "this", "that", "from", "our", "all", "your", "page", "home"}
        words = re.findall(r'[a-zA-Z]{3,}', text.lower())
        return {w for w in words if w not in stopwords}

    schema_conflicts = []
    for p in pages:
        h1_text = " ".join(p.get("h1", []))
        title_text = p.get("title", "")
        visible_tokens = extract_semantic_tokens(h1_text + " " + title_text)
        if not visible_tokens:
            continue

        for block in p.get("json_ld", []):
            if not isinstance(block, dict):
                continue
            nodes = [block] + (block.get("@graph", []) if isinstance(block.get("@graph"), list) else [])
            for node in nodes:
                if not isinstance(node, dict):
                    continue
                schema_name = node.get("name") or node.get("headline")
                if isinstance(schema_name, str) and len(schema_name.strip()) > 5:
                    schema_tokens = extract_semantic_tokens(schema_name)
                    # Only flag if schema_tokens has at least 2 distinct semantic tokens
                    # and none of them appear in visible tokens or visible text sample
                    if len(schema_tokens) >= 2:
                        overlap = schema_tokens & visible_tokens
                        sample_lower = p.get("visible_text_sample", "").lower()
                        in_sample = any(tok in sample_lower for tok in schema_tokens)
                        if not overlap and not in_sample:
                            schema_conflicts.append((p, schema_name, h1_text or title_text))
                            break

    if schema_conflicts:
        distinct_conflicts = list({item[0]["url"]: item for item in schema_conflicts}.values())
        target_item = distinct_conflicts[0]
        findings.append({
            "check_id": "SDC-209",
            "title": f"Semantic contradiction between Schema.org and visible headings on {len(distinct_conflicts)} page(s)",
            "category": "discoverability",
            "severity": "medium",
            "confidence": "high",
            "affected_urls": [item[0]["url"] for item in distinct_conflicts[:5]],
            "evidence": (
                f"Declared Schema.org entity name/headline contradicts visible page headings: "
                f"Page {target_item[0]['url']} declares schema entity '{target_item[1]}' "
                f"while visible heading is '{target_item[2]}'. "
                "Contradictory entity facts cause AI models to discount site reliability."
            ),
            "tags": ["schema-org", "trust", "contradiction", "structured-data"],
            "suggested_action": {
                "summary": "Ensure Schema.org entity names and headlines correspond to the actual on-page title and headings.",
                "priority": "medium",
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
