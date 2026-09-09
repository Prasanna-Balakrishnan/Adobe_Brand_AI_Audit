#!/usr/bin/env python3
"""
audit.py — entity-identity-audit skill

Checks brand name consistency, About/Contact presence, author attribution,
and entity ambiguity risk from snapshot.json.

Usage:
    python audit.py --snapshot snapshot.json --output entity_findings.json
"""

import argparse
import json
import re
import sys
from collections import Counter
from urllib.parse import urlparse

SKILL_NAME = "entity-identity-audit"

ABOUT_URL_PATTERNS = ["/about", "/who-we-are", "/our-story", "/company", "/team",
                      "/mission", "/history", "/overview", "/a-propos", "/sobre-nosotros",
                      "/acerca-de", "/ueber-uns", "/uber-uns", "/chi-siamo"]
ABOUT_TITLE_PATTERNS = ["about", "who we are", "our story", "our team", "company",
                         "about us", "à propos", "a propos", "sobre nosotros", "über uns",
                         "ueber uns", "chi siamo"]
CONTACT_URL_PATTERNS = ["/contact", "/reach-us", "/get-in-touch", "/contact-us",
                         "/support", "/help", "/connect", "/contacto", "/kontakt",
                         "/nous-contacter", "/contatto"]
CONTACT_TEXT_PATTERNS = [
    r'\b[\w.+-]+@[\w-]+\.[\w.]+\b',          # email
    r'\b\+?[\d][\d\s\-().]{7,}\d\b',          # phone number
    r'\b\d{1,5}\s[\w\s]{3,30},\s[\w]{2,}',   # street address
]
BLOG_URL_PATTERNS = ["/blog", "/article", "/news", "/post", "/insight"]
AMBIGUOUS_SHORT_NAMES_STOPWORDS = {
    "a", "i", "the", "and", "or", "in", "at", "by", "for", "my", "our", "your",
    "it", "is", "was", "be", "an", "on", "of", "to", "up", "do"
}
NAME_SUFFIX_STRIP = re.compile(
    r'[,.\s]+(inc\.?|llc\.?|ltd\.?|corp\.?|corporation|company|co\.?|gmbh|plc|s\.a\.|s\.a\.s|pvt\.?|s\.l\.|s\.r\.l\.|ag|bv|nv)$',
    re.IGNORECASE
)
SAME_AS_DOMAINS = ["wikipedia.org", "wikidata.org", "linkedin.com", "crunchbase.com",
                   "twitter.com", "facebook.com"]


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--snapshot", default="snapshot.json")
    p.add_argument("--output", default="entity_findings.json")
    return p.parse_args()


