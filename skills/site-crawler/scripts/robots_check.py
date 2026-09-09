#!/usr/bin/env python3
"""
robots_check.py — robots.txt parser and URL allow/disallow checker.

Wraps urllib.robotparser with fallback for malformed robots.txt files and
records the disallowed paths for the snapshot crawl_meta.
"""

import sys
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser
import urllib.request


class RobotsChecker:
    """
    Fetch and parse robots.txt for a given site.

    Attributes:
        robots_url      — The robots.txt URL checked.
        robots_status   — HTTP status of the robots.txt fetch (0 = error).
        disallowed_paths — List of disallowed path prefixes for * or Googlebot.
        crawl_delay     — Crawl-Delay from robots.txt (seconds), or None.
    """

    def __init__(self, start_url: str, user_agent: str = "*"):
        parsed = urlparse(start_url)
        self.robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
        self.user_agent = user_agent
        self.robots_status = 0
        self.disallowed_paths: list[str] = []
        self.sitemaps: list[str] = []
        self.ai_agent_rules: dict[str, list[str]] = {}
        self.crawl_delay: float | None = None
        self._parser = RobotFileParser()
        self._parser.set_url(self.robots_url)
        self._fetch()

    def _fetch(self):
        try:
            req = urllib.request.Request(
                self.robots_url,
                headers={"User-Agent": self.user_agent}
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                self.robots_status = resp.status
                content = resp.read().decode("utf-8", errors="replace")
            self._parser.parse(content.splitlines())
            self._extract_disallowed(content)
            self.crawl_delay = self._parser.crawl_delay(self.user_agent)
        except urllib.error.HTTPError as e:
            self.robots_status = e.code
            print(f"[WARN] robots.txt returned HTTP {e.code}; treating as no restrictions",
                  file=sys.stderr)
        except Exception as e:
            self.robots_status = 0
            print(f"[WARN] Could not fetch robots.txt: {e}; treating as no restrictions",
                  file=sys.stderr)

    def _extract_disallowed(self, content: str):
        """Extract disallowed paths for * and Googlebot agents, sitemaps, and AI crawler rules."""
        applicable_agents = {"*", "googlebot"}
        ai_agents = {"gptbot", "claudebot", "perplexitybot", "ccbot", "anthropic-ai", "google-extended"}
        current_agents: list[str] = []
        collecting_standard = False
        collecting_ai = False

        for line in content.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                if collecting_standard or collecting_ai:
                    current_agents = []
                    collecting_standard = False
                    collecting_ai = False
                continue

            if line.lower().startswith("sitemap:"):
                sm_url = line[len("sitemap:"):].strip()
                if sm_url and sm_url not in self.sitemaps:
                    self.sitemaps.append(sm_url)
                continue

            if line.lower().startswith("user-agent:"):
                agent = line[len("user-agent:"):].strip().lower()
                current_agents.append(agent)
                collecting_standard = any(a in applicable_agents for a in current_agents)
                collecting_ai = any(a in ai_agents for a in current_agents)
            elif line.lower().startswith("disallow:"):
                path = line[len("disallow:"):].strip()
                if path:
                    if collecting_standard and path not in self.disallowed_paths:
                        self.disallowed_paths.append(path)
                    if collecting_ai:
                        for agent in current_agents:
                            if agent in ai_agents:
                                self.ai_agent_rules.setdefault(agent, []).append(path)

    def is_allowed(self, url: str) -> bool:
        """Return True if the URL is allowed to be crawled."""
        # If robots.txt was not found (e.g. 404, 410), failed to fetch, or returned non-200, allow everything (RFC 9309)
        if self.robots_status != 200:
            return True
        try:
            return self._parser.can_fetch(self.user_agent, url)
        except Exception:
            return True
