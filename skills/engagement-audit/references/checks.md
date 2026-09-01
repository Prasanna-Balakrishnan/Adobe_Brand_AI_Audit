# Engagement Audit — Check Definitions

All checks use only data from `snapshot.json`. Check IDs use prefix `ENG`.

---

## ENG-001 — No primary CTA on homepage (HIGH)

**Category:** engagement
**Confidence:** medium (heuristic: link text analysis)

**Trigger:** The homepage has no link whose text matches CTA patterns:
"get started", "try", "sign up", "register", "buy", "shop", "contact us",
"book", "request", "learn more", "start free", "demo", "download".

**Evidence:** Confirm no matching link text on the homepage. List the actual link
texts found (up to 10).

**Suggested action:** Add a prominent primary CTA button above the fold on the
homepage. The CTA should clearly state the next step for a new visitor.

---

## ENG-002 — Homepage lacks a clear value proposition (HIGH)

**Category:** engagement
**Confidence:** medium

**Trigger:** The homepage has fewer than 50 visible characters in the first H1/H2
heading, OR the visible text sample contains none of the terms "help", "solution",
"platform", "service", "product", "tool", "enables", "makes", "provides", "lets",
"for [audience]", and the visible text is short (<200 chars).

**Evidence:** Show the visible_text_sample and H1/H2 texts from the homepage.

**Suggested action:** Add a concise headline (H1) that states who you help and how,
followed by a sub-headline with one key benefit.

---

## ENG-003 — Navigation has no visible labels (HIGH)

**Category:** engagement
**Confidence:** medium

**Trigger:** The set of internal link texts from the homepage contains fewer than 3
distinct non-empty strings that are longer than 2 characters (suggesting icon-only
or image-only navigation).

**Evidence:** List the homepage's internal link texts.

**Suggested action:** Add visible text labels to all navigation items. Icon-only
navigation is inaccessible and prevents AI assistants from understanding site structure.

---

## ENG-004 — Dead-end pages (no outbound internal links) (MEDIUM)

**Category:** engagement
**Confidence:** high

**Trigger:** >15% of crawled pages with HTTP 200 have zero internal links in their
`links` array (pages with no path forward for visitors).

**Evidence:** Count of dead-end pages / total 200 pages; list up to 5 dead-end URLs.

**Suggested action:** Add navigation links, related content, or a site-wide footer
to ensure every page has at least one onward path.

---

## ENG-005 — No About page or similar orientation content (MEDIUM)

**Category:** engagement
**Confidence:** medium

**Trigger:** No crawled URL matches `/about`, `/who`, `/story`, `/team`, `/company`
and no page title contains "About" or "Who we are". (Same detection as ENT-003 but
reported for engagement category.)

**Evidence:** Confirm absence in URL list.

**Suggested action:** Create an About page to orient first-time visitors and explain
who is behind the site.

---

## ENG-006 — Navigation depth > 4 levels (MEDIUM)

**Category:** engagement
**Confidence:** medium (heuristic: URL path depth)

**Trigger:** >25% of crawled pages have URL path depth > 4 levels
(e.g. `/a/b/c/d/e` = depth 5).

**Evidence:** List pages with deep paths; show their depths.

**Suggested action:** Flatten the site architecture so important content is
reachable within 3 click-levels from the homepage.

---

## ENG-007 — Thin pages with no engagement signals (MEDIUM)

**Category:** engagement
**Confidence:** medium

**Trigger:** Pages with `visible_text_length < 150` AND zero internal links AND
zero images — likely placeholder or error pages that are being served to users.

**Evidence:** List the pages and their metrics.

**Suggested action:** Remove or consolidate stub pages. Ensure any published page
has meaningful content and at least one navigation link.

---

## ENG-008 — No contact/support link from any page (LOW)

**Category:** engagement
**Confidence:** medium

**Trigger:** No crawled page's link set contains a link whose text matches "contact",
"support", "help", "chat", "reach us", "get help".

**Evidence:** Confirm absence of contact-intent link text across all pages.

**Suggested action:** Add a "Contact" or "Support" link to the site header or footer
on every page.

---

## Strengths to Detect

| Condition | Strength title | Category |
|-----------|---------------|----------|
| Homepage has clear CTA | "Homepage has a clear primary call-to-action" | engagement |
| 0 dead-end pages | "No dead-end pages found — all pages have onward navigation" | engagement |
| Navigation has visible labels | "Site navigation has descriptive text labels" | engagement |
