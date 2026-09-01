#!/usr/bin/env python3
"""
audit.py — freshness-corroboration-audit skill

Checks date signals, stale content, and internal fact contradictions from snapshot.json.

Usage:
    python audit.py --snapshot snapshot.json --output freshness_findings.json \
                    --stale-threshold-days 365
"""

import argparse
import json
import re
import sys
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime

SKILL_NAME = "freshness-corroboration-audit"

# Patterns for detecting dates in visible text (for contradiction detection)
YEAR_PATTERN = re.compile(r'\b(19|20)\d{2}\b')
FOUNDED_PATTERN = re.compile(r'\b(?:founded|established|since|est\.?)\s+(?:in\s+)?((?:19|20)\d{2})\b', re.IGNORECASE)
EMPLOYEE_PATTERN = re.compile(r'\b(\d[\d,]+)\s+(?:employees|team members|staff|people)\b', re.IGNORECASE)
PRICE_PATTERN = re.compile(r'(?:USD|EUR|GBP|\$|€|£)\s*(\d[\d,]*(?:\.\d{2})?)', re.IGNORECASE)


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--snapshot", default="snapshot.json")
    p.add_argument("--output", default="freshness_findings.json")
    p.add_argument("--stale-threshold-days", type=int, default=365)
    return p.parse_args()


