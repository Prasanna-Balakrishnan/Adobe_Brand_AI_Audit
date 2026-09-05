#!/usr/bin/env python3
"""
score.py — Computes AI readiness score, AI Agent Journey scores, Agent Answerability,
and multi-factor prioritized recommendations.

Usage:
    from score import compute_summary, compute_agent_journey_scores, evaluate_agent_answerability, compute_top_priorities
"""

import json
import re
import sys
from urllib.parse import urlparse

# Severity deductions for overall ai_readiness_score
SEVERITY_DEDUCTIONS = {
    "critical": 25,
    "high": 10,
    "medium": 4,
    "low": 1
}

# Pillar weight deductions for AI Agent Journey evaluation (Req 10)
JOURNEY_DEDUCTIONS = {
    "critical": 25,
    "high": 15,
    "medium": 8,
    "low": 3
}

PILLAR_TAGS = {
    "reach": {"crawlability", "robots-txt", "noindex", "redirect", "canonical", "broken-link", "http-error"},
    "read": {"js-render", "thin-content", "heading-structure", "page-title", "meta-description"},
    "understand": {"json-ld", "schema-org", "structured-data", "entity-identity", "entity-disambiguation", "entity-name"},
    "trust": {"freshness", "stale-date", "contradiction", "author-attribution", "canonical-conflict", "identity-drift"},
    "navigate": {"internal-linking", "dead-end", "navigation", "broken-link", "depth"},
    "act": {"cta", "value-proposition", "contact-page", "social-links"}
}

# Regex patterns for fact checking
EMAIL_REGEX = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b')
PHONE_REGEX = re.compile(r'\b(?:\+?\d{1,3}[-.\s]?)?\(?\d{2,4}\)?[-.\s]?\d{3,4}[-.\s]?\d{3,4}\b')
PRICE_REGEX = re.compile(r'(?:[\$€£]\s*\d+(?:\.\d{2})?|\b\d+(?:\.\d{2})?\s*(?:USD|EUR|GBP)\b)')


def compute_summary(findings: list[dict], snapshot: dict | None = None) -> dict:
    """
    Compute the summary block from a list of deduplicated findings.
    Retains strict schema compatibility while adding journey scores.
    """
    counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    by_category = {"discoverability": 0, "engagement": 0}

    for f in findings:
        sev = f.get("severity", "low")
        if sev in counts:
            counts[sev] += 1

        cat = f.get("category", "discoverability")
        if cat in by_category:
            by_category[cat] += 1

    score = max(
        0,
        100
        - counts["critical"] * SEVERITY_DEDUCTIONS["critical"]
        - counts["high"] * SEVERITY_DEDUCTIONS["high"]
        - counts["medium"] * SEVERITY_DEDUCTIONS["medium"]
        - counts["low"] * SEVERITY_DEDUCTIONS["low"]
    )

    journey_scores = compute_agent_journey_scores(findings)

    return {
        "total_findings": len(findings),
        "critical": counts["critical"],
        "high": counts["high"],
        "medium": counts["medium"],
        "low": counts["low"],
        "ai_readiness_score": score,
        "by_category": by_category,
        "agent_journey_scores": journey_scores
    }


def compute_agent_journey_scores(findings: list[dict]) -> dict:
    """
    Evaluate AI Agent Journey across 6 pillars: Reach, Read, Understand, Trust, Navigate, Act. (Req 10)
    """
    deductions = {pillar: 0 for pillar in PILLAR_TAGS}

    for f in findings:
        sev = f.get("severity", "low")
        cost = JOURNEY_DEDUCTIONS.get(sev, 3)
        tags = set(f.get("tags", []))
        check_id = f.get("check_id", "")
        cat = f.get("category", "")

        # Map to pillars
        matched_pillars = set()
        for pillar, pillar_tag_set in PILLAR_TAGS.items():
            if tags & pillar_tag_set:
                matched_pillars.add(pillar)

        # Fallback category mapping if tags didn't hit
        if not matched_pillars:
            if cat == "discoverability":
                matched_pillars.add("reach")
            elif cat == "engagement":
                matched_pillars.add("act")

        for p in matched_pillars:
            deductions[p] += cost

    scores = {}
    for pillar in PILLAR_TAGS:
        scores[pillar] = max(0, 100 - deductions[pillar])

    overall = round(sum(scores.values()) / len(scores))
    scores["overall_journey_score"] = overall
    return scores


