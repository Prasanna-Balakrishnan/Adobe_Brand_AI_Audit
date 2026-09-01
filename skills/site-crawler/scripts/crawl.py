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
                      crawled_with_js: bool) -> dict:
    """Parse HTML and extract all fields required by snapshot.json schema."""
    soup = BeautifulSoup(html, "html.parser")

    # Canonical
    canonical_tag = soup.find("link", rel="canonical")
    canonical = canonical_tag["href"] if canonical_tag and canonical_tag.get("href") else None

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

    # Last-Modified
    last_modified = response_headers.get("Last-Modified") or response_headers.get("last-modified")
    if not last_modified:
        # Check meta tags for date
        for meta in soup.find_all("meta"):
            prop = (meta.get("property", "") or meta.get("name", "") or "").lower()
            if "modified" in prop or "published" in prop or "date" in prop:
                last_modified = meta.get("content", "")
                break

    return {
        "url": url,
        "status_code": http_status,
        "final_url": redirect_chain[-1] if redirect_chain else url,
        "redirect_chain": redirect_chain[:-1] if redirect_chain else [],
        "canonical": canonical,
        "meta_robots": meta_robots,
        "x_robots_tag": x_robots_tag,
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
        "raw_html_length": len(html)
    }


def fetch_page(url: str, session: requests.Session, use_js: bool) -> tuple:
    """
    Returns (html, status_code, redirect_chain, response_headers, crawled_with_js).
    redirect_chain includes the final URL as last element.
    """
    try:
        resp = session.get(
            url,
            timeout=REQUEST_TIMEOUT,
            allow_redirects=True,
            stream=False
        )
        redirect_chain = [r.url for r in resp.history] + [resp.url]
        html = resp.text
        status = resp.status_code
        headers = dict(resp.headers)
        crawled_with_js = False

        # JS render heuristic check
        if use_js and js_render_available():
            text_length = len(BeautifulSoup(html, "html.parser").get_text(strip=True))
            has_spa_root = (
                '<div id="root">' in html or
                '<div id="app">' in html or
                'data-reactroot' in html or
                '__NEXT_DATA__' in html
            )
            if text_length < 300 and has_spa_root:
                js_html = render_with_js(resp.url)
                if js_html:
                    html = js_html
                    crawled_with_js = True

        return html, status, redirect_chain, headers, crawled_with_js

    except requests.exceptions.TooManyRedirects:
        return "", 310, [url], {}, False
    except requests.exceptions.Timeout:
        return "", 408, [url], {}, False
    except requests.exceptions.ConnectionError:
        # retry once
        time.sleep(2)
        try:
            resp = session.get(url, timeout=REQUEST_TIMEOUT, allow_redirects=True)
            redirect_chain = [r.url for r in resp.history] + [resp.url]
            return resp.text, resp.status_code, redirect_chain, dict(resp.headers), False
        except Exception:
            return "", 0, [url], {}, False
    except Exception as e:
        print(f"[WARN] Unexpected error fetching {url}: {e}", file=sys.stderr)
        return "", 0, [url], {}, False


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

    if checker.is_allowed(start_url):
        queue.append(start_url)
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
        html, status, redirect_chain, headers, crawled_with_js = fetch_page(
            url, session, args.use_js_render
        )
        visited.add(url)

        # Skip empty responses
        if not html and status == 0:
            pages.append({
                "url": url,
                "status_code": 0,
                "final_url": url,
                "redirect_chain": [],
                "canonical": None,
                "meta_robots": "",
                "x_robots_tag": "",
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
                "raw_html_length": 0
            })
            continue

        page_data = extract_page_data(url, html, status, redirect_chain, headers, crawled_with_js)
        pages.append(page_data)

        # Enqueue internal links from successful pages
        if status < 400:
            for link in page_data["links"]:
                href = link["href"]
                if (link["is_internal"] and
                        href not in visited and
                        href not in queue and
                        not should_skip_url(href) and
                        checker.is_allowed(href)):
                    queue.append(href)

    crawl_end = datetime.now(timezone.utc)

    snapshot = {
        "crawl_meta": {
            "start_url": start_url,
            "crawl_started_at": crawl_start.isoformat().replace("+00:00", "Z"),
            "crawl_ended_at": crawl_end.isoformat().replace("+00:00", "Z"),
            "pages_crawled": len(pages),
            "max_pages": args.max_pages,
            "robots_txt_respected": True,
            "robots_txt_url": checker.robots_url,
            "robots_txt_status": robots_status,
            "disallowed_paths": disallowed_paths,
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
