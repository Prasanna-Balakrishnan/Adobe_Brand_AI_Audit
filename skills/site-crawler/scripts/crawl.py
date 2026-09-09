#!/usr/bin/env python3
"""
crawl.py — Main crawl engine for the Brand AI-Readiness Audit marketplace.

Reads: CLI arguments (--url, --max-pages, --output, --use-js-render, --timeout)
Writes: snapshot.json to --output path

Usage:
    python crawl.py --url https://example.com --max-pages 20 --output snapshot.json
"""

import argparse
import json
import re
import sys
import time
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from robots_check import RobotsChecker
from render_dom import render_with_js, js_render_available

REQUEST_TIMEOUT = 15  # seconds per request
CRAWL_DELAY = 0.5     # minimum seconds between requests to same host
USER_AGENT = "BrandAuditBot/1.0 (+https://github.com/adobe-hackathon/brand-ai-readiness-audit)"
SKIP_EXTENSIONS = {".pdf", ".zip", ".doc", ".docx", ".xls", ".xlsx", ".ppt",
                   ".pptx", ".mp4", ".mp3", ".avi", ".mov", ".jpg", ".jpeg",
                   ".png", ".gif", ".svg", ".ico", ".woff", ".woff2", ".ttf"}
MAX_REDIRECTS = 5

PAGE_TYPES = [
    "Homepage", "About", "Contact", "Product", "Service", "Pricing",
    "Blog/article", "Documentation", "Event", "Careers", "Other/unknown"
]