def evaluate_agent_answerability(snapshot: dict, findings: list[dict] | None = None) -> list[dict]:
    """
    Determine whether critical brand questions can be answered by an AI Agent from crawled content. (Req 11)
    Returns list of evaluated questions with Supported, Weakly supported, Conflicting, or Not found.
    """
    pages = snapshot.get("pages", [])
    meta = snapshot.get("crawl_meta", {})
    start_url = meta.get("start_url", "")
    findings = findings or []

    # Check for contradictions in findings
    contradiction_finding = any(
        "contradiction" in f.get("tags", []) or "conflict" in f.get("tags", []) or f.get("check_id") in ("FRE-004", "SDC-013")
        for f in findings
    )

    homepage = next(
        (p for p in pages if p.get("url") == start_url or p.get("final_url") == start_url),
        pages[0] if pages else None
    )

    # 1. What does this company do?
    desc = ""
    about_pages = [p for p in pages if p.get("page_type") == "About" or "/about" in p.get("url", "").lower()]
    if homepage:
        desc = homepage.get("meta_description") or ""
        if not desc:
            for b in homepage.get("json_ld", []):
                if isinstance(b, dict) and b.get("description"):
                    desc = b["description"]
                    break

    q1 = {
        "question": "What does this company do?",
        "status": "Not found",
        "confidence": "medium",
        "evidence": "No clear company summary or description found across crawled pages.",
        "sources": []
    }
    if desc and len(desc) > 30:
        q1["status"] = "Supported"
        q1["confidence"] = "high"
        q1["evidence"] = f"Declared purpose: '{desc[:180]}...'"
        q1["sources"] = [homepage.get("url", start_url)]
    elif about_pages:
        about_sample = about_pages[0].get("visible_text_sample", "")
        if len(about_sample) > 50:
            q1["status"] = "Supported"
            q1["confidence"] = "high"
            q1["evidence"] = f"Identified on About page ({about_pages[0]['url']}): '{about_sample[:150]}...'"
            q1["sources"] = [about_pages[0]["url"]]
    elif homepage and homepage.get("title"):
        q1["status"] = "Weakly supported"
        q1["confidence"] = "medium"
        q1["evidence"] = f"Inferred loosely from homepage title: '{homepage.get('title')}'."
        q1["sources"] = [homepage.get("url", start_url)]

    # 2. What products/services does it offer?
    prod_serv_pages = [p for p in pages if p.get("page_type") in ("Product", "Service", "Pricing")]
    q2 = {
        "question": "What products/services does it offer?",
        "status": "Not found",
        "confidence": "medium",
        "evidence": "No dedicated Product or Service pages discovered in snapshot.",
        "sources": []
    }
    if prod_serv_pages:
        names = [p.get("title") or p.get("url") for p in prod_serv_pages[:3]]
        q2["status"] = "Supported"
        q2["confidence"] = "high"
        q2["evidence"] = f"Found {len(prod_serv_pages)} product/service page(s): {', '.join(names[:2])}."
        q2["sources"] = [p["url"] for p in prod_serv_pages[:3]]
    else:
        # Check headings on homepage
        prod_keywords = ["feature", "service", "solution", "product", "platform", "offering"]
        found_headings = []
        if homepage:
            for h in homepage.get("headings", []):
                text = h.get("text", "")
                if any(k in text.lower() for k in prod_keywords):
                    found_headings.append(text)
        if found_headings:
            q2["status"] = "Weakly supported"
            q2["confidence"] = "medium"
            q2["evidence"] = f"Key offerings mentioned in headings: {found_headings[:2]}."
            q2["sources"] = [homepage.get("url", start_url)]

    # 3. Where is it located?
    locations_found = []
    location_sources = []
    for p in pages:
        # Check JSON-LD
        for block in p.get("json_ld", []):
            if isinstance(block, dict):
                addr = block.get("address")
                if isinstance(addr, dict):
                    loc_str = f"{addr.get('streetAddress', '')} {addr.get('addressLocality', '')} {addr.get('addressCountry', '')}".strip()
                    if loc_str and loc_str not in locations_found:
                        locations_found.append(loc_str)
                        location_sources.append(p["url"])
        # Check text sample on contact/about
        if p.get("page_type") in ("Contact", "About"):
            sample = p.get("visible_text_sample", "")
            loc_match = re.search(r'\b\d{1,5}\s+[A-Za-z0-9\s,]{3,40}\b(?:Street|St|Avenue|Ave|Road|Rd|Blvd|Drive|Dr|Way|Lane|Ln|CA|NY|TX|UK|India|Germany|France)\b', sample, re.IGNORECASE)
            if loc_match and loc_match.group(0) not in locations_found:
                locations_found.append(loc_match.group(0))
                location_sources.append(p["url"])

    q3 = {
        "question": "Where is it located?",
        "status": "Not found",
        "confidence": "medium",
        "evidence": "No physical address or geographic location declared in JSON-LD or contact text.",
        "sources": []
    }
    if len(locations_found) > 1 and not all(locations_found[0].lower() in loc.lower() for loc in locations_found):
        # Conflicting locations detected across pages
        q3["status"] = "Conflicting"
        q3["confidence"] = "high"
        q3["evidence"] = f"Inconsistent locations declared across pages: {locations_found[:2]}."
        q3["sources"] = location_sources[:2]
    elif len(locations_found) == 1:
        q3["status"] = "Supported"
        q3["confidence"] = "high"
        q3["evidence"] = f"Official address found: '{locations_found[0]}'."
        q3["sources"] = location_sources[:1]

    # 4. What does the product cost?
    prices_found = []
    price_sources = []
    has_pricing_page = any(p.get("page_type") == "Pricing" or "/pricing" in p.get("url", "").lower() for p in pages)
    for p in pages:
        # Check json-ld offers
        for block in p.get("json_ld", []):
            if isinstance(block, dict):
                offers = block.get("offers")
                if isinstance(offers, dict) and "price" in offers:
                    prices_found.append(str(offers["price"]))
                    price_sources.append(p["url"])
        # Check text sample
        sample = p.get("visible_text_sample", "")
        pm = PRICE_REGEX.findall(sample)
        if pm:
            for pr in pm:
                if pr not in prices_found:
                    prices_found.append(pr)
                    price_sources.append(p["url"])

    q4 = {
        "question": "What does the product cost?",
        "status": "Not found",
        "confidence": "medium",
        "evidence": "No clear pricing, price tiers, or pricing model mentioned in crawled pages.",
        "sources": []
    }
    # Check for visible vs JSON-LD price conflict
    price_conflict = any("price" in f.get("evidence", "").lower() and "conflict" in f.get("title", "").lower() for f in findings)
    if price_conflict:
        q4["status"] = "Conflicting"
        q4["confidence"] = "high"
        q4["evidence"] = "Conflicting pricing found between visible content and structured data."
        q4["sources"] = price_sources[:2]
    elif prices_found:
        q4["status"] = "Supported"
        q4["confidence"] = "high"
        q4["evidence"] = f"Explicit pricing found: {', '.join(prices_found[:3])}."
        q4["sources"] = list(dict.fromkeys(price_sources))[:2]
    elif has_pricing_page:
        q4["status"] = "Weakly supported"
        q4["confidence"] = "medium"
        q4["evidence"] = "Pricing page exists but numeric prices are gated or require contact for quote."
        q4["sources"] = [p["url"] for p in pages if p.get("page_type") == "Pricing"][:1]

    # 5. How can users contact it?
    emails = []
    phones = []
    contact_sources = []
    contact_pages = [p for p in pages if p.get("page_type") == "Contact" or "/contact" in p.get("url", "").lower()]
    for p in pages:
        sample = p.get("visible_text_sample", "")
        em = EMAIL_REGEX.findall(sample)
        if em:
            emails.extend(em)
            contact_sources.append(p["url"])
        ph = PHONE_REGEX.findall(sample)
        if ph:
            phones.extend(ph)
            contact_sources.append(p["url"])

    q5 = {
        "question": "How can users contact it?",
        "status": "Not found",
        "confidence": "high",
        "evidence": "No email, telephone number, or dedicated contact page discovered.",
        "sources": []
    }
    if emails or phones:
        q5["status"] = "Supported"
        q5["confidence"] = "high"
        contact_items = list(dict.fromkeys(emails[:2] + phones[:1]))
        q5["evidence"] = f"Direct contact channels found: {', '.join(contact_items)}."
        q5["sources"] = list(dict.fromkeys(contact_sources))[:2]
    elif contact_pages:
        q5["status"] = "Weakly supported"
        q5["confidence"] = "medium"
        q5["evidence"] = f"Contact page detected at {contact_pages[0]['url']} (form or support portal)."
        q5["sources"] = [contact_pages[0]["url"]]

    return [q1, q2, q3, q4, q5]


