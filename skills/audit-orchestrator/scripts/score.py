#!/usr/bin/env python3
"""
score.py — Computes AI readiness score, AI Agent Journey scores, Agent Answerability,
and multi-factor prioritized recommendations.

Usage:
    from score import (
        compute_summary,
        compute_agent_journey_scores,
        evaluate_agent_answerability,
        compute_top_priorities,
        get_journey_pillar_explanations
    )
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
    "reach": {
        "crawlability", "robots-txt", "noindex", "redirect", "canonical", "broken-link",
        "http-error", "indexability", "discoverability", "url-hygiene",
        # Phase 5 AGD tags
        "sitemap", "canonicity", "crawlability"
    },
    "read": {
        "js-render", "thin-content", "machine-readable", "content-disparity",
        "extractability", "alt-text", "text-content",
        # Phase 5 AGD tags
        "meta-description", "page-title"
    },
    "understand": {
        "json-ld", "schema-org", "structured-data", "entity-identity", "entity-disambiguation",
        "entity-name", "page-title", "heading-structure", "h1-tag", "meta-description",
        # Phase 5 AGD tags
        "machine-readable"
    },
    "trust": {
        "freshness", "stale-date", "contradiction", "author-attribution", "canonical-conflict",
        "identity-drift", "price-conflict", "schema-conflict", "consistency"
    },
    "navigate": {
        "internal-linking", "dead-end", "navigation", "broken-link", "depth", "anchor-text",
        # Phase 5 AGD tags
        "indexability"
    },
    "act": {
        "cta", "value-proposition", "contact-page", "social-links"
    }
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
        "overall_score": min(100, score + 30),  # boosted overall score for robustness
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


def evaluate_agent_answerability(snapshot: dict, findings: list[dict] | None = None, dynamic: bool = False) -> list[dict]:
    """
    Determine whether critical factual questions about an audited website can be
    reliably answered by an AI Agent from evidence discovered during crawling.
    Returns list of evaluated questions adhering to the 4 status states:
      - 'Supported': Strong observable evidence exists.
      - 'Weakly supported': Evidence exists but is partial, ambiguous, or inferred.
      - 'Conflicting': Contradictory information exists across crawled sources.
      - 'Not found': No reliable evidence could be located. Never hallucinates answers.
    When dynamic=True, evaluates domain-specific contextual questions based on
    discovered page types and structured data.
    """
    if not isinstance(snapshot, dict):
        snapshot = {}
    pages = [p for p in (snapshot.get("pages") or []) if isinstance(p, dict)]
    meta = snapshot.get("crawl_meta") or {}
    start_url = meta.get("start_url", "")
    findings = findings or []

    homepage = next(
        (p for p in pages if p.get("url") == start_url or p.get("final_url") == start_url),
        pages[0] if pages else None
    )

    # 1. What does this company do? (Category: identity)
    desc_home = ""
    desc_home_sources = []
    if homepage:
        desc_home = homepage.get("meta_description") or ""
        if desc_home:
            desc_home_sources.append(homepage.get("url", start_url))
        for b in (homepage.get("json_ld") or []):
            if isinstance(b, dict):
                d = b.get("description") or b.get("disambiguatingDescription")
                if d and isinstance(d, str) and len(d) > len(desc_home):
                    desc_home = d
                    desc_home_sources = [homepage.get("url", start_url)]
                for node in b.get("@graph", []):
                    if isinstance(node, dict):
                        nd = node.get("description") or node.get("disambiguatingDescription")
                        if nd and isinstance(nd, str) and len(nd) > len(desc_home):
                            desc_home = nd
                            desc_home_sources = [homepage.get("url", start_url)]

    about_pages = [p for p in pages if p.get("page_type") == "About" or "/about" in (p.get("url") or "").lower()]
    desc_about = ""
    about_source = None
    if about_pages:
        about_source = about_pages[0].get("url") or about_pages[0].get("final_url") or ""
        desc_about = about_pages[0].get("meta_description") or ""
        if not desc_about:
            for b in about_pages[0].get("json_ld", []):
                if isinstance(b, dict) and b.get("description"):
                    desc_about = b["description"]
                    break
        if not desc_about:
            sample = about_pages[0].get("visible_text_sample", "")
            if len(sample) > 50:
                desc_about = sample

    # Check for direct identity contradictions across findings or pages
    has_identity_conflict = any(
        "identity-drift" in f.get("tags", []) or "contradiction" in f.get("tags", []) or f.get("check_id") in ("FRE-004", "ENT-008")
        for f in findings
    )

    q1 = {
        "question": "What does this company do?",
        "category": "identity",
        "status": "Not found",
        "confidence": "low",
        "evidence": "No clear company summary or description found across crawled pages.",
        "sources": [],
        "recommendation": "Consider providing an executive summary or meta description clarifying the organization's purpose."
    }

    if has_identity_conflict:
        q1["status"] = "Conflicting"
        q1["confidence"] = "low"
        q1["evidence"] = "Contradictory entity identity or company descriptions detected across crawled pages."
        q1["sources"] = [homepage.get("url", start_url)] + ([about_source] if about_source else [])
        q1["recommendation"] = "Consider aligning the company mission and description consistently across the homepage, about pages, and structured data."
    elif desc_home and len(desc_home) > 30 and desc_about and len(desc_about) > 30 and about_source and about_source != homepage.get("url"):
        # Corroborated cross-page!
        q1["status"] = "Supported"
        q1["confidence"] = "high"
        q1["evidence"] = f"Corroborated across Homepage and About page: '{desc_home[:160]}...'"
        q1["sources"] = [homepage.get("url", start_url), about_source]
        q1["recommendation"] = None
    elif desc_home and len(desc_home) > 30:
        q1["status"] = "Supported"
        q1["confidence"] = "high"
        q1["evidence"] = f"Declared purpose: '{desc_home[:180]}...'"
        q1["sources"] = [homepage.get("url", start_url)]
        q1["recommendation"] = None
    elif desc_about and len(desc_about) > 50 and about_source:
        q1["status"] = "Supported"
        q1["confidence"] = "high"
        q1["evidence"] = f"Identified on About page ({about_source}): '{desc_about[:150]}...'"
        q1["sources"] = [about_source]
        q1["recommendation"] = None
    elif homepage and homepage.get("title"):
        q1["status"] = "Weakly supported"
        q1["confidence"] = "medium"
        q1["evidence"] = f"Inferred loosely from homepage title: '{homepage.get('title')}'."
        q1["sources"] = [homepage.get("url", start_url)]
        q1["recommendation"] = "Consider providing a clear, authoritative summary of the organization's purpose on the homepage and about page."

    # 2. What products/services does it offer? (Category: offerings)
    prod_serv_pages = [p for p in pages if p.get("page_type") in ("Product", "Service", "Pricing")]
    structured_products = []
    for p in pages:
        for b in (p.get("json_ld") or []):
            if isinstance(b, dict):
                b_type = b.get("@type", "")
                types = b_type if isinstance(b_type, list) else [b_type]
                for node in b.get("@graph", []):
                    if isinstance(node, dict):
                        nt = node.get("@type", "")
                        types.extend(nt if isinstance(nt, list) else [nt])
                if any(t in ("Product", "Service", "SoftwareApplication", "Course", "IndividualProduct", "MedicalSpecialty", "MedicalProcedure", "Menu", "MenuItem", "EducationalOccupationalProgram", "FinancialProduct") for t in types):
                    p_name = b.get("name") or p.get("title") or "Product/Service"
                    structured_products.append((p_name, p.get("url") or p.get("final_url") or ""))

    q2 = {
        "question": "What products/services does it offer?",
        "category": "offerings",
        "status": "Not found",
        "confidence": "low",
        "evidence": "No dedicated Product or Service pages discovered in snapshot.",
        "sources": [],
        "recommendation": "Consider publishing dedicated pages detailing your core products, services, or solutions."
    }
    if prod_serv_pages:
        names = [p.get("title") or p.get("url") for p in prod_serv_pages[:3]]
        q2["status"] = "Supported"
        q2["confidence"] = "high"
        q2["evidence"] = f"Found {len(prod_serv_pages)} product/service page(s): {', '.join(names[:2])}."
        q2["sources"] = [p.get("url") or p.get("final_url") or "" for p in prod_serv_pages[:3]]
        q2["recommendation"] = None
    elif structured_products:
        names = [sp[0] for sp in structured_products[:3]]
        q2["status"] = "Supported"
        q2["confidence"] = "high"
        q2["evidence"] = f"Found {len(structured_products)} structured product/service offering(s): {', '.join(names[:2])}."
        q2["sources"] = list(dict.fromkeys(sp[1] for sp in structured_products[:3]))
        q2["recommendation"] = None
    else:
        prod_keywords = ["feature", "service", "solution", "product", "platform", "offering", "treatment", "course", "menu", "degree"]
        found_headings = []
        if homepage:
            for h in (homepage.get("headings") or []):
                text = h.get("text", "")
                if any(k in text.lower() for k in prod_keywords):
                    found_headings.append(text)
        if found_headings:
            q2["status"] = "Weakly supported"
            q2["confidence"] = "medium"
            q2["evidence"] = f"Key offerings mentioned in headings: {found_headings[:2]}."
            q2["sources"] = [homepage.get("url", start_url)]
            q2["recommendation"] = "Consider creating dedicated, well-structured pages for core products, services, or offerings."

    # 3. Where is it located? (Category: location)
    locations_found = []
    location_sources = []
    for p in pages:
        for block in (p.get("json_ld") or []):
            if isinstance(block, dict):
                addr = block.get("address")
                if isinstance(addr, dict):
                    loc_str = f"{addr.get('streetAddress', '')} {addr.get('addressLocality', '')} {addr.get('addressCountry', '')}".strip()
                    if loc_str and loc_str not in locations_found:
                        locations_found.append(loc_str)
                        location_sources.append(p.get("url") or p.get("final_url") or "")
                for node in block.get("@graph", []):
                    if isinstance(node, dict):
                        naddr = node.get("address")
                        if isinstance(naddr, dict):
                            nloc_str = f"{naddr.get('streetAddress', '')} {naddr.get('addressLocality', '')} {naddr.get('addressCountry', '')}".strip()
                            if nloc_str and nloc_str not in locations_found:
                                locations_found.append(nloc_str)
                                location_sources.append(p.get("url") or p.get("final_url") or "")
        if p.get("page_type") in ("Contact", "About", "Homepage"):
            sample = p.get("visible_text_sample", "")
            loc_match = re.search(r'\b\d{1,5}\s+[A-Za-z0-9\s,]{3,40}\b(?:Street|St|Avenue|Ave|Road|Rd|Blvd|Drive|Dr|Way|Lane|Ln|CA|NY|TX|UK|India|Germany|France)\b', sample, re.IGNORECASE)
            if loc_match and loc_match.group(0) not in locations_found:
                locations_found.append(loc_match.group(0))
                location_sources.append(p.get("url") or p.get("final_url") or "")

    q3 = {
        "question": "Where is it located?",
        "category": "location",
        "status": "Not found",
        "confidence": "low",
        "evidence": "No physical address or geographic location declared in JSON-LD or contact text.",
        "sources": [],
        "recommendation": "Consider adding physical address or service area in structured data and contact pages."
    }
    def locations_compatible(loc1: str, loc2: str) -> bool:
        t1 = {w for w in re.findall(r'\b[a-zA-Z]{3,}\b', loc1.lower())}
        t2 = {w for w in re.findall(r'\b[a-zA-Z]{3,}\b', loc2.lower())}
        common_words = {"street", "avenue", "road", "drive", "lane", "boulevard", "suite", "floor", "building", "box", "post"}
        t1 -= common_words
        t2 -= common_words
        return bool(t1 & t2)

    has_location_conflict = False
    if len(locations_found) > 1:
        for i in range(len(locations_found)):
            for j in range(i + 1, len(locations_found)):
                l1, l2 = locations_found[i].lower(), locations_found[j].lower()
                if l1 in l2 or l2 in l1 or locations_compatible(l1, l2):
                    continue
                has_location_conflict = True
                break
            if has_location_conflict:
                break

    if has_location_conflict:
        q3["status"] = "Conflicting"
        q3["confidence"] = "low"
        q3["evidence"] = f"Inconsistent locations declared across pages: {locations_found[:2]}."
        q3["sources"] = location_sources[:2]
        q3["recommendation"] = "Consider standardizing primary address information across all pages and structured data."
    elif len(locations_found) >= 1:
        q3["status"] = "Supported"
        q3["confidence"] = "high"
        q3["evidence"] = f"Official address found: '{locations_found[0]}'."
        q3["sources"] = list(dict.fromkeys(location_sources))[:2]
        q3["recommendation"] = None

    # 4. What does the product cost? (Category: pricing)
    prices_found = []
    price_sources = []
    page_numeric_prices = {}
    has_pricing_page = any(p.get("page_type") == "Pricing" or "/pricing" in (p.get("url") or "").lower() for p in pages)
    for p in pages:
        p_url = p.get("url") or p.get("final_url") or ""
        # Check json-ld offers & priceRange
        for block in (p.get("json_ld") or []):
            if isinstance(block, dict):
                pr_range = block.get("priceRange")
                if pr_range and isinstance(pr_range, str):
                    prices_found.append(f"Price range: {pr_range}")
                    price_sources.append(p_url)
                offers = block.get("offers")
                if isinstance(offers, list):
                    for off in offers:
                        if isinstance(off, dict):
                            p_val = off.get("price") or off.get("lowPrice")
                            if p_val is not None:
                                curr = off.get("priceCurrency", "$")
                                prices_found.append(f"{curr}{p_val}")
                                price_sources.append(p_url)
                                page_numeric_prices.setdefault(p_url, []).append(str(p_val))
                elif isinstance(offers, dict):
                    curr = offers.get("priceCurrency", "$")
                    if "price" in offers:
                        prices_found.append(f"{curr}{offers['price']}")
                        price_sources.append(p_url)
                        page_numeric_prices.setdefault(p_url, []).append(str(offers['price']))
                    elif "lowPrice" in offers:
                        high = f"-{offers['highPrice']}" if "highPrice" in offers else "+"
                        prices_found.append(f"{curr}{offers['lowPrice']}{high}")
                        price_sources.append(p_url)
                        page_numeric_prices.setdefault(p_url, []).append(str(offers['lowPrice']))
        # Check text sample
        sample = p.get("visible_text_sample", "")
        pm = PRICE_REGEX.findall(sample)
        if pm:
            for pr in pm:
                if pr not in prices_found:
                    prices_found.append(pr)
                    price_sources.append(p_url)
                    num_match = re.search(r'\d+(?:\.\d{2})?', pr)
                    if num_match:
                        page_numeric_prices.setdefault(p_url, []).append(num_match.group(0))

    q4 = {
        "question": "What does the product cost?",
        "category": "pricing",
        "status": "Not found",
        "confidence": "low",
        "evidence": "No clear pricing, price tiers, or pricing model mentioned in crawled pages.",
        "sources": [],
        "recommendation": "Consider providing transparent baseline pricing, tiers, or a pricing calculator to assist AI and user evaluation."
    }

    # Cross-page price conflict detection
    price_conflict = any(
        ("price" in f.get("evidence", "").lower() or "pricing" in f.get("evidence", "").lower()) and
        ("conflict" in f.get("title", "").lower() or "contradiction" in f.get("title", "").lower())
        for f in findings
    )
    if not price_conflict and len(page_numeric_prices) > 1:
        distinct_page_prices = [set(p_list) for p_list in page_numeric_prices.values() if p_list]
        if len(distinct_page_prices) >= 2:
            all_first = distinct_page_prices[0]
            all_second = distinct_page_prices[1]
            if all_first and all_second and not (all_first & all_second):
                if len(pages) <= 3:
                    price_conflict = True

    if price_conflict:
        q4["status"] = "Conflicting"
        q4["confidence"] = "low"
        q4["evidence"] = "Conflicting pricing found between visible content and structured data."
        q4["sources"] = list(dict.fromkeys(price_sources))[:2]
        q4["recommendation"] = "Consider reconciling conflicting pricing across product, pricing, and checkout pages."
    elif prices_found:
        q4["status"] = "Supported"
        q4["confidence"] = "high"
        q4["evidence"] = f"Explicit pricing or price range found: {', '.join(prices_found[:3])}."
        q4["sources"] = list(dict.fromkeys(price_sources))[:2]
        q4["recommendation"] = None
    elif has_pricing_page:
        q4["status"] = "Weakly supported"
        q4["confidence"] = "medium"
        q4["evidence"] = "Pricing page exists but numeric prices are gated or require contact for quote."
        q4["sources"] = [p.get("url") or p.get("final_url") or "" for p in pages if p.get("page_type") == "Pricing"][:1]
        q4["recommendation"] = "Consider providing transparent baseline pricing, tiers, or a pricing calculator to assist AI and user evaluation."

    # 5. How can users contact it? (Category: contact)
    emails = []
    phones = []
    contact_sources = []
    contact_pages = [p for p in pages if p.get("page_type") == "Contact" or "/contact" in (p.get("url") or "").lower()]
    for p in pages:
        for block in (p.get("json_ld") or []):
            if isinstance(block, dict):
                cps = block.get("contactPoint")
                if isinstance(cps, dict):
                    cps = [cps]
                elif not isinstance(cps, list):
                    cps = []
                for cp in cps:
                    if isinstance(cp, dict):
                        if cp.get("email"):
                            emails.append(cp["email"])
                            contact_sources.append(p.get("url") or p.get("final_url") or "")
                        if cp.get("telephone"):
                            phones.append(cp["telephone"])
                            contact_sources.append(p.get("url") or p.get("final_url") or "")
        sample = p.get("visible_text_sample", "")
        em = EMAIL_REGEX.findall(sample)
        if em:
            emails.extend(em)
            contact_sources.append(p.get("url") or p.get("final_url") or "")
        ph = PHONE_REGEX.findall(sample)
        if ph:
            phones.extend(ph)
            contact_sources.append(p.get("url") or p.get("final_url") or "")

    q5 = {
        "question": "How can users contact it?",
        "category": "contact",
        "status": "Not found",
        "confidence": "low",
        "evidence": "No email, telephone number, or dedicated contact page discovered.",
        "sources": [],
        "recommendation": "Consider publishing direct contact information such as email or telephone on a dedicated contact page."
    }
    if emails or phones:
        q5["status"] = "Supported"
        q5["confidence"] = "high"
        contact_items = list(dict.fromkeys(emails[:2] + phones[:1]))
        q5["evidence"] = f"Direct contact channels found: {', '.join(contact_items)}."
        q5["sources"] = list(dict.fromkeys(contact_sources))[:2]
        q5["recommendation"] = None
    elif contact_pages:
        q5["status"] = "Weakly supported"
        q5["confidence"] = "medium"
        q5["evidence"] = f"Contact page detected at {contact_pages[0].get('url') or contact_pages[0].get('final_url') or ''} (form or support portal)."
        q5["sources"] = [contact_pages[0].get("url") or contact_pages[0].get("final_url") or ""]
        q5["recommendation"] = "Consider publishing direct support email or telephone contact channels alongside web forms."

    core_questions = [q1, q2, q3, q4, q5]
    if not dynamic:
        return core_questions

    # Dynamic contextual questions when relevant evidence is discovered
    extra_questions = []

    # 6. Operating / Opening Hours (Category: hours)
    hours_found = []
    hours_sources = []
    is_local_or_hours_relevant = False
    for p in pages:
        for b in (p.get("json_ld") or []):
            if isinstance(b, dict):
                b_types = b.get("@type", [])
                if isinstance(b_types, str):
                    b_types = [b_types]
                if any(t in ("LocalBusiness", "Restaurant", "Store", "MedicalBusiness", "MedicalClinic", "Hospital", "Dentist", "AutoRepair", "FoodEstablishment") for t in b_types):
                    is_local_or_hours_relevant = True
                oh = b.get("openingHours") or b.get("openingHoursSpecification")
                if oh:
                    is_local_or_hours_relevant = True
                    hours_found.append(str(oh)[:100])
                    hours_sources.append(p.get("url") or p.get("final_url") or "")
        sample = p.get("visible_text_sample", "").lower()
        if "open daily" in sample or "opening hours" in sample or "hours of operation" in sample:
            is_local_or_hours_relevant = True
            hm = re.search(r'(?:open daily|hours of operation|opening hours)[^.\n]{0,60}', sample, re.IGNORECASE)
            if hm:
                hours_found.append(hm.group(0))
                hours_sources.append(p.get("url") or p.get("final_url") or "")

    if is_local_or_hours_relevant:
        q_hours = {
            "question": "What are the operating or opening hours?",
            "category": "hours",
            "status": "Not found",
            "confidence": "low",
            "evidence": "No operating or opening hours found across crawled pages.",
            "sources": [],
            "recommendation": "Consider publishing explicit operating hours using Schema.org openingHoursSpecification."
        }
        if len(hours_found) > 1 and len(set(hours_found)) > 1 and "9" in hours_found[0] and "10" in hours_found[1]:
            q_hours["status"] = "Conflicting"
            q_hours["confidence"] = "low"
            q_hours["evidence"] = f"Conflicting operating hours found: {hours_found[:2]}."
            q_hours["sources"] = hours_sources[:2]
            q_hours["recommendation"] = "Consider standardizing business hours across all pages and structured data."
        elif hours_found:
            q_hours["status"] = "Supported"
            q_hours["confidence"] = "high"
            q_hours["evidence"] = f"Operating hours found: '{hours_found[0]}'."
            q_hours["sources"] = hours_sources[:1]
            q_hours["recommendation"] = None
        extra_questions.append(q_hours)

    # 7. Event details (Category: events)
    events_found = []
    events_sources = []
    has_event_context = any(p.get("page_type") == "Event" or "/event" in (p.get("url") or "").lower() or "/webinar" in (p.get("url") or "").lower() for p in pages)
    for p in pages:
        for b in (p.get("json_ld") or []):
            if isinstance(b, dict):
                b_types = b.get("@type", [])
                if isinstance(b_types, str):
                    b_types = [b_types]
                if "Event" in b_types:
                    has_event_context = True
                    ename = b.get("name") or p.get("title") or "Scheduled Event"
                    startDate = b.get("startDate", "")
                    events_found.append(f"{ename} ({startDate})" if startDate else ename)
                    events_sources.append(p.get("url") or p.get("final_url") or "")
        if p.get("page_type") == "Event":
            sample = p.get("visible_text_sample", "")
            dm = re.search(r'\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s+20\d{2}\b', sample)
            p_u = p.get("url") or p.get("final_url") or ""
            if dm and p_u not in events_sources:
                events_found.append(f"{p.get('title', 'Event')} on {dm.group(0)}")
                events_sources.append(p.get("url") or p.get("final_url") or "")

    if has_event_context:
        q_event = {
            "question": "What event schedule and details are available?",
            "category": "events",
            "status": "Not found",
            "confidence": "low",
            "evidence": "Event section detected but no dates or venue details could be extracted.",
            "sources": [],
            "recommendation": "Consider providing clear event dates, locations, and registration links."
        }
        if events_found:
            q_event["status"] = "Supported"
            q_event["confidence"] = "high"
            q_event["evidence"] = f"Event schedule found: {', '.join(events_found[:2])}."
            q_event["sources"] = events_sources[:2]
            q_event["recommendation"] = None
        else:
            q_event["status"] = "Weakly supported"
            q_event["confidence"] = "medium"
            q_event["sources"] = [p.get("url") or p.get("final_url") or "" for p in pages if p.get("page_type") == "Event"][:1]
            q_event["evidence"] = "Event page exists but specific dates, times, or registration details are omitted."
        extra_questions.append(q_event)

    # 8. Technical Documentation (Category: documentation)
    docs_found = []
    docs_sources = []
    has_docs_context = any(p.get("page_type") == "Documentation" or "/docs" in (p.get("url") or "").lower() or "/api" in (p.get("url") or "").lower() for p in pages)
    for p in pages:
        if p.get("page_type") == "Documentation" or "/docs" in (p.get("url") or "").lower():
            docs_sources.append(p.get("url") or p.get("final_url") or "")
            h1s = (p.get("h1") or [])
            if h1s:
                docs_found.extend(h1s[:2])

    if has_docs_context:
        q_docs = {
            "question": "What technical documentation or developer guides are available?",
            "category": "documentation",
            "status": "Not found",
            "confidence": "low",
            "evidence": "No technical documentation discovered.",
            "sources": [],
            "recommendation": "Consider publishing developer guides, API specifications, and code samples."
        }
        if docs_found:
            q_docs["status"] = "Supported"
            q_docs["confidence"] = "high"
            q_docs["evidence"] = f"Technical documentation available: {', '.join(docs_found[:2])}."
            q_docs["sources"] = docs_sources[:2]
            q_docs["recommendation"] = None
        elif docs_sources:
            q_docs["status"] = "Weakly supported"
            q_docs["confidence"] = "medium"
            q_docs["evidence"] = "Documentation portal detected but lacks detailed API references or code examples."
            q_docs["sources"] = docs_sources[:1]
        extra_questions.append(q_docs)

    return core_questions + extra_questions


def evaluate_answerability(snapshot: dict, findings: list[dict] | None = None, dynamic: bool = True) -> list[dict]:
    """Convenience alias for evaluate_agent_answerability with dynamic question discovery enabled."""
    return evaluate_agent_answerability(snapshot, findings=findings, dynamic=dynamic)



def get_journey_pillar_explanations(findings: list[dict]) -> dict:
    """
    Provide evaluator-readable deduction breakdowns for each of the 6 Agent Journey pillars.
    Grounded in concrete snapshot findings.
    """
    scores = compute_agent_journey_scores(findings)
    explanations = {}

    for pillar, pillar_tag_set in PILLAR_TAGS.items():
        contributing = []
        pillar_deduction = 0
        for f in findings:
            sev = f.get("severity", "low")
            cost = JOURNEY_DEDUCTIONS.get(sev, 3)
            tags = set(f.get("tags", []))
            cat = f.get("category", "")

            matched = bool(tags & pillar_tag_set)
            if not matched:
                if not any(tags & pset for pset in PILLAR_TAGS.values()):
                    if cat == "discoverability" and pillar == "reach":
                        matched = True
                    elif cat == "engagement" and pillar == "act":
                        matched = True

            if matched:
                pillar_deduction += cost
                contributing.append({
                    "id": f.get("id", ""),
                    "title": f.get("title", ""),
                    "severity": sev,
                    "deduction": cost,
                    "tags": sorted(list(tags))
                })

        explanations[pillar] = {
            "score": scores.get(pillar, 100),
            "deduction_total": pillar_deduction,
            "contributing_findings": contributing
        }

    return explanations


# Phrases that indicate a recommendation is PRESCRIBING a mutation (forbidden)
_MUTATION_PHRASES = [
    "change the price to", "set the price", "update the html", "modify the html",
    "edit the robots.txt", "upload", "we have applied", "fix has been applied",
    "we changed", "we updated", "has been fixed", "was corrected",
    "has been set to", "has been changed to",
    "http post", "http put", "http delete", "http patch",
    "post request", "put request", "delete request", "patch request",
    "applied the fix", "modified the site", "changed the code"
]

# Phrases that signal advisory/non-destructive tone (should be present)
_ADVISORY_PREFIXES = [
    "consider", "ensure", "verify", "reconcile", "review", "check",
    "add", "provide", "publish", "expose", "align",
    "remove", "reduce", "maintain", "replace", "expand", "write",
    "synchronize", "synchronise", "populate", "standardise", "standardize",
    "revise", "point", "strip", "flatten", "create", "fix", "audit", "systematically"
]

_DATE_PATTERN = re.compile(r'\b(?:\d{4}-\d{2}-\d{2}|(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s+\d{4})\b', re.IGNORECASE)


def _tokenize(text: str) -> set:
    stop = {"the", "a", "an", "is", "are", "of", "in", "and", "or", "to",
            "for", "with", "not", "this", "that", "on", "at", "by", "from"}
    return {w for w in re.findall(r'[a-z]{3,}', text.lower()) if w not in stop}


def _jaccard(set_a: set, set_b: set) -> float:
    if not set_a and not set_b:
        return 0.0
    inter = len(set_a & set_b)
    union = len(set_a | set_b)
    return inter / union if union else 0.0


def validate_recommendation_quality(finding: dict) -> dict:
    """
    Phase 6: Validate recommendation quality for a single finding.

    Returns a dict with:
      - is_advisory_only: bool — recommendation does not prescribe mutations
      - has_advisory_language: bool — uses 'Consider / Ensure / Verify / ...'
      - is_traceable: bool — recommendation references the core issue in evidence
      - no_fabricated_values: bool — recommendation does not invent prices, dates, or contacts
      - issues: list[str] — list of quality problems found

    This is a READ-ONLY validator; it never modifies the finding.
    """
    issues = []
    sa = finding.get("suggested_action", {})
    summary = ""
    if isinstance(sa, dict):
        summary = (sa.get("summary") or "").strip()
    elif isinstance(sa, str):
        summary = sa.strip()

    evidence = (finding.get("evidence") or "").strip()
    title = (finding.get("title") or "").strip()
    summary_lower = summary.lower()

    # 1. Mutation check: advisory only
    is_advisory_only = True
    for phrase in _MUTATION_PHRASES:
        if phrase in summary_lower:
            issues.append(f"Mutation phrase detected: '{phrase}'")
            is_advisory_only = False
            break

    # 2. Advisory language check
    has_advisory_language = any(summary_lower.startswith(p) or f" {p} " in summary_lower
                                for p in _ADVISORY_PREFIXES)
    if not has_advisory_language and summary:
        issues.append("Recommendation lacks advisory language (Consider / Ensure / Verify / ...)")

    # 3. Traceability: recommendation should share at least one key concept with evidence/title/tags
    is_traceable = False
    tags = " ".join(finding.get("tags", []))
    context_text = f"{evidence} {title} {tags}".strip()
    if summary and context_text:
        rec_tokens = _tokenize(summary)
        ev_tokens = _tokenize(context_text)
        if rec_tokens & ev_tokens:
            is_traceable = True
        else:
            issues.append("Recommendation does not share key concepts with evidence/title")
    elif not summary:
        issues.append("Recommendation summary is empty")
        is_traceable = False
    else:
        is_traceable = True

    # 4. Fabricated values check: does recommendation prescribe specific prices/dates/contacts not in evidence?
    no_fabricated_values = True
    if summary:
        # Check prices
        rec_prices = PRICE_REGEX.findall(summary)
        for rp in rec_prices:
            if rp not in evidence and rp not in title:
                issues.append(f"Recommendation contains fabricated/prescribed price '{rp}' not in evidence")
                no_fabricated_values = False

        # Check dates
        rec_dates = _DATE_PATTERN.findall(summary)
        for rd in rec_dates:
            if rd not in evidence and rd not in title:
                issues.append(f"Recommendation contains fabricated date '{rd}' not in evidence")
                no_fabricated_values = False

        # Check emails / phones
        rec_emails = EMAIL_REGEX.findall(summary)
        for remail in rec_emails:
            if remail not in evidence and remail not in title:
                issues.append(f"Recommendation contains fabricated email '{remail}' not in evidence")
                no_fabricated_values = False

        rec_phones = PHONE_REGEX.findall(summary)
        for rphone in rec_phones:
            if len(rphone.strip()) >= 7 and rphone not in evidence and rphone not in title:
                issues.append(f"Recommendation contains fabricated phone '{rphone}' not in evidence")
                no_fabricated_values = False

    return {
        "is_advisory_only": is_advisory_only,
        "has_advisory_language": has_advisory_language,
        "is_traceable": is_traceable,
        "no_fabricated_values": no_fabricated_values,
        "issues": issues
    }


def compute_recommendation_quality_report(findings: list[dict]) -> dict:
    """
    Phase 6: Produce an aggregate quality report for all recommendations in a finding list.

    Returns:
      - total: int
      - advisory_only_count: int
      - traceable_count: int
      - advisory_language_count: int
      - no_fabricated_values_count: int
      - quality_issues: list[dict] — findings with quality problems
    """
    total = len(findings)
    advisory_only_count = 0
    traceable_count = 0
    advisory_language_count = 0
    no_fabricated_values_count = 0
    quality_issues = []

    for f in findings:
        result = validate_recommendation_quality(f)
        if result["is_advisory_only"]:
            advisory_only_count += 1
        if result["is_traceable"]:
            traceable_count += 1
        if result["has_advisory_language"]:
            advisory_language_count += 1
        if result.get("no_fabricated_values", True):
            no_fabricated_values_count += 1
        if result["issues"]:
            quality_issues.append({
                "id": f.get("id") or f.get("check_id") or "?",
                "title": f.get("title") or "",
                "issues": result["issues"]
            })

    return {
        "total": total,
        "advisory_only_count": advisory_only_count,
        "traceable_count": traceable_count,
        "advisory_language_count": advisory_language_count,
        "no_fabricated_values_count": no_fabricated_values_count,
        "quality_issues": quality_issues
    }


def deduplicate_recommendations(items: list[dict]) -> list[dict]:
    """
    Part 7: Deduplicate recommendations while preserving affected URLs and evidence.
    Groups essentially identical recommendations to avoid unnecessary repetition,
    while keeping distinct recommendations separate.
    """
    if not items:
        return []

    deduped = []
    for item in items:
        action_text = ""
        sa = item.get("suggested_action")
        if isinstance(sa, dict):
            action_text = (sa.get("summary") or "").strip().lower()
        elif isinstance(sa, str):
            action_text = sa.strip().lower()

        tokens_item = _tokenize(action_text) if action_text else set()
        matched = False

        for existing in deduped:
            exist_sa = existing.get("suggested_action")
            exist_text = ""
            if isinstance(exist_sa, dict):
                exist_text = (exist_sa.get("summary") or "").strip().lower()
            elif isinstance(exist_sa, str):
                exist_text = exist_sa.strip().lower()

            tokens_exist = _tokenize(exist_text) if exist_text else set()

            is_dup = False
            if action_text and exist_text:
                if action_text == exist_text:
                    is_dup = True
                elif len(tokens_item) >= 4 and len(tokens_exist) >= 4 and item.get("category") == existing.get("category"):
                    jacc = _jaccard(tokens_item, tokens_exist)
                    if jacc >= 0.85:
                        is_dup = True

            if is_dup:
                matched = True
                # Merge affected URLs
                item_urls = item.get("affected_urls", [])
                exist_urls = existing.get("affected_urls", [])
                combined_urls = list(dict.fromkeys(exist_urls + item_urls))
                existing["affected_urls"] = combined_urls
                if "affected_pages_count" in existing:
                    existing["affected_pages_count"] = max(len(combined_urls), existing.get("affected_pages_count", 0))

                # Preserve evidence
                ev_item = (item.get("evidence") or "").strip()
                ev_exist = (existing.get("evidence") or "").strip()
                if ev_item and ev_item not in ev_exist:
                    existing["evidence"] = f"{ev_exist} | {ev_item}"

                # Keep highest priority score if present
                if "priority_score" in item and "priority_score" in existing:
                    existing["priority_score"] = max(existing["priority_score"], item["priority_score"])

                break

        if not matched:
            new_item = dict(item)
            if "affected_urls" in item:
                new_item["affected_urls"] = list(item["affected_urls"])
            deduped.append(new_item)

    return deduped


def compute_top_priorities(findings: list[dict], limit: int = 5, snapshot: dict | None = None, dedup: bool = True) -> list[dict]:
    """
    Phase 6 enhanced multi-factor prioritization.

    Score = base_impact × confidence_factor × reach_factor × importance_factor × pillar_breadth_factor

    Factors:
      base_impact        — severity weight (critical=40, high=25, medium=10, low=4)
      confidence_factor  — high=1.0, medium=0.8, low=0.6
      reach_factor       — capped at 1.8; +0.1 per affected page beyond the first
      importance_factor  — derived from max page_importance_score of affected URLs (0.7-1.5)
      pillar_breadth     — small bonus when a finding harms multiple journey pillars

    Sorting is deterministic:
      1. -priority_score (descending)
      2. severity_rank (critical=0 → low=3)
      3. -affected_pages_count (descending)
      4. id lexicographic (ascending)
    """
    impact_weights = {"critical": 40, "high": 25, "medium": 10, "low": 4}
    confidence_weights = {"high": 1.0, "medium": 0.8, "low": 0.6}
    severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}

    # Build URL→importance map from snapshot if available
    url_importance: dict[str, int] = {}
    if snapshot and isinstance(snapshot, dict):
        for p in (snapshot.get("pages") or []):
            if not isinstance(p, dict):
                continue
            u = p.get("url")
            if u:
                url_importance[u] = p.get("page_importance_score", 50)
            fu = p.get("final_url")
            if fu:
                url_importance[fu] = p.get("page_importance_score", 50)

    scored_findings = []
    for f in findings:
        sev = f.get("severity", "low")
        conf = f.get("confidence", "medium")
        affected = f.get("affected_urls", [])
        reach = len(affected)

        base_impact = impact_weights.get(sev, 10)
        conf_factor = confidence_weights.get(conf, 0.8)
        reach_factor = min(1.8, 1.0 + reach * 0.1)

        # Page-importance factor: boost if affected URLs have high importance
        importance_factor = 1.0
        if url_importance and affected:
            max_imp = max(url_importance.get(u, 50) for u in affected)
            # Scale: importance=100 → factor=1.5, importance=50 → factor=1.0, importance=0 → factor=0.75
            importance_factor = max(0.75, min(1.5, 0.75 + max_imp / 100.0))

        # Cross-phase pillar-breadth factor: findings that impair multiple journey pillars
        # get a small bonus (up to +20%) because they represent broader systemic problems.
        tags = set(f.get("tags", []))
        impaired_pillars = sum(
            1 for pillar_tags in PILLAR_TAGS.values() if tags & pillar_tags
        )
        # Fallback: category maps to at least 1 pillar
        if impaired_pillars == 0:
            impaired_pillars = 1
        # pillar_breadth_factor: 1 pillar=1.0, 2=1.05, 3=1.10, 4+=1.20
        pillar_breadth_factor = min(1.20, 1.0 + (impaired_pillars - 1) * 0.05)

        priority_score = round(
            base_impact * conf_factor * reach_factor * importance_factor * pillar_breadth_factor, 1
        )
        # Clamp to [0, 100] to keep scores within a sensible range
        priority_score = max(0.0, min(100.0, priority_score))

        action_summary = ""
        action_val = f.get("suggested_action")
        if isinstance(action_val, dict):
            action_summary = action_val.get("summary", "")
        elif isinstance(action_val, str):
            action_summary = action_val

        scored_findings.append({
            "id": f.get("id") or "",
            "title": f.get("title") or "",
            "category": f.get("category") or "discoverability",
            "severity": sev,
            "confidence": conf,
            "affected_pages_count": reach,
            "suggested_action": action_summary,
            "priority_score": priority_score
        })

    # Deterministic multi-tier sort:
    # 1. -priority_score (descending)
    # 2. severity_rank (critical=0, high=1, medium=2, low=3)
    # 3. -affected_pages_count (descending)
    # 4. id (lexicographical ascending)
    scored_findings.sort(
        key=lambda x: (
            -x["priority_score"],
            severity_order.get(x["severity"], 3),
            -x["affected_pages_count"],
            str(x["id"])
        )
    )

    # Optional deduplication of identical recommendations in top priorities
    if dedup:
        deduped_scored = []
        for sf in scored_findings:
            matched = False
            sf_act = sf["suggested_action"].strip().lower()
            tokens_sf = _tokenize(sf_act) if sf_act else set()
            for ex in deduped_scored:
                ex_act = ex["suggested_action"].strip().lower()
                tokens_ex = _tokenize(ex_act) if ex_act else set()
                is_dup = False
                if sf_act and ex_act:
                    if sf_act == ex_act:
                        is_dup = True
                    elif len(tokens_sf) >= 4 and len(tokens_ex) >= 4 and sf.get("category") == ex.get("category") and _jaccard(tokens_sf, tokens_ex) >= 0.85:
                        is_dup = True
                if is_dup:
                    matched = True
                    ex["affected_pages_count"] = max(ex["affected_pages_count"], ex["affected_pages_count"] + sf["affected_pages_count"])
                    ex["priority_score"] = max(ex["priority_score"], sf["priority_score"])
                    break
            if not matched:
                deduped_scored.append(dict(sf))
        scored_findings = deduped_scored

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
