# Extractability Checks — Content Accessibility for AI Agents

All checks use only data from `snapshot.json`. Check IDs use prefix `SDC` (2xx range).

---

## SDC-201 — Key facts locked in images (HIGH)

**Category:** discoverability
**Confidence:** medium (heuristic: image count vs text length)

**Trigger:** A page has many images (>5) relative to its visible text (<500 chars) AND
many images lack alt text. This suggests important content (prices, specs, features)
may be locked in images with no textual alternative.

**Evidence:** Count of images without alt text vs. total images; visible_text_length
of affected pages. List affected URLs.

**Suggested action:** Add descriptive alt text to all images; duplicate key factual
information (prices, specs, feature lists) as visible plain text alongside images.

---

## SDC-202 — Thin visible text on content pages (MEDIUM)

**Category:** discoverability
**Confidence:** high

**Trigger:** Pages that are NOT homepage or navigation-only have `visible_text_length < 300`.

**Evidence:** List URLs with their visible text lengths.

**Suggested action:** Expand content pages with substantive plain text that AI
assistants can cite. Aim for at least 300–500 characters per content page.

---

## SDC-203 — Missing alt text on images (MEDIUM)

**Category:** discoverability
**Confidence:** high

**Trigger:** >50% of images across crawled pages have empty `alt` attributes.

**Evidence:** Count of images without alt / total images; ratio; list URLs of pages
with the most missing alt text.

**Suggested action:** Add descriptive alt text to every meaningful image. Use empty
alt (`alt=""`) only for decorative images.

---

## SDC-204 — Key factual content absent in page text (MEDIUM)

**Category:** discoverability
**Confidence:** medium (heuristic)

**Trigger:** Pages with product/service URL patterns have very low visible text (<300
chars) combined with zero JSON-LD. Both content channels (plain text + structured
data) are absent.

**Evidence:** Count of pages where both text and JSON-LD are absent; list URLs.

**Suggested action:** State key facts (product names, prices, specifications,
availability) both as visible plain text AND as schema.org structured data.

---

## SDC-205 — No descriptive page titles found (MEDIUM)

**Category:** discoverability
**Confidence:** high

**Trigger:** More than 25% of pages have `title` that is either empty or fewer than
10 characters.

**Evidence:** Count of pages with short/empty titles; list URLs with their titles.

**Suggested action:** Write unique, descriptive titles for every page. Titles should
include the brand name and page topic (e.g., "Product Name — BrandName").
