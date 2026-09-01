#!/usr/bin/env python3
"""
render_dom.py — Optional headless JS rendering via Playwright.

Called by crawl.py when:
  - --use-js-render is set
  - visible_text_length from raw HTML < 300 characters
  - The page contains SPA root markers (<div id="root">, <div id="app">, etc.)

If Playwright is not installed, js_render_available() returns False and
this module degrades gracefully — the crawler continues with raw HTML.

Usage (from crawl.py):
    from render_dom import render_with_js, js_render_available
    html = render_with_js("https://example.com")
"""

import sys

_PLAYWRIGHT_AVAILABLE = None


def js_render_available() -> bool:
    """Return True if Playwright is installed and usable."""
    global _PLAYWRIGHT_AVAILABLE
    if _PLAYWRIGHT_AVAILABLE is None:
        try:
            from playwright.sync_api import sync_playwright  # noqa: F401
            _PLAYWRIGHT_AVAILABLE = True
        except ImportError:
            _PLAYWRIGHT_AVAILABLE = False
            print(
                "[INFO] Playwright not installed; JS rendering disabled. "
                "Install with: pip install playwright && playwright install chromium",
                file=sys.stderr
            )
    return _PLAYWRIGHT_AVAILABLE


def render_with_js(url: str, timeout_ms: int = 10000) -> str | None:
    """
    Render a page with Playwright (headless Chromium) and return full HTML.

    Args:
        url: The URL to render.
        timeout_ms: Navigation timeout in milliseconds (default 10s).

    Returns:
        The page's full HTML after JS execution, or None on failure.
    """
    if not js_render_available():
        return None

    try:
        from playwright.sync_api import sync_playwright, Error as PlaywrightError

        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent=(
                    "BrandAuditBot/1.0 "
                    "(+https://github.com/adobe-hackathon/brand-ai-readiness-audit)"
                ),
                extra_http_headers={
                    "Accept-Language": "en-US,en;q=0.9"
                }
            )
            page = context.new_page()

            try:
                page.goto(url, wait_until="networkidle", timeout=timeout_ms)
                # Wait for common SPA root elements to appear
                for selector in ["#root", "#app", "[data-reactroot]", "main"]:
                    try:
                        page.wait_for_selector(selector, timeout=2000)
                        break
                    except PlaywrightError:
                        continue
                html = page.content()
                return html

            except PlaywrightError as e:
                print(f"[WARN] Playwright navigation failed for {url}: {e}", file=sys.stderr)
                # Try to get whatever content is available
                try:
                    return page.content()
                except Exception:
                    return None
            finally:
                context.close()
                browser.close()

    except Exception as e:
        print(f"[WARN] Playwright render error for {url}: {e}", file=sys.stderr)
        return None
