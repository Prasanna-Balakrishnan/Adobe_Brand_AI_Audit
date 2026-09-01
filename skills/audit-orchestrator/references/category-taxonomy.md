# Category Taxonomy — Brand AI-Readiness Audit

This document defines the two allowed categories, their sub-domains, and the
`check_id` prefix registry for each audit skill.

---

## Categories

### `discoverability`
Findings that affect whether AI assistants can **find, read, and correctly represent**
the brand's information.

Sub-domains:
- **crawlability** — can crawlers access the content at all?
- **structured-data** — is machine-readable markup present and valid?
- **extractability** — are key facts stated as explicit plain text?
- **entity-identity** — can the brand be uniquely identified?
- **freshness** — are facts current and cross-verifiable?

### `engagement`
Findings that affect whether **human visitors who do arrive** understand the site
and take action.

Sub-domains:
- **navigation** — can users find their way around?
- **orientation** — do users know where they are and what the site does?
- **cta** — are there clear calls to action?
- **dead-ends** — are there pages with no onward path?
- **value-proposition** — is the brand's offering clearly stated?

---

## Check ID Prefix Registry

Each skill owns a unique prefix. `check_id` values must be `PREFIX-NNN` (e.g. `CRA-001`).

| Skill | Prefix | Example |
|-------|--------|---------|
| crawlability-render-audit | `CRA` | `CRA-001` |
| structured-data-content-audit | `SDC` | `SDC-001` |
| entity-identity-audit | `ENT` | `ENT-001` |
| freshness-corroboration-audit | `FRS` | `FRS-001` |
| engagement-audit | `ENG` | `ENG-001` |
| proactive-opportunities-audit | `PRO` | `PRO-001` |

### Prefix Rules
1. Each prefix is **globally unique** across the entire marketplace.
2. Numbers are **zero-padded to 3 digits** (`001`, `002`, ...).
3. The orchestrator assigns the final `id` (`F-001`, `F-002`, ...) during normalization;
   `check_id` is the skill-internal identifier preserved in `source_skill`.

---

## Tags Registry (Common Tags)

Tags are freeform but these standard tags should be reused when applicable:

| Tag | Use when |
|-----|----------|
| `json-ld` | JSON-LD markup is involved |
| `schema-org` | schema.org type usage |
| `robots-txt` | robots.txt directive |
| `noindex` | noindex meta tag or header |
| `canonical` | canonical URL tag |
| `redirect` | HTTP redirect issues |
| `broken-link` | Broken internal/external links |
| `alt-text` | Image alt text |
| `heading-structure` | H1/H2 hierarchy |
| `meta-description` | Meta description tag |
| `page-title` | `<title>` tag |
| `thin-content` | Low word count pages |
| `stale-content` | Outdated date signals |
| `entity-name` | Brand/org name consistency |
| `author-attribution` | Author metadata |
| `value-proposition` | Site value statement |
| `navigation` | Site navigation structure |
| `cta` | Call-to-action elements |
| `dead-end` | Pages with no onward links |
| `entity-disambiguation` | Ambiguous entity identity |
| `js-render` | JavaScript rendering dependency |

---

## Category Assignment Rules

1. If a finding affects **both** categories (e.g. missing alt text harms both
   crawlability and accessibility), assign the **primary** failure mechanism's category.
2. The `proactive-opportunities-audit` may use either category for recommendations,
   but must not duplicate any `finding.category` + `finding.title` combination.
3. `strengths` objects follow the same two-value enum.