def load_snapshot(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def normalise_name(name: str) -> str:
    """Strip legal suffixes, punctuation, extra whitespace, and lowercase for robust comparison."""
    if not name or not isinstance(name, str):
        return ""
    cleaned = name.strip()
    n = NAME_SUFFIX_STRIP.sub("", cleaned).strip().lower()
    n = re.sub(r'[^\w\s]', '', n)
    return re.sub(r'\s+', ' ', n).strip()


ORG_SUBSTRINGS = {
    "organization", "corporation", "business", "company", "university", "college",
    "school", "ngo", "institution", "agency", "association", "newsmedia",
    "restaurant", "hospital", "clinic", "hotel", "store", "food", "establishment"
}


def is_org_type(t: str | list) -> bool:
    types = [t] if isinstance(t, str) else (t or [])
    for item in types:
        if not isinstance(item, str):
            continue
        item_lower = item.lower()
        if item in {"Organization", "LocalBusiness", "Corporation", "NGO",
                    "GovernmentOrganization", "WebSite"}:
            return True
        if any(sub in item_lower for sub in ORG_SUBSTRINGS):
            return True
    return False


def get_org_names_from_jsonld(json_ld_blocks: list) -> list[str]:
    names = []
    for block in json_ld_blocks:
        if not isinstance(block, dict):
            continue
        t = block.get("@type", "")
        if is_org_type(t):
            name = block.get("name", "")
            if name:
                names.append(name)
        # Check @graph
        for node in block.get("@graph", []):
            if isinstance(node, dict):
                nt = node.get("@type", "")
                if is_org_type(nt):
                    name = node.get("name", "")
                    if name:
                        names.append(name)
    return names


def has_same_as(json_ld_blocks: list) -> bool:
    for block in json_ld_blocks:
        if not isinstance(block, dict):
            continue
        t = block.get("@type", "")
        if is_org_type(t):
            if block.get("sameAs"):
                return True
        for node in block.get("@graph", []):
            if isinstance(node, dict) and is_org_type(node.get("@type", "")):
                if node.get("sameAs"):
                    return True
    return False


def derive_brand_name(snapshot: dict) -> tuple[str | None, str]:
    """Return (candidate_name, source) from JSON-LD → H1 → domain."""
    if not isinstance(snapshot, dict):
        return None, "none"
    meta = snapshot.get("crawl_meta") or {}
    pages = [p for p in (snapshot.get("pages") or []) if isinstance(p, dict)]
    start_url = meta.get("start_url", "")
    homepage = next(
        (p for p in pages if p.get("url") == start_url or p.get("final_url") == start_url),
        pages[0] if pages else None
    )

    # 1. JSON-LD Organization.name
    if homepage:
        org_names = get_org_names_from_jsonld((homepage.get("json_ld") or []))
        if org_names:
            return org_names[0], "json-ld"

    # 2. Most common H1 text across all pages
    all_h1 = []
    for p in pages:
        all_h1.extend((p.get("h1") or []))
    if all_h1:
        counter = Counter(all_h1)
        return counter.most_common(1)[0][0], "h1"

    # 3. Domain name
    if start_url:
        netloc = urlparse(start_url).netloc
        domain = netloc.split(".")[0]
        if domain and not domain.isdigit() and not re.match(r'^\d{1,3}(?:\.\d{1,3}){3}', netloc):
            return domain, "domain"

    return None, "none"


def compute_entity_confidence(snapshot: dict, findings: list[dict] | None = None) -> tuple[float, str, list[str]]:
    """
    Calculate deterministic entity identity confidence (0.0 to 1.0) based on
    corroborating evidence across crawl snapshot.
    """
    if not isinstance(snapshot, dict):
        return 0.0, "Low", []
    pages = [p for p in (snapshot.get("pages") or []) if isinstance(p, dict)]
    meta = snapshot.get("crawl_meta") or {}
    start_url = meta.get("start_url", "")
    homepage = next(
        (p for p in pages if p.get("url") == start_url or p.get("final_url") == start_url),
        pages[0] if pages else None
    )

    brand_name, brand_source = derive_brand_name(snapshot)
    all_urls = [(p.get("url") or p.get("final_url") or "").lower() for p in pages]
    all_titles = [p.get("title", "").lower() for p in pages]
    has_about = (
        any(p.get("page_type") == "About" for p in pages) or
        any(any(pat in u for pat in ABOUT_URL_PATTERNS) for u in all_urls) or
        any(any(pat in t for pat in ABOUT_TITLE_PATTERNS) for t in all_titles)
    )
    has_contact_page = (
        any(any(pat in u for pat in CONTACT_URL_PATTERNS) for u in all_urls) or
        any(p.get("page_type") == "Contact" for p in pages)
    )
    has_contact_info = any(
        any(re.search(pat, p.get("visible_text_sample", "")) for pat in CONTACT_TEXT_PATTERNS)
        for p in pages
    )

    confidence_score = 0.0
    confidence_signals = []
    if brand_name:
        confidence_score += 0.25
        confidence_signals.append(f"brand name identified as '{brand_name}'")
    if brand_source == "json-ld":
        confidence_score += 0.25
        confidence_signals.append("verified by Organization JSON-LD")
    if has_about:
        confidence_score += 0.20
        confidence_signals.append("authoritative About page present")
    if has_contact_page or has_contact_info:
        confidence_score += 0.15
        confidence_signals.append("contact channels available")
    if homepage and has_same_as((homepage.get("json_ld") or [])):
        confidence_score += 0.15
        confidence_signals.append("external sameAs entity links declared")

    if findings:
        # Deductions for contradictions
        if any(f.get("check_id") in ("ENT-002", "ENT-008") for f in findings):
            confidence_score -= 0.30
        if any(f.get("check_id") in ("ENT-009", "ENT-010", "ENT-011") for f in findings):
            confidence_score -= 0.20
        if any(f.get("check_id") == "ENT-006" for f in findings):
            confidence_score -= 0.15

    confidence_score = max(0.0, min(1.0, round(confidence_score, 2)))
    conf_level = "High" if confidence_score >= 0.75 else ("Moderate" if confidence_score >= 0.45 else "Low")
    return confidence_score, conf_level, confidence_signals


def run_checks(snapshot: dict) -> tuple[list[dict], list[dict]]:
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
    homepage = next(
        (p for p in pages if p.get("url") == start_url or p.get("final_url") == start_url),
        pages[0] if pages else None
    )

    # Derive candidate brand name
    brand_name, brand_source = derive_brand_name(snapshot)

    # --- ENT-001: Brand name not detectable ---
    if not brand_name:
        findings.append({
            "check_id": "ENT-001",
            "title": "Brand name cannot be identified from any crawled page",
            "category": "discoverability",
            "severity": "high",
            "confidence": "medium",
            "affected_urls": [start_url] if start_url else [],
            "evidence": (
                "No Organization JSON-LD with a name field, no H1 text, and domain "
                "name extraction failed. AI assistants cannot identify this brand."
            ),
            "tags": ["entity-disambiguation", "entity-name"],
            "suggested_action": {
                "summary": "Add Organization JSON-LD with a name field to the homepage; add an H1 with the brand name.",
                "priority": "high",
                "effort": "low"
            }
        })
    else:
        if brand_source == "json-ld":
            strengths.append({
                "title": "Brand name declared in Organization JSON-LD",
                "category": "discoverability"
            })

    # --- ENT-002: Inconsistent name across pages (Req 7, 12, 15) ---
    if brand_name:
        norm_brand = normalise_name(brand_name)
        inconsistent_pages = []
        name_variants = set()
        for p in pages:
            # Collect all org names from this page's JSON-LD
            page_org_names = get_org_names_from_jsonld((p.get("json_ld") or []))
            for n in page_org_names:
                norm_n = normalise_name(n)
                if norm_n and norm_n != norm_brand and norm_n not in norm_brand and norm_brand not in norm_n:
                    inconsistent_pages.append(p)
                    name_variants.add(n)
                    break
        if inconsistent_pages:
            findings.append({
                "check_id": "ENT-002",
                "title": f"Organisation name is inconsistent across {len(inconsistent_pages)}/{total} pages",
                "category": "discoverability",
                "severity": "high",
                "confidence": "high",
                "affected_urls": [p.get("url") or p.get("final_url") or "" for p in inconsistent_pages[:5]],
                "evidence": (
                    f"Canonical name '{brand_name}' (from {brand_source}), but {len(name_variants)} variant(s) found: "
                    f"{list(name_variants)[:5]} across {len(inconsistent_pages)}/{total} pages. "
                    "Inconsistent naming confuses AI entity resolution."
                ),
                "tags": ["entity-name", "entity-disambiguation", "identity-drift"],
                "root_cause_group": "entity_identity_drift",
                "suggested_action": {
                    "summary": "Standardise the organisation name across all pages and JSON-LD blocks.",
                    "priority": "high",
                    "effort": "medium"
                }
            })

    # --- ENT-003: No About page ---
    is_doc_site = any(p.get("page_type") == "Documentation" or "/docs" in p.get("url", "").lower() for p in pages)
    all_urls = [(p.get("url") or p.get("final_url") or "").lower() for p in pages]
    all_titles = [p.get("title", "").lower() for p in pages]
    has_about = (
        any(p.get("page_type") == "About" for p in pages) or
        any(any(pat in u for pat in ABOUT_URL_PATTERNS) for u in all_urls) or
        any(any(pat in t for pat in ABOUT_TITLE_PATTERNS) for t in all_titles)
    )
    if not has_about and not is_doc_site:
        sev = "medium" if (total <= 3 or (homepage and get_org_names_from_jsonld((homepage.get("json_ld") or [])))) else "high"
        conf = "low" if total <= 2 else "medium"
        findings.append({
            "check_id": "ENT-003",
            "title": "No About page detected",
            "category": "discoverability",
            "severity": sev,
            "confidence": conf,
            "affected_urls": [start_url],
            "evidence": (
                f"None of {total} crawled URLs match about-page patterns "
                f"({', '.join(ABOUT_URL_PATTERNS[:3])}, ...) and no page title contains 'About'."
            ),
            "tags": ["about-page", "entity-identity", "entity-disambiguation"],
            "suggested_action": {
                "summary": "Consider creating an About page with org name, description, founding year, and mission.",
                "priority": sev,
                "effort": "medium"
            }
        })
    elif has_about:
        strengths.append({
            "title": "About page present for entity context",
            "category": "discoverability"
        })

    # --- ENT-004: No Contact page or contact info ---
    has_contact_page = (
        any(p.get("page_type") == "Contact" for p in pages) or
        any(any(pat in u for pat in CONTACT_URL_PATTERNS) for u in all_urls)
    )
    has_contact_info = False
    for p in pages:
        # Check JSON-LD for contactPoint, telephone, email
        for block in (p.get("json_ld") or []):
            if isinstance(block, dict):
                if block.get("contactPoint") or block.get("telephone") or block.get("email"):
                    has_contact_info = True
                    break
        if has_contact_info:
            break
        sample = p.get("visible_text_sample", "") or ""
        for pat in CONTACT_TEXT_PATTERNS:
            if re.search(pat, sample):
                has_contact_info = True
                break
        if has_contact_info:
            break

    if not has_contact_page and not has_contact_info:
        findings.append({
            "check_id": "ENT-004",
            "title": "No contact page or contact information found",
            "category": "discoverability",
            "severity": "high",
            "confidence": "medium",
            "affected_urls": [start_url],
            "evidence": (
                f"No URL matches contact-page patterns and no email, phone, or address "
                f"detected in visible text samples across {total} crawled pages."
            ),
            "tags": ["contact-page", "entity-identity"],
            "suggested_action": {
                "summary": "Add a Contact page with email, phone, and/or address.",
                "priority": "high",
                "effort": "low"
            }
        })
    else:
        strengths.append({
            "title": "Contact information accessible",
            "category": "discoverability"
        })

    # --- ENT-005: No author attribution on blog/article pages ---
    blog_pages = []
    for p in pages:
        if p.get("page_type") == "Homepage":
            continue
        p_path = urlparse(p.get("url") or p.get("final_url") or "").path.lower().rstrip("/")
        if not p_path:
            continue
        if p.get("page_type") in ("Blog", "Article", "NewsArticle") or any(pat in p_path for pat in BLOG_URL_PATTERNS):
            blog_pages.append(p)

    if blog_pages:
        no_author_pages = []
        for p in blog_pages:
            # Check JSON-LD for author
            has_author_jsonld = False
            for block in (p.get("json_ld") or []):
                if isinstance(block, dict) and block.get("author"):
                    has_author_jsonld = True
                    break
            # Check visible text for "by [Name]" pattern
            sample = p.get("visible_text_sample", "") or ""
            has_author_text = bool(re.search(r'\bby\s+[A-Z][a-z]+', sample))
            if not has_author_jsonld and not has_author_text:
                no_author_pages.append(p)
        if no_author_pages:
            findings.append({
                "check_id": "ENT-005",
                "title": f"Author attribution missing on {len(no_author_pages)}/{len(blog_pages)} article pages",
                "category": "discoverability",
                "severity": "medium",
                "confidence": "medium",
                "affected_urls": [p.get("url") or p.get("final_url") or "" for p in no_author_pages[:5]],
                "evidence": (
                    f"{len(no_author_pages)} blog/article pages have no author in JSON-LD "
                    "and no visible byline. AI agents cannot attribute content."
                ),
                "tags": ["author-attribution", "entity-identity"],
                "suggested_action": {
                    "summary": "Add author to Article JSON-LD and include visible bylines on article pages.",
                    "priority": "medium",
                    "effort": "low"
                }
            })

    # --- ENT-006: Entity name ambiguity risk ---
    if brand_name:
        name_words = normalise_name(brand_name).split()
        is_ambiguous = (
            len(brand_name) < 4 or
            (len(name_words) <= 2 and all(w in AMBIGUOUS_SHORT_NAMES_STOPWORDS for w in name_words))
        )
        if is_ambiguous:
            findings.append({
                "check_id": "ENT-006",
                "title": f"Brand name '{brand_name}' may be ambiguous or generic",
                "category": "discoverability",
                "severity": "medium",
                "confidence": "low",
                "affected_urls": [start_url],
                "evidence": (
                    f"Detected brand name '{brand_name}' is short ({len(brand_name)} chars) "
                    "or uses only common words, creating disambiguation risk for AI agents."
                ),
                "tags": ["entity-disambiguation", "entity-name"],
                "suggested_action": {
                    "summary": "Add disambiguatingDescription and sameAs to Organisation JSON-LD; use full legal name.",
                    "priority": "medium",
                    "effort": "low"
                }
            })

    # --- ENT-007: Missing sameAs in Organisation JSON-LD ---
    if homepage:
        hp_jsonld = (homepage.get("json_ld") or [])
        hp_org_names = get_org_names_from_jsonld(hp_jsonld)
        if hp_org_names:  # Has org JSON-LD
            if not has_same_as(hp_jsonld):
                findings.append({
                    "check_id": "ENT-007",
                    "title": "Organisation JSON-LD missing sameAs links",
                    "category": "discoverability",
                    "severity": "low",
                    "confidence": "high",
                    "affected_urls": [homepage.get("url") or homepage.get("final_url") or ""] if homepage else [start_url],
                    "evidence": (
                        "Homepage Organization JSON-LD has no sameAs property. "
                        "sameAs links to authoritative profiles help AI corroborate entity identity."
                    ),
                    "tags": ["entity-disambiguation", "schema-org"],
                    "suggested_action": {
                        "summary": "Add sameAs URLs (LinkedIn, Wikipedia, Wikidata) to Organization JSON-LD.",
                        "priority": "low",
                        "effort": "low"
                    }
                })
            else:
                strengths.append({
                    "title": "sameAs links in Organization schema support entity corroboration",
                    "category": "discoverability"
                })

    # --- ENT-008: Name inconsistency across title, H1, JSON-LD, About & Contact (Req 7) ---
    declared_names = {}
    if homepage:
        hp_orgs = get_org_names_from_jsonld((homepage.get("json_ld") or []))
        if hp_orgs:
            declared_names["homepage_jsonld"] = hp_orgs[0].strip()
        if homepage.get("title"):
            title_brand = homepage["title"].split("|")[0].split("-")[0].strip()
            if len(title_brand) > 2:
                declared_names["homepage_title"] = title_brand

    for p in pages:
        if p.get("page_type") == "About":
            ab_orgs = get_org_names_from_jsonld((p.get("json_ld") or []))
            if ab_orgs:
                declared_names["about_jsonld"] = ab_orgs[0].strip()
        elif p.get("page_type") == "Contact":
            ct_orgs = get_org_names_from_jsonld((p.get("json_ld") or []))
            if ct_orgs:
                declared_names["contact_jsonld"] = ct_orgs[0].strip()

    HEAD_STRIP_RE = re.compile(r'^(about(\s+us)?|contact(\s+us)?|welcome\s+to|our\s+story|meet\s+the\s+team|the)\s+', re.IGNORECASE)
    for p in pages:
        if p.get("page_type") in ("Homepage", "About", "Contact") and p.get("h1"):
            raw_h1 = p["h1"][0].strip()
            stripped_h1 = HEAD_STRIP_RE.sub("", raw_h1).strip()
            words = stripped_h1.split()
            if 1 <= len(words) <= 4 and not any(w.lower() in ("home", "overview", "platform", "solutions", "team", "services") for w in words):
                declared_names[f"{p.get('page_type', 'page').lower()}_h1"] = stripped_h1

    canonical_norm = normalise_name(brand_name) if brand_name else ""
    distinct_norm_names = {}
    for elem, val in declared_names.items():
        n = normalise_name(val)
        if not n or len(n) <= 2 or n in ("about us", "contact us", "home", "welcome"):
            continue
        if canonical_norm and (n in canonical_norm or canonical_norm in n):
            continue
        distinct_norm_names.setdefault(n, []).append((elem, val))

    if len(distinct_norm_names) > 0 and canonical_norm and not any(f.get("check_id") == "ENT-002" for f in findings):
        names_summary = [f"{v[0][0]} ('{v[0][1]}')" for v in distinct_norm_names.values()]
        findings.append({
            "check_id": "ENT-008",
            "title": f"Inconsistent organization identity across key page elements ({len(distinct_norm_names) + 1} variations)",
            "category": "discoverability",
            "severity": "medium",
            "confidence": "high",
            "affected_urls": [homepage.get("url") or homepage.get("final_url") or ""] if homepage else [start_url],
            "evidence": (
                f"Disparate identity signals detected vs canonical '{brand_name}': {', '.join(names_summary[:3])}. "
                "AI search agents cross-reference title, H1, and JSON-LD to ground entity identity."
            ),
            "tags": ["entity-name", "entity-identity", "identity-drift"],
            "root_cause_group": "entity_identity_drift",
            "suggested_action": {
                "summary": "Align organization name consistently across Title, H1 headings, and JSON-LD schema.",
                "priority": "medium",
                "effort": "low"
            }
        })

    # --- ENT-009: Fact consistency - conflicting founding years or locations (Req 7, 12) ---
    founding_years = set()
    locations = set()
    founding_re = re.compile(r'\b(?:founded|established|est\.?)\s+(?:in\s+)?((?:19|20)\d{2})\b', re.IGNORECASE)
    loc_re = re.compile(r'\b(?:headquarters|based in|located in)\s*:?\s*([A-Za-z\s]{3,25}(?:,\s*[A-Za-z\s]{2,20})?)\b', re.IGNORECASE)

    # Collect contact points
    page_phones = {}
    page_emails = {}
    email_re = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b')
    phone_re = re.compile(r'\b(?:\+?1[-.\s]?)?\(?[2-9]\d{2}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b|\b\+?\d{2,3}[-.\s]?\d{2,4}[-.\s]?\d{3,4}[-.\s]?\d{3,4}\b')

    for p in pages:
        sample = p.get("visible_text_sample", "")
        # Founding years
        for m in founding_re.finditer(sample):
            founding_years.add(m.group(1))

        # Visible locations
        for m in loc_re.finditer(sample):
            cleaned_loc = m.group(1).strip()
            if len(cleaned_loc) > 3 and not any(w in cleaned_loc.lower() for w in ("the", "our", "all", "your", "today")):
                locations.add(cleaned_loc)

        # Visible contact info
        p_url = p.get("url") or p.get("final_url") or ""
        for m in email_re.finditer(sample):
            page_emails.setdefault(p_url, set()).add(m.group(0).lower())
        for m in phone_re.finditer(sample):
            page_phones.setdefault(p_url, set()).add(re.sub(r'[^\d+]', '', m.group(0)))

        # JSON-LD foundingDate, address, contactPoint
        for block in (p.get("json_ld") or []):
            if isinstance(block, dict):
                fd = str(block.get("foundingDate") or "")
                if fd and len(fd) >= 4 and fd[:4].isdigit():
                    founding_years.add(fd[:4])
                addr = block.get("address")
                if isinstance(addr, dict):
                    loc_text = f"{addr.get('addressLocality', '')} {addr.get('addressCountry', '')}".strip()
                    if loc_text:
                        locations.add(loc_text)
                elif isinstance(addr, str) and len(addr) > 3:
                    locations.add(addr.strip())

                tel = block.get("telephone")
                if isinstance(tel, str):
                    p_url = p.get("url") or p.get("final_url") or ""
                    clean_tel = re.sub(r'[^\d+]', '', tel)
                    if len(clean_tel) >= 7:
                        page_phones.setdefault(p_url, set()).add(clean_tel)
                em = block.get("email")
                if isinstance(em, str) and "@" in em:
                    p_url = p.get("url") or p.get("final_url") or ""
                    page_emails.setdefault(p_url, set()).add(em.strip().lower())

    if len(founding_years) > 1:
        findings.append({
            "check_id": "ENT-009",
            "title": f"Conflicting founding years detected across pages ({', '.join(sorted(founding_years))})",
            "category": "discoverability",
            "severity": "high",
            "confidence": "high",
            "affected_urls": [p.get("url") or p.get("final_url") or "" for p in pages[:5]],
            "evidence": (
                f"Discrepancy in company founding year: {sorted(founding_years)} found across crawled content. "
                "Factual contradictions severely degrade AI confidence and lead to incorrect answers."
            ),
            "tags": ["entity-identity", "contradiction", "fact-consistency"],
            "root_cause_group": "entity_identity_drift",
            "suggested_action": {
                "summary": "Verify and align founding dates across all website copy and JSON-LD markup.",
                "priority": "high",
                "effort": "low"
            }
        })

    # --- ENT-010: Conflicting locations detected across pages or schema ---
    if len(locations) > 1:
        norm_locs = {re.sub(r'[^\w\s]', '', loc.lower()).strip() for loc in locations if len(loc.strip()) > 3}
        clusters = []  # list of sets of locations
        for l in norm_locs:
            tokens = {w for w in l.split() if len(w) > 2}
            matched_cluster = None
            for cl in clusters:
                if any(
                    (tokens and {w for w in other.split() if len(w) > 2} and (tokens & {w for w in other.split() if len(w) > 2}))
                    or l in other or other in l
                    for other in cl
                ):
                    matched_cluster = cl
                    break
            if matched_cluster is not None:
                matched_cluster.add(l)
            else:
                clusters.append({l})

        if len(clusters) > 1:
            findings.append({
                "check_id": "ENT-010",
                "title": f"Conflicting organization locations detected across pages ({', '.join(sorted(locations)[:3])})",
                "category": "discoverability",
                "severity": "medium",
                "confidence": "high",
                "affected_urls": [p.get("url") or p.get("final_url") or "" for p in pages[:5]],
                "evidence": (
                    f"Discrepancy in primary location: {sorted(locations)[:3]} declared across crawled pages and structured data. "
                    "Inconsistent location facts confuse geographic entity resolution in search and AI assistants."
                ),
                "tags": ["entity-location", "entity-identity", "contradiction"],
                "root_cause_group": "entity_identity_drift",
                "suggested_action": {
                    "summary": "Consider establishing a single authoritative primary location across structured data and site copy.",
                    "priority": "medium",
                    "effort": "low"
                }
            })

    # --- ENT-011: Conflicting contact channels across pages ---
    all_emails = set()
    for em_set in page_emails.values():
        all_emails.update(em_set)
    # Filter out common false positives and compare distinct domains
    email_domains = {e.split("@")[1] for e in all_emails if "@" in e}
    if len(email_domains) > 1 and not any(d in ("gmail.com", "outlook.com", "example.com") for d in email_domains):
        conflict_urls = [u for u, ems in page_emails.items() if ems]
        findings.append({
            "check_id": "ENT-011",
            "title": f"Conflicting corporate contact emails across pages ({', '.join(sorted(all_emails)[:3])})",
            "category": "discoverability",
            "severity": "medium",
            "confidence": "high",
            "affected_urls": conflict_urls[:5],
            "evidence": (
                f"Different corporate email domains found across site pages: {sorted(all_emails)[:3]}. "
                "Conflicting contact channels impair AI assistants from routing inquiries to authoritative personnel."
            ),
            "tags": ["contact-info", "entity-identity", "contradiction"],
            "suggested_action": {
                "summary": "Ensure consistent contact email addresses and support channels across all site pages.",
                "priority": "medium",
                "effort": "low"
            }
        })
    elif len(all_emails) >= 1 and len(page_emails) >= 2:
        strengths.append({
            "title": "Contact information corroborated across multiple site pages",
            "category": "discoverability"
        })

    # Calculate deterministic entity identity confidence
    confidence_score, conf_level, confidence_signals = compute_entity_confidence(snapshot, findings)

    if confidence_score >= 0.75:
        strengths.append({
            "title": f"Entity identity strongly corroborated ({conf_level} confidence: {int(confidence_score * 100)}%)",
            "category": "discoverability"
        })

    # Priority adjustment based on page importance (Phase 4 Part 7)
    url_importance = {(p.get("url") or p.get("final_url") or ""): p.get("page_importance_score", 50) for p in pages}
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

    findings, strengths = run_checks(snapshot)
    output = {"skill": SKILL_NAME, "findings": findings, "strengths": strengths}

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"[OK] {SKILL_NAME}: {len(findings)} finding(s), {len(strengths)} strength(s) → {args.output}",
          file=sys.stderr)
    print(args.output)


if __name__ == "__main__":
    main()
