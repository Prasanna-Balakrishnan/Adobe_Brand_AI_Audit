---
name: agent-discoverability-audit
description: >
  Evaluates whether important website information is structured and exposed in a way
  that makes it useful for AI agents, search systems, and marketplace-style discovery.
  Checks canonical entry points, machine-actionable metadata on important pages,
  link-graph reachability, agent-readable summaries, and cross-page relationship signals.
  All findings are weighted by page_importance_score so high-value pages are prioritized.
---

# Agent Discoverability Audit

## Purpose

Determines whether an AI agent or search system that discovers this website can:

1. **Navigate** to its most important pages from a canonical entry point.
2. **Read** machine-readable metadata (title, meta description, OG, JSON-LD) on all
   important pages without needing to render or scrape body text.
3. **Understand** the scope and relationships of pages (canonical paths, cross-page links).
4. **Act** on discovered information (structured pricing, contact, offers, entity data).

## Check IDs

| ID      | Title |
|---------|-------|
| AGD-001 | Important pages lack machine-readable summary metadata |
| AGD-002 | High-importance page not reachable from homepage link-graph |
| AGD-003 | Important pages missing agent-actionable structured data |
| AGD-004 | Missing sitemap or feed signal for bulk agent discovery |
| AGD-005 | Important pages have non-canonical URL patterns |
| AGD-006 | Cluster isolation: related content pages not interlinked |
| AGD-007 | Thin agent-visible content on important page |

## Anti-Overfitting Rules

- Does NOT assume any specific industry, CMS, schema type, or domain.
- Uses only evidence from the shared crawl snapshot.
- Context-aware: only applies checks relevant to observed page types.
- Results are deterministic across identical snapshots.
