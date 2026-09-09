#!/usr/bin/env python3
"""
deduplicate_findings.py — Clusters near-duplicate findings into root_cause_groups
and assigns final F-NNN IDs.

Deduplication rule: findings from DIFFERENT skills that share:
  - same category
  - overlapping affected_urls (at least 1 URL in common)
  - keyword overlap in title/evidence (Jaccard similarity >= 0.15)

These are merged into a single root_cause_group. One representative finding is
kept; others are merged into it (their affected_urls are combined, evidence
extended, and source_skill becomes a list). All findings in a group share the
same root_cause_group ID (RC-NNN).

Usage (called by build_report.py):
    from deduplicate_findings import deduplicate
    deduped = deduplicate(normalized_findings)
"""

import json
import re
import sys
from typing import Any
from urllib.parse import urlparse

JACCARD_THRESHOLD = 0.15

STOP_WORDS = frozenset({
    "the", "a", "an", "is", "are", "was", "were", "on", "at", "of",
    "in", "and", "or", "to", "for", "with", "from", "by", "all",
    "no", "not", "any", "has", "have", "had", "this", "that", "it",
    "its", "be", "as", "than", "which", "when", "where", "if"
})
TOKEN_PATTERN = re.compile(r'\b[a-z]{3,}\b')
SPECIFIC_ROOT_TAGS = frozenset({"about-page", "contact-page", "canonical", "page-title", "thin-content"})


def tokenize(text: str) -> set:
    """Lowercase, strip punctuation, split into tokens, remove stopwords."""
    if not text:
        return set()
    tokens = TOKEN_PATTERN.findall(text.lower())
    return {t for t in tokens if t not in STOP_WORDS}


def jaccard(set_a: set, set_b: set) -> float:
    if not set_a and not set_b:
        return 0.0
    intersection = len(set_a & set_b)
    union = len(set_a | set_b)
    return intersection / union if union else 0.0


def normalize_url_for_dedup(url: str) -> str:
    if not isinstance(url, str):
        return ""
    p = urlparse(url)
    scheme = (p.scheme or "").lower()
    netloc = (p.netloc or "").lower()
    if netloc.endswith(":80") and scheme == "http":
        netloc = netloc[:-3]
    elif netloc.endswith(":443") and scheme == "https":
        netloc = netloc[:-4]
    path = (p.path or "").rstrip("/")
    if not path:
        path = "/"
    return f"{scheme}://{netloc}{path}".lower()


def urls_overlap(urls_a: list, urls_b: list, norm_a: set = None, norm_b: set = None) -> bool:
    if not urls_a or not urls_b:
        return False
    if set(urls_a) & set(urls_b):
        return True
    if norm_a is not None and norm_b is not None:
        return bool(norm_a & norm_b)
    norm_a = {normalize_url_for_dedup(u) for u in urls_a if u}
    norm_b = {normalize_url_for_dedup(u) for u in urls_b if u}
    return bool(norm_a & norm_b)


def are_near_duplicates(a: dict, b: dict) -> bool:
    """Return True if two findings should be grouped."""
    # Check if essentially identical recommendations with overlapping affected_urls
    sa_a = a.get("_sa_text")
    if sa_a is None:
        if isinstance(a.get("suggested_action"), dict):
            sa_a = (a["suggested_action"].get("summary") or "").strip().lower()
        elif isinstance(a.get("suggested_action"), str):
            sa_a = a["suggested_action"].strip().lower()
        else:
            sa_a = ""

    sa_b = b.get("_sa_text")
    if sa_b is None:
        if isinstance(b.get("suggested_action"), dict):
            sa_b = (b["suggested_action"].get("summary") or "").strip().lower()
        elif isinstance(b.get("suggested_action"), str):
            sa_b = b["suggested_action"].strip().lower()
        else:
            sa_b = ""

    norm_a = a.get("_norm_urls")
    norm_b = b.get("_norm_urls")
    has_overlap = urls_overlap(a.get("affected_urls", []), b.get("affected_urls", []), norm_a, norm_b)

    if sa_a and sa_b and has_overlap:
        if sa_a == sa_b:
            return True
        sa_toks_a = a.get("_sa_toks") if a.get("_sa_toks") is not None else tokenize(sa_a)
        sa_toks_b = b.get("_sa_toks") if b.get("_sa_toks") is not None else tokenize(sa_b)
        if len(sa_toks_a) >= 4 and len(sa_toks_b) >= 4 and jaccard(sa_toks_a, sa_toks_b) >= 0.85:
            return True

    # Must be from different skills (same-skill dedup handled in normalize)
    if a["source_skill"] == b["source_skill"]:
        return False
    # Must have overlapping affected_urls
    if not has_overlap:
        return False

    # Check for shared specific root-cause tags across skills
    tags_a = a.get("_tag_set") if a.get("_tag_set") is not None else set(a.get("tags", []))
    tags_b = b.get("_tag_set") if b.get("_tag_set") is not None else set(b.get("tags", []))
    if tags_a & tags_b & SPECIFIC_ROOT_TAGS:
        return True

    # Check keyword overlap in title + evidence
    tokens_a = a.get("_tokens") if a.get("_tokens") is not None else tokenize(a["title"] + " " + a["evidence"])
    tokens_b = b.get("_tokens") if b.get("_tokens") is not None else tokenize(b["title"] + " " + b["evidence"])
    jacc = jaccard(tokens_a, tokens_b)

    # Same category: use standard threshold
    if a["category"] == b["category"]:
        return jacc >= JACCARD_THRESHOLD

    # Different category: require high lexical overlap (>= 0.35)
    return jacc >= 0.35


