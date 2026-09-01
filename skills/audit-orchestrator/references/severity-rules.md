# Severity Rules — Brand AI-Readiness Audit

This document defines severity levels, classification criteria, and the deterministic
`ai_readiness_score` formula. All audit skills must assign severity using these rules.

---

## Severity Levels

### CRITICAL
The site is effectively invisible or unusable — an AI assistant would fail entirely.

**Criteria (any one is sufficient):**
- `robots.txt` blocks all crawlers on root path
- `noindex` on all crawled pages
- HTTP 5xx on the homepage
- Zero pages successfully crawled (crawl completely blocked)
- Brand name cannot be identified on any crawled page
- Site returns identical boilerplate for all URLs (cloaking signal)

**Effect on score:** −25 per finding

---

### HIGH
A significant barrier that substantially reduces AI discoverability or engagement —
a knowledgeable human would notice it immediately.

**Criteria:**
- `noindex` on the majority (>50%) of crawled pages
- Missing JSON-LD on all product/service pages
- Homepage has no discernible H1
- No canonical tag on any page
- Broken internal links on >30% of pages
- Redirect loop on homepage or top navigation URLs
- No descriptive alt text on >50% of images
- No About / Contact page detected
- Organization name inconsistent across >50% of pages
- All key facts (prices, specs) locked in images with no alt text
- Navigation has no visible labels
- No primary CTA on homepage

**Effect on score:** −10 per finding

---

### MEDIUM
A meaningful gap that a skilled optimizer would fix in a normal sprint.

**Criteria:**
- Missing JSON-LD on *some* pages (25–50%)
- Canonical tag missing on *some* pages (25–50%)
- Stale date signals (last-modified > 12 months) on >30% of pages
- Internally contradicting facts across pages
- Author attribution missing on blog/article pages
- `<title>` or `meta description` missing on >25% of pages
- Thin content (visible-text < 200 words) on >25% of pages
- Navigation depth > 4 levels on most paths
- Dead-end pages (no outbound links) on >15% of pages
- Multiple H1 tags on >25% of pages

**Effect on score:** −4 per finding

---

### LOW
A polish item — noticeable to an expert, unlikely to block discoverability alone.

**Criteria:**
- Missing or short `meta description` on a minority of pages (<25%)
- Schema.org type used is valid but sub-optimal (e.g. `Thing` instead of `Organization`)
- Minor heading hierarchy gaps (H2 before H1 on isolated pages)
- A few broken internal links (<10% of pages)
- Isolated stale-date signals
- Minor entity name variation (e.g. "Acme" vs "Acme Inc" on one page)

**Effect on score:** −1 per finding

---

## AI Readiness Score Formula

```
score = max(0, 100 − (critical × 25) − (high × 10) − (medium × 4) − (low × 1))
```

Implemented in `scripts/score.py`. The score is an integer in `[0, 100]`.

### Score Bands

| Band | Range | Meaning |
|------|-------|---------|
| Excellent | 90–100 | AI-ready; minor polish only |
| Good | 75–89 | AI-findable with small gaps |
| Fair | 50–74 | Noticeable barriers; prioritize high findings |
| Poor | 25–49 | Major barriers; AI citations unlikely |
| Critical | 0–24 | Effectively invisible to AI assistants |

---

## Severity Assignment Rules (for audit skill authors)

1. **Do not upgrade severity** based on assumed intent — only on observed evidence.
2. **Threshold-based rules win**: if the percentage threshold for HIGH is not met,
   downgrade to MEDIUM. Use the exact thresholds above.
3. When in doubt between two levels, choose the **lower** one to avoid false positives.
4. **`confidence` must be set consistently with the check type:**
   - Parsed/mechanical check → `"high"`
   - Heuristic/text-based → `"medium"`
   - Estimated/inferred → `"low"`
5. A finding with `confidence: "low"` must not be assigned severity `"critical"`.