PAGE_TYPE_SIGNALS = {
    "About": {
        "priority": 90,
        "url_patterns": ("/about", "/who-we-are", "/our-story", "/company", "/team", "/mission", "/overview",
                        "/a-propos", "/a-propos-de-nous", "/sobre-nosotros", "/acerca-de", "/ueber-uns", "/uber-uns", "/chi-siamo"),
        "title_keywords": ("about us", "about", "who we are", "our story", "our company", "our mission", "leadership team", "meet the team",
                          "à propos", "a propos", "sobre nosotros", "acerca de nosotros", "über uns", "ueber uns", "chi siamo"),
        "h1_keywords": ("about us", "who we are", "our mission", "our story", "about",
                       "à propos", "a propos", "sobre nosotros", "über uns", "chi siamo"),
        "schema_types": ("AboutPage",),
        "content_keywords": ("founded in", "our mission", "our vision", "our team", "leadership", "headquarters", "core values", "who we are", "our story", "company history"),
        "nav_keywords": ("about", "about us", "who we are", "company", "our story", "our team", "company info",
                        "à propos", "a propos", "sobre nosotros", "über uns", "chi siamo"),
    },
    "Contact": {
        "priority": 85,
        "url_patterns": ("/contact", "/contact-us", "/reach-us", "/get-in-touch", "/support", "/help-center",
                        "/contacto", "/kontakt", "/nous-contacter", "/contatto"),
        "title_keywords": ("contact us", "contact", "reach us", "get in touch", "support", "help center",
                          "contacto", "kontakt", "contactez-nous", "contatti"),
        "h1_keywords": ("contact us", "contact", "get in touch", "reach us",
                       "contacto", "kontakt", "contactez-nous", "contatti"),
        "schema_types": ("ContactPage",),
        "content_keywords": ("contact us", "send a message", "phone:", "email:", "get in touch", "office location", "headquarters", "support team", "customer support"),
        "nav_keywords": ("contact", "contact us", "reach us", "get in touch", "support",
                        "contacto", "kontakt", "contactez-nous"),
    },
    "Product": {
        "priority": 80,
        "url_patterns": ("/product", "/products", "/item", "/shop", "/catalog", "/store", "/platform", "/features",
                        "/produits", "/produkte", "/productos", "/prodotti"),
        "title_keywords": ("product", "products", "item", "catalog", "store", "shop",
                          "produits", "produkte", "productos"),
        "h1_keywords": ("products", "product", "features", "our products", "catalog",
                       "produits", "produkte", "productos"),
        "schema_types": ("Product", "IndividualProduct"),
        "content_keywords": ("add to cart", "in stock", "sku", "specifications", "product details", "buy now", "features & specs"),
        "nav_keywords": ("products", "platform", "features", "shop", "catalog", "store"),
    },
    "Service": {
        "priority": 80,
        "url_patterns": ("/service", "/services", "/solutions", "/offerings", "/capabilities",
                        "/servicios", "/dienstleistungen", "/prestations"),
        "title_keywords": ("service", "services", "solutions", "what we do", "offerings", "capabilities",
                          "servicios", "dienstleistungen", "prestations"),
        "h1_keywords": ("services", "solutions", "what we do", "our services"),
        "schema_types": ("Service",),
        "content_keywords": ("our services", "consulting", "managed services", "tailored solutions", "how we help", "client engagement"),
        "nav_keywords": ("services", "solutions", "offerings", "capabilities"),
    },
    "Pricing": {
        "priority": 75,
        "url_patterns": ("/pricing", "/plans", "/cost", "/subscription", "/pricing-plans",
                        "/preise", "/precios", "/tarifs", "/prezzi"),
        "title_keywords": ("pricing", "plans", "pricing & plans", "cost", "subscription",
                          "tarifs", "preise", "precios"),
        "h1_keywords": ("pricing", "plans", "pricing plans", "subscription"),
        "schema_types": ("PriceSpecification", "Offer"),
        "content_keywords": ("per month", "/mo", "/month", "/year", "billed annually", "billed monthly", "free trial", "tier", "subscription plan", "pricing plans", "$", "€", "£"),
        "nav_keywords": ("pricing", "plans", "pricing & plans", "cost", "subscription"),
    },
    "Documentation": {
        "priority": 70,
        "url_patterns": ("/docs", "/documentation", "/api", "/developers", "/guide", "/reference", "/quickstart", "/sdk"),
        "title_keywords": ("documentation", "docs", "api reference", "developer docs", "user guide", "quickstart"),
        "h1_keywords": ("documentation", "api reference", "developer guide", "api docs", "getting started"),
        "schema_types": ("TechArticle", "APIReference"),
        "content_keywords": ("api", "endpoint", "curl", "request body", "parameters", "sdk", "code example", "authentication", "api key", "json response"),
        "nav_keywords": ("documentation", "docs", "api reference", "developer docs", "quickstart"),
    },
    "Careers": {
        "priority": 65,
        "url_patterns": ("/careers", "/jobs", "/work-with-us", "/join-us", "/openings", "/job-openings",
                        "/karriere", "/empleo", "/recrutement", "/carriere"),
        "title_keywords": ("careers", "jobs", "join our team", "open positions", "work with us", "job openings",
                          "karriere", "empleo", "recrutement"),
        "h1_keywords": ("careers", "jobs", "open positions", "join our team", "work with us"),
        "schema_types": ("JobPosting",),
        "content_keywords": ("open positions", "apply now", "job openings", "we're hiring", "benefits", "competitive salary", "equal opportunity", "career opportunities"),
        "nav_keywords": ("careers", "jobs", "join our team", "open positions", "work with us"),
    },
    "Event": {
        "priority": 60,
        "url_patterns": ("/event", "/events", "/webinar", "/webinars", "/conference", "/summit"),
        "title_keywords": ("events", "conferences", "webinars", "upcoming events", "summit", "event", "webinar"),
        "h1_keywords": ("event", "events", "webinar", "conference", "summit"),
        "schema_types": ("Event",),
        "content_keywords": ("register now", "rsvp", "speakers", "agenda", "keynote", "virtual event", "date & time", "save your spot"),
        "nav_keywords": ("events", "conferences", "webinars", "upcoming events"),
    },
    "Blog/article": {
        "priority": 50,
        "url_patterns": ("/blog", "/article", "/articles", "/news", "/posts", "/insights", "/stories"),
        "title_keywords": ("blog", "insights", "latest news", "articles", "news", "posts"),
        "h1_keywords": ("blog", "insights", "latest news", "articles"),
        "schema_types": ("BlogPosting", "Article", "NewsArticle"),
        "content_keywords": ("min read", "published on", "author:", "reading time", "share this article", "related posts", "posted on"),
        "nav_keywords": ("blog", "news", "articles", "insights"),
    },
}


def _collect_schema_types(json_ld_blocks: list) -> set:
    """Recursively collect all Schema.org @type values from JSON-LD blocks."""
    types = set()

    def _extract_from_obj(obj):
        if isinstance(obj, dict):
            t = obj.get("@type")
            if isinstance(t, str):
                types.add(t)
            elif isinstance(t, list):
                for item in t:
                    if isinstance(item, str):
                        types.add(item)
            for v in obj.values():
                _extract_from_obj(v)
        elif isinstance(obj, list):
            for item in obj:
                _extract_from_obj(item)

    for block in (json_ld_blocks or []):
        _extract_from_obj(block)
    return types


def _score_content_signals(text: str) -> dict:
    """Score semantic content keyword density for various page types."""
    if not text:
        return {}
    text_lower = text.lower()
    scores = {}
    for ptype, cfg in PAGE_TYPE_SIGNALS.items():
        kw_list = cfg.get("content_keywords", ())
        cnt = sum(1 for kw in kw_list if kw in text_lower)
        if cnt > 0:
            scores[ptype] = cnt
    return scores


def _extract_nav_link_texts(soup: BeautifulSoup) -> list:
    """Extract navigation link anchor texts from nav and header elements."""
    if not soup:
        return []
    nav_texts = []
    nav_elements = soup.find_all(["nav", "header"])
    nav_elements.extend(soup.find_all(attrs={"role": lambda r: r in ("navigation", "menubar")}))
    for elem in nav_elements:
        for a in elem.find_all("a"):
            txt = a.get_text(strip=True)
            if txt and len(txt) <= 60 and txt not in nav_texts:
                nav_texts.append(txt)
    return nav_texts