def merge_findings(primary: dict, secondary: dict) -> dict:
    """Merge secondary into primary. Primary is the representative finding."""
    # Combine affected_urls (deduplicated & sorted)
    merged_urls = sorted(list(dict.fromkeys(primary["affected_urls"] + secondary["affected_urls"])))
    primary["affected_urls"] = merged_urls

    # Extend evidence
    sec_evidence = secondary["evidence"]
    if sec_evidence not in primary["evidence"]:
        primary["evidence"] += f" [Also: {secondary['source_skill']}: {sec_evidence[:200]}]"

    # Track all source skills
    if "source_skills" not in primary:
        primary["source_skills"] = [primary["source_skill"]]
    if secondary["source_skill"] not in primary["source_skills"]:
        primary["source_skills"].append(secondary["source_skill"])

    # Merge tags
    for tag in secondary.get("tags", []):
        if tag not in primary["tags"]:
            primary["tags"].append(tag)

    return primary


def deduplicate(findings: list[dict]) -> list[dict]:
    """
    Cluster near-duplicate findings, assign RC-NNN group IDs and F-NNN finding IDs.

    Returns a list of representative findings (one per group + all unique findings),
    each with:
      - id: "F-NNN"
      - root_cause_group: "RC-NNN" or null
    """
    n = len(findings)
    if n == 0:
        return []

    # Precompute tokens and caches in O(N)
    for f in findings:
        f["_tokens"] = tokenize(f.get("title", "") + " " + f.get("evidence", ""))
        sa = ""
        if isinstance(f.get("suggested_action"), dict):
            sa = (f["suggested_action"].get("summary") or "").strip().lower()
        elif isinstance(f.get("suggested_action"), str):
            sa = f["suggested_action"].strip().lower()
        f["_sa_text"] = sa
        f["_sa_toks"] = tokenize(sa) if sa else set()
        f["_tag_set"] = set(f.get("tags", []))
        f["_norm_urls"] = {normalize_url_for_dedup(u) for u in f.get("affected_urls", []) if u}

    # Union-find for grouping
    parent = list(range(n))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(x, y):
        px, py = find(x), find(y)
        if px != py:
            parent[py] = px

    # Build groups
    for i in range(n):
        for j in range(i + 1, n):
            if are_near_duplicates(findings[i], findings[j]):
                union(i, j)

    # Collect groups
    groups: dict[int, list[int]] = {}
    for i in range(n):
        root = find(i)
        groups.setdefault(root, []).append(i)
    for i in range(n):
        root = find(i)
        groups.setdefault(root, []).append(i)

    # Assign RC-NNN to groups with > 1 member
    rc_counter = 1
    group_rc: dict[int, str | None] = {}
    for root, members in groups.items():
        if len(members) > 1:
            group_rc[root] = f"RC-{rc_counter:03d}"
            rc_counter += 1
        else:
            group_rc[root] = None

    # Build output: one representative per group
    result = []
    processed_roots = set()

    for i in range(n):
        root = find(i)
        if root in processed_roots:
            continue
        processed_roots.add(root)
        members = groups[root]
        rc = group_rc[root]

        if len(members) == 1:
            # Unique finding — no dedup needed
            rep = dict(findings[members[0]])
            rep["root_cause_group"] = rc
            result.append(rep)
        else:
            # Merge all members into the first (primary) finding
            primary_idx = members[0]
            rep = dict(findings[primary_idx])
            rep["root_cause_group"] = rc
            for j in members[1:]:
                rep = merge_findings(rep, findings[j])
            # Combine source_skills into source_skill for display
            if "source_skills" in rep and len(rep["source_skills"]) > 1:
                rep["source_skill"] = rep["source_skills"][0]  # keep primary
                rep["merged_from_skills"] = rep.pop("source_skills")
            elif "source_skills" in rep:
                rep["source_skill"] = rep.pop("source_skills")[0]
            result.append(rep)

    # Assign final F-NNN IDs in order and clean up internal helper fields
    temp_keys = ("_tokens", "_sa_text", "_sa_toks", "_tag_set", "_norm_urls")
    for idx, finding in enumerate(result, start=1):
        finding["id"] = f"F-{idx:03d}"
        for k in temp_keys:
            finding.pop(k, None)

    for f in findings:
        for k in temp_keys:
            f.pop(k, None)

    return result


if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser()
    p.add_argument("--input", required=True, help="Path to normalized_findings.json")
    p.add_argument("--output", default="deduplicated_findings.json")
    args = p.parse_args()

    try:
        with open(args.input, encoding="utf-8") as f:
            data = json.load(f)
        findings = data.get("findings", data) if isinstance(data, dict) else data
    except Exception as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        sys.exit(1)

    deduped = deduplicate(findings)

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump({"findings": deduped}, f, indent=2, ensure_ascii=False)

    print(f"[OK] {len(deduped)} findings after deduplication → {args.output}", file=sys.stderr)
