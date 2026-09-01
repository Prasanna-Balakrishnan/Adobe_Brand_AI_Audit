# Crawl Policy — site-crawler

This document defines the crawl policy rules and the `snapshot.json` field reference
for the shared crawl engine.

---

## Crawl Policy Rules

### 1. Rate Limiting
- Minimum 500 ms delay between requests to the same host.
- Maximum concurrent requests: 1 (sequential crawl by default).
- Honour `Crawl-delay` directive in `robots.txt` if present (minimum 1 s).

### 2. robots.txt Compliance
- Always fetch and parse `robots.txt` before crawling any page.
- Apply disallow rules for both `*` and `Googlebot` user-agents.
- A URL is blocked if ANY matching disallow rule applies.
- `Allow:` directives take precedence over `Disallow:` per standard robots.txt rules.
- If `robots.txt` is unreachable (network error), log a warning and proceed with
  conservative assumptions (only crawl the homepage).

### 3. URL Scope
- Only crawl URLs on the **same origin** (scheme + host + port) as `start_url`.
- Do not crawl:
  - `mailto:`, `tel:`, `javascript:` pseudo-URLs
  - Fragment-only URLs (`#section`)
  - URLs matching disallowed patterns
  - Binary file extensions: `.pdf`, `.zip`, `.doc`, `.xls`, `.ppt`, `.mp4`, `.mp3`
  - URLs with query parameters that are pagination-only (e.g. `?page=2` beyond page 3)

### 4. Redirect Handling
- Follow up to 5 redirects per URL.
- A redirect chain longer than 5 hops is treated as a redirect loop — emit a `CRA` finding.
- Record the full `redirect_chain` in the page record.
- If the final URL is off-origin, do NOT follow; record the page with `status_code` from
  the last on-origin response.

### 5. JS Render Heuristics
Attempt JS render (`render_dom.py`) if ALL of the following are true:
- `use_js_render=true` is set
- `visible_text_length` from raw HTML < 300 characters
- The page contains `<script` tags and `<div id="root">` or `<div id="app">`

### 6. Timeouts
- Per-request timeout: 15 seconds.
- Total crawl timeout: `timeout_seconds` (default 240s).
- If total timeout is reached, stop crawling and serialize what has been collected.

### 7. Error Handling
- HTTP 4xx / 5xx: record the page with the error code; do not enqueue further links from it.
- Connection errors: retry once after 2 seconds; if still failing, record as `status_code: 0`.

---

## snapshot.json Field Reference

### `crawl_meta`

| Field | Type | Description |
|-------|------|-------------|
| `start_url` | string | The URL passed as input |
| `crawl_started_at` | string (ISO-8601) | When crawling began |
| `crawl_ended_at` | string (ISO-8601) | When crawling finished |
| `pages_crawled` | integer | Number of pages in `pages[]` |
| `max_pages` | integer | The configured cap |
| `robots_txt_respected` | boolean | Always `true` |
| `robots_txt_url` | string | The robots.txt URL checked |
| `robots_txt_status` | integer | HTTP status of robots.txt fetch |
| `disallowed_paths` | array\<string\> | Disallowed path prefixes from robots.txt |
| `crawl_timeout_hit` | boolean | `true` if crawl stopped due to timeout |

### `pages[]` — Per-Page Record

| Field | Type | Description |
|-------|------|-------------|
| `url` | string | URL as requested |
| `status_code` | integer | Final HTTP status code (0 = connection error) |
| `final_url` | string | URL after all redirects |
| `redirect_chain` | array\<string\> | Intermediate URLs in redirect chain |
| `canonical` | string \| null | `href` value of `<link rel="canonical">` |
| `meta_robots` | string | Content of `<meta name="robots">` (empty if absent) |
| `x_robots_tag` | string | Value of `X-Robots-Tag` HTTP header (empty if absent) |
| `title` | string | `<title>` text content (empty if absent) |
| `meta_description` | string | `<meta name="description">` content (empty if absent) |
| `h1` | array\<string\> | All `<h1>` text values on the page |
| `headings` | array\<{level, text}\> | All heading tags in document order |
| `json_ld` | array\<object\> | Parsed JSON-LD objects from `<script type="application/ld+json">` |
| `open_graph` | object | `og:*` meta tags as key/value pairs |
| `twitter_card` | object | `twitter:*` meta tags as key/value pairs |
| `links` | array\<{href, text, is_internal}\> | All `<a>` tags on the page |
| `images` | array\<{src, alt, width, height}\> | All `<img>` tags |
| `visible_text_length` | integer | Character count of stripped visible text |
| `visible_text_sample` | string | First 500 characters of visible text |
| `last_modified` | string \| null | From `Last-Modified` header or `<meta>` date |
| `crawled_with_js` | boolean | `true` if Playwright render was used |
| `js_render_available` | boolean | `true` if Playwright is installed |
| `raw_html_length` | integer | Byte length of raw HTML response |
