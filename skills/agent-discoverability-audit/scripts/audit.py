#!/usr/bin/env python3
"""
audit.py — agent-discoverability-audit skill

Phase 5: Marketplace / Agent Discoverability

Evaluates whether important website information is structured and exposed in a way
that makes it useful for AI agents, search systems, and marketplace-style discovery.

Checks:
  AGD-001 Important pages lack machine-readable summary metadata
  AGD-002 High-importance page not reachable from homepage link-graph
  AGD-003 Important pages missing agent-actionable structured data
  AGD-004 Missing sitemap or feed signal for bulk agent discovery
  AGD-005 Important pages have non-canonical URL patterns (query params, mixed case)
  AGD-006 Cluster isolation — related content pages not interlinked
  AGD-007 Thin agent-visible content on important page

All checks use page_importance_score to weight findings and focus on important pages.
The implementation is GENERIC and must NOT hardcode any specific domain, brand,
industry, CMS, schema type, or URL pattern beyond structural indicators.

Usage:
    python audit.py --snapshot snapshot.json --output agd_findings.json
"""

import argparse
import json
import re
import sys
from urllib.parse import urlparse, urlunparse, urlencode, parse_qs

SKILL_NAME = "agent-discoverability-audit"

# Importance threshold: pages at or above this are "important"
HIGH_IMPORTANCE_THRESHOLD = 60
# Very important pages (Homepage, key landing pages)
VERY_HIGH_IMPORTANCE_THRESHOLD = 80

# Page types that should always have rich structured data when present
STRUCTURED_DATA_EXPECTED_TYPES = {
    "Product", "Service", "Pricing", "Event", "Article",
    "Documentation", "Homepage", "Category"
}

# Page types where thin content is most problematic for agents
THIN_CONTENT_SENSITIVE_TYPES = {
    "Product", "Service", "Pricing", "Homepage", "Category", "Article"
}

# Minimum visible text for an agent to extract meaningful content
THIN_CONTENT_MIN_CHARS = 200

# Schema types that represent actionable machine-readable data
ACTIONABLE_SCHEMA_TYPES = {
    "Product", "Service", "SoftwareApplication", "Event", "Course",
    "JobPosting", "Recipe", "LocalBusiness", "Organization", "WebSite",
    "MedicalClinic", "MedicalBusiness", "Hospital", "Restaurant",
    "FoodEstablishment", "Store", "FinancialProduct", "EducationalOccupationalProgram",
    "Article", "NewsArticle", "BlogPosting", "TechArticle",
    "FAQPage", "HowTo", "BreadcrumbList", "ItemList"
}


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--snapshot", default="snapshot.json")
    p.add_argument("--output", default="agd_findings.json")
    return p.parse_args()