def load_snapshot(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def parse_date_str(date_str: str | None) -> datetime | None:
    """Try to parse a date string from various formats."""
    if not date_str:
        return None
    # Try HTTP date format
    try:
        return parsedate_to_datetime(date_str).replace(tzinfo=timezone.utc)
    except Exception:
        pass
    # Try ISO 8601
    for fmt in ["%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S%z",
                "%Y-%m-%d", "%Y/%m/%d", "%d/%m/%Y", "%B %d, %Y"]:
        try:
            dt = datetime.strptime(date_str[:len(fmt)], fmt)
            return dt.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def get_jsonld_date(json_ld_blocks: list, field: str) -> str | None:
    """Extract a date field from JSON-LD blocks."""
    for block in json_ld_blocks:
        if isinstance(block, dict):
            if block.get(field):
                return block[field]
            for node in block.get("@graph", []):
                if isinstance(node, dict) and node.get(field):
                    return node[field]
    return None


def run_checks(snapshot: dict, stale_threshold_days: int = 365) -> tuple[list[dict], list[dict]]:
    meta = snapshot.get("crawl_meta", {})
    pages = snapshot.get("pages", [])
    findings = []
    strengths = []
    total = len(pages)

    if total == 0:
        return findings, strengths

    start_url = meta.get("start_url", "")
    now = datetime.now(timezone.utc)
    stale_cutoff = now - timedelta(days=stale_threshold_days)

    # Collect date info for all pages
    page_dates = []  # (page, datetime | None, source)
    for p in pages:
        dt = None
        source = None
        # Try last_modified header/meta
        lm = p.get("last_modified")
        if lm:
            dt = parse_date_str(lm)
            if dt:
                source = "last_modified"
        # Try JSON-LD dateModified / datePublished
        if not dt:
            jsonld_date = (
                get_jsonld_date(p.get("json_ld", []), "dateModified") or
                get_jsonld_date(p.get("json_ld", []), "datePublished")
            )
            if jsonld_date:
                dt = parse_date_str(jsonld_date)
                if dt:
                    source = "json-ld"
        page_dates.append((p, dt, source))

    pages_with_dates = [(p, dt, src) for p, dt, src in page_dates if dt]
    pages_without_dates = [(p, dt, src) for p, dt, src in page_dates if dt is None]

    # --- FRS-001: No date signals on any page ---
    if not pages_with_dates:
        findings.append({
            "check_id": "FRS-001",
            "title": "No date signals found on any crawled page",
            "category": "discoverability",
            "severity": "high",
            "confidence": "high",
            "affected_urls": [p["url"] for p in pages[:5]],
            "evidence": (
                f"Checked {total} pages: no Last-Modified headers, no datePublished, "
                "and no dateModified in any JSON-LD block. AI assistants cannot assess content currency."
            ),
            "tags": ["stale-content"],
            "suggested_action": {
                "summary": "Add Last-Modified headers and datePublished/dateModified to JSON-LD on all content pages.",
                "priority": "high",
                "effort": "medium"
            }
        })
    else:
        # --- FRS-002: Stale content ---
        stale_pages = [(p, dt, src) for p, dt, src in pages_with_dates if dt < stale_cutoff]
        stale_ratio = len(stale_pages) / len(pages_with_dates)
        if stale_ratio > 0.30:
            oldest = min(pages_with_dates, key=lambda x: x[1])
            findings.append({
                "check_id": "FRS-002",
                "title": f"Stale content on {len(stale_pages)}/{len(pages_with_dates)} pages with dates (>{stale_threshold_days} days old)",
                "category": "discoverability",
                "severity": "high",
                "confidence": "medium",
                "affected_urls": [p["url"] for p, _, _ in stale_pages[:5]],
                "evidence": (
                    f"{len(stale_pages)} of {len(pages_with_dates)} pages with date signals "
                    f"({stale_ratio*100:.0f}%) are older than {stale_threshold_days} days. "
                    f"Oldest page: {oldest[0]['url']} ({oldest[1].date()})."
                ),
                "tags": ["stale-content"],
                "suggested_action": {
                    "summary": "Update high-priority pages; establish a content review cycle.",
                    "priority": "high",
                    "effort": "high"
                }
            })
        else:
            strengths.append({
                "title": "Content appears fresh (recent modification dates)",
                "category": "discoverability"
            })

        # Date completeness strength
        if len(pages_with_dates) == total:
            strengths.append({
                "title": "All crawled pages have date signals",
                "category": "discoverability"
            })

    # --- FRS-003: Internally contradicting facts ---
    founded_years = {}  # page_url -> set of years
    for p in pages:
        sample = p.get("visible_text_sample", "") or ""
        matches = FOUNDED_PATTERN.findall(sample)
        if matches:
            founded_years[p["url"]] = set(matches)

    # Check for contradictions across pages
    all_found_years = set()
    for years in founded_years.values():
        all_found_years.update(years)
    if len(all_found_years) > 1:
        conflict_pages = [url for url, years in founded_years.items() if years]
        findings.append({
            "check_id": "FRS-003",
            "title": "Contradicting founding/establishment years across pages",
            "category": "discoverability",
            "severity": "medium",
            "confidence": "low",
            "affected_urls": conflict_pages[:5],
            "evidence": (
                f"Different founding years detected across pages: {sorted(all_found_years)}. "
                f"Affecting {len(conflict_pages)} pages. Contradicting facts undermine AI trust."
            ),
            "tags": ["stale-content"],
            "suggested_action": {
                "summary": "Reconcile contradicting facts across pages; use JSON-LD foundingDate as canonical source.",
                "priority": "medium",
                "effort": "medium"
            }
        })

    # --- FRS-004: Missing datePublished/dateModified in Article JSON-LD ---
    article_types = {"Article", "BlogPosting", "NewsArticle", "TechArticle"}
    article_pages_missing_dates = []
    for p in pages:
        for block in p.get("json_ld", []):
            if not isinstance(block, dict):
                continue
            t = block.get("@type", "")
            types = [t] if isinstance(t, str) else (t if isinstance(t, list) else [])
            if any(at in article_types for at in types):
                if not block.get("datePublished") and not block.get("dateModified"):
                    article_pages_missing_dates.append(p)
                    break
    if article_pages_missing_dates:
        findings.append({
            "check_id": "FRS-004",
            "title": f"Article JSON-LD missing datePublished/dateModified on {len(article_pages_missing_dates)} page(s)",
            "category": "discoverability",
            "severity": "medium",
            "confidence": "high",
            "affected_urls": [p["url"] for p in article_pages_missing_dates[:5]],
            "evidence": (
                f"{len(article_pages_missing_dates)} page(s) have Article/BlogPosting JSON-LD "
                "but no datePublished or dateModified. AI cannot assess content currency."
            ),
            "tags": ["stale-content", "schema-org"],
            "suggested_action": {
                "summary": "Add datePublished and dateModified to all Article JSON-LD blocks.",
                "priority": "medium",
                "effort": "low"
            }
        })
    else:
        # Only report strength if there were article pages to check
        article_pages_any = [
            p for p in pages
            if any(
                any(at in article_types for at in (
                    [b.get("@type")] if isinstance(b.get("@type"), str) else (b.get("@type") or [])
                    if isinstance(b, dict) else []
                ))
                for b in p.get("json_ld", [])
            )
        ]
        if article_pages_any:
            strengths.append({
                "title": "Article pages have datePublished in JSON-LD",
                "category": "discoverability"
            })

    # --- FRS-005: Inconsistent date signals ---
    inconsistent_date_pages = []
    for p in pages:
        lm = p.get("last_modified")
        jsonld_date_str = (
            get_jsonld_date(p.get("json_ld", []), "dateModified") or
            get_jsonld_date(p.get("json_ld", []), "datePublished")
        )
        if lm and jsonld_date_str:
            lm_dt = parse_date_str(lm)
            jld_dt = parse_date_str(jsonld_date_str)
            if lm_dt and jld_dt:
                diff = abs((lm_dt - jld_dt).days)
                if diff > 30:
                    inconsistent_date_pages.append((p, lm_dt, jld_dt))

    if inconsistent_date_pages:
        findings.append({
            "check_id": "FRS-005",
            "title": f"Inconsistent date signals on {len(inconsistent_date_pages)} page(s)",
            "category": "discoverability",
            "severity": "low",
            "confidence": "medium",
            "affected_urls": [p["url"] for p, _, _ in inconsistent_date_pages[:5]],
            "evidence": (
                f"{len(inconsistent_date_pages)} page(s) have Last-Modified headers and JSON-LD "
                "dates that differ by more than 30 days. Example: "
                f"{inconsistent_date_pages[0][0]['url']} — HTTP: {inconsistent_date_pages[0][1].date()}, "
                f"JSON-LD: {inconsistent_date_pages[0][2].date()}."
            ),
            "tags": ["stale-content"],
            "suggested_action": {
                "summary": "Synchronise Last-Modified headers with dateModified in JSON-LD.",
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

    findings, strengths = run_checks(snapshot, args.stale_threshold_days)
    output = {"skill": SKILL_NAME, "findings": findings, "strengths": strengths}

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"[OK] {SKILL_NAME}: {len(findings)} finding(s), {len(strengths)} strength(s) → {args.output}",
          file=sys.stderr)
    print(args.output)


if __name__ == "__main__":
    main()
