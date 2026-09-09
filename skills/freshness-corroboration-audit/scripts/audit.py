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
PRICE_PATTERN = re.compile(r'(?:USD|EUR|GBP|\$|€|£)\s*(\d[\d,]*(?:\.\d{2})?)|\b(\d[\d,]*(?:\.\d{2})?)\s*(?:USD|EUR|GBP)\b', re.IGNORECASE)
VISIBLE_DATE_PATTERN = re.compile(
    r'\b(?:last\s+updated|updated\s+on|published\s+on|last\s+modified|date\s+published)\s*:?\s*'
    r'([A-Za-z]+\s+\d{1,2},?\s+\d{4}|\d{4}-\d{2}-\d{2})\b',
    re.IGNORECASE
)


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
    s = str(date_str).strip()
    for fmt in [
        "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d", "%Y/%m/%d", "%d/%m/%Y", "%B %d, %Y", "%b %d, %Y"
    ]:
        try:
            dt = datetime.strptime(s, fmt)
            return dt.replace(tzinfo=timezone.utc)
        except ValueError:
            pass
        if len(s) >= 10:
            try:
                dt = datetime.strptime(s[:10], fmt)
                return dt.replace(tzinfo=timezone.utc)
            except ValueError:
                pass
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
    if not isinstance(snapshot, dict):
        return [], []
    meta = snapshot.get("crawl_meta") or {}
    pages = [p for p in (snapshot.get("pages") or []) if isinstance(p, dict)]
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
                get_jsonld_date((p.get("json_ld") or []), "dateModified") or
                get_jsonld_date((p.get("json_ld") or []), "datePublished")
            )
            if jsonld_date:
                dt = parse_date_str(jsonld_date)
                if dt:
                    source = "json-ld"
        # Try visible date in text sample
        if not dt:
            sample = p.get("visible_text_sample", "")
            vm = VISIBLE_DATE_PATTERN.search(sample)
            if vm:
                dt = parse_date_str(vm.group(1))
                if dt:
                    source = "visible_text"
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
            "affected_urls": [p.get("url") or p.get("final_url") or "" for p in pages[:5]],
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
        # --- FRS-002: Stale content (Req 8, 23) ---
        # Differentiate time-sensitive pages (Pricing, Product, Service) from evergreen (Docs, About)
        time_sensitive_types = {"Pricing", "Product", "Service", "Event"}
        evergreen_types = {"About", "Documentation", "Careers"}

        stale_time_sensitive = []
        stale_evergreen = []

        for p, dt, src in pages_with_dates:
            ptype = p.get("page_type", "Other/unknown")
            if dt < stale_cutoff:
                p_url_lower = (p.get("url") or p.get("final_url") or "").lower()
                if ptype in time_sensitive_types or any(k in p_url_lower for k in ("/pricing", "/product", "/shop")):
                    stale_time_sensitive.append((p, dt, src))
                elif ptype in evergreen_types or "/docs" in p_url_lower or "/about" in p_url_lower:
                    # Only flag evergreen if older than 3 years
                    if dt < (now - timedelta(days=1095)):
                        stale_evergreen.append((p, dt, src))
                else:
                    stale_time_sensitive.append((p, dt, src))

        stale_pages = stale_time_sensitive + stale_evergreen
        stale_ratio = len(stale_pages) / len(pages_with_dates)

        if len(stale_time_sensitive) > 0 and stale_ratio > 0.30:
            oldest = min(pages_with_dates, key=lambda x: x[1])
            findings.append({
                "check_id": "FRS-002",
                "title": f"Stale time-sensitive content on {len(stale_time_sensitive)}/{len(pages_with_dates)} pages (>{stale_threshold_days} days old)",
                "category": "discoverability",
                "severity": "high",
                "confidence": "high",
                "affected_urls": [p.get("url") or p.get("final_url") or "" for p, _, _ in stale_time_sensitive[:5]],
                "evidence": (
                    f"{len(stale_time_sensitive)} of {len(pages_with_dates)} pages with date signals "
                    f"contain stale time-sensitive content (older than {stale_threshold_days} days). "
                    f"Oldest page: {oldest[0].get('url', '')} ({oldest[1].date()})."
                ),
                "tags": ["stale-content", "freshness"],
                "suggested_action": {
                    "summary": "Review and update time-sensitive pricing, product, and policy pages.",
                    "priority": "high",
                    "effort": "medium"
                }
            })
        elif len(stale_evergreen) > 0:
            findings.append({
                "check_id": "FRS-002",
                "title": f"Archived or aged evergreen documentation ({len(stale_evergreen)} pages >3 years old)",
                "category": "discoverability",
                "severity": "low",
                "confidence": "medium",
                "affected_urls": [p.get("url") or p.get("final_url") or "" for p, _, _ in stale_evergreen[:5]],
                "evidence": (
                    f"{len(stale_evergreen)} evergreen/doc page(s) have not been refreshed in >3 years. "
                    "Confirm if technical details remain accurate for AI agents."
                ),
                "tags": ["stale-content", "evergreen"],
                "suggested_action": {
                    "summary": "Review long-standing documentation for technical accuracy.",
                    "priority": "low",
                    "effort": "low"
                }
            })
        else:
            strengths.append({
                "title": "Content appears fresh (recent modification dates on time-sensitive pages)",
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
            founded_years[p.get("url") or p.get("final_url") or ""] = set(matches)

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
        for block in (p.get("json_ld") or []):
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
            "affected_urls": [p.get("url") or p.get("final_url") or "" for p in article_pages_missing_dates[:5]],
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
                for b in (p.get("json_ld") or [])
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
            get_jsonld_date((p.get("json_ld") or []), "dateModified") or
            get_jsonld_date((p.get("json_ld") or []), "datePublished")
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
            "affected_urls": [p.get("url") or p.get("final_url") or "" for p, _, _ in inconsistent_date_pages[:5]],
            "evidence": (
                f"{len(inconsistent_date_pages)} page(s) have Last-Modified headers and JSON-LD "
                "dates that differ by more than 30 days. Example: "
                f"{inconsistent_date_pages[0][0].get('url', '')} — HTTP: {inconsistent_date_pages[0][1].date()}, "
                f"JSON-LD: {inconsistent_date_pages[0][2].date()}."
            ),
            "tags": ["stale-content"],
            "suggested_action": {
                "summary": "Synchronise Last-Modified headers with dateModified in JSON-LD.",
                "priority": "low",
                "effort": "low"
            }
        })

    # --- FRS-006: Cross-page pricing corroboration & contradiction ---
    page_pricing = {}
    for p in pages:
        u = p.get("url") or p.get("final_url") or ""
        h1_text = " ".join((p.get("h1") or []))
        title_text = p.get("title", "")
        sample = p.get("visible_text_sample", "")

        for block in (p.get("json_ld") or []):
            if isinstance(block, dict):
                p_name = block.get("name") or h1_text or title_text
                offers = block.get("offers")
                if isinstance(offers, dict) and "price" in offers:
                    try:
                        page_pricing.setdefault(u, []).append((p_name.strip(), float(str(offers["price"]).replace(",", ""))))
                    except (ValueError, TypeError):
                        pass

        vis_matches = PRICE_PATTERN.findall(sample)
        for vm in vis_matches:
            val_str = vm[0] or vm[1]
            try:
                val = float(val_str.replace(",", ""))
                name_cand = h1_text or title_text or "Product"
                page_pricing.setdefault(u, []).append((name_cand.strip(), val))
            except (ValueError, TypeError):
                pass

    price_conflicts = []
    corroborated_prices = []
    checked_pairs = set()

    for u1, items1 in page_pricing.items():
        for u2, items2 in page_pricing.items():
            if u1 >= u2:
                continue
            pair_key = (u1, u2)
            if pair_key in checked_pairs:
                continue
            checked_pairs.add(pair_key)

            for name1, p1 in items1:
                for name2, p2 in items2:
                    words1 = set(re.findall(r'\w{3,}', name1.lower()))
                    words2 = set(re.findall(r'\w{3,}', name2.lower()))
                    name_overlap = bool(words1 & words2) if (words1 and words2) else False

                    if (name_overlap or len(items1) == 1 == len(items2)) and abs(p1 - p2) >= 1.0:
                        price_conflicts.append((u1, u2, name1 or name2, p1, p2))
                        break
                    elif (name_overlap or len(items1) == 1 == len(items2)) and abs(p1 - p2) < 0.01:
                        corroborated_prices.append((u1, u2, p1))

    if price_conflicts:
        c_u1, c_u2, c_name, cp1, cp2 = price_conflicts[0]
        distinct_urls = sorted({u for item in price_conflicts for u in (item[0], item[1]) if u})
        findings.append({
            "check_id": "FRS-006",
            "title": f"Conflicting pricing information detected across {len(distinct_urls)} crawled pages",
            "category": "discoverability",
            "severity": "high",
            "confidence": "high",
            "affected_urls": distinct_urls[:5],
            "evidence": (
                f"Contradicting price figures discovered: {c_u1} declares ${cp1} while {c_u2} declares ${cp2} for '{c_name}'. "
                "Discrepancies in published pricing confuse AI assistants and undermine transactional trust."
            ),
            "tags": ["pricing", "corroboration", "contradiction"],
            "suggested_action": {
                "summary": "Reconcile product pricing across product pages, pricing tables, and structured data.",
                "priority": "high",
                "effort": "low"
            }
        })
    elif corroborated_prices:
        strengths.append({
            "title": "Pricing information corroborated across multiple crawled pages",
            "category": "discoverability"
        })

    # --- FRS-007: Event schedule corroboration & contradiction ---
    month_names = r'(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)'
    event_date_re = re.compile(
        rf'\b(\d{{4}}-\d{{2}}-\d{{2}})\b|\b({month_names}\s+\d{{1,2}},?\s+\d{{4}})\b|\b(\d{{1,2}}\s+{month_names}\s+\d{{4}})\b',
        re.IGNORECASE
    )
    event_declarations = []  # list of (url, source_label, event_name, date_str, parsed_dt)

    for p in pages:
        u = p.get("url") or p.get("final_url") or ""
        h1_text = " ".join((p.get("h1") or []))
        title_text = p.get("title", "")
        ename = h1_text or title_text or "Event"

        for block in (p.get("json_ld") or []):
            if isinstance(block, dict):
                t = block.get("@type", "")
                types = [t] if isinstance(t, str) else (t if isinstance(t, list) else [])
                if any("Event" in item for item in types):
                    sd = block.get("startDate")
                    if isinstance(sd, str) and sd.strip():
                        bname = block.get("name") or ename
                        p_dt = parse_date_str(sd)
                        event_declarations.append((u, "JSON-LD", bname, sd.strip(), p_dt))

        if p.get("page_type") == "Event" or "/event" in u.lower():
            sample = p.get("visible_text_sample", "")
            d_matches = event_date_re.finditer(sample)
            for dm in d_matches:
                d_val = dm.group(1) or dm.group(2) or dm.group(3)
                if d_val:
                    clean_d = d_val.strip()
                    p_dt = parse_date_str(clean_d)
                    event_declarations.append((u, "Visible Announcement", ename, clean_d, p_dt))

    event_conflicts = []
    event_matches = []
    checked_pairs = set()

    for i in range(len(event_declarations)):
        for j in range(i + 1, len(event_declarations)):
            u1, src1, name1, d1, dt1 = event_declarations[i]
            u2, src2, name2, d2, dt2 = event_declarations[j]

            if u1 == u2 and src1 == src2:
                continue

            pair_key = (min(u1 + src1 + d1, u2 + src2 + d2), max(u1 + src1 + d1, u2 + src2 + d2))
            if pair_key in checked_pairs:
                continue
            checked_pairs.add(pair_key)

            if dt1 and dt2:
                diff_days = abs((dt1 - dt2).days)
                if diff_days >= 2:
                    event_conflicts.append((u1, u2, name1 or name2, d1, d2))
                else:
                    event_matches.append((u1, u2, d1))
            elif d1 and d2:
                if d1.lower() == d2.lower():
                    event_matches.append((u1, u2, d1))
                else:
                    event_conflicts.append((u1, u2, name1 or name2, d1, d2))

    if event_conflicts:
        eu1, eu2, ename, ed1, ed2 = event_conflicts[0]
        distinct_urls = sorted({u for item in event_conflicts for u in (item[0], item[1]) if u})
        findings.append({
            "check_id": "FRS-007",
            "title": f"Conflicting event dates detected across {len(distinct_urls)} crawled pages",
            "category": "discoverability",
            "severity": "medium",
            "confidence": "high",
            "affected_urls": distinct_urls[:5],
            "evidence": (
                f"Contradicting event dates discovered: {eu1} declares '{ed1}' while {eu2} declares '{ed2}' for '{ename}'. "
                "Conflicting event schedules cause AI assistants to communicate unreliable event timing."
            ),
            "tags": ["event", "freshness", "corroboration", "contradiction"],
            "suggested_action": {
                "summary": "Consider synchronizing event dates across schedules, announcements, and structured data.",
                "priority": "medium",
                "effort": "low"
            }
        })
    elif event_matches:
        strengths.append({
            "title": "Event schedule corroborated across event announcements and structured data",
            "category": "discoverability"
        })

    # --- FRS-008: Contact channels corroboration & contradiction ---
    page_phones = {}
    page_emails = {}
    email_re = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b')
    phone_re = re.compile(r'\b(?:\+?1[-.\s]?)?\(?[2-9]\d{2}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b|\b\+?\d{2,3}[-.\s]?\d{2,4}[-.\s]?\d{3,4}[-.\s]?\d{3,4}\b')

    for p in pages:
        p_url = p.get("url") or p.get("final_url") or ""
        sample = p.get("visible_text_sample", "")
        for m in email_re.finditer(sample):
            page_emails.setdefault(p_url, set()).add(m.group(0).lower())
        for m in phone_re.finditer(sample):
            page_phones.setdefault(p_url, set()).add(re.sub(r'[^\d+]', '', m.group(0)))

        for block in (p.get("json_ld") or []):
            if isinstance(block, dict):
                tel = block.get("telephone")
                if isinstance(tel, str):
                    clean_tel = re.sub(r'[^\d+]', '', tel)
                    if len(clean_tel) >= 7:
                        page_phones.setdefault(p_url, set()).add(clean_tel)
                em = block.get("email")
                if isinstance(em, str) and "@" in em:
                    page_emails.setdefault(p_url, set()).add(em.strip().lower())

    all_emails = set()
    for em_set in page_emails.values():
        all_emails.update(em_set)
    email_domains = {e.split("@")[1] for e in all_emails if "@" in e}
    if len(email_domains) > 1 and not any(d in ("gmail.com", "outlook.com", "example.com") for d in email_domains):
        conflict_urls = [u for u, ems in page_emails.items() if ems]
        findings.append({
            "check_id": "FRS-008",
            "title": f"Conflicting contact channels detected across {len(conflict_urls)} crawled pages",
            "category": "discoverability",
            "severity": "medium",
            "confidence": "high",
            "affected_urls": conflict_urls[:5],
            "evidence": (
                f"Different corporate email domains found across site pages: {sorted(all_emails)[:3]}. "
                "Contradictory contact channels prevent AI agents from reliably directing users to support."
            ),
            "tags": ["contact-info", "corroboration", "contradiction"],
            "suggested_action": {
                "summary": "Ensure consistent contact telephone numbers and email addresses across all pages.",
                "priority": "medium",
                "effort": "low"
            }
        })
    elif len(all_emails) >= 1 and len(page_emails) >= 2:
        strengths.append({
            "title": "Contact channels corroborated across multiple site pages",
            "category": "discoverability"
        })

    # Priority adjustment based on page importance (Phase 4 Part 7)
    url_importance = {(p.get("url") or p.get("final_url") or ""): p.get("page_importance_score", 50) for p in pages}
    start_url = snapshot.get("crawl_meta", {}).get("start_url", "")
    for f in findings:
        aff = f.get("affected_urls", [])
        if any(url_importance.get(u, 50) >= 80 or u == start_url for u in aff):
            if isinstance(f.get("suggested_action"), dict):
                if f["suggested_action"].get("priority") == "medium":
                    f["suggested_action"]["priority"] = "high"

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
