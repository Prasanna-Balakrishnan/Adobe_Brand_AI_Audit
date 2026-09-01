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

JACCARD_THRESHOLD = 0.15


def tokenize(text: str) -> set:
    """Lowercase, strip punctuation, split into tokens, remove stopwords."""
    stop = {"the", "a", "an", "is", "are", "was", "were", "on", "at", "of",
            "in", "and", "or", "to", "for", "with", "from", "by", "all",
            "no", "not", "any", "has", "have", "had", "this", "that", "it",
            "its", "be", "as", "than", "which", "when", "where", "if"}
    tokens = re.findall(r'\b[a-z]{3,}\b', text.lower())
    return {t for t in tokens if t not in stop}


def jaccard(set_a: set, set_b: set) -> float:
    if not set_a and not set_b:
        return 0.0
    intersection = len(set_a & set_b)
    union = len(set_a | set_b)
    return intersection / union if union else 0.0


def urls_overlap(urls_a: list, urls_b: list) -> bool:
    return bool(set(urls_a) & set(urls_b))


def are_near_duplicates(a: dict, b: dict) -> bool:
    """Return True if two findings should be grouped."""
    # Must be same category
    if a["category"] != b["category"]:
        return False
    # Must be from different skills (same-skill dedup handled in normalize)
    if a["source_skill"] == b["source_skill"]:
        return False
    # Must have overlapping affected_urls
    if not urls_overlap(a["affected_urls"], b["affected_urls"]):
        return False
    # Must have keyword overlap in title + evidence
    tokens_a = tokenize(a["title"] + " " + a["evidence"])
    tokens_b = tokenize(b["title"] + " " + b["evidence"])
    return jaccard(tokens_a, tokens_b) >= JACCARD_THRESHOLD


def merge_findings(primary: dict, secondary: dict) -> dict:
    """Merge secondary into primary. Primary is the representative finding."""
    # Combine affected_urls (deduplicated)
    merged_urls = list(dict.fromkeys(primary["affected_urls"] + secondary["affected_urls"]))
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

    # Assign final F-NNN IDs in order
    for idx, finding in enumerate(result, start=1):
        finding["id"] = f"F-{idx:03d}"

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
