#!/usr/bin/env python3
"""
normalize_findings.py — Assigns F-NNN IDs, enforces enum values, attaches source_skill.

Input: list of raw intermediate skill outputs (dicts with skill name + findings[]).
Output: normalized_findings.json — list of Finding objects ready for deduplication.

Usage (called by build_report.py):
    from normalize_findings import normalize_all
    normalized = normalize_all(skill_outputs)
"""

import json
import sys
from typing import Any

VALID_SEVERITIES = {"critical", "high", "medium", "low"}
VALID_CATEGORIES = {"discoverability", "engagement"}
VALID_CONFIDENCES = {"high", "medium", "low"}

# Severity ordering for sort key
SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}


def normalize_finding(raw: dict, skill_name: str) -> dict | None:
    """
    Validate and normalize a single raw finding from a skill.
    Returns None if the finding is invalid and should be dropped.
    """
    required_fields = ["check_id", "title", "category", "severity",
                        "affected_urls", "evidence", "suggested_action"]
    for field in required_fields:
        if field not in raw:
            print(f"[WARN] Dropping finding from {skill_name}: missing field '{field}'",
                  file=sys.stderr)
            return None

    # Enforce enum: severity
    severity = str(raw.get("severity", "")).lower()
    if severity not in VALID_SEVERITIES:
        print(f"[WARN] Dropping finding '{raw.get('check_id')}' from {skill_name}: "
              f"invalid severity '{severity}'", file=sys.stderr)
        return None

    # Enforce enum: category
    category = str(raw.get("category", "")).lower()
    if category not in VALID_CATEGORIES:
        print(f"[WARN] Dropping finding '{raw.get('check_id')}' from {skill_name}: "
              f"invalid category '{category}'", file=sys.stderr)
        return None

    # Enforce enum: confidence (optional; default to "medium")
    confidence = str(raw.get("confidence", "medium")).lower()
    if confidence not in VALID_CONFIDENCES:
        confidence = "medium"

    # Validate affected_urls
    affected_urls = raw.get("affected_urls", [])
    if not isinstance(affected_urls, list) or len(affected_urls) == 0:
        print(f"[WARN] Dropping finding '{raw.get('check_id')}' from {skill_name}: "
              "empty or invalid affected_urls", file=sys.stderr)
        return None

    # Validate evidence
    evidence = str(raw.get("evidence", "")).strip()
    if not evidence:
        print(f"[WARN] Dropping finding '{raw.get('check_id')}' from {skill_name}: "
              "empty evidence", file=sys.stderr)
        return None

    # Validate suggested_action
    sa = raw.get("suggested_action", {})
    if not isinstance(sa, dict) or not sa.get("summary"):
        print(f"[WARN] Dropping finding '{raw.get('check_id')}' from {skill_name}: "
              "invalid suggested_action", file=sys.stderr)
        return None

    # Normalize suggested_action priority/effort
    sa_priority = str(sa.get("priority", severity)).lower()
    if sa_priority not in VALID_SEVERITIES:
        sa_priority = severity

    sa_effort = str(sa.get("effort", "medium")).lower()
    if sa_effort not in {"low", "medium", "high"}:
        sa_effort = "medium"

    return {
        # id assigned later
        "title": str(raw.get("title", "")).strip(),
        "category": category,
        "severity": severity,
        "confidence": confidence,
        "source_skill": skill_name,
        "check_id": str(raw.get("check_id", "")),
        "tags": [str(t).lower() for t in raw.get("tags", []) if t],
        "affected_urls": sorted(list(dict.fromkeys(str(u) for u in affected_urls if u))),
        "evidence": evidence,
        "root_cause_group": None,  # assigned by deduplicate_findings.py
        "suggested_action": {
            "summary": str(sa.get("summary", "")).strip(),
            "priority": sa_priority,
            "effort": sa_effort
        }
    }


def normalize_all(skill_outputs: list[dict]) -> tuple[list[dict], list[dict]]:
    """
    Process all skill outputs, normalize findings, collect strengths.

    Args:
        skill_outputs: list of {"skill": str, "findings": [...], "strengths": [...]}

    Returns:
        (normalized_findings, all_strengths)
        normalized_findings: sorted by severity then source_skill then check_id
        Findings do not yet have 'id' assigned — that happens after dedup.
    """
    all_findings = []
    all_strengths = []
    seen_check_ids: dict[str, set] = {}  # skill -> set of check_ids

    for output in skill_outputs:
        skill_name = output.get("skill", "unknown-skill")
        seen_check_ids.setdefault(skill_name, set())

        for raw_finding in output.get("findings", []):
            check_id = raw_finding.get("check_id", "")

            # Dedup within same skill
            if check_id in seen_check_ids[skill_name]:
                print(f"[WARN] Duplicate check_id '{check_id}' in {skill_name}; dropping",
                      file=sys.stderr)
                continue
            seen_check_ids[skill_name].add(check_id)

            normalized = normalize_finding(raw_finding, skill_name)
            if normalized:
                all_findings.append(normalized)

        for strength in output.get("strengths", []):
            if isinstance(strength, dict) and strength.get("title"):
                cat = str(strength.get("category", "discoverability")).lower()
                if cat in VALID_CATEGORIES:
                    all_strengths.append({
                        "title": str(strength["title"]).strip(),
                        "category": cat
                    })

    # Sort: severity ASC (critical first), then source_skill alpha, then check_id alpha
    all_findings.sort(key=lambda f: (
        SEVERITY_ORDER.get(f["severity"], 99),
        f["source_skill"],
        f["check_id"]
    ))

    # Deduplicate strengths by title
    seen_strength_titles = set()
    unique_strengths = []
    for s in all_strengths:
        if s["title"] not in seen_strength_titles:
            seen_strength_titles.add(s["title"])
            unique_strengths.append(s)

    return all_findings, unique_strengths


if __name__ == "__main__":
    # CLI mode for testing
    import argparse

    p = argparse.ArgumentParser()
    p.add_argument("--inputs", nargs="+", required=True,
                   help="Paths to skill output JSON files")
    p.add_argument("--output", default="normalized_findings.json")
    args = p.parse_args()

    outputs = []
    for path in args.inputs:
        try:
            with open(path, encoding="utf-8") as f:
                outputs.append(json.load(f))
        except Exception as e:
            print(f"[WARN] Could not load {path}: {e}", file=sys.stderr)

    findings, strengths = normalize_all(outputs)

    result = {"findings": findings, "strengths": strengths}
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print(f"[OK] {len(findings)} normalized findings, {len(strengths)} strengths → {args.output}",
          file=sys.stderr)