def classify_page_type(url: str, start_url: str = "", title: str = "",
                       h1_list: list = None, headings: list = None,
                       json_ld_blocks: list = None, soup: BeautifulSoup = None,
                       visible_text: str = "", nav_anchors: list = None) -> tuple:
    """
    Contextually and generally classify the page into one of the 11 designated PAGE_TYPES.
    Combines:
      1. Structural URL patterns and homepage detection
      2. Exhaustive Schema.org @type signals
      3. Title and H1 heading semantics
      4. Navigation link anchor text
      5. Observable content keywords and density
    Returns (page_type, confidence) where confidence is 'high', 'medium', or 'low'.
    """
    p_url = urlparse(url)
    path = p_url.path.lower().rstrip("/")
    start_path = urlparse(start_url).path.lower().rstrip("/") if start_url else ""
    title_lower = (title or "").lower()
    h1_combined = " ".join((h or "").lower() for h in (h1_list or []))
    schema_types = _collect_schema_types(json_ld_blocks or [])

    # 1. Homepage
    if path == "" or path == "/" or (start_path and path == start_path) or path in ("/index.html", "/index.php", "/home"):
        return "Homepage", "high"

    # 2. Strong Schema.org type associations (definitive)
    schema_map = {
        "JobPosting": "Careers",
        "Event": "Event",
        "BlogPosting": "Blog/article",
        "Article": "Blog/article",
        "NewsArticle": "Blog/article",
        "Product": "Product",
        "IndividualProduct": "Product",
        "SoftwareApplication": "Product",
        "MenuItem": "Product",
        "Service": "Service",
        "Course": "Service",
        "MedicalProcedure": "Service",
        "AboutPage": "About",
        "ContactPage": "Contact",
        "TechArticle": "Documentation",
        "APIReference": "Documentation"
    }
    for st, ptype in schema_map.items():
        if st in schema_types:
            return ptype, "high"

    # 3. Multi-signal scoring across categories
    nav_text_combined = " ".join(t.lower() for t in (nav_anchors or []))
    content_scores = _score_content_signals(visible_text)

    scores = {}
    for ptype, cfg in PAGE_TYPE_SIGNALS.items():
        s = 0
        patterns = cfg.get("url_patterns", ())
        title_keys = cfg.get("title_keywords", ())
        h1_keys = cfg.get("h1_keywords", ())
        nav_keys = cfg.get("nav_keywords", ())

        # Exact path or path segment match
        if any(p == path or path.startswith(p + "/") or path.endswith(p) or f"{p}/" in path for p in patterns):
            s += 45
        elif any(p.lstrip("/") in path for p in patterns if len(p) > 4):
            s += 25

        # Title keyword match
        if any(k in title_lower for k in title_keys):
            s += 35

        # H1 keyword match
        if any(k in h1_combined for k in h1_keys):
            s += 30

        # Nav anchor text matching
        if any(k in nav_text_combined for k in nav_keys):
            s += 15

        # Content keyword signal
        c_count = content_scores.get(ptype, 0)
        if c_count >= 3:
            s += 25
        elif c_count >= 1:
            s += 12

        if s > 0:
            scores[ptype] = s

    if scores:
        best_type, best_score = max(scores.items(), key=lambda x: x[1])
        if best_score >= 45:
            return best_type, "high"
        elif best_score >= 20:
            return best_type, "medium"

    return "Other/unknown", "low"


def detect_page_type(url: str, start_url: str, title: str, h1_list: list,
                     headings: list, json_ld_blocks: list, soup: BeautifulSoup) -> str:
    """
    Contextually classify the page type into one of the 11 designated types.
    Delegates to classify_page_type, retaining 100% backward compatibility with
    the existing signature and return type.
    """
    visible_text = ""
    nav_anchors = []
    if soup:
        nav_anchors = _extract_nav_link_texts(soup)
        visible_text = soup.get_text(separator=" ", strip=True)

    ptype, _ = classify_page_type(
        url=url,
        start_url=start_url,
        title=title,
        h1_list=h1_list,
        headings=headings,
        json_ld_blocks=json_ld_blocks,
        soup=soup,
        visible_text=visible_text,
        nav_anchors=nav_anchors
    )
    return ptype


def parse_args():
    p = argparse.ArgumentParser(description="Brand AI-Readiness Audit — Site Crawler")
    p.add_argument("--url", required=True, help="Start URL to crawl")
    p.add_argument("--max-pages", type=int, default=20, help="Maximum pages to crawl")
    p.add_argument("--output", default="snapshot.json", help="Output path for snapshot.json")
    p.add_argument("--use-js-render", action="store_true", help="Enable Playwright JS rendering")
    p.add_argument("--timeout", type=int, default=240, help="Total crawl timeout in seconds")
    return p.parse_args()