def compute_top_priorities(findings: list[dict], limit: int = 5) -> list[dict]:
    """
    Multi-factor prioritization using Impact x Reach x Confidence (Req 14).
    Avoids arbitrary high severity for minor SEO issues and highlights high-ROI actions.
    """
    impact_weights = {"critical": 40, "high": 25, "medium": 10, "low": 4}
    confidence_weights = {"high": 1.0, "medium": 0.8, "low": 0.6}

    scored_findings = []
    for f in findings:
        sev = f.get("severity", "low")
        conf = f.get("confidence", "medium")
        reach = len(f.get("affected_urls", []))

        base_impact = impact_weights.get(sev, 10)
        conf_factor = confidence_weights.get(conf, 0.8)
        reach_factor = min(1.8, 1.0 + reach * 0.1)

        priority_score = round(base_impact * conf_factor * reach_factor, 1)

        scored_findings.append({
            "id": f.get("id"),
            "title": f.get("title"),
            "category": f.get("category"),
            "severity": sev,
            "confidence": conf,
            "affected_pages_count": reach,
            "suggested_action": f.get("suggested_action", {}).get("summary", ""),
            "priority_score": priority_score
        })

    # Sort descending by priority_score
    scored_findings.sort(key=lambda x: x["priority_score"], reverse=True)

    top = []
    for idx, item in enumerate(scored_findings[:limit]):
        item["priority_rank"] = idx + 1
        top.append(item)

    return top


if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser()
    p.add_argument("--input", required=True, help="Path to deduplicated_findings.json")
    p.add_argument("--output", default="summary.json")
    args = p.parse_args()

    try:
        with open(args.input, encoding="utf-8") as f:
            data = json.load(f)
        findings = data.get("findings", data) if isinstance(data, dict) else data
    except Exception as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        sys.exit(1)

    summary = compute_summary(findings)

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    print(f"[OK] Score: {summary['ai_readiness_score']}/100 "
          f"(C:{summary['critical']} H:{summary['high']} "
          f"M:{summary['medium']} L:{summary['low']}) → {args.output}",
          file=sys.stderr)