def load_snapshot(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def get_page_importance(page: dict) -> int:
    """Return page importance score (0-100), defaulting to 50."""
    return page.get("page_importance_score", 50)


def get_schema_types(page: dict) -> set:
    """Extract all @type values from a page's JSON-LD."""
    types = set()
    for block in page.get("json_ld", []):
        if not isinstance(block, dict):
            continue
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


def has_actionable_schema(page: dict) -> bool:
    """Return True if page has at least one actionable Schema.org type."""
    types = get_schema_types(page)
    return bool(types & ACTIONABLE_SCHEMA_TYPES)


def has_good_metadata(page: dict) -> bool:
    """Return True if page has title AND meta_description (agent-readable summary)."""
    title = (page.get("title") or "").strip()
    desc = (page.get("meta_description") or "").strip()
    return bool(title and len(title) > 5 and desc and len(desc) > 20)


def has_og_metadata(page: dict) -> bool:
    """Return True if page has og:title and og:description."""
    og = page.get("open_graph") or {}
    return bool(og.get("og:title") and og.get("og:description"))


def is_canonical_url(url: str) -> bool:
    """
    Return True if URL is in canonical form:
    - no query parameters that look like session/tracking params
    - no mixed-case path
    - no duplicate slashes
    """
    parsed = urlparse(url)
    path = parsed.path

    # Detect mixed case in path (e.g., /Products vs /products)
    if path != path.lower():
        return False

    # Detect session/tracking query parameters
    if parsed.query:
        qs = parse_qs(parsed.query)
        tracking_params = {
            "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
            "sessionid", "session_id", "sid", "phpsessid", "jsessionid",
            "ref", "referrer", "source", "campaign", "fbclid", "gclid", "msclkid",
            "_ga", "_gl", "affiliate", "cid", "pid"
        }
        if any(k.lower() in tracking_params for k in qs):
            return False

    # Detect double slashes in path
    if "//" in path:
        return False

    return True


def build_link_graph(pages: list) -> dict:
    """
    Build a mapping from page URL to set of internally linked URLs.
    """
    graph = {}
    url_set = {p.get("url") or p.get("final_url") or "" for p in pages}
    for page in pages:
        url = page.get("url") or page.get("final_url") or ""
        linked = set()
        for lnk in page.get("links", []):
            if not lnk.get("is_internal"):
                continue
            href = lnk.get("href", "")
            if href and href in url_set:
                linked.add(href)
        graph[url] = linked
    return graph


def reachable_from_homepage(homepage_url: str, target_url: str, graph: dict, max_hops: int = 3) -> bool:
    """
    BFS: can we reach target_url within max_hops from homepage?
    """
    if homepage_url == target_url:
        return True
    visited = {homepage_url}
    frontier = {homepage_url}
    for _ in range(max_hops):
        next_frontier = set()
        for node in frontier:
            neighbors = graph.get(node, set())
            for nb in neighbors:
                if nb == target_url:
                    return True
                if nb not in visited:
                    visited.add(nb)
                    next_frontier.add(nb)
        frontier = next_frontier
        if not frontier:
            break
    return False


def infer_content_cluster(page: dict) -> str | None:
    """
    Infer content cluster from URL path prefix (e.g. /blog, /docs, /products).
    Returns the first non-trivial path segment, or None.
    """
    path = urlparse(page.get("url", "")).path
    parts = [p for p in path.strip("/").split("/") if p and len(p) > 1]
    if len(parts) >= 2:
        return parts[0].lower()
    return None


def run_checks(snapshot: dict) -> tuple[list[dict], list[dict]]:
    if not isinstance(snapshot, dict):
        return [], []
    meta = snapshot.get("crawl_meta", {})
    pages = snapshot.get("pages", [])
    findings = []
    strengths = []

    total = len(pages)
    if total == 0:
        return findings, strengths

    start_url = meta.get("start_url", "")
    homepage = next(
        (p for p in pages if (p.get("url") or p.get("final_url") or "") == start_url),
        pages[0] if pages else None
    )

    important_pages = [p for p in pages if get_page_importance(p) >= HIGH_IMPORTANCE_THRESHOLD]
    very_important_pages = [p for p in pages if get_page_importance(p) >= VERY_HIGH_IMPORTANCE_THRESHOLD]

    # ─── AGD-001: Important pages lack machine-readable summary metadata ─────
    # An agent must be able to determine page relevance without rendering body text.
    # Important pages should have title + meta_description + (ideally) OG tags.
    metadata_poor = []
    for p in important_pages:
        if not has_good_metadata(p):
            metadata_poor.append(p)

    if metadata_poor:
        affected = [p.get("url") or p.get("final_url") or "" for p in sorted(metadata_poor, key=lambda x: -get_page_importance(x))[:5]]
        missing_details = []
        for p in metadata_poor[:3]:
            title = (p.get("title") or "").strip()
            desc = (p.get("meta_description") or "").strip()
            issues = []
            if not title or len(title) <= 5:
                issues.append("no title")
            if not desc or len(desc) <= 20:
                issues.append("no meta description")
            missing_details.append(f"{p.get('url') or p.get('final_url') or ''} ({', '.join(issues)})")

        findings.append({
            "check_id": "AGD-001",
            "title": f"Important pages lack machine-readable summary metadata ({len(metadata_poor)} page(s))",
            "category": "discoverability",
            "severity": "high",
            "confidence": "high",
            "affected_urls": affected,
            "evidence": (
                f"{len(metadata_poor)} of {len(important_pages)} important page(s) "
                f"(importance >= {HIGH_IMPORTANCE_THRESHOLD}) are missing title or meta description. "
                f"Sample: {'; '.join(missing_details[:2])}. "
                "AI agents use these signals to determine page relevance without full rendering."
            ),
            "tags": ["meta-description", "page-title", "machine-readable", "discoverability"],
            "suggested_action": {
                "summary": (
                    "Ensure every important page has a descriptive <title> (10-70 chars) "
                    "and <meta name='description'> (50-160 chars) capturing the page's core value."
                ),
                "priority": "high",
                "effort": "low"
            }
        })
    else:
        strengths.append({
            "title": "All important pages have title and meta description for agent readability",
            "category": "discoverability"
        })

    # ─── AGD-002: High-importance page not reachable from homepage ───────────
    # AI agents crawl by following links. Important pages must be reachable
    # within a reasonable number of hops from the site's canonical entry point.
    if homepage and len(pages) > 1:
        link_graph = build_link_graph(pages)
        hp_url = homepage.get("url") or homepage.get("final_url") or ""
        unreachable = []
        for p in very_important_pages:
            p_u = p.get("url") or p.get("final_url") or ""
            if p_u == hp_url:
                continue
            if not reachable_from_homepage(hp_url, p.get("url") or p.get("final_url") or "", link_graph, max_hops=3):
                unreachable.append(p)

        if unreachable:
            unreachable_sorted = sorted(unreachable, key=lambda x: -get_page_importance(x))
            findings.append({
                "check_id": "AGD-002",
                "title": f"High-importance page(s) not reachable from homepage within 3 hops ({len(unreachable)} page(s))",
                "category": "discoverability",
                "severity": "high",
                "confidence": "medium",
                "affected_urls": [p.get("url") or p.get("final_url") or "" for p in unreachable_sorted[:5]],
                "evidence": (
                    f"{len(unreachable)} page(s) with importance >= {VERY_HIGH_IMPORTANCE_THRESHOLD} "
                    f"cannot be reached from {hp_url} within 3 link hops. "
                    f"Examples: {', '.join(p.get('url') or p.get('final_url') or '' for p in unreachable_sorted[:2])}. "
                    "AI crawlers that start at the homepage will miss this content."
                ),
                "tags": ["internal-linking", "discoverability", "navigation", "indexability"],
                "suggested_action": {
                    "summary": (
                        "Ensure high-value pages are linked from the homepage or primary navigation. "
                        "Consider adding a sitemap and prominent internal links to key sections."
                    ),
                    "priority": "high",
                    "effort": "medium"
                }
            })
        elif very_important_pages:
            strengths.append({
                "title": "All high-importance pages are reachable from homepage within 3 hops",
                "category": "discoverability"
            })

    # ─── AGD-003: Important pages missing agent-actionable structured data ────
    # Important pages (Product, Service, Pricing, Event, Homepage, Category)
    # that have NO actionable JSON-LD schema are invisible to structured agents.
    schema_missing = []
    for p in important_pages:
        pt = p.get("page_type", "Other")
        if pt not in STRUCTURED_DATA_EXPECTED_TYPES:
            continue
        if not has_actionable_schema(p):
            schema_missing.append(p)

    if schema_missing:
        schema_sorted = sorted(schema_missing, key=lambda x: -get_page_importance(x))
        pt_counts = {}
        for p in schema_missing:
            pt = p.get("page_type", "Other")
            pt_counts[pt] = pt_counts.get(pt, 0) + 1
        pt_summary = ", ".join(f"{v} {k}" for k, v in sorted(pt_counts.items(), key=lambda x: -x[1]))

        findings.append({
            "check_id": "AGD-003",
            "title": f"Important pages missing agent-actionable structured data ({len(schema_missing)} page(s))",
            "category": "discoverability",
            "severity": "high",
            "confidence": "high",
            "affected_urls": [p.get("url") or p.get("final_url") or "" for p in schema_sorted[:5]],
            "evidence": (
                f"{len(schema_missing)} important page(s) of types that benefit from structured data "
                f"have no actionable JSON-LD: {pt_summary}. "
                "Without structured data, AI agents cannot reliably extract offers, schedules, or entity details."
            ),
            "tags": ["json-ld", "schema-org", "structured-data", "discoverability", "machine-readable"],
            "suggested_action": {
                "summary": (
                    "Add appropriate Schema.org JSON-LD to important pages: "
                    "Product/Offer on product pages, Event on event pages, "
                    "Organization/WebSite on the homepage. "
                    "Focus on pages with highest importance scores first."
                ),
                "priority": "high",
                "effort": "medium"
            }
        })
    elif any(p.get("page_type") in STRUCTURED_DATA_EXPECTED_TYPES for p in important_pages):
        strengths.append({
            "title": "Important content pages have actionable Schema.org structured data",
            "category": "discoverability"
        })

    # ─── AGD-004: Missing sitemap or feed signal for bulk agent discovery ────
    # AI systems that index at scale rely on sitemaps to discover content efficiently.
    # We check for sitemap signals in the snapshot meta and page links.
    has_sitemap_signal = False

    # Check crawl_meta for sitemap reference
    if meta.get("sitemap_url") or meta.get("has_sitemap"):
        has_sitemap_signal = True

    # Check robots.txt field in meta
    robots = meta.get("robots_txt", "") or ""
    if "sitemap:" in robots.lower():
        has_sitemap_signal = True

    # Check if any page URL or link references sitemap.xml
    for p in pages:
        if "sitemap" in (p.get("url") or "").lower():
            has_sitemap_signal = True
            break
        for lnk in (p.get("links") or []):
            href = lnk.get("href", "").lower()
            if "sitemap" in href or href.endswith(".xml"):
                has_sitemap_signal = True
                break
        if has_sitemap_signal:
            break

    # Only flag if site is large enough (>3 pages) to benefit from a sitemap
    if not has_sitemap_signal and total > 3:
        findings.append({
            "check_id": "AGD-004",
            "title": "No sitemap signal detected — bulk agent discovery may be impaired",
            "category": "discoverability",
            "severity": "medium",
            "confidence": "medium",
            "affected_urls": [start_url],
            "evidence": (
                f"No sitemap.xml reference found in robots.txt, crawl metadata, or any of "
                f"the {total} crawled pages. AI indexing systems rely on sitemaps for efficient "
                "bulk content discovery, especially for sites with many pages."
            ),
            "tags": ["discoverability", "crawlability", "indexability", "sitemap"],
            "suggested_action": {
                "summary": (
                    "Consider publishing an XML sitemap at /sitemap.xml and referencing it "
                    "in robots.txt (Sitemap: https://yourdomain.com/sitemap.xml). "
                    "Include all important pages with <lastmod> dates."
                ),
                "priority": "medium",
                "effort": "low"
            }
        })
    elif has_sitemap_signal:
        strengths.append({
            "title": "Sitemap signal detected — bulk agent discovery is supported",
            "category": "discoverability"
        })

    # ─── AGD-005: Important pages have non-canonical URL patterns ────────────
    # Mixed-case paths, tracking parameters in canonical URLs, or duplicate-slash
    # URLs create ambiguity for AI systems that deduplicate by URL.
    non_canonical = []
    for p in important_pages:
        url = p.get("url") or p.get("final_url") or ""
        if not is_canonical_url(url):
            non_canonical.append(p)

    if non_canonical:
        nc_sorted = sorted(non_canonical, key=lambda x: -get_page_importance(x))
        # Describe WHY each URL is non-canonical
        examples = []
        for p in nc_sorted[:3]:
            url = p.get("url") or p.get("final_url") or ""
            parsed = urlparse(url)
            reasons = []
            if parsed.path != parsed.path.lower():
                reasons.append("mixed-case path")
            if parsed.query:
                reasons.append("query parameters in canonical URL")
            if "//" in parsed.path:
                reasons.append("double slash in path")
            examples.append(f"{url} ({', '.join(reasons)})")

        findings.append({
            "check_id": "AGD-005",
            "title": f"Important pages have non-canonical URL patterns ({len(non_canonical)} page(s))",
            "category": "discoverability",
            "severity": "medium",
            "confidence": "high",
            "affected_urls": [p.get("url") or p.get("final_url") or "" for p in nc_sorted[:5]],
            "evidence": (
                f"{len(non_canonical)} important page(s) have non-canonical URL patterns: "
                f"{'; '.join(examples[:2])}. "
                "AI systems that deduplicate by URL may treat these as separate pages or fail to "
                "consolidate their authority."
            ),
            "tags": ["url-hygiene", "canonical-conflict", "discoverability", "indexability"],
            "suggested_action": {
                "summary": (
                    "Ensure all important page URLs use lowercase paths, no tracking parameters, "
                    "and no duplicate slashes. Add canonical <link> tags to consolidate authority "
                    "if multiple URL variants exist."
                ),
                "priority": "medium",
                "effort": "medium"
            }
        })
    elif important_pages:
        strengths.append({
            "title": "All important pages use canonical URL patterns",
            "category": "discoverability"
        })

    # ─── AGD-006: Cluster isolation — related content pages not interlinked ──
    # Content that belongs to the same section (e.g. /blog, /docs, /products)
    # should be interlinked. Isolated clusters reduce AI agent's ability to
    # discover related content and understand the site's content graph.
    # Only flag when there are at least 2 pages in a cluster.
    cluster_map: dict[str, list] = {}
    for p in pages:
        cluster = infer_content_cluster(p)
        if cluster:
            cluster_map.setdefault(cluster, []).append(p)

    isolated_clusters = []
    for cluster, cluster_pages in cluster_map.items():
        if len(cluster_pages) < 2:
            continue
        # Check what fraction of cluster pages have internal links to other cluster pages
        cluster_urls = {p.get("url") or p.get("final_url") or "" for p in cluster_pages}
        unlinked = []
        for p in cluster_pages:
            imp = get_page_importance(p)
            if imp < HIGH_IMPORTANCE_THRESHOLD:
                continue
            outbound_cluster_links = sum(
                1 for lnk in (p.get("links") or [])
                if lnk.get("is_internal") and lnk.get("href") in cluster_urls
            )
            if outbound_cluster_links == 0:
                unlinked.append(p)
        # Only flag if a meaningful fraction of important cluster pages are isolated
        important_in_cluster = [p for p in cluster_pages if get_page_importance(p) >= HIGH_IMPORTANCE_THRESHOLD]
        if not important_in_cluster:
            continue
        isolated_ratio = len(unlinked) / len(important_in_cluster)
        if isolated_ratio > 0.5 and len(unlinked) >= 2:
            isolated_clusters.append({
                "cluster": cluster,
                "total_pages": len(cluster_pages),
                "unlinked_important": len(unlinked),
                "urls": [p.get("url") or p.get("final_url") or "" for p in unlinked[:3]]
            })

    if isolated_clusters:
        all_affected = []
        cluster_summaries = []
        for ic in isolated_clusters[:3]:
            all_affected.extend(ic["urls"])
            cluster_summaries.append(
                f"/{ic['cluster']} ({ic['unlinked_important']} of {ic['total_pages']} pages unlinked)"
            )

        findings.append({
            "check_id": "AGD-006",
            "title": f"Content cluster isolation — related pages not interlinked ({len(isolated_clusters)} cluster(s))",
            "category": "discoverability",
            "severity": "medium",
            "confidence": "medium",
            "affected_urls": list(dict.fromkeys(all_affected))[:5],
            "evidence": (
                f"{len(isolated_clusters)} content cluster(s) have important pages with no "
                f"internal links to sibling pages in the same section: "
                f"{'; '.join(cluster_summaries)}. "
                "AI agents use internal links to discover related content and map content relationships."
            ),
            "tags": ["internal-linking", "discoverability", "navigation"],
            "suggested_action": {
                "summary": (
                    "Add 'related content' or 'next/previous' links within each content section. "
                    "Consider adding index or category pages that link to all items in a cluster."
                ),
                "priority": "medium",
                "effort": "medium"
            }
        })

    # ─── AGD-007: Thin agent-visible content on important page ───────────────
    # An important page with very little visible text offers little value to AI
    # agents even if it has metadata. The agent cannot verify the metadata claims.
    thin_important = []
    for p in important_pages:
        pt = p.get("page_type", "Other")
        if pt not in THIN_CONTENT_SENSITIVE_TYPES:
            continue
        vis_len = p.get("visible_text_length", 9999)
        if vis_len < THIN_CONTENT_MIN_CHARS:
            thin_important.append(p)

    if thin_important:
        thin_sorted = sorted(thin_important, key=lambda x: -get_page_importance(x))
        findings.append({
            "check_id": "AGD-007",
            "title": f"Thin agent-visible content on important page(s) ({len(thin_important)} page(s))",
            "category": "discoverability",
            "severity": "medium",
            "confidence": "medium",
            "affected_urls": [p.get("url") or p.get("final_url") or "" for p in thin_sorted[:5]],
            "evidence": (
                f"{len(thin_important)} important page(s) of content-rich types "
                f"({', '.join(set(p.get('page_type', 'Other') for p in thin_important))}) "
                f"have fewer than {THIN_CONTENT_MIN_CHARS} visible characters. "
                "AI agents cannot validate or expand on metadata claims without substantive body text."
            ),
            "tags": ["thin-content", "extractability", "machine-readable", "discoverability"],
            "suggested_action": {
                "summary": (
                    "Ensure important content pages have at least 200 words of visible, "
                    "substantive text describing the entity, offer, or topic. "
                    "AI agents use visible content to corroborate structured data and extract facts."
                ),
                "priority": "medium",
                "effort": "medium"
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
