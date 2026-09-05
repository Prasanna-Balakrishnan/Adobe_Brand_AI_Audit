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


def detect_page_type(url: str, start_url: str, title: str, h1_list: list,
                     headings: list, json_ld_blocks: list, soup: BeautifulSoup) -> str:
    """
    Contextually classify the page type into one of the 11 designated types.
    Uses URL paths, page titles, H1 headings, and Schema.org types.
    """
    p_url = urlparse(url)
    path = p_url.path.lower().rstrip("/")
    start_path = urlparse(start_url).path.lower().rstrip("/")
    title_lower = (title or "").lower()
    h1_combined = " ".join((h or "").lower() for h in h1_list)

    # 1. Homepage
    if path == "" or path == "/" or path == start_path or path in ("/index.html", "/index.php", "/home"):
        return "Homepage"

    # Schema types helper
    schema_types = set()
    for block in json_ld_blocks:
        if isinstance(block, dict):
            t = block.get("@type")
            if isinstance(t, str):
                schema_types.add(t)
            elif isinstance(t, list):
                schema_types.update(t)
            for node in block.get("@graph", []):
                if isinstance(node, dict):
                    nt = node.get("@type")
                    if isinstance(nt, str):
                        schema_types.add(nt)
                    elif isinstance(nt, list):
                        schema_types.update(nt)

    # 2. Contact
    if any(k in path for k in ("/contact", "/reach-us", "/get-in-touch", "/support", "/help-center")):
        return "Contact"
    if "contact" in title_lower or "contact us" in h1_combined:
        return "Contact"

    # 3. About
    if any(k in path for k in ("/about", "/who-we-are", "/our-story", "/company", "/team", "/mission")):
        return "About"
    if "about us" in title_lower or "about" in title_lower or "who we are" in h1_combined:
        return "About"

    # 4. Pricing
    if any(k in path for k in ("/pricing", "/plans", "/cost", "/subscription")):
        return "Pricing"
    if "pricing" in title_lower or "pricing" in h1_combined or "plans" in h1_combined:
        return "Pricing"

    # 5. Careers
    if any(k in path for k in ("/careers", "/jobs", "/work-with-us", "/join-us", "/openings")):
        return "Careers"
    if "careers" in title_lower or "jobs" in title_lower or "open positions" in h1_combined:
        return "Careers"

    # 6. Documentation
    if any(k in path for k in ("/docs", "/documentation", "/api", "/developers", "/guide", "/reference")):
        return "Documentation"
    if "documentation" in title_lower or "api reference" in title_lower or "user guide" in title_lower:
        return "Documentation"

    # 7. Event
    if any(k in path for k in ("/event", "/events", "/webinar", "/webinars", "/conference")):
        return "Event"
    if "Event" in schema_types or "webinar" in title_lower:
        return "Event"

    # 8. Blog / article
    if any(k in path for k in ("/blog", "/article", "/articles", "/news", "/posts", "/insights")):
        return "Blog/article"
    if any(st in schema_types for st in ("BlogPosting", "Article", "NewsArticle")):
        return "Blog/article"

    # 9. Product
    if any(k in path for k in ("/product", "/products", "/item", "/shop", "/catalog", "/store")):
        return "Product"
    if any(st in schema_types for st in ("Product", "IndividualProduct")):
        return "Product"

    # 10. Service
    if any(k in path for k in ("/service", "/services", "/solutions", "/offerings")):
        return "Service"
    if "Service" in schema_types:
        return "Service"

    return "Other/unknown"


def parse_args():
    p = argparse.ArgumentParser(description="Brand AI-Readiness Audit — Site Crawler")
    p.add_argument("--url", required=True, help="Start URL to crawl")
    p.add_argument("--max-pages", type=int, default=20, help="Maximum pages to crawl")
    p.add_argument("--output", default="snapshot.json", help="Output path for snapshot.json")
    p.add_argument("--use-js-render", action="store_true", help="Enable Playwright JS rendering")
    p.add_argument("--timeout", type=int, default=240, help="Total crawl timeout in seconds")
    return p.parse_args()


def normalise_url(url: str) -> str:
    """Remove fragment; strip trailing slash only from bare roots."""
    parsed = urlparse(url)
    clean = parsed._replace(fragment="").geturl()
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
            data = json.loads(script.string or "")
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

    # Visible text
    for tag in soup(["script", "style", "noscript", "head"]):
        tag.decompose()
    visible_text = soup.get_text(separator=" ", strip=True)
    visible_text_length = len(visible_text)
    visible_text_sample = visible_text[:500]

    # Page type classification (Req 5)
    page_type = detect_page_type(url, start_url or url, title, h1_tags, headings, json_ld_blocks, soup)

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
        "title": title,
        "meta_description": meta_description,
        "h1": h1_tags,
        "headings": headings,
        "json_ld": json_ld_blocks,
        "open_graph": open_graph,
        "twitter_card": twitter_card,
        "links": links,
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
        raw_soup = BeautifulSoup(raw_html, "html.parser")
        for tag in raw_soup(["script", "style", "noscript", "head"]):
            tag.decompose()
        raw_text_len = len(raw_soup.get_text(separator=" ", strip=True))
        rendered_text_len = raw_text_len
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
            raw_h1_count = len(BeautifulSoup(raw_html, "html.parser").find_all("h1"))
            # Render if text is suspiciously low (< 1000) with SPA root or missing H1
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
    queue = []
    discovered_urls = set()
    skipped_urls_count = 0
    failed_pages = []
    page_type_counts = {}

    if checker.is_allowed(start_url):
        queue.append(start_url)
        discovered_urls.add(start_url)
    else:
        print(f"[WARN] start_url {start_url} is disallowed by robots.txt. Aborting.", file=sys.stderr)

    timeout_hit = False
    last_request_time = 0.0

    while queue and len(visited) < args.max_pages:
        # Check total timeout
        elapsed = (datetime.now(timezone.utc) - crawl_start).total_seconds()
        if elapsed >= args.timeout:
            timeout_hit = True
            print(f"[INFO] Crawl timeout reached after {elapsed:.1f}s", file=sys.stderr)
            break

        url = queue.pop(0)
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
                if link["is_internal"]:
                    discovered_urls.add(href)
                    if (href not in visited and
                            href not in queue and
                            not should_skip_url(href) and
                            checker.is_allowed(href)):
                        # Bound crawl: max 3 representative pages per repetitive type (Req 2, 24)
                        # Estimate type from path:
                        path_lower = urlparse(href).path.lower()
                        is_repetitive = any(seg in path_lower for seg in ("/blog", "/article", "/posts", "/news", "/item/", "/product/"))
                        est_type = "Blog/article" if any(seg in path_lower for seg in ("/blog", "/article", "/posts", "/news")) else ("Product" if any(seg in path_lower for seg in ("/item/", "/product/")) else None)
                        if est_type and page_type_counts.get(est_type, 0) >= 3:
                            skipped_urls_count += 1
                            continue
                        queue.append(href)

    crawl_end = datetime.now(timezone.utc)
    crawl_duration = round((crawl_end - crawl_start).total_seconds(), 2)

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