def normalise_url(url: str) -> str:
    """Remove fragment; normalize bare root path to /."""
    parsed = urlparse(url)
    path = parsed.path or "/"
    clean = parsed._replace(fragment="", path=path).geturl()
    return clean


def same_origin(url: str, origin_parsed) -> bool:
    p = urlparse(url)
    return (p.scheme == origin_parsed.scheme and
            p.netloc == origin_parsed.netloc)


def should_skip_url(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return True
    path = parsed.path.lower()
    for ext in SKIP_EXTENSIONS:
        if path.endswith(ext):
            return True
    return False


def is_repetitive_leaf(url: str) -> tuple[bool, str | None]:
    """
    Check if URL is an individual repetitive leaf page (e.g. specific blog post, specific product)
    rather than a main hub/category page.
    Returns (is_leaf, leaf_type).
    """
    parsed = urlparse(url)
    path = parsed.path.lower().rstrip("/")
    segments = [s for s in path.split("/") if s]
    if not segments:
        return False, None

    # Date-based post path e.g. /2026/01/post-name or /2024/post-name
    if re.search(r'/(?:19|20)\d{2}(?:/\d{1,2})?/[a-z0-9_-]+', path):
        return True, "blog_leaf"

    # Blog / News / Article leaf (depth > 1 under the root segment)
    blog_roots = {"blog", "article", "articles", "posts", "news", "insights"}
    if segments[0] in blog_roots:
        if len(segments) > 1:
            return True, "blog_leaf"
        return False, None  # /blog itself is the hub

    # Product / Item leaf (depth > 1 under the root segment)
    product_roots = {"product", "products", "item", "items", "p", "shop", "store", "catalog"}
    if segments[0] in product_roots:
        if len(segments) > 1:
            return True, "product_leaf"
        return False, None  # /products or /shop itself is the hub

    return False, None


def score_url_priority(url: str, link_text: str = "", depth: int = 1) -> tuple[int, str]:
    """
    Score discovered URL priority to ensure high-value diverse pages are crawled
    within the max-pages budget. Higher score = crawled earlier.

    Priority hierarchy:
      1. Homepage (100)
      2. About (90)
      3. Contact (85)
      4. Products/Services (80)
      5. Pricing (75)
      6. Documentation (70)
      7. Careers (65)
      8. Events (60)
      9. Category / Hub Listing Pages (50)
      10. Representative Internal Pages (40)
      11. Repetitive Leaf Items (30)
      12. Deep / Utility Pages (20)

    Returns (priority_score, estimated_category).
    """
    parsed = urlparse(url)
    path = parsed.path.lower().rstrip("/")
    link_lower = link_text.strip().lower()
    segments = [s for s in path.split("/") if s]

    # 1. Homepage (Score 100)
    if not path or depth == 0 or path in ("/index.html", "/index.php", "/home"):
        return 100, "Homepage"

    is_leaf, leaf_type = is_repetitive_leaf(url)

    # 2-8. High priority categories driven by PAGE_TYPE_SIGNALS
    priority_order = ["About", "Contact", "Product", "Service", "Pricing", "Documentation", "Careers", "Event"]
    for cat in priority_order:
        cfg = PAGE_TYPE_SIGNALS.get(cat, {})
        patterns = cfg.get("url_patterns", ())
        nav_keys = cfg.get("nav_keywords", ())
        title_keys = cfg.get("title_keywords", ())
        h1_keys = cfg.get("h1_keywords", ())

        if is_leaf and cat in ("Product", "Service"):
            continue

        path_match = any(p == path or path.startswith(p + "/") or path.endswith(p) for p in patterns)
        link_match = any(w in link_lower for w in nav_keys) or any(w in link_lower for w in title_keys) or any(w in link_lower for w in h1_keys)

        if cat == "About" and any(cw in link_lower for cw in ("join", "careers", "jobs", "hiring")):
            continue

        if path_match or link_match:
            display_cat = "Products/Services" if cat in ("Product", "Service") else ("Events" if cat == "Event" else cat)
            return cfg.get("priority", 50), display_cat

    # Check repetitive leaf before category hubs so /blog/post-1 gets Score 30, not Score 50
    if is_leaf:
        return 30, leaf_type or "Repetitive_Leaf"

    # 9. Important Category / Hub Pages (Score 50)
    # Shallow depth hub pages like /blog, /news, /shop, /catalog, /resources
    hub_roots = {"blog", "news", "articles", "shop", "store", "catalog", "categories", "resources", "case-studies"}
    if segments and segments[0] in hub_roots and len(segments) <= 1:
        return 50, "Category/Hub"
    if any(w in link_lower for w in ("blog", "news", "catalog", "shop all", "resources", "case studies")):
        return 50, "Category/Hub"

    # 10. Representative Internal Pages (Score 40)
    # Direct links from homepage with short, clean paths (<= 2 segments)
    if depth <= 1 and len(segments) <= 2:
        return 40, "Representative"

    # 12. Deep / Utility Pages (Score 20)
    # Long paths, pagination, tag filters
    if any(p in path for p in ("/tag/", "/tags/", "/page/", "/archive/", "/author/")) or len(segments) > 3 or parsed.query:
        return 20, "Utility/Deep"

    return 35, "Internal"


def extract_page_data(url: str, html: str, http_status: int,
                      redirect_chain: list, response_headers: dict,
                      crawled_with_js: bool, start_url: str = "",
                      raw_text_len: int = 0, rendered_text_len: int = 0,
                      js_dependent: bool = False, raw_html_len: int = 0) -> dict:
    """Parse HTML and extract all fields required by snapshot.json schema."""
    soup = BeautifulSoup(html, "html.parser")

    # Canonical
    canonical_tag = soup.find("link", rel="canonical")
    canonical = canonical_tag["href"] if canonical_tag and canonical_tag.get("href") else None

    # Final URL
    final_url = redirect_chain[-1] if redirect_chain else url

    # Canonical conflict check (Req 2)
    canonical_conflict = False
    if canonical:
        p_canon = urlparse(canonical)
        p_final = urlparse(final_url)
        # Check if canonical points to a different domain or substantially different path
        if p_canon.netloc and p_final.netloc and p_canon.netloc != p_final.netloc:
            canonical_conflict = True
        elif p_canon.path.rstrip("/") != p_final.path.rstrip("/"):
            canonical_conflict = True

    # Redirect loop check (Req 2)
    redirect_loop = False
    if redirect_chain and len(redirect_chain) > len(set(redirect_chain)):
        redirect_loop = True
    elif len(redirect_chain) >= 5 or http_status == 310:
        redirect_loop = True

    # Meta robots
    meta_robots_tag = soup.find("meta", attrs={"name": lambda v: v and v.lower() == "robots"})
    meta_robots = meta_robots_tag.get("content", "") if meta_robots_tag else ""

    # X-Robots-Tag
    x_robots_tag = response_headers.get("X-Robots-Tag", "") or response_headers.get("x-robots-tag", "")

    # Title
    title_tag = soup.find("title")
    title = title_tag.get_text(strip=True) if title_tag else ""

    # Meta description
    meta_desc_tag = soup.find("meta", attrs={"name": lambda v: v and v.lower() == "description"})
    meta_description = meta_desc_tag.get("content", "") if meta_desc_tag else ""

    # H1 tags
    h1_tags = [t.get_text(strip=True) for t in soup.find_all("h1")]

    # All headings in order
    headings = []
    for tag in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"]):
        level = int(tag.name[1])
        text = tag.get_text(strip=True)
        if text:
            headings.append({"level": level, "text": text})

    # JSON-LD
    json_ld_blocks = []
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            raw = (script.string or script.get_text() or "").strip()
            if raw:
                data = json.loads(raw)
                json_ld_blocks.append(data)
        except (json.JSONDecodeError, TypeError):
            pass

    # Open Graph
    open_graph = {}
    for tag in soup.find_all("meta", property=True):
        prop = tag.get("property", "")
        if prop.startswith("og:"):
            open_graph[prop] = tag.get("content", "")

    # Twitter Card
    twitter_card = {}
    for tag in soup.find_all("meta", attrs={"name": True}):
        name = tag.get("name", "")
        if name.startswith("twitter:"):
            twitter_card[name] = tag.get("content", "")

    # Links
    links = []
    origin_parsed = urlparse(url)
    seen_hrefs = set()
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if not href or href.startswith("#") or href.startswith("javascript:"):
            continue
        full_href = urljoin(url, href)
        full_href = normalise_url(full_href)
        if full_href in seen_hrefs:
            continue
        seen_hrefs.add(full_href)
        is_internal = same_origin(full_href, origin_parsed)
        links.append({
            "href": full_href,
            "text": a.get_text(strip=True)[:200],
            "is_internal": is_internal
        })

    # Images
    images = []
    for img in soup.find_all("img"):
        src = img.get("src", "")
        if src:
            src = urljoin(url, src)
        images.append({
            "src": src,
            "alt": img.get("alt", ""),
            "width": img.get("width"),
            "height": img.get("height")
        })

    nav_link_texts = _extract_nav_link_texts(soup)

    # Visible text
    for tag in soup(["script", "style", "noscript", "head"]):
        tag.decompose()
    visible_text = soup.get_text(separator=" ", strip=True)
    visible_text_length = len(visible_text)
    visible_text_sample = visible_text[:500]

    # Page type classification (Req 5)
    page_type, classification_confidence = classify_page_type(
        url=url,
        start_url=start_url or url,
        title=title,
        h1_list=h1_tags,
        headings=headings,
        json_ld_blocks=json_ld_blocks,
        soup=soup,
        visible_text=visible_text,
        nav_anchors=nav_link_texts
    )

    # Last-Modified
    last_modified = response_headers.get("Last-Modified") or response_headers.get("last-modified")
    if not last_modified:
        # Check meta tags for date
        for meta in soup.find_all("meta"):
            prop = (meta.get("property", "") or meta.get("name", "") or "").lower()
            if "modified" in prop or "published" in prop or "date" in prop:
                last_modified = meta.get("content", "")
                break

    actual_raw_len = raw_html_len or len(html)
    actual_raw_text = raw_text_len or visible_text_length
    actual_rend_text = rendered_text_len or (visible_text_length if crawled_with_js else actual_raw_text)

    return {
        "url": url,
        "status_code": http_status,
        "final_url": final_url,
        "redirect_chain": redirect_chain[:-1] if redirect_chain else [],
        "redirect_loop": redirect_loop,
        "canonical": canonical,
        "canonical_conflict": canonical_conflict,
        "meta_robots": meta_robots,
        "x_robots_tag": x_robots_tag,
        "page_type": page_type,
        "classification_confidence": classification_confidence,
        "title": title,
        "meta_description": meta_description,
        "h1": h1_tags,
        "headings": headings,
        "json_ld": json_ld_blocks,
        "open_graph": open_graph,
        "twitter_card": twitter_card,
        "links": links,
        "nav_link_texts": nav_link_texts[:30],
        "images": images,
        "visible_text_length": visible_text_length,
        "visible_text_sample": visible_text_sample,
        "last_modified": last_modified,
        "crawled_with_js": crawled_with_js,
        "js_render_available": js_render_available(),
        "raw_html_length": actual_raw_len,
        "raw_text_length": actual_raw_text,
        "rendered_text_length": actual_rend_text,
        "js_dependent_content": js_dependent,
        "content_disparity": max(0, actual_rend_text - actual_raw_text)
    }


def fetch_page(url: str, session: requests.Session, use_js: bool) -> tuple:
    """
    Returns (html, status, redirect_chain, headers, crawled_with_js,
             raw_html_len, raw_text_len, rendered_text_len, js_dependent).
    """
    try:
        resp = session.get(
            url,
            timeout=REQUEST_TIMEOUT,
            allow_redirects=True,
            stream=False
        )
        redirect_chain = [r.url for r in resp.history] + [resp.url]
        raw_html = resp.text
        html = raw_html
        status = resp.status_code
        headers = dict(resp.headers)
        crawled_with_js = False
        raw_html_len = len(raw_html)
        raw_text_len = 0
        rendered_text_len = 0
        js_dependent = False

        # Adaptive JS render check (Req 3):
        # Inspect raw HTML first. Render only when meaningful content appears to depend on JS.
        if use_js and js_render_available():
            has_spa_root = (
                '<div id="root">' in raw_html or
                '<div id="app">' in raw_html or
                'data-reactroot' in raw_html or
                '__NEXT_DATA__' in raw_html or
                '__nuxt' in raw_html
            )
            # Only parse if suspected SPA or small HTML (<2000 chars)
            if has_spa_root or raw_html_len < 2000:
                raw_soup = BeautifulSoup(raw_html, "html.parser")
                for tag in raw_soup(["script", "style", "noscript", "head"]):
                    tag.decompose()
                raw_text_len = len(raw_soup.get_text(separator=" ", strip=True))
                rendered_text_len = raw_text_len
                raw_h1_count = len(raw_soup.find_all("h1"))
                if (raw_text_len < 1000 and (has_spa_root or raw_h1_count == 0)):
                    js_html = render_with_js(resp.url)
                    if js_html:
                        html = js_html
                        crawled_with_js = True
                        rend_soup = BeautifulSoup(js_html, "html.parser")
                        for tag in rend_soup(["script", "style", "noscript", "head"]):
                            tag.decompose()
                        rendered_text_len = len(rend_soup.get_text(separator=" ", strip=True))
                        # Check if important content was only available after rendering (Req 3)
                        if (rendered_text_len - raw_text_len > 300) or (raw_h1_count == 0 and len(rend_soup.find_all("h1")) > 0):
                            js_dependent = True

        return html, status, redirect_chain, headers, crawled_with_js, raw_html_len, raw_text_len, rendered_text_len, js_dependent

    except requests.exceptions.TooManyRedirects:
        return "", 310, [url], {}, False, 0, 0, 0, False
    except requests.exceptions.Timeout:
        return "", 408, [url], {}, False, 0, 0, 0, False
    except requests.exceptions.ConnectionError:
        # retry once
        time.sleep(2)
        try:
            resp = session.get(url, timeout=REQUEST_TIMEOUT, allow_redirects=True)
            redirect_chain = [r.url for r in resp.history] + [resp.url]
            raw_len = len(resp.text)
            return resp.text, resp.status_code, redirect_chain, dict(resp.headers), False, raw_len, 0, 0, False
        except Exception:
            return "", 0, [url], {}, False, 0, 0, 0, False
    except Exception as e:
        print(f"[WARN] Unexpected error fetching {url}: {e}", file=sys.stderr)
        return "", 0, [url], {}, False, 0, 0, 0, False



def compute_page_importance_scores(pages: list) -> list:
    """
    Compute generic importance score (0-100) for each crawled page based on
    internal-link relationships, structural depth, and navigation presence.
    Additive: modifies each page dict in-place and returns pages.
    """
    if not pages:
        return pages

    valid_pages = [p for p in pages if isinstance(p, dict)]
    if not valid_pages:
        return pages

    norm_to_page = {}
    for p in valid_pages:
        u = normalise_url(p.get("url", ""))
        norm_to_page[u] = p
        p.setdefault("incoming_link_count", 0)
        p.setdefault("page_importance_score", 0)

    incoming_counts = {u: 0 for u in norm_to_page}
    nav_linked_urls = set()

    for p in valid_pages:
        page_links = p.get("links") or []
        nav_texts = set(t.lower() for t in (p.get("nav_link_texts") or []) if isinstance(t, str))
        seen_targets_on_page = set()
        for link in page_links:
            if not isinstance(link, dict) or not link.get("is_internal"):
                continue
            target_norm = normalise_url(link.get("href") or "")
            if target_norm in incoming_counts and target_norm not in seen_targets_on_page:
                seen_targets_on_page.add(target_norm)
                incoming_counts[target_norm] += 1
                if (link.get("text") or "").strip().lower() in nav_texts:
                    nav_linked_urls.add(target_norm)

    max_incoming = max(incoming_counts.values()) if incoming_counts else 0

    for u, p in norm_to_page.items():
        in_count = incoming_counts.get(u, 0)
        p["incoming_link_count"] = in_count

        # Base score from incoming link frequency (0 to 50)
        link_ratio = (in_count / max_incoming) if max_incoming > 0 else 0.0
        score = link_ratio * 50.0

        # Nav boost: linked from nav menus (+25)
        if u in nav_linked_urls:
            score += 25.0

        # Page type structural boost (+25 for Homepage, +15 for core conversion/info, +10 for docs/careers)
        ptype = p.get("page_type", "")
        if ptype == "Homepage":
            score += 25.0
        elif ptype in ("About", "Contact", "Pricing", "Product", "Service"):
            score += 15.0
        elif ptype in ("Documentation", "Careers"):
            score += 10.0

        p["page_importance_score"] = int(min(100, max(0, round(score))))

    return pages


def main():
    args = parse_args()
    start_url = normalise_url(args.url)
    origin_parsed = urlparse(start_url)
    crawl_start = datetime.now(timezone.utc)

    # robots.txt check
    checker = RobotsChecker(start_url, USER_AGENT)
    robots_status = checker.robots_status
    disallowed_paths = checker.disallowed_paths
    crawl_delay = checker.crawl_delay or CRAWL_DELAY

    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})

    pages = []
    visited = set()
    queue: list[dict] = []
    queued_urls = set()
    discovered_urls = set()
    skipped_urls_count = 0
    failed_pages = []
    page_type_counts = {}
    repetitive_counts = {"blog_leaf": 0, "product_leaf": 0}
    discovery_counter = 0

    if checker.is_allowed(start_url):
        queue.append({
            "url": start_url,
            "priority": 100,
            "depth": 0,
            "order": discovery_counter
        })
        queued_urls.add(start_url)
        discovered_urls.add(start_url)
    else:
        print(f"[WARN] start_url {start_url} is disallowed by robots.txt. Aborting.", file=sys.stderr)

    timeout_hit = False
    last_request_time = 0.0
    queue_needs_sort = True

    while queue and len(visited) < args.max_pages:
        # Check total timeout
        elapsed = (datetime.now(timezone.utc) - crawl_start).total_seconds()
        if elapsed >= args.timeout:
            timeout_hit = True
            print(f"[INFO] Crawl timeout reached after {elapsed:.1f}s", file=sys.stderr)
            break

        # Deterministic priority ordering: highest priority first (-priority), lowest depth first (depth), earliest discovery order (order)
        if queue_needs_sort:
            queue.sort(key=lambda item: (-item["priority"], item["depth"], item["order"]))
            queue_needs_sort = False
        current_item = queue.pop(0)
        url = current_item.get("url") or current_item.get("final_url") or ""
        current_depth = current_item["depth"]

        if url in visited:
            continue
        if should_skip_url(url):
            continue
        if not checker.is_allowed(url):
            continue

        # Rate limiting
        now = time.time()
        wait = crawl_delay - (now - last_request_time)
        if wait > 0:
            time.sleep(wait)
        last_request_time = time.time()

        print(f"[INFO] Crawling ({len(visited)+1}/{args.max_pages}): {url}", file=sys.stderr)
        (html, status, redirect_chain, headers, crawled_with_js,
         raw_html_len, raw_text_len, rendered_text_len, js_dependent) = fetch_page(
            url, session, args.use_js_render
        )
        visited.add(url)
        if redirect_chain:
            for red_u in redirect_chain:
                norm_red = normalise_url(red_u)
                visited.add(norm_red)
                queued_urls.add(norm_red)

        # Track failed pages
        if status >= 400 or status == 0:
            failed_pages.append({"url": url, "status_code": status})

        # Skip empty responses
        if not html and status == 0:
            pages.append({
                "url": url,
                "status_code": 0,
                "final_url": url,
                "redirect_chain": [],
                "redirect_loop": False,
                "canonical": None,
                "canonical_conflict": False,
                "meta_robots": "",
                "x_robots_tag": "",
                "page_type": "Other/unknown",
                "title": "",
                "meta_description": "",
                "h1": [],
                "headings": [],
                "json_ld": [],
                "open_graph": {},
                "twitter_card": {},
                "links": [],
                "images": [],
                "visible_text_length": 0,
                "visible_text_sample": "",
                "last_modified": None,
                "crawled_with_js": False,
                "js_render_available": js_render_available(),
                "raw_html_length": 0,
                "raw_text_length": 0,
                "rendered_text_length": 0,
                "js_dependent_content": False,
                "content_disparity": 0
            })
            continue

        page_data = extract_page_data(
            url, html, status, redirect_chain, headers, crawled_with_js,
            start_url=start_url, raw_text_len=raw_text_len,
            rendered_text_len=rendered_text_len, js_dependent=js_dependent,
            raw_html_len=raw_html_len
        )
        pages.append(page_data)
        p_type = page_data.get("page_type", "Other/unknown")
        page_type_counts[p_type] = page_type_counts.get(p_type, 0) + 1

        # Enqueue internal links from successful pages
        if status < 400:
            for link in page_data["links"]:
                href = link["href"]
                link_text = link.get("text", "")
                if link["is_internal"]:
                    discovered_urls.add(href)
                    if (href not in visited and
                            href not in queued_urls and
                            not should_skip_url(href) and
                            checker.is_allowed(href)):
                        # Bound crawl: safeguard against repetitive leaf explosion (max 3 per leaf type)
                        is_leaf, leaf_type = is_repetitive_leaf(href)
                        if is_leaf and leaf_type:
                            if repetitive_counts.get(leaf_type, 0) >= 3:
                                skipped_urls_count += 1
                                continue
                            repetitive_counts[leaf_type] = repetitive_counts.get(leaf_type, 0) + 1

                        discovery_counter += 1
                        priority, est_type = score_url_priority(href, link_text=link_text, depth=current_depth + 1)
                        queue.append({
                            "url": href,
                            "priority": priority,
                            "depth": current_depth + 1,
                            "order": discovery_counter
                        })
                        queued_urls.add(href)
                        queue_needs_sort = True

    crawl_end = datetime.now(timezone.utc)
    crawl_duration = round((crawl_end - crawl_start).total_seconds(), 2)
    pages = compute_page_importance_scores(pages)

    # Crawl coverage metrics (Req 20)
    js_status = "adaptive_rendered" if any(p.get("crawled_with_js") for p in pages) else ("not_needed" if args.use_js_render else "disabled")

    snapshot = {
        "crawl_meta": {
            "start_url": start_url,
            "crawl_started_at": crawl_start.isoformat().replace("+00:00", "Z"),
            "crawl_ended_at": crawl_end.isoformat().replace("+00:00", "Z"),
            "crawl_duration_seconds": crawl_duration,
            "pages_discovered": len(discovered_urls) + 1,
            "pages_crawled": len(pages),
            "pages_skipped": skipped_urls_count,
            "failed_pages": failed_pages,
            "max_pages": args.max_pages,
            "robots_txt_respected": True,
            "robots_txt_url": checker.robots_url,
            "robots_txt_status": robots_status,
            "disallowed_paths": disallowed_paths,
            "sitemaps": checker.sitemaps,
            "ai_agent_rules": checker.ai_agent_rules,
            "js_rendering_status": js_status,
            "page_types_found": page_type_counts,
            "crawl_timeout_hit": timeout_hit
        },
        "pages": pages
    }

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(snapshot, f, indent=2, ensure_ascii=False)

    print(f"[OK] Snapshot written to {args.output} ({len(pages)} pages)", file=sys.stderr)
    print(args.output)  # stdout: path for orchestrator to read


if __name__ == "__main__":
    main()
